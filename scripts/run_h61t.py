#!/usr/bin/env python3
"""H61-T driver -- buried-structure lane, session arena/f1bed08d (2026-10-11).

Two NEW in-lane constructions, both grounded in the lane paragraph (basement
depth steps from Parker/Oldenburg inversion of the isostatic residual), and
both targeting the lane's named competing explanation -- density contrasts
INSIDE the basement -- as a measured discriminator rather than an assertion:

E2  **Step persistence (T1 arm).**  A buried normal fault is a monopole step:
    the depth offset measured across the HGM maximum PERSISTS along the
    gradient direction (the far-field offset equals the near-field offset,
    same sign).  A finite density body inside the basement (sill, dike,
    pluton flank) is a closing dipole: the local gradient is large but the
    offset measured +/-8 px along the gradient direction shrinks or flips
    sign.  Emission is restricted to steps whose offset persists
    (sign agreement and far/near ratio >= 0.6) -- the competing explanation
    removed by measurement.

E3  **Independent-depth consensus (T2 arm).**  The organiser supplies an
    independent basement-depth product (band 15, depth_to_base_surf).  The
    lane's own inversion of band 13 is a separate processing chain.  A
    gravity-inversion artefact (smearing, regional/residual leakage) will
    not generally coincide with an edge of the supplied depth surface, so
    steps of BOTH surfaces within +/-5 px of each other are kept.  Band 15
    has only ever been a calibration target / habitat covariate in this
    repository; it has never been a lane locator.

E1  **Baseline (T0 arm).**  The pure lane field re-measured on the current
    evaluator: persistent basement steps with measured throw >= 80 m,
    restricted to the basin interior, ranked by throw.

Reuse, don't rebuild (protocol rule 2): the 200 m + 400 m GP-1012-calibrated
inversions and their derived fields come from the shared cache built by
``scripts/run_h61mh.py features`` (``.cache/h61m/``).  Holdout, scoring,
bootstrap CI, segment recovery and the leakage canary are the shared
instruments of ``gems61.holdout_segmented`` v2 and ``scripts/run_h61g.py``.

Stages (each writes one JSON into evidence/):
  holdout   E1/E2/E3 + controls + leakage canary + segment recovery
  final     build + validate the GeoTIFF of the holdout's choice
  unique    uniqueness.check() against every registry raster + repo rasters
  card      the run card
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems61 import buried as B                       # noqa: E402
from gems61 import grid as gridmod                   # noqa: E402
from gems61 import holdout_segmented as holdoutmod   # noqa: E402
from gems61 import submission_writer                 # noqa: E402
from gems61 import uniqueness as U                   # noqa: E402
from gems61.metric import ALPHA, BETA, EPS, kernel   # noqa: E402

import run_h61g as R                                 # noqa: E402  (shared tools, not forks)
from gems61 import h61mh as MH                       # noqa: E402

EVID = ROOT / "evidence"
OUT = ROOT / "out"
CACHE = ROOT / ".cache" / "h61m"
DOWNLOADS = ROOT / "docs" / "downloads"
SEEDS = R.SEEDS
EVALUATOR = R.EVALUATOR

BUDGETS = (20000, 40000)
PRUNES = (2.0, 3.0)
TILE_PX = 3
NEAR_PX = 2.0          # near-field offset half-span, 200 m
FAR_PX = 8.0           # far-field offset half-span, 800 m
PERSIST_MIN = 0.6      # far/near offset ratio for a monopole step
DETREND_PX = 6.0       # local-plane removal scale for offset measurement, 600 m
CONSENSUS_CORRIDOR_PX = 5   # +/- 500 m agreement between the two depth surfaces
MIN_NEAR_M = 40.0      # |near-field offset| floor so ratios are not noise/noise


def log(msg: str) -> None:
    print(msg, flush=True)


def load_base():
    g = gridmod.load_grid()
    grav = np.asarray(B.load_band(13), np.float64)
    valid = g.footprint & np.isfinite(grav)
    return g, grav, valid


def _need(name: str) -> np.ndarray:
    p = CACHE / f"{name}.npy"
    if not p.exists():
        raise SystemExit(f"missing {p}; run: PYTHONPATH=src python scripts/run_h61mh.py features")
    return np.load(p)


_INPAINT_CACHE: dict = {}


def depth_filled(depth_fine: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Diffusion-inpainted depth surface (NaN holes at survey rims included).

    Every directional measurement in H61-T samples this surface; a zero or
    mean fill would fabricate offsets wherever the sampling span crosses a
    NaN hole (measured artefact, corrected).  The inpaint is cached so the
    expensive diffusion runs once per process.
    """
    key = id(depth_fine)
    if key not in _INPAINT_CACHE:
        d = np.asarray(depth_fine, np.float64)
        finite = np.isfinite(d) & np.asarray(valid, bool)
        fill = float(d[finite].mean()) if finite.any() else 0.0
        _INPAINT_CACHE[key] = B.inpaint_smooth(np.where(finite, d, fill), finite)
    return _INPAINT_CACHE[key]


def depth_gradients(depth_fine: np.ndarray, valid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Gradients of the upsampled inverted depth on the inpainted surface."""
    filled = depth_filled(depth_fine, valid)
    gy, gx = np.gradient(filled)
    return np.where(valid, gx, 0.0), np.where(valid, gy, 0.0)


# --------------------------------------------------------------------------- #
# E2: step persistence (monopole fault step vs closing intrabasement dipole)
# --------------------------------------------------------------------------- #
def _local_plane_detrend(d: np.ndarray, valid: np.ndarray, radius_px: int = 10) -> np.ndarray:
    """Subtract the weighted least-squares plane fitted in a square window.

    For a square window centred on the pixel the normal equations decouple
    (the cross term sum x'y' vanishes by symmetry), so the fitted slopes are

        b = sum x' z / sum x'^2 ,   a = sum y' z / sum y'^2 ,   c = mean z

    all computed as box-filter sums weighted by ``valid``.  Removing the local
    plane takes out half-graben tilt and the regional gradient while keeping
    the step itself (a 600 m Gaussian detrend was tried first and removed the
    near-field signal it meant to measure -- instrument artefact, corrected).
    """
    from scipy.ndimage import uniform_filter
    H, W = d.shape
    w = np.asarray(valid, np.float64)
    z = np.where(np.isfinite(d) & (w > 0), d, 0.0) * w
    yy, xx = np.mgrid[0:H, 0:W]
    y = yy.astype(np.float64) * w
    x = xx.astype(np.float64) * w
    size = 2 * radius_px + 1
    kw = dict(size=size, mode="nearest")
    N = uniform_filter(w, **kw)
    Sz = uniform_filter(z, **kw)
    Sx = uniform_filter(x, **kw)
    Sy = uniform_filter(y, **kw)
    Sxz = uniform_filter(xx.astype(np.float64) * z, **kw)
    Syz = uniform_filter(yy.astype(np.float64) * z, **kw)
    Sx2 = uniform_filter(xx.astype(np.float64) ** 2 * w, **kw)
    Sy2 = uniform_filter(yy.astype(np.float64) ** 2 * w, **kw)
    N = np.maximum(N, 1e-9)
    zbar = Sz / N
    xb = Sx / N
    yb = Sy / N
    cov_xz = Sxz / N - xb * zbar
    cov_yz = Syz / N - yb * zbar
    var_x = np.maximum(Sx2 / N - xb * xb, 1e-9)
    var_y = np.maximum(Sy2 / N - yb * yb, 1e-9)
    b = cov_xz / var_x
    a = cov_yz / var_y
    plane = a * (yy - yb) + b * (xx - xb) + zbar
    out = np.where(w > 0, d - plane, 0.0)
    return out


def step_persistence(depth_fine: np.ndarray, grad_x: np.ndarray, grad_y: np.ndarray,
                     valid: np.ndarray) -> dict:
    """Far-field / near-field depth offset measured along the local gradient.

    The depth surface is locally plane-detrended in a +/-1 km window so that a
    regional half-graben tilt cannot masquerade as a persistent offset: a pure
    plane gives zero detrended offset everywhere, so only genuine steps
    survive.  A buried normal fault is a monopole: the detrended offset at
    +/-800 m keeps the sign and most of the magnitude of the +/-200 m offset.
    A finite intrabasement density body is a closing dipole: the far offset
    shrinks or flips.
    """
    from scipy.ndimage import map_coordinates
    d = depth_filled(depth_fine, valid)
    det = _local_plane_detrend(d, valid, radius_px=10)

    gmag = np.hypot(grad_x, grad_y)
    uy = np.where(gmag > 1e-9, grad_y / np.maximum(gmag, 1e-9), 0.0)
    ux = np.where(gmag > 1e-9, grad_x / np.maximum(gmag, 1e-9), 0.0)

    yy, xx = np.mgrid[0:det.shape[0], 0:det.shape[1]]

    def offset(span_px: float) -> np.ndarray:
        py = yy + span_px * uy
        px = xx + span_px * ux
        my = yy - span_px * uy
        mx = xx - span_px * ux
        plus = map_coordinates(det, [py.ravel(), px.ravel()], order=1,
                               mode="nearest").reshape(det.shape)
        minus = map_coordinates(det, [my.ravel(), mx.ravel()], order=1,
                                mode="nearest").reshape(det.shape)
        return plus - minus

    o_near = offset(NEAR_PX)
    o_far = offset(FAR_PX)
    ratio = np.abs(o_far) / np.maximum(np.abs(o_near), 1e-9)
    persist = np.clip(ratio, 0.0, 1.5)
    sign_ok = (o_far * o_near) > 0
    qualified = sign_ok & (persist >= PERSIST_MIN) & (np.abs(o_near) >= MIN_NEAR_M)
    return dict(o_near=o_near, o_far=o_far, persist=np.where(sign_ok, persist, 0.0),
                qualified=qualified, detrend="local plane fit +/-1 km window",
                near_px=NEAR_PX, far_px=FAR_PX, persist_min=PERSIST_MIN,
                min_near_m=MIN_NEAR_M)


# --------------------------------------------------------------------------- #
# E3: independent-depth consensus (lane inversion vs supplied band 15)
# --------------------------------------------------------------------------- #
def band15_steps(valid: np.ndarray) -> dict:
    b15 = np.asarray(B.load_band(15), np.float64)
    finite = valid & np.isfinite(b15)
    work = B.inpaint_smooth(np.where(finite, b15, np.nan), finite)
    hgm = B.horizontal_gradient_magnitude(np.where(finite, work, np.nan), B.PIXEL_M)
    mx = B.blakely_simpson_maxima(hgm) & finite
    throw = B.step_magnitude(np.where(finite, work, np.nan), mx, window_px=1)
    keep = mx & np.isfinite(throw) & (throw >= MH.MIN_THROW_M)
    return dict(hgm=hgm, maxima=mx, throw=throw, steps=keep, finite=finite,
                n_steps=int(keep.sum()))


def consensus_mask(steps_inv: np.ndarray, steps_b15: np.ndarray,
                   corridor_px: int = CONSENSUS_CORRIDOR_PX) -> np.ndarray:
    """Mutual-corridor agreement of the two independent step sets."""
    c_inv = ndi.distance_transform_edt(~steps_inv) <= corridor_px
    c_b15 = ndi.distance_transform_edt(~steps_b15) <= corridor_px
    return c_inv & c_b15


# --------------------------------------------------------------------------- #
def stage_holdout(_a) -> None:
    t0 = time.time()
    g, grav, valid = load_base()
    depth_fine = _need("depth_fine")
    grad_x, grad_y = depth_gradients(depth_fine, valid)
    steps = _need("steps").astype(bool)
    throw = _need("throw")
    basin = _need("basin").astype(bool)
    corridor = _need("corridor").astype(bool)

    # ---- E2 instrument ------------------------------------------------------ #
    pers = step_persistence(depth_fine, grad_x, grad_y, valid)
    n_steps = int(steps.sum())
    n_pers = int((steps & pers["qualified"]).sum())
    log(f"E2: {n_steps} step px; {n_pers} persist ({n_pers / max(n_steps, 1):.2%})")

    # ---- E3 instrument ------------------------------------------------------ #
    b15 = band15_steps(valid)
    cons = consensus_mask(steps, b15["steps"])
    union_steps = (steps | b15["steps"]) & cons
    n_cons = int(union_steps.sum())
    log(f"E3: band15 steps {b15['n_steps']} px; consensus union {n_cons} px")

    # ---- arm score fields (0 outside the emission set; rank carries the order) #
    throw_inv = np.where(np.isfinite(throw), throw, 0.0)
    throw_b15 = np.where(np.isfinite(b15["throw"]), b15["throw"], 0.0)
    throw_union = np.maximum(throw_inv, throw_b15)

    s_t0 = np.where(steps & basin, throw_inv, 0.0)
    keep_t1 = steps & basin & pers["qualified"]
    s_t1 = np.where(keep_t1, throw_inv * np.clip(pers["persist"], 0.0, 1.0), 0.0)
    keep_t2 = union_steps & cons & basin
    s_t2 = np.where(keep_t2, throw_union, 0.0)

    arms = dict(T0_steps_basin=s_t0,
                T1_persistent_step=s_t1,
                T2_consensus=s_t2)
    for k, s in arms.items():
        log(f"  arm {k}: {int((s > 0).sum())} emission px, "
            f"{float((s > 0).sum()) / max(valid.sum(), 1):.4%} of footprint")

    # ---- holdout instrument ------------------------------------------------- #
    ctx = holdoutmod.build_holdout(g, hide_frac=0.20, seeds=SEEDS, modes=("all",))
    n_truth = sum(c.n_truth for c in ctx.cells)
    log(f"holdout: {len(ctx.cells)} cells, {n_truth} withheld truth px")
    from gems61.network import segments
    seg_cache = segments(g.catalogue, max_len_px=12)[0]
    dom_total = float(sum(c.active.sum() for c in ctx.cells if c.seed == ctx.cells[0].seed))
    results = []

    def run(name, kind, emit, budget=None, prune=None, tile=TILE_PX):
        parts, rec_rows = [], []
        for ci, cell in enumerate(ctx.cells):
            sl = cell.bbox
            vis = ctx.visible(cell.key)[sl]
            far = ndi.distance_transform_edt(~vis) > prune
            allowed = cell.active & far
            dom_px = float(cell.active.sum())
            b_cell = int(round(budget * dom_px / dom_total))
            p_crop = emit(cell, allowed, b_cell, ci)
            part, dp = R._score_crop(cell, p_crop)
            parts.append(part)
            hid = ctx.hidden_by_cell[cell.key][sl]
            ids = np.unique(seg_cache[sl][hid]); ids = ids[ids > 0]
            if dp is None:
                dp = np.full(hid.shape, np.inf)
            near = dp <= 3.0
            dep = depth_fine[sl]
            for sid in ids:
                m = (seg_cache[sl] == sid) & hid
                if m.any():
                    rec_rows.append((cell.key, int(sid), int(m.sum()),
                                     float(np.nanmedian(dep[m])) if np.isfinite(dep[m]).any() else float("nan"),
                                     float(near[m].mean())))
        pooled = R._pool(parts)
        rec = np.array([(r[2], r[3], r[4]) for r in rec_rows], np.float64) if rec_rows else np.zeros((0, 3))
        bmask = rec[:, 1] > 300.0 if rec.size else np.zeros(0, bool)
        n_b = int(bmask.sum()); k_b = int((rec[bmask, 2] >= 0.5).sum()) if n_b else 0
        n_all = int(rec.shape[0]); k_all = int((rec[:, 2] >= 0.5).sum()) if n_all else 0
        row = dict(name=name, kind=kind, budget=budget, prune_px=prune, tile_px=tile,
                   **pooled, ci95_bootstrap_cells=R._boot_ci(parts),
                   n_emitted_per_draw=pooled["n_emitted"] / len(SEEDS),
                   segments_withheld_total=n_all, segments_recovered_total=k_all,
                   segments_withheld_basin_interior=n_b, segments_recovered_basin_interior=k_b,
                   basin_recovery_rate=(k_b / n_b) if n_b else None,
                   basin_recovery_ci95=list(MH.wilson(k_b, n_b)) if n_b else None)
        results.append(row)
        log(f"  {name:58s} n/draw={row['n_emitted_per_draw']:7.0f} DTI={row['pooled_dti']:.4f} "
            f"CI[{row['ci95_bootstrap_cells'][0]:.4f},{row['ci95_bootstrap_cells'][1]:.4f}] "
            f"basin {k_b}/{n_b}")
        return row

    # ---- controls ----------------------------------------------------------- #
    for budget in BUDGETS:
        run(f"CONTROL random lines @ {budget}", "lines",
            lambda c, a, b, ci, **k: R.H.random_lines(a.shape, a, b, seed=100 + ci),
            budget=budget, prune=3.0)
    run("CONTROL random dots anywhere @ 40000", "dots",
        lambda c, a, b, ci, **k: R.H.random_dots(a, b, seed=300 + ci),
        budget=40000, prune=3.0)

    # ---- candidates --------------------------------------------------------- #
    def emit_field(score):
        """One dot per tile on the EMISSION SET ONLY.

        Pixels outside the arm's emission set carry -inf, not 0: ``dot_thin``
        treats any finite value (including 0) as emit-eligible, so a zero fill
        silently spends the remaining budget on arbitrary active pixels
        (measured bug, corrected; the arm then emits at most its own set size).
        """
        s = np.where(score > 0, score, -np.inf)

        def _emit(cell, allowed, b_cell, ci, **k):
            return MH.dot_thin(s[cell.bbox], allowed, b_cell, tile_px=TILE_PX)
        return _emit

    for arm, score in arms.items():
        for budget in BUDGETS:
            for prune in PRUNES:
                run(f"{arm} @ {budget} (prune {prune:.0f}px)", "candidate",
                    emit_field(score), budget=budget, prune=prune)

    # ---- leakage canary (protocol rule 4: AUC > 0.90 = leakage) ------------- #
    rng = np.random.default_rng(3)
    feats = {
        "corridor indicator": corridor.astype(np.float64),
        "step persistence (E2)": np.where(steps, pers["persist"], 0.0),
        "consensus indicator (E3)": cons.astype(np.float64),
        "inverted depth (200 m)": depth_fine,
        "step throw": throw_inv,
        "band 15 depth": np.asarray(B.load_band(15), np.float64),
        "band 13 gravity": grav,
    }
    pos_idx, neg_idx = [], []
    for cell in ctx.cells:
        sl = cell.bbox
        yy, xx = cell.truth_yx
        pos_idx.append((yy + sl[0].start, xx + sl[1].start))
        act = np.argwhere(cell.active)
        pick = act[rng.choice(act.shape[0], size=min(20000, act.shape[0]), replace=False)]
        neg_idx.append((pick[:, 0] + sl[0].start, pick[:, 1] + sl[1].start))
    py = np.concatenate([p[0] for p in pos_idx]); px = np.concatenate([p[1] for p in pos_idx])
    ny = np.concatenate([p[0] for p in neg_idx]); nx = np.concatenate([p[1] for p in neg_idx])
    canary = {}
    for fname, f in feats.items():
        pv = np.nan_to_num(np.asarray(f)[py, px], nan=0.0)
        nv = np.nan_to_num(np.asarray(f)[ny, nx], nan=0.0)
        canary[fname] = dict(auc=MH.auc_rank(pv, nv), n_pos=int(pv.size), n_neg=int(nv.size))
        log(f"  canary {fname:28s} AUC={canary[fname]['auc']:.3f}")
    worst = max(canary.values(), key=lambda r: r["auc"])["auc"]

    cands = [r for r in results if r["kind"] == "candidate"]
    best = max(cands, key=lambda r: r["pooled_dti"])
    R.write_json("h61t_holdout.json", dict(
        evidence_class="HOLDOUT-DTI",
        evaluator=EVALUATOR, alpha=ALPHA, beta=BETA, kernel_m=300,
        n_withheld_truth_px=int(n_truth), n_cells=len(ctx.cells),
        instruments=dict(
            E2_step_persistence=dict(detrend=pers["detrend"], near_px=pers["near_px"],
                                     far_px=pers["far_px"], persist_min=pers["persist_min"],
                                     min_near_m=pers["min_near_m"],
                                     qualified_px=n_pers, steps_px=n_steps,
                                     qualified_fraction=n_pers / max(n_steps, 1)),
            E3_consensus=dict(band15_steps_px=b15["n_steps"], consensus_union_px=n_cons,
                              corridor_px=CONSENSUS_CORRIDOR_PX,
                              note="band 15 HGM steps (throw >= 80 m) within +/-5 px of the "
                                   "lane-inversion steps, and vice versa")),
        results=results, best_candidate=best["name"],
        leakage_canary=dict(threshold_auc=0.90, worst_auc=worst,
                            worst_feature=max(canary, key=lambda k: canary[k]["auc"]),
                            passed=bool(worst < 0.90), per_feature=canary),
        note="HOLDOUT-DTI is an evaluator-version index on withheld catalogue traces; it is not a "
             "competition score. No arm trains on the catalogue: every score field is a "
             "catalogue-free physics construction, pruned only against the visible catalogue "
             "of its own cell, per parallel-run protocol rule 2.",
        elapsed_s=round(time.time() - t0, 1)))


# --------------------------------------------------------------------------- #
def stage_equaldot(_a) -> None:
    """Equal-emission control: random lines/dots at the shipped arm's dot count.

    The lane's step field is emission-capped (~4 k dots), so the protocol's
    "steps vs random lines" question is only fair at the same number of
    emitted dots.  Appended to evidence/h61t_holdout.json, never re-scored
    into the candidate sweep.
    """
    g, grav, valid = load_base()
    depth_fine = _need("depth_fine")
    hold = json.loads((EVID / "h61t_holdout.json").read_text())
    t0 = next(r for r in hold["results"] if r["name"].startswith("T0_steps_basin")
              and r["prune_px"] == 2.0)
    budget = int(round(t0["n_emitted_per_draw"]))
    ctx = holdoutmod.build_holdout(g, hide_frac=0.20, seeds=SEEDS, modes=("all",))
    from gems61.network import segments
    seg_cache = segments(g.catalogue, max_len_px=12)[0]
    dom_total = float(sum(c.active.sum() for c in ctx.cells if c.seed == ctx.cells[0].seed))
    rows = []

    def run(name, emit):
        parts, rec_rows = [], []
        for ci, cell in enumerate(ctx.cells):
            sl = cell.bbox
            vis = ctx.visible(cell.key)[sl]
            far = ndi.distance_transform_edt(~vis) > 2.0
            allowed = cell.active & far
            b_cell = int(round(budget * float(cell.active.sum()) / dom_total))
            p_crop = emit(cell, allowed, b_cell, ci)
            part, dp = R._score_crop(cell, p_crop)
            parts.append(part)
            hid = ctx.hidden_by_cell[cell.key][sl]
            ids = np.unique(seg_cache[sl][hid]); ids = ids[ids > 0]
            if dp is None:
                dp = np.full(hid.shape, np.inf)
            near = dp <= 3.0
            dep = depth_fine[sl]
            for sid in ids:
                m = (seg_cache[sl] == sid) & hid
                if m.any():
                    rec_rows.append((float(np.nanmedian(dep[m])) if np.isfinite(dep[m]).any()
                                     else float("nan"), float(near[m].mean())))
        pooled = R._pool(parts)
        rec = np.array(rec_rows, np.float64) if rec_rows else np.zeros((0, 2))
        bmask = rec[:, 0] > 300.0 if rec.size else np.zeros(0, bool)
        rows.append(dict(name=name, budget=budget, **pooled,
                         ci95_bootstrap_cells=R._boot_ci(parts),
                         n_emitted_per_draw=pooled["n_emitted"] / len(SEEDS),
                         segments_withheld_basin_interior=int(bmask.sum()),
                         segments_recovered_basin_interior=int((rec[bmask, 1] >= 0.5).sum())))
        log(f"  {name:50s} n/draw={rows[-1]['n_emitted_per_draw']:6.0f} "
            f"DTI={pooled['pooled_dti']:.4f} basin {rows[-1]['segments_recovered_basin_interior']}"
            f"/{rows[-1]['segments_withheld_basin_interior']}")

    run(f"CONTROL random lines @ {budget} (equal-emission)",
        lambda c, a, b, ci, **k: R.H.random_lines(a.shape, a, b, seed=500 + ci))
    run(f"CONTROL random dots @ {budget} (equal-emission)",
        lambda c, a, b, ci, **k: R.H.random_dots(a, b, seed=600 + ci))
    hold["equal_emission_controls"] = dict(
        matched_to=f"{t0['name']} (n_emitted_per_draw={t0['n_emitted_per_draw']})",
        t0_segments_recovered_basin_interior=t0["segments_recovered_basin_interior"],
        rows=rows)
    R.write_json("h61t_holdout.json", hold)


# --------------------------------------------------------------------------- #
def stage_final(a) -> None:
    g, grav, valid = load_base()
    hold = json.loads((EVID / "h61t_holdout.json").read_text())
    cands = [r for r in hold["results"] if r["kind"] == "candidate"]
    chosen = max(cands, key=lambda r: r["pooled_dti"]) if not a.candidate else \
        next(r for r in cands if r["name"] == a.candidate)
    log(f"chosen: {chosen['name']}  DTI={chosen['pooled_dti']:.4f}")

    depth_fine = _need("depth_fine")
    grad_x, grad_y = depth_gradients(depth_fine, valid)
    steps = _need("steps").astype(bool)
    throw = _need("throw")
    basin = _need("basin").astype(bool)

    arm = chosen["name"].split(" @")[0]
    if arm == "T0_steps_basin":
        score = np.where(steps & basin, np.where(np.isfinite(throw), throw, 0.0), 0.0)
        arm_desc = ("Blakely-Simpson maxima of the Parker/Oldenburg inverted basement depth "
                    "(measured throw >= 80 m), basin interior, ranked by throw")
    elif arm == "T1_persistent_step":
        pers = step_persistence(depth_fine, grad_x, grad_y, valid)
        keep = steps & basin & pers["qualified"]
        score = np.where(keep, np.where(np.isfinite(throw), throw, 0.0) *
                         np.clip(pers["persist"], 0.0, 1.0), 0.0)
        arm_desc = ("monopole step persistence: far-field offset (+/-800 m along gradient) "
                    "keeps sign and >= 60% of the near-field (+/-200 m) offset; closing "
                    "intrabasement density bodies removed by measurement")
    elif arm == "T2_consensus":
        b15 = band15_steps(valid)
        cons = consensus_mask(steps, b15["steps"])
        keep = (steps | b15["steps"]) & cons & basin
        throw_union = np.maximum(np.where(np.isfinite(throw), throw, 0.0),
                                 np.where(np.isfinite(b15["throw"]), b15["throw"], 0.0))
        score = np.where(keep, throw_union, 0.0)
        arm_desc = ("consensus: steps of the lane's band-13 inversion within +/-500 m of steps "
                    "of the organiser-supplied band-15 depth surface (independent chain)")
    else:
        raise SystemExit(f"unknown arm {arm}")

    budget = int(chosen["budget"]); prune = float(chosen["prune_px"])
    far = ndi.distance_transform_edt(~g.catalogue) > prune
    allowed = valid & far & ~g.catalogue
    # emission set only: outside pixels carry -inf so dot_thin cannot spend
    # the remaining budget on arbitrary pixels (same fix as in stage_holdout)
    score_emit = np.where(score > 0, score, -np.inf)
    dots = MH.dot_thin(score_emit, allowed, budget, tile_px=TILE_PX)
    values = dots.astype(np.float32)
    n_dots = int(dots.sum())
    dcat = ndi.distance_transform_edt(~g.catalogue)[dots]
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    digest = hashlib.sha256(values.tobytes()).hexdigest()[:12]
    name = f"gems61-h61t-{arm.lower().replace('_', '-')}-{n_dots}dots-{stamp}-{digest}-zeros"
    short = arm_desc[:84]
    if len(arm_desc) > 84:
        short = short[:short.rfind(" ")]               # cut at a word edge
        if short.count("(") > short.count(")"):        # never dangle an open bracket
            short = short[:short.rfind("(")].rstrip()
    note = f"H61-T {arm}: {short}; {n_dots} dots; UNSCORED"
    assert len(note) <= 140, len(note)
    OUT.mkdir(exist_ok=True)
    receipt = submission_writer.write_submission(
        OUT / f"{name}.tif", values, sample=gridmod.DATA_DIR / "sample_submission.tif",
        footprint=g.footprint, note=note, name=name[:140], catalogue=g.catalogue,
        metadata=dict(method="H61-T", arm=arm, arm_description=arm_desc, budget=budget,
                      prune_px=prune, tile_px=TILE_PX, n_dots=n_dots,
                      holdout_dti=chosen["pooled_dti"], holdout_ci95=chosen["ci95_bootstrap_cells"],
                      evaluator=EVALUATOR,
                      sources=dict(
                          parker="Parker (1973) GJI 31:447-455, doi:10.1111/j.1365-246X.1973.tb02307.x",
                          oldenburg="Oldenburg (1974) Geophysics 39(4):526-536, doi:10.1190/1.1440444",
                          blakely_simpson="Blakely & Simpson (1986) Geophysics 51(7):1494-1498, doi:10.1190/1.1442197",
                          blakely_jachens="Blakely & Jachens (1991) GSA Bulletin 103:795-803",
                          gp1012="Saltus & Jachens (1995) USGS GP-1012, doi:10.3133/gp1012"),
                      no_prior_submission_raster_used=True))
    # persist the soft surface for the uniqueness surface leg
    np.save(OUT / f"{name}.surface.npy", score.astype(np.float32))
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    for ext in (".tif", ".zip", ".json"):
        shutil.copy2(OUT / f"{name}{ext}", DOWNLOADS / f"{name}{ext}")
    rand = next((r for r in hold["results"] if r["name"].startswith("CONTROL random lines")
                 and r["budget"] == budget), None)
    R.write_json("h61t_final.json", dict(
        evidence_class="MEASURED (file) + HOLDOUT-DTI (selection)",
        submission=name, note=note, note_chars=len(note), arm=arm, arm_description=arm_desc,
        budget=budget, prune_px=prune, tile_px=TILE_PX, n_dots=n_dots,
        dots_distance_to_catalogue_px=dict(min=float(dcat.min()), median=float(np.median(dcat)),
                                           mean=float(dcat.mean()),
                                           frac_within_3px=float((dcat <= 3).mean())),
        tif=f"out/{name}.tif", zip=f"out/{name}.zip", receipt=f"out/{name}.json",
        download_tif=f"docs/downloads/{name}.tif", download_zip=f"docs/downloads/{name}.zip",
        sha256=receipt["sha256"], bytes=receipt["bytes"], zip_sha256=receipt["zip_sha256"],
        validator=receipt["validator"]["checks"],
        validator_all_passed=receipt["validator"]["all_checks_passed"],
        holdout=dict(dti=chosen["pooled_dti"], ci95=chosen["ci95_bootstrap_cells"],
                     random_lines=rand["pooled_dti"] if rand else None,
                     beats_random_lines=bool(rand and chosen["pooled_dti"] > rand["pooled_dti"]),
                     segments_withheld_basin_interior=chosen["segments_withheld_basin_interior"],
                     segments_recovered_basin_interior=chosen["segments_recovered_basin_interior"],
                     basin_recovery_ci95=chosen["basin_recovery_ci95"],
                     random_lines_segments_recovered_basin_interior=(
                         rand["segments_recovered_basin_interior"] if rand else None),
                     n_withheld_truth_px=hold["n_withheld_truth_px"], evaluator=EVALUATOR),
        organizer_receipt=None))
    log(f"shipped {name}: {n_dots} dots, sha256 {receipt['sha256']}")


# --------------------------------------------------------------------------- #
def stage_unique(_a) -> None:
    import rasterio
    g = gridmod.load_grid()
    fin = json.loads((EVID / "h61t_final.json").read_text())
    with rasterio.open(ROOT / fin["tif"]) as src:
        mine = src.read(1)
    mine_dots = mine > 0.5
    surface = np.load(str(ROOT / fin["tif"]).replace(".tif", ".surface.npy"))

    # leg 1+2 against every registry raster (fail-closed shared gate).
    # surface_stride=4: the candidate is a 0/1 field at 0.09 % support, so a
    # ~325 k-sample lattice subsample is more than enough for the 0.90 drift
    # threshold; the dot leg runs on every emitted dot (exact).
    gate = U.check(candidate_surface=surface, candidate_dots=mine_dots,
                   footprint=g.footprint, surface_stride=4,
                   progress=lambda i, n: log(f"  registry {i}/{n}") if i % 200 == 0 else None)

    # extra leg: every earlier raster published in THIS repository
    local_rows = []
    for d in (DOWNLOADS, ROOT / "docs" / "submissions"):
        for p in sorted(d.glob("*.tif")):
            if p.name == Path(fin["tif"]).name:
                continue
            try:
                with rasterio.open(p) as src:
                    if (src.height, src.width) != g.shape:
                        continue
                    other = src.read(1)
            except Exception as exc:  # noqa: BLE001
                local_rows.append(dict(file=p.name, error=str(exc)[:100])); continue
            res = U.compare(mine.astype(np.float64), np.where(np.isfinite(other), other, 0.0),
                            g.footprint)
            local_rows.append(dict(file=p.name, sha256=U.sha256(p), **res))
            log(f"  local {p.name[:64]:64s} rho={res['spearman']:+.4f} "
                f"overlap3px={res['frac_dots_within_3px']:.3f} (base {res['eligible_base_rate_within_3px']:.3f})")
    local_overlap_worst = max((r for r in local_rows if "frac_dots_within_3px" in r),
                              key=lambda r: r["frac_dots_within_3px"], default=None)
    local_rho_worst = max((r for r in local_rows if "spearman" in r),
                          key=lambda r: r["spearman"], default=None)
    unique_local = bool((local_overlap_worst is None or
                         local_overlap_worst["frac_dots_within_3px"] <= U.OVERLAP_LIMIT or
                         (local_overlap_worst.get("enrichment_vs_base_rate", 1e9) or 1e9) < U.DUPLICATE_LIFT) and
                        (local_rho_worst is None or local_rho_worst["spearman"] <= U.SPEARMAN_LIMIT))
    per_raster = gate.pop("per_raster")
    R.write_json("h61t_uniqueness.json", dict(
        evidence_class="UNIQUENESS-CHECK", my_file=fin["tif"], my_sha256=fin["sha256"],
        my_dots=int(mine_dots.sum()),
        registry_gate=dict(gate, per_raster_rows=len(per_raster),
                           per_raster_omitted="748 rows kept in registry_refreshed.json + "
                                              "re-runnable via scripts/run_h61t.py unique"),
        local_repo_gate=dict(n_compared=len(local_rows),
                             worst_spearman=local_rho_worst,
                             worst_overlap=local_overlap_worst,
                             pass_local=unique_local,
                             rows=local_rows),
        verdict="UNIQUE" if (gate["unique"] and unique_local) else "DUPLICATE -- do not submit"))
    log(f"UNIQUENESS verdict: {'UNIQUE' if gate['unique'] and unique_local else 'DUPLICATE'}")


# --------------------------------------------------------------------------- #
def stage_card(_a) -> None:
    hold = json.loads((EVID / "h61t_holdout.json").read_text())
    fin = json.loads((EVID / "h61t_final.json").read_text())
    uni = json.loads((EVID / "h61t_uniqueness.json").read_text())
    cands = [r for r in hold["results"] if r["kind"] == "candidate"]
    best = max(cands, key=lambda r: r["pooled_dti"])
    rand = next((r for r in hold["results"] if r["name"].startswith("CONTROL random lines")
                 and r["budget"] == best["budget"]), None)
    prev_best = 0.06063316101428559     # evidence/h61m_run_card.json (H61-MH)
    beats_prev_lane_best = best["pooled_dti"] > prev_best
    beats_random = bool(rand and best["pooled_dti"] > rand["pooled_dti"])
    verdict = "promote" if (beats_random and beats_prev_lane_best) else "negative"
    card = dict(
        session="H61-T (arena/f1bed08d-61gemsdoe, 2026-10-11)",
        lane="buried-structure: basement-depth steps from gravity inversion",
        hypothesis=("A buried normal fault is a MONOPOLE step in the GP-1012-calibrated inverted "
                    "basement surface: the depth offset persists along the gradient direction, "
                    "whereas the lane's named competing explanation -- density contrasts inside "
                    "the basement -- closes into a dipole.  Additionally, a step seen by BOTH the "
                    "lane's band-13 inversion and the organiser-supplied band-15 depth surface "
                    "(independent processing chains) is less likely to be an inversion artefact."),
        mechanism=("Isostatic residual gravity (band 13) -> Parker/Oldenburg slab inversion at "
                   "200 m, regional removed at 15 km, density contrast calibrated to GP-1012 "
                   "basin-depth statistics -> Blakely-Simpson maxima of |grad depth| with measured "
                   "throw >= 80 m -> (E2) far-field/near-field offset persistence along the local "
                   "gradient on the locally-detrended depth surface; (E3) mutual +/-5 px corridor "
                   "agreement with band-15 depth-surface steps -> dots at 3 px spacing in the "
                   "basin interior, pruned >2-3 px from the visible mapped catalogue."),
        named_non_fault_process=("Density contrasts within basement (sills, dikes, pluton flanks, "
                                 "intrabasement lithologic contacts) make the same horizontal-"
                                 "gradient maximum.  E2 measures the discriminator directly: a "
                                 "finite body's offset closes over +/-800 m (far/near < 0.6 or "
                                 "sign flip); a fault's offset persists.  E3's independent-depth "
                                 "consensus is the second, unrelated filter."),
        experiments=dict(
            E1_baseline="T0 arm: pure lane field re-measured on the current evaluator",
            E2_persistence="T1 arm: monopole-step persistence gate",
            E3_consensus="T2 arm: band-13 inversion x band-15 supplied depth consensus"),
        holdout_dti=dict(
            value=best["pooled_dti"], ci95=best["ci95_bootstrap_cells"],
            evaluator=hold["evaluator"], n_withheld_positive_px=hold["n_withheld_truth_px"],
            label=f"HOLDOUT-DTI ({hold['evaluator']}, {hold['n_withheld_truth_px']} withheld "
                  "positive px, seeds 20+21, mode all, pooled alpha 0.2 beta 0.8 R 300 m)",
            random_lines_same_budget=rand["pooled_dti"] if rand else None,
            lane_previous_best_H61MH=prev_best,
            beats_random_lines=beats_random, beats_previous_lane_best=beats_prev_lane_best,
            basin_interior_recovery=dict(
                withheld=best["segments_withheld_basin_interior"],
                recovered=best["segments_recovered_basin_interior"],
                rate=best["basin_recovery_rate"], ci95=best["basin_recovery_ci95"],
                random_lines_recovered=(rand["segments_recovered_basin_interior"] if rand else None),
                equal_emission_controls=hold.get("equal_emission_controls"))),
        leakage_canary=hold["leakage_canary"],
        correlation_vs_registry=dict(
            worst_spearman=uni["registry_gate"]["worst_spearman"],
            worst_spearman_source=uni["registry_gate"]["worst_spearman_source"],
            limit=0.90,
            worst_dot_overlap_3px=uni["registry_gate"]["worst_dot_overlap_3px"],
            worst_dot_overlap_source=uni["registry_gate"]["worst_dot_overlap_source"],
            overlap_limit=0.70,
            n_registry_rasters=uni["registry_gate"]["n_registry_rasters"],
            verdict=uni["verdict"]),
        ribbon_note=("The lane paragraph says 'emit multi-line ribbons rather than thin lines'. "
                     "The shipped file emits dots because the live metric charges alpha=0.2 per "
                     "extra positive pixel and this lane measured 3x3 ribbons at roughly half the "
                     "pooled DTI of the same dots (H61-MH M4 arm, evidence/h61m_holdout.json). The "
                     "ribbon form of a gravity-step construction exists in this repo for audit "
                     "(gems61-h61m-gravmag-corridor-ribbon-40000dots, "
                     "61gemsdoe-basement-step-ribbon-20261011T054408Z); the selector may emit a "
                     "ribbon version of this exact dot set with MH.ribbon(dots, 1) at the cost of "
                     "~9x positive pixels and the measured DTI penalty."),
        raster_sha256=fin["sha256"],
        validator=dict(all_checks_passed=fin["validator_all_passed"], checks=fin["validator"]),
        submission=dict(name=fin["submission"], note=fin["note"], note_chars=fin["note_chars"],
                        download_tif=fin["download_tif"], download_zip=fin["download_zip"],
                        n_dots=fin["n_dots"], organizer_confirmed_score=None,
                        organizer_status="UNSCORED -- no submission-page receipt exists"),
        # Format-safe to download and upload (validator + uniqueness gates above);
        # whether to spend a weekly slot on it is the selector's decision (rule 6),
        # and this card's verdict says NOT to.
        okay_to_download=bool(fin["validator_all_passed"] and uni["verdict"] == "UNIQUE"),
        raster=dict(file=fin["download_tif"], sha256=fin["sha256"], bytes=fin["bytes"],
                    zip_file=fin["download_zip"], positive_pixels=fin["n_dots"]),
        verdict=verdict,
        verdict_note=("Every number above is HOLDOUT-DTI (evaluator version "
                      f"'{hold['evaluator']}'); nothing is ORGANIZER-CONFIRMED.  "
                      "A projection is never written as a score.") if verdict == "negative" else
                     ("Holdout best of the lane so far; promotion still needs the selector step "
                      "and an organiser receipt before any score is quoted."))
    R.write_json("h61t_run_card.json", card)
    log(f"run card written; verdict={verdict}")


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["holdout", "equaldot", "final", "unique", "card", "all"])
    ap.add_argument("--candidate", default=None)
    a = ap.parse_args()
    stages = {"holdout": stage_holdout, "equaldot": stage_equaldot, "final": stage_final,
              "unique": stage_unique, "card": stage_card}
    for name in (["holdout", "equaldot", "final", "unique", "card"]
                 if a.stage == "all" else [a.stage]):
        log(f"==== {name} ====")
        stages[name](a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
