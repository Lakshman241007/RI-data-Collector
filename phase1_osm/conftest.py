"""Ensures the project root is importable as a package source for tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
