"""Resume Step 6 of pdf2md pipeline: CSV extraction + MD assembly.
Assumes Steps 1-5 completed (panels/, images/, descriptions.json exist).
Checkpoints after each panel to survive kills."""

import os, sys, json, base64, re, io, argparse
from pathlib import Path
import yaml, requests
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def call_vlm(img_b64, prompt, model, api_base, api_key, max_tokens=300, timeout=90):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
            {"type": "text", "text": prompt},
        ]}],
        "max_tokens": max_tokens,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    r = requests.post(f"{api_base}/chat/completions", json=payload, headers=headers, timeout=timeout)
    r.raise_for_status()
    resp = r.json()
    content = resp["choices"][0]["message"]["content"]
    if isinstance(content, list):
        content = "\n".join(
            item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"
        )
    elif isinstance(content, dict):
        content = content.get("text", str(content))
    return content

def resize_for_vlm(img_path, max_size=1024):
    img = Image.open(img_path)
    w, h = img.size
    if max(w, h) > max_size:
        ratio = max_size / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def extract_json(text):
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if not match:
        raise ValueError("No JSON array found in response")
    return json.loads(match.group(0))

def load_panel_prompt():
    prompt_path = Path(__file__).resolve().parent / "references" / "figure_rules.md"
    return prompt_path.read_text(encoding="utf-8")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("output_dir", help="Existing output directory from Steps 1-5")
    p.add_argument("--config", type=Path, default=Path(__file__).resolve().parent / "config.yaml")
    args = p.parse_args()

    out = Path(args.output_dir)
    config_path = args.config.resolve()
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    vlm = cfg["vlm"]
    model, api_base, api_key = vlm["model"].strip(), vlm["api_base"].strip().rstrip("/"), vlm["api_key"].strip()

    PANEL_PROMPT = load_panel_prompt()
    panels_dir = out / "panels"
    images_dir = out / "images"
    csv_json_path = out / "panels_data.json"
    desc_path = out / "descriptions.json"

    # Load descriptions
    descriptions = json.loads(desc_path.read_text(encoding="utf-8")) if desc_path.exists() else {}

    # Load existing checkpoint
    csv_results = {}
    if csv_json_path.exists():
        csv_results = json.loads(csv_json_path.read_text(encoding="utf-8"))
        print(f"Loaded checkpoint: {len(csv_results)} panels already done")

    # Find all panel PNGs
    panel_files = sorted(panels_dir.glob("*.png"))
    print(f"Total panels: {len(panel_files)}")

    # Process remaining panels
    remaining = [p for p in panel_files if p.name not in csv_results]
    print(f"Remaining: {len(remaining)}")

    for i, panel_path in enumerate(remaining, 1):
        name = panel_path.name
        caption = descriptions.get(name, "")
        if not isinstance(caption, str):
            caption = str(caption) if caption else ""
        prompt = PANEL_PROMPT.replace("{caption}", caption)
        print(f"  [{i}/{len(remaining)}] {name}...", end=" ", flush=True)

        img_b64 = resize_for_vlm(panel_path)
        try:
            resp_text = call_vlm(img_b64, prompt, model, api_base, api_key, max_tokens=4000, timeout=180)
            if not isinstance(resp_text, str):
                resp_text = str(resp_text)
            parsed = extract_json(resp_text)
            csv_results[name] = parsed
            print(f"OK ({len(parsed)} sub-figures)")
        except Exception as e:
            print(f"FAIL: {e}")
            csv_results[name] = [{"fig_type": "error", "data_type": "description", "content": str(e)}]

        # Checkpoint after each panel
        with open(csv_json_path, "w", encoding="utf-8") as f:
            json.dump(csv_results, f, ensure_ascii=False, indent=2)

    # Assemble final MD
    print(f"\n{'=' * 60}", flush=True)
    print("Assembling final markdown...", flush=True)

    # Build markdown from descriptions and panels
    blocks = []
    panel_list = sorted(panel_files, key=lambda p: p.name)
    for panel_path in panel_list:
        name = panel_path.name
        entries = csv_results.get(name, [])
        blocks.append(f"![{name}](panels/{name})\n")
        for entry in entries:
            fig_type = entry.get("fig_type", "")
            data_type = entry.get("data_type", "")
            content = entry.get("content", "")
            blocks.append(f"**Type:** {fig_type} | **Data:** {data_type}\n")
            if data_type == "num_table" and content:
                lines = content.strip().split("\n")
                header = lines[0].split(",")
                blocks.append("| " + " | ".join(header) + " |")
                blocks.append("| " + " | ".join(["---"] * len(header)) + " |")
                for line in lines[1:]:
                    cells = line.split(",")
                    blocks.append("| " + " | ".join(cells) + " |")
                blocks.append("")
            elif data_type == "description" and content:
                blocks.append(f"> {content}\n")
        blocks.append("---\n")

    paper_name = out.name
    final_path = out / f"{paper_name}_complete.md"
    final_path.write_text("\n".join(blocks), encoding="utf-8")

    # Summary
    print(f"\n{'=' * 60}", flush=True)
    print("RESULTS", flush=True)
    print(f"{'=' * 60}", flush=True)
    print(f"  Output dir:     {out}", flush=True)
    print(f"  Final MD:       {final_path} ({final_path.stat().st_size:,} bytes)", flush=True)
    print(f"  CSV JSON:       {csv_json_path}", flush=True)
    print(f"  Panels:         {len(panel_files)}", flush=True)
    print(f"  Captions:       {len(descriptions)}", flush=True)
    print(f"\nDone!", flush=True)

if __name__ == "__main__":
    main()
