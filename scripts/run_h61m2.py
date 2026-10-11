#!/usr/bin/env python3
"""RETIRED H61-M2 experiment runner; direct execution fails closed.

The legacy experiment description below is retained for historical context only.
The archived candidate fails strict final-dot uniqueness and the lineage budget is exceeded.

Experiment 1 (``scripts/run_h61mh.py holdout``) established, on the shared
segmented holdout:

  * a hard corridor gate (the lane's literal "steps as candidates") *reduces*
    the score: 0.0364-0.0409 gated vs 0.0606 ungated at the same 40 k budget;
  * the corridor indicator's leakage-canary AUC against the withheld faults is
    0.510 -- the step field carries almost no information about *where the
    unmapped faults are* at 300 m, which is the lane's hard limit stated by
    H61-G;
  * a 3 x 3 ribbon (the lane's "multi-line ribbon") scores 0.0184 against
    0.0409 for the same dots -- the metric charges 0.2 per extra positive pixel.

Experiment 2 therefore asks two questions and nothing else:

  Q1  does a non-linear model (histogram gradient boosting) beat the L2
      logistic habitat model on the same features?
  Q2  does a *soft* step prior -- the lane's basement-step evidence entering as
      a multiplicative boost on the candidate ranking rather than as a hard
      gate -- recover any of the lane's signal without paying the gate's cost?

Writes evidence/h61m2_holdout.json.
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
from gems61.metric import ALPHA, BETA, EPS           # noqa: E402

import run_h61g as R                                 # noqa: E402
import run_h61mh as R1                                # noqa: E402

EVID = ROOT / "evidence"
CACHE = ROOT / ".cache" / "h61m"
EVALUATOR = R.EVALUATOR
SEEDS = R.SEEDS


def log(m):
    print(m, flush=True)


def train_gbm(stack, valid, positives, names, *, seed=0):
    from sklearn.ensemble import HistGradientBoostingClassifier
    rng = np.random.default_rng(seed)
    pos_idx = np.flatnonzero((positives & valid).ravel())
    neg_pool = np.flatnonzero((valid & ~positives).ravel())
    neg_idx = rng.choice(neg_pool, size=min(4 * pos_idx.size, neg_pool.size), replace=False)
    flat = stack.reshape(-1, stack.shape[-1])
    X = np.concatenate([flat[pos_idx], flat[neg_idx]])
    del flat
    y = np.concatenate([np.ones(pos_idx.size, np.int8), np.zeros(neg_idx.size, np.int8)])
    keep = np.isfinite(X).all(axis=1)
    X, y = np.nan_to_num(X[keep], nan=0.0), y[keep]
    model = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.08,
                                           max_leaf_nodes=31, min_samples_leaf=40,
                                           l2_regularization=1.0, random_state=seed)
    model.fit(X, y)
    rec = dict(n_pos=int((y == 1).sum()), n_neg=int((y == 0).sum()),
               train_auc=float(M._auc(model.predict_proba(X)[:, 1], y)),
               model="HistGradientBoostingClassifier(max_iter=200, lr=0.08, leaves=31)")
    return model, rec


def main() -> int:
    print("RETIRED: H61-M2 would create another holdout trial after the lineage budget was exceeded; "
          "the archived H61-MH TIFF fails strict final-dot uniqueness. No experiment may be run.",
          file=sys.stderr)
    return 2

    t0 = time.time()
    g = gridmod.load_grid()
    grav = np.asarray(B.load_band(13), np.float64)
    valid = g.footprint & np.isfinite(grav)
    stack = np.load(CACHE / "stack.npy", mmap_mode="r")
    names = json.loads((EVID / "h61m_features.json").read_text())["feature_names"]
    hgm = np.load(CACHE / "hgm.npy")
    throw = np.load(CACHE / "throw.npy")
    depth_fine = np.load(CACHE / "depth_fine.npy")
    corridor = np.load(CACHE / "corridor.npy")

    # soft prior from the lane's own basement-step field: rank of |grad depth|
    # and of the measured throw, both normalised over the footprint.
    step_rank = M._rank01(hgm, valid).astype(np.float64)
    throw_rank = M._rank01(throw, valid).astype(np.float64)
    conceal = np.clip((depth_fine - 100.0) / 1400.0, 0.0, 1.0)

    ctx = holdoutmod.build_holdout(g, hide_frac=0.20, seeds=SEEDS, modes=("all",))
    n_truth = sum(c.n_truth for c in ctx.cells)
    dom_total = float(sum(c.active.sum() for c in ctx.cells if c.seed == ctx.cells[0].seed))
    log(f"holdout: {len(ctx.cells)} cells, {n_truth} withheld truth px")

    from gems61.network import segments
    seg_cache = segments(g.catalogue, max_len_px=12)[0]

    models = {}
    for kind, fn in (("logistic", M.train_habitat), ("gbm", train_gbm)):
        oof = {}
        receipts = []
        for cell in ctx.cells:
            model, rec = fn(np.asarray(stack), valid, ctx.visible(cell.key), names,
                            seed=cell.seed)
            p = M.predict_habitat(model, np.asarray(stack), valid)
            oof[cell.key] = p.astype(np.float32)
            rec["cell"] = cell.key
            receipts.append(rec)
            del model, p
        models[kind] = dict(oof=oof, receipts=receipts)
        log(f"  {kind}: mean train_auc={np.mean([r['train_auc'] for r in receipts]):.4f}")

    results = []

    def run(name, kind, prior=None, prior_k=1.0, prune=3.0, budget=40000, tile=3):
        parts, rec_rows = [], []
        oof = models[kind]["oof"]
        for ci, cell in enumerate(ctx.cells):
            sl = cell.bbox
            vis = ctx.visible(cell.key)[sl]
            far = ndi.distance_transform_edt(~vis) > prune
            allowed = cell.active & far
            b_cell = int(round(budget * float(cell.active.sum()) / dom_total))
            p = oof[cell.key][sl].astype(np.float64)
            if prior == "step":
                p = p * (1.0 + prior_k * step_rank[sl])
            elif prior == "throw":
                p = p * (1.0 + prior_k * throw_rank[sl] * (0.5 + 0.5 * conceal[sl]))
            elif prior == "corridor":
                p = p * (1.0 + prior_k * corridor[sl].astype(np.float64))
            dots = M.dot_thin(p, allowed, b_cell, tile_px=tile)
            part, dp = R._score_crop(cell, dots)
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
        bm = rec[:, 1] > 300.0 if rec.size else np.zeros(0, bool)
        n_b = int(bm.sum()); k_b = int((rec[bm, 2] >= 0.5).sum()) if n_b else 0
        n_all = int(rec.shape[0]); k_all = int((rec[:, 2] >= 0.5).sum()) if n_all else 0
        row = dict(name=name, kind=kind, prior=prior, prior_k=prior_k, prune_px=prune,
                   budget=budget, tile_px=tile, **pooled,
                   ci95_bootstrap_cells=R._boot_ci(parts),
                   n_emitted_per_draw=pooled["n_emitted"] / len(SEEDS),
                   segments_withheld_total=n_all, segments_recovered_total=k_all,
                   segments_withheld_basin_interior=n_b, segments_recovered_basin_interior=k_b,
                   basin_recovery_rate=(k_b / n_b) if n_b else None,
                   basin_recovery_ci95=list(M.wilson(k_b, n_b)) if n_b else None)
        results.append(row)
        log(f"  {name:56s} n/draw={row['n_emitted_per_draw']:7.0f} DTI={row['pooled_dti']:.4f} "
            f"CI[{row['ci95_bootstrap_cells'][0]:.4f},{row['ci95_bootstrap_cells'][1]:.4f}] "
            f"cov={row['coverage']:.3f} basin {k_b}/{n_b}")
        return row

    # Q1: model class, no prior
    for kind in ("logistic", "gbm"):
        for prune in (2.0, 3.0):
            run(f"E2 {kind} no-prior prune{prune:.0f} @ 40000", kind, prune=prune)
    # Q2: soft step prior, both models
    for kind in ("logistic", "gbm"):
        for prior, k in (("step", 0.5), ("step", 2.0), ("throw", 1.0)):
            run(f"E2 {kind} prior={prior} k={k} prune3 @ 40000", kind, prior=prior,
                prior_k=k, prune=3.0)
    # budget / spacing sweep on the best-so-far construction
    best = max(results, key=lambda r: r["pooled_dti"])
    log(f"best so far: {best['name']} DTI={best['pooled_dti']:.4f}")
    for budget in (30000, 60000):
        run(f"E2 {best['kind']} prior={best['prior']} k={best['prior_k']} "
            f"prune{best['prune_px']:.0f} @ {budget}", best["kind"], prior=best["prior"],
            prior_k=best["prior_k"], prune=best["prune_px"], budget=budget)
    for tile in (2, 4):
        run(f"E2 {best['kind']} prior={best['prior']} k={best['prior_k']} "
            f"prune{best['prune_px']:.0f} tile{tile} @ 40000", best["kind"],
            prior=best["prior"], prior_k=best["prior_k"], prune=best["prune_px"], tile=tile)

    # leakage canary on the two model families
    rng = np.random.default_rng(3)
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
    for kind in ("logistic", "gbm"):
        mean_p = np.zeros(g.shape, np.float64)
        for c in ctx.cells:
            mean_p += models[kind]["oof"][c.key]
        mean_p /= len(ctx.cells)
        canary[f"{kind} OOF probability"] = dict(
            auc=M.auc_rank(np.nan_to_num(mean_p[py, px]), np.nan_to_num(mean_p[ny, nx])),
            n_pos=int(py.size), n_neg=int(ny.size))
        log(f"  canary {kind:24s} AUC={canary[f'{kind} OOF probability']['auc']:.3f}")
    worst = max(canary.values(), key=lambda r: r["auc"])["auc"]

    R.write_json("h61m2_holdout.json", dict(
        evidence_class="HOLDOUT-DTI",
        evaluator=EVALUATOR, alpha=ALPHA, beta=BETA, kernel_m=300,
        n_withheld_truth_px=int(n_truth), n_cells=len(ctx.cells),
        questions=dict(Q1="does a non-linear model beat the logistic habitat model?",
                       Q2="does a soft step prior beat a hard corridor gate?"),
        model_receipts={k: v["receipts"] for k, v in models.items()},
        results=results, best_candidate=max(results, key=lambda r: r["pooled_dti"])["name"],
        leakage_canary=dict(threshold_auc=0.90, worst_auc=worst, passed=bool(worst < 0.90),
                            per_feature=canary),
        note="HOLDOUT-DTI is an evaluator-version index on withheld catalogue traces, not a "
             "competition score. Every candidate is trained only on the VISIBLE catalogue of its "
             "own cell and pruned only against that visible catalogue.",
        elapsed_s=round(time.time() - t0, 1)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
