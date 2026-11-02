#!/usr/bin/env python3
"""
Retry failed panel extractions in processed PDFs.
Re-processes panels with fig_type="error" by calling VLM API again.

Usage:
    python examples/retry_failures.py [options] <processed_dir>

Options:
    --max-retries N     Max retry attempts per panel (default: 3)
    --delay SECONDS     Delay between API calls (default: 0.5)
    --parallel N        Number of parallel workers (default: 1)
    --pdf NAME          Only process specific PDF(s), can be used multiple times
    --dry-run           Show what would be retried without actually retrying
    --verbose           Show detailed output

Example:
    python examples/retry_failures.py ~/PDFs/processed/
    python examples/retry_failures.py --parallel 5 --pdf Tang_2025 ~/PDFs/processed/
"""

import json
import sys
import os
import base64
import time
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path to import pipeline functions
sys.path.insert(0, str(Path(__file__).parent))
from pipeline import call_vlm, configure_runtime, extract_json, load_config, load_panel_prompt


def retry_single_panel(panel_path, caption, panel_prompt, model, api_base, api_key, max_retries=3):
    """
    Retry a single panel extraction.

    Returns:
        tuple: (success: bool, result: list or None, error_msg: str or None)
    """
    for attempt in range(max_retries):
        try:
            # Encode image
            with open(panel_path, 'rb') as f:
                img_data = f.read()
            img_b64 = base64.b64encode(img_data).decode('utf-8')

            # Prepare prompt
            prompt = panel_prompt.replace('{caption}', caption)

            # Call VLM
            response = call_vlm(img_b64, prompt, model, api_base, api_key, max_tokens=4000, timeout=180)

            # Extract JSON
            result = extract_json(response)

            return True, result, None

        except Exception as e:
            error_msg = str(e)
            if attempt < max_retries - 1:
                # Wait before retry
                time.sleep(1)
            else:
                return False, None, error_msg

    return False, None, "Max retries exceeded"


def process_pdf(pdf_dir, panel_prompt, model, api_base, api_key, args):
    """Process a single PDF directory."""
    pdf_name = pdf_dir.name
    panels_data_path = pdf_dir / "panels_data.json"
    descriptions_path = pdf_dir / "descriptions.json"
    panels_dir = pdf_dir / "panels"

    if not panels_data_path.exists():
        print(f"⚠️  {pdf_name}: panels_data.json not found, skipping")
        return 0, 0, []

    # Load panels data
    try:
        with open(panels_data_path, 'r', encoding='utf-8') as f:
            panels_data = json.load(f)
    except Exception as e:
        print(f"⚠️  {pdf_name}: Could not load panels_data.json: {e}")
        return 0, 0, []

    # Load descriptions
    descriptions = {}
    if descriptions_path.exists():
        try:
            with open(descriptions_path, 'r', encoding='utf-8') as f:
                descriptions = json.load(f)
        except Exception as e:
            print(f"⚠️  {pdf_name}: Could not load descriptions.json: {e}")

    # Find failed panels
    failed_panels = []
    for panel_name, entries in panels_data.items():
        if not isinstance(entries, list):
            continue

        for entry in entries:
            if isinstance(entry, dict) and entry.get('fig_type') == 'error':
                failed_panels.append(panel_name)
                break

    if not failed_panels:
        return 0, 0, []

    print(f"📄 {pdf_name}: {len(failed_panels)} failed panels")

    if args.dry_run:
        for panel_name in failed_panels:
            print(f"  - Would retry: {panel_name}")
        return 0, len(failed_panels), []

    # Retry failed panels
    success_count = 0
    fail_count = 0
    retry_errors = []

    def retry_panel_task(panel_name):
        panel_path = panels_dir / panel_name
        if not panel_path.exists():
            return panel_name, False, None, f"Panel file not found: {panel_path}"

        caption = descriptions.get(panel_name, "")
        if not isinstance(caption, str):
            caption = ""

        success, result, error = retry_single_panel(
            panel_path, caption, panel_prompt, model, api_base, api_key, args.max_retries
        )

        return panel_name, success, result, error

    # Process panels (parallel or sequential)
    if args.parallel > 1:
        with ThreadPoolExecutor(max_workers=args.parallel) as executor:
            futures = {executor.submit(retry_panel_task, panel): panel for panel in failed_panels}

            for future in as_completed(futures):
                panel_name, success, result, error = future.result()

                if success:
                    panels_data[panel_name] = result
                    success_count += 1
                    if args.verbose:
                        print(f"  ✅ {panel_name}: Success")
                else:
                    fail_count += 1
                    retry_errors.append({'panel': panel_name, 'error': error})
                    if args.verbose:
                        print(f"  ❌ {panel_name}: {error}")

                # Delay between requests
                if args.delay > 0:
                    time.sleep(args.delay)
    else:
        for panel_name in failed_panels:
            panel_name, success, result, error = retry_panel_task(panel_name)

            if success:
                panels_data[panel_name] = result
                success_count += 1
                if args.verbose:
                    print(f"  ✅ {panel_name}: Success")
            else:
                fail_count += 1
                retry_errors.append({'panel': panel_name, 'error': error})
                if args.verbose:
                    print(f"  ❌ {panel_name}: {error}")

            # Delay between requests
            if args.delay > 0:
                time.sleep(args.delay)

    # Save updated panels data
    if success_count > 0 and not args.dry_run:
        try:
            with open(panels_data_path, 'w', encoding='utf-8') as f:
                json.dump(panels_data, f, ensure_ascii=False, indent=2)
            print(f"  💾 Updated panels_data.json ({success_count} fixed, {fail_count} still failed)")
        except Exception as e:
            print(f"  ⚠️  Could not save panels_data.json: {e}")

    return success_count, fail_count, retry_errors


def main():
    parser = argparse.ArgumentParser(description='Retry failed panel extractions')
    parser.add_argument('processed_dir', help='Processed PDFs directory')
    parser.add_argument('--max-retries', type=int, default=3, help='Max retry attempts per panel (default: 3)')
    parser.add_argument('--delay', type=float, default=0.5, help='Delay between API calls in seconds (default: 0.5)')
    parser.add_argument('--parallel', type=int, default=1, help='Number of parallel workers (default: 1)')
    parser.add_argument('--pdf', action='append', help='Only process specific PDF(s), can be used multiple times')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be retried without actually retrying')
    parser.add_argument('--verbose', action='store_true', help='Show detailed output')

    args = parser.parse_args()

    processed_dir = Path(args.processed_dir)
    if not processed_dir.exists():
        print(f"Error: Directory not found: {processed_dir}")
        sys.exit(1)

    # Load config
    config_path = Path(__file__).parent.parent / "config.yaml"
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)

    config = load_config(config_path)
    configure_runtime(config)
    model = config['model']
    api_base = config['api_base']
    api_key = config['api_key']

    # Load panel prompt
    panel_prompt = load_panel_prompt()

    print("🔄 PDF2MD Retry Tool")
    print("=" * 60)
    print(f"Processed dir: {processed_dir}")
    print(f"Max retries: {args.max_retries}")
    print(f"Delay: {args.delay}s")
    print(f"Parallel workers: {args.parallel}")
    if args.pdf:
        print(f"Filter PDFs: {', '.join(args.pdf)}")
    if args.dry_run:
        print("Mode: DRY RUN (no changes will be made)")
    print()

    # Process PDFs
    total_success = 0
    total_fail = 0
    total_skipped = 0
    all_errors = []

    pdf_dirs = sorted([d for d in processed_dir.iterdir() if d.is_dir()])

    if args.pdf:
        # Filter to specific PDFs
        pdf_dirs = [d for d in pdf_dirs if d.name in args.pdf]

    for pdf_dir in pdf_dirs:
        success, fail, errors = process_pdf(pdf_dir, panel_prompt, model, api_base, api_key, args)
        total_success += success
        total_fail += fail
        all_errors.extend(errors)

    # Summary
    print()
    print("=" * 60)
    print("📊 重试统计 | Retry Summary")
    print("=" * 60)
    print(f"成功修复 | Successfully fixed: {total_success}")
    print(f"仍然失败 | Still failed: {total_fail}")

    if args.dry_run:
        print(f"待处理 | Would retry: {total_success + total_fail}")
    else:
        if total_success > 0:
            print()
            print("💡 Next steps:")
            print("   1. Reassemble markdown files if needed:")
            print("      python examples/assemble_md.py <pdf_dir>")
            print("   2. Check remaining failures:")
            print(f"      python examples/check_failures.py {processed_dir}")

    if all_errors and args.verbose:
        print()
        print("❌ Failed panels:")
        for err in all_errors[:10]:
            print(f"  - {err['panel']}: {err['error'][:60]}")
        if len(all_errors) > 10:
            print(f"  ... and {len(all_errors) - 10} more")


if __name__ == "__main__":
    main()
