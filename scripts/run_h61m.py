#!/usr/bin/env python3
"""Retired H61-M runner; its measured outputs are retained as historical evidence.

The old pipeline performed its holdout before final uniqueness and used a
partial, locally implemented registry screen. The archived H61-M TIFF now
measures 94.6836% one-sided overlap with an earlier raster, above the strict
70% stop. Do not rerun it or treat its old UNIQUE label as clearance.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    print("H61-M runner retired: archived TIFF fails strict one-sided overlap at 94.6836%.")
    print("No candidate/holdout is run. See evidence/local_artifact_strict_dot_audit.json")
    print("and evidence/h61l_run_card.json. Do not submit any repository TIFF.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
