#!/usr/bin/env python3
"""Experiment 2 - basement-step ridges on the hide-and-recover holdout.

Scores the lane's candidate against pre-registered controls, runs the leakage
canary on every provided band, and measures segment-level recovery of withheld
basin-interior faults.  Every number printed here is HOLDOUT-DTI, never a score.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import io as gio                     # noqa: E402
from gems61 import basement_steps as bs          # noqa: E402
from gems61 import holdout as ho                 # noqa: E402
from gems61 import emission as em                # noqa: E402
from scipy import ndimage                        # noqa: E402

Z0, DRHO = 600, 222
BUDGETS = [37654, 44090]
MIN_SEP = 3          # px -> 300 m, the kernel radius
COLLAR_PX = 3        # visible faults masked with a 300 m collar


def pooled_score(pred_fn, folds):
    """pred_fn(fold) -> bool mask; pool TP/FP/FN over folds."""
    TP = FP = FN = nT = nP = 0
    per = {}
    for f in folds:
        p = pred_fn(f) & f.domain
        d, _, parts = ho.dti(f.hidden, p, f.domain)
        TP += parts["TP"]; FP += parts["FP"]; FN += parts["FN"]
        nT += parts["n_truth"]; nP += parts["n_pred"]
        per[f.name] = d
    dti = TP / (TP + 0.2 * FP + 0.8 * FN) if (TP + FP + FN) else 0.0
    return dict(dti_pooled=float(dti), per_fold=per, TP=TP, FP=FP, FN=FN,
                n_truth=nT, n_pred=nP)


def main() -> int:
    t0 = time.time()
    grid = gio.load_grid(verify=False)
    z = np.load(ROOT / "data" / "cache" / f"basement_z{Z0}_dr{DRHO}.npz")
    depth, depth_hp, hgm = z["depth"], z["depth_hp"], z["hgm"]
    g = np.asarray(grid.band("isostatic_gravity_anomaly"), dtype=np.float32)
    slope = np.asarray(grid.band("detrended_elevation_slope"), dtype=np.float32)
    baseref = np.asarray(grid.band("depth_to_basement_surface"), dtype=np.float32)
    valid = grid.footprint & np.isfinite(g)

    folds = ho.make_folds(grid.footprint, grid.catalogue, n_folds=4,
                          collar_px=COLLAR_PX, min_px=20)
    print("folds:", [(f.name, f.n_segments, int(f.hidden.sum()), int(f.domain.sum()))
                     for f in folds])

    # ---- covers / gates -----------------------------------------------------
    med_slope = float(np.nanmedian(slope[valid]))
    med_base = float(np.nanmedian(baseref[valid]))
    cover_flat = valid & (slope <= med_slope)            # alluvial basin floor
    cover_thick = valid & (baseref >= med_base)          # thick sedimentary fill
    gates = dict(none=valid, flat=cover_flat, thick=cover_thick,
                 flat_and_thick=cover_flat & cover_thick)
    print("gate sizes:", {k: int((v & grid.footprint).sum()) for k, v in gates.items()},
          f"median slope={med_slope:.3f} median base={med_base:.1f}")

    # ---- ridge surfaces at two smoothing scales -----------------------------
    surfaces = {}
    for sg in (3.0, 5.0):
        s = ndimage.gaussian_filter(depth_hp, sg, mode="nearest")
        gy, gx = np.gradient(s, 100.0)
        mag = np.hypot(gx, gy)
        ridge = bs.directional_nms(mag, gx, gy)
        surfaces[f"sg{sg:g}"] = dict(mag=mag, ridge=ridge,
                                     rib2=bs.ribbon(ridge, 2.0),
                                     rib3=bs.ribbon(ridge, 3.0))
        print(f"sigma={sg}: ridge={int(ridge.sum())} rib2={int(surfaces[f'sg{sg:g}']['rib2'].sum())}"
              f" rib3={int(surfaces[f'sg{sg:g}']['rib3'].sum())}")

    results = {}

    # ---- leakage canary: each provided band alone ---------------------------
    canary = {}
    pooled_truth = np.zeros_like(grid.footprint)
    pooled_dom = np.zeros_like(grid.footprint)
    for f in folds:
        pooled_truth |= f.hidden & f.domain
        pooled_dom |= f.domain
    bg = pooled_dom & ~pooled_truth
    print(f"pooled truth={int(pooled_truth.sum())} domain={int(pooled_dom.sum())}")
    for name in grid.names:
        b = np.asarray(grid.band(name), dtype=np.float64)
        canary[name] = ho.auc(np.where(pooled_dom, b, np.nan), pooled_truth,
                              n_bg=300000, seed=1)
    canary["basement_step_hgm_sg3"] = ho.auc(
        np.where(pooled_dom, surfaces["sg3"]["mag"], np.nan), pooled_truth, 300000, 1)
    canary["basement_step_hgm_sg5"] = ho.auc(
        np.where(pooled_dom, surfaces["sg5"]["mag"], np.nan), pooled_truth, 300000, 1)
    canary["basement_depth_inv"] = ho.auc(
        np.where(pooled_dom, depth, np.nan), pooled_truth, 300000, 1)
    results["leakage_canary_auc"] = canary
    print("canary top:", sorted(canary.items(), key=lambda kv: -abs(kv[1] - 0.5))[:6])

    # ---- candidate emissions ------------------------------------------------
    rng = np.random.default_rng(0)
    for skey, sur in surfaces.items():
        for rib_name in ("rib2", "rib3"):
            for gname, gate in gates.items():
                for budget in BUDGETS:
                    tag = f"{skey}-{rib_name}-{gname}-n{budget}"
                    def fn(f, sur=sur, rib_name=rib_name, gate=gate, budget=budget):
                        # visible faults are already masked by the fold collar;
                        # hidden (withheld) segments are the truth and stay eligible
                        elig = f.domain & gate
                        return em.emit(sur["mag"], elig & sur[rib_name], budget,
                                       MIN_SEP, seed=0)
                    results[tag] = pooled_score(fn, folds)
                    r = results[tag]
                    print(f"{tag:34s} DTI={r['dti_pooled']:.5f} pred={r['n_pred']:6d} "
                          f"truth={r['n_truth']:6d} folds=" +
                          " ".join(f"{k}:{v:.4f}" for k, v in r["per_fold"].items()),
                          flush=True)

    # ---- no-inversion control: gradient of the provided isostatic gravity ----
    for sg in (3.0,):
        s = ndimage.gaussian_filter(np.nan_to_num(g, nan=float(np.nanmedian(g))), sg,
                                    mode="nearest")
        gy, gx = np.gradient(s, 100.0)
        mag = np.hypot(gx, gy)
        ridge = bs.directional_nms(mag, gx, gy)
        rib = bs.ribbon(ridge, 3.0)
        def fn(f, mag=mag, rib=rib):
            return em.emit(mag, f.domain & gates["flat"] & rib, BUDGETS[0], MIN_SEP, 0)
        results["ctrl_no_inversion_grav_hgm_sg3"] = pooled_score(fn, folds)
        print("ctrl_no_inversion_grav_hgm_sg3", results["ctrl_no_inversion_grav_hgm_sg3"]["dti_pooled"])

    # ---- controls: random lines / random dots at the same budget ------------
    for budget in BUDGETS:
        def fn_lines(f, budget=budget):
            r = np.random.default_rng(12345)
            return ho.random_lines(f.hidden.shape, budget, f.domain & gates["flat"], r)
        results[f"ctrl_random_lines-n{budget}"] = pooled_score(fn_lines, folds)
        def fn_dots(f, budget=budget):
            r = np.random.default_rng(999)
            elig = np.flatnonzero((f.domain & gates["flat"]).ravel())
            sel = r.choice(elig, size=min(budget, len(elig)), replace=False)
            out = np.zeros(f.hidden.size, bool); out[sel] = True
            return out.reshape(f.hidden.shape)
        results[f"ctrl_random_dots-n{budget}"] = pooled_score(fn_dots, folds)
        print(f"ctrl_random_lines-n{budget}", results[f"ctrl_random_lines-n{budget}"]["dti_pooled"],
              f"ctrl_random_dots-n{budget}", results[f"ctrl_random_dots-n{budget}"]["dti_pooled"],
              flush=True)

    # ---- segment recovery: basin-interior withheld segments -----------------
    recovery = {}
    best_tag = max((k for k in results if not k.startswith("ctrl")),
                   key=lambda k: results[k]["dti_pooled"])
    skey, rib_name, gname, nb = best_tag.split("-")
    sur = surfaces[skey]; gate = gates[gname]; budget = int(nb[1:])
    def best_pred(f):
        elig = f.domain & gate
        return em.emit(sur["mag"], elig & sur[rib_name], budget, MIN_SEP, 0)
    preds = {f.name: best_pred(f) for f in folds}
    # per-fold recovery, candidate vs random lines at the same budget
    def rec_for(pred_map, restrict):
        out = {}
        for f in folds:
            hidden = f.hidden if restrict is None else (f.hidden & restrict)
            lab = ho.segments(hidden, min_px=20)
            ids = np.unique(lab[lab > 0])
            if len(ids) == 0:
                continue
            d = ndimage.distance_transform_edt(~(pred_map[f.name] & f.domain), sampling=100.0)
            hits = np.array(ndimage.minimum(d, lab, ids))
            out[f.name] = dict(n=len(ids), recovered=int((hits <= 300).sum()),
                               frac=float((hits <= 300).mean()))
        return out
    rand_map = {f.name: ho.random_lines(f.hidden.shape, budget, f.domain & gates["flat"],
                                        np.random.default_rng(12345)) for f in folds}
    recovery["candidate_all"] = rec_for(preds, None)
    recovery["random_lines_all"] = rec_for(rand_map, None)
    recovery["candidate_basin_interior"] = rec_for(preds, cover_flat & cover_thick)
    recovery["random_lines_basin_interior"] = rec_for(rand_map, cover_flat & cover_thick)
    results["segment_recovery"] = recovery
    results["best_candidate_tag"] = best_tag
    results["gates"] = {k: int((v & grid.footprint).sum()) for k, v in gates.items()}
    results["seconds"] = time.time() - t0
    (ROOT / "evidence" / "e2_holdout.json").write_text(json.dumps(results, indent=2))

    print("\n--- best candidate:", best_tag, results[best_tag]["dti_pooled"])
    for k in ("candidate_all", "random_lines_all", "candidate_basin_interior",
              "random_lines_basin_interior"):
        d = recovery[k]
        n = sum(v["n"] for v in d.values()); r = sum(v["recovered"] for v in d.values())
        print(f"{k:32s} segments={n:5d} recovered={r:5d} frac={r/max(n,1):.4f}")
    print(f"total {results['seconds']:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
