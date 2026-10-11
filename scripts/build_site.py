#!/usr/bin/env python3
"""Compatibility CLI; all published pages use the current evidence-driven builder.

Older session-specific site generators could overwrite the fail-closed status
with stale submission claims. Keep their entry points, but delegate rendering to
``build_site_status.py`` so every caller publishes the same current verdict.
"""
from __future__ import annotations

import runpy
from pathlib import Path

# Shared with scripts/check_site.py so it validates exactly the current pages.
PAGES = [
    ("index.html", "Status"),
    ("executive-summary.html", "Executive summary & how to submit"),
    ("analysis.html", "Score provenance"),
    ("hypotheses.html", "Next hypotheses"),
    ("method.html", "Method"),
    ("holdout.html", "Holdout evidence"),
    ("irregularities.html", "Irregularities"),
    ("next-steps.html", "Next steps"),
    ("verify.html", "Verify"),
    ("submit.html", "Submission instructions"),
    ("limitations.html", "Limitations"),
]

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("build_site_status.py")),
                   run_name="__main__")
