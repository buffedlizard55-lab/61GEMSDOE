#!/usr/bin/env python3
"""Compatibility CLI for the current evidence-driven status site builder.

The historical E2 page is no longer a current clearance source. Delegate to
the single status renderer so old entry points cannot publish stale verdicts.
"""
from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("build_site_status.py")),
                   run_name="__main__")
