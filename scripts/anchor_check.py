#!/usr/bin/env python3
"""Calibrate the holdout: score the registry's own scored rasters on the SAME folds.

WHY THIS EXISTS.  A holdout number on its own says nothing.  0.02 could mean "the lane
is weak" or "the holdout is hard".  The only way to tell them apart is to put a raster
whose competition score is known into the same harness and see what it gets.

If a raster the group reports at 0.2600 also scores low here, then this holdout is
harder than the competition's hidden set and the lane's number must be read relative
to the anchor, not relative to the leaderboard.  If it scores high here, then the lane
really is weaker than what is already in the registry, and the honest verdict is
negative.  Either answer is a result; the script just reports it.

    python scripts/anchor_check.py --data data --registry /tmp/refs/registry
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import numpy as np
import rasterio

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fields import greedy_peaks  # noqa: E402
from holdout import make_contexts, make_folds  # noqa: E402

CLAIMED = {
    "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif": 0.2778,
    "gems28-h36-1-rung30-blind-r1-20261003-b531dae0a36f-allfinite.tif": 0.2710,
    "gems28-h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc-allfinite.tif": 0.2708,
    "gemsdoe30-d28-poisson300m-offcat-44090-20261003T233156Z-91eae1ca.tif": 0.2600,
    "gems27-topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-allfinite.tif": 0.2449,
    "gems49-gate_ortho_w0.25-40k-20261006T213721Z-zeros.tif": 0.2376,
    "gemsdoe29-sgmc-off-catalogue-44k-20261003-c8dcd780e3fd-nan.tif": 0.0512,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--registry", default="/tmp/refs/registry")
    ap.add_argument("--out", default="reports/anchor.json")
    ap.add_argument("--seed", type=int, default=3)
    args = ap.parse_args()

    with rasterio.open(os.path.join(args.data, "labels.tif")) as s:
        labels = s.read(1)
    valid = labels != -1
    gt = labels == 1

    folds = make_folds(gt, valid, n_rows=6, n_cols=6, n_folds=4, buffer_px=6,
                       min_segment_px=8)
    ctxs = make_contexts(folds, valid)

    rng = np.random.default_rng(args.seed)
    rows = []

    # random control at the median registry pixel count
    for k in (10000, 44090):
        per = []
        for ctx in ctxs:
            m, _ = greedy_peaks(np.where(valid, rng.random(valid.shape), 0.0), valid,
                                k=k, min_sep=3)
            per.append(float(ctx.score(np.where(m, 1.0, 0.0))["dti"]))
        rows.append(dict(name=f"RANDOM k={k}", claimed=None,
                         dti_mean=round(float(np.mean(per)), 6)))

    for p in sorted(glob.glob(os.path.join(args.registry, "*.tif"))):
        base = os.path.basename(p)
        with rasterio.open(p) as s:
            a = np.nan_to_num(s.read(1).astype(np.float64), nan=0.0)
        np.clip(a, 0, 1, out=a)
        per = [float(c.score(a)["dti"]) for c in ctxs]
        rows.append(dict(name=base, claimed=CLAIMED.get(base),
                         n_nonzero=int((a > 0).sum()),
                         dti_mean=round(float(np.mean(per)), 6),
                         dti_per_fold=[round(v, 6) for v in per]))

    rows.sort(key=lambda r: -r["dti_mean"])
    out = dict(
        note="Registry rasters scored on the SAME spatially blocked holdout used for "
             "this project's lane field. This calibrates the holdout; it is not a "
             "leaderboard prediction for anyone.",
        folds=[dict(fold=f["fold"], n_hidden=f["n_hidden"]) for f in folds],
        total_hidden=int(sum(f["n_hidden"] for f in folds)),
        rows=rows,
    )
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=1)
    print(f"{'raster':<58}{'claimed':>9}{'holdout':>10}")
    for r in rows:
        print(f"{r['name'][:56]:<58}{str(r.get('claimed')):>9}{r['dti_mean']:>10.6f}")
    print("->", args.out)


if __name__ == "__main__":
    main()
