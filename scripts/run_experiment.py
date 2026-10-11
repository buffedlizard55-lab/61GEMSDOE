#!/usr/bin/env python3
"""Experiments 1-3 for the buried-structure lane.

Experiment 1  inversion sanity + leakage canary on every candidate field
Experiment 2  operating-point sweep on a spatially blocked hide-and-recover holdout,
              with the random-line control the lane protocol demands
Experiment 3  basin-interior recovery (the lane's actual claim) + block bootstrap CI

Usage:
    python scripts/run_experiment.py --data data --out reports
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import rasterio

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from fields import auc, greedy_peaks, normalise_field, off_catalogue_mask  # noqa: E402
from gravity import (fill_nodata, horizontal_gradient_magnitude,  # noqa: E402
                     parker_oldenburg_invert)
from holdout import basin_interior_mask, make_contexts, make_folds  # noqa: E402


def load(path):
    with rasterio.open(path) as s:
        return s.read(1)


def plane_detrend(a, valid):
    H, W = a.shape
    yy, xx = np.mgrid[0:H, 0:W]
    xv = xx[valid].ravel().astype(np.float64)
    yv = yy[valid].ravel().astype(np.float64)
    zv = np.asarray(a, dtype=np.float64)[valid].ravel()
    A = np.stack([xv, yv, np.ones_like(xv)], axis=1)
    coef, *_ = np.linalg.lstsq(A, zv, rcond=None)
    return a - (coef[0] * xx + coef[1] * yy + coef[2])


def block_contributions(ctx, pred, nblk=20):
    """Per-block TP_w / FP_w / |G| so the CI can be bootstrapped over space.

    Pooled DTI is a ratio of sums, so resampling whole spatial blocks and re-summing
    is a valid block bootstrap.  Block = (H//nblk) x (W//nblk) cells.
    """
    H, W = ctx.shape
    bh, bw = max(1, H // nblk), max(1, W // nblk)
    p = np.clip(np.nan_to_num(np.asarray(pred, np.float64), nan=0.0), 0, 1)
    p = p * ctx.valid_flat.reshape(ctx.shape)

    # FP per block
    fp = (p.ravel() * ctx.discount_flat).reshape(ctx.shape)
    fp_blk = fp[:bh * nblk, :bw * nblk].reshape(nblk, bh, nblk, bw).sum(axis=(1, 3))

    # TP per hidden pixel -> its block
    credit = np.zeros(ctx.n_gt)
    for dy, dx, k in ctx.offsets:
        sy, sx = ctx.gy + dy, ctx.gx + dx
        ok = (sy >= 0) & (sy < H) & (sx >= 0) & (sx < W)
        vals = np.zeros(ctx.n_gt)
        vals[ok] = p[sy[ok], sx[ok]]
        np.maximum(credit, k * vals, out=credit)

    by = np.clip(ctx.gy // bh, 0, nblk - 1)
    bx = np.clip(ctx.gx // bw, 0, nblk - 1)
    flat = by * nblk + bx
    tp_blk = np.bincount(flat, weights=credit, minlength=nblk * nblk)
    gt_blk = np.bincount(flat, minlength=nblk * nblk).astype(np.float64)
    return dict(tp=tp_blk, fp=fp_blk.ravel(), gt=gt_blk, n=nblk * nblk)


def bootstrap_dti(all_tp, all_fp, all_gt, n_boot=2000, alpha=0.2, beta=0.8, seed=11):
    """95 % CI for pooled DTI by resampling spatial blocks with replacement."""
    tp = np.concatenate(all_tp); fp = np.concatenate(all_fp); gt = np.concatenate(all_gt)
    rng = np.random.default_rng(seed)
    n = tp.size
    out = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, n)
        TP = tp[idx].sum(); FP = fp[idx].sum(); G = gt[idx].sum()
        out[b] = TP / (TP + alpha * FP + beta * (G - TP) + 1e-7)
    return dict(mean=float(out.mean()), lo=float(np.percentile(out, 2.5)),
                hi=float(np.percentile(out, 97.5)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="reports")
    ap.add_argument("--cache", default="/tmp/gems_fields.npz")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    t0 = time.time()

    labels = load(os.path.join(args.data, "labels.tif"))
    valid = labels != -1
    gt = labels == 1
    with rasterio.open(os.path.join(args.data, "training_features.tif")) as src:
        n_band = src.count
        feats = {i: src.read(i) for i in (3, 5, 6, 11, 13, 15, 18, 19)}
    b15 = feats[15]

    report = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    report["data"] = dict(shape=list(labels.shape), n_valid=int(valid.sum()),
                          n_gt=int(gt.sum()),
                          positive_fraction=round(float(gt.sum() / valid.sum()), 6),
                          n_features=int(n_band))

    # ------------------------------------------------- experiment 1: inversion ---
    te = time.time()
    if os.path.exists(args.cache):
        z = np.load(args.cache)
        hgm = z["hgm"].astype(np.float64)
        h_depth = z["h_depth"].astype(np.float64)
        print(f"[1] gravity field from cache ({time.time() - te:.0f}s)")
    else:
        b13 = feats[13].astype(np.float64)
        g = fill_nodata(b13, valid, sigma=25.0)
        gres = plane_detrend(g, valid)
        h = parker_oldenburg_invert(gres, 100.0, 100.0, z0=1200.0, drho=-420.0,
                                    max_depth=4000.0, n_terms=4, n_iter=6)
        h_depth = -h
        hgm = horizontal_gradient_magnitude(h_depth, valid, smooth_sigma=2.0)
        np.savez_compressed(args.cache, h_depth=h_depth.astype(np.float32),
                            hgm=hgm.astype(np.float32), gres=gres.astype(np.float32))
        print(f"[1] Parker-Oldenburg inversion done ({time.time() - te:.0f}s)")

    a, b = h_depth[valid], b15[valid]
    step = max(1, a.size // 200000)
    ra = np.argsort(np.argsort(a[::step]))
    rb = np.argsort(np.argsort(b[::step]))
    report["experiment1_inversion"] = dict(
        method="Parker (1973) forward / Oldenburg (1974) iterative inversion of band B13",
        params=dict(z0_m=1200.0, drho_kgm3=-420.0, cutoff_kc="0.5/z0", n_terms=4,
                    n_iter=6, filter="Gaussian band-pass exp(-(k z0 /0.5)^2)"),
        verification=dict(
            pearson_vs_provided_B15_depth=round(float(np.corrcoef(a, b)[0, 1]), 4),
            spearman_approx=round(float(np.corrcoef(ra, rb)[0, 1]), 4),
            n=int(a.size),
            independent_check="competition band 15 'Depth to basement surface'"),
        n_finite=bool(np.isfinite(hgm[valid]).all()),
        hgm_range=[round(float(hgm[valid].min()), 6), round(float(hgm[valid].max()), 6)],
    )
    print("[1] verify corr(Parker-Oldenburg relief, provided B15 depth) =",
          report["experiment1_inversion"]["verification"]["pearson_vs_provided_B15_depth"])

    cands = {
        "B03_tmi_hgrad": feats[3].astype(np.float64),
        "B05_isograv_slope": feats[5].astype(np.float64),
        "B06_tilt_curvature": feats[6].astype(np.float64),
        "B11_isograv_vgrad_abs": np.abs(feats[11].astype(np.float64)),
        "B15_provided_depth_to_basement": b15.astype(np.float64),
        "B18_isograv_hgrad_abs": np.abs(feats[18].astype(np.float64)),
        "LANE_grav_inversion_hgm": hgm,
    }
    canary = {k: round(auc(v, gt, valid), 4) for k, v in cands.items()}
    canary["_rule"] = "AUC > 0.90 = leakage until proven otherwise"
    canary["_note"] = ("AUC here is against the VISIBLE catalogue, which is the wrong "
                       "target by construction; it is a leakage detector, not a score.")
    report["experiment1_leakage_canary"] = canary
    print("[1] canary:", {k: v for k, v in canary.items() if not k.startswith('_')})

    # ------------------------------------------------------- experiment 2 -------
    folds = make_folds(gt, valid, n_rows=6, n_cols=6, n_folds=4, buffer_px=6,
                       min_segment_px=8)
    ctxs = make_contexts(folds, valid)
    report["experiment2_holdout"] = dict(
        protocol="hide whole segments inside contiguous row-blocks, 6 px buffer, "
                 "catalogue features from visible pixels only, pooled DTI",
        folds=[dict(fold=f["fold"], n_hidden=f["n_hidden"], n_visible=f["n_visible"])
               for f in folds],
        total_hidden=int(sum(f["n_hidden"] for f in folds)))
    print(f"[2] folds hidden px = {[f['n_hidden'] for f in folds]}")

    field = normalise_field(hgm, valid)
    rng = np.random.default_rng(3)
    rand_field = np.where(valid, rng.random(valid.shape), 0.0)

    # cache the per-fold, per-radius catalogue exclusion masks: they depend only on
    # the fold, not on the candidate, and each is a 12.3 M-pixel dilation.
    excl_cache = {}
    for ctx, fold in zip(ctxs, folds):
        for rr in (0, 3, 5, 8):
            excl_cache[(fold["fold"], rr)] = (
                off_catalogue_mask(fold["visible"], rr) if rr else None)

    def run(name, f, excl_r, k, hw):
        per, contribs, n_emit = [], [], 0
        for ctx, fold in zip(ctxs, folds):
            m, _ = greedy_peaks(f, valid, k=k, min_sep=3, half_width=hw,
                                exclude=excl_cache[(fold["fold"], excl_r)])
            n_emit = int(m.sum())
            r = ctx.score(np.where(m, 1.0, 0.0))
            per.append(float(r["dti"]))
            contribs.append(block_contributions(ctx, np.where(m, 1.0, 0.0)))
        return dict(name=name, exclude_radius=excl_r, k=k, ribbon_half_width=hw,
                    dti_mean=round(float(np.mean(per)), 5),
                    dti_per_fold=[round(v, 5) for v in per],
                    n_emitted=n_emit,
                    boot=bootstrap_dti([c["tp"] for c in contribs],
                                       [c["fp"] for c in contribs],
                                       [c["gt"] for c in contribs]))

    rows = []
    grids = {
        "LANE_grav_inversion_hgm": (field, (0, 3, 5), (0, 1, 2)),
        "B18_isograv_hgrad_abs": (normalise_field(np.abs(feats[18].astype(np.float64)), valid), (0, 3), (0, 2)),
        "B15_provided_depth_to_basement": (normalise_field(b15.astype(np.float64), valid), (0, 3), (0, 2)),
        "RANDOM_control": (rand_field, (0,), (0,)),
    }
    for nm, (f, radii, widths) in grids.items():
        for er in radii:
            for k in (10000, 20000, 30000, 45000):
                for hw in widths:
                    rows.append(run(nm, f, er, k, hw))
                    print(f"    .. {nm} excl<={er} k={k} hw={hw} dti={rows[-1]['dti_mean']:.5f}")
    rows.sort(key=lambda r: -r["dti_mean"])
    report["experiment2_sweep"] = rows
    print("\n[2] top 12 operating points (holdout pooled DTI, mean over folds)")
    for r in rows[:12]:
        print(f"   {r['dti_mean']:.5f} [{r['boot']['lo']:.5f},{r['boot']['hi']:.5f}] "
              f"{r['name']:<32} excl<={r['exclude_radius']} k={r['k']:<6} hw={r['ribbon_half_width']} n={r['n_emitted']}")

    best = rows[0]
    ctrl = []
    for seed in range(20):
        rr = np.random.default_rng(seed)
        m, _ = greedy_peaks(np.where(valid, rr.random(valid.shape), 0.0), valid,
                            k=best["k"], min_sep=3)
        ctrl.append(float(np.mean([c.score(np.where(m, 1.0, 0.0))["dti"] for c in ctxs])))
    report["experiment2_random_line_control"] = dict(
        n_draws=20, mean=round(float(np.mean(ctrl)), 5),
        std=round(float(np.std(ctrl)), 6), max=round(float(np.max(ctrl)), 5),
        emission_count=best["k"],
        note="identical pixel budget, uniformly random locations")
    print(f"[2] random-line control at the same budget: "
          f"{np.mean(ctrl):.5f} +/- {np.std(ctrl):.6f}  (max {np.max(ctrl):.5f})")

    # ------------------------------------------------------- experiment 3 -------
    basin = basin_interior_mask(b15, valid, percentile=60.0)
    report["experiment3_basin_interior"] = dict(
        definition="depth-to-basement >= 60th percentile of valid pixels (B15)",
        basin_px=int(basin.sum()),
        per_fold=[],
    )
    for ctx, fold in zip(ctxs, folds):
        excl = off_catalogue_mask(fold["visible"], best["exclude_radius"]) if best["exclude_radius"] else None
        m, _ = greedy_peaks(field, valid, k=best["k"], min_sep=3,
                            half_width=best["ribbon_half_width"], exclude=excl)
        in_basin = m & basin
        hid_basin = fold["hidden"] & basin
        hid_out = fold["hidden"] & ~basin
        geol = int(fold["hidden"].sum())
        report["experiment3_basin_interior"]["per_fold"].append(dict(
            fold=fold["fold"],
            hidden_total=geol,
            hidden_basin_interior=int(hid_basin.sum()),
            hidden_basin_fraction=round(float(hid_basin.sum() / max(1, geol)), 4),
            emitted_in_basin=int(in_basin.sum()),
            dti_basin_only=round(float(ctx.score(np.where(in_basin, 1.0, 0.0))["dti"]), 5),
            dti_outside_basin_only=round(float(ctx.score(np.where(m & ~basin, 1.0, 0.0))["dti"]), 5),
        ))
    rb_ = report["experiment3_basin_interior"]
    rb_["mean_dti_basin_only"] = round(float(np.mean([p["dti_basin_only"] for p in rb_["per_fold"]])), 5)
    rb_["mean_dti_outside_basin_only"] = round(float(np.mean([p["dti_outside_basin_only"] for p in rb_["per_fold"]])), 5)
    rb_["verdict"] = ("basin-interior component carries the signal" if
                      rb_["mean_dti_basin_only"] >= rb_["mean_dti_outside_basin_only"] else
                      "basin-interior component does NOT carry the signal")
    print("[3] basin-interior DTI", rb_["mean_dti_basin_only"],
          "vs outside-basin DTI", rb_["mean_dti_outside_basin_only"])

    report["experiment2_holdout"]["best"] = best
    with open(os.path.join(args.out, "experiment.json"), "w") as fh:
        json.dump(report, fh, indent=1)
    print(f"\n[done] {time.time() - t0:.0f}s -> {args.out}/experiment.json")


if __name__ == "__main__":
    main()
