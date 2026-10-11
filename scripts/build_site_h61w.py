#!/usr/bin/env python3
"""Compatibility CLI for the H61-W session.

The published pages are owned by the current evidence-driven builder
(``scripts/build_site_status.py``), which renders the fail-closed status from the
strict uniqueness audit.  Session-specific builders used to overwrite that status
with stale "safe to submit" claims, so this entry point is kept for the audit
trail but delegates rendering to the canonical builder.
"""
from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("build_site_status.py")), run_name="__main__")
