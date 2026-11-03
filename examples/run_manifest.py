"""Persistent run state for the PDF2MD pipeline."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MANIFEST_NAME = "run_manifest.json"
MANIFEST_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_atomic(path: Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def write_text_atomic(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


class RunManifest:
    def __init__(self, output_dir: Path, data: dict[str, Any]):
        self.output_dir = Path(output_dir)
        self.path = self.output_dir / MANIFEST_NAME
        self.data = data

    @classmethod
    def create(cls, output_dir: Path, pdf_path: Path) -> "RunManifest":
        now = utc_now()
        manifest = cls(
            output_dir,
            {
                "manifest_version": MANIFEST_VERSION,
                "created_at": now,
                "updated_at": now,
                "pdf": {
                    "path": str(Path(pdf_path).resolve()),
                    "sha256": sha256_file(pdf_path),
                },
                "stages": {},
                "artifacts": {},
                "panels": {},
                "usage": {},
            },
        )
        manifest.save()
        return manifest

    @classmethod
    def load(cls, output_dir: Path) -> "RunManifest":
        path = Path(output_dir) / MANIFEST_NAME
        if not path.is_file():
            raise FileNotFoundError(f"Run manifest not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("manifest_version") != MANIFEST_VERSION:
            raise ValueError(f"Unsupported manifest version: {data.get('manifest_version')}")
        return cls(output_dir, data)

    def save(self) -> None:
        self.data["updated_at"] = utc_now()
        write_json_atomic(self.path, self.data)

    def stage(self, name: str) -> dict[str, Any]:
        return self.data.setdefault("stages", {}).get(name, {"status": "pending"})

    def stage_completed(self, name: str) -> bool:
        return self.stage(name).get("status") == "completed"

    def set_stage(
        self,
        name: str,
        status: str,
        *,
        error: str | None = None,
        save: bool = True,
    ) -> None:
        entry = {"status": status, "updated_at": utc_now()}
        if error:
            entry["error"] = error
        self.data.setdefault("stages", {})[name] = entry
        if save:
            self.save()

    def artifact(self, name: str, default: Any = None) -> Any:
        return self.data.setdefault("artifacts", {}).get(name, default)

    def set_artifact(self, name: str, value: Any, *, save: bool = True) -> None:
        self.data.setdefault("artifacts", {})[name] = value
        if save:
            self.save()

    def set_panel_status(
        self,
        panel_name: str,
        status: str,
        *,
        error: str | None = None,
        save: bool = True,
    ) -> None:
        entry = {"status": status, "updated_at": utc_now()}
        if error:
            entry["error"] = error
        self.data.setdefault("panels", {})[panel_name] = entry
        if save:
            self.save()

    def set_usage(self, source: str, usage: dict[str, int]) -> None:
        self.data.setdefault("usage", {})[source] = {
            key: int(value) for key, value in usage.items()
        }

    def add_usage(self, usage: dict[str, int], source: str = "vlm") -> None:
        total = self.data.setdefault("usage", {}).setdefault(source, {})
        for key, value in usage.items():
            total[key] = int(total.get(key, 0)) + int(value)

    def validate_pdf(self, pdf_path: Path) -> None:
        expected = self.data.get("pdf", {}).get("sha256")
        actual = sha256_file(pdf_path)
        if expected != actual:
            raise ValueError("Input PDF does not match the existing run manifest")
