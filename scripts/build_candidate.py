#!/usr/bin/env python3
"""RETIRED legacy candidate/holdout pipeline.

The CLI is fail-closed because this older runner can score candidate arms before
applying the current complete-inventory pre-placement gate, and the aggregate
candidate-experiment budget is already exhausted. Its implementation remains in
source for historical reproducibility, but direct execution is not authorized.
Use the current run card and strict-gated H61-G/H61-L entrypoints only after a
new eligible candidate and selector authorization exist.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt, label

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import competing, emission, evaluate_holdout as eh, gravity as gv  # noqa: E402
from gems61 import grid as gd, holdout as ho, steps as st                      # noqa: E402

BUDGET = 40_000
THIN_PX = 1.0
STRUCT8 = np.ones((3, 3), bool)


def log(msg: str) -> None:
    print(f"[cand] {msg}", flush=True)


def cached(name: str, builder):
    path = ROOT / ".cache" / name
    if path.exists():
        return np.load(path)
    a = builder()
    np.save(path, a.astype(np.float32))
    return a


def random_line_null(crest, footprint, exclude, target_dots, seed, n_rep=1,
                     restrict=None):
    """Random straight lines whose *emitted dot count* matches the candidate.

    The null keeps the spatial domain, the off-catalogue rule and -- crucially --
    the number of emitted dots identical to the candidate, and randomises only
    where the lines go.  Without the dot-count match a comparison of two DTI
    values would be a comparison of two budgets, not of two geometries.

    Two passes: the first measures how many dots a unit of placed line length
    yields (random lines overlap and cross, so this is well under 1), the second
    places enough length to reach ``target_dots``.
    """
    lab, n = label(crest, structure=STRUCT8)
    if n == 0:
        raise ValueError("empty crest")
    sizes = np.bincount(lab.ravel())[1:]
    sizes = sizes[sizes >= 20]
    if sizes.size == 0:
        sizes = np.array([50])
    domain = np.asarray(footprint, bool)
    if restrict is not None:
        domain = domain & np.asarray(restrict, bool)
    ys, xs = np.nonzero(domain)
    rng = np.random.default_rng(seed)
    shape = np.asarray(crest).shape

    def place(mask, length_needed):
        placed = 0
        guard = 0
        while placed < length_needed and guard < 40000:
            guard += 1
            length = int(min(int(rng.choice(sizes)), 400))
            k = rng.integers(len(ys))
            y0, x0 = float(ys[k]), float(xs[k])
            ang = rng.uniform(0, np.pi)
            t = np.arange(length, dtype=np.float64)
            yy = np.round(y0 + t * np.sin(ang)).astype(int)
            xx = np.round(x0 + t * np.cos(ang)).astype(int)
            ok = (yy >= 0) & (yy < shape[0]) & (xx >= 0) & (xx < shape[1])
            mask[yy[ok], xx[ok]] = True
            placed += length
        return placed

    out = []
    for rep in range(n_rep):
        mask = np.zeros(shape, bool)
        placed = place(mask, int(np.asarray(crest).sum()))
        mask &= footprint
        mask &= ~np.asarray(exclude, bool)
        if restrict is not None:
            mask &= np.asarray(restrict, bool)
        sc = np.float32(mask)
        got = int(emission.thin_to_dots(mask, sc, THIN_PX).sum())
        ratio = got / max(placed, 1)
        if got < target_dots:
            need = int(target_dots / max(ratio, 1e-6) * 1.15) - placed
            if need > 0:
                placed += place(mask, need)
                mask &= footprint
                mask &= ~np.asarray(exclude, bool)
                if restrict is not None:
                    mask &= np.asarray(restrict, bool)
        out.append(mask)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--drho", type=float, default=400.0)
    ap.add_argument("--z0", type=float, default=3000.0)
    ap.add_argument("--cutoff", type=float, default=5000.0)
    ap.add_argument("--budget", type=int, default=BUDGET)
    ap.add_argument("--hide-fraction", type=float, default=0.20)
    ap.add_argument("--buffer-px", type=int, default=3)
    ap.add_argument("--seed", type=int, default=61011)
    ap.add_argument("--null-reps", type=int, default=2)
    a = ap.parse_args()

    started = time.time()
    g = gd.load_grid()
    fp = g.footprint
    log(f"grid {g.shape} footprint={int(fp.sum())} catalogue={int(g.catalogue.sum())}")

    b13 = np.array(gd.load_band(13))
    b2 = np.array(gd.load_band(2))
    filled = cached("b13_filled.npy", lambda: gv.inpaint(np.nan_to_num(b13), np.isfinite(b13)))
    b2f = cached("b2_filled.npy", lambda: gv.inpaint(np.nan_to_num(b2), np.isfinite(b2)))

    path = ROOT / ".cache" / f"relief_d{int(a.drho)}_z{int(a.z0)}_l{int(a.cutoff)}.npy"
    if path.exists():
        relief = np.load(path)
    else:
        relief, diag = gv.oldenburg_invert(
            filled, a.drho, a.z0, 100.0, cutoff_wavelength_m=a.cutoff, n_iter=20,
            n_terms=5, pad=96, return_diagnostics=True)
        np.save(path, relief.astype(np.float32))
        log(f"inversion {diag['n_iter_done']} iters")
    depth = -relief.astype(np.float32)

    folds = ho.make_folds(g.catalogue, fp, fraction=a.hide_fraction,
                          buffer_px=a.buffer_px, seed=a.seed)
    hidden = np.zeros(fp.shape, bool)
    for f in folds:
        hidden |= f.truth
    visible = folds[0].visible
    valid, known = fp, visible
    log("folds: " + ", ".join(f"{f.name}={f.n_truth}" for f in folds)
        + f" total={int(hidden.sum())}")

    # --------------------------------------------------------- E1 canary
    # Every feature is scored ALONE against the withheld segments before any
    # result is trusted.  max(AUC, 1-AUC) > 0.90 is treated as leakage until
    # proven otherwise.
    log("E1 leakage canary (each feature alone)")
    canary: dict[str, float] = {}
    feats: dict[str, np.ndarray] = {}
    for sigma in (1.0, 2.0, 3.0):
        si = st.detect_steps(depth, sigma_px=sigma, half_width_px=4.0, valid=fp)
        feats[f"inv_step_gradient_s{sigma:g}"] = si.gradient
        feats[f"inv_step_throw_s{sigma:g}"] = np.where(si.crest, si.throw, 0.0)
    b15 = np.array(gd.load_band(15))
    b12 = np.array(gd.load_band(12))
    b15i = cached("b15_filled.npy", lambda: gv.inpaint(np.nan_to_num(b15), np.isfinite(b15)))
    b12i = cached("b12_filled.npy", lambda: gv.inpaint(np.nan_to_num(b12), np.isfinite(b12)))
    _, _, g15 = st._unit_gradient(b15i.astype(np.float32), 2.0)
    _, _, g13 = st._unit_gradient(filled.astype(np.float32), 2.0)
    _, _, g12 = st._unit_gradient(b12i.astype(np.float32), 2.0)
    feats["band15_depth_gradient"] = g15
    feats["band13_gravity_gradient"] = g13
    feats["band12_det_elev_gradient"] = g12
    for name, fld in feats.items():
        canary[name] = float(eh.auc(fld, hidden, valid & ~known))
    for name, v in sorted(canary.items(), key=lambda kv: -max(kv[1], 1 - kv[1])):
        flag = "LEAKAGE-SUSPECT" if max(v, 1 - v) > 0.90 else "ok"
        log(f"    AUC {name:30s} = {v:.4f}  [{flag}]")

    # ------------------------------------------------------------ geometry
    # sigma comes from E1 (holdout-selected), not from taste.
    s = st.detect_steps(depth, sigma_px=1.0, half_width_px=4.0, valid=fp)
    score0 = np.where(s.crest, s.throw, 0.0)
    log(f"sigma=1 crest px={s.n_crest} throw p50={np.median(s.throw[s.crest]):.0f} m")

    basin = ho.basin_interior_mask(depth, fp, depth_quantile=0.60)
    log(f"basin-interior domain = {int(basin.sum())} px "
        f"({basin.sum()/fp.sum():.3f} of footprint)")

    # E3: the competing intra-basement density contrast.
    mag_crest = competing.magnetic_contact_crests(b2f.astype(np.float32),
                                                  sigma_grid=(2.0,), min_quantile=0.90)
    ambiguous = competing.coincidence_map(s.crest, mag_crest, tolerance_px=2.0)
    log(f"magnetic crest px={int(mag_crest.sum())}; ambiguous steps="
        f"{int(ambiguous.sum())}/{s.n_crest} = {ambiguous.sum()/max(s.n_crest,1):.3f}")

    arms: dict[str, np.ndarray] = {}
    domain_of: dict[str, np.ndarray | None] = {}

    def emit(mask, score, tag, restrict=None):
        m = np.asarray(mask, bool) & fp
        if restrict is not None:
            m &= np.asarray(restrict, bool)
        if not m.any():
            log(f"    {tag}: EMPTY")
            return
        dots = emission.thin_to_dots(m, score, THIN_PX)
        dots = emission.prune_near(dots, visible, 2)
        dots = emission.apply_budget(dots, score, a.budget)
        arms[tag] = dots
        domain_of[tag] = restrict
        log(f"    {tag}: support={int(m.sum())} dots={int(dots.sum())}")

    crest_all = s.crest
    crest_dem = s.crest & ~ambiguous
    score_dem = emission.nearest_crest_value(np.where(crest_dem, s.throw, 0.0), crest_dem)

    def ribbon(crest, sc0, offs):
        rib, _ = emission.ribbon_mask(crest, offsets_px=offs)
        return rib, emission.nearest_crest_value(sc0, crest) * rib

    geometry = {
        "k1": (0.0,),
        "k2_s3": (0.0, 3.0),
        "k2_s6": (0.0, 6.0),
        "k3_s6": (0.0, 6.0, 12.0),
        "k4_s3": (0.0, 3.0, 6.0, 9.0),
        "k3_s9": (0.0, 9.0, 18.0),
    }
    for tag, offs in geometry.items():
        rib, sc = ribbon(crest_all, score0, offs)
        emit(rib, sc, f"ribbon_{tag}")
    for tag, offs in geometry.items():
        rib, sc = ribbon(crest_all, score0, offs)
        emit(rib, sc, f"basin_{tag}", restrict=basin)
    for tag, offs in (("k1", (0.0,)), ("k3_s6", (0.0, 6.0, 12.0))):
        rib, sc = ribbon(crest_dem, np.where(crest_dem, s.throw, 0.0), offs)
        emit(rib, sc, f"demoted_{tag}")

    # top-throw concentration inside the basin (pre-registered refinement)
    rib1, sc1 = ribbon(crest_all, score0, (0.0,))
    emit(rib1 & (sc1 >= np.quantile(sc1[basin & rib1], 0.75)), sc1,
         "basin_topthrow_k1", restrict=basin)

    # ---------------------------------------------------------------- nulls
    # Every null is matched to a *specific* arm: same spatial domain and the
    # same number of dots, so the paired difference is a clean test of whether
    # the step geometry carries information at all.
    for name in list(arms):
        restrict = domain_of[name]
        n_dots = int(arms[name].sum())
        support = crest_all if restrict is None else (crest_all & restrict)
        reps = random_line_null(support, fp, visible, max(n_dots, 1), a.seed, 1,
                                restrict=restrict)
        sc = np.float32(reps[0])
        d = emission.thin_to_dots(reps[0], sc, THIN_PX)
        d = emission.apply_budget(d, sc, n_dots)
        arms[f"null__{name}"] = d
        domain_of[f"null__{name}"] = restrict
        log(f"    null__{name}: dots={int(d.sum())} (matched to {n_dots})")

    # ------------------------------------------------------------ scoring
    log("holdout scoring")
    terms = {n: eh.terms_for(d.astype(np.float32), hidden, valid=valid, known=known)[0]
             for n, d in arms.items()}
    dtis = eh.pooled(terms)
    for n, v in sorted(dtis.items(), key=lambda kv: -kv[1]):
        log(f"    HOLDOUT-DTI {n:22s} = {v:.6f}")

    structural = [n for n in arms if not n.startswith("null__")]
    boot = {}
    for cand in structural:
        ref = f"null__{cand}"
        if ref not in terms:
            continue
        boot[cand] = eh.bootstrap_paired(terms, cand, ref, draws=1000, seed=a.seed)
    summary = {}
    for cand, b in boot.items():
        ref = f"null__{cand}"
        key = f"{cand}_minus_{ref}"
        summary[cand] = dict(dots=int(arms[cand].sum()),
                             null_dots=int(arms[ref].sum()),
                             dti=b[cand]["dti"], ci95=b[cand]["ci95"],
                             null_dti=b[ref]["dti"],
                             reference=ref,
                             diff=b[key]["mean"], diff_ci95=b[key]["ci95"],
                             p_ge_zero=b[key]["p_ge_zero"],
                             beats_null=bool(b[key]["ci95"][0] > 0.0))
    for n in sorted(summary, key=lambda k: -summary[k]["dti"]):
        q = summary[n]
        log(f"    {n:22s} DTI={q['dti']:.6f} CI=[{q['ci95'][0]:.6f},{q['ci95'][1]:.6f}]"
            f"  null={q['null_dti']:.6f}  d={q['diff']:+.6f} "
            f"CI=[{q['diff_ci95'][0]:+.6f},{q['diff_ci95'][1]:+.6f}] "
            f"P(d>=0)={q['p_ge_zero']:.3f} {'BEATS' if q['beats_null'] else 'tie/loss'}")

    # positional resolution of the chosen geometry, measured not assumed
    d_crest = distance_transform_edt(~s.crest)
    dh = d_crest[g.catalogue]
    resolution = dict(p10=float(np.percentile(dh, 10)), p50=float(np.percentile(dh, 50)),
                      p90=float(np.percentile(dh, 90)))
    log(f"catalogue distance to crest p10/p50/p90 = "
        f"{resolution['p10']:.1f}/{resolution['p50']:.1f}/{resolution['p90']:.1f} px")

    # ------------------------------------------------- lane recovery test
    # The prompt's own question: how many withheld basin-interior segments do
    # the steps recover, against random lines?
    from scipy.ndimage import label as _label
    lab, nlab = _label(hidden, structure=STRUCT8)
    ids = np.unique(lab[lab > 0])
    dcrest = distance_transform_edt(~s.crest)

    def recovery(dots):
        d = distance_transform_edt(~np.asarray(dots, bool))
        rec = tot = brec = btot = 0
        for i in ids:
            seg = lab == i
            hit = bool((d[seg] <= 3.0).any())
            tot += 1
            rec += int(hit)
            if (seg & basin).any():
                btot += 1
                brec += int(hit)
        return dict(segments_total=tot, segments_recovered=rec,
                    recovery_rate=rec / max(tot, 1),
                    basin_segments_total=btot, basin_segments_recovered=brec,
                    basin_recovery_rate=brec / max(btot, 1))

    recovery_out = {}
    for cand in structural:
        recovery_out[cand] = recovery(arms[cand])
        recovery_out[f"null__{cand}"] = recovery(arms[f"null__{cand}"])
    for n in sorted(structural, key=lambda k: -summary[k]["dti"]):
        r, rn = recovery_out[n], recovery_out[f"null__{n}"]
        log(f"    recovery {n:22s} basin {r['basin_segments_recovered']}/"
            f"{r['basin_segments_total']} = {r['basin_recovery_rate']:.3f}  "
            f"null {rn['basin_segments_recovered']}/{rn['basin_segments_total']} = "
            f"{rn['basin_recovery_rate']:.3f}")

    (ROOT / "evidence").mkdir(exist_ok=True)
    (ROOT / ".cache").mkdir(exist_ok=True)
    for name, d in arms.items():
        np.save(ROOT / f".cache/arm_{name}.npy", d)
    out = dict(
        evidence_class="HOLDOUT-DTI",
        evaluator_version=eh.VERSION,
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        parameters=dict(drho=a.drho, z0=a.z0, cutoff_wavelength_m=a.cutoff,
                        budget=a.budget, hide_fraction=a.hide_fraction,
                        buffer_px=a.buffer_px, seed=a.seed, thin_px=THIN_PX),
        n_withheld_positives=int(hidden.sum()),
        n_visible_masked=int(visible.sum()),
        folds={f.name: f.n_truth for f in folds},
        basin_interior_px=int(basin.sum()),
        magnetic=dict(magnetic_crest_px=int(mag_crest.sum()),
                      ambiguous_step_px=int(ambiguous.sum()),
                      ambiguous_fraction=float(ambiguous.sum() / max(s.n_crest, 1))),
        resolution_px=resolution,
        holdout_dti=summary,
        raw_dti=dtis,
        recovery=recovery_out,
        canary_auc=canary,
        runtime_s=round(time.time() - started, 1),
    )
    (ROOT / "evidence/candidate_arms.json").write_text(json.dumps(out, indent=2) + "\n")
    (ROOT / "evidence/lane_experiments.json").write_text(json.dumps(out, indent=2) + "\n")
    log(f"done in {time.time()-started:.0f}s -> evidence/candidate_arms.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(
        "Retired: this legacy candidate/holdout pipeline has no current pre-placement "
        "gate and the experiment budget is exhausted. Do not run another candidate or holdout trial."
    )
