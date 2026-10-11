#!/usr/bin/env python3
"""Compatibility CLI for the evidence-driven status site builder.

The former H61-G builder hard-coded an invalid dense-reference/Jaccard
uniqueness exception and called owner-reported scores organizer-confirmed. It is
retired; pages are now rendered by ``build_site_status.py`` from current evidence.
"""
from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("build_site_status.py")),
                   run_name="__main__")
