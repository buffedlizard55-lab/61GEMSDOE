#!/usr/bin/env python3
"""Retired H61-X runner; historical outputs remain in evidence/ and docs/.

This pipeline's archived uniqueness screen used a dense-reference/Jaccard
exception and ran holdout before the corrected strict gate. It must not be used
to create or clear another TIFF. See the post-merge audit and current run card.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    print("H61-X runner retired: old candidate artifacts fail the strict final-dot gate.")
    print("No candidate/holdout is run. See evidence/local_artifact_strict_dot_audit.json")
    print("and evidence/h61l_run_card.json. Do not submit a repository TIFF.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
