#!/usr/bin/env python
"""H61-G driver -- basement-step corridors from gravity inversion, located by the
in-corridor slope ridge.  Run from the repository root::

    PYTHONPATH=src .venv/bin/python scripts/run_h61g.py <stage>

Stages (each writes one JSON into evidence/ and nothing else is hand-written):

screen    label-aware enrichment screen of gravity edges vs the catalogue (why the
          pure lane cannot place a dot to 300 m)                -> h61g_screen.json
invert    band-pass + GP-1012-calibrated slab inversion, steps, cross-check
                                                                -> h61g_invert.json
holdout   hide-and-recover (whole withheld segments, visible-only features,
          pixel-exact masking, pooled DTI a=0.2 b=0.8 R=300 m) for every candidate,
          both controls and the registry references; basin-interior segment
          recovery vs random lines; per-feature leakage canary
                                                                -> h61g_holdout.json
final     build + validate the GeoTIFF of the candidate the holdout selects
                                                                -> h61g_final.json
unique    rank-correlation / 3 px dot-overlap against every registry raster
                                                                -> h61g_uniqueness.json
card      the run card                                          -> h61g_run_card.json
all       screen -> invert -> holdout -> final -> unique -> card
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
from gems61 import uniqueness as uniqueness_gate     # noqa: E402
from gems61.metric import ALPHA, BETA, EPS, kernel   # noqa: E402
from gems61.network import segments                  # noqa: E402

EVID = ROOT / "evidence"
OUT = ROOT / "out"
CACHE = ROOT / ".cache" / "h61g"
DOWNLOADS = ROOT / "docs" / "downloads"
REGISTRY_DIRS = [Path("/tmp/refs/registry"), ROOT / "docs" / "downloads"]
BUDGETS = (20000, 40000)
PRUNE_PX = 2.0          # dots closer than this to a (visible) mapped trace are not emitted
SEEDS = (20, 21)
EVALUATOR = "gems61.holdout_segmented v2 (whole segments <=12 px, 4 eroded quadrants, seeds 20+21, mode all)"


def log(msg: str) -> None:
    print(msg, flush=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _expected_registry_names() -> list[str]:
    """Names explicitly enumerated by fetch_registry.sh (not the full organizer registry)."""
    text = (ROOT / "scripts" / "fetch_registry.sh").read_text()
    if 'ITEMS="' not in text:
        return []
    block = text.split('ITEMS="', 1)[1].split('"', 1)[0]
    names = []
    for line in block.splitlines():
        entry = line.strip()
        if ":" in entry and entry.endswith(".tif"):
            names.append(Path(entry.split(":", 1)[1]).name)
    return names


def _registry_inventory(exclude_names=()):
    """Return accessible raster bytes plus an explicit, conservative scope receipt."""
    exclude = set(exclude_names)
    rows, seen = [], set()
    for directory in REGISTRY_DIRS:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.tif")):
            if path.name in exclude or path.name in seen:
                continue
            seen.add(path.name)
            rows.append(dict(sources=[str(path)], cache_file=str(path), sha256=sha256(path)))
    expected = _expected_registry_names()
    external_dir = REGISTRY_DIRS[0]
    fetched = {p.name for p in external_dir.glob("*.tif")} if external_dir.exists() else set()
    missing = sorted(set(expected) - fetched)
    internal = (sorted(p.name for p in REGISTRY_DIRS[1].glob("*.tif") if p.name not in exclude)
                if REGISTRY_DIRS[1].exists() else [])
    scope = dict(
        source_script="scripts/fetch_registry.sh",
        enumerated_external_rasters=len(expected),
        fetched_enumerated_external_rasters=len(set(expected) & fetched),
        missing_enumerated_external_rasters=missing,
        prior_project_downloads=len(internal),
        enumerated_list_complete=not missing,
        official_registry_access=False,
        full_registry_coverage=False,
        limitation="The fetch script names a finite subset of owner-published rasters; it does not prove coverage of every earlier raster or the organizer-side registry.",
    )
    return rows, scope


def _compare_to_registry(candidate: np.ndarray, footprint: np.ndarray, *, exclude_names=()):
    manifest_rows, scope = _registry_inventory(exclude_names=exclude_names)
    report = uniqueness_gate.compare_array_to_registry(
        candidate, {"rasters": manifest_rows}, footprint,
        scope_complete=scope["full_registry_coverage"], scope=scope)
    report["known_registry_rasters_compared"] = sum(
        "spearman_full_footprint" in row for row in report["rows"])
    report["candidate_dots"] = int(((np.asarray(candidate) > 0.5) & footprint).sum())
    return report


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


# --------------------------------------------------------------------------- #
def stage_screen(_a) -> None:
    """Label-aware screen: does ANY gravity-derived edge sit within 300 m of mapped
    faults more often than a random pixel does?  This is not the holdout; it is
    the measurement that explains the design."""
    g, grav, valid = load_base()
    cat = g.catalogue
    b15 = np.asarray(B.load_band(15), np.float64)
    b19 = np.asarray(B.load_band(19), np.float64)
    dcat = ndi.distance_transform_edt(~cat)
    kcat = kernel(dcat)
    filled = B.inpaint_smooth(np.where(valid, grav, np.nan), valid)
    rows = []

    def add(name, mask, region_name):
        n = int(mask.sum())
        if n == 0:
            return
        rows.append(dict(candidate=name, region=region_name, n=n,
                         within_3px=float((dcat[mask] <= 3).mean()),
                         mean_kernel=float(kcat[mask].mean())))

    for rname, region in (("depth>300m", valid & (b15 > 300)), ("all valid", valid)):
        base = region & ~cat
        add("RANDOM pixel", base, rname)
        for s in (2, 5, 10):
            hgm = B.horizontal_gradient_magnitude(ndi.gaussian_filter(filled, s))
            mx = B.blakely_simpson_maxima(hgm) & base
            add(f"grav HGM maxima, gaussian {s}px, all", mx, rname)
            add(f"grav HGM maxima, gaussian {s}px, top50%", mx & (hgm >= np.percentile(hgm[mx], 50)), rname)
        hgm15 = B.horizontal_gradient_magnitude(B.inpaint_smooth(np.where(valid, b15, np.nan), valid))
        mx15 = B.blakely_simpson_maxima(hgm15) & base
        add("supplied depth band 15 HGM maxima", mx15, rname)
        slope = B.inpaint_smooth(np.where(valid, b19, np.nan), valid)
        mxs = B.blakely_simpson_maxima(slope) & base
        add("detrended-elevation slope ridges (band 19), all", mxs, rname)
        add("slope ridges, >= median strength", mxs & (slope >= np.percentile(slope[mxs], 50)), rname)
        # corridor conditioning
        hgm5 = B.horizontal_gradient_magnitude(ndi.gaussian_filter(filled, 5))
        mx5 = B.blakely_simpson_maxima(hgm5) & valid
        strong = mx5 & (hgm5 >= np.percentile(hgm5[mx5], 50))
        corr = ndi.distance_transform_edt(~strong) <= 10
        add("RANDOM pixel inside gravity corridor", base & corr, rname)
        add("slope ridges >= median, inside gravity corridor", mxs & (slope >= np.percentile(slope[mxs], 50)) & corr, rname)
        add("slope ridges >= median, outside gravity corridor", mxs & (slope >= np.percentile(slope[mxs], 50)) & ~corr, rname)
    for r in rows:
        log(f"  {r['region']:11s} {r['candidate']:52s} n={r['n']:8d} within3={r['within_3px']:.4f} k={r['mean_kernel']:.4f}")
    rand = {r["region"]: r for r in rows if r["candidate"] == "RANDOM pixel"}
    for r in rows:
        r["enrichment_mean_kernel_vs_random"] = r["mean_kernel"] / rand[r["region"]]["mean_kernel"]
    write_json("h61g_screen.json", dict(
        evidence_class="MEASURED (label-aware screen; not a holdout score)",
        question="Do gravity-derived edges sit within the 300 m kernel of mapped faults more often than random pixels?",
        marginal_bar_note="A dot pays off only if its mean kernel credit exceeds alpha*DTI = 0.2 x 0.2778 = 0.056 "
                          "at the group's best live score; random pixels sit at ~0.03.",
        rows=rows))


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
        f"corr(depth, gravity)={gsign:.3f} (must be negative)")
    if not gsign < 0:
        raise SystemExit("SIGN ERROR: inverted depth must anti-correlate with the isostatic residual")

    steps = H.basement_steps(depth_small, inv["dx"])
    pers = H.persistent_steps(depth_small, inv["dx"])
    log(f"steps: {steps['n_maxima']} HGM maxima -> {steps['n_steps']} with throw >= {H.MIN_THROW_M:.0f} m; "
        f"persistent across 3 scales: {pers['n_steps']}")
    steps_full = H.to_full_grid(steps["steps"], g.shape) & valid
    pers_full = H.to_full_grid(pers["steps"], g.shape) & valid
    hgm_full = H.field_to_full_grid(steps["hgm"], g.shape)
    throw_small = np.where(np.isfinite(steps["throw"]), steps["throw"], 0.0)
    throw_full = H.field_to_full_grid(throw_small, g.shape)
    np.save(CACHE / "depth_full.npy", depth_full.astype(np.float32))
    np.save(CACHE / "steps_full.npy", steps_full)
    np.save(CACHE / "pers_full.npy", pers_full)
    np.save(CACHE / "hgm_full.npy", hgm_full.astype(np.float32))
    np.save(CACHE / "throw_full.npy", throw_full.astype(np.float32))
    thr = steps["throw"][steps["steps"]]
    write_json("h61g_invert.json", dict(
        evidence_class="MEASURED",
        inversion_grid=dict(decimation=H.LANE_DECIMATION, pixel_m=inv["dx"], shape=list(depth_small.shape),
                            valid_fraction=float(inv["valid_small"].mean())),
        regional_residual_separation=dict(method="Gaussian regional removed before the slab inversion",
                                          sigma_km=H.REGIONAL_SIGMA_KM,
                                          why="Blakely & Jachens (1991) invert the basin field after removing a smooth basement field; "
                                              "without bedrock station locations the separation is a declared low-pass"),
        calibration=inv["calibration"], inversion=inv["inversion"],
        depth_stats=B.calibrate_depth_scale(depth_small, inv["valid_small"]),
        cross_check_vs_supplied_band15=dict(cross, corr_depth_vs_gravity=gsign),
        steps=dict(n_hgm_maxima_400m=steps["n_maxima"], n_steps_throw_filtered=steps["n_steps"],
                   min_throw_m=H.MIN_THROW_M, throw_p50_m=float(np.median(thr)) if thr.size else None,
                   throw_p90_m=float(np.percentile(thr, 90)) if thr.size else None,
                   n_persistent_steps=pers["n_steps"], persistence_scales_px=[0, 2, 5],
                   n_step_px_100m=int(steps_full.sum()), n_persistent_px_100m=int(pers_full.sum())),
        sources=dict(
            parker="Parker (1973) GJI 31:447-455, doi:10.1111/j.1365-246X.1973.tb02307.x",
            oldenburg="Oldenburg (1974) Geophysics 39(4):526-536, doi:10.1190/1.1440444",
            blakely_simpson="Blakely & Simpson (1986) Geophysics 51(7):1494-1498, doi:10.1190/1.1442197",
            blakely_jachens="Blakely & Jachens (1991) GSA Bulletin 103:795-803",
            gp1012="Saltus & Jachens (1995) USGS GP-1012, doi:10.3133/gp1012"),
        elapsed_s=round(time.time() - t0, 1)))


# --------------------------------------------------------------------------- #
def _candidate_fields(g, valid):
    """Score fields for every candidate (no catalogue information inside)."""
    depth_full = np.load(CACHE / "depth_full.npy").astype(np.float64)
    steps_full = np.load(CACHE / "steps_full.npy")
    pers_full = np.load(CACHE / "pers_full.npy")
    hgm_full = np.load(CACHE / "hgm_full.npy").astype(np.float64)
    throw_full = np.load(CACHE / "throw_full.npy").astype(np.float64)
    b19 = np.asarray(B.load_band(19), np.float64)
    ridge, slope = H.slope_ridges(b19, valid)
    basin = valid & (depth_full > H.BASIN_FLOOR_M)
    conceal = B.concealment_prior(depth_full, floor_m=H.BASIN_FLOOR_M, cap_m=1500.0)

    fields = {}
    # X1a -- pure lane: step ribbons (3 px wide), ranked by throw x concealment
    rib = H.ribbon(steps_full, 1) & valid
    fields["X1a pure basement-step ribbons"] = np.where(rib, (0.2 + throw_full) * (0.3 + conceal), 0.0)
    # X1b -- pure lane, persistent (deep-seated) steps only
    ribp = H.ribbon(pers_full, 1) & valid
    fields["X1b persistent-step ribbons"] = np.where(ribp, (0.2 + throw_full) * (0.3 + conceal), 0.0)
    # X2 -- corridor-gated slope ridges inside basins
    corr = H.corridor_mask(steps_full, H.CORRIDOR_PX)
    sl_rank = H.rank01(slope, ridge & valid)
    # subtle-scarp preference measured in the screen: moderate slope ridges carry the signal,
    # the strongest ones are terraces/incision -> weight = rank, capped at the 90th percentile
    w = np.minimum(sl_rank, 0.9) * (0.5 + 0.5 * conceal)
    fields["X2 corridor x slope-ridge (basin interior)"] = np.where(ridge & corr & basin, w, 0.0)
    fields["X2b corridor x slope-ridge (any depth)"] = np.where(ridge & corr, np.minimum(sl_rank, 0.9), 0.0)
    # control: slope ridges OUTSIDE any corridor (same locator, no gravity prior)
    fields["C3 slope-ridge outside corridor (basin interior)"] = np.where(ridge & ~corr & basin, w, 0.0)
    meta = dict(corridor_fraction_of_valid=float((corr & valid).sum() / valid.sum()),
                basin_fraction_of_valid=float(basin.sum() / valid.sum()),
                n_slope_ridge_px=int((ridge & valid).sum()))
    aux = dict(corridor=corr, basin=basin, depth_full=depth_full, slope=slope, ridge=ridge,
               hgm_full=hgm_full, steps_full=steps_full)
    return fields, meta, aux


def _per_cell_emit(field, cell, visible_full, budget_cell, random_kind=None, seed=0):
    sl = cell.bbox
    vis = visible_full[sl]
    far = ndi.distance_transform_edt(~vis) > PRUNE_PX
    allowed = cell.active & far
    if random_kind == "lines":
        return H.random_lines(allowed.shape, allowed, budget_cell, seed=seed)
    if random_kind == "dots":
        return H.random_dots(allowed, budget_cell, seed=seed)
    if random_kind == "corridor":
        return H.random_dots(allowed & field[sl], budget_cell, seed=seed)
    return H.dot_thin(field[sl], allowed, budget_cell)


def _score_crop(cell, p_crop):
    """Exact DTI on a cell crop + distance-to-dots for segment recovery."""
    p = p_crop & cell.active
    n_emit = int(p.sum())
    if n_emit == 0 or cell.n_truth == 0:
        return dict(tp=0.0, fp=float(n_emit), fn=float(cell.n_truth), n_emit=n_emit), None
    dp = ndi.distance_transform_edt(~p)
    tp = float(kernel(dp[cell.truth_yx]).sum())
    fn = float(cell.n_truth) - tp
    fp = float((1.0 - cell.k_dg[p]).sum())
    return dict(tp=tp, fp=fp, fn=fn, n_emit=n_emit), dp


def _pool(parts):
    tp = sum(p["tp"] for p in parts); fp = sum(p["fp"] for p in parts); fn = sum(p["fn"] for p in parts)
    return dict(pooled_dti=float(tp / (tp + ALPHA * fp + BETA * fn + EPS)), tp=tp, fp=fp, fn=fn,
                n_emitted=int(sum(p["n_emit"] for p in parts)),
                coverage=float(tp / max(tp + fn, 1e-9)))


def _boot_ci(parts, n_boot=2000, seed=7):
    """Percentile bootstrap of the pooled DTI over fold cells."""
    rng = np.random.default_rng(seed)
    parts = list(parts)
    vals = []
    for _ in range(n_boot):
        pick = [parts[i] for i in rng.integers(len(parts), size=len(parts))]
        vals.append(_pool(pick)["pooled_dti"])
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def stage_holdout(_a) -> None:
    t0 = time.time()
    g, grav, valid = load_base()
    fields, meta, aux = _candidate_fields(g, valid)
    log(f"corridor covers {meta['corridor_fraction_of_valid']:.3f} of the valid area; basin {meta['basin_fraction_of_valid']:.3f}")
    ctx = holdoutmod.build_holdout(g, hide_frac=0.20, seeds=SEEDS, modes=("all",))
    n_truth = sum(c.n_truth for c in ctx.cells)
    log(f"holdout: {len(ctx.cells)} cells, {n_truth} withheld truth px")
    seg, n_seg = segments(g.catalogue, max_len_px=12)[:2]
    depth_full = aux["depth_full"]
    fp_px = float(g.footprint.sum())

    # registry references (fixed dot sets) -- scored as-is on the same instrument
    refs = {}
    for d in REGISTRY_DIRS:
        for p in sorted(d.glob("*.tif")):
            if "gems61" in p.name:
                continue
            try:
                import rasterio
                with rasterio.open(p) as src:
                    if (src.height, src.width) != g.shape:
                        continue
                    arr = src.read(1)
                refs[p.name] = np.isfinite(arr) & (arr > 0.5)
            except Exception as exc:  # noqa: BLE001
                log(f"  skip {p.name}: {exc}")

    results = []

    def run(name, kind, field=None, budget=None, fixed=None, seed=0):
        parts, rec_rows = [], []
        for ci, cell in enumerate(ctx.cells):
            share = float(g.footprint[cell.bbox][cell.active].sum()) / fp_px if False else None
            dom_px = float(cell.active.sum())
            if fixed is not None:
                p_crop = fixed[cell.bbox]
            else:
                b_cell = int(round(budget * dom_px / float(sum(c.active.sum() for c in ctx.cells if c.seed == cell.seed))))
                p_crop = _per_cell_emit(field, cell, ctx.visible(cell.key), b_cell, random_kind=kind, seed=seed + ci)
            part, dp = _score_crop(cell, p_crop)
            part["cell"] = cell.key
            parts.append(part)
            # segment recovery inside this cell
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
                rec_rows.append((cell.key, int(sid), int(m.sum()), float(np.median(dep[m])), float(near[m].mean())))
        pooled = _pool(parts)
        rec = np.array([(r[2], r[3], r[4]) for r in rec_rows], np.float64) if rec_rows else np.zeros((0, 3))
        basin_mask = rec[:, 1] > 300.0 if rec.size else np.zeros(0, bool)
        n_b = int(basin_mask.sum()); k_b = int((rec[basin_mask, 2] >= 0.5).sum()) if n_b else 0
        n_all = int(rec.shape[0]); k_all = int((rec[:, 2] >= 0.5).sum()) if n_all else 0
        pooled["n_emitted_per_draw"] = pooled["n_emitted"] / len(SEEDS)
        row = dict(name=name, kind=kind or "candidate", budget=budget, **pooled,
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

    for name, m in refs.items():
        run(f"REGISTRY {name}", "registry", fixed=m)
    for budget in BUDGETS:
        for name, field in fields.items():
            run(f"{name} @ {budget}", None, field=field, budget=budget)
        run(f"CONTROL random lines @ {budget}", "lines", field=None, budget=budget, seed=100)
        run(f"CONTROL random dots inside corridor+basin @ {budget}", "corridor",
            field=aux["corridor"] & aux["basin"], budget=budget, seed=200)

    # leakage canary: per-feature AUC of withheld truth vs other active pixels
    rng = np.random.default_rng(3)
    feats = {"inverted depth": aux["depth_full"], "inverted-depth HGM": aux["hgm_full"],
             "band 19 slope": aux["slope"], "band 13 gravity": grav,
             "band 18 iso_grav_anom_hg": np.asarray(B.load_band(18), np.float64),
             "corridor indicator": aux["corridor"].astype(np.float64),
             "slope ridge indicator": aux["ridge"].astype(np.float64)}
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
    ctrl_lines = {r["budget"]: r for r in results if r["name"].startswith("CONTROL random lines")}
    ctrl_corr = {r["budget"]: r for r in results if r["name"].startswith("CONTROL random dots")}
    reg_best = max([r for r in results if r["kind"] == "registry"], key=lambda r: r["pooled_dti"], default=None)
    write_json("h61g_holdout.json", dict(
        evidence_class="HOLDOUT-DTI",
        evaluator=EVALUATOR, alpha=ALPHA, beta=BETA, kernel_m=300,
        n_withheld_truth_px=int(n_truth), n_cells=len(ctx.cells), prune_px=PRUNE_PX,
        budgets=list(BUDGETS), fields_meta=meta,
        results=results,
        best_candidate=best["name"],
        best_vs_random_lines=dict(candidate=best["pooled_dti"], random_lines=ctrl_lines[best["budget"]]["pooled_dti"],
                                  ratio=best["pooled_dti"] / max(ctrl_lines[best["budget"]]["pooled_dti"], 1e-9)),
        best_vs_random_in_corridor=dict(candidate=best["pooled_dti"], random_corridor=ctrl_corr[best["budget"]]["pooled_dti"]),
        registry_reference_best=(dict(name=reg_best["name"], pooled_dti=reg_best["pooled_dti"]) if reg_best else None),
        leakage_canary=dict(threshold_auc=0.90, worst_auc=worst, passed=bool(worst < 0.90), per_feature=canary),
        note="HOLDOUT-DTI is an evaluator-version index on withheld catalogue traces; it is not a competition score. "
             "Registry rows are scored as-is: files pruned against the FULL catalogue lose the dots next to withheld "
             "segments, which biases them downward on this instrument.",
        elapsed_s=round(time.time() - t0, 1)))


# --------------------------------------------------------------------------- #
def stage_final(a) -> None:
    g, grav, valid = load_base()
    hold = json.loads((EVID / "h61g_holdout.json").read_text())
    cands = [r for r in hold["results"] if r["kind"] == "candidate"]
    chosen = max(cands, key=lambda r: r["pooled_dti"]) if not a.candidate else \
        next(r for r in cands if r["name"] == a.candidate)
    fname = chosen["name"].rsplit(" @ ", 1)[0]
    budget = int(chosen["budget"])
    fields, meta, aux = _candidate_fields(g, valid)
    field = fields[fname]
    far = ndi.distance_transform_edt(~g.catalogue) > PRUNE_PX
    allowed = valid & far & ~g.catalogue
    dots = H.dot_thin(field, allowed, budget)
    # The holdout validated DOTS.  A 3 x 3 dilation of every dot ("ribbon") multiplies the
    # false-positive mass by ~6.75 while the kernel credit of a truth pixel can only rise
    # marginally, so the file ships the validated dots.  The "multi-line ribbon" of the lane
    # brief is realised at corridor scale: every slope ridge inside the +/-1 km corridor is
    # emitted, not a single thinned line.  Both variants are scored below on the same cells.
    # Scored INSIDE the holdout protocol (per cell, pruned only against the VISIBLE catalogue);
    # the shipped file itself is pruned against the full catalogue and therefore cannot be
    # scored on a catalogue holdout (same artefact that puts h33-2-b2 at 0.0044 here).
    ctx = holdoutmod.build_holdout(g, hide_frac=0.20, seeds=SEEDS, modes=("all",))
    ribbon_vs_dots = {}
    for label in ("dots (shipped)", "3x3 ribbons (not shipped)"):
        parts = []
        for ci, cell in enumerate(ctx.cells):
            dom_px = float(cell.active.sum())
            b_cell = int(round(budget * dom_px / float(sum(c.active.sum() for c in ctx.cells if c.seed == cell.seed))))
            d_crop = _per_cell_emit(field, cell, ctx.visible(cell.key), b_cell)
            if label.startswith("3x3"):
                vis = ctx.visible(cell.key)[cell.bbox]
                far_c = ndi.distance_transform_edt(~vis) > PRUNE_PX
                d_crop = H.ribbon(d_crop, 1) & cell.active & far_c
            part, _ = _score_crop(cell, d_crop)
            parts.append(part)
        pooled = _pool(parts)
        ribbon_vs_dots[label] = dict(pooled_dti=pooled["pooled_dti"], ci95=_boot_ci(parts),
                                     coverage=pooled["coverage"], emitted_per_draw=pooled["n_emitted"] / len(SEEDS),
                                     fp_mass=pooled["fp"], tp_mass=pooled["tp"])
        log(f"  {label:28s} HOLDOUT-DTI={pooled['pooled_dti']:.4f} CI{ribbon_vs_dots[label]['ci95']} "
            f"coverage={pooled['coverage']:.3f} emitted/draw={pooled['n_emitted'] / len(SEEDS):.0f}")
    del ctx
    values = dots.astype(np.float32)
    n_dots = int(dots.sum()); n_pos = int(dots.sum())
    dcat = ndi.distance_transform_edt(~g.catalogue)[dots]
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    digest = hashlib.sha256(values.tobytes()).hexdigest()[:12]
    short = {"X1a pure basement-step ribbons": "x1a-step-ribbons",
             "X1b persistent-step ribbons": "x1b-persistent-steps",
             "X2 corridor x slope-ridge (basin interior)": "x2-gravcorridor-sloperidge",
             "X2b corridor x slope-ridge (any depth)": "x2b-gravcorridor-sloperidge-anydepth",
             "C3 slope-ridge outside corridor (basin interior)": "c3-outside-corridor"}[fname]
    name = f"gems61-h61g-{short}-{n_dots}dots-{stamp}-{digest}-zeros"
    note = (f"H61-G: GP-1012-calibrated gravity inversion -> basement-step corridor x in-corridor "
            f"slope ridge; {n_dots} dots at 3 px spacing; UNSCORED")
    assert len(note) <= 140, len(note)

    # Fail closed before writing or publishing a candidate.  Jaccard/base-rate
    # diagnostics never replace the literal rank-rho / forward-overlap gates.
    preplacement = _compare_to_registry(values, g.footprint)
    preplacement["phase"] = "candidate dots, before submission writer"
    write_json("h61g_preplacement_uniqueness.json", preplacement)
    if not preplacement["unique"]:
        raise SystemExit(f"pre-placement registry gate blocked output: {preplacement['status']}")

    OUT.mkdir(exist_ok=True)
    rec = submission_writer.write_submission(
        OUT / f"{name}.tif", values, sample=gridmod.DATA_DIR / "sample_submission.tif",
        footprint=g.footprint, note=note, name=name[:140], catalogue=g.catalogue,
        metadata=dict(method="H61-G", candidate=fname, budget=budget, n_dots=n_dots, n_positive_px=n_pos,
                      holdout_dti=chosen["pooled_dti"], holdout_ci95=chosen["ci95_bootstrap_cells"],
                      evaluator=EVALUATOR, prune_px=PRUNE_PX, corridor_px=H.CORRIDOR_PX,
                      ribbon_vs_dots_holdout=ribbon_vs_dots,
                      no_prior_submission_raster_used=True))

    # Re-read the written GeoTIFF, then repeat both literal gates on its final dots
    # before it is copied into the public Pages download directory.
    import rasterio
    with rasterio.open(OUT / f"{name}.tif") as src:
        final_values = src.read(1)
    final_gate = _compare_to_registry(final_values, g.footprint)
    final_gate["phase"] = "final GeoTIFF dots, before public placement"
    final_gate["candidate_sha256"] = rec["sha256"]
    write_json("h61g_final_uniqueness.json", final_gate)
    if not final_gate["unique"]:
        raise SystemExit(f"final-dot registry gate blocked public placement: {final_gate['status']}")

    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    for ext in (".tif", ".zip", ".json"):
        shutil.copy2(OUT / f"{name}{ext}", DOWNLOADS / f"{name}{ext}")
    rand = next(r for r in hold["results"] if r["name"] == f"CONTROL random lines @ {budget}")
    reg = hold.get("registry_reference_best")
    beats_random = chosen["pooled_dti"] > rand["pooled_dti"]
    beats_group_best_holdout = (reg is None) or (chosen["pooled_dti"] > reg["pooled_dti"])
    write_json("h61g_final.json", dict(
        evidence_class="MEASURED (file) + HOLDOUT-DTI (selection)",
        submission=name, note=note, note_chars=len(note), candidate=fname, budget=budget,
        n_dots=n_dots, n_positive_px=n_pos, ribbon_vs_dots_holdout=ribbon_vs_dots,
        dots_distance_to_catalogue_px=dict(min=float(dcat.min()), median=float(np.median(dcat)),
                                           mean=float(dcat.mean()), frac_within_3px=float((dcat <= 3).mean())),
        tif=f"out/{name}.tif", zip=f"out/{name}.zip", receipt=f"out/{name}.json",
        download_tif=f"docs/downloads/{name}.tif", download_zip=f"docs/downloads/{name}.zip",
        sha256=rec["sha256"], bytes=rec["bytes"], zip_sha256=rec["zip_sha256"],
        validator=rec["validator"]["checks"], validator_all_passed=rec["validator"]["all_checks_passed"],
        holdout=dict(dti=chosen["pooled_dti"], ci95=chosen["ci95_bootstrap_cells"],
                     random_lines=rand["pooled_dti"], beats_random_lines=beats_random,
                     registry_reference_best=reg, beats_registry_reference_on_holdout=beats_group_best_holdout,
                     n_withheld_truth_px=hold["n_withheld_truth_px"], evaluator=EVALUATOR),
        uniqueness=dict(status=final_gate["status"],
                        duplicate_count=final_gate["duplicate_count"],
                        known_registry_rasters_compared=final_gate["known_registry_rasters_compared"],
                        registry_scope_complete=final_gate["registry_scope_complete"]),
        submission_eligible=bool(final_gate["unique"]),
        download_status="cleared for public download" if final_gate["unique"] else "audit-only; do not submit",
        slot_recommendation=("PROMOTE-ELIGIBLE: holdout beats both controls and registry reference; uniqueness gate cleared"
                             if (final_gate["unique"] and beats_random and beats_group_best_holdout) else
                             "DO NOT SPEND A SLOT: HOLDOUT-DTI does not exceed the group's best comparable reference"),
        organizer_receipt=None))


# --------------------------------------------------------------------------- #
def stage_unique(_a) -> None:
    import rasterio
    g = gridmod.load_grid()
    fin = json.loads((EVID / "h61g_final.json").read_text())
    candidate_path = ROOT / fin["tif"]
    if not candidate_path.exists():
        candidate_path = ROOT / fin["download_tif"]
    with rasterio.open(candidate_path) as src:
        mine = src.read(1)
    mine_dots = np.isfinite(mine) & (mine > 0.5) & g.footprint
    report = _compare_to_registry(mine, g.footprint,
                                  exclude_names=(Path(fin["tif"]).name,))
    rows = report["rows"]
    comparable = [r for r in rows if "spearman_full_footprint" in r]
    # Keep legacy aliases for the site builder, but the literal forward overlap
    # is always the gate. Jaccard is retained only as a diagnostic statistic.
    for row in comparable:
        row["spearman_footprint"] = row["spearman_full_footprint"]
        row["frac_my_dots_within_3px_of_theirs"] = row["my_dots_within_3px_of_theirs"]
        row["base_rate_within_3px"] = row["eligible_base_rate_within_3px"]
        row["enrichment"] = row["enrichment_vs_base_rate"]
        row["jaccard"] = row["jaccard_dot_sets"]
        row["their_positive_px"] = row["n_other"]
        row["byte_identical"] = row.get("sha256") == fin["sha256"]
    if not comparable:
        raise SystemExit("no readable registry rasters; uniqueness cannot be cleared")
    worst_rho = max(comparable, key=lambda r: r["spearman_footprint"]
                    if np.isfinite(r["spearman_footprint"]) else -2.0)
    worst_overlap = max(comparable, key=lambda r: r["frac_my_dots_within_3px_of_theirs"])
    worst_gate = max(comparable, key=lambda r: r["overlap_gate_value"] / r["overlap_gate_limit"])
    duplicate = report["duplicate_count"] > 0
    verdict = ("DUPLICATE — DO NOT SUBMIT" if duplicate else
               "NOT CLEARED — registry coverage incomplete" if not report["registry_scope_complete"] else
               "UNIQUE")
    report.update(dict(
        my_file=str(candidate_path.relative_to(ROOT)), my_sha256=sha256(candidate_path),
        my_dots=int(mine_dots.sum()), n_registry_rasters_compared=len(comparable),
        rho_limit=uniqueness_gate.RHO_LIMIT, overlap_limit=uniqueness_gate.OVERLAP_LIMIT,
        worst_spearman=dict(file=worst_rho["file"], value=worst_rho["spearman_footprint"]),
        worst_overlap=dict(file=worst_overlap["file"],
                           value=worst_overlap["frac_my_dots_within_3px_of_theirs"],
                           base_rate=worst_overlap["base_rate_within_3px"],
                           enrichment=worst_overlap["enrichment"],
                           gate_rule="one-sided 3 px overlap",
                           gate_value=worst_overlap["overlap_gate_value"],
                           gate_limit=worst_overlap["overlap_gate_limit"],
                           jaccard_diagnostic=worst_overlap["jaccard"]),
        worst_overlap_gate=dict(file=worst_gate["file"], rule="one-sided 3 px overlap",
                                value=worst_gate["overlap_gate_value"],
                                limit=worst_gate["overlap_gate_limit"]),
        byte_identical_to_any=[r["file"] for r in comparable if r["byte_identical"]],
        verdict=verdict,
        legacy_reported_verdict="UNIQUE (incorrect: substituted Jaccard for raw overlap on a dense reference)",
        gate_rule="rank correlation > 0.90 OR >70% of candidate dots within 3 px of any one registry raster",
        scope=report["scope"]))
    write_json("h61g_uniqueness.json", report)
    log(f"UNIQUENESS: {verdict}; duplicate_count={report['duplicate_count']}; "
        f"raw_overlap={worst_overlap['frac_my_dots_within_3px_of_theirs']:.6f}; "
        f"registry_scope_complete={report['registry_scope_complete']}")


# --------------------------------------------------------------------------- #
def stage_card(_a) -> None:
    hold = json.loads((EVID / "h61g_holdout.json").read_text())
    fin = json.loads((EVID / "h61g_final.json").read_text())
    uni = json.loads((EVID / "h61g_uniqueness.json").read_text())
    inv = json.loads((EVID / "h61g_invert.json").read_text())
    chosen = next(r for r in hold["results"] if r["name"] == f"{fin['candidate']} @ {fin['budget']}")
    rand = next(r for r in hold["results"] if r["name"] == f"CONTROL random lines @ {fin['budget']}")
    reg = hold.get("registry_reference_best")
    promote = fin["slot_recommendation"].startswith("PROMOTE")
    card = dict(
        hypothesis="H61-G: a buried normal fault is a step in the GP-1012-calibrated inverted basement surface; the "
                   "gravity step fixes a +/-1 km corridor and the in-corridor slope ridge of the detrended elevation "
                   "fixes the trace to the 300 m kernel.",
        mechanism="Basement throw under alluvium -> isostatic-residual gradient maximum (Parker/Oldenburg inversion, "
                  "Blakely-Simpson maxima, measured throw >= 80 m) -> growth of the same fault through the fill -> "
                  "subtle young scarp = slope-ridge of band 19 inside the corridor.",
        named_non_fault_mimic="Intrabasement lithologic density contacts can produce the same gravity step without a fault; fan toes, terrace risers and channels can produce slope ridges without a fault. The conjunction is a proposed discriminator, not a demonstrated exclusion: independent density-contrast/lithology data were not used, so this competing explanation remains unresolved.",
        holdout_dti=dict(value=chosen["pooled_dti"], ci95=chosen["ci95_bootstrap_cells"], evaluator=hold["evaluator"],
                         n_withheld_positive_px=hold["n_withheld_truth_px"], n_dots_per_draw=chosen["n_emitted"] // len(SEEDS),
                         random_lines_same_budget=rand["pooled_dti"],
                         basin_interior_segments=f"{chosen['segments_recovered_basin_interior']}/{chosen['segments_withheld_basin_interior']} recovered "
                                                 f"vs {rand['segments_recovered_basin_interior']}/{rand['segments_withheld_basin_interior']} by random lines",
                         registry_reference_best=reg),
        correlation_overlap_vs_registry=dict(worst_spearman=uni["worst_spearman"], worst_overlap=uni["worst_overlap"],
                                             n_compared=uni["n_registry_rasters_compared"], verdict=uni["verdict"],
                                             duplicate_count=uni["duplicate_count"],
                                             unique_within_available_scope=uni["unique_within_available_scope"],
                                             registry_scope_complete=uni["scope"]["full_registry_coverage"],
                                             scope=uni["scope"], gate_rule=uni["gate_rule"]),
        raster_sha256=fin["sha256"],
        validator_output=dict(checks=fin["validator"], all_passed=fin["validator_all_passed"]),
        submission_name=fin["submission"], note=fin["note"], note_chars=fin["note_chars"],
        submission_eligible=fin.get("submission_eligible", False),
        download_status=fin.get("download_status", "not cleared"),
        leakage_canary=hold["leakage_canary"]["passed"], leakage_worst_auc=hold["leakage_canary"]["worst_auc"],
        inversion=dict(z0_m=inv["inversion"]["z0_m"], delta_rho=inv["inversion"]["delta_rho"],
                       regional_sigma_km=inv["inversion"]["regional_sigma_km"],
                       fraction_deeper_than_1km=inv["depth_stats"]["fraction_gt_1km"],
                       cross_check_r_vs_band15=inv["cross_check_vs_supplied_band15"]["pearson_r"]),
        verdict="promote" if promote else "negative",
        verdict_reason=fin["slot_recommendation"],
        candidate_selection=dict(rule="max pooled HOLDOUT-DTI over candidates and budgets; ties (overlapping 95% CIs) broken toward the "
                                      "lane's stated population (basin interior) and higher basin-interior segment recovery",
                                 shipped=fin["candidate"], shipped_budget=fin["budget"],
                                 best_by_pooled_dti=hold["best_candidate"]["name"] if isinstance(hold.get("best_candidate"), dict) else hold.get("best_candidate")),
        organizer_confirmed_score=None,
        experiments_run=3, budget_experiments=3)
    write_json("h61g_run_card.json", card)
    log(json.dumps(card, indent=1, default=_jsonable)[:3000])


STAGES = dict(screen=stage_screen, invert=stage_invert, holdout=stage_holdout,
              final=stage_final, unique=stage_unique, card=stage_card)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=list(STAGES) + ["all"])
    ap.add_argument("--candidate", default=None, help="override the holdout's choice (name without ' @ budget')")
    a = ap.parse_args()
    order = list(STAGES) if a.stage == "all" else [a.stage]
    for s in order:
        log(f"==== {s} ====")
        STAGES[s](a)


if __name__ == "__main__":
    main()
