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


# ---------------------------------------------------------------------------
# merged from the parallel lane on origin/main (names kept only where this
# module did not already define them)
# ---------------------------------------------------------------------------

VERSION = 'gems61-pooled-hide-v2'


def evaluate(prediction, fold, valid, block_side=200, *, origin=(0, 0),
             global_shape=None):
    """Exact fold score plus additive terms on globally aligned spatial blocks.

    ``origin`` and ``global_shape`` locate a cropped fold in the common pixel
    grid. Pass them when combining terms from multiple crop windows; otherwise
    local block coordinates would not denote the same physical clusters.
    """
    if block_side <= 0:
        raise ValueError('block_side must be positive')
    p = np.asarray(prediction)
    if p.ndim != 2:
        raise ValueError('prediction must be a 2D array')
    if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
        raise ValueError('predictions must be finite in [0,1] before masking')
    valid = np.asarray(valid, bool)
    region = np.asarray(fold['region'], bool)
    # Shared-tool fix (session arena/d29229b5, 2026-10-11): the default argument of
    # dict.get() is evaluated eagerly, so the previous spelling raised KeyError
    # whenever a caller passed 'masked_known' without 'visible'.  Same semantics,
    # lazy lookup.
    known = np.asarray(fold['masked_known'] if 'masked_known' in fold else fold['visible'], bool)
    truth_all = np.asarray(fold['truth'], bool)
    if p.ndim != 2 or any(a.shape != p.shape for a in (valid, region, known, truth_all)):
        raise ValueError('fold/prediction grid shape mismatch')
    active = valid & region & ~known
    p = np.where(active, p, 0).astype(np.float64)
    truth = active & truth_all
    if not truth.any():
        raise ValueError('a holdout fold must contain positives')
    result = metric.dti_exact(p, truth, valid=active)
    covers, q, _ = metric.max_cover(p, truth)
    tpw = float(covers.sum())
    fpw = float((p * (1.0 - q)).sum())
    fnw = float(truth.sum()) - tpw
    h, w = truth.shape
    oy, ox = map(int, origin)
    gh, gw = map(int, global_shape or (h + oy, w + ox))
    if oy < 0 or ox < 0 or oy + h > gh or ox + w > gw:
        raise ValueError('crop origin/global_shape do not contain the evaluation arrays')
    ncols = (gw + block_side - 1) // block_side
    nrows = (gh + block_side - 1) // block_side
    terms = np.zeros((ncols * nrows, 4), np.float64)
    y, x = np.nonzero(truth)
    gy, gx = y + oy, x + ox
    ids = (gy // block_side) * ncols + (gx // block_side)
    for j, v in ((0, covers), (2, 1.0 - covers), (3, np.ones(len(y)))):
        terms[:, j] = np.bincount(ids, weights=v, minlength=len(terms))
    y, x = np.nonzero(p > 0)
    gy, gx = y + oy, x + ox
    ids = (gy // block_side) * ncols + (gx // block_side)
    terms[:, 1] = np.bincount(ids, weights=p[y, x].astype(float) * (1.0 - q[y, x]), minlength=len(terms))
    totals = terms.sum(axis=0)
    np.testing.assert_allclose(
        totals, [result['tp'], result['fp'], result['fn'], result['n_truth']],
        rtol=1e-11, atol=1e-7)
    result.update(tpw=result['tp'], fpw=result['fp'], fnw=result['fn'],
                  n_truth=int(truth.sum()), n_emitted=int((p > 0).sum()),
                  emitted=int((p > 0).sum()),
                  evidence_class='HOLDOUT-DTI', evaluator_version=VERSION,
                  spatial_bootstrap_cluster_m=block_side * metric.PIXEL_M)
    return result, terms


def from_terms(terms):
    a = np.asarray(terms, dtype=float)
    tp, fp, fn = a[..., 0], a[..., 1], a[..., 2]
    den = tp + metric.ALPHA * fp + metric.BETA * fn + metric.EPS
    return np.divide(tp, den, out=np.zeros_like(tp), where=den > 0)


def pooled_summary(terms_by_arm, draws=1000, seed=520810, candidate='disagreement'):
    """Pool terms first; paired percentile CI resamples physical 20 km blocks.

    Each arm has identical block coordinates/order and evaluation masks. Contributions
    from the same physical block across folds are merged BEFORE resampling, so overlap
    in a component tail is not mistaken for an independent new spatial cluster.
    """
    names = list(terms_by_arm)
    if not names or candidate not in terms_by_arm:
        raise ValueError('candidate and at least one arm required')
    if draws < 20:
        raise ValueError('too few bootstrap draws')
    arrays = {n: np.asarray(v, float) for n, v in terms_by_arm.items()}
    shape = next(iter(arrays.values())).shape
    if len(shape) != 2 or shape[1] != 4 or any(a.shape != shape for a in arrays.values()):
        raise ValueError('aligned per-spatial-block arrays of four terms required')
    if any(not np.isfinite(a).all() or (a < -1e-8).any() for a in arrays.values()):
        raise ValueError('invalid metric terms')
    truth_counts = [a[:, 3] for a in arrays.values()]
    reference_counts = truth_counts[0]
    if not np.allclose(reference_counts, np.rint(reference_counts), rtol=0.0, atol=1e-8):
        raise ValueError('spatial-block truth counts must be integers')
    if any(not np.array_equal(counts, reference_counts) for counts in truth_counts[1:]):
        raise ValueError('all candidate/control arms must use the same integer truth count per spatial block')
    # Include negative-only clusters carrying FP weight for any comparator.
    active = np.any(np.stack([a.sum(axis=1) > 0 for a in arrays.values()]), axis=0)
    arrays = {n: a[active] for n, a in arrays.items()}
    nb = int(active.sum())
    if nb < 2:
        raise ValueError('need at least two nonempty spatial clusters')
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, nb, size=(draws, nb))
    boot = {n: from_terms(a[picks].sum(axis=1)) for n, a in arrays.items()}
    summaries = {}
    for n, a in arrays.items():
        t = a.sum(axis=0)
        summaries[n] = dict(evidence_class='HOLDOUT-DTI', evaluator_version=VERSION,
            dti=float(from_terms(t)), ci95=[float(x) for x in np.quantile(boot[n], [.025, .975])],
            withheld_positive_pixels=int(round(t[3])), tpw=float(t[0]), fpw=float(t[1]), fnw=float(t[2]))
    controls = [n for n in names if n != candidate]
    best = max(controls, key=lambda n: summaries[n]['dti']) if controls else None
    differences = {}
    for n in controls:
        delta = boot[candidate] - boot[n]
        differences[n] = dict(evidence_class='HOLDOUT-DTI', evaluator_version=VERSION,
            delta=summaries[candidate]['dti'] - summaries[n]['dti'],
            ci95=[float(x) for x in np.quantile(delta, [.025, .975])],
            withheld_positive_pixels=summaries[candidate]['withheld_positive_pixels'])
    return dict(evidence_class='HOLDOUT-DTI', evaluator_version=VERSION,
        alpha=metric.ALPHA, beta=metric.BETA, triangular_radius_m=metric.R_M,
        pooled=True, scores=summaries, best_comparable_control=best,
        paired_differences=differences, bootstrap=dict(method='paired physical spatial-cluster percentile',
            clusters=nb, draws=draws, seed=seed, confidence=.95,
            caveat='Conditional on fitted folds, catalogue labels and fixed budgets; not a leaderboard interval.'),
        implementation_sha256=implementation_hashes())

