#!/usr/bin/env python3
"""
Check for failed panel extractions in processed PDFs.
Scans panels_data.json files and reports panels with fig_type="error".

Usage:
    python examples/check_failures.py <processed_dir>

Example:
    python examples/check_failures.py ~/PDFs/processed/
"""

import json
import sys
from pathlib import Path
from collections import defaultdict


def check_failures(processed_dir):
    """Check all PDFs in processed_dir for failed panels."""
    processed_dir = Path(processed_dir)
    if not processed_dir.exists():
        print(f"Error: Directory not found: {processed_dir}")
        sys.exit(1)

    # Statistics
    total_failures = 0
    pdf_stats = {}
    error_types = defaultdict(int)

    if (processed_dir / "panels_data.json").is_file():
        pdf_dirs = [processed_dir]
    else:
        pdf_dirs = sorted(path for path in processed_dir.iterdir() if path.is_dir())

    # Scan PDF output directories
    for pdf_dir in pdf_dirs:

        panels_data_path = pdf_dir / "panels_data.json"
        if not panels_data_path.exists():
            continue

        # Load panels data
        try:
            with open(panels_data_path, 'r', encoding='utf-8') as f:
                panels_data = json.load(f)
        except Exception as e:
            print(f"Warning: Could not load {panels_data_path}: {e}")
            continue

        # Check for failures
        failures = []
        for panel_name, entries in panels_data.items():
            if not isinstance(entries, list):
                continue

            for entry in entries:
                if isinstance(entry, dict) and entry.get('fig_type') == 'error':
                    error_msg = entry.get('content', 'Unknown error')
                    failures.append({
                        'panel': panel_name,
                        'error': error_msg
                    })

                    # Categorize error type
                    if 'timeout' in error_msg.lower():
                        error_types['timeout'] += 1
                    elif '429' in error_msg or 'rate limit' in error_msg.lower():
                        error_types['rate_limit'] += 1
                    elif '400' in error_msg or 'bad request' in error_msg.lower():
                        error_types['bad_request'] += 1
                    elif '401' in error_msg or 'unauthorized' in error_msg.lower():
                        error_types['auth_error'] += 1
                    elif '500' in error_msg or 'internal server' in error_msg.lower():
                        error_types['server_error'] += 1
                    else:
                        error_types['other'] += 1

        if failures:
            pdf_stats[pdf_dir.name] = failures
            total_failures += len(failures)

    # Print summary
    print("📊 失败统计 | Failure Summary")
    print("=" * 60)
    print(f"总失败数 | Total failures: {total_failures}")
    print(f"失败PDF数 | PDFs with failures: {len(pdf_stats)}")
    print()

    # Error type breakdown
    if error_types:
        print("错误类型分布 | Error Type Breakdown:")
        for error_type, count in sorted(error_types.items(), key=lambda x: -x[1]):
            print(f"  - {error_type}: {count}")
        print()

    # Per-PDF details
    for pdf_name, failures in sorted(pdf_stats.items()):
        print(f"📄 {pdf_name}: {len(failures)} failures")
        for fail in failures[:5]:  # Show first 5
            error_short = fail['error'][:80] + "..." if len(fail['error']) > 80 else fail['error']
            print(f"  - {fail['panel']}: {error_short}")
        if len(failures) > 5:
            print(f"  ... and {len(failures) - 5} more")
        print()

    return total_failures, pdf_stats


def main():
    if len(sys.argv) < 2:
        print("Usage: python examples/check_failures.py <processed_dir>")
        print("Example: python examples/check_failures.py ~/PDFs/processed/")
        sys.exit(1)

    processed_dir = sys.argv[1]
    total_failures, pdf_stats = check_failures(processed_dir)

    if total_failures == 0:
        print("✅ No failures found! All panels extracted successfully.")
        sys.exit(0)
    else:
        print(f"💡 Run retry to fix failures:")
        print(f"   python examples/retry_failures.py {processed_dir}")
        sys.exit(1)


if __name__ == "__main__":
    main()
