#!/usr/bin/env python3
"""RETIRED H61-M3 tuning runner; direct execution fails closed.

The legacy sweep description below is retained for historical context only; the
archived candidate fails strict final-dot uniqueness and the lineage budget is exceeded.

Two things, both required before a file is written:

A. **Leave-one-quadrant-out (LOQO) generalisation test.**  The leakage canary in
   experiment 2 put the GBM habitat model's out-of-fold AUC at 0.901, i.e. just
   above the protocol's 0.90 "leakage until proven otherwise" line.  The canary
   is *not* spatially blocked: the withheld segments sit inside the same
   quadrant as the visible traces the model was trained on, so a high AUC could
   in principle be adjacency rather than skill.  This stage retrains the model
   on three quadrants and scores it on the fourth, with no training pixel inside
   the scored quadrant at all.  If the AUC survives that, the 0.901 is skill.

B. **Configuration sweep.**  Dot spacing (tile), dot budget and catalogue prune,
   at the model class that won experiment 2.  The prune has a known conflict
   between instruments: on this holdout a 2 px prune beats 3 px (withheld truth
   is adjacent to visible traces), while the group's own organizer-scored pair
   ``gems25-dotted-h19-5-d2-8`` (0.2600, small prune) and
   ``gemsdoe32-h33-h33-2-b2`` (0.2778 = the same field with every dot within
   3 px of the catalogue deleted, verified as an exact set difference in
   ``reports/forensics.json``) says 3 px wins on the live metric.  Both are
   reported; the shipped file follows the live evidence and the divergence is
   logged as an irregularity.

Writes evidence/h61m3_sweep.json and evidence/h61m3_loqo.json.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import buried as B                       # noqa: E402
from gems61 import grid as gridmod                   # noqa: E402
from gems61 import h61mh as M                         # noqa: E402
from gems61 import holdout_segmented as holdoutmod   # noqa: E402
from gems61.metric import ALPHA, BETA                # noqa: E402

import run_h61g as R                                 # noqa: E402
from run_h61m2 import train_gbm                      # noqa: E402

EVID = ROOT / "evidence"
CACHE = ROOT / ".cache" / "h61m"
EVALUATOR = R.EVALUATOR
SEEDS = R.SEEDS


def log(m):
    print(m, flush=True)


def load_all():
    g = gridmod.load_grid()
    grav = np.asarray(B.load_band(13), np.float64)
    valid = g.footprint & np.isfinite(grav)
    stack = np.load(CACHE / "stack.npy", mmap_mode="r")
    names = json.loads((EVID / "h61m_features.json").read_text())["feature_names"]
    depth_fine = np.load(CACHE / "depth_fine.npy")
    return g, grav, valid, stack, names, depth_fine


def emit_and_score(ctx, seg_cache, oof, cell, prune, budget, dom_total, tile, depth_fine):
    sl = cell.bbox
    vis = ctx.visible(cell.key)[sl]
    far = ndi.distance_transform_edt(~vis) > prune
    allowed = cell.active & far
    b_cell = int(round(budget * float(cell.active.sum()) / dom_total))
    p = oof[cell.key][sl].astype(np.float64)
    dots = M.dot_thin(p, allowed, b_cell, tile_px=tile)
    part, dp = R._score_crop(cell, dots)
    hid = ctx.hidden_by_cell[cell.key][sl]
    ids = np.unique(seg_cache[sl][hid]); ids = ids[ids > 0]
    if dp is None:
        dp = np.full(hid.shape, np.inf)
    near = dp <= 3.0
    dep = depth_fine[sl]
    rows = []
    for sid in ids:
        m = (seg_cache[sl] == sid) & hid
        if m.any():
            rows.append((cell.key, int(sid), int(m.sum()),
                         float(np.median(dep[m])), float(near[m].mean())))
    return part, rows


def summarise(parts, rec_rows, n_seeds):
    pooled = R._pool(parts)
    rec = np.array([(r[2], r[3], r[4]) for r in rec_rows], np.float64) if rec_rows else np.zeros((0, 3))
    bm = rec[:, 1] > 300.0 if rec.size else np.zeros(0, bool)
    n_b = int(bm.sum()); k_b = int((rec[bm, 2] >= 0.5).sum()) if n_b else 0
    n_all = int(rec.shape[0]); k_all = int((rec[:, 2] >= 0.5).sum()) if n_all else 0
    return dict(**pooled, n_emitted_per_draw=pooled["n_emitted"] / n_seeds,
                segments_withheld_total=n_all, segments_recovered_total=k_all,
                segments_withheld_basin_interior=n_b,
                segments_recovered_basin_interior=k_b,
                basin_recovery_rate=(k_b / n_b) if n_b else None,
                basin_recovery_ci95=list(M.wilson(k_b, n_b)) if n_b else None)


# --------------------------------------------------------------------------- #
def stage_loqo() -> dict:
    g, grav, valid, stack, names, depth_fine = load_all()
    ctx = holdoutmod.build_holdout(g, hide_frac=0.20, seeds=SEEDS, modes=("all",))
    from gems61.network import segments
    seg_cache = segments(g.catalogue, max_len_px=12)[0]
    quad = ctx.quad
    dom_total = float(sum(c.active.sum() for c in ctx.cells if c.seed == ctx.cells[0].seed))
    rows = []
    for q, qname in enumerate(holdoutmod.FOLD_NAMES):
        # training positives: visible catalogue OUTSIDE quadrant q, minus the
        # segments withheld in any cell of quadrant q
        outside = quad != q
        hidden_here = np.zeros(g.shape, bool)
        for c in ctx.cells:
            if c.fold == q:
                hidden_here |= ctx.hidden_by_cell[c.key]
        train_pos = g.catalogue & outside & ~hidden_here
        model, rec = train_gbm(np.asarray(stack), valid, train_pos, names, seed=100 + q)
        p = M.predict_habitat(model, np.asarray(stack), valid)
        oof = {c.key: p.astype(np.float32) for c in ctx.cells if c.fold == q}
        del model, p
        # score the model only on quadrant q's cells
        parts, rec_rows = [], []
        for cell in ctx.cells:
            if cell.fold != q:
                continue
            part, rr = emit_and_score(ctx, seg_cache, oof, cell, 3.0, 40000,
                                      dom_total, 3, depth_fine)
            parts.append(part); rec_rows += rr
        s = summarise(parts, rec_rows, len(SEEDS))
        # canary restricted to quadrant q
        rng = np.random.default_rng(5)
        py, px, ny, nx = [], [], [], []
        for cell in ctx.cells:
            if cell.fold != q:
                continue
            sl = cell.bbox
            yy, xx = cell.truth_yx
            py.append(yy + sl[0].start); px.append(xx + sl[1].start)
            act = np.argwhere(cell.active)
            pick = act[rng.choice(act.shape[0], size=min(20000, act.shape[0]), replace=False)]
            ny.append(pick[:, 0] + sl[0].start); nx.append(pick[:, 1] + sl[1].start)
        py = np.concatenate(py); px = np.concatenate(px)
        ny = np.concatenate(ny); nx = np.concatenate(nx)
        pm = np.zeros(g.shape, np.float64)
        for c in ctx.cells:
            if c.fold == q:
                pm += oof[c.key]
        auc = M.auc_rank(np.nan_to_num(pm[py, px]), np.nan_to_num(pm[ny, nx]))
        row = dict(quadrant=qname, n_train_positive_px=int(train_pos.sum()),
                   train_auc=rec["train_auc"], loqo_canary_auc=auc,
                   loqo_pooled_dti=s["pooled_dti"], loqo_coverage=s["coverage"],
                   basin_interior=f"{s['segments_recovered_basin_interior']}/"
                                  f"{s['segments_withheld_basin_interior']}")
        rows.append(row)
        log(f"  LOQO {qname}: train_pos={row['n_train_positive_px']} "
            f"train_auc={rec['train_auc']:.3f} canary_auc={auc:.3f} "
            f"DTI={s['pooled_dti']:.4f} cov={s['coverage']:.3f} basin {row['basin_interior']}")
        del oof
    worst = max(r["loqo_canary_auc"] for r in rows)
    out = dict(evidence_class="MEASURED (spatially blocked generalisation test)",
               question="Is the GBM habitat model's 0.901 canary AUC skill or adjacency to the "
                        "visible traces it was trained on?",
               method="Leave-one-quadrant-out: retrain on the visible catalogue of the other three "
                      "quadrants only, then score the fourth. No training pixel lies inside the "
                      "scored quadrant.",
               rows=rows, worst_loqo_canary_auc=worst,
               verdict=("SKILL: AUC stays high with zero training data inside the scored quadrant"
                        if worst >= 0.75 else
                        "ADJACENCY: AUC collapses without training data in the scored quadrant"))
    R.write_json("h61m3_loqo.json", out)
    return out


# --------------------------------------------------------------------------- #
def stage_sweep() -> dict:
    g, grav, valid, stack, names, depth_fine = load_all()
    ctx = holdoutmod.build_holdout(g, hide_frac=0.20, seeds=SEEDS, modes=("all",))
    from gems61.network import segments
    seg_cache = segments(g.catalogue, max_len_px=12)[0]
    dom_total = float(sum(c.active.sum() for c in ctx.cells if c.seed == ctx.cells[0].seed))
    n_truth = sum(c.n_truth for c in ctx.cells)

    oof = {}
    receipts = []
    for cell in ctx.cells:
        model, rec = train_gbm(np.asarray(stack), valid, ctx.visible(cell.key), names,
                               seed=cell.seed)
        p = M.predict_habitat(model, np.asarray(stack), valid)
        oof[cell.key] = p.astype(np.float32)
        rec["cell"] = cell.key
        receipts.append(rec)
        del model, p
    log("  gbm trained on all 8 cells' visible catalogues")

    results = []
    for prune in (2.0, 3.0):
        for tile in (3, 4, 5):
            for budget in (40000, 60000):
                parts, rec_rows = [], []
                for cell in ctx.cells:
                    part, rr = emit_and_score(ctx, seg_cache, oof, cell, prune, budget,
                                              dom_total, tile, depth_fine)
                    parts.append(part); rec_rows += rr
                s = summarise(parts, rec_rows, len(SEEDS))
                s.update(name=f"S gbm prune{prune:.0f} tile{tile} @ {budget}", prune_px=prune,
                         tile_px=tile, budget=budget,
                         ci95_bootstrap_cells=R._boot_ci(parts))
                results.append(s)
                log(f"  {s['name']:34s} n/draw={s['n_emitted_per_draw']:7.0f} "
                    f"DTI={s['pooled_dti']:.4f} CI[{s['ci95_bootstrap_cells'][0]:.4f},"
                    f"{s['ci95_bootstrap_cells'][1]:.4f}] cov={s['coverage']:.3f} "
                    f"basin {s['segments_recovered_basin_interior']}/"
                    f"{s['segments_withheld_basin_interior']}")
    best = max(results, key=lambda r: r["pooled_dti"])
    R.write_json("h61m3_sweep.json", dict(
        evidence_class="HOLDOUT-DTI", evaluator=EVALUATOR, alpha=ALPHA, beta=BETA,
        kernel_m=300, n_withheld_truth_px=int(n_truth), n_cells=len(ctx.cells),
        model="HistGradientBoostingClassifier(max_iter=200, lr=0.08, leaves=31, "
              "min_samples_leaf=40, l2=1.0) over 28 catalogue-independent features",
        model_receipts=receipts, results=results, best_candidate=best["name"],
        note="HOLDOUT-DTI is an evaluator-version index on withheld catalogue traces, not a "
             "competition score. Prune 2 px wins on this instrument because the withheld truth is "
             "adjacent to visible traces; the group's organizer-scored pair says 3 px wins live "
             "(IR-61-PRUNE-01)."))
    return best


def main() -> int:
    print("RETIRED: H61-M3 would create additional tuning/LOQO holdouts after the lineage budget was exceeded; "
          "the archived H61-MH TIFF fails strict final-dot uniqueness. No experiment may be run.",
          file=sys.stderr)
    return 2

    t0 = time.time()
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("loqo", "all"):
        log("==== loqo ====")
        stage_loqo()
    if which in ("sweep", "all"):
        log("==== sweep ====")
        stage_sweep()
    log(f"done in {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
