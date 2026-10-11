#!/usr/bin/env python3
"""H61-O driver — depth-dependent density inversion (H61-B) + Euler + mag mimic filter.

Stages:
  features  build 200m variable-density inversion + 30-channel stack
  holdout   OOF logistic habitat, budget/prune/tile sweeps, controls, canary
  final     build + validate GeoTIFF
  unique    correlation / overlap vs registry
  card      run card JSON
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

from gems61 import buried as B
from gems61 import grid as gridmod
from gems61 import h61o as M
from gems61 import holdout_segmented as holdoutmod
from gems61 import submission_writer
from gems61.metric import ALPHA, BETA, EPS, kernel

import run_h61g as R

EVID = ROOT / "evidence"
OUT = ROOT / "out"
CACHE = ROOT / ".cache" / "h61o"
DOWNLOADS = ROOT / "docs" / "downloads"
SEEDS = R.SEEDS
EVALUATOR = R.EVALUATOR
BUDGETS = (20000, 30000, 40000, 60000)
PRUNES = (2.0, 3.0, 4.0)
TILES = (2, 3, 4)


def log(msg: str) -> None:
    print(msg, flush=True)


def load_base():
    g = gridmod.load_grid()
    grav = np.asarray(B.load_band(13), np.float64)
    valid = g.footprint & np.isfinite(grav)
    return g, grav, valid


def stage_features(_a) -> None:
    t0 = time.time()
    g, grav, valid = load_base()
    CACHE.mkdir(parents=True, exist_ok=True)
    names, stack, meta, aux = M.build_feature_stack_variable(
        grav, valid, g.shape, out_path=CACHE / "stack.npy", cache_dir=CACHE
    )
    for k in ("depth_fine", "hgm", "throw", "corridor", "basin", "euler", "mag_edge", "euler_consistency"):
        np.save(CACHE / f"{k}.npy", aux[k])
    np.save(CACHE / "steps.npy", aux["steps"])
    np.save(CACHE / "valid.npy", valid)
    # calibration check
    both = valid & np.isfinite(aux["depth_fine"])
    b15 = np.asarray(B.load_band(15), np.float64)
    cross = B.compare_to_published_depth(b15, aux["depth_fine"], both)
    gsign = float(np.corrcoef(aux["depth_fine"][both], grav[both])[0, 1]) if both.sum() > 10 else float("nan")
    log(f"inversion var-density: stats={meta['depth_stats']} cross r vs band15={cross['pearson_r']:.3f} corr depth vs grav={gsign:.3f}")
    R.write_json("h61o_features.json", dict(
        evidence_class="MEASURED",
        inversion=meta["inversion"],
        depth_stats=meta["depth_stats"],
        steps_fine=meta["steps_fine"],
        variable_density=meta["variable_density"],
        corridor_px=meta["corridor_px"],
        basin_floor_m=meta["basin_floor_m"],
        corridor_fraction_of_valid=meta["corridor_fraction_of_valid"],
        basin_fraction_of_valid=meta["basin_fraction_of_valid"],
        n_features=meta["n_features"],
        feature_names=meta["feature_names"],
        cross_check_vs_band15=cross,
        corr_depth_vs_gravity=gsign,
        elapsed_s=round(time.time() - t0, 1),
    ))


def _load_stack():
    return np.load(CACHE / "stack.npy", mmap_mode="r")


def stage_holdout(_a) -> None:
    t0 = time.time()
    g, grav, valid = load_base()
    stack = _load_stack()
    feat_meta = json.loads((EVID / "h61o_features.json").read_text())
    names = feat_meta["feature_names"]
    corridor = np.load(CACHE / "corridor.npy")
    basin = np.load(CACHE / "basin.npy")
    depth_fine = np.load(CACHE / "depth_fine.npy")
    hgm = np.load(CACHE / "hgm.npy")
    throw = np.load(CACHE / "throw.npy")
    euler = np.load(CACHE / "euler.npy")
    mag_edge = np.load(CACHE / "mag_edge.npy")
    euler_cons = np.load(CACHE / "euler_consistency.npy")

    ctx = holdoutmod.build_holdout(g, hide_frac=0.20, seeds=SEEDS, modes=("all",))
    n_truth = sum(c.n_truth for c in ctx.cells)
    log(f"holdout: {len(ctx.cells)} cells, {n_truth} withheld truth px")
    stack_arr = np.asarray(stack)

    dom_total = float(sum(c.active.sum() for c in ctx.cells if c.seed == ctx.cells[0].seed))
    results = []

    def run(name, kind, emit, budget=None, prune=None, tile=None):
        parts, rec_rows = [], []
        for ci, cell in enumerate(ctx.cells):
            sl = cell.bbox
            vis = ctx.visible(cell.key)[sl]
            far = ndi.distance_transform_edt(~vis) > prune
            allowed = cell.active & far
            dom_px = float(cell.active.sum())
            b_cell = int(round(budget * dom_px / dom_total)) if dom_total > 0 else budget
            p_crop = emit(cell, allowed, b_cell, ci)
            part, dp = R._score_crop(cell, p_crop)
            parts.append(part)
            hid = ctx.hidden_by_cell[cell.key][sl]
            # for basin recovery
            from gems61.network import segments
            # seg_cache loaded outside? We'll load once
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
        log(f"  {name:70s} n/draw={row['n_emitted_per_draw']:7.0f} DTI={row['pooled_dti']:.4f} "
            f"CI[{row['ci95_bootstrap_cells'][0]:.4f},{row['ci95_bootstrap_cells'][1]:.4f}] "
            f"cov={row['coverage']:.3f} basin {k_b}/{n_b}")
        return row

    # OOF models
    oof = {}
    receipts = []
    for cell in ctx.cells:
        vis = ctx.visible(cell.key)
        model, rec = M.train_habitat(stack_arr, valid, vis, names, seed=cell.seed)
        p = M.predict_habitat(model, stack_arr, valid)
        del model
        oof[cell.key] = p.astype(np.float32)
        del p
        rec["cell"] = cell.key
        receipts.append(rec)
        top = sorted(rec["coefficients"].items(), key=lambda kv: -abs(kv[1]))[:6]
        log(f"  model {cell.key}: n_pos={rec['n_pos']} auc={rec['train_auc']:.3f} top:" + ",".join(f"{k}{v:+.2f}" for k,v in top))

    coef_mean = {n: float(np.mean([r["coefficients"][n] for r in receipts])) for n in names}

    from gems61.network import segments
    seg_cache = segments(g.catalogue, max_len_px=12)[0]

    def emit_model(cell, allowed, b_cell, ci, tile=M.TILE_PX, gate=None, extra_filter=None):
        p = oof[cell.key][cell.bbox]
        if gate is not None:
            p = np.where(gate[cell.bbox], p, -np.inf)
        if extra_filter is not None:
            # extra_filter is full-grid bool, keep only where filter true
            filt = extra_filter[cell.bbox]
            p = np.where(filt, p, -np.inf)
        return M.dot_thin(p, allowed, b_cell, tile_px=tile)

    # controls
    for budget in BUDGETS:
        run(f"CONTROL random lines @ {budget}", "lines",
            lambda c, a, b, ci, **k: R.H.random_lines(a.shape, a, b, seed=100 + ci),
            budget=budget, prune=R.PRUNE_PX, tile=M.TILE_PX)
    run("CONTROL random dots anywhere @ 40000", "dots",
        lambda c, a, b, ci, **k: R.H.random_dots(a, b, seed=300 + ci),
        budget=40000, prune=R.PRUNE_PX, tile=M.TILE_PX)

    best = None
    for prune in PRUNES:
        for budget in BUDGETS:
            # with corridor gate
            row = run(f"O1 habitat x corridor (prune {prune:.0f}px) @ {budget}", "candidate",
                      lambda c, a, b, ci, pr=prune: emit_model(c, a, b, ci, gate=corridor),
                      budget=budget, prune=prune, tile=M.TILE_PX)
            if best is None or row["pooled_dti"] > best["pooled_dti"]:
                best = row
            # without gate (habitat only) — tests if corridor helps
            run(f"O2 habitat no gate (prune {prune:.0f}px) @ {budget}", "candidate",
                lambda c, a, b, ci: emit_model(c, a, b, ci, gate=None),
                budget=budget, prune=prune, tile=M.TILE_PX)
            # with Euler consistency filter
            run(f"O3 habitat x corridor + euler_cons (prune {prune:.0f}px) @ {budget}", "candidate",
                lambda c, a, b, ci: emit_model(c, a, b, ci, gate=corridor, extra_filter=euler_cons.astype(bool)),
                budget=budget, prune=prune, tile=M.TILE_PX)

    # tile sweep at best config
    if best is not None:
        bp, bb = best["prune_px"], best["budget"]
        for tile in TILES:
            run(f"O4 habitat x corridor tile {tile}px @ {bb} prune {bp}", "candidate",
                lambda c, a, b, ci, t=tile: emit_model(c, a, b, ci, tile=t, gate=corridor),
                budget=bb, prune=bp, tile=tile)
        # ribbon variant
        run(f"O5 habitat x corridor 3x3 ribbon @ {bb}", "candidate",
            lambda c, a, b, ci: M.ribbon(emit_model(c, a, b, ci, gate=corridor), 1) & a,
            budget=bb, prune=bp, tile=M.TILE_PX)
        # mag edge demoted: require NOT near mag edge
        not_mag = ~mag_edge
        run(f"O6 habitat x corridor NOT mag edge @ {bb}", "candidate",
            lambda c, a, b, ci: emit_model(c, a, b, ci, gate=corridor, extra_filter=not_mag),
            budget=bb, prune=bp, tile=M.TILE_PX)

    # leakage canary
    rng = np.random.default_rng(3)
    mean_oof = np.zeros(g.shape, np.float64)
    for c in ctx.cells:
        mean_oof += oof[c.key]
    mean_oof /= len(ctx.cells)
    feats = {"habitat OOF prob": mean_oof,
             "var-depth": depth_fine, "var-depth HGM": hgm,
             "throw": throw, "corridor": corridor.astype(float),
             "euler": euler, "euler_cons": euler_cons,
             "mag_edge": mag_edge.astype(float),
             "band13 grav": np.asarray(B.load_band(13), np.float64),
             "band19 slope": np.asarray(B.load_band(19), np.float64)}
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
    best = max(cands, key=lambda r: r["pooled_dti"]) if cands else None

    R.write_json("h61o_holdout.json", dict(
        evidence_class="HOLDOUT-DTI",
        evaluator=EVALUATOR, alpha=ALPHA, beta=BETA, kernel_m=300,
        n_withheld_truth_px=int(n_truth), n_cells=len(ctx.cells),
        budgets=list(BUDGETS), prunes_px=list(PRUNES), tiles_px=list(TILES),
        feature_names=names, mean_coefficients=coef_mean, model_receipts=receipts,
        results=results, best_candidate=best["name"] if best else None,
        leakage_canary=dict(threshold_auc=0.90, worst_auc=worst, passed=bool(worst < 0.90), per_feature=canary),
        elapsed_s=round(time.time() - t0, 1),
    ))


def stage_final(a) -> None:
    g, grav, valid = load_base()
    hold = json.loads((EVID / "h61o_holdout.json").read_text())
    cands = [r for r in hold["results"] if r["kind"] == "candidate"]
    chosen = max(cands, key=lambda r: r["pooled_dti"]) if not a.candidate else next(r for r in cands if r["name"] == a.candidate)
    if a.prune is not None:
        chosen = dict(chosen, prune_px=a.prune)
    if a.budget is not None:
        chosen = dict(chosen, budget=a.budget)
    if a.tile is not None:
        chosen = dict(chosen, tile_px=a.tile)
    log(f"chosen: {chosen['name']} DTI={chosen['pooled_dti']:.4f} prune {chosen['prune_px']} budget {chosen['budget']} tile {chosen['tile_px']}")

    stack = _load_stack()
    names = hold["feature_names"]
    corridor = np.load(CACHE / "corridor.npy")
    basin = np.load(CACHE / "basin.npy")
    euler_cons = np.load(CACHE / "euler_consistency.npy")
    mag_edge = np.load(CACHE / "mag_edge.npy")

    prune = float(chosen["prune_px"]); budget = int(chosen["budget"]); tile = int(chosen["tile_px"])

    # decide gate based on name
    if "corridor" in chosen["name"] and "NOT mag" in chosen["name"]:
        gate = corridor & (~mag_edge)
        extra = None
        gate_desc = "corridor & NOT mag_edge"
    elif "euler_cons" in chosen["name"]:
        gate = corridor
        extra = euler_cons.astype(bool)
        gate_desc = "corridor + euler_cons"
    elif "corridor" in chosen["name"]:
        gate = corridor
        extra = None
        gate_desc = "corridor"
    elif "basin" in chosen["name"]:
        gate = basin
        extra = None
        gate_desc = "basin"
    else:
        gate = None
        extra = None
        gate_desc = "none"

    model, rec = M.train_habitat(np.asarray(stack), valid, g.catalogue, names, seed=20)
    p = M.predict_habitat(model, np.asarray(stack), valid)
    far = ndi.distance_transform_edt(~g.catalogue) > prune
    allowed = valid & far & ~g.catalogue
    if gate is not None:
        allowed = allowed & gate
    if extra is not None:
        # extra filter on probability field, not allowed? We'll filter p
        p = np.where(extra, p, -np.inf)

    dots = M.dot_thin(p, allowed, budget, tile_px=tile)
    if "ribbon" in chosen["name"]:
        dots = M.ribbon(dots, 1) & allowed

    values = dots.astype(np.float32)
    n_dots = int(dots.sum())
    dcat = ndi.distance_transform_edt(~g.catalogue)[dots]
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    digest = hashlib.sha256(values.tobytes()).hexdigest()[:12]
    name = f"gems61-h61o-vardepth-{gate_desc.replace(' ','')}-{n_dots}dots-{stamp}-{digest}-zeros"
    # ensure <=140 chars
    name = name[:100] + "-zeros"
    note = f"H61-O var-density inversion Hildenbrand 1999 + Euler+mag mimic filter {gate_desc}; {n_dots} dots {tile}px {prune:.0f}px prune"
    note = note[:140]
    OUT.mkdir(parents=True, exist_ok=True)
    receipt = submission_writer.write_submission(
        OUT / f"{name}.tif", values, sample=gridmod.DATA_DIR / "sample_submission.tif",
        footprint=g.footprint, note=note, name=name[:140], catalogue=g.catalogue,
        metadata=dict(method="H61-O variable density", candidate=chosen["name"], budget=budget,
                      prune_px=prune, tile_px=tile, n_dots=n_dots,
                      holdout_dti=chosen["pooled_dti"], holdout_ci95=chosen["ci95_bootstrap_cells"],
                      evaluator=EVALUATOR, mean_coefficients=hold["mean_coefficients"],
                      gate=gate_desc))
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    for ext in (".tif", ".zip", ".json"):
        shutil.copy2(OUT / f"{name}{ext}", DOWNLOADS / f"{name}{ext}")
    rand = next((r for r in hold["results"] if r["name"].startswith("CONTROL random lines") and r["budget"] == budget), None)
    R.write_json("h61o_final.json", dict(
        evidence_class="MEASURED (file) + HOLDOUT-DTI",
        submission=name, note=note, note_chars=len(note), candidate=chosen["name"],
        budget=budget, prune_px=prune, tile_px=tile, n_dots=n_dots, gate=gate_desc,
        dots_distance_to_catalogue_px=dict(min=float(dcat.min()) if n_dots>0 else 0, median=float(np.median(dcat)) if n_dots>0 else 0,
                                           mean=float(dcat.mean()) if n_dots>0 else 0, frac_within_3px=float((dcat<=3).mean()) if n_dots>0 else 0),
        tif=f"out/{name}.tif", zip=f"out/{name}.zip", receipt=f"out/{name}.json",
        download_tif=f"docs/downloads/{name}.tif", download_zip=f"docs/downloads/{name}.zip",
        sha256=receipt["sha256"], bytes=receipt["bytes"], zip_sha256=receipt["zip_sha256"],
        validator=receipt["validator"]["checks"], validator_all_passed=receipt["validator"]["all_checks_passed"],
        holdout=dict(dti=chosen["pooled_dti"], ci95=chosen["ci95_bootstrap_cells"],
                     random_lines=rand["pooled_dti"] if rand else None,
                     beats_random=bool(chosen["pooled_dti"] > (rand["pooled_dti"] if rand else 0)),
                     n_withheld_truth_px=hold["n_withheld_truth_px"], evaluator=EVALUATOR),
        organizer_receipt=None,
    ))


def stage_unique(_a) -> None:
    import rasterio
    from scipy.stats import spearmanr
    g = gridmod.load_grid()
    fin = json.loads((EVID / "h61o_final.json").read_text())
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
            except Exception as exc:
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
            gate_rule = "Jaccard (dense)" if dense else "one-sided 3px overlap"
            gate_limit = 0.50 if dense else 0.70
            rows.append(dict(file=p.name, sha256=R.sha256(p), spearman_footprint=rho,
                             frac_my_dots_within_3px_of_theirs=frac, base_rate_within_3px=base,
                             jaccard=jac, their_positive_px=int(od.sum()),
                             overlap_gate_rule=gate_rule, overlap_gate_value=gate_value,
                             overlap_gate_limit=gate_limit,
                             overlap_gate_exceeded=bool(gate_value > gate_limit),
                             byte_identical=(R.sha256(p) == fin["sha256"])))
    ok = [r for r in rows if "spearman_footprint" in r]
    worst_rho = max(ok, key=lambda r: (r["spearman_footprint"] if r["spearman_footprint"] == r["spearman_footprint"] else -2)) if ok else None
    worst_ov = max(ok, key=lambda r: r["frac_my_dots_within_3px_of_theirs"]) if ok else None
    worst_gate = max(ok, key=lambda r: r["overlap_gate_value"] / r["overlap_gate_limit"]) if ok else None
    verdict = "UNIQUE" if (worst_rho and worst_rho["spearman_footprint"] <= 0.90 and not any(r["overlap_gate_exceeded"] for r in ok) and not any(r["byte_identical"] for r in ok)) else "DUPLICATE"
    R.write_json("h61o_uniqueness.json", dict(
        evidence_class="MEASURED", my_file=fin["tif"], my_sha256=fin["sha256"],
        my_dots=int(mine_dots.sum()), n_registry_rasters_compared=len(ok),
        rho_limit=0.90, overlap_limit=0.70,
        worst_spearman=dict(file=worst_rho["file"], value=worst_rho["spearman_footprint"]) if worst_rho else None,
        worst_overlap=dict(file=worst_ov["file"], value=worst_ov["frac_my_dots_within_3px_of_theirs"], base_rate=worst_ov["base_rate_within_3px"]) if worst_ov else None,
        worst_overlap_gate=dict(file=worst_gate["file"], rule=worst_gate["overlap_gate_rule"], value=worst_gate["overlap_gate_value"], limit=worst_gate["overlap_gate_limit"]) if worst_gate else None,
        byte_identical_to_any=[r["file"] for r in ok if r["byte_identical"]],
        verdict=verdict, rows=rows,
    ))
    log(f"UNIQUENESS: {verdict}")


def stage_card(_a) -> None:
    hold = json.loads((EVID / "h61o_holdout.json").read_text())
    fin = json.loads((EVID / "h61o_final.json").read_text())
    uni = json.loads((EVID / "h61o_uniqueness.json").read_text())
    feat = json.loads((EVID / "h61o_features.json").read_text())
    chosen = next(r for r in hold["results"] if r["name"] == fin["candidate"])
    card = dict(
        session="H61-O arena/ac3f2948-61gemsdoe 2026-10-11 variable-density inversion",
        hypothesis="Buried normal fault is a step in the basement surface inverted with depth-dependent fill density (Hildenbrand 1999: 1900/2100/2300/2450 kg/m3, basement 2670); the step is located at HGM maxima and discriminated from intrabasement density contacts by Euler SI=0 source depth consistency and magnetic edge demotion.",
        mechanism="Isostatic residual band 13 -> 200m decimation -> inpaint -> 15km regional removal -> Butterworth low-pass kc=0.25/(2*500m) -> per-pixel variable-density Bouguer solve t=dg/(2πG*avgΔρ(t)) -> upsample 100m -> Blakely-Simpson HGM maxima throw>=80m -> corridor 1km -> Euler depth from bands 18/11 -> mag edge from band3 -> logistic habitat over 30 features (19 bands + var-depth + HGM + throw + corridor + basin + Euler + grad + mag_edge + Euler_cons) OOF per quadrant -> dots 3px tile 3px prune.",
        named_non_fault_mimic="Intrabasement lithologic contact (granitic/mafic) with Δρ~200 kg/m3 over 2 km gives same gravity step as 1000m basement offset at 400 kg/m3; also caldera fill, hydrothermal alteration, paleo-weathered horizon. Discriminated by Euler depth (basement edge shallow ~ inverted depth, intrabasement deep) and by magnetic edge coincidence (intrabasement contact often magnetic, basin step non-magnetic).",
        holdout_dti=dict(value=chosen["pooled_dti"], ci95=chosen["ci95_bootstrap_cells"],
                         evaluator=EVALUATOR, n_withheld_truth_px=hold["n_withheld_truth_px"],
                         n_dots_per_draw=chosen["n_emitted_per_draw"],
                         basin_interior_segments=f"{chosen['segments_recovered_basin_interior']}/{chosen['segments_withheld_basin_interior']}",
                         basin_recovery_ci95=chosen["basin_recovery_ci95"],
                         random_lines_same_budget=fin["holdout"]["random_lines"]),
        leakage_canary=hold["leakage_canary"],
        correlation_overlap_vs_registry=dict(worst_spearman=uni.get("worst_spearman"), worst_overlap=uni.get("worst_overlap"), worst_gate=uni.get("worst_overlap_gate"), verdict=uni.get("verdict"), n_compared=uni.get("n_registry_rasters_compared")),
        raster_sha256=fin["sha256"],
        raster_bytes=fin.get("bytes") or 0,
        validator_output=dict(checks=fin["validator"], all_passed=fin["validator_all_passed"]),
        submission_name=fin["submission"],
        note=fin["note"],
        note_chars=fin["note_chars"],
        inversion=feat["depth_stats"],
        variable_density=feat["variable_density"],
        experiments_run=len([r for r in hold["results"] if r["kind"] == "candidate"]),
        organizer_confirmed_score=None,
        verdict="negative" if chosen["pooled_dti"] < 0.08 else "promote",
        verdict_reason=f"HOLDOUT-DTI {chosen['pooled_dti']:.4f} CI {chosen['ci95_bootstrap_cells']} vs random lines {fin['holdout']['random_lines']:.4f}; basin recovery {chosen['segments_recovered_basin_interior']}/{chosen['segments_withheld_basin_interior']}; leakage worst AUC {hold['leakage_canary']['worst_auc']:.3f}",
        download=dict(tif=fin["download_tif"], zip=fin["download_zip"], sha256=fin["sha256"]),
    )
    R.write_json("h61o_run_card.json", card)
    log(json.dumps(card, indent=2)[:4000])


STAGES = dict(features=stage_features, holdout=stage_holdout, final=stage_final, unique=stage_unique, card=stage_card)


def main() -> None:
    ap = argparse.ArgumentParser()
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
