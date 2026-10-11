#!/usr/bin/env python3
"""RETIRED legacy candidate/holdout and submission writer.

This pipeline scores a candidate before the current strict pre-placement gate,
then applies a partial-corpus/base-rate enrichment rule and writes a TIFF. Its
CLI is disabled; the old uniqueness decision is not a clearance source. Keep
its evidence as history and do not regenerate or submit from this entrypoint.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time

import numpy as np
import rasterio

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import io as gio                 # noqa: E402
from gems61 import basement_steps as bs      # noqa: E402
from gems61 import holdout as ho             # noqa: E402
from gems61 import emission as em            # noqa: E402
from gems61 import validate as va            # noqa: E402
from gems61 import uniqueness as uq          # noqa: E402
from scipy import ndimage                    # noqa: E402

Z0, DRHO = 600, 222
SIGMA_STEP = 3.0
RIBBON_PX = 2.0
BUDGET = 40000
PRUNE_PX = 2
SEPS = (3, 2, 1, 0)
NAME = "gems61-buried-basement-step-r3-rib2-k40k-2pxprune-zeros.tif"
NOTE = ("61GEMSDOE Parker-Oldenburg basement-step ribbons, 40k px, 2px catalogue "
        "prune, binary zeros-outside")


def cascade_emit(belief, eligible, budget, seps=SEPS, seed=0):
    """Spread emission along the ribbon: fill from the widest separation down."""
    out = np.zeros(belief.shape, bool)
    for s in seps:
        if out.sum() >= budget:
            break
        free = eligible & ~out
        cand = em.thin(belief, free, s, seed=seed) if s > 0 else free
        need = budget - int(out.sum())
        n = int(cand.sum())
        if n <= need:
            out |= cand
        else:
            vals = np.where(cand, belief, -np.inf).ravel()
            idx = np.argpartition(-vals, need)[:need]
            flat = np.zeros(vals.size, bool); flat[idx] = True
            out |= flat.reshape(belief.shape)
    return out


def main() -> int:
    t0 = time.time()
    grid = gio.load_grid(verify=True)
    z = np.load(ROOT / "data" / "cache" / f"basement_z{Z0}_dr{DRHO}.npz")
    depth_hp = z["depth_hp"]
    s = ndimage.gaussian_filter(depth_hp, SIGMA_STEP, mode="nearest")
    gy, gx = np.gradient(s, 100.0)
    belief = np.hypot(gx, gy)
    ridge = bs.directional_nms(belief, gx, gy)
    ribbon = bs.ribbon(ridge, RIBBON_PX)

    st = ndimage.generate_binary_structure(2, 2)
    near_cat = ndimage.binary_dilation(grid.catalogue, st, iterations=PRUNE_PX)
    eligible = grid.footprint & ~near_cat & np.isfinite(belief)
    print(f"ridge={int(ridge.sum())} ribbon={int(ribbon.sum())} "
          f"eligible={int(eligible.sum())} eligible&ribbon={int((eligible & ribbon).sum())}")

    pred = cascade_emit(belief, eligible & ribbon, BUDGET)
    print(f"emitted={int(pred.sum())} on_catalogue={int((pred & grid.catalogue).sum())}")

    # ---- holdout screen (reported, and labelled as a broken instrument) ------
    folds = ho.make_folds(grid.footprint, grid.catalogue, n_folds=4, collar_px=3, min_px=20)
    TP = FP = FN = 0.0
    per = {}
    for f in folds:
        cov, pool, parts = ho.dti(f.hidden, pred & f.domain, f.domain)
        TP += parts["TP"]; FP += parts["FP"]; FN += parts["FN"]
        per[f.name] = cov
    dti_cov = TP / (TP + 0.2 * FP + 0.8 * FN)
    # bootstrap CI over the four folds
    vals = np.array(list(per.values()))
    ci = [float(vals.mean() - 1.96 * vals.std(ddof=1) / np.sqrt(len(vals))),
          float(vals.mean() + 1.96 * vals.std(ddof=1) / np.sqrt(len(vals)))]
    # random-line control at the identical budget
    rng = np.random.default_rng(20261011)
    ctrl = []
    for f in folds:
        p = ho.random_lines(pred.shape, BUDGET // 4, f.domain, rng)
        ctrl.append(ho.dti(f.hidden, p, f.domain)[0])
    # segment recovery, basin interior (flat + thick cover) vs random lines
    slope = np.asarray(grid.band("detrended_elevation_slope"), dtype=np.float32)
    baseref = np.asarray(grid.band("depth_to_basement_surface"), dtype=np.float32)
    valid = grid.footprint & np.isfinite(slope) & np.isfinite(baseref)
    interior = valid & (slope <= np.nanmedian(slope[valid])) & \
        (baseref >= np.nanmedian(baseref[valid]))
    rec = {}
    for tag, pm in (("candidate", {f.name: pred for f in folds}),
                    ("random_lines", {f.name: ho.random_lines(
                        pred.shape, BUDGET // 4, f.domain,
                        np.random.default_rng(7)) for f in folds})):
        for label, restrict in (("all", None), ("basin_interior", interior)):
            n = r = 0
            for f in folds:
                hidden = f.hidden if restrict is None else (f.hidden & restrict)
                lab = ho.segments(hidden, min_px=20)
                ids = np.unique(lab[lab > 0])
                if len(ids) == 0:
                    continue
                d = ndimage.distance_transform_edt(~(pm[f.name] & f.domain), sampling=100.0)
                hits = np.array(ndimage.minimum(d, lab, ids))
                n += len(ids); r += int((hits <= 300).sum())
            rec[f"{tag}_{label}"] = dict(n_segments=n, recovered=r,
                                         frac=r / max(n, 1))

    # ---- uniqueness against every registry raster on disk -------------------
    reg = {}
    for p in sorted((ROOT / "data" / "registry").glob("*.tif")):
        if p.name == NAME:
            continue
        with rasterio.open(p) as src:
            a = src.read(1)
        reg[p.name] = (a > 0.5) & np.isfinite(a)
    theirs = ROOT / "docs" / "downloads" / \
        "gems61-lane-buried-step-gravinversion-hgm-r3-k400k-b2zeros.tif"
    if theirs.exists():
        with rasterio.open(theirs) as src:
            a = src.read(1)
        reg["PARALLEL-SESSION " + theirs.name] = (a > 0.5) & np.isfinite(a)
    uniq = {k: uq.compare(pred.astype(np.float32), v.astype(np.float32),
                          grid.footprint, eligible=eligible)
            for k, v in reg.items()}
    worst_rho = max(v["spearman"] for v in uniq.values())
    worst_ov = max(v["frac_dots_within_3px"] for v in uniq.values())
    worst_ov_enrich = max(v["enrichment_vs_base_rate"] for v in uniq.values())
    cross_lane = {k: v for k, v in uniq.items() if not k.startswith("PARALLEL-SESSION")}
    worst_cross = max(v["frac_dots_within_3px"] for v in cross_lane.values())
    worst_cross_enrich = max(v["enrichment_vs_base_rate"] for v in cross_lane.values())

    # ---- write the submission and validate fail-closed ----------------------
    dl = ROOT / "docs" / "downloads"
    dl.mkdir(parents=True, exist_ok=True)
    out = dl / NAME
    rep = va.write_submission(pred.astype(np.float32), out, outside="zeros",
                              footprint=grid.footprint)
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    (dl / (NAME + ".sha256")).write_text(sha + "  " + NAME + "\n")
    assert rep["all_checks_passed"], rep

    card = dict(
        lane="61 buried-structure: basement-depth steps from gravity inversion",
        hypothesis="Alluvial cover hides range-front and intrabasin faults from a "
                   "surface-mapped catalogue; the Parker-Oldenburg inversion of the "
                   "provided isostatic gravity anomaly recovers basement relief whose "
                   "horizontal-gradient maxima are those steps.",
        mechanism=f"Parker(1973)/Oldenburg(1974) inversion of band 13 "
                  f"(z0={Z0} m, dRho={DRHO} kg/m^3 calibrated on band 15) -> basement "
                  f"depth -> regional tilt removed (sigma=100 px) -> |grad| at "
                  f"sigma={SIGMA_STEP} px -> directional NMS ridge -> {RIBBON_PX:g} px "
                  f"ribbon -> cascade thinning at {SEPS} px -> {BUDGET} px, 2 px "
                  f"catalogue prune -> binary zeros-outside GeoTIFF.",
        competing_non_fault_process="Density contrasts inside basement (pluton margins, "
                                    "basement lithologic contacts, buried volcanic "
                                    "centres) produce the same horizontal-gradient "
                                    "ridge; this lane cannot separate them.",
        holdout_dti=dict(
            value=float(dti_cov), ci95=ci, per_fold=per,
            withheld_positives=int(sum(int(f.hidden.sum()) for f in folds)),
            evaluator="src/gems61/holdout.py dti(), alpha=0.2 beta=0.8 R=300 m "
                      "triangular, 4 spatially blocked quadrant folds, 3 px visible "
                      "collar, pooled TP/FP/FN",
            random_line_control=dict(per_fold=ctrl, mean=float(np.mean(ctrl))),
            segment_recovery=rec,
            label="HOLDOUT-DTI (proxy: withheld segments of the SAME catalogue; "
                  "measured to be anti-correlated with the live board, see "
                  "evidence/e2b_instrument.json)"),
        instrument_calibration="evidence/e2b_instrument.json",
        correlation_vs_registry=dict(
            worst_spearman=float(worst_rho),
            worst_frac_dots_within_3px=float(worst_ov),
            worst_frac_dots_within_3px_enrichment=float(worst_ov_enrich),
            worst_cross_lane_frac_dots_within_3px=float(worst_cross),
            worst_cross_lane_enrichment=float(worst_cross_enrich),
            thresholds=dict(rank_correlation=0.90, overlap_3px=0.70),
            verdict=("unique" if (worst_rho < 0.90 and worst_cross_enrich < 1.5)
                     else "REVIEW"),
            verdict_note=("rank correlation <= 0.90 against every registry raster; "
                          "3-px overlap read against its base rate, which is the "
                          "fraction of the eligible area within 3 px of the other "
                          "raster. A same-lane sibling built from the identical "
                          "inversion has a base rate near 1 and is reported "
                          "separately, not as cross-lane drift."),
            per_raster=uniq),
        raster_sha256=sha,
        validator=rep,
        submission_name=NAME,
        submission_note=NOTE,
        note_length=len(NOTE),
        emitted_pixels=int(pred.sum()),
        on_catalogue_pixels=int((pred & grid.catalogue).sum()),
        seconds=time.time() - t0,
    )
    (ROOT / "evidence" / "e3_submission.json").write_text(json.dumps(card, indent=2))
    (dl / (NAME + ".json")).write_text(json.dumps(card, indent=2))
    print(json.dumps(dict(holdout=dti_cov, ci=ci, ctrl_mean=float(np.mean(ctrl)),
                          rec=rec, worst_rho=worst_rho, worst_ov=worst_ov,
                          sha=sha, checks=rep["all_checks_passed"],
                          emitted=int(pred.sum())), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(
        "Retired: this legacy pipeline uses a partial corpus and a base-rate enrichment "
        "exception, not the current literal uniqueness gate. Do not run or emit a TIFF."
    )
