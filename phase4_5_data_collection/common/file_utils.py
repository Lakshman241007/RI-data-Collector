"""
common/file_utils.py
File-system helpers used across all collectors.
"""
from __future__ import annotations

import gzip
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


def ensure_dir(path: Path) -> Path:
    """Create *path* (and parents) if it does not exist. Returns *path*."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def file_size_bytes(path: Path) -> int:
    """Return the size of *path* in bytes, or 0 if it does not exist."""
    return path.stat().st_size if path.exists() else 0


def timestamp_utc() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


def archive_file(src: Path, dest_dir: Path, compress: bool = False) -> Path:
    """
    Copy *src* into *dest_dir*, optionally compressing with gzip.

    Parameters
    ----------
    src:
        Source file.
    dest_dir:
        Destination directory (created if absent).
    compress:
        If ``True`` the file is stored as ``<name>.gz``.

    Returns
    -------
    Path
        Path of the archived file inside *dest_dir*.
    """
    ensure_dir(dest_dir)
    if compress:
        dest = dest_dir / (src.name + ".gz")
        with src.open("rb") as f_in, gzip.open(dest, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    else:
        dest = dest_dir / src.name
        shutil.copy2(src, dest)
    return dest


def iter_files(directory: Path, suffix: str = "") -> Iterator[Path]:
    """
    Yield all files in *directory* (recursively) optionally filtered by *suffix*.

    Parameters
    ----------
    directory:
        Root directory to walk.
    suffix:
        If non-empty only files whose name ends with this suffix are yielded
        (e.g. ``".json"``).
    """
    for p in directory.rglob("*"):
        if p.is_file():
            if suffix and not p.name.endswith(suffix):
                continue
            yield p


def safe_filename(name: str) -> str:
    """
    Convert *name* to a safe filename by replacing special characters.
    """
    return (
        name.strip()
        .lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
    )
