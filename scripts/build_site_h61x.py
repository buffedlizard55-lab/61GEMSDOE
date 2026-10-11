#!/usr/bin/env python3
"""Compatibility CLI; render the current evidence-driven status site.

The former H61-X builder published stale "UNIQUE" and submission-ready claims
under the retired density/Jaccard exception. Keep this historical entry point
safe: all page builds delegate to the single strict status renderer.
"""
from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("build_site_status.py")),
                   run_name="__main__")
