"""Resume a PDF2MD run from its persisted manifest."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from run_manifest import RunManifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Resume an interrupted PDF2MD run")
    parser.add_argument("output_dir")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    manifest = RunManifest.load(output_dir)
    pdf_path = manifest.data["pdf"]["path"]
    config_path = args.config or Path(__file__).resolve().parents[1] / "config.yaml"
    command = [
        sys.executable,
        "-X",
        "utf8",
        str(Path(__file__).with_name("pipeline.py")),
        pdf_path,
        "-o",
        str(output_dir),
        "--config",
        str(config_path),
        "--resume",
    ]
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
