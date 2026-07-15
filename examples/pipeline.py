"""Reference pipeline: PDF -> panel detection -> captions -> CSV extraction -> final MD.
This is a REFERENCE script for the pdf2md skill. Adapt paths and config for each PDF."""

import os, sys, json, base64, re, requests, io, shutil, argparse
from pathlib import Path
import numpy as np
import yaml
import concurrent.futures

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import fitz
from PIL import Image
Image.MAX_IMAGE_PIXELS = None


def parse_args():
    p = argparse.ArgumentParser(description="PDF to MD with figure data extraction")
    p.add_argument("pdf", help="Path to the PDF file")
    p.add_argument("--output", "-o", default=None, help="Output directory (default: <pdf_name>-with-csv)")
    p.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "config.yaml",
        help="VLM config file (default: <skill_dir>/config.yaml)",
    )
    p.add_argument("--overwrite", action="store_true", help="Replace managed files in a non-empty output directory")
    p.add_argument("--filter-size", type=int, default=30, help="Min image size in KB (default 30)")
    p.add_argument("--keep-original-images", action="store_true", help="Keep original pic_*.png files in images/ directory (default: delete after processing)")
    return p.parse_args()


def load_config(config_path):
    if not config_path.is_file():
        raise FileNotFoundError(
            f"VLM config not found: {config_path}. "
            "Copy config.example.yaml to config.yaml and fill in your provider settings."
        )

    with config_path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    vlm = config.get("vlm")
    if not isinstance(vlm, dict):
        raise ValueError(f"Missing 'vlm' mapping in VLM config: {config_path}")

    required = ("model", "api_base", "api_key")
    missing = [key for key in required if not isinstance(vlm.get(key), str) or not vlm[key].strip()]
    if missing:
        raise ValueError(f"Missing VLM config values in {config_path}: {', '.join(missing)}")

    runtime = config.get("runtime", {})
    if not isinstance(runtime, dict):
        raise ValueError(f"'runtime' must be a mapping in config: {config_path}")
    offline = runtime.get("offline", False)
    if not isinstance(offline, bool):
        raise ValueError(f"'runtime.offline' must be true or false in config: {config_path}")

    return {
        "model": vlm["model"].strip(),
        "api_base": vlm["api_base"].strip().rstrip("/"),
        "api_key": vlm["api_key"].strip(),
        "offline": offline,
    }


def load_vlm_config(config_path):
    config = load_config(config_path)
    return config["model"], config["api_base"], config["api_key"]


def configure_runtime(config):
    if config["offline"]:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"


def load_panel_prompt():
    prompt_path = Path(__file__).resolve().parents[1] / "references" / "figure_rules.md"
    return prompt_path.read_text(encoding="utf-8")


def resolve_renamed_image(original_path, renamed_images):
    return renamed_images.get(original_path.name, original_path.name)


def prepare_output_dir(output_dir, paper_name, overwrite):
    if output_dir.exists() and any(output_dir.iterdir()) and not overwrite:
        raise FileExistsError(
            f"Output directory is not empty: {output_dir}. "
            "Choose another directory or pass --overwrite."
        )

    if overwrite:
        for directory in (output_dir / "images", output_dir / "panels"):
            if directory.exists():
                shutil.rmtree(directory)
        for file_path in (
            output_dir / "panels_data.json",
            output_dir / "descriptions.json",
            output_dir / f"{paper_name}_complete.md",
        ):
            file_path.unlink(missing_ok=True)

    output_dir.mkdir(exist_ok=True)
    (output_dir / "images").mkdir(exist_ok=True)
    (output_dir / "panels").mkdir(exist_ok=True)


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


def process_single_panel(panel_path, caption, prompt_template, model, api_base, api_key):
    """Process a single panel for CSV extraction - designed for parallel execution"""
    name = panel_path.name
    caption = caption if isinstance(caption, str) else (str(caption) if caption else "")
    prompt = prompt_template.replace("{caption}", caption)

    img_b64 = resize_for_vlm(panel_path)
    try:
        resp_text = call_vlm(img_b64, prompt, model, api_base, api_key, max_tokens=4000, timeout=180)
        if not isinstance(resp_text, str):
            resp_text = str(resp_text)
        parsed = extract_json(resp_text)
        return name, parsed, None
    except Exception as e:
        return name, [{"fig_type": "error", "data_type": "description", "content": str(e)}], e


def extract_json(text):
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if not match:
        raise ValueError("No JSON array found in response")
    return json.loads(match.group(0))


def main():
    args = parse_args()
    config = load_config(args.config.resolve())
    configure_runtime(config)
    model = config["model"]
    api_base = config["api_base"]
    api_key = config["api_key"]

    pdf_path = Path(args.pdf).resolve()
    output_dir = Path(args.output) if args.output else pdf_path.parent / f"{pdf_path.stem}-with-csv"
    prepare_output_dir(output_dir, pdf_path.stem, args.overwrite)

    size_threshold = args.filter_size * 1024

    # ── Step 1: PDF Parsing (single-pass) ──
    print("=" * 60, flush=True)
    print("Step 1: PDF Parsing (single-pass)", flush=True)
    print("=" * 60, flush=True)

    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TableStructureOptions
    from docling.datamodel.pipeline_options import TableFormerMode

    pipeline_opts = PdfPipelineOptions(
        do_ocr=False,
        do_table_structure=True,
        table_structure_options=TableStructureOptions(mode=TableFormerMode.FAST),
        generate_picture_images=True,
        generate_page_images=False,
        images_scale=500/72,
    )

    # Single-pass processing for accurate table extraction
    # (Batched processing causes tables to lose headers and fragment)
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_opts)}
    )
    result = converter.convert(str(pdf_path))
    doc = result.document

    md = doc.export_to_markdown()
    all_tables = doc.tables
    total_pages = len(doc.pages)
    print(f"  Pages: {total_pages}", flush=True)
    print(f"  Pictures: {len(doc.pictures)}", flush=True)
    print(f"  Tables: {len(all_tables)}", flush=True)

    # Save images
    pictures = []
    for i, pic in enumerate(doc.pictures):
        img = pic.get_image(doc=doc)
        if img:
            path = output_dir / "images" / f"pic_{i:03d}.png"
            img.save(str(path), format="PNG")
            pictures.append((i, pic, path))
    print(f"  Saved {len(pictures)} pictures", flush=True)

    # ── Step 2: Image Filtering ──
    FILTER_PROMPT = "Is this a scientific figure/chart/photo from a research paper? Answer only YES or NO."

    filtered_pictures = []
    for i, pic, path in pictures:
        size = path.stat().st_size
        if size < size_threshold:
            print(f"  [FILTER] pic_{i:03d}.png ({size:,} bytes) - too small, skipping", flush=True)
            path.unlink(missing_ok=True)
            continue

        img_b64 = resize_for_vlm(path)
        try:
            resp = call_vlm(img_b64, FILTER_PROMPT, model, api_base, api_key, max_tokens=10, timeout=30).strip().upper()
            is_scientific = "YES" in resp
        except Exception as e:
            print(f"  [FILTER] pic_{i:03d}.png - VLM error ({e}), keeping", flush=True)
            is_scientific = True

        if is_scientific:
            filtered_pictures.append((i, pic, path))
        else:
            print(f"  [FILTER] pic_{i:03d}.png ({size:,} bytes) - not a scientific figure, skipping", flush=True)
            path.unlink(missing_ok=True)

    pictures = filtered_pictures
    print(f"  After filtering: {len(pictures)} pictures", flush=True)

    # Identify bad tables (image-based)
    bad_tables = []
    for table in all_tables:
        data = table.data
        cells = data.table_cells if hasattr(data, 'table_cells') else []
        all_dots = all('.' in c.text for c in cells if hasattr(c, 'text'))
        if all_dots and len(cells) <= 2:
            page_no = table.prov[0].page_no
            bad_tables.append((table, page_no))
            print(f"  Bad table on page {page_no} (image-based)", flush=True)

    # ── Step 3: Panel Detection ──
    print(f"\n{'=' * 60}", flush=True)
    print("Step 3: Panel Detection with figpanel", flush=True)
    print(f"{'=' * 60}", flush=True)

    import figpanel

    def trim_panel_caption(panel_img):
        arr = np.array(panel_img.convert("L"))
        h, w = arr.shape
        if h < 200 or w < 200:
            return panel_img
        dark = arr < 100
        third = w // 3
        left_has = dark[:, :third].any(axis=1)
        right_has = dark[:, 2 * third:].any(axis=1)
        dark_ratio = dark.mean(axis=1)
        is_text_row = left_has & right_has & (dark_ratio > 0.08)
        window = 50
        caption_start = h
        for y in range(h - window, -1, -1):
            frac = is_text_row[y:y + window].mean()
            if frac >= 0.40:
                caption_start = y
            else:
                if caption_start < h:
                    break
        text_h = h - caption_start
        remaining_h = caption_start
        if text_h > h * 0.70 and remaining_h > 300:
            return panel_img.crop((0, 0, w, caption_start))
        return panel_img

    figure_panels = {}

    for i, pic, pic_path in pictures:
        print(f"  [pic {i+1}] {pic_path.name}...", end=" ", flush=True)
        img = Image.open(pic_path)
        img_w, img_h = img.size

        try:
            results = figpanel.detect(str(pic_path))
            subplots = results.get('subplots', [])

            if not subplots:
                print("SKIP: no panels detected")
                continue

            subplots_sorted = sorted(subplots, key=lambda b: (b[1] // 100, b[0]))
            panel_list = []
            for idx, (x1, y1, x2, y2, conf) in enumerate(subplots_sorted):
                px1, py1, px2, py2 = int(x1), int(y1), int(x2), int(y2)
                px1 = max(0, min(img_w, px1))
                py1 = max(0, min(img_h, py1))
                px2 = max(0, min(img_w, px2))
                py2 = min(img_h, py2)
                panel_w = px2 - px1
                panel_h = py2 - py1
                if panel_w < 50 or panel_h < 50:
                    continue
                if conf < 0.3:
                    continue
                panel_img = img.crop((px1, py1, px2, py2))
                orig_h = panel_img.size[1]
                panel_img = trim_panel_caption(panel_img)
                if panel_img.size[1] < orig_h:
                    print(f"[trim {chr(65+idx)}: {orig_h}->{panel_img.size[1]}px]", end=" ", flush=True)
                img_array = np.array(panel_img.convert("L"))
                if img_array.size == 0:
                    continue
                variance = np.var(img_array)
                if variance < 50:
                    continue
                label = chr(65 + idx) if idx < 26 else f"P{idx+1}"
                panel_path = output_dir / "panels" / f"pic{i:03d}_{label}.png"
                panel_img.save(str(panel_path), format="PNG")
                panel_list.append((label, panel_path, panel_img))

            if panel_list:
                figure_panels[i] = panel_list
                print(f"OK ({len(panel_list)} panels)")
            else:
                print("SKIP: no valid panels after filtering")
        except Exception as e:
            print(f"FAIL: {e}")

    # ── Step 4: Panel Captions ──
    print(f"\n{'=' * 60}", flush=True)
    print("Step 4: Panel Captions", flush=True)
    print(f"{'=' * 60}", flush=True)

    CAPTION_PROMPT = (
        "First, identify the sub-panel label (e.g., A, B, C, D) visible in the "
        "upper-left corner of this image. If no label is visible, say NONE.\n"
        "Then, describe this panel in 2-3 sentences in English. "
        "Focus on what the panel shows, key findings, and any visible labels.\n"
        "Format your response exactly as:\n"
        "LABEL: <label>\n"
        "DESCRIPTION: <description>\n"
        "If this is not a scientific figure (e.g. a logo, advertisement, or banner), "
        "briefly say so in the description. Be concise and accurate. /no_think"
    )

    FALLBACK_CAPTION_PROMPT = (
        "Describe this figure from a scientific paper in 2-3 sentences in English. "
        "Focus on what the figure shows, key findings, and panel labels "
        "(A, B, C, etc.) if visible. "
        "If this is not a scientific figure (e.g. a logo, advertisement, or banner), "
        "briefly say so. Be concise and accurate. /no_think"
    )

    descriptions = {}
    relabel_map = {}

    for i, panels in figure_panels.items():
        vlm_labels = {}
        for label, panel_path, _ in panels:
            print(f"  [pic {i+1} panel {label}] {panel_path.name}...", end=" ", flush=True)
            with open(panel_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            try:
                resp_text = call_vlm(img_b64, CAPTION_PROMPT, model, api_base, api_key, max_tokens=400, timeout=90)
                m_desc = re.search(r'^DESCRIPTION:\s*(.*)$', resp_text, re.MULTILINE | re.DOTALL)
                desc_text = m_desc.group(1).strip() if m_desc else resp_text
                descriptions[panel_path.name] = desc_text
                m_label = re.search(r'^LABEL:\s*(.+)$', resp_text, re.MULTILINE)
                if m_label:
                    raw = m_label.group(1).strip().upper()
                    if len(raw) == 1 and raw.isalpha():
                        vlm_labels[label] = raw
                    else:
                        vlm_labels[label] = None
                else:
                    vlm_labels[label] = None
                print(f"OK ({len(desc_text)} chars)")
            except Exception as e:
                print(f"FAIL: {e}")
                descriptions[panel_path.name] = f"(failed: {e})"
                vlm_labels[label] = None

        positional_labels = {lbl for lbl, _, _ in panels}
        used = set()
        for label, _, _ in panels:
            vlm_lbl = vlm_labels.get(label)
            if vlm_lbl and vlm_lbl not in positional_labels and vlm_lbl not in used:
                relabel_map.setdefault(i, {})[label] = vlm_lbl
                used.add(vlm_lbl)
            else:
                used.add(label)
        for lbl, actual in relabel_map.get(i, {}).items():
            print(f"    relabel {lbl}->{actual}", flush=True)

    for i, pic, pic_path in pictures:
        if i in figure_panels and figure_panels[i]:
            continue
        print(f"  [pic {i+1} fallback] {pic_path.name}...", end=" ", flush=True)
        with open(pic_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        try:
            desc = call_vlm(img_b64, FALLBACK_CAPTION_PROMPT, model, api_base, api_key, max_tokens=300, timeout=90)
            descriptions[pic_path.name] = desc
            print(f"OK ({len(desc)} chars)")
        except Exception as e:
            print(f"FAIL: {e}")
            descriptions[pic_path.name] = f"(failed: {e})"

    # ── Step 5: Image-Based Tables ──
    print(f"\n{'=' * 60}", flush=True)
    print("Step 5: Image-Based Tables", flush=True)
    print(f"{'=' * 60}", flush=True)

    TABLE_PROMPT = (
        "Convert this table to a Markdown table. "
        "Preserve ALL rows and columns exactly as shown. "
        "Output ONLY the markdown table, nothing else. /no_think"
    )

    extracted_tables = {}
    pdf = fitz.open(str(pdf_path))
    for table, page_no in bad_tables:
        print(f"  Processing table on page {page_no}...", flush=True)
        page = pdf[page_no - 1]
        for img_idx, img in enumerate(page.get_images(full=True)):
            base_image = pdf.extract_image(img[0])
            if base_image['width'] > 500 and base_image['height'] > 300:
                img_b64 = base64.b64encode(base_image["image"]).decode()
                try:
                    table_md = call_vlm(img_b64, TABLE_PROMPT, model, api_base, api_key, max_tokens=8000, timeout=180)
                    extracted_tables[table.self_ref] = table_md
                    print(f"  Extracted: {len(table_md)} chars", flush=True)
                except Exception as e:
                    print(f"  FAIL: {e}")
                break
    pdf.close()

    # ── Step 6: Panel CSV Extraction + MD Assembly ──
    print(f"\n{'=' * 60}", flush=True)
    print("Step 6: Panel CSV Extraction + MD Assembly", flush=True)
    print(f"{'=' * 60}", flush=True)

    PANEL_PROMPT = load_panel_prompt()

    # Build figure-to-panel mapping
    parts = md.split("<!-- image -->")

    # Rebuild parts array: merge text for filtered images
    # parts has N+1 elements for N images: parts[0] before img0, parts[1] between img0-1, etc.
    kept_indices = set(i for i, _, _ in pictures)
    new_parts = [parts[0]]  # Always keep first part
    for orig_idx in range(1, len(parts)):
        img_idx = orig_idx - 1  # Image index for this part boundary
        if img_idx in kept_indices:
            new_parts.append(parts[orig_idx])
        else:
            new_parts[-1] = new_parts[-1] + parts[orig_idx]  # Merge filtered image's text
    parts = new_parts

    # Remap picture indices to sequential (0, 1, 2, ...) matching new parts
    old_to_new_idx = {}
    new_pictures = []
    for new_idx, (old_idx, pic, path) in enumerate(pictures):
        old_to_new_idx[old_idx] = new_idx
        new_pictures.append((new_idx, pic, path))
    pictures = new_pictures

    # Remap downstream dicts to use new indices
    figure_panels = {old_to_new_idx[k]: v for k, v in figure_panels.items() if k in old_to_new_idx}
    relabel_map = {old_to_new_idx[k]: v for k, v in relabel_map.items() if k in old_to_new_idx}

    pic_to_fig = {}
    figure_num = 1
    for pic_idx, _, _ in pictures:
        if pic_idx < len(parts) - 1:
            pic_to_fig[pic_idx] = figure_num
            figure_num += 1

    # Rename panels to Figure{N}_Panel{X}.png
    renamed_panels = {}
    for pic_idx, panels in figure_panels.items():
        fig_num = pic_to_fig.get(pic_idx, 0)
        for idx, (label, old_path, _) in enumerate(panels):
            actual_label = relabel_map.get(pic_idx, {}).get(label, label)
            new_name = f"Figure{fig_num}_Panel{actual_label}.png"
            new_path = output_dir / "panels" / new_name
            if old_path.exists():
                shutil.move(str(old_path), str(new_path))
                renamed_panels[old_path.name] = new_name

    # Move full images (no panels)
    for pic_idx, fig_num in pic_to_fig.items():
        if pic_idx not in figure_panels or not figure_panels[pic_idx]:
            for i, pic, pic_path in pictures:
                if i == pic_idx:
                    new_name = f"Figure{fig_num}_full.png"
                    new_path = output_dir / "images" / new_name
                    if pic_path.exists():
                        shutil.move(str(pic_path), str(new_path))
                        renamed_panels[pic_path.name] = new_name
                    break

    # Clean old pic_*.png (unless --keep-original-images is set)
    if not args.keep_original_images:
        for old_pic in (output_dir / "images").glob("pic_*.png"):
            old_pic.unlink()
    else:
        kept_count = len(list((output_dir / "images").glob("pic_*.png")))
        if kept_count > 0:
            print(f"  Keeping {kept_count} original pic_*.png files")

    # Save descriptions with renamed keys
    renamed_descriptions = {}
    for old_name, desc in descriptions.items():
        new_name = renamed_panels.get(old_name, old_name)
        renamed_descriptions[new_name] = desc

    desc_path = output_dir / "descriptions.json"
    with open(desc_path, "w", encoding="utf-8") as f:
        json.dump(renamed_descriptions, f, ensure_ascii=False, indent=2)

    # CSV extraction on each panel (PARALLEL)
    panel_files = sorted((output_dir / "panels").glob("*.png"))
    print(f"  Found {len(panel_files)} panels")

    # Parallel processing configuration
    MAX_PARALLEL_WORKERS = int(os.environ.get("PDF2MD_PARALLEL_WORKERS", "10"))
    csv_results = {}

    if len(panel_files) > 1:
        # Use ThreadPoolExecutor for parallel API calls
        print(f"  Processing in parallel (max {MAX_PARALLEL_WORKERS} workers)...")
        tasks = []
        for panel_path in panel_files:
            name = panel_path.name
            caption = renamed_descriptions.get(name, "")
            tasks.append((panel_path, caption))

        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_PARALLEL_WORKERS) as executor:
            futures = {
                executor.submit(
                    process_single_panel,
                    panel_path, caption, PANEL_PROMPT, model, api_base, api_key
                ): panel_path.name
                for panel_path, caption in tasks
            }

            completed = 0
            for future in concurrent.futures.as_completed(futures):
                name, result, error = future.result()
                csv_results[name] = result
                completed += 1
                if error:
                    print(f"  [{completed}/{len(panel_files)}] {name}... FAIL: {error}", flush=True)
                else:
                    print(f"  [{completed}/{len(panel_files)}] {name}... OK ({len(result)} sub-figures)", flush=True)
    else:
        # Single panel - process directly
        for i, panel_path in enumerate(panel_files, 1):
            name = panel_path.name
            caption = renamed_descriptions.get(name, "")
            caption = caption if isinstance(caption, str) else (str(caption) if caption else "")
            prompt = PANEL_PROMPT.replace("{caption}", caption)
            print(f"  [{i}/{len(panel_files)}] {name}...", end=" ", flush=True)

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

    # Save CSV JSON
    csv_json_path = output_dir / "panels_data.json"
    with open(csv_json_path, "w", encoding="utf-8") as f:
        json.dump(csv_results, f, ensure_ascii=False, indent=2)

    # Assemble final MD
    def format_panel_content(panel_name):
        entries = csv_results.get(panel_name, [])
        if not entries:
            return ""
        blocks = []
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
        return "\n".join(blocks)

    final = parts[0]
    last_part_idx = 0
    for pic_idx, _, pic_path in pictures:
        fig_num = pic_to_fig.get(pic_idx, 0)
        panels = figure_panels.get(pic_idx, [])
        if panels:
            block = ""
            for label, old_path, _ in panels:
                actual_label = relabel_map.get(pic_idx, {}).get(label, label)
                new_name = renamed_panels.get(old_path.name, old_path.name)
                panel_content = format_panel_content(new_name)
                block += f"![Figure {fig_num} Panel {actual_label}](panels/{new_name})\n\n{panel_content}\n---\n\n"
            final += block + parts[pic_idx + 1]
        else:
            new_name = resolve_renamed_image(pic_path, renamed_panels)
            desc = renamed_descriptions.get(new_name, "")
            final += f"![Figure {fig_num}](images/{new_name})\n\n> caption: {desc}\n\n" + parts[pic_idx + 1]
        last_part_idx = pic_idx + 1

    # Append any remaining parts after the last processed picture
    for remaining_idx in range(last_part_idx + 1, len(parts)):
        final += parts[remaining_idx]

    # Replace bad tables
    for table_ref, table_md in extracted_tables.items():
        final = re.sub(r'\|\s*\.{20,}\s*\|\n\|[-]+\|', table_md, final, count=1)

    paper_name = pdf_path.stem
    final_path = output_dir / f"{paper_name}_complete.md"
    with open(final_path, "w", encoding="utf-8") as f:
        f.write(final)

    # Summary
    print(f"\n{'=' * 60}", flush=True)
    print("RESULTS", flush=True)
    print(f"{'=' * 60}", flush=True)
    print(f"  Output dir:     {output_dir}", flush=True)
    print(f"  Final MD:       {final_path} ({final_path.stat().st_size:,} bytes)", flush=True)
    print(f"  CSV JSON:       {csv_json_path}", flush=True)
    print(f"  Pictures:       {len(pictures)}", flush=True)
    print(f"  Panels:         {sum(len(v) for v in figure_panels.values())}", flush=True)
    print(f"  Captions:       {len(renamed_descriptions)}", flush=True)
    print(f"  Tables:         {len(extracted_tables)}", flush=True)
    print(f"  CSV extracted:  {len(csv_results)}", flush=True)


if __name__ == "__main__":
    main()
