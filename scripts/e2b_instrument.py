#!/usr/bin/env python3
"""RETIRED historical holdout/instrument calibration.

The prior analysis compared proxy holdout rankings with unverified owner-reported
scores. It is not a competition score, and the current experiment budget is
exhausted. The CLI is disabled; retained outputs are historical only.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np
import rasterio

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import io as gio        # noqa: E402
from gems61 import holdout as ho    # noqa: E402
from scipy import ndimage           # noqa: E402
from scipy.stats import spearmanr   # noqa: E402

# file -> owner-reported live score (group ledger; NOT organiser-confirmed)
REGISTRY = {
    "h19_5_01922.tif": dict(live=0.1922, site="GEMSDOE19 h19-5-powerlaw"),
    "d15_02477.tif": dict(live=0.2477, site="GEMSDOE24 h25-1-dotted-d1.5"),
    "dotted_d2_8_02600.tif": dict(live=0.2600, site="GEMSDOE25 dotted-h19-5-d2.8"),
    "dotted_d2_8_02708.tif": dict(live=0.2708, site="GEMSDOE31 h27-4-solo-d2.8"),
    "dotted_b2_prune_02778.tif": dict(live=0.2778, site="GEMSDOE32 h33-2-b2 (audit says UNSCORED)"),
    "h36_rung30_02710.tif": dict(live=0.2710, site="GEMSDOE28 h36-1-rung30-blind-r1"),
    "tip_stepover_r30_02632.tif": dict(live=0.2632, site="GEMSDOE33 h33d-analog-tip-stepover"),
    "sgmc44k_00512.tif": dict(live=0.0512, site="GEMSDOE29 sgmc-off-catalogue-44k"),
}


def main() -> int:
    t0 = time.time()
    grid = gio.load_grid(verify=False)
    folds = ho.make_folds(grid.footprint, grid.catalogue, n_folds=4, collar_px=3, min_px=20)
    # distance from every pixel to the nearest catalogue pixel (all of it)
    d_cat = ndimage.distance_transform_edt(~grid.catalogue, sampling=100.0)

    rows = {}
    for name, info in REGISTRY.items():
        p = ROOT / "data" / "registry" / name
        with rasterio.open(p) as src:
            a = src.read(1)
        pred_all = (a > 0.5) & np.isfinite(a)
        TP = FP = FN = 0.0
        sumk = 0.0
        nP = nT = 0
        per = {}
        for f in folds:
            P = pred_all & f.domain
            cov, pool, parts = ho.dti(f.hidden, P, f.domain)
            TP += parts["TP"]; FP += parts["FP"]; FN += parts["FN"]
            nP += parts["n_pred"]; nT += parts["n_truth"]
            per[f.name] = dict(cov=cov, pool=pool)
            d_truth = ndimage.distance_transform_edt(~(f.hidden & f.domain), sampling=100.0)
            sumk += float(np.clip(1 - d_truth[P] / 300.0, 0, 1).sum())
        dti_cov = TP / (TP + 0.2 * FP + 0.8 * FN)
        dti_pool = sumk / (0.2 * nP + 0.8 * nT)
        rows[name] = dict(
            site=info["site"], live_owner_reported=info["live"],
            n_pos=int(pred_all.sum()),
            n_pos_in_domain=int((pred_all & folds[0].domain).sum()),
            dti_coverage=float(dti_cov), dti_pooled=float(dti_pool),
            mean_kernel_credit_per_dot=float(sumk / max(nP, 1)),
            frac_dots_within_300m_of_any_catalogue=float(
                (pred_all & (d_cat <= 300)).sum() / max(pred_all.sum(), 1)),
            median_dist_to_catalogue_m=float(np.median(d_cat[pred_all])),
            per_fold=per)
        print(f"{name:28s} live={info['live']:.4f} cov={dti_cov:.5f} pool={dti_pool:.5f} "
              f"n={int(pred_all.sum()):6d} k={sumk/max(nP,1):.4f} "
              f"<300m={rows[name]['frac_dots_within_300m_of_any_catalogue']:.3f} "
              f"medD={rows[name]['median_dist_to_catalogue_m']:.0f}m", flush=True)

    live = np.array([rows[k]["live_owner_reported"] for k in REGISTRY])
    rows["_summary"] = {}
    for conv in ("dti_coverage", "dti_pooled"):
        v = np.array([rows[k][conv] for k in REGISTRY])
        rho = spearmanr(v, live)
        rows.setdefault("_summary", {})[conv] = dict(
            spearman_vs_live=float(rho.statistic), p=float(rho.pvalue), n=len(v))
        print(f"rank corr {conv:14s} vs owner-reported live: rho={rho.statistic:+.4f} p={rho.pvalue:.4f}")
    # also: does kernel credit per dot alone explain the live ranking?
    v = np.array([rows[k]["mean_kernel_credit_per_dot"] for k in REGISTRY])
    rho = spearmanr(v, live)
    rows["_summary"]["mean_kernel_credit"] = dict(spearman_vs_live=float(rho.statistic),
                                                  p=float(rho.pvalue), n=len(v))
    print(f"rank corr kernel credit vs live: rho={rho.statistic:+.4f} p={rho.pvalue:.4f}")
    v = np.array([rows[k]["median_dist_to_catalogue_m"] for k in REGISTRY])
    rho = spearmanr(v, live)
    rows["_summary"]["median_dist_to_catalogue"] = dict(
        spearman_vs_live=float(rho.statistic), p=float(rho.pvalue), n=len(v))
    print(f"rank corr median-dist-to-catalogue vs live: rho={rho.statistic:+.4f} p={rho.pvalue:.4f}")
    v = np.array([rows[k]["frac_dots_within_300m_of_any_catalogue"] for k in REGISTRY])
    rho = spearmanr(v, live)
    rows["_summary"]["frac_dots_within_300m_catalogue"] = dict(
        spearman_vs_live=float(rho.statistic), p=float(rho.pvalue), n=len(v))
    print(f"rank corr frac-dots-<300m-of-catalogue vs live: rho={rho.statistic:+.4f} p={rho.pvalue:.4f}")
    v = np.array([rows[k]["n_pos"] for k in REGISTRY])
    rho = spearmanr(v, live)
    rows["_summary"]["n_pos"] = dict(spearman_vs_live=float(rho.statistic),
                                     p=float(rho.pvalue), n=len(v))
    print(f"rank corr n_positive_pixels vs live: rho={rho.statistic:+.4f} p={rho.pvalue:.4f}")
    rows["_summary"]["seconds"] = time.time() - t0
    (ROOT / "evidence" / "e2b_instrument.json").write_text(json.dumps(rows, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(
        "Retired: this historical instrument calibration compares HOLDOUT-DTI to "
        "owner-reported scores and is not authorized for a new experiment."
    )
