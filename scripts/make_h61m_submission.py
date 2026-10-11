#!/usr/bin/env python3
"""Retired H61-M GeoTIFF writer.

This historical writer is disabled because its archived output fails the
corrected strict final-dot gate. Use only a new candidate pipeline that runs
the shared pre-placement gate before holdout/placement and the shared final-dot
gate before writing. No weekly slot is cleared by this script.
"""
from __future__ import annotations


def main() -> int:
    print("H61-M writer retired: it must not write a new or submission-ready TIFF.")
    print("The archived H61-M TIFF fails the strict dot gate; see the current run card.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
