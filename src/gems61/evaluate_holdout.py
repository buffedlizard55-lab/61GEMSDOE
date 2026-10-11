"""Pooled hide-and-recover evaluator.

Score is the exact official distance-weighted Tversky index
(``alpha = 0.2``, ``beta = 0.8``, 300 m triangular kernel) computed by
:mod:`gems61.metric`.  Terms are accumulated per 20 km spatial block so the
confidence interval resamples *faults*, not pixels.

Additivity
----------
``TP_w`` and ``FN_w`` are sums over truth pixels and attribute to a block
trivially.  ``FP_w = sum_x p(x) (1 - max_g k(d(x,g)))`` is not a per-truth
quantity, so each emitted cell's false-positive weight is attributed to the
block of the truth pixel that gives it its maximal kernel credit.  Every cell's
weight then lands in exactly one block and the block totals reproduce the
global DTI exactly (asserted in :func:`terms_for`).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt
from scipy.stats import rankdata

from . import metric
from .holdout import BLOCK_SIDE_PX

VERSION = "gems61-pooled-hide-v1"


def implementation_hashes() -> dict[str, str]:
    return {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
            for name in ("evaluate_holdout.py", "holdout.py", "metric.py", "grid.py")}


def terms_for(prediction, truth, valid=None, known=None, block_side: int = BLOCK_SIDE_PX):
    """Per-spatial-block ``(tp, fp, fn, n_truth)`` for one prediction/truth pair."""
    p = np.asarray(prediction, np.float64)
    truth = np.asarray(truth, bool)
    valid_ = np.ones(p.shape, bool) if valid is None else np.asarray(valid, bool)
    known_ = np.zeros(p.shape, bool) if known is None else np.asarray(known, bool)
    if p.shape != truth.shape or p.shape != valid_.shape:
        raise ValueError("grid shape mismatch")
    if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
        raise ValueError("predictions must be finite in [0,1] before masking")
    active = valid_ & ~known_
    pp = np.where(active, p, 0.0)
    g = active & truth
    yy, xx = np.nonzero(g)
    n = int(yy.size)
    if n == 0:
        raise ValueError("holdout truth is empty")
    credit, q, _ = metric.max_cover(pp, g)
    tp = float(credit.sum())
    fn = float(n) - tp

    h, w = p.shape
    block_id_truth = (yy // block_side) * ((w + block_side - 1) // block_side) + (xx // block_side)
    n_blocks = ((h + block_side - 1) // block_side) * ((w + block_side - 1) // block_side)
    terms = np.zeros((n_blocks, 4), np.float64)
    np.add.at(terms, (block_id_truth, 0), credit)
    np.add.at(terms, (block_id_truth, 2), 1.0 - credit)
    np.add.at(terms, (block_id_truth, 3), 1.0)

    py, px = np.nonzero(pp > 0)
    fpw = pp[py, px] * (1.0 - q[py, px])
    # Attribute each emitted cell's FP weight to the block of the truth pixel
    # that gives it its maximal kernel credit, i.e. the nearest truth pixel.
    ncols = (w + block_side - 1) // block_side
    _, (ny, nx) = distance_transform_edt(~g, return_indices=True)
    nearest_block = (ny[py, px] // block_side) * ncols + (nx[py, px] // block_side)
    np.add.at(terms, (nearest_block, 1), fpw)

    totals = terms.sum(axis=0)
    assert abs(totals[0] - tp) < 1e-6, (totals[0], tp)
    assert abs(totals[1] - float(fpw.sum())) < 1e-6
    assert abs(totals[2] - fn) < 1e-6
    assert abs(totals[3] - n) < 1e-9
    return terms, dict(tpw=tp, fpw=float(fpw.sum()), fnw=fn, n_truth=n,
                       n_emitted=int((pp > 0).sum()),
                       dti=metric.dti_from_components(tp, float(fpw.sum()), fn),
                       coverage=tp / n)


def dti_from_terms(terms: np.ndarray) -> float:
    a = np.asarray(terms, np.float64)
    tp, fp, fn = a[..., 0].sum(), a[..., 1].sum(), a[..., 2].sum()
    return metric.dti_from_components(tp, fp, fn)


def pooled(terms_by_arm: dict[str, np.ndarray]) -> dict[str, float]:
    return {name: dti_from_terms(t) for name, t in terms_by_arm.items()}


def bootstrap_paired(terms_by_arm: dict[str, np.ndarray], candidate: str,
                     reference: str | None = None, draws: int = 2000,
                     seed: int = 61011) -> dict:
    """Paired block bootstrap; returns the candidate CI and paired differences."""
    if candidate not in terms_by_arm:
        raise ValueError("candidate missing")
    arrays = {n: np.asarray(t, np.float64) for n, t in terms_by_arm.items()}
    shape = next(iter(arrays.values())).shape
    if any(a.shape != shape for a in arrays.values()):
        raise ValueError("all arms must share block coordinates")
    counts = [a[:, 3] for a in arrays.values()]
    if any(not np.array_equal(c, counts[0]) for c in counts[1:]):
        raise ValueError("all arms must share the integer truth count per block")
    active = np.any(np.stack([a.sum(axis=1) > 0 for a in arrays.values()]), axis=0)
    arrays = {n: a[active] for n, a in arrays.items()}
    nb = int(active.sum())
    if nb < 2:
        raise ValueError("need at least two nonempty spatial clusters")
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, nb, size=(draws, nb))
    out: dict[str, dict] = {}
    samples = {}
    for name, a in arrays.items():
        s = a[picks].sum(axis=1)                     # (draws, 4)
        dti = s[:, 0] / (s[:, 0] + metric.ALPHA * s[:, 1] + metric.BETA * s[:, 2] + metric.EPS)
        samples[name] = dti
        out[name] = dict(dti=float(dti_from_terms(a)),
                         ci95=[float(np.percentile(dti, 2.5)), float(np.percentile(dti, 97.5))])
    if reference is not None and reference in samples:
        diff = samples[candidate] - samples[reference]
        out[f"{candidate}_minus_{reference}"] = dict(
            mean=float(diff.mean()),
            ci95=[float(np.percentile(diff, 2.5)), float(np.percentile(diff, 97.5))],
            p_ge_zero=float((diff >= 0).mean()))
    out["_meta"] = dict(evaluator_version=VERSION, draws=draws, n_clusters=nb,
                        block_side_px=int(BLOCK_SIDE_PX), seed=seed,
                        evidence_class="HOLDOUT-DTI")
    return out


def auc(feature: np.ndarray, truth: np.ndarray, valid: np.ndarray) -> float:
    """Rank-sum AUC of one feature against the holdout truth (leakage canary)."""
    f = np.asarray(feature, np.float64)[valid]
    y = np.asarray(truth, bool)[valid]
    n_pos = int(y.sum())
    n_neg = int((~y).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    ranks = rankdata(f)          # average ranks; ties share the mean rank
    return float((ranks[y].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))
