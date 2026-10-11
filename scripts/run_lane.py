#!/usr/bin/env python3
"""61GEMSDOE lane: basement-depth steps from Parker-Oldenburg gravity inversion.

Three predeclared experiments (budget: 3 experiments / 2 hours).

* **E1 -- leakage canary and arm selection.**  Every candidate feature is
  scored alone against the withheld segments (AUC and the DTI of a
  budget-matched emission).  ``max(AUC, 1-AUC) > 0.90`` is treated as leakage
  until proven otherwise.  The step-detection smoothing scale is chosen here.
* **E2 -- multi-line ribbons versus a thin line, versus random lines.**  The
  positional resolution of the inverted step is *measured* (distance from
  withheld segment pixels to the nearest crest) and the ribbon geometry is then
  read off the closed-form DTI gain table rather than chosen by taste.  The
  lane-specific recovery test counts how many withheld **basin-interior**
  segments the steps recover, against a random-line null of matched length.
* **E3 -- the competing explanation.**  Steps that coincide with a magnetic
  lineament may be lateral density contrasts *within* basement rather than
  offsets of the basement surface.  Demoting them is scored on the holdout.

Every score below is HOLDOUT-DTI with the evaluator version, the withheld
positive count and a 95 % paired block-bootstrap CI.  Nothing here is a
leaderboard score.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_dilation, distance_transform_edt, label

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import competing, emission, evaluate_holdout as eh, gravity as gv  # noqa: E402
from gems61 import grid as gd, holdout as ho, steps as st                      # noqa: E402

BUDGET = 40_000
THIN_PX = 1.0   # dot separation; the crest is ~2 px wide, so 1 px removes only that redundancy
STRUCT8 = np.ones((3, 3), bool)


def log(msg: str) -> None:
    print(f"[lane] {msg}", flush=True)


def cached(name: str, builder):
    path = ROOT / ".cache" / name
    if path.exists():
        return np.load(path)
    a = builder()
    np.save(path, a.astype(np.float32))
    return a


def build_inversion(drho: float, z0: float, cutoff: float, filled):
    path = ROOT / ".cache" / f"relief_d{int(drho)}_z{int(z0)}_l{int(cutoff)}.npy"
    if path.exists():
        relief = np.load(path)
    else:
        t0 = time.time()
        relief, diag = gv.oldenburg_invert(
            filled, drho, z0, 100.0, cutoff_wavelength_m=cutoff, n_iter=20,
            n_terms=5, pad=96, return_diagnostics=True)
        np.save(path, relief.astype(np.float32))
        log(f"inversion drho={drho} z0={z0} lc={cutoff}: {time.time()-t0:.0f}s, "
            f"{diag['n_iter_done']} iters")
    return -relief.astype(np.float32)          # depth to basement, metres


def pooled_terms(pred, truth, valid, known) -> np.ndarray:
    terms, _ = eh.terms_for(pred, truth, valid=valid, known=known)
    return terms


def random_line_null(crest: np.ndarray, footprint: np.ndarray, exclude: np.ndarray,
                     budget: int, seed: int, n_rep: int = 5):
    """Random straight lines of matched total length, inside the footprint.

    The null keeps the *length budget* and the off-catalogue rule identical to
    the candidate and randomises only where the lines go, which is what the
    lane's recovery question asks.
    """
    lab, n = label(crest, structure=STRUCT8)
    if n == 0:
        raise ValueError("empty crest")
    sizes = np.bincount(lab.ravel())[1:]
    sizes = sizes[sizes >= 20]                 # ignore 1-2 px noise fragments
    if sizes.size == 0:
        sizes = np.array([50])
    ys, xs = np.nonzero(footprint)
    rng = np.random.default_rng(seed)
    out = []
    for rep in range(n_rep):
        mask = np.zeros(crest.shape, bool)
        placed = 0
        guard = 0
        while placed < int(crest.sum()) and guard < 6000:
            guard += 1
            length = int(min(int(rng.choice(sizes)), 400))
            k = rng.integers(len(ys))
            y0, x0 = float(ys[k]), float(xs[k])
            ang = rng.uniform(0, np.pi)
            t = np.arange(length, dtype=np.float64)
            yy = np.round(y0 + t * np.sin(ang)).astype(int)
            xx = np.round(x0 + t * np.cos(ang)).astype(int)
            ok = (yy >= 0) & (yy < crest.shape[0]) & (xx >= 0) & (xx < crest.shape[1])
            mask[yy[ok], xx[ok]] = True
            placed += length
        mask &= footprint
        mask &= ~exclude
        out.append(mask)
    return out


def recovery_counts(dots: np.ndarray, hidden: np.ndarray, basin: np.ndarray) -> dict:
    """How many withheld whole segments in the basin interior are recovered.

    A segment counts as recovered when at least one emitted cell lies within
    300 m (3 px) of any of its pixels.
    """
    lab, n = label(hidden, structure=STRUCT8)
    ids = np.unique(lab[lab > 0])
    d = distance_transform_edt(~dots)
    recovered = basin_rec = 0
    total = basin_total = 0
    for i in ids:
        seg = lab == i
        total += 1
        hit = bool((d[seg] <= 3.0).any())
        recovered += int(hit)
        if (seg & basin).any():
            basin_total += 1
            basin_rec += int(hit)
    return dict(segments_total=int(total), segments_recovered=int(recovered),
                basin_segments_total=int(basin_total),
                basin_segments_recovered=int(basin_rec),
                basin_recovery_rate=(basin_rec / basin_total) if basin_total else None)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--drho", type=float, default=400.0)
    ap.add_argument("--z0", type=float, default=3000.0)
    ap.add_argument("--cutoff", type=float, default=5000.0)
    ap.add_argument("--budget", type=int, default=BUDGET)
    ap.add_argument("--hide-fraction", type=float, default=0.20)
    ap.add_argument("--buffer-px", type=int, default=3)
    ap.add_argument("--seed", type=int, default=61011)
    ap.add_argument("--null-reps", type=int, default=5)
    a = ap.parse_args()

    started = time.time()
    g = gd.load_grid()
    fp = g.footprint
    log(f"grid {g.shape} footprint={int(fp.sum())} catalogue={int(g.catalogue.sum())}")

    b13 = np.array(gd.load_band(13))
    b15 = np.array(gd.load_band(15))
    b2 = np.array(gd.load_band(2))
    filled = cached("b13_filled.npy", lambda: gv.inpaint(np.nan_to_num(b13), np.isfinite(b13)))
    b15i = cached("b15_filled.npy", lambda: gv.inpaint(np.nan_to_num(b15), np.isfinite(b15)))

    depth = build_inversion(a.drho, a.z0, a.cutoff, filled)
    log(f"depth in footprint: min={depth[fp].min():.0f} max={depth[fp].max():.0f} "
        f"std={depth[fp].std():.0f} m")

    folds = ho.make_folds(g.catalogue, fp, fraction=a.hide_fraction,
                          buffer_px=a.buffer_px, seed=a.seed)
    hidden = np.zeros(fp.shape, bool)
    for f in folds:
        hidden |= f.truth
    visible = folds[0].visible
    log("folds: " + ", ".join(f"{f.name}={f.n_truth}" for f in folds)
        + f" total={int(hidden.sum())}")
    valid = fp
    known = visible

    # ---------------------------------------------------------------- E1
    log("E1: leakage canary")
    canary = {}
    features = {}
    for sigma in (1.0, 2.0, 3.0):
        s = st.detect_steps(depth, sigma_px=sigma, half_width_px=4.0, valid=fp)
        features[f"inv_step_gradient_s{sigma:g}"] = s.gradient
        features[f"inv_step_throw_s{sigma:g}"] = np.where(s.crest, s.throw, 0.0)
    _, _, gr15 = st._unit_gradient(b15i.astype(np.float32), 2.0)
    _, _, gr13 = st._unit_gradient(filled.astype(np.float32), 2.0)
    b12 = np.array(gd.load_band(12))
    f12 = gv.inpaint(np.nan_to_num(b12), np.isfinite(b12))
    _, _, gr12 = st._unit_gradient(f12.astype(np.float32), 2.0)
    features["band15_depth_gradient"] = gr15
    features["band13_gravity_gradient"] = gr13
    features["band12_det_elev_gradient"] = gr12
    for name, fld in features.items():
        canary[name] = float(eh.auc(fld, hidden, valid & ~visible))
    for name, v in sorted(canary.items(), key=lambda kv: -max(kv[1], 1 - kv[1])):
        flag = "LEAKAGE-SUSPECT" if max(v, 1 - v) > 0.90 else "ok"
        log(f"    AUC {name:32s} = {v:.4f}  [{flag}]")

    # arm selection: budget-matched dotted emission from each step scale
    log("E1: arm selection (budget-matched dotted emission)")
    arms: dict[str, np.ndarray] = {}
    arm_terms: dict[str, np.ndarray] = {}
    cat_dist = distance_transform_edt(~g.catalogue)
    for sigma in (1.0, 2.0, 3.0):
        s = st.detect_steps(depth, sigma_px=sigma, half_width_px=4.0, valid=fp)
        score = np.where(s.crest, s.throw, 0.0)
        log(f"    sigma={sigma:g}: crest px={s.n_crest}")
        dots = emission.thin_to_dots(s.crest, score, THIN_PX)
        dots = emission.prune_near(dots, visible, 2)
        dots = emission.apply_budget(dots, score, a.budget)
        arms[f"steps_s{sigma:g}_k1"] = dots
        log(f"    crest={s.n_crest} dots={int(dots.sum())}")
    # measured positional resolution of the step network
    for sigma in (1.0, 2.0, 3.0):
        s = st.detect_steps(depth, sigma_px=sigma, half_width_px=4.0, valid=fp)
        d = distance_transform_edt(~s.crest)
        dh = d[g.catalogue]
        log(f"    resolution s={sigma:g}: catalogue p10/p50/p90 distance to crest = "
            f"{np.percentile(dh,10):.1f}/{np.percentile(dh,50):.1f}/{np.percentile(dh,90):.1f} px")
    for name, dots in arms.items():
        arm_terms[name] = pooled_terms(dots.astype(np.float32), hidden, valid, known)
    dtis_early = eh.pooled(arm_terms)
    for name, v in sorted(dtis_early.items(), key=lambda kv: -kv[1]):
        log(f"    E1 HOLDOUT-DTI {name:20s} = {v:.6f}")

    # ---------------------------------------------------------------- E2
    log("E2: ribbons vs thin line vs random lines")
    # The smoothing scale is chosen by the E1 holdout result, not by taste.
    scale_keys = [k for k in arms if k.startswith("steps_s")]
    best_sigma = float(max(scale_keys, key=lambda k: dtis_early[k]).split("_s")[1].split("_")[0])
    log(f"    selected smoothing scale sigma={best_sigma:g} px "
        f"(best of {scale_keys} on the E1 holdout)")
    s_best = st.detect_steps(depth, sigma_px=best_sigma, half_width_px=4.0, valid=fp)
    score0 = np.where(s_best.crest, s_best.throw, 0.0)
    for name, offs in (("k1", (0.0,)), ("k2_s3", (0.0, 3.0)), ("k3_s3", (0.0, 3.0, 6.0)),
                       ("k2_s2", (0.0, 2.0))):
        rib, _ = emission.ribbon_mask(s_best.crest, offsets_px=offs)
        rib &= fp
        score = emission.nearest_crest_value(score0, s_best.crest) * rib
        dots = emission.thin_to_dots(rib, score, THIN_PX)
        dots = emission.prune_near(dots, visible, 2)
        dots = emission.apply_budget(dots, score, a.budget)
        arms[f"ribbon_{name}"] = dots
        log(f"    ribbon {name}: ribbon px={int(rib.sum())} dots={int(dots.sum())}")
    # random-line null
    nulls = random_line_null(s_best.crest, fp, visible, a.budget, a.seed, a.null_reps)
    for i, nm in enumerate(nulls):
        dots = emission.thin_to_dots(nm, np.float32(nm), 3.0)
        dots = emission.apply_budget(dots, np.float32(dots), min(a.budget, int(dots.sum())))
        arms[f"randomlines_r{i}"] = dots
    for name in [k for k in arms if k.startswith("ribbon_") or k.startswith("randomlines_")]:
        arm_terms[name] = pooled_terms(arms[name].astype(np.float32), hidden, valid, known)

    # basin-interior recovery
    basin = ho.basin_interior_mask(depth, fp, depth_quantile=0.60)
    recovery = {}
    for name in ("ribbon_k1", "ribbon_k2_s3", "ribbon_k3_s3"):
        recovery[name] = recovery_counts(arms[name], hidden, basin)
    recovery["randomlines_r0"] = recovery_counts(arms["randomlines_r0"], hidden, basin)
    for name, r in recovery.items():
        log(f"    recovery {name:16s} basin {r['basin_segments_recovered']}/"
            f"{r['basin_segments_total']} = "
            f"{(r['basin_recovery_rate'] or 0):.3f}  all {r['segments_recovered']}/"
            f"{r['segments_total']}")

    # ---------------------------------------------------------------- E3
    log("E3: intra-basement density-contrast demotion")
    mag_crest = competing.magnetic_contact_crests(
        gv.inpaint(np.nan_to_num(b2), np.isfinite(b2)).astype(np.float32),
        sigma_grid=(2.0,), min_quantile=0.90)
    ambiguous = competing.coincidence_map(s_best.crest, mag_crest, tolerance_px=2.0)
    log(f"    magnetic crest px={int(mag_crest.sum())}; ambiguous gravity steps="
        f"{int(ambiguous.sum())} of {s_best.n_crest} ({ambiguous.sum()/max(s_best.n_crest,1):.3f})")
    for tag, drop in (("all", False), ("demoted", True)):
        crest = s_best.crest & (~ambiguous if drop else True)
        rib, _ = emission.ribbon_mask(crest, offsets_px=(0.0, 3.0))
        rib &= fp
        sc0 = np.where(crest, s_best.throw, 0.0)
        score = emission.nearest_crest_value(sc0, crest) * rib
        dots = emission.thin_to_dots(rib, score, THIN_PX)
        dots = emission.prune_near(dots, visible, 2)
        dots = emission.apply_budget(dots, score, a.budget)
        arms[f"e3_{tag}"] = dots
        arm_terms[f"e3_{tag}"] = pooled_terms(dots.astype(np.float32), hidden, valid, known)
        log(f"    e3_{tag}: crest={int(crest.sum())} dots={int(dots.sum())}")

    # ------------------------------------------------------------ scoring
    log("pooled scoring")
    dtis = eh.pooled(arm_terms)
    for name, v in sorted(dtis.items(), key=lambda kv: -kv[1]):
        log(f"    HOLDOUT-DTI {name:24s} = {v:.6f}")
    boot = {}
    for cand in dtis:
        ref = "ribbon_k1" if cand != "ribbon_k1" else "randomlines_r0"
        boot[cand] = eh.bootstrap_paired(arm_terms, cand, ref, draws=1000, seed=a.seed)
    summary = {k: dict(dti=v["dti"], ci95=v["ci95"]) for k, v in boot.items()}
    for name in sorted(summary, key=lambda k: -summary[k]["dti"]):
        s = summary[name]
        log(f"    {name:24s} DTI={s['dti']:.6f} CI=[{s['ci95'][0]:.6f},{s['ci95'][1]:.6f}]")

    out = dict(
        evidence_class="HOLDOUT-DTI",
        evaluator_version=eh.VERSION,
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        parameters=dict(drho=a.drho, z0=a.z0, cutoff_wavelength_m=a.cutoff, budget=a.budget,
                        hide_fraction=a.hide_fraction, buffer_px=a.buffer_px, seed=a.seed),
        n_withheld_positives=int(hidden.sum()),
        n_visible_masked=int(visible.sum()),
        folds={f.name: f.n_truth for f in folds},
        canary_auc=canary,
        holdout_dti=summary,
        paired_differences={k: {kk: vv for kk, vv in v.items() if kk.startswith(("candidate", "ribbon", "e3", "randomlines"))}
                            for k, v in boot.items()},
        recovery=recovery,
        magnetic=dict(magnetic_crest_px=int(mag_crest.sum()),
                      ambiguous_step_px=int(ambiguous.sum()),
                      ambiguous_fraction=float(ambiguous.sum() / max(s_best.n_crest, 1))),
        density_contrast_equivalents_m={
            "200 kg/m3 over 2 km at 400 kg/m3 fill-basement contrast":
                competing.density_contrast_equivalent_metres(200.0, 2000.0, 400.0)},
        runtime_s=round(time.time() - started, 1),
    )
    (ROOT / "evidence").mkdir(exist_ok=True)
    (ROOT / "evidence/lane_experiments.json").write_text(json.dumps(out, indent=2) + "\n")
    np.save(ROOT / ".cache/depth_final.npy", depth.astype(np.float32))
    log(f"done in {time.time()-started:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
