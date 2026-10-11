#!/usr/bin/env python3
"""Run the shared, literal pre-placement and/or final-dot uniqueness gate.

Requires the complete hash/grid-verified declared inventory. Partial registry
subsets are not a clearance source; no density/Jaccard exception is applied.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import gates, grid  # noqa: E402


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--surface", type=Path, help="continuous candidate surface .npy")
    parser.add_argument("--dots", type=Path, help="final candidate raster/mask .npy")
    parser.add_argument("--inventory", type=Path, default=Path("evidence/registry_accessible_index.json"))
    parser.add_argument("--out", type=Path, default=Path("evidence/uniqueness.json"))
    args = parser.parse_args()
    if args.surface is None and args.dots is None:
        parser.error("provide --surface and/or --dots")

    inventory_path = args.inventory if args.inventory.is_absolute() else ROOT / args.inventory
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    if not inventory.get("declared_scope_complete") or inventory.get("errors"):
        raise SystemExit("incomplete registry inventory; uniqueness fails closed")
    g = grid.load_grid()
    sample = grid.DATA_DIR / "sample_submission.tif"
    started = time.time()

    def check(path: Path, phase: str) -> dict:
        resolved = path if path.is_absolute() else ROOT / path
        candidate = np.load(resolved, mmap_mode="r")
        if candidate.ndim != 2:
            raise ValueError(f"{resolved}: expected a 2-D array, got {candidate.shape}")
        print(f"[uniq] {phase} against {len(inventory['rasters'])} indexed rasters", flush=True)
        report = gates.lane_uniqueness_report(
            np.asarray(candidate), g.footprint, sample=sample, phase=phase,
            registry_index=inventory,
            log=lambda message: print(f"[uniq] {message}", flush=True),
        )
        report["candidate_path"] = str(resolved.relative_to(ROOT) if resolved.is_relative_to(ROOT) else resolved)
        report["inventory_path"] = inventory_path.relative_to(ROOT).as_posix()
        report["elapsed_s"] = time.time() - started
        return report

    results = []
    if args.surface is not None:
        results.append(check(args.surface, "surface"))
    if args.dots is not None:
        results.append(check(args.dots, "dots"))
    output = dict(
        evidence_class="MEASURED shared strict uniqueness gate",
        inventory_path=inventory_path.relative_to(ROOT).as_posix(),
        declared_scope_complete=inventory["declared_scope_complete"],
        organizer_registry_complete=inventory.get("organizer_registry_complete", False),
        unique=all(row["unique"] for row in results),
        results=results,
    )
    out_path = args.out if args.out.is_absolute() else ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(json_safe(output), indent=2, allow_nan=False) + "\n",
                        encoding="utf-8")
    for row in results:
        print(f"[uniq] {row['phase']}: {row['verdict']} (unique={row['unique']})")
    print(f"[uniq] receipt: {out_path}")
    return 0 if output["unique"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
