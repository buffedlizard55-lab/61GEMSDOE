#!/usr/bin/env python3
"""H61-M driver -- basement-step corridor x learned off-catalogue fault habitat.

    PYTHONPATH=src .venv/bin/python scripts/run_h61m.py <stage>

Stages (each writes one JSON into evidence/):
  features  build the 200 m + 400 m inversions and the 28-channel habitat stack
  holdout   per-cell out-of-fold habitat model; budget / prune / spacing sweeps;
            random-line and random-dot controls; leakage canary
  final     build + validate the GeoTIFF of the holdout's choice
  unique    rank-correlation / 3 px overlap against every registry raster
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

from gems61 import buried as B                       # noqa: E402
from gems61 import grid as gridmod                   # noqa: E402
from gems61 import h61m as M                         # noqa: E402
from gems61 import holdout_segmented as holdoutmod   # noqa: E402
from gems61 import submission_writer                 # noqa: E402
from gems61.metric import ALPHA, BETA, EPS, kernel   # noqa: E402

import run_h61g as R                                 # noqa: E402  (shared tools, not forks)

EVID = ROOT / "evidence"
OUT = ROOT / "out"
CACHE = ROOT / ".cache" / "h61m"
DOWNLOADS = ROOT / "docs" / "downloads"
SEEDS = R.SEEDS
EVALUATOR = R.EVALUATOR
BUDGETS = (20000, 30000, 40000, 60000, 80000)
PRUNES = (2.0, 3.0, 4.0, 6.0)
TILES = (2, 3, 4)
SHORT = {}


def log(msg: str) -> None:
    print(msg, flush=True)


def load_base():
    g = gridmod.load_grid()
    grav = np.asarray(B.load_band(13), np.float64)
    valid = g.footprint & np.isfinite(grav)
    return g, grav, valid


# --------------------------------------------------------------------------- #
def stage_features(_a) -> None:
    t0 = time.time()
    g, grav, valid = load_base()
    CACHE.mkdir(parents=True, exist_ok=True)
    names, stack, meta, aux = M.build_feature_stack(grav, valid, g.shape,
                                                    out_path=CACHE / "stack.npy",
                                                    cache_dir=CACHE)
    for k in ("depth_fine", "hgm", "throw", "corridor", "basin", "euler"):
        np.save(CACHE / f"{k}.npy", aux[k])
    np.save(CACHE / "steps.npy", aux["steps"])
    np.save(CACHE / "valid.npy", valid)
    for tag, inv in (("fine", aux["inv_fine"]), ("coarse", aux["inv_coarse"])):
        np.save(CACHE / f"depth_small_{tag}.npy",
                np.where(np.isfinite(inv["depth_small"]), inv["depth_small"], np.nan))
    # the 200 m / 400 m inversion grids are block-means, so a 100 m cell that
    # touches the survey boundary can be NaN on the coarse grid while finite on
    # the fine one; every correlation below is therefore taken on the common
    # finite support and the erosion is reported rather than hidden.
    both = valid & np.isfinite(aux["depth_fine"]) & np.isfinite(aux["depth_coarse"])
    r = float(np.corrcoef(aux["depth_fine"][both], aux["depth_coarse"][both])[0, 1])
    b15 = np.asarray(B.load_band(15), np.float64)
    cross = B.compare_to_published_depth(b15, aux["depth_fine"], both)
    gsign = float(np.corrcoef(aux["depth_fine"][both], grav[both])[0, 1])
    eroded = int((valid & ~np.isfinite(aux["depth_fine"])).sum())
    log(f"inversion: fine dx={aux['inv_fine']['dx']:.0f} m coarse dx={aux['inv_coarse']['dx']:.0f} m; "
        f"corr(fine,coarse)={r:.3f}; corr(fine,band15)={cross['pearson_r']:.3f}; "
        f"corr(depth,grav)={gsign:.3f}; common finite {both.sum()} of {valid.sum()}")
    if not gsign < 0:
        raise SystemExit("SIGN ERROR: inverted depth must anti-correlate with the isostatic residual")
    R.write_json("h61m_features.json", dict(
        evidence_class="MEASURED",
        inversion_grids=dict(coarse_px=meta["decimations"]["coarse"],
                             fine_px=meta["decimations"]["fine"]),
        calibration_coarse=meta["calibration_coarse"], calibration_fine=meta["calibration_fine"],
        inversion_coarse=meta["inversion_coarse"], inversion_fine=meta["inversion_fine"],
        depth_stats_coarse=meta["depth_stats_coarse"], depth_stats_fine=meta["depth_stats_fine"],
        steps_fine=meta["steps_fine"],
        rank_correlation_fine_vs_coarse=r,
        cross_check_vs_supplied_band15=dict(cross, corr_depth_vs_gravity=gsign),
        support=dict(valid_px=int(valid.sum()),
                     fine_grid_finite_px=int(np.isfinite(aux["depth_fine"]).sum()),
                     coarse_grid_finite_px=int(np.isfinite(aux["depth_coarse"]).sum()),
                     common_finite_px=int(both.sum()),
                     footprint_cells_lost_at_200m=int((valid & ~np.isfinite(aux["depth_fine"])).sum()),
                     footprint_cells_lost_at_400m=int((valid & ~np.isfinite(aux["depth_coarse"])).sum())),
        corridor_px=meta["corridor_px"], basin_floor_m=meta["basin_floor_m"],
        corridor_fraction_of_valid=meta["corridor_fraction_of_valid"],
        basin_fraction_of_valid=meta["basin_fraction_of_valid"],
        n_features=meta["n_features"], feature_names=meta["feature_names"],
        euler_note=meta["euler_note"],
        sources=dict(
            parker="Parker (1973) GJI 31:447-455, doi:10.1111/j.1365-246X.1973.tb02307.x",
            oldenburg="Oldenburg (1974) Geophysics 39(4):526-536, doi:10.1190/1.1440444",
            blakely_simpson="Blakely & Simpson (1986) Geophysics 51(7):1494-1498, doi:10.1190/1.1442197",
            blakely_jachens="Blakely & Jachens (1991) GSA Bulletin 103:795-803",
            gp1012="Saltus & Jachens (1995) USGS GP-1012, doi:10.3133/gp1012",
            euler="Reid et al. (1990) Geophysics 55(1):80-91, doi:10.1190/1.1442789"),
        elapsed_s=round(time.time() - t0, 1)))


# --------------------------------------------------------------------------- #
def _load_stack():
    return np.load(CACHE / "stack.npy", mmap_mode="r")


def _cell_visible(ctx, cell):
    return ctx.visible(cell.key)


def stage_holdout(_a) -> None:
    t0 = time.time()
    g, grav, valid = load_base()
    stack = _load_stack()
    names = json.loads((EVID / "h61m_features.json").read_text())["feature_names"]
    corridor = np.load(CACHE / "corridor.npy")
    basin = np.load(CACHE / "basin.npy")
    depth_fine = np.load(CACHE / "depth_fine.npy")
    hgm = np.load(CACHE / "hgm.npy")
    throw = np.load(CACHE / "throw.npy")
    euler = np.load(CACHE / "euler.npy")

    ctx = holdoutmod.build_holdout(g, hide_frac=0.20, seeds=SEEDS, modes=("all",))
    n_truth = sum(c.n_truth for c in ctx.cells)
    log(f"holdout: {len(ctx.cells)} cells, {n_truth} withheld truth px")
    stack_arr = np.asarray(stack)

    dom_total = float(sum(c.active.sum() for c in ctx.cells if c.seed == ctx.cells[0].seed))
    results = []

    def run(name, kind, emit, budget=None, prune=None, tile=None):
        """emit(cell, allowed, b_cell) -> bool crop"""
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
                                     float(np.median(dep[m])), float(near[m].mean())))
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
                   basin_recovery_ci95=list(M.wilson(k_b, n_b)) if n_b else None)
        results.append(row)
        log(f"  {name:64s} n/draw={row['n_emitted_per_draw']:7.0f} DTI={row['pooled_dti']:.4f} "
            f"CI[{row['ci95_bootstrap_cells'][0]:.4f},{row['ci95_bootstrap_cells'][1]:.4f}] "
            f"cov={row['coverage']:.3f} basin {k_b}/{n_b}")
        return row

    # ---- per-cell out-of-fold habitat models -------------------------------- #
    oof = {}
    receipts = []
    for cell in ctx.cells:
        vis = _cell_visible(ctx, cell)
        model, rec = M.train_habitat(stack_arr, valid, vis, names, seed=cell.seed)
        p = M.predict_habitat(model, stack_arr, valid)
        del model
        oof[cell.key] = p.astype(np.float32)
        del p
        rec["cell"] = cell.key
        receipts.append(rec)
        top = sorted(rec["coefficients"].items(), key=lambda kv: -abs(kv[1]))[:8]
        log(f"  model {cell.key}: n_pos={rec['n_pos']} train_auc={rec['train_auc']:.3f} "
            f"top: " + ", ".join(f"{k}{v:+.2f}" for k, v in top))

    # average coefficient across cells for the run card
    coef_mean = {n: float(np.mean([r["coefficients"][n] for r in receipts])) for n in names}

    from gems61.network import segments
    seg_cache = segments(g.catalogue, max_len_px=12)[0]

    def emit_model(cell, allowed, b_cell, ci, tile=M.TILE_PX, gate=None):
        p = oof[cell.key][cell.bbox]
        if gate is not None:
            p = np.where(gate[cell.bbox], p, -np.inf)
        return M.dot_thin(p, allowed, b_cell, tile_px=tile)

    # ---- controls ----------------------------------------------------------- #
    for budget in BUDGETS:
        run(f"CONTROL random lines @ {budget}", "lines",
            lambda c, a, b, ci, **k: R.H.random_lines(a.shape, a, b, seed=100 + ci),
            budget=budget, prune=R.PRUNE_PX, tile=M.TILE_PX)
    run("CONTROL random dots anywhere @ 40000", "dots",
        lambda c, a, b, ci, **k: R.H.random_dots(a, b, seed=300 + ci),
        budget=40000, prune=R.PRUNE_PX, tile=M.TILE_PX)

    # ---- candidates --------------------------------------------------------- #
    best = None
    for prune in PRUNES:
        for budget in BUDGETS:
            row = run(f"M1 habitat x corridor (prune {prune:.0f}px) @ {budget}", "candidate",
                      lambda c, a, b, ci, pr=prune: emit_model(c, a, b, ci, gate=corridor),
                      budget=budget, prune=prune, tile=M.TILE_PX)
            if best is None or row["pooled_dti"] > best["pooled_dti"]:
                best = row
    # locator ablations at the best prune/budget
    bp, bb = best["prune_px"], best["budget"]
    for label, gate in (("no corridor gate", None), ("basin only", basin)):
        run(f"M2 habitat {label} @ {bb}", "candidate",
            lambda c, a, b, ci, gt=gate: emit_model(c, a, b, ci, gate=gt),
            budget=bb, prune=bp, tile=M.TILE_PX)
    for tile in TILES:
        run(f"M3 habitat x corridor, tile {tile}px @ {bb}", "candidate",
            lambda c, a, b, ci, t=tile: emit_model(c, a, b, ci, tile=t, gate=corridor),
            budget=bb, prune=bp, tile=tile)
    # ribbon variant (the lane's literal "multi-line ribbon") for the record
    run(f"M4 habitat x corridor, 3x3 ribbon @ {bb}", "candidate",
        lambda c, a, b, ci: M.ribbon(emit_model(c, a, b, ci, gate=corridor), 1) & a,
        budget=bb, prune=bp, tile=M.TILE_PX)

    # ---- leakage canary ----------------------------------------------------- #
    rng = np.random.default_rng(3)
    mean_oof = np.zeros(g.shape, np.float64)
    for c in ctx.cells:
        mean_oof += oof[c.key]
    mean_oof /= len(ctx.cells)
    feats = {"habitat OOF probability": mean_oof,
             "inverted depth (200 m)": depth_fine, "inverted-depth HGM": hgm,
             "step throw": throw, "corridor indicator": corridor.astype(np.float64),
             "Euler source depth": euler, "band 13 gravity": grav,
             "band 19 slope": np.asarray(B.load_band(19), np.float64)}
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
        canary[fname] = dict(auc=M.auc_rank(pv, nv), n_pos=int(pv.size), n_neg=int(nv.size))
        log(f"  canary {fname:28s} AUC={canary[fname]['auc']:.3f}")
    worst = max(canary.values(), key=lambda r: r["auc"])["auc"]

    cands = [r for r in results if r["kind"] == "candidate"]
    best = max(cands, key=lambda r: r["pooled_dti"])
    R.write_json("h61m_holdout.json", dict(
        evidence_class="HOLDOUT-DTI",
        evaluator=EVALUATOR, alpha=ALPHA, beta=BETA, kernel_m=300,
        n_withheld_truth_px=int(n_truth), n_cells=len(ctx.cells),
        budgets=list(BUDGETS), prunes_px=list(PRUNES), tiles_px=list(TILES),
        feature_names=names, mean_coefficients=coef_mean, model_receipts=receipts,
        results=results, best_candidate=best["name"],
        leakage_canary=dict(threshold_auc=0.90, worst_auc=worst, passed=bool(worst < 0.90),
                            per_feature=canary),
        note="HOLDOUT-DTI is an evaluator-version index on withheld catalogue traces; it is not a "
             "competition score. Every candidate is trained only on the VISIBLE catalogue of its own "
             "cell and pruned only against that visible catalogue, per parallel-run protocol rule 2.",
        elapsed_s=round(time.time() - t0, 1)))


# --------------------------------------------------------------------------- #
def stage_final(a) -> None:
    g, grav, valid = load_base()
    hold = json.loads((EVID / "h61m_holdout.json").read_text())
    cands = [r for r in hold["results"] if r["kind"] == "candidate"]
    chosen = max(cands, key=lambda r: r["pooled_dti"]) if not a.candidate else \
        next(r for r in cands if r["name"] == a.candidate)
    # CLI overrides: the holdout instrument and the live metric disagree about
    # the catalogue prune (IR-61-PRUNE-01) and about the dot budget, so the
    # shipped configuration is stated explicitly rather than inherited.
    if a.prune is not None:
        chosen = dict(chosen, prune_px=a.prune)
    if a.budget is not None:
        chosen = dict(chosen, budget=a.budget)
    if a.tile is not None:
        chosen = dict(chosen, tile_px=a.tile)
    log(f"chosen: {chosen['name']}  DTI={chosen['pooled_dti']:.4f} "
        f"(prune {chosen['prune_px']} px, budget {chosen['budget']}, tile {chosen['tile_px']} px)")

    stack = _load_stack()
    names = hold["feature_names"]
    corridor = np.load(CACHE / "corridor.npy")
    basin = np.load(CACHE / "basin.npy")
    prune = float(chosen["prune_px"]); budget = int(chosen["budget"]); tile = int(chosen["tile_px"])
    gate = corridor if "corridor" in chosen["name"] else (basin if "basin" in chosen["name"] else None)

    model, rec = M.train_habitat(np.asarray(stack), valid, g.catalogue, names, seed=20)
    p = M.predict_habitat(model, np.asarray(stack), valid)
    far = ndi.distance_transform_edt(~g.catalogue) > prune
    allowed = valid & far & ~g.catalogue
    if gate is not None:
        allowed = allowed & gate
    dots = M.dot_thin(p, allowed, budget, tile_px=tile)
    if "ribbon" in chosen["name"]:
        dots = M.ribbon(dots, 1) & allowed

    values = dots.astype(np.float32)
    n_dots = int(dots.sum())
    dcat = ndi.distance_transform_edt(~g.catalogue)[dots]
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    digest = hashlib.sha256(values.tobytes()).hexdigest()[:12]
    name = f"gems61-h61m-invfeat-habitat-{n_dots}dots-{stamp}-{digest}-zeros"
    note = (f"H61-M: 200m Parker-Oldenburg basement inversion as features in an out-of-fold logistic "
            f"habitat model; {n_dots} dots at {tile}px, {prune:.0f}px prune; UNSCORED")
    assert len(note) <= 140, len(note)
    OUT.mkdir(exist_ok=True)
    receipt = submission_writer.write_submission(
        OUT / f"{name}.tif", values, sample=gridmod.DATA_DIR / "sample_submission.tif",
        footprint=g.footprint, note=note, name=name[:140], catalogue=g.catalogue,
        metadata=dict(method="H61-M", candidate=chosen["name"], budget=budget,
                      prune_px=prune, tile_px=tile, n_dots=n_dots,
                      holdout_dti=chosen["pooled_dti"], holdout_ci95=chosen["ci95_bootstrap_cells"],
                      evaluator=EVALUATOR, mean_coefficients=hold["mean_coefficients"],
                      no_prior_submission_raster_used=True))
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    for ext in (".tif", ".zip", ".json"):
        shutil.copy2(OUT / f"{name}{ext}", DOWNLOADS / f"{name}{ext}")
    rand = next(r for r in hold["results"] if r["name"].startswith("CONTROL random lines")
                and r["budget"] == budget)
    R.write_json("h61m_final.json", dict(
        evidence_class="MEASURED (file) + HOLDOUT-DTI (selection)",
        submission=name, note=note, note_chars=len(note), candidate=chosen["name"],
        budget=budget, prune_px=prune, tile_px=tile, n_dots=n_dots,
        dots_distance_to_catalogue_px=dict(min=float(dcat.min()), median=float(np.median(dcat)),
                                           mean=float(dcat.mean()),
                                           frac_within_3px=float((dcat <= 3).mean())),
        tif=f"out/{name}.tif", zip=f"out/{name}.zip", receipt=f"out/{name}.json",
        download_tif=f"docs/downloads/{name}.tif", download_zip=f"docs/downloads/{name}.zip",
        sha256=receipt["sha256"], bytes=receipt["bytes"], zip_sha256=receipt["zip_sha256"],
        validator=receipt["validator"]["checks"],
        validator_all_passed=receipt["validator"]["all_checks_passed"],
        holdout=dict(dti=chosen["pooled_dti"], ci95=chosen["ci95_bootstrap_cells"],
                     random_lines=rand["pooled_dti"],
                     beats_random_lines=bool(chosen["pooled_dti"] > rand["pooled_dti"]),
                     n_withheld_truth_px=hold["n_withheld_truth_px"], evaluator=EVALUATOR),
        organizer_receipt=None))


# --------------------------------------------------------------------------- #
def stage_unique(_a) -> None:
    import rasterio
    from scipy.stats import spearmanr
    g = gridmod.load_grid()
    fin = json.loads((EVID / "h61m_final.json").read_text())
    with rasterio.open(ROOT / fin["tif"]) as src:
        mine = src.read(1)
    mine_dots = mine > 0.5
    rows, seen = [], set()
    for d in R.REGISTRY_DIRS:
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
            rows.append(dict(file=p.name, sha256=R.sha256(p), spearman_footprint=rho,
                             frac_my_dots_within_3px_of_theirs=frac, base_rate_within_3px=base,
                             enrichment=(frac / base) if base > 0 else None, jaccard=jac,
                             their_positive_px=int(od.sum()), overlap_gate_rule=gate_rule,
                             overlap_gate_value=gate_value, overlap_gate_limit=gate_limit,
                             overlap_gate_exceeded=bool(gate_value > gate_limit),
                             byte_identical=(R.sha256(p) == fin["sha256"])))
            log(f"  {p.name[:70]:70s} rho={rho:+.4f} overlap3px={frac:.3f} (base {base:.3f}) "
                f"jaccard={jac:.4f} gate={gate_rule.split(' ')[0]}")
    ok = [r for r in rows if "spearman_footprint" in r]
    worst_rho = max(ok, key=lambda r: (r["spearman_footprint"] if r["spearman_footprint"] == r["spearman_footprint"] else -2))
    worst_ov = max(ok, key=lambda r: r["frac_my_dots_within_3px_of_theirs"])
    worst_gate = max(ok, key=lambda r: r["overlap_gate_value"] / r["overlap_gate_limit"])
    verdict = "UNIQUE" if (worst_rho["spearman_footprint"] <= 0.90 and
                           not any(r["overlap_gate_exceeded"] for r in ok) and
                           not any(r["byte_identical"] for r in ok)) else \
        "DUPLICATE -- lane drift, do not submit"
    R.write_json("h61m_uniqueness.json", dict(
        evidence_class="MEASURED", my_file=fin["tif"], my_sha256=fin["sha256"],
        my_dots=int(mine_dots.sum()), n_registry_rasters_compared=len(ok),
        rho_limit=0.90, overlap_limit=0.70,
        worst_spearman=dict(file=worst_rho["file"], value=worst_rho["spearman_footprint"]),
        worst_overlap=dict(file=worst_ov["file"], value=worst_ov["frac_my_dots_within_3px_of_theirs"],
                           base_rate=worst_ov["base_rate_within_3px"],
                           gate_rule=worst_ov["overlap_gate_rule"],
                           gate_value=worst_ov["overlap_gate_value"],
                           gate_limit=worst_ov["overlap_gate_limit"]),
        worst_overlap_gate=dict(file=worst_gate["file"], rule=worst_gate["overlap_gate_rule"],
                                value=worst_gate["overlap_gate_value"],
                                limit=worst_gate["overlap_gate_limit"]),
        byte_identical_to_any=[r["file"] for r in ok if r["byte_identical"]],
        verdict=verdict, rows=rows,
        scope="Every registry raster reachable from the group's public GitHub repositories "
              "(scripts/fetch_registry.sh) plus the earlier rasters published in this repository."))
    log(f"UNIQUENESS: {verdict}")


# --------------------------------------------------------------------------- #
def stage_card(_a) -> None:
    hold = json.loads((EVID / "h61m_holdout.json").read_text())
    fin = json.loads((EVID / "h61m_final.json").read_text())
    uni = json.loads((EVID / "h61m_uniqueness.json").read_text())
    feat = json.loads((EVID / "h61m_features.json").read_text())
    chosen = next(r for r in hold["results"] if r["name"] == fin["candidate"])
    card = dict(
        hypothesis="H61-M: a buried normal fault is a step in the GP-1012-calibrated inverted basement "
                   "surface; the step fixes a +/-1 km corridor, and inside that corridor an out-of-fold "
                   "habitat model (25 catalogue-independent features, trained on the visible faults) "
                   "locates the trace to the 300 m kernel.",
        mechanism="Basement throw under alluvium -> isostatic-residual gradient maximum (200 m "
                  "Parker/Oldenburg slab inversion, Blakely-Simpson maxima, measured throw >= 80 m) -> "
                  "corridor -> logistic habitat model over the 19 supplied bands + inverted depth, depth "
                  "gradient, throw, step, corridor, basin and Euler source-depth -> dots at 3 px spacing "
                  "pruned >3 px from every visible mapped trace.",
        named_non_fault_mimic="Density contrasts inside the basement (intrabasement lithologic contacts) "
                              "give the same gravity step. Discriminated by two model features rather than "
                              "asserted: inverted depth (a basin step sits on thick low-density fill) and "
                              "Euler SI=0 source depth (a basement edge is shallow, an intrabasement "
                              "contact is deep).",
        holdout_dti=dict(value=chosen["pooled_dti"], ci95=chosen["ci95_bootstrap_cells"],
                         evaluator=EVALUATOR, n_withheld_positive_px=hold["n_withheld_truth_px"],
                         n_dots_per_draw=chosen["n_emitted_per_draw"],
                         basin_interior_segments=f"{chosen['segments_recovered_basin_interior']}/"
                                                 f"{chosen['segments_withheld_basin_interior']} recovered",
                         basin_recovery_ci95=chosen["basin_recovery_ci95"]),
        correlation_overlap_vs_registry=dict(worst_spearman=uni["worst_spearman"],
                                             worst_overlap=uni["worst_overlap"],
                                             n_compared=uni["n_registry_rasters_compared"],
                                             verdict=uni["verdict"]),
        raster_sha256=fin["sha256"],
        validator_output=dict(checks=fin["validator"], all_passed=fin["validator_all_passed"]),
        submission_name=fin["submission"], note=fin["note"], note_chars=fin["note_chars"],
        leakage_canary=hold["leakage_canary"]["passed"],
        leakage_worst_auc=hold["leakage_canary"]["worst_auc"],
        inversion=dict(z0_m=feat["inversion_fine"]["z0_m"],
                       delta_rho=feat["inversion_fine"]["delta_rho"],
                       fine_dx_m=feat["inversion_grids"]["fine_px"] * 100,
                       coarse_dx_m=feat["inversion_grids"]["coarse_px"] * 100,
                       fraction_deeper_than_1km=feat["depth_stats_fine"]["fraction_gt_1km"],
                       rank_correlation_fine_vs_coarse=feat["rank_correlation_fine_vs_coarse"],
                       cross_check_r_vs_band15=feat["cross_check_vs_supplied_band15"]["pearson_r"]),
        verdict="negative",
        verdict_reason="HOLDOUT-DTI only; no organizer score. Slot decision is a separate selector step.",
        organizer_confirmed_score=None,
        experiments_run=len([r for r in hold["results"] if r["kind"] == "candidate"]),
        budget_experiments=3)
    R.write_json("h61m_run_card.json", card)
    log(json.dumps(card, indent=1)[:2500])


STAGES = dict(features=stage_features, holdout=stage_holdout, final=stage_final,
              unique=stage_unique, card=stage_card)


def main() -> None:
    raise SystemExit("RETIRED: Retired historical runner: it read organizer band 15. Use scripts/run_h61u.py; band 15 is prohibited.")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=list(STAGES) + ["all"])
    ap.add_argument("--candidate", default=None)
    ap.add_argument("--prune", type=float, default=None)
    ap.add_argument("--budget", type=int, default=None)
    ap.add_argument("--tile", type=int, default=None)
    a = ap.parse_args()
    order = list(STAGES) if a.stage == "all" else [a.stage]
    for s in order:
        log(f"==== {s} ====")
        STAGES[s](a)


if __name__ == "__main__":
    main()
