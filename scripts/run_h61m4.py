#!/usr/bin/env python3
"""H61-M experiment 4 -- which locator actually generalises across space?

Experiment 3 showed that the gradient-boosted habitat model's 0.901 canary AUC
was adjacency, not skill: retrained with no training pixel inside the scored
quadrant, its AUC falls to 0.525-0.608 and its pooled DTI to about the random
baseline.  Before anything is written to disk this stage puts every locator
through the same spatially blocked test:

  logistic   L2 logistic habitat over the same 28 features
  gbm        histogram gradient boosting over the same 28 features
  slope19    the single strongest supplied band (detrended-elevation slope)
  corridor   the lane's basement-step corridor x slope-ridge locator (H61-G X2)

Each is trained on the visible catalogue of the three quadrants outside the
scored one and scored on the fourth.  Writes evidence/h61m4_loqo.json.
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
from gems61 import h61m as M                         # noqa: E402
from gems61 import holdout_segmented as holdoutmod   # noqa: E402

import run_h61g as R                                 # noqa: E402
from run_h61m2 import train_gbm                      # noqa: E402
from run_h61m3 import emit_and_score, summarise      # noqa: E402

EVID = ROOT / "evidence"
CACHE = ROOT / ".cache" / "h61m"
EVALUATOR = R.EVALUATOR


def log(m):
    print(m, flush=True)


def main() -> int:
    t0 = time.time()
    g = gridmod.load_grid()
    grav = np.asarray(B.load_band(13), np.float64)
    valid = g.footprint & np.isfinite(grav)
    stack = np.asarray(np.load(CACHE / "stack.npy", mmap_mode="r"))
    names = json.loads((EVID / "h61m_features.json").read_text())["feature_names"]
    depth_fine = np.load(CACHE / "depth_fine.npy")
    hgm = np.load(CACHE / "hgm.npy")
    corridor = np.load(CACHE / "corridor.npy")
    basin = np.load(CACHE / "basin.npy")
    b19 = np.asarray(B.load_band(19), np.float64)

    ctx = holdoutmod.build_holdout(g, hide_frac=0.20, seeds=R.SEEDS, modes=("all",))
    from gems61.network import segments
    seg_cache = segments(g.catalogue, max_len_px=12)[0]
    quad = ctx.quad
    dom_total = float(sum(c.active.sum() for c in ctx.cells if c.seed == ctx.cells[0].seed))
    n_truth = sum(c.n_truth for c in ctx.cells)

    slope_rank = M._rank01(b19, valid).astype(np.float64)
    hgm_rank = M._rank01(hgm, valid).astype(np.float64)

    locators = ("logistic", "gbm", "slope19", "corridor")
    rows = {k: [] for k in locators}
    per_quad = {}

    for q, qname in enumerate(holdoutmod.FOLD_NAMES):
        outside = quad != q
        hidden_here = np.zeros(g.shape, bool)
        for c in ctx.cells:
            if c.fold == q:
                hidden_here |= ctx.hidden_by_cell[c.key]
        train_pos = g.catalogue & outside & ~hidden_here
        fields = {}
        for kind in ("logistic", "gbm"):
            fn = M.train_habitat if kind == "logistic" else train_gbm
            model, rec = fn(stack, valid, train_pos, names, seed=100 + q)
            fields[kind] = M.predict_habitat(model, stack, valid).astype(np.float32)
            del model
        fields["slope19"] = slope_rank.astype(np.float32)
        fields["corridor"] = (slope_rank * (1.0 + hgm_rank)).astype(np.float32)

        for kind in locators:
            oof = {c.key: fields[kind] for c in ctx.cells if c.fold == q}
            allowed_extra = None
            if kind == "corridor":
                allowed_extra = (corridor & basin)
            parts, rec_rows = [], []
            for cell in ctx.cells:
                if cell.fold != q:
                    continue
                sl = cell.bbox
                vis = ctx.visible(cell.key)[sl]
                far = ndi.distance_transform_edt(~vis) > 3.0
                allowed = cell.active & far
                if allowed_extra is not None:
                    allowed = allowed & allowed_extra[sl]
                b_cell = int(round(40000 * float(cell.active.sum()) / dom_total))
                p = oof[cell.key][sl].astype(np.float64)
                dots = M.dot_thin(p, allowed, b_cell, tile_px=3)
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
            s = summarise(parts, rec_rows, len(R.SEEDS))
            # spatially blocked canary for this locator
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
            auc = M.auc_rank(np.nan_to_num(fields[kind][py, px]), np.nan_to_num(fields[kind][ny, nx]))
            row = dict(locator=kind, quadrant=qname, loqo_canary_auc=auc,
                       loqo_pooled_dti=s["pooled_dti"], coverage=s["coverage"],
                       n_emitted_per_draw=s["n_emitted_per_draw"],
                       basin_interior=f"{s['segments_recovered_basin_interior']}/"
                                      f"{s['segments_withheld_basin_interior']}")
            rows[kind].append(row)
            per_quad.setdefault(qname, {})[kind] = row
            log(f"  {qname} {kind:10s} auc={auc:.3f} DTI={s['pooled_dti']:.4f} "
                f"cov={s['coverage']:.3f} n/draw={s['n_emitted_per_draw']:.0f} "
                f"basin {row['basin_interior']}")
        del fields

    summary = {}
    for kind in locators:
        rs = rows[kind]
        tp = sum(r["loqo_pooled_dti"] * 0 for r in rs)  # placeholder, pooled below
        summary[kind] = dict(
            mean_loqo_dti=float(np.mean([r["loqo_pooled_dti"] for r in rs])),
            min_loqo_dti=float(np.min([r["loqo_pooled_dti"] for r in rs])),
            max_loqo_dti=float(np.max([r["loqo_pooled_dti"] for r in rs])),
            mean_loqo_canary_auc=float(np.mean([r["loqo_canary_auc"] for r in rs])),
            mean_coverage=float(np.mean([r["coverage"] for r in rs])))
    R.write_json("h61m4_loqo.json", dict(
        evidence_class="MEASURED (spatially blocked generalisation test)",
        question="Which locator generalises to a quadrant with no training fault in it?",
        method="Leave-one-quadrant-out: train on the visible catalogue of the other three "
               "quadrants, score the fourth. 40 000 dots at 3 px spacing, 3 px catalogue prune, "
               "pooled DTI alpha 0.2 beta 0.8 R = 300 m.",
        evaluator=EVALUATOR, n_withheld_truth_px=int(n_truth),
        per_quadrant=per_quad, summary=summary,
        note="The non-spatially-blocked holdout (evidence/h61m_holdout.json, h61m2_holdout.json) "
             "over-rewards locators that sit next to visible traces, because the withheld "
             "segments are themselves adjacent to visible traces. The group's own "
             "organizer-scored pair (0.2600 -> 0.2778 by deleting every dot within 3 px of the "
             "catalogue) shows that adjacency does not pay on the live metric either, so the "
             "LOQO number is the one to trust for a slot decision."))
    log(json.dumps(summary, indent=1))
    log(f"done in {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
