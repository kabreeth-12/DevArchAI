from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


def load_json_from_path(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"CI/CD source not found: {path}")

    if path.is_dir():
        # Pick latest JSON file
        json_files = sorted(path.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not json_files:
            raise FileNotFoundError(f"No JSON files found in directory: {path}")
        path = json_files[0]

    # Handle files saved with UTF-8 BOM (common on Windows)
    return json.loads(path.read_text(encoding="utf-8-sig", errors="ignore"))


def load_payload(
    source_path: Optional[str] = None,
    raw_json: Optional[str] = None,
) -> Dict[str, Any]:
    if raw_json:
        return json.loads(raw_json)
    if source_path:
        return load_json_from_path(Path(source_path))
    raise ValueError("Either source_path or raw_json must be provided")
