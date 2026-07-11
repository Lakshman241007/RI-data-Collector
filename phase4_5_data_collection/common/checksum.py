"""
common/checksum.py
SHA-256 checksum utilities for file integrity verification.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


BUFFER_SIZE = 1 << 20  # 1 MiB


def sha256_file(path: Path) -> str:
    """
    Compute the SHA-256 hex digest of *path*.

    Parameters
    ----------
    path:
        Path to the file to hash.

    Returns
    -------
    str
        64-character lowercase hex digest.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"Checksum: file not found – {path}")

    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(BUFFER_SIZE):
            h.update(chunk)
    return h.hexdigest()


def verify_checksum(path: Path, expected: str) -> bool:
    """
    Verify that *path* matches *expected* SHA-256 hex digest.

    Returns
    -------
    bool
        ``True`` if the digest matches, ``False`` otherwise.
    """
    actual = sha256_file(path)
    return actual.lower() == expected.lower()
