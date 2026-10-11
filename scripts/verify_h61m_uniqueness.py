#!/usr/bin/env python3
"""Compatibility verifier using the shared literal one-sided overlap gate.

The previous verifier substituted Jaccard when the comparator was dense. That
exception is retired; this wrapper delegates to the repository's canonical
local-artifact audit and exits nonzero when H61-M fails.
"""
from __future__ import annotations

import json
from pathlib import Path

from audit_local_artifact_dots import main as run_shared_dot_audit

ROOT = Path(__file__).resolve().parents[1]
H61M = "docs/downloads/gems61-h61m-gravmag-corridor-ribbon-40000dots-20261011T051415Z-zeros.tif"


def main() -> int:
    run_shared_dot_audit()
    report = json.loads((ROOT / "evidence/local_artifact_strict_dot_audit.json").read_text())
    row = next((candidate for candidate in report["candidates"]
                if H61M in candidate["paths"]), None)
    if row is None:
        print("H61-M TIFF is missing from the indexed local-artifact audit; fail closed.")
        return 2
    print(f"H61-M strict overlap={row['one_sided_overlap_fraction']:.6%}; "
          f"verdict={row['verdict']}; cleared={row['cleared_for_submission']}")
    return 1 if row["overlap_stop"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
