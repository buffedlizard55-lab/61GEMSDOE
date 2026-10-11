#!/usr/bin/env python3
"""Run both uniqueness gate legs against every earlier family raster.

Surface leg: full-footprint Spearman rank correlation of the candidate's soft
surface against every registry raster (limit 0.90).
Dot leg: fraction of the candidate's dots within 3 px of one registry raster's
positive cells (limit 0.70).

The gate fails closed: a missing registry file or an incomplete scan is an
error, never evidence of uniqueness.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import grid as gd, uniqueness as uq  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--surface", default=None, help="soft surface .npy (pre-placement leg)")
    ap.add_argument("--dots", default=None, help="binary dot mask .npy (final-dot leg)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default="evidence/uniqueness.json")
    a = ap.parse_args()
    if a.surface is None and a.dots is None:
        raise SystemExit("provide --surface and/or --dots")

    g = gd.load_grid()
    surface = np.load(ROOT / a.surface) if a.surface else None
    dots = np.load(ROOT / a.dots).astype(bool) if a.dots else None
    if surface is not None:
        surface = np.where(g.footprint, surface, 0.0)

    started = time.time()
    def progress(i, n):
        print(f"[uniq] {i}/{n} ({time.time()-started:.0f}s)", flush=True)

    out = uq.check(surface, dots, g.footprint, root=ROOT, limit=a.limit, progress=progress)
    out["generated_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out["candidate"] = dict(surface=a.surface, dots=a.dots,
                            positive_pixels=int(dots.sum()) if dots is not None else None)
    (ROOT / a.out).write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    print(f"[uniq] n={out['n_registry_rasters']} worst_rho={out['worst_spearman']:.6f} "
          f"({out['worst_spearman_source']}) worst_overlap={out['worst_dot_overlap_3px']:.6f} "
          f"({out['worst_dot_overlap_source']}) unique={out['unique']}")
    return 0 if out["unique"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
