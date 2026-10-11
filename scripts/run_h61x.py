#!/usr/bin/env python
"""H61-X driver -- two-scale basement-step corridors from gravity inversion.

The lane (see README "standing brief") says: invert the supplied isostatic
gravity, map maxima of the horizontal gradient of basement depth as candidate
buried range-front or intrabasin faults, emit multi-line ribbons (gravity
resolves a step only to a few hundred metres), report withheld basin-interior
segment recovery versus random lines, treat density contrasts within basement
as the competing explanation, output the standard validated GeoTIFF
uniqueness-checked against every earlier raster.

What this session adds (and why it is inside the lane)
------------------------------------------------------
The H61-G label-aware screen (evidence/h61g_screen.json) measured that gravity
HGM maxima are MORE fault-enriched at coarser smoothing: 1.08x at 200 m,
1.22x at 500 m, 1.32x at 1000 m (top 50 %), while H61-G's shipped corridor
(X2) used the unsmoothed (base-scale) step lines only.  Broad maxima survive
only where the step is large in total throw and deep -- i.e. the buried,
basin-interior basement steps the lane exists to find, as opposed to the
sharp shallow steps that dominate the base scale.

Construction (every number a measurement, no fitting to the score):

  1. invert_basement            (unchanged from H61-G: Parker/Oldenburg first
                                 iterate, GP-1012 calibrated, 400 m grid)
  2. base steps                 (unchanged: Blakely-Simpson maxima, throw >= 80 m)
  3. coarse steps               Blakely-Simpson maxima of the depth surface
                                 smoothed with a Gaussian sigma = 2 cells
                                 (800 m), throw >= 80 m, DISJOINT from the base
                                 corridor (nothing within 3 cells = 1.2 km)
  4. corridors, +/- 10 px (1 km):  corr_base (the X2 control corridor),
                                    corr_union = corr_base | corr_coarse (X3),
                                    corr_coarse (X3c, uniqueness-safe variant)
  5. emission (the locator H61-G validated inside this lane): Blakely-Simpson
     maxima of the detrended-elevation slope (band 19) inside corridor x basin
     interior (inverted depth > 100 m), weight = min(rank, 0.9) x
     (0.5 + 0.5 * concealment), one dot per 3 x 3 px tile, 40,000 dot budget,
     2 px prune from the VISIBLE catalogue per fold cell.

Candidates scored on the same holdout (protocol rule 2: whole withheld
segments, visible-only context, pixel-exact masking, pooled DTI
alpha=0.2 beta=0.8, 300 m triangular kernel):

  X2   corridor(corr_base)   -- instrument reproduction of H61-G's 0.0465
  X3   corridor(corr_union)  -- main hypothesis
  X3c  corridor(corr_coarse) -- coarse steps alone (the new step lines)
  CONTROL random lines @ same budget

The competing explanation (density contrasts INSIDE the basement) is handled
twice: (a) the in-corridor slope-ridge conjunction -- an intrabasement contact
gives a gravity step but no scarp, so it fails the conjunction; (b) a measured
diagnostic -- the fraction of base vs coarse step lines that sit on strong
magnetic edges (RTP band 2 HGM top 50 %, the proxy for igneous/lithologic
contacts), which is reported in h61x_invert.json, not used as a gate.

Stages (each writes one JSON into evidence/):

    invert   inversion + base/coarse steps + competing-explanation diagnostics
    holdout  scored candidates + controls + per-feature leakage canary
    final    build + validate the GeoTIFF the holdout selects
    unique   rank-correlation / 3 px dot-overlap against every earlier raster
    card     the run card
    all      invert -> holdout -> final -> unique -> card

Run from the repository root:

    PYTHONPATH=src .venv/bin/python scripts/run_h61x.py all
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

from gems61 import buried as B                       # noqa: E402
from gems61 import grid as gridmod                   # noqa: E402
from gems61 import h61g as H                         # noqa: E402
from gems61 import holdout_segmented as holdoutmod   # noqa: E402
from gems61 import submission_writer                 # noqa: E402
from gems61.metric import ALPHA, BETA, EPS, kernel   # noqa: E402
from gems61.network import segments                  # noqa: E402

EVID = ROOT / "evidence"
OUT = ROOT / "out"
CACHE = ROOT / ".cache" / "h61x"
DOWNLOADS = ROOT / "docs" / "downloads"
REGISTRY_DIRS = [Path("/tmp/refs/registry"), ROOT / "docs" / "downloads"]
BUDGET = 40000
PRUNE_PX = 2.0
SEEDS = (20, 21)
EVALUATOR = "gems61.holdout_segmented v2 (whole segments <=12 px, 4 eroded quadrants, seeds 20+21, mode all)"
COARSE_SMOOTH_PX = 2.0     # 800 m Gaussian on the 400 m inversion grid
COARSE_DISJOINT_PX = 3     # a coarse step within 1.2 km of a base step is not a new line
CORRIDOR_PX = 10           # +/- 1 km, the X2 width (one kernel of the lane's own resolution)

# The H61-G holdout was built with exactly these parameters; the construction is
# deterministic in (catalogue, seeds, modes), so its registry rows and controls
# are re-used here instead of re-scored, and one registry file is re-verified
# in-place below as the instrument check.
PREV_HOLDOUT = EVID / "h61g_holdout.json"


def log(msg: str) -> None:
    print(msg, flush=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(name: str, obj) -> Path:
    EVID.mkdir(exist_ok=True)
    p = EVID / name
    p.write_text(json.dumps(obj, indent=2, default=_jsonable) + "\n")
    log(f"wrote {p.relative_to(ROOT)}")
    return p


def _jsonable(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return str(o)


def load_base():
    g = gridmod.load_grid()
    grav = np.asarray(B.load_band(13), np.float64)
    valid = g.footprint & np.isfinite(grav)
    return g, grav, valid


def _pool(parts):
    tp = sum(p["tp"] for p in parts); fp = sum(p["fp"] for p in parts); fn = sum(p["fn"] for p in parts)
    return dict(pooled_dti=float(tp / (tp + ALPHA * fp + BETA * fn + EPS)), tp=tp, fp=fp, fn=fn,
                n_emitted=int(sum(p["n_emit"] for p in parts)),
                coverage=float(tp / max(tp + fn, 1e-9)))


def _boot_ci(parts, n_boot=2000, seed=7):
    rng = np.random.default_rng(seed)
    parts = list(parts)
    vals = []
    for _ in range(n_boot):
        pick = [parts[i] for i in rng.integers(len(parts), size=len(parts))]
        vals.append(_pool(pick)["pooled_dti"])
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def _score_crop(cell, p_crop):
    p = p_crop & cell.active
    n_emit = int(p.sum())
    if n_emit == 0 or cell.n_truth == 0:
        return dict(tp=0.0, fp=float(n_emit), fn=float(cell.n_truth), n_emit=n_emit), None
    dp = ndi.distance_transform_edt(~p)
    tp = float(kernel(dp[cell.truth_yx]).sum())
    fn = float(cell.n_truth) - tp
    fp = float((1.0 - cell.k_dg[p]).sum())
    return dict(tp=tp, fp=fp, fn=fn, n_emit=n_emit), dp


def _per_cell_emit(field, cell, visible_full, budget_cell):
    sl = cell.bbox
    vis = visible_full[sl]
    far = ndi.distance_transform_edt(~vis) > PRUNE_PX
    allowed = cell.active & far
    return H.dot_thin(field[sl], allowed, budget_cell)


# --------------------------------------------------------------------------- #
def stage_invert(_a) -> None:
    t0 = time.time()
    g, grav, valid = load_base()
    CACHE.mkdir(parents=True, exist_ok=True)
    inv = H.invert_basement(grav, valid)
    best = inv["calibration"]["best"]
    log(f"calibration: z0={best['z0_m']:.0f} m drho={best['delta_rho']:.0f} kg/m3 kc_scale={best['kc_scale']} "
        f"-> p50 {best['stats']['p50']:.0f} m, p90 {best['stats']['p90']:.0f} m, "
        f">1 km {best['stats']['fraction_gt_1km']:.3f} (GP-1012 anchor 0.20), rms {best['rms_residual_mgal']:.2f} mGal")
    depth_small = inv["depth_small"]
    depth_full = H.field_to_full_grid(depth_small, g.shape)
    b15 = np.asarray(B.load_band(15), np.float64)
    cross = B.compare_to_published_depth(b15, depth_full, valid)
    gsign = float(np.corrcoef(depth_full[valid], grav[valid])[0, 1])
    log(f"cross-check vs supplied band 15: r={cross['pearson_r']:.3f} slope={cross['slope_published_on_inverted']:.3f}; "
        f"corr(depth, gravity)={gsign:.4f} (must be negative)")
    if not gsign < 0:
        raise SystemExit("SIGN ERROR: inverted depth must anti-correlate with the isostatic residual")

    base = H.basement_steps(depth_small, inv["dx"], smooth_px=0.0)
    coarse_all = H.basement_steps(depth_small, inv["dx"], smooth_px=COARSE_SMOOTH_PX)
    # a coarse maximum is a NEW step line only if it is not within COARSE_DISJOINT_PX
    # of a base-scale step (same line seen blurred, not an additional structure)
    near_base = ndi.distance_transform_edt(~base["steps"]) <= COARSE_DISJOINT_PX
    coarse = coarse_all["steps"] & ~near_base
    # diagnostic only: the even coarser scale, for the report (declared, not a gate)
    coarse5 = H.basement_steps(depth_small, inv["dx"], smooth_px=5.0)
    coarse5_disjoint = int((coarse5["steps"] & ~near_base).sum())
    base_full = H.to_full_grid(base["steps"], g.shape) & valid
    coarse_full = H.to_full_grid(coarse, g.shape) & valid
    throw_coarse = np.where(coarse_all["steps"], coarse_all["throw"], 0.0)
    throw_coarse_full = H.field_to_full_grid(throw_coarse, g.shape)
    corr_base = H.corridor_mask(base_full, CORRIDOR_PX)
    corr_coarse = H.corridor_mask(coarse_full, CORRIDOR_PX)
    corr_union = corr_base | corr_coarse
    log(f"steps: base {base['n_maxima']} maxima -> {base['n_steps']} throw>=80 m; "
        f"coarse (sigma={COARSE_SMOOTH_PX} cells) {coarse_all['n_maxima']} maxima -> "
        f"{int(coarse_all['steps'].sum())} throw>=80 m, of which {int(coarse.sum())} DISJOINT from the base corridor")

    # --- competing-explanation diagnostic (measured, not a gate) ----------- #
    # an intrabasement density contrast (igneous contact / pluton margin) makes
    # a gravity step WITHOUT a fault: it should show a strong magnetic edge.
    rtp = np.asarray(B.load_band(2), np.float64)
    rtp_filled = B.inpaint_smooth(np.where(valid, rtp, np.nan), valid)
    rtp_hgm = B.horizontal_gradient_magnitude(ndi.gaussian_filter(rtp_filled, 2.0))
    rtp_mx = B.blakely_simpson_maxima(rtp_hgm) & valid
    rtp_strong = rtp_mx & (rtp_hgm >= np.percentile(rtp_hgm[rtp_mx], 50))
    d_mag = ndi.distance_transform_edt(~rtp_strong)
    d_mag_small = d_mag[::H.LANE_DECIMATION, ::H.LANE_DECIMATION][:depth_small.shape[0], :depth_small.shape[1]]
    def step_diag(mask_small, label):
        m = np.asarray(mask_small, bool)
        if not m.any():
            return dict(n=0, on_strong_mag_edge=None, median_depth=None)
        dep = depth_small[m]
        return dict(n=int(m.sum()),
                    on_strong_mag_edge=float((d_mag_small[m] <= 2).mean()),
                    median_depth=float(np.median(np.where(np.isfinite(dep), dep, np.nan))) if np.isfinite(dep).any() else None)
    diag_base = step_diag(base["steps"], "base")
    diag_coarse = step_diag(coarse, "coarse")
    log(f"competing explanation (magnetic-edge diagnostic): base steps on strong mag edge "
        f"{diag_base['on_strong_mag_edge']:.3f} (n={diag_base['n']}); coarse steps "
        f"{diag_coarse['on_strong_mag_edge']:.3f} (n={diag_coarse['n']})")

    throw_b = base["throw"][base["steps"]]
    throw_c = coarse_all["throw"][coarse]
    np.save(CACHE / "depth_full.npy", depth_full.astype(np.float32))
    np.save(CACHE / "base_full.npy", base_full)
    np.save(CACHE / "coarse_full.npy", coarse_full)
    np.save(CACHE / "throw_coarse_full.npy", throw_coarse_full.astype(np.float32))
    np.save(CACHE / "corr_base.npy", corr_base)
    np.save(CACHE / "corr_coarse.npy", corr_coarse)
    np.save(CACHE / "corr_union.npy", corr_union)
    write_json("h61x_invert.json", dict(
        evidence_class="MEASURED",
        inversion_grid=dict(decimation=H.LANE_DECIMATION, pixel_m=inv["dx"], shape=list(depth_small.shape),
                            valid_fraction=float(inv["valid_small"].mean())),
        calibration=inv["calibration"], inversion=inv["inversion"],
        depth_stats=B.calibrate_depth_scale(depth_small, inv["valid_small"]),
        cross_check_vs_supplied_band15=dict(cross, corr_depth_vs_gravity=gsign),
        steps=dict(
            base=dict(n_hgm_maxima=base["n_maxima"], n_throw_filtered=base["n_steps"],
                      min_throw_m=H.MIN_THROW_M,
                      throw_p50_m=float(np.median(throw_b)) if throw_b.size else None),
            coarse=dict(smooth_px=COARSE_SMOOTH_PX, n_cells=H.LANE_DECIMATION,
                        n_hgm_maxima=coarse_all["n_maxima"],
                        n_throw_filtered=int(coarse_all["steps"].sum()),
                        n_disjoint_from_base=int(coarse.sum()),
                        min_throw_m=H.MIN_THROW_M, disjoint_px=COARSE_DISJOINT_PX,
                        throw_p50_m=float(np.median(throw_c)) if throw_c.size else None,
                        sigma5_diagnostic=dict(n_hgm_maxima=coarse5["n_maxima"],
                                               n_throw_filtered=int(coarse5["steps"].sum()),
                                               n_disjoint_from_base=coarse5_disjoint)),
            corridor_px=CORRIDOR_PX,
            corr_base_fraction_of_valid=float((corr_base & valid).sum() / valid.sum()),
            corr_coarse_fraction_of_valid=float((corr_coarse & valid).sum() / valid.sum()),
            corr_union_fraction_of_valid=float((corr_union & valid).sum() / valid.sum())),
        competing_explanation=dict(
            named_process="density contrasts inside the basement (igneous contacts, pluton margins, buried "
                          "volcanic centres) produce the same horizontal-gradient maximum as a fault step, "
                          "with no scarp at the surface",
            test_1="in-corridor slope-ridge conjunction: an intrabasement contact has a gravity step but "
                   "no young scarp, so it fails the conjunction at emission",
            test_2_magnetic_edge=dict(
                proxy="RTP band 2 HGM maxima (sigma 2 px), top 50 % = strong magnetic edge",
                base_steps=diag_base, coarse_steps=diag_coarse,
                note="diagnostic only, not a gate: a HIGH fraction says the magnetic (intrusive) "
                     "competing explanation is live for that step population"),
            test_3="the coarse-scale maxima are the large-total-throw, deep steps: median inverted depth "
                   "of coarse vs base steps is reported below"),
        median_depth_m=dict(base=float(np.median(depth_small[base["steps"]])) if base["steps"].any() else None,
                            coarse=float(np.median(depth_small[coarse])) if coarse.any() else None),
        sources=dict(
            parker="Parker (1973) GJI 31:447-455, doi:10.1111/j.1365-246X.1973.tb02307.x",
            oldenburg="Oldenburg (1974) Geophysics 39(4):526-356, doi:10.1190/1.1440444",
            blakely_simpson="Blakely & Simpson (1986) Geophysics 51(7):1494-1498, doi:10.1190/1.1442197",
            blakely_jachens="Blakely & Jachens (1991) GSA Bulletin 103:795-803, doi:10.1130/0016-7606(1991)103<0795:RSOMRI>2.3.CO;2",
            gp1012="Saltus & Jachens (1995) USGS GP-1012, doi:10.3133/gp1012"),
        elapsed_s=round(time.time() - t0, 1)))


# --------------------------------------------------------------------------- #
RIBBON_HALF_PX = 2      # the lane: "gravity resolves such steps only to a few hundred metres
                        # at best, so emit multi-line ribbons rather than thin lines"


def _candidate_fields(g, valid):
    depth_full = np.load(CACHE / "depth_full.npy").astype(np.float64)
    corr_base = np.load(CACHE / "corr_base.npy")
    corr_coarse = np.load(CACHE / "corr_coarse.npy")
    corr_union = np.load(CACHE / "corr_union.npy")
    coarse_full = np.load(CACHE / "coarse_full.npy")
    throw_coarse_full = np.load(CACHE / "throw_coarse_full.npy").astype(np.float64)
    b19 = np.asarray(B.load_band(19), np.float64)
    ridge, slope = H.slope_ridges(b19, valid)
    basin = valid & (depth_full > H.BASIN_FLOOR_M)
    conceal = B.concealment_prior(depth_full, floor_m=H.BASIN_FLOOR_M, cap_m=1500.0)
    sl_rank = H.rank01(slope, ridge & valid)
    # the subtle-scarp preference measured in the H61-G screen: moderate slope ridges
    # carry the signal; weight = rank capped at the 90th percentile, x concealment
    w = np.minimum(sl_rank, 0.9) * (0.5 + 0.5 * conceal)
    fields = {}
    fields["X2 corridor x slope-ridge (basin interior)"] = np.where(ridge & corr_base & basin, w, 0.0)
    fields["X3 union-corridor x slope-ridge (basin interior)"] = np.where(ridge & corr_union & basin, w, 0.0)
    fields["X3c coarse-corridor x slope-ridge (basin interior)"] = np.where(ridge & corr_coarse & basin, w, 0.0)
    # X4 -- the lane's literal instruction: multi-line ribbons on the NEW (coarse,
    # disjoint) step lines.  5 px wide (2*2+1), the ~200 m placement uncertainty a
    # gravity step carries.  Weight form declared to be comparable with H61-G's X1a
    # (pure base-step ribbons scored 0.0230 there): (0.2 + throw) x (0.3 + conceal).
    rib = H.ribbon(coarse_full, RIBBON_HALF_PX) & basin
    fields["X4 coarse-step multi-line ribbons (basin interior)"] = \
        np.where(rib, (0.2 + throw_coarse_full) * (0.3 + conceal), 0.0)
    meta = dict(corr_base_fraction_of_valid=float((corr_base & valid).sum() / valid.sum()),
                corr_coarse_fraction_of_valid=float((corr_coarse & valid).sum() / valid.sum()),
                corr_union_fraction_of_valid=float((corr_union & valid).sum() / valid.sum()),
                basin_fraction_of_valid=float(basin.sum() / valid.sum()),
                n_slope_ridge_px=int((ridge & valid).sum()),
                ridge_in_union_basin=int((ridge & corr_union & basin).sum()),
                ridge_in_coarse_basin=int((ridge & corr_coarse & basin).sum()),
                ridge_in_base_basin=int((ridge & corr_base & basin).sum()),
                ribbon_coarse_px=int(rib.sum()))
    return fields, meta


def stage_holdout(_a) -> None:
    t0 = time.time()
    g, grav, valid = load_base()
    fields, meta = _candidate_fields(g, valid)
    log(f"corridors of valid area: base {meta['corr_base_fraction_of_valid']:.3f}  "
        f"coarse {meta['corr_coarse_fraction_of_valid']:.3f}  union {meta['corr_union_fraction_of_valid']:.3f}; "
        f"basin {meta['basin_fraction_of_valid']:.3f}; ridge px in base/coarse/union x basin: "
        f"{meta['ridge_in_base_basin']}/{meta['ridge_in_coarse_basin']}/{meta['ridge_in_union_basin']}")
    ctx = holdoutmod.build_holdout(g, hide_frac=0.20, seeds=SEEDS, modes=("all",))
    n_truth = sum(c.n_truth for c in ctx.cells)
    log(f"holdout: {len(ctx.cells)} cells, {n_truth} withheld truth px")
    assert n_truth == 22641, f"holdout construction drifted from H61-G (expected 22641 withheld px, got {n_truth})"

    # instrument check: the H61-G holdout file was built with these exact
    # parameters; re-score one registry file in place and compare its row.
    prev = json.loads(PREV_HOLDOUT.read_text())
    prev_rows = {r["name"]: r for r in prev["results"]}
    check_name = "REGISTRY gems25-dotted-h19-5-d2-8-20261002-e56ea318af89-zeros.tif"
    import rasterio
    with rasterio.open(_path_of(check_name)) as src:
        ref_arr = src.read(1)
    ref_mask = np.isfinite(ref_arr) & (ref_arr > 0.5)
    parts = []
    for cell in ctx.cells:
        part, _ = _score_crop(cell, ref_mask[cell.bbox])
        parts.append(part)
    pooled = _pool(parts)
    prev_val = prev_rows[check_name]["pooled_dti"]
    log(f"instrument check: {check_name} -> {pooled['pooled_dti']:.4f} (H61-G recorded {prev_val:.4f})")
    if abs(pooled["pooled_dti"] - prev_val) > 1e-6:
        raise SystemExit("INSTRUMENT DRIFT: holdout construction no longer reproduces H61-G; re-score the registry")

    seg, n_seg = segments(g.catalogue, max_len_px=12)[:2]
    depth_full = np.load(CACHE / "depth_full.npy").astype(np.float64)
    fp_px = float(g.footprint.sum())
    results = []
    # re-use the H61-G rows (deterministic construction, verified above)
    for r in prev["results"]:
        if r["kind"] in ("registry", "lines") and r["budget"] in (None, BUDGET):
            results.append(dict(name=r["name"] + "  [re-scored in H61-G pass, same deterministic holdout]",
                                kind=r["kind"], budget=r["budget"],
                                pooled_dti=r["pooled_dti"], ci95_bootstrap_cells=r["ci95_bootstrap_cells"],
                                n_emitted=r["n_emitted"], coverage=r["coverage"],
                                segments_withheld_total=r.get("segments_withheld_total"),
                                segments_recovered_total=r.get("segments_recovered_total"),
                                segments_withheld_basin_interior=r.get("segments_withheld_basin_interior"),
                                segments_recovered_basin_interior=r.get("segments_recovered_basin_interior"),
                                basin_recovery_rate=r.get("basin_recovery_rate"),
                                basin_recovery_ci95=r.get("basin_recovery_ci95")))

    def run(name, field=None, budget=BUDGET, random_lines=False, seed=100):
        parts, rec_rows = [], []
        for ci, cell in enumerate(ctx.cells):
            dom_px = float(cell.active.sum())
            b_cell = int(round(budget * dom_px / float(sum(c.active.sum() for c in ctx.cells if c.seed == cell.seed))))
            if random_lines:
                p_crop = H.random_lines(cell.active.shape, cell.active, b_cell, seed=seed + ci)
            else:
                p_crop = _per_cell_emit(field, cell, ctx.visible(cell.key), b_cell)
            part, dp = _score_crop(cell, p_crop)
            part["cell"] = cell.key
            parts.append(part)
            hid = ctx.hidden_by_cell[cell.key][cell.bbox]
            ids = np.unique(seg[cell.bbox][hid])
            ids = ids[ids > 0]
            if dp is None:
                dp = np.full(hid.shape, np.inf)
            near = dp <= 3.0
            segc = seg[cell.bbox]
            dep = depth_full[cell.bbox]
            for sid in ids:
                m = (segc == sid) & hid
                if not m.any():
                    continue
                rec_rows.append((int(m.sum()), float(np.median(dep[m])), float(near[m].mean())))
        pooled = _pool(parts)
        rec = np.array(rec_rows, np.float64) if rec_rows else np.zeros((0, 3))
        basin_mask = rec[:, 1] > 300.0 if rec.size else np.zeros(0, bool)
        n_b = int(basin_mask.sum()); k_b = int((rec[basin_mask, 2] >= 0.5).sum()) if n_b else 0
        n_all = int(rec.shape[0]); k_all = int((rec[:, 2] >= 0.5).sum()) if n_all else 0
        pooled["n_emitted_per_draw"] = pooled["n_emitted"] / len(SEEDS)
        row = dict(name=name, kind="candidate" if field is not None else "lines", budget=budget, **pooled,
                   ci95_bootstrap_cells=_boot_ci(parts),
                   per_cell_dti=[round(float(p["tp"] / (p["tp"] + ALPHA * p["fp"] + BETA * p["fn"] + EPS)), 5) for p in parts],
                   segments_withheld_total=n_all, segments_recovered_total=k_all,
                   segments_withheld_basin_interior=n_b, segments_recovered_basin_interior=k_b,
                   basin_recovery_rate=(k_b / n_b) if n_b else None,
                   basin_recovery_ci95=list(H.wilson(k_b, n_b)) if n_b else None)
        results.append(row)
        log(f"  {name:58s} n/draw={row['n_emitted_per_draw']:8.0f} HOLDOUT-DTI={row['pooled_dti']:.4f} "
            f"CI[{row['ci95_bootstrap_cells'][0]:.4f},{row['ci95_bootstrap_cells'][1]:.4f}] "
            f"cov={row['coverage']:.3f} basin-seg {k_b}/{n_b}")
        return row

    for name, field in fields.items():
        run(name, field=field)
    run("CONTROL random lines @ 40000", random_lines=True, seed=100)

    # leakage canary: per-feature AUC of withheld truth vs other active pixels
    rng = np.random.default_rng(3)
    b19 = np.asarray(B.load_band(19), np.float64)
    ridge, slope = H.slope_ridges(b19, valid)
    corr_union = np.load(CACHE / "corr_union.npy")
    corr_coarse = np.load(CACHE / "corr_coarse.npy")
    depth_full = np.load(CACHE / "depth_full.npy").astype(np.float64)
    feats = {"inverted depth": depth_full, "band 19 slope": slope, "band 13 gravity": grav,
             "union corridor indicator": corr_union.astype(np.float64),
             "coarse corridor indicator": corr_coarse.astype(np.float64),
             "slope ridge indicator": ridge.astype(np.float64)}
    canary = {}
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
    for fname, f in feats.items():
        pv = np.nan_to_num(f[py, px], nan=0.0); nv = np.nan_to_num(f[ny, nx], nan=0.0)
        canary[fname] = dict(auc=H.auc_rank(pv, nv), n_pos=int(pv.size), n_neg=int(nv.size))
        log(f"  canary {fname:28s} AUC={canary[fname]['auc']:.3f}")
    worst = max(canary.values(), key=lambda r: r["auc"])["auc"]

    cands = [r for r in results if r["kind"] == "candidate"]
    best = max(cands, key=lambda r: r["pooled_dti"])
    write_json("h61x_holdout.json", dict(
        evidence_class="HOLDOUT-DTI",
        evaluator=EVALUATOR, alpha=ALPHA, beta=BETA, kernel_m=300,
        n_withheld_truth_px=int(n_truth), n_cells=len(ctx.cells), prune_px=PRUNE_PX,
        budget=BUDGET, fields_meta=meta,
        instrument_check=dict(file=check_name, re_scored=pooled["pooled_dti"],
                              recorded_h61g=prev_val, difference=abs(pooled["pooled_dti"] - prev_val)),
        registry_rows_source=f"re-used from {PREV_HOLDOUT.name} (deterministic holdout, verified by the instrument check)",
        results=results,
        best_candidate=best["name"],
        leakage_canary=dict(threshold_auc=0.90, worst_auc=worst, passed=bool(worst < 0.90), per_feature=canary),
        note="HOLDOUT-DTI is an evaluator-version index on withheld catalogue traces; it is not a competition score. "
             "Registry rows are scored as-is: files pruned against the FULL catalogue lose the dots next to withheld "
             "segments, which biases them downward on this instrument.",
        elapsed_s=round(time.time() - t0, 1)))


def _path_of(registry_name: str) -> Path:
    fname = registry_name.replace("REGISTRY ", "", 1)
    for d in REGISTRY_DIRS:
        p = d / fname
        if p.exists():
            return p
    raise FileNotFoundError(fname)


# --------------------------------------------------------------------------- #
def stage_final(a) -> None:
    g, grav, valid = load_base()
    hold = json.loads((EVID / "h61x_holdout.json").read_text())
    inv = json.loads((EVID / "h61x_invert.json").read_text())
    cands = {r["name"]: r for r in hold["results"] if r["kind"] == "candidate"}
    ctrl = next(r for r in hold["results"] if r["kind"] == "lines" and "[re-scored" not in r["name"])
    reg_best = max((r for r in hold["results"] if r["kind"] == "registry"), key=lambda r: r["pooled_dti"])

    fields, meta = _candidate_fields(g, valid)
    far = ndi.distance_transform_edt(~g.catalogue) > PRUNE_PX
    allowed = valid & far & ~g.catalogue
    # the primary random control is THIS run's draw (per-cell seeds 100+ci); the
    # H61-G draw (single seed 100, re-used row) is kept as a secondary reference.
    ctrl_prev = next((r for r in hold["results"] if r["kind"] == "lines" and "[re-scored" in r["name"]), None)

    # candidate dots (same construction as the holdout, full catalogue prune)
    dots_by_name = {}
    for name, field in fields.items():
        dots_by_name[name] = H.dot_thin(field, allowed, BUDGET)

    # uniqueness pre-check (protocol rule 1: check BEFORE placement, on the
    # surface that will be shipped): fraction of my dots within 3 px of any
    # earlier raster's dots must stay <= 0.70 (dense refs use Jaccard <= 0.5).
    import rasterio
    prev_dots = {}
    for d in REGISTRY_DIRS:
        for p in sorted(d.glob("*.tif")):
            if "h61x" in p.name:
                continue
            try:
                with rasterio.open(p) as src:
                    if (src.height, src.width) != g.shape:
                        continue
                    prev_dots[p.name] = np.isfinite(src.read(1)) & (src.read(1) > 0.5)
            except Exception:  # noqa: BLE001
                pass
    uniq_pre = {}
    for name, dots in dots_by_name.items():
        rows = []
        for ref_name, od in prev_dots.items():
            near = ndi.distance_transform_edt(~od) <= 3.0
            frac = float(near[dots].mean()) if dots.any() else float("nan")
            inter = int((dots & od).sum()); union = int((dots | od).sum())
            jac = inter / max(union, 1)
            dense = int(od.sum()) > 5 * int(dots.sum())
            gate = jac if dense else frac
            rows.append(dict(file=ref_name, frac_within_3px=frac, jaccard=jac,
                             gate_rule="jaccard(dense)" if dense else "overlap3px",
                             gate_value=gate, gate_limit=0.5 if dense else 0.70))
        worst = max(rows, key=lambda r: r["gate_value"] / r["gate_limit"])
        uniq_pre[name] = dict(worst=worst, n_compared=len(rows),
                              unique=not any(r["gate_value"] > r["gate_limit"] for r in rows))
        log(f"  pre-unique {name:52s} worst gate={worst['gate_value']:.3f} ({worst['gate_rule']}) vs {worst['file'][:60]}")

    # selection (declared rule, recorded in the run card):
    #   primary eligibility = passes the uniqueness pre-check (protocol rule 1);
    #   among eligible, prefer candidates that beat the random-lines control,
    #   then highest pooled HOLDOUT-DTI, ties toward basin-interior segment recovery.
    #   If NO candidate beats random, the best unique candidate still ships --
    #   a unique, validated TIF is the lane's deliverable and the verdict is negative.
    # (X2 is the instrument reproduction and is the already-shipped H61-G file; it
    #  cannot be a new submission and is excluded from eligibility.)
    new_cands = {n: r for n, r in cands.items() if not n.startswith("X2 ")}
    unique_cands = {n: r for n, r in new_cands.items() if uniq_pre[n]["unique"]}
    beats = {n: r["pooled_dti"] > ctrl["pooled_dti"] for n, r in new_cands.items()}
    for name, row in new_cands.items():
        log(f"  selection {name:52s} beats_random={beats[name]} unique={uniq_pre[name]['unique']}")
    if not unique_cands:
        chosen = None
    else:
        def key(n):
            r = unique_cands[n]
            return (0 if beats[n] else 1, -r["pooled_dti"], -(r["segments_recovered_basin_interior"] or 0))
        ranked = sorted(unique_cands, key=key)
        chosen = ranked[0]
    log(f"selected: {chosen}")

    if chosen is None:
        raise SystemExit("no unique candidate to ship; redesign required (none of the new "
                         "constructions passed the protocol rule 1 uniqueness pre-check)")
    fname = chosen
    field = fields[fname]
    dots = dots_by_name[fname]
    values = dots.astype(np.float32)
    n_dots = int(dots.sum())
    dcat = ndi.distance_transform_edt(~g.catalogue)[dots]
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    digest = hashlib.sha256(values.tobytes()).hexdigest()[:12]
    short = {"X2 corridor x slope-ridge (basin interior)": "x2-base-corridor",
             "X3 union-corridor x slope-ridge (basin interior)": "x3-twoscale-corridor",
             "X3c coarse-corridor x slope-ridge (basin interior)": "x3c-coarse-corridor",
             "X4 coarse-step multi-line ribbons (basin interior)": "x4-coarse-step-ribbons"}[fname]
    name = f"gems61-h61x-{short}-{n_dots}dots-{stamp}-{digest}-zeros"
    note_by_cand = {
        "X3 union-corridor x slope-ridge (basin interior)":
            f"H61-X: two-scale GP-1012-calibrated gravity inversion -> base+coarse basement-step corridor x "
            f"in-corridor slope ridge; {n_dots} dots; UNSCORED",
        "X3c coarse-corridor x slope-ridge (basin interior)":
            f"H61-X: coarse (800 m) basement-step corridor from GP-1012-calibrated gravity inversion x "
            f"in-corridor slope ridge; {n_dots} dots; UNSCORED",
        "X4 coarse-step multi-line ribbons (basin interior)":
            f"H61-X: multi-line ribbons on coarse basement steps of the GP-1012-calibrated gravity inversion, "
            f"basin interior; {n_dots} dots; UNSCORED",
    }
    note = note_by_cand[fname]
    assert len(note) <= 140, len(note)
    OUT.mkdir(exist_ok=True)
    rec = submission_writer.write_submission(
        OUT / f"{name}.tif", values, sample=gridmod.DATA_DIR / "sample_submission.tif",
        footprint=g.footprint, note=note, name=name[:140], catalogue=g.catalogue,
        metadata=dict(method="H61-X", candidate=fname, budget=BUDGET, n_dots=n_dots,
                      holdout_dti=cands[fname]["pooled_dti"],
                      holdout_ci95=cands[fname]["ci95_bootstrap_cells"],
                      evaluator=EVALUATOR, prune_px=PRUNE_PX, corridor_px=CORRIDOR_PX,
                      coarse_smooth_px=COARSE_SMOOTH_PX,
                      no_prior_submission_raster_used=True))
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    for ext in (".tif", ".zip", ".json"):
        shutil.copy2(OUT / f"{name}{ext}", DOWNLOADS / f"{name}{ext}")
    rand = ctrl
    beats_random = cands[fname]["pooled_dti"] > rand["pooled_dti"]
    beats_group_best_holdout = cands[fname]["pooled_dti"] > reg_best["pooled_dti"]
    write_json("h61x_final.json", dict(
        evidence_class="MEASURED (file) + HOLDOUT-DTI (selection)",
        submission=name, note=note, note_chars=len(note), candidate=fname, budget=BUDGET,
        n_dots=n_dots, n_positive_px=n_dots,
        dots_distance_to_catalogue_px=dict(min=float(dcat.min()), median=float(np.median(dcat)),
                                           mean=float(dcat.mean()), frac_within_3px=float((dcat <= 3).mean())),
        tif=f"out/{name}.tif", zip=f"out/{name}.zip", receipt=f"out/{name}.json",
        download_tif=f"docs/downloads/{name}.tif", download_zip=f"docs/downloads/{name}.zip",
        sha256=rec["sha256"], bytes=rec["bytes"], zip_sha256=rec["zip_sha256"],
        validator=rec["validator"]["checks"], validator_all_passed=rec["validator"]["all_checks_passed"],
        uniqueness_pre_check=uniq_pre,
        selection_rule=("primary eligibility = uniqueness pre-check (protocol rule 1); among eligible prefer "
                        "beating the random-lines control, then highest pooled HOLDOUT-DTI, ties toward "
                        "basin-interior segment recovery; if no candidate beats random, the best unique "
                        "candidate ships with verdict=negative"),
        holdout=dict(dti=cands[fname]["pooled_dti"], ci95=cands[fname]["ci95_bootstrap_cells"],
                     random_lines=rand["pooled_dti"],
                     random_lines_h61g_draw=(ctrl_prev["pooled_dti"] if ctrl_prev else None),
                     beats_random_lines=beats_random,
                     registry_reference_best=dict(name=reg_best["name"], pooled_dti=reg_best["pooled_dti"]),
                     beats_registry_reference_on_holdout=beats_group_best_holdout,
                     n_withheld_truth_px=hold["n_withheld_truth_px"], evaluator=EVALUATOR,
                     basin_segments=f"{cands[fname]['segments_recovered_basin_interior']}/{cands[fname]['segments_withheld_basin_interior']} "
                                    f"vs random {rand['segments_recovered_basin_interior']}/{rand['segments_withheld_basin_interior']}"),
        selection=dict(
            eligible_unique=sorted(unique_cands),
            beats_random={n: bool(beats[n]) for n in sorted(new_cands)},
            rule=("primary eligibility = uniqueness pre-check (protocol rule 1); among eligible prefer "
                  "beating the random-lines control, then highest pooled HOLDOUT-DTI, ties toward "
                  "basin-interior segment recovery; if no candidate beats random, the best unique "
                  "candidate ships with verdict=negative")),
        slot_recommendation=("PROMOTE-ELIGIBLE: beats both controls and the registry reference on the holdout"
                             if (beats_random and beats_group_best_holdout) else
                             "DO NOT SPEND A SLOT: file is valid and unique, but the holdout does not put it above "
                             "the group's best-known file; keep as a negative/diagnostic result"),
        organizer_receipt=None))


# --------------------------------------------------------------------------- #
def stage_unique(_a) -> None:
    import rasterio
    from scipy.stats import spearmanr
    g = gridmod.load_grid()
    fin = json.loads((EVID / "h61x_final.json").read_text())
    with rasterio.open(ROOT / fin["tif"]) as src:
        mine = src.read(1)
    mine_dots = mine > 0.5
    rows = []
    seen = set()
    for d in REGISTRY_DIRS:
        for p in sorted(d.glob("*.tif")):
            if p.name in seen or p.name == Path(fin["tif"]).name:
                continue
            seen.add(p.name)
            try:
                with rasterio.open(p) as src:
                    if (src.height, src.width) != g.shape:
                        continue
                    other = src.read(1)
            except Exception as exc:  # noqa: BLE001
                rows.append(dict(file=p.name, error=str(exc)[:100])); continue
            o = np.where(np.isfinite(other), other, 0.0)
            a_ = mine[g.footprint]; b_ = o[g.footprint]
            rho = float(spearmanr(a_, b_).statistic) if a_.std() > 0 and b_.std() > 0 else float("nan")
            od = o > 0.5
            near = ndi.distance_transform_edt(~od) <= 3.0
            frac = float(near[mine_dots].mean()) if mine_dots.any() else float("nan")
            base = float(near[g.footprint].mean())
            inter = int((mine_dots & od).sum()); union = int((mine_dots | od).sum())
            jac = inter / max(union, 1)
            dense = int(od.sum()) > 5 * int(mine_dots.sum())
            gate_value = jac if dense else frac
            gate_rule = "Jaccard (reference is dense: >5x my support)" if dense else "one-sided 3 px overlap"
            gate_limit = 0.50 if dense else 0.70
            rows.append(dict(file=p.name, sha256=sha256(p), spearman_footprint=rho,
                             frac_my_dots_within_3px_of_theirs=frac, base_rate_within_3px=base,
                             jaccard=jac, their_positive_px=int(od.sum()),
                             overlap_gate_rule=gate_rule, overlap_gate_value=gate_value,
                             overlap_gate_limit=gate_limit,
                             overlap_gate_exceeded=bool(gate_value > gate_limit),
                             byte_identical=(sha256(p) == fin["sha256"])))
            log(f"  {p.name[:70]:70s} rho={rho:+.4f} overlap3px={frac:.3f} (base {base:.3f}) jaccard={jac:.4f}")
    ok = [r for r in rows if "spearman_footprint" in r]
    worst_rho = max(ok, key=lambda r: (r["spearman_footprint"] if r["spearman_footprint"] == r["spearman_footprint"] else -2))
    worst_ov = max(ok, key=lambda r: r["frac_my_dots_within_3px_of_theirs"])
    worst_gate = max(ok, key=lambda r: r["overlap_gate_value"] / r["overlap_gate_limit"])
    verdict = "UNIQUE" if (worst_rho["spearman_footprint"] <= 0.90 and
                           not any(r["overlap_gate_exceeded"] for r in ok) and
                           not any(r["byte_identical"] for r in ok)) else "DUPLICATE -- lane drift, do not submit"
    write_json("h61x_uniqueness.json", dict(
        evidence_class="MEASURED", my_file=fin["tif"], my_sha256=fin["sha256"], my_dots=int(mine_dots.sum()),
        n_registry_rasters_compared=len(ok), rho_limit=0.90, overlap_limit=0.70,
        worst_spearman=dict(file=worst_rho["file"], value=worst_rho["spearman_footprint"]),
        worst_overlap=dict(file=worst_ov["file"], value=worst_ov["frac_my_dots_within_3px_of_theirs"],
                           base_rate=worst_ov["base_rate_within_3px"], gate_rule=worst_ov["overlap_gate_rule"],
                           gate_value=worst_ov["overlap_gate_value"], gate_limit=worst_ov["overlap_gate_limit"]),
        worst_overlap_gate=dict(file=worst_gate["file"], rule=worst_gate["overlap_gate_rule"],
                                value=worst_gate["overlap_gate_value"], limit=worst_gate["overlap_gate_limit"]),
        byte_identical_to_any=[r["file"] for r in ok if r["byte_identical"]],
        verdict=verdict, rows=rows,
        scope="Every registry raster fetched by scripts/fetch_registry.sh plus the earlier rasters published "
              "in this repository. The full organizer-side registry is not reachable from this sandbox."))
    log(f"UNIQUENESS: {verdict}")


# --------------------------------------------------------------------------- #
def stage_card(_a) -> None:
    hold = json.loads((EVID / "h61x_holdout.json").read_text())
    fin = json.loads((EVID / "h61x_final.json").read_text())
    uni = json.loads((EVID / "h61x_uniqueness.json").read_text())
    inv = json.loads((EVID / "h61x_invert.json").read_text())
    chosen = next(r for r in hold["results"] if r["name"] == fin["candidate"])
    rand = next(r for r in hold["results"] if r["kind"] == "lines" and "[re-scored" not in r["name"])
    reg = fin["holdout"]["registry_reference_best"]
    promote = fin["slot_recommendation"].startswith("PROMOTE")
    card = dict(
        hypothesis="H61-X: a buried intrabasin fault is a BROAD step in the GP-1012-calibrated inverted basement "
                   "surface; the coarse-scale (800 m) horizontal-gradient maxima of that surface are the deep, "
                   "large-total-throw steps the catalogue misses under alluvial cover; the step fixes a +/-1 km "
                   "corridor and the in-corridor slope ridge of the detrended elevation fixes the trace to the "
                   "300 m kernel.",
        mechanism="Basement throw under alluvium -> isostatic-residual gradient maximum (Parker/Oldenburg first "
                  "iterate, Blakely-Simpson maxima, measured throw >= 80 m) at two scales; the coarse scale keeps "
                  "only the broad steps (deep, large throw) -> growth of the same fault through the fill -> subtle "
                  "young scarp = slope-ridge of band 19 inside the corridor.",
        named_non_fault_mimic="Density contrasts inside the basement (igneous contacts, pluton margins, buried "
                              "volcanic centres) give the same gravity step with no scarp: test 1 = the "
                              "corridor x scarp conjunction at emission; test 2 = measured magnetic-edge "
                              f"diagnostic (base steps on strong mag edge "
                              f"{inv['competing_explanation']['test_2_magnetic_edge']['base_steps']['on_strong_mag_edge']:.3f} vs coarse "
                              f"{inv['competing_explanation']['test_2_magnetic_edge']['coarse_steps']['on_strong_mag_edge']:.3f}); "
                              "alluvial-fan toes and terrace risers give slope ridges with no gravity step.",
        holdout_dti=dict(value=chosen["pooled_dti"], ci95=chosen["ci95_bootstrap_cells"], evaluator=hold["evaluator"],
                         n_withheld_positive_px=hold["n_withheld_truth_px"],
                         n_dots_per_draw=chosen["n_emitted"] // len(SEEDS),
                         random_lines_same_budget=rand["pooled_dti"],
                         basin_interior_segments=f"{chosen['segments_recovered_basin_interior']}/{chosen['segments_withheld_basin_interior']} recovered "
                                                 f"vs {rand['segments_recovered_basin_interior']}/{rand['segments_withheld_basin_interior']} by random lines",
                         registry_reference_best=reg,
                         instrument_check=hold["instrument_check"]),
        correlation_overlap_vs_registry=dict(worst_spearman=uni["worst_spearman"], worst_overlap=uni["worst_overlap"],
                                             n_compared=uni["n_registry_rasters_compared"], verdict=uni["verdict"]),
        raster_sha256=fin["sha256"],
        validator_output=dict(checks=fin["validator"], all_passed=fin["validator_all_passed"]),
        submission_name=fin["submission"], note=fin["note"], note_chars=fin["note_chars"],
        leakage_canary=hold["leakage_canary"]["passed"], leakage_worst_auc=hold["leakage_canary"]["worst_auc"],
        inversion=dict(z0_m=inv["inversion"]["z0_m"], delta_rho=inv["inversion"]["delta_rho"],
                       regional_sigma_km=inv["inversion"]["regional_sigma_km"],
                       fraction_deeper_than_1km=inv["depth_stats"]["fraction_gt_1km"],
                       cross_check_r_vs_band15=inv["cross_check_vs_supplied_band15"]["pearson_r"],
                       base_steps=inv["steps"]["base"]["n_throw_filtered"],
                       coarse_steps_disjoint=inv["steps"]["coarse"]["n_disjoint_from_base"]),
        verdict="promote" if promote else "negative",
        verdict_reason=fin["slot_recommendation"],
        candidate_selection=dict(rule=fin["selection"]["rule"],
                                 eligible_unique=fin["selection"]["eligible_unique"],
                                 beats_random=fin["selection"]["beats_random"],
                                 shipped=fin["candidate"], shipped_budget=BUDGET),
        organizer_confirmed_score=None,
        experiments_run=3, budget_experiments=3)
    write_json("h61x_run_card.json", card)
    log(json.dumps(card, indent=1, default=_jsonable)[:3000])


STAGES = dict(invert=stage_invert, holdout=stage_holdout, final=stage_final,
              unique=stage_unique, card=stage_card)


def main() -> None:
    raise SystemExit("RETIRED: Retired historical runner: it read organizer band 15. Use scripts/run_h61u.py; band 15 is prohibited.")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=list(STAGES) + ["all"])
    a = ap.parse_args()
    order = list(STAGES) if a.stage == "all" else [a.stage]
    for s in order:
        log(f"==== {s} ====")
        STAGES[s](a)


if __name__ == "__main__":
    main()
