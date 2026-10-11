#!/usr/bin/env python3
"""Deprecated H61-MH site-builder alias.

The old builder publishes a stale H61-MH UNIQUE/download-ready claim. This
compatibility entry point now delegates only to the canonical evidence-driven
status builder, which marks every failing artifact as not cleared.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    print("DEPRECATED: delegating to scripts/build_site_status.py; "
          "the H61-MH artifact is not cleared for submission.", file=sys.stderr)
    runpy.run_path(str(ROOT / "scripts" / "build_site_status.py"), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
