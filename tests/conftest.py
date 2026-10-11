"""Test path setup, one place.

The suite is run as ``.venv/bin/python -m pytest tests/`` from the repository root;
the package lives in ``src/`` and is not installed, so it has to be on ``sys.path``
before any test module imports it.
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
