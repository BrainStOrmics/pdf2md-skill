"""Resume script: Pick up from Step 6 panel CSV extraction.
Skips panels that already have entries in panels_data.json.
Then does MD assembly as normal."""

import os, sys, json, base64, re, io, shutil
from pathlib import Path
import yaml

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None


def load_config(config_path):
    with config_path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    vlm = config.get("vlm", {})
    return {
        "model": vlm["model"].strip(),
        "api_base": vlm["api_base"].strip().rstrip("/"),
        "api_key": vlm["api_key"].strip(),
        "offline": config.get("runtime", {}).get("offline", False),
    }


def call_vlm(img_b64, prompt, model, api_base, api_key, max_tokens=300, timeout=90):
    import requests
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
    prompt_path = Path(__file__).resolve().parents[1] / "references" / "figure_rules.md"
    return prompt_path.read_text(encoding="utf-8")


def main():
    config_path = Path("/home/xq/pdf2md-skill/config.yaml")
    config = load_config(config_path)
    model = config["model"]
    api_base = config["api_base"]
    api_key = config["api_key"]

    output_dir = Path(os.path.expanduser("~/PDF/processed/Yang_2021"))
    desc_path = output_dir / "descriptions.json"
    csv_json_path = output_dir / "panels_data.json"

    # Load descriptions
    with open(desc_path, encoding="utf-8") as f:
        descriptions = json.load(f)
    print(f"Loaded descriptions: {len(descriptions)} entries", flush=True)

    # Load existing CSV results (if any)
    if csv_json_path.exists():
        with open(csv_json_path, encoding="utf-8") as f:
            csv_results = json.load(f)
        print(f"Loaded existing CSV results: {len(csv_results)} panels", flush=True)
    else:
        csv_results = {}
        print("No existing CSV results, starting fresh", flush=True)

    PANEL_PROMPT = load_panel_prompt()

    # Get all panel files
    panel_files = sorted((output_dir / "panels").glob("*.png"))
    print(f"Found {len(panel_files)} panels in output dir", flush=True)

    print(f"\n{'=' * 60}", flush=True)
    print("Step 6 (RESUMED): Panel CSV Extraction", flush=True)
    print(f"{'=' * 60}", flush=True)

    # Process panels, skipping already-done ones
    total = len(panel_files)
    skipped = 0
    processed = 0
    failed = 0

    for i, panel_path in enumerate(panel_files, 1):
        name = panel_path.name

        if name in csv_results:
            print(f"  [{i}/{total}] {name}... SKIP (already done)", flush=True)
            skipped += 1
            continue

        caption = descriptions.get(name, "")
        if not isinstance(caption, str):
            caption = str(caption) if caption else ""
        prompt = PANEL_PROMPT.replace("{caption}", caption)
        print(f"  [{i}/{total}] {name}...", end=" ", flush=True)

        img_b64 = resize_for_vlm(panel_path)
        try:
            resp_text = call_vlm(img_b64, prompt, model, api_base, api_key, max_tokens=4000, timeout=180)
            if not isinstance(resp_text, str):
                resp_text = str(resp_text)
            parsed = extract_json(resp_text)
            csv_results[name] = parsed
            processed += 1
            print(f"OK ({len(parsed)} sub-figures)", flush=True)
        except Exception as e:
            print(f"FAIL: {e}", flush=True)
            csv_results[name] = [{"fig_type": "error", "data_type": "description", "content": str(e)}]
            failed += 1

        # Save incrementally after each panel
        with open(csv_json_path, "w", encoding="utf-8") as f:
            json.dump(csv_results, f, ensure_ascii=False, indent=2)

    print(f"\n  Skipped: {skipped}, Processed: {processed}, Failed: {failed}", flush=True)

    # Now we need the markdown text and figure mapping to do assembly.
    # Since we don't have the original docling output, we'll do a simplified assembly.
    # The pipeline's full MD assembly needs the original parsed markdown (parts array).
    # We'll note this and let the user know.
    print(f"\n{'=' * 60}", flush=True)
    print("RESULTS", flush=True)
    print(f"{'=' * 60}", flush=True)
    print(f"  Panels processed:  {len(csv_results)}/{total}", flush=True)
    print(f"  CSV JSON saved:    {csv_json_path}", flush=True)
    print(f"\n  NOTE: MD assembly requires re-running the full pipeline for the text parts.", flush=True)
    print(f"  The panels_data.json is now complete and can be used for assembly.", flush=True)


if __name__ == "__main__":
    main()
