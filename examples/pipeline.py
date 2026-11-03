"""Reference pipeline: PDF -> panel detection -> captions -> CSV extraction -> final MD.
This is a REFERENCE script for the pdf2md skill. Adapt paths and config for each PDF."""

import os, sys, json, base64, re, requests, shutil, argparse
from pathlib import Path
import numpy as np
import yaml
import concurrent.futures

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import fitz
from PIL import Image
from assemble_md import assemble_and_validate
from run_manifest import RunManifest, write_json_atomic, write_text_atomic
from vlm_client import VLMClient, encode_image, extract_json_value
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
    p.add_argument("--resume", action="store_true", help="Resume completed or interrupted stages from run_manifest.json")
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

    enable_thinking = vlm.get("enable_thinking")
    if enable_thinking is not None and not isinstance(enable_thinking, bool):
        raise ValueError(f"'vlm.enable_thinking' must be true or false in config: {config_path}")

    return {
        "model": vlm["model"].strip(),
        "api_base": vlm["api_base"].strip().rstrip("/"),
        "api_key": vlm["api_key"].strip(),
        "offline": offline,
        "enable_thinking": enable_thinking,
    }


def load_vlm_config(config_path):
    config = load_config(config_path)
    return config["model"], config["api_base"], config["api_key"]


def configure_runtime(config):
    if config["offline"]:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
    enable_thinking = config.get("enable_thinking")
    if enable_thinking is None:
        os.environ.pop("PDF2MD_ENABLE_THINKING", None)
    else:
        os.environ["PDF2MD_ENABLE_THINKING"] = "1" if enable_thinking else "0"


def load_panel_prompt():
    prompt_path = Path(__file__).resolve().parents[1] / "references" / "figure_rules.md"
    return prompt_path.read_text(encoding="utf-8")


def resolve_renamed_image(original_path, renamed_images):
    return renamed_images.get(original_path.name, original_path.name)


def prepare_output_dir(output_dir, paper_name, overwrite, resume=False):
    if output_dir.exists() and any(output_dir.iterdir()) and not overwrite and not resume:
        raise FileExistsError(
            f"Output directory is not empty: {output_dir}. "
            "Choose another directory, pass --overwrite, or pass --resume."
        )

    if overwrite:
        for directory in (output_dir / "images", output_dir / "panels"):
            if directory.exists():
                shutil.rmtree(directory)
        for file_path in (
            output_dir / "panels_data.json",
            output_dir / "descriptions.json",
            output_dir / f"{paper_name}_complete.md",
            output_dir / "docling.md",
            output_dir / "run_manifest.json",
            output_dir / "quality_report.json",
        ):
            file_path.unlink(missing_ok=True)

    output_dir.mkdir(exist_ok=True)
    (output_dir / "images").mkdir(exist_ok=True)
    (output_dir / "panels").mkdir(exist_ok=True)


def call_vlm(img_b64, prompt, model, api_base, api_key, max_tokens=300, timeout=90):
    value = os.environ.get("PDF2MD_ENABLE_THINKING")
    enable_thinking = None if value is None else value == "1"
    client = VLMClient(
        model=model,
        api_base=api_base,
        api_key=api_key,
        enable_thinking=enable_thinking,
    )
    return client.analyze_b64(img_b64, prompt, max_tokens=max_tokens, timeout=timeout)


def resize_for_vlm(img_path, max_size=1024):
    return encode_image(Path(img_path), max_size=max_size)


def process_single_panel(client, panel_path, caption, prompt_template):
    """Process a single panel for CSV extraction - designed for parallel execution"""
    name = panel_path.name
    caption = caption if isinstance(caption, str) else (str(caption) if caption else "")
    prompt = prompt_template.replace("{caption}", caption)

    try:
        parsed = client.analyze_json_array(panel_path, prompt, max_tokens=4000, timeout=180)
        return name, parsed, None
    except Exception as e:
        return name, [{"fig_type": "error", "data_type": "description", "content": str(e)}], e


def extract_json(text):
    value = extract_json_value(text)
    if not isinstance(value, list):
        raise ValueError("Expected a JSON array")
    return value


def main():
    args = parse_args()
    if args.overwrite and args.resume:
        raise ValueError("--overwrite and --resume cannot be used together")
    config = load_config(args.config.resolve())
    configure_runtime(config)
    client = VLMClient(
        model=config["model"],
        api_base=config["api_base"],
        api_key=config["api_key"],
        enable_thinking=config.get("enable_thinking"),
    )

    pdf_path = Path(args.pdf).resolve()
    output_dir = Path(args.output).resolve() if args.output else pdf_path.parent / f"{pdf_path.stem}-with-csv"
    prepare_output_dir(output_dir, pdf_path.stem, args.overwrite, args.resume)
    if args.resume:
        manifest = RunManifest.load(output_dir)
        manifest.validate_pdf(pdf_path)
    else:
        manifest = RunManifest.create(output_dir, pdf_path)
    manifest.set_artifact("paper_name", pdf_path.stem)

    size_threshold = args.filter_size * 1024

    # ── Step 1: PDF Parsing (single-pass) ──
    print("=" * 60, flush=True)
    print("Step 1: PDF Parsing (single-pass)", flush=True)
    print("=" * 60, flush=True)

    if args.resume and manifest.stage_completed("parse"):
        source_path = output_dir / manifest.artifact("source_markdown")
        if not source_path.is_file():
            raise FileNotFoundError(f"Missing parsed Markdown: {source_path}")
        pictures = manifest.artifact("original_pictures", [])
        bad_tables = manifest.artifact("bad_tables", [])
        total_pages = manifest.artifact("page_count", 0)
        print(f"  [RESUME] Reusing parsed document ({total_pages} pages)", flush=True)
    else:
        manifest.set_stage("parse", "running")
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.document import ConversionStatus
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
        result = converter.convert(str(pdf_path), raises_on_error=False)
        if result.status != ConversionStatus.SUCCESS:
            errors = [str(error) for error in result.errors]
            message = f"Docling conversion status: {result.status.value}"
            if errors:
                message += f"; errors: {'; '.join(errors)}"
            manifest.set_artifact("parse_status", result.status.value, save=False)
            manifest.set_artifact("parse_errors", errors, save=False)
            manifest.set_stage("parse", "failed", error=message)
            raise RuntimeError(message)
        doc = result.document

        md = doc.export_to_markdown()
        all_tables = doc.tables
        total_pages = len(doc.pages)
        print(f"  Pages: {total_pages}", flush=True)
        print(f"  Pictures: {len(doc.pictures)}", flush=True)
        print(f"  Tables: {len(all_tables)}", flush=True)

        write_text_atomic(output_dir / "docling.md", md)
        pictures = []
        for i, pic in enumerate(doc.pictures):
            img = pic.get_image(doc=doc)
            if img:
                path = output_dir / "images" / f"pic_{i:03d}.png"
                img.save(str(path), format="PNG")
                pictures.append({
                    "index": i,
                    "path": str(path.relative_to(output_dir)),
                })
        print(f"  Saved {len(pictures)} pictures", flush=True)

        bad_tables = []
        for table in all_tables:
            data = table.data
            cells = data.table_cells if hasattr(data, "table_cells") else []
            all_dots = all("." in c.text for c in cells if hasattr(c, "text"))
            if all_dots and len(cells) <= 2:
                page_no = table.prov[0].page_no
                bad_tables.append({"ref": table.self_ref, "page": page_no})
                print(f"  Bad table on page {page_no} (image-based)", flush=True)

        manifest.set_artifact("source_markdown", "docling.md", save=False)
        manifest.set_artifact("original_pictures", pictures, save=False)
        manifest.set_artifact("bad_tables", bad_tables, save=False)
        manifest.set_artifact("page_count", total_pages, save=False)
        manifest.set_artifact("parse_status", result.status.value, save=False)
        manifest.set_artifact("parse_errors", [], save=False)
        manifest.set_stage("parse", "completed")
        print(f"  [STATE] Parse checkpoint saved", flush=True)

    # ── Step 2: Image Filtering ──
    FILTER_PROMPT = "Is this a scientific figure/chart/photo from a research paper? Answer only YES or NO."

    if args.resume and manifest.stage_completed("filter"):
        pictures = manifest.artifact("filtered_pictures", [])
        print(f"  [RESUME] Reusing {len(pictures)} filtered pictures", flush=True)
    else:
        manifest.set_stage("filter", "running")
        filtered_pictures = []
        for picture in pictures:
            i = int(picture["index"])
            path = output_dir / picture["path"]
            size = path.stat().st_size
            if size < size_threshold:
                print(f"  [FILTER] pic_{i:03d}.png ({size:,} bytes) - too small, skipping", flush=True)
                path.unlink(missing_ok=True)
                continue

            try:
                response = client.analyze_image(
                    path,
                    FILTER_PROMPT,
                    max_tokens=300,
                    timeout=60,
                ).strip().upper()
                is_scientific = response == "YES" or response.startswith("YES")
            except Exception as e:
                print(f"  [FILTER] pic_{i:03d}.png - VLM error ({e}), keeping", flush=True)
                is_scientific = True

            if is_scientific:
                filtered_pictures.append(picture)
            else:
                print(f"  [FILTER] pic_{i:03d}.png ({size:,} bytes) - not a scientific figure, skipping", flush=True)
                path.unlink(missing_ok=True)

        pictures = filtered_pictures
        print(f"  After filtering: {len(pictures)} pictures", flush=True)
        manifest.set_artifact("filtered_pictures", pictures, save=False)
        manifest.set_stage("filter", "completed")
        print(f"  [STATE] Filter checkpoint saved", flush=True)

    # ── Step 3: Panel Detection ──
    print(f"\n{'=' * 60}", flush=True)
    print("Step 3: Panel Detection with figpanel", flush=True)
    print(f"{'=' * 60}", flush=True)

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

    if args.resume and manifest.stage_completed("panels"):
        figure_panels = {
            int(index): panels
            for index, panels in manifest.artifact("figure_panels", {}).items()
        }
        print(f"  [RESUME] Reusing panels for {len(figure_panels)} pictures", flush=True)
    else:
        manifest.set_stage("panels", "running")
        import figpanel
        figure_panels = {}

        for picture in pictures:
            i = int(picture["index"])
            pic_path = output_dir / picture["path"]
            print(f"  [pic {i+1}] {pic_path.name}...", end=" ", flush=True)
            img = Image.open(pic_path)
            img_w, img_h = img.size

            try:
                results = figpanel.detect(str(pic_path))
                subplots = results.get("subplots", [])

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
                    panel_list.append({
                        "label": label,
                        "path": str(panel_path.relative_to(output_dir)),
                    })

                if panel_list:
                    figure_panels[i] = panel_list
                    print(f"OK ({len(panel_list)} panels)")
                else:
                    print("SKIP: no valid panels after filtering")
            except Exception as e:
                print(f"FAIL: {e}")

        manifest.set_artifact("figure_panels", figure_panels, save=False)
        manifest.set_stage("panels", "completed")
        print(f"  [STATE] Panel checkpoint saved", flush=True)

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

    if args.resume and manifest.stage_completed("descriptions"):
        descriptions = manifest.artifact("descriptions", {})
        relabel_map = {
            int(index): labels
            for index, labels in manifest.artifact("relabel_map", {}).items()
        }
        print(f"  [RESUME] Reusing {len(descriptions)} descriptions", flush=True)
    else:
        manifest.set_stage("descriptions", "running")
        descriptions = {}
        relabel_map = {}

        for i, panels in figure_panels.items():
            vlm_labels = {}
            for panel in panels:
                label = panel["label"]
                panel_path = output_dir / panel["path"]
                print(f"  [pic {i+1} panel {label}] {panel_path.name}...", end=" ", flush=True)
                try:
                    resp_text = client.analyze_image(
                        panel_path,
                        CAPTION_PROMPT,
                        max_tokens=400,
                        timeout=90,
                    )
                    m_desc = re.search(r"^DESCRIPTION:\s*(.*)$", resp_text, re.MULTILINE | re.DOTALL)
                    desc_text = m_desc.group(1).strip() if m_desc else resp_text
                    descriptions[panel_path.name] = desc_text
                    m_label = re.search(r"^LABEL:\s*(.+)$", resp_text, re.MULTILINE)
                    if m_label:
                        raw = m_label.group(1).strip().upper()
                        vlm_labels[label] = raw if len(raw) == 1 and raw.isalpha() else None
                    else:
                        vlm_labels[label] = None
                    print(f"OK ({len(desc_text)} chars)")
                except Exception as e:
                    print(f"FAIL: {e}")
                    descriptions[panel_path.name] = f"(failed: {e})"
                    vlm_labels[label] = None

            positional_labels = {panel["label"] for panel in panels}
            used = set()
            for panel in panels:
                label = panel["label"]
                vlm_lbl = vlm_labels.get(label)
                if vlm_lbl and vlm_lbl not in positional_labels and vlm_lbl not in used:
                    relabel_map.setdefault(i, {})[label] = vlm_lbl
                    used.add(vlm_lbl)
                else:
                    used.add(label)
            for lbl, actual in relabel_map.get(i, {}).items():
                print(f"    relabel {lbl}->{actual}", flush=True)

        for picture in pictures:
            i = int(picture["index"])
            if i in figure_panels and figure_panels[i]:
                continue
            pic_path = output_dir / picture["path"]
            print(f"  [pic {i+1} fallback] {pic_path.name}...", end=" ", flush=True)
            try:
                desc = client.analyze_image(
                    pic_path,
                    FALLBACK_CAPTION_PROMPT,
                    max_tokens=300,
                    timeout=90,
                )
                descriptions[pic_path.name] = desc
                print(f"OK ({len(desc)} chars)")
            except Exception as e:
                print(f"FAIL: {e}")
                descriptions[pic_path.name] = f"(failed: {e})"

        manifest.set_artifact("descriptions", descriptions, save=False)
        manifest.set_artifact("relabel_map", relabel_map, save=False)
        manifest.set_stage("descriptions", "completed")
        print(f"  [STATE] Description checkpoint saved", flush=True)

    # ── Step 5: Image-Based Tables ──
    print(f"\n{'=' * 60}", flush=True)
    print("Step 5: Image-Based Tables", flush=True)
    print(f"{'=' * 60}", flush=True)

    TABLE_PROMPT = (
        "Convert this table to a Markdown table. "
        "Preserve ALL rows and columns exactly as shown. "
        "Output ONLY the markdown table, nothing else. /no_think"
    )

    if args.resume and manifest.stage_completed("tables"):
        extracted_tables = manifest.artifact("extracted_tables", {})
        print(f"  [RESUME] Reusing {len(extracted_tables)} extracted tables", flush=True)
    else:
        manifest.set_stage("tables", "running")
        extracted_tables = {}
        pdf = fitz.open(str(pdf_path))
        for table in bad_tables:
            table_ref = table["ref"]
            page_no = int(table["page"])
            print(f"  Processing table on page {page_no}...", flush=True)
            page = pdf[page_no - 1]
            for image in page.get_images(full=True):
                base_image = pdf.extract_image(image[0])
                if base_image["width"] > 500 and base_image["height"] > 300:
                    img_b64 = base64.b64encode(base_image["image"]).decode()
                    try:
                        table_md = client.analyze_b64(
                            img_b64,
                            TABLE_PROMPT,
                            max_tokens=8000,
                            timeout=180,
                        )
                        extracted_tables[table_ref] = table_md
                        print(f"  Extracted: {len(table_md)} chars", flush=True)
                    except Exception as e:
                        print(f"  FAIL: {e}")
                    break
        pdf.close()
        manifest.set_artifact("extracted_tables", extracted_tables, save=False)
        manifest.set_stage("tables", "completed")
        print(f"  [STATE] Table checkpoint saved", flush=True)

    # ── Step 6: Panel CSV Extraction ──
    print(f"\n{'=' * 60}", flush=True)
    print("Step 6: Panel CSV Extraction", flush=True)
    print(f"{'=' * 60}", flush=True)

    PANEL_PROMPT = load_panel_prompt()

    if args.resume and manifest.stage_completed("prepare"):
        figures = manifest.artifact("figures", [])
        renamed_descriptions = manifest.artifact("descriptions", {})
        print(f"  [RESUME] Reusing {len(figures)} prepared figures", flush=True)
    else:
        manifest.set_stage("prepare", "running")
        figures = []
        renamed_assets = {}

        for picture_index, picture in enumerate(pictures):
            docling_index = int(picture["index"])
            figure_number = picture_index + 1
            panels = figure_panels.get(docling_index, [])
            figure = {
                "docling_index": docling_index,
                "picture_index": picture_index,
                "figure_number": figure_number,
                "panels": [],
                "full_image": None,
            }

            for panel in panels:
                label = panel["label"]
                old_path = output_dir / panel["path"]
                actual_label = relabel_map.get(docling_index, {}).get(label, label)
                new_name = f"Figure{figure_number}_Panel{actual_label}.png"
                new_path = output_dir / "panels" / new_name
                if old_path.exists() and old_path.resolve() != new_path.resolve():
                    if new_path.exists():
                        old_path.unlink()
                    else:
                        shutil.move(str(old_path), str(new_path))
                figure["panels"].append({
                    "label": actual_label,
                    "path": str(new_path.relative_to(output_dir)),
                })
                renamed_assets[old_path.name] = new_name

            if not panels:
                old_path = output_dir / picture["path"]
                new_name = f"Figure{figure_number}_full.png"
                new_path = output_dir / "images" / new_name
                if old_path.exists() and old_path.resolve() != new_path.resolve():
                    if new_path.exists():
                        old_path.unlink()
                    else:
                        shutil.move(str(old_path), str(new_path))
                figure["full_image"] = str(new_path.relative_to(output_dir))
                renamed_assets[old_path.name] = new_name

            figures.append(figure)

        if not args.keep_original_images:
            for old_pic in (output_dir / "images").glob("pic_*.png"):
                old_pic.unlink()

        renamed_descriptions = {
            renamed_assets.get(old_name, old_name): desc
            for old_name, desc in descriptions.items()
        }
        write_json_atomic(output_dir / "descriptions.json", renamed_descriptions)
        manifest.set_artifact("figures", figures, save=False)
        manifest.set_artifact("descriptions", renamed_descriptions, save=False)
        manifest.set_stage("prepare", "completed")
        print(f"  [STATE] Figure preparation checkpoint saved", flush=True)

    # CSV extraction on each panel (PARALLEL)
    panel_files = sorted(
        output_dir / panel["path"]
        for figure in figures
        for panel in figure.get("panels", [])
    )
    print(f"  Found {len(panel_files)} panels")

    csv_json_path = output_dir / "panels_data.json"
    csv_results = {}
    if args.resume and csv_json_path.exists():
        csv_results = json.loads(csv_json_path.read_text(encoding="utf-8"))

    def has_valid_result(name):
        entries = csv_results.get(name)
        return isinstance(entries, list) and not any(
            isinstance(entry, dict) and entry.get("fig_type") == "error"
            for entry in entries
        )

    tasks = []
    for panel_path in panel_files:
        name = panel_path.name
        if args.resume and has_valid_result(name):
            manifest.set_panel_status(name, "completed", save=False)
            continue
        caption = renamed_descriptions.get(name, "")
        tasks.append((panel_path, caption))

    if args.resume and manifest.stage_completed("extract") and not tasks:
        print(f"  [RESUME] Reusing {len(csv_results)} panel results", flush=True)
    else:
        manifest.set_stage("extract", "running")
        MAX_PARALLEL_WORKERS = max(1, int(os.environ.get("PDF2MD_PARALLEL_WORKERS", "10")))
        if tasks:
            print(f"  Processing {len(tasks)} panels in parallel (max {MAX_PARALLEL_WORKERS} workers)...")

        def record_result(name, result, error):
            csv_results[name] = result
            write_json_atomic(csv_json_path, csv_results)
            manifest.set_panel_status(
                name,
                "failed" if error else "completed",
                error=str(error) if error else None,
                save=False,
            )
            manifest.set_usage("vlm", client.snapshot_usage())
            manifest.save()

        if len(tasks) > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_PARALLEL_WORKERS) as executor:
                futures = {
                    executor.submit(
                        process_single_panel,
                        client,
                        panel_path,
                        caption,
                        PANEL_PROMPT,
                    ): panel_path.name
                    for panel_path, caption in tasks
                }

                completed = 0
                for future in concurrent.futures.as_completed(futures):
                    name, result, error = future.result()
                    record_result(name, result, error)
                    completed += 1
                    if error:
                        print(f"  [{completed}/{len(tasks)}] {name}... FAIL: {error}", flush=True)
                    else:
                        print(
                            f"  [{completed}/{len(tasks)}] {name}... "
                            f"OK ({len(result)} sub-figures)",
                            flush=True,
                        )
        else:
            for index, (panel_path, caption) in enumerate(tasks, 1):
                name, result, error = process_single_panel(
                    client,
                    panel_path,
                    caption,
                    PANEL_PROMPT,
                )
                record_result(name, result, error)
                if error:
                    print(f"  [{index}/{len(tasks)}] {name}... FAIL: {error}", flush=True)
                else:
                    print(
                        f"  [{index}/{len(tasks)}] {name}... "
                        f"OK ({len(result)} sub-figures)",
                        flush=True,
                    )

        write_json_atomic(csv_json_path, csv_results)
        failures = [
            path.name
            for path in panel_files
            if not has_valid_result(path.name)
        ]
        if failures:
            manifest.set_stage(
                "extract",
                "failed",
                error=f"{len(failures)} panel(s) failed",
            )
        else:
            manifest.set_stage("extract", "completed")

    # ── Step 7: Markdown Assembly and Quality Gate ──
    print(f"\n{'=' * 60}", flush=True)
    print("Step 7: Markdown Assembly and Quality Gate", flush=True)
    print(f"{'=' * 60}", flush=True)
    manifest.set_stage("assemble", "running")
    assembly = assemble_and_validate(output_dir, manifest)
    final_path = assembly["markdown_path"]
    quality = assembly["report"]
    print(f"  Quality gate: {'PASS' if quality['ok'] else 'FAIL'}", flush=True)
    for warning in quality["warnings"]:
        print(f"  WARNING: {warning}", flush=True)
    for error in quality["errors"]:
        print(f"  ERROR: {error}", flush=True)

    # Summary
    print(f"\n{'=' * 60}", flush=True)
    print("RESULTS", flush=True)
    print(f"{'=' * 60}", flush=True)
    print(f"  Output dir:     {output_dir}", flush=True)
    print(f"  Final MD:       {final_path} ({final_path.stat().st_size:,} bytes)", flush=True)
    print(f"  CSV JSON:       {csv_json_path}", flush=True)
    print(f"  Manifest:       {manifest.path}", flush=True)
    print(f"  Pictures:       {len(figures)}", flush=True)
    print(f"  Panels:         {sum(len(v.get('panels', [])) for v in figures)}", flush=True)
    print(f"  Captions:       {len(renamed_descriptions)}", flush=True)
    print(f"  Tables:         {len(extracted_tables)}", flush=True)
    print(f"  CSV extracted:  {len(csv_results)}", flush=True)
    print(f"  Quality gate:   {'PASS' if quality['ok'] else 'FAIL'}", flush=True)
    if not quality["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
