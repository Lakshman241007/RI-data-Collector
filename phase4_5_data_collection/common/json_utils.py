"""
common/json_utils.py
JSON read/write helpers with consistent encoding and error handling.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    """
    Load and return the JSON content of *path*.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    json.JSONDecodeError
        If the file contains invalid JSON.
    """
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def save_json(data: Any, path: Path, *, indent: int = 2) -> None:
    """
    Serialise *data* to JSON and write it to *path*.

    Parameters
    ----------
    data:
        JSON-serialisable object.
    path:
        Destination file (parent directories must already exist).
    indent:
        Pretty-print indentation level (default 2).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=indent, ensure_ascii=False, default=str)


def safe_load_json(path: Path, default: Any = None) -> Any:
    """
    Like :func:`load_json` but returns *default* on any error instead of
    raising.
    """
    try:
        return load_json(path)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        return default
