"""Assemble and validate the final PDF2MD Markdown output."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
from pathlib import Path
from typing import Any

from run_manifest import RunManifest, utc_now, write_json_atomic, write_text_atomic


def _escape_table_cell(value: str) -> str:
    return value.replace("|", r"\|").replace("\n", "<br>").strip()


def render_panel_content(entries: list[dict[str, Any]]) -> str:
    blocks = []
    for entry in entries:
        fig_type = entry.get("fig_type", "")
        data_type = entry.get("data_type", "")
        content = entry.get("content", "")
        blocks.append(f"**Type:** {fig_type} | **Data:** {data_type}\n")
        if data_type == "num_table" and content:
            rows = list(csv.reader(io.StringIO(str(content).strip())))
            if rows:
                blocks.append("| " + " | ".join(_escape_table_cell(cell) for cell in rows[0]) + " |")
                blocks.append("| " + " | ".join(["---"] * len(rows[0])) + " |")
                for row in rows[1:]:
                    cells = row + [""] * max(0, len(rows[0]) - len(row))
                    blocks.append(
                        "| "
                        + " | ".join(_escape_table_cell(cell) for cell in cells[: len(rows[0])])
                        + " |"
                    )
                blocks.append("")
        elif data_type == "description" and content:
            blocks.append(f"> {content}\n")
    return "\n".join(blocks)


def build_markdown(output_dir: Path, manifest: RunManifest, panels_data: dict[str, Any]) -> str:
    source_path = output_dir / manifest.artifact("source_markdown")
    source = source_path.read_text(encoding="utf-8")
    figures = manifest.artifact("figures", [])
    parts = source.split("<!-- image -->")

    kept_docling_indices = {
        int(figure["docling_index"])
        for figure in figures
        if "docling_index" in figure
    }
    rebuilt_parts = [parts[0]]
    for original_index in range(1, len(parts)):
        image_index = original_index - 1
        if image_index in kept_docling_indices:
            rebuilt_parts.append(parts[original_index])
        else:
            rebuilt_parts[-1] += parts[original_index]

    final = rebuilt_parts[0]
    for position, figure in enumerate(figures):
        figure_number = int(figure["figure_number"])
        panels = figure.get("panels", [])
        if panels:
            block = ""
            for panel in panels:
                panel_name = Path(panel["path"]).name
                content = render_panel_content(panels_data.get(panel_name, []))
                block += (
                    f"![Figure {figure_number} Panel {panel['label']}]"
                    f"({panel['path']})\n\n{content}\n---\n\n"
                )
            final += block
        else:
            full_image = figure["full_image"]
            description = manifest.artifact("descriptions", {}).get(Path(full_image).name, "")
            final += f"![Figure {figure_number}]({full_image})\n\n> caption: {description}\n\n"

        part_index = position + 1
        if part_index < len(rebuilt_parts):
            final += rebuilt_parts[part_index]

    covered_parts = min(len(figures), max(0, len(rebuilt_parts) - 1))
    for part_index in range(covered_parts + 1, len(rebuilt_parts)):
        final += rebuilt_parts[part_index]

    for table_ref, table_markdown in manifest.artifact("extracted_tables", {}).items():
        final = re.sub(
            r"\|\s*\.{20,}\s*\|\n\|[-]+\|",
            table_markdown,
            final,
            count=1,
        )
    return final


def validate_output(
    output_dir: Path,
    manifest: RunManifest,
    markdown: str,
    panels_data: dict[str, Any],
) -> dict[str, Any]:
    errors = []
    warnings = []
    links = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", markdown)
    missing_links = []
    for link in links:
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", link):
            continue
        if not (output_dir / link).exists():
            missing_links.append(link)
    if missing_links:
        errors.append(f"Missing image links: {missing_links}")
    if "<!-- image -->" in markdown:
        errors.append("Unresolved image placeholders remain")

    error_entries = [
        name
        for name, entries in panels_data.items()
        if any(isinstance(entry, dict) and entry.get("fig_type") == "error" for entry in entries)
    ]
    if error_entries:
        errors.append(f"Panels with error entries: {error_entries}")

    expected_panels = {
        Path(panel["path"]).name
        for figure in manifest.artifact("figures", [])
        for panel in figure.get("panels", [])
    }
    missing_results = sorted(expected_panels.difference(panels_data))
    if missing_results:
        errors.append(f"Panels without extraction results: {missing_results}")

    descriptions = manifest.artifact("descriptions", {})
    missing_descriptions = sorted(name for name in expected_panels if not descriptions.get(name))
    if missing_descriptions:
        warnings.append(f"Panels without descriptions: {missing_descriptions}")
    if not markdown.strip():
        errors.append("Final Markdown is empty")
    if len(markdown.strip()) < 1000:
        warnings.append("Final Markdown is unexpectedly short")
    if "References" not in markdown[-50000:] and "REFERENCES" not in markdown[-50000:]:
        warnings.append("References section was not found near the end of the document")

    return {
        "ok": not errors,
        "checked_at": utc_now(),
        "errors": errors,
        "warnings": warnings,
        "metrics": {
            "markdown_bytes": len(markdown.encode("utf-8")),
            "image_links": len(links),
            "panels": len(expected_panels),
            "panels_data": len(panels_data),
            "descriptions": len(descriptions),
            "data_entries": sum(len(entries) for entries in panels_data.values()),
        },
    }


def assemble_and_validate(
    output_dir: Path,
    manifest: RunManifest | None = None,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    manifest = manifest or RunManifest.load(output_dir)
    panels_data_path = output_dir / "panels_data.json"
    panels_data = json.loads(panels_data_path.read_text(encoding="utf-8"))
    markdown = build_markdown(output_dir, manifest, panels_data)

    paper_name = manifest.artifact("paper_name")
    markdown_path = output_dir / f"{paper_name}_complete.md"
    write_text_atomic(markdown_path, markdown)
    report = validate_output(output_dir, manifest, markdown, panels_data)
    report_path = output_dir / "quality_report.json"
    write_json_atomic(report_path, report)

    manifest.set_artifact("assembled_markdown", markdown_path.name, save=False)
    manifest.set_artifact("quality_report", report_path.name, save=False)
    manifest.set_stage(
        "assemble",
        "completed" if report["ok"] else "failed",
        error=None if report["ok"] else "; ".join(report["errors"]),
        save=False,
    )
    manifest.save()
    return {
        "markdown_path": markdown_path,
        "report_path": report_path,
        "report": report,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble and validate PDF2MD Markdown")
    parser.add_argument("output_dir")
    args = parser.parse_args()
    result = assemble_and_validate(Path(args.output_dir).resolve())
    report = result["report"]
    print(f"Markdown: {result['markdown_path']}")
    print(f"Quality report: {result['report_path']}")
    print(f"Quality gate: {'PASS' if report['ok'] else 'FAIL'}")
    for error in report["errors"]:
        print(f"ERROR: {error}")
    for warning in report["warnings"]:
        print(f"WARNING: {warning}")
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
