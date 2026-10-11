"""Shared pooled hide-and-recover evaluator (gems61-pooled-hide-v2).

The DTI terms follow :mod:`gems61.metric` exactly: alpha=0.2, beta=0.8,
and a 300 m triangular kernel. Per-pixel TP/FN contributions are attributed to
the spatial block of their truth cell; FP contributions are attributed to the
block containing the emitted pixel. This makes the block terms additive and
keeps the pooled score exact while enabling paired resampling of 20 km blocks.

A pooled metric is evidence only when reported with this evaluator version,
the withheld-positive count, and the paired spatial-block 95% CI. Fold-local
scores are diagnostics and deliberately carry no standalone confidence claim.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

from . import metric
from .holdout import BLOCK_SIDE_PX

VERSION = "gems61-pooled-hide-v2"


def implementation_hashes() -> dict[str, str]:
    """SHA-256 the shared evaluator, fold, metric, and grid implementations."""
    root = Path(__file__).parent
    names = ("evaluate_holdout.py", "holdout.py", "metric.py", "grid.py")
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


def _validate_inputs(prediction, truth, valid=None, known=None):
    p = np.asarray(prediction, np.float64)
    g = np.asarray(truth, bool)
    v = np.ones(p.shape, bool) if valid is None else np.asarray(valid, bool)
    k = np.zeros(p.shape, bool) if known is None else np.asarray(known, bool)
    if p.ndim != 2 or any(a.shape != p.shape for a in (g, v, k)):
        raise ValueError("prediction, truth, valid and known must be matching 2-D arrays")
    if not np.isfinite(p).all() or (p < 0.0).any() or (p > 1.0).any():
        raise ValueError("predictions must be finite in [0,1] before masking")
    return p, g, v, k


def _aligned_terms(prediction, truth, active, block_side: int,
                   origin=(0, 0), global_shape=None) -> tuple[np.ndarray, dict]:
    """Compute exact DTI and additive terms on globally aligned spatial blocks."""
    p = np.asarray(prediction, np.float64)
    g = np.asarray(truth, bool) & np.asarray(active, bool)
    active = np.asarray(active, bool)
    if block_side <= 0:
        raise ValueError("block_side must be positive")
    h, w = p.shape
    oy, ox = map(int, origin)
    gh, gw = map(int, global_shape or (h + oy, w + ox))
    if oy < 0 or ox < 0 or oy + h > gh or ox + w > gw:
        raise ValueError("crop origin/global_shape do not contain the evaluation arrays")
    if not g.any():
        raise ValueError("holdout truth is empty")
    pp = np.where(active, p, 0.0)
    parts = metric.dti_exact(pp, g)
    credit, q, _ = metric.max_cover(pp, g)
    tp = float(credit.sum())
    fn = float(g.sum()) - tp
    fpw = float((pp * (1.0 - q)).sum())

    ncols = (gw + block_side - 1) // block_side
    nrows = (gh + block_side - 1) // block_side
    terms = np.zeros((nrows * ncols, 4), np.float64)
    yy, xx = np.nonzero(g)
    gy, gx = yy + oy, xx + ox
    truth_ids = (gy // block_side) * ncols + (gx // block_side)
    np.add.at(terms[:, 0], truth_ids, credit)
    np.add.at(terms[:, 2], truth_ids, 1.0 - credit)
    np.add.at(terms[:, 3], truth_ids, 1.0)
    py, px = np.nonzero(pp > 0.0)
    pred_ids = ((py + oy) // block_side) * ncols + ((px + ox) // block_side)
    np.add.at(terms[:, 1], pred_ids, pp[py, px] * (1.0 - q[py, px]))

    totals = terms.sum(axis=0)
    np.testing.assert_allclose(totals, [tp, fpw, fn, int(g.sum())], rtol=1e-11, atol=1e-7)
    dti = metric.dti_from_components(tp, fpw, fn)
    np.testing.assert_allclose(dti, parts["dti"], rtol=1e-11, atol=1e-12)
    info = dict(evidence_class="HOLDOUT-DTI", evaluator_version=VERSION,
                metric_scope="fold diagnostic; pooled score and spatial-block CI are reported separately",
                ci95=None, withheld_positive_count=int(g.sum()), n_truth=int(g.sum()),
                alpha=metric.ALPHA, beta=metric.BETA,
                triangular_radius_m=metric.R_M, tpw=tp, fpw=fpw, fnw=fn,
                n_emitted=int((pp > 0.0).sum()), dti=float(dti),
                coverage=float(tp / g.sum()),
                spatial_bootstrap_cluster_m=int(block_side * metric.PIXEL_M))
    return terms, info


def terms_for(prediction, truth, valid=None, known=None,
              block_side: int = BLOCK_SIDE_PX) -> tuple[np.ndarray, dict]:
    """Per-20-km-block ``(TP_w, FP_w, FN_w, withheld_positive_count)`` terms."""
    if block_side <= 0:
        raise ValueError("block_side must be positive")
    p, g, v, k = _validate_inputs(prediction, truth, valid, known)
    active = v & ~k
    return _aligned_terms(p, g, active, int(block_side), origin=(0, 0),
                          global_shape=p.shape)


def dti_from_terms(terms: np.ndarray) -> float:
    """Reconstruct the exact pooled DTI from additive block terms."""
    a = np.asarray(terms, np.float64)
    if a.ndim < 2 or a.shape[-1] != 4:
        raise ValueError("terms must have a final axis of (TP_w, FP_w, FN_w, n_truth)")
    tp, fp, fn = a[..., 0].sum(), a[..., 1].sum(), a[..., 2].sum()
    return metric.dti_from_components(float(tp), float(fp), float(fn))


def from_terms(terms: np.ndarray) -> np.ndarray:
    """DTI for one or more resampled aggregate term vectors."""
    a = np.asarray(terms, np.float64)
    if a.shape[-1] != 4:
        raise ValueError("terms must end in four additive components")
    tp, fp, fn = a[..., 0], a[..., 1], a[..., 2]
    den = tp + metric.ALPHA * fp + metric.BETA * fn + metric.EPS
    return np.divide(tp, den, out=np.zeros_like(tp), where=den > 0)


def _validate_arms(terms_by_arm: dict[str, np.ndarray]) -> tuple[dict[str, np.ndarray], np.ndarray]:
    if not terms_by_arm:
        raise ValueError("at least one candidate/control arm is required")
    arrays = {name: np.asarray(value, np.float64) for name, value in terms_by_arm.items()}
    first = next(iter(arrays.values()))
    if first.ndim != 2 or first.shape[1] != 4 or any(a.shape != first.shape for a in arrays.values()):
        raise ValueError("all arms need aligned (n_spatial_blocks, 4) term arrays")
    if any(not np.isfinite(a).all() or (a < -1e-8).any() for a in arrays.values()):
        raise ValueError("invalid or negative DTI terms")
    counts = [a[:, 3] for a in arrays.values()]
    if not np.allclose(counts[0], np.rint(counts[0]), rtol=0.0, atol=1e-8):
        raise ValueError("withheld-positive counts per block must be integers")
    if any(not np.array_equal(count, counts[0]) for count in counts[1:]):
        raise ValueError("candidate and controls must use identical withheld truth per block")
    return arrays, counts[0]


def pooled_summary(terms_by_arm: dict[str, np.ndarray], draws: int = 1000,
                   seed: int = 520810, candidate: str = "candidate") -> dict:
    """Pool first, then paired-bootstrap globally aligned 20 km spatial blocks."""
    if candidate not in terms_by_arm:
        raise ValueError("candidate arm missing")
    if int(draws) < 20:
        raise ValueError("at least 20 bootstrap draws are required")
    arrays, _ = _validate_arms(terms_by_arm)
    active = np.any(np.stack([np.abs(a).sum(axis=1) > 0 for a in arrays.values()]), axis=0)
    arrays = {name: a[active] for name, a in arrays.items()}
    n_blocks = int(active.sum())
    if n_blocks < 2:
        raise ValueError("need at least two nonempty spatial clusters for a CI")
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, n_blocks, size=(int(draws), n_blocks))
    boot = {name: from_terms(a[picks].sum(axis=1)) for name, a in arrays.items()}
    scores = {}
    for name, a in arrays.items():
        total = a.sum(axis=0)
        samples = boot[name]
        scores[name] = dict(
            evidence_class="HOLDOUT-DTI", evaluator_version=VERSION,
            dti=float(from_terms(total)),
            ci95=[float(v) for v in np.quantile(samples, [0.025, 0.975])],
            withheld_positive_count=int(round(total[3])),
            tpw=float(total[0]), fpw=float(total[1]), fnw=float(total[2]),
            n_spatial_blocks=n_blocks)
    controls = [name for name in arrays if name != candidate]
    best_control = max(controls, key=lambda name: scores[name]["dti"]) if controls else None
    paired = {}
    for name in controls:
        delta = boot[candidate] - boot[name]
        paired[name] = dict(
            evidence_class="HOLDOUT-DTI", evaluator_version=VERSION,
            delta=float(scores[candidate]["dti"] - scores[name]["dti"]),
            ci95=[float(v) for v in np.quantile(delta, [0.025, 0.975])],
            withheld_positive_count=scores[candidate]["withheld_positive_count"],
            candidate=candidate, reference=name)
    return dict(
        evidence_class="HOLDOUT-DTI", evaluator_version=VERSION,
        alpha=metric.ALPHA, beta=metric.BETA,
        triangular_kernel_radius_m=metric.R_M,
        pooled=True, scores=scores, best_comparable_control=best_control,
        paired_differences=paired,
        bootstrap=dict(method="paired percentile bootstrap of globally aligned 20 km blocks",
                       cluster_side_px=BLOCK_SIDE_PX,
                       cluster_size_m=BLOCK_SIDE_PX * metric.PIXEL_M,
                       clusters=n_blocks, draws=int(draws), seed=int(seed), confidence=0.95,
                       caveat=("Conditional on the fixed folds, candidate features and catalogue "
                               "truth; this is not an ORGANIZER-CONFIRMED score.")),
        implementation_sha256=implementation_hashes())


def pooled(terms_by_arm: dict[str, np.ndarray]) -> dict[str, float]:
    """Exact pooled DTI point estimates (no interval); diagnostics only."""
    arrays, _ = _validate_arms(terms_by_arm)
    return {name: dti_from_terms(value) for name, value in arrays.items()}


def bootstrap_paired(terms_by_arm: dict[str, np.ndarray], candidate: str,
                     reference: str | None = None, draws: int = 1000,
                     seed: int = 61011) -> dict:
    """Compatibility adapter returning scores plus paired candidate-reference CI."""
    summary = pooled_summary(terms_by_arm, draws=draws, seed=seed, candidate=candidate)
    out = {name: dict(dti=row["dti"], ci95=row["ci95"],
                      withheld_positive_count=row["withheld_positive_count"],
                      evidence_class=row["evidence_class"],
                      evaluator_version=row["evaluator_version"])
           for name, row in summary["scores"].items()}
    if reference is not None and reference in summary["paired_differences"]:
        row = summary["paired_differences"][reference]
        out[f"{candidate}_minus_{reference}"] = dict(
            mean=row["delta"], ci95=row["ci95"],
            p_ge_zero=float("nan"), withheld_positive_count=row["withheld_positive_count"],
            evidence_class=row["evidence_class"], evaluator_version=row["evaluator_version"])
    out["_meta"] = dict(evidence_class="HOLDOUT-DTI", evaluator_version=VERSION,
                        draws=int(draws), n_clusters=summary["bootstrap"]["clusters"],
                        block_side_px=BLOCK_SIDE_PX, seed=int(seed), confidence=0.95)
    return out


def _field(fold, key: str):
    if isinstance(fold, dict):
        if key in fold:
            return fold[key]
        aliases = {"region": ("domain",), "truth": ("hidden",),
                   "visible": ("masked_known",), "masked_known": ("visible",)}
        for alt in aliases.get(key, ()):
            if alt in fold:
                return fold[alt]
        raise KeyError(key)
    aliases = {"region": "domain", "truth": "hidden", "masked_known": "visible"}
    if hasattr(fold, key):
        return getattr(fold, key)
    if key in aliases and hasattr(fold, aliases[key]):
        return getattr(fold, aliases[key])
    raise AttributeError(key)


def evaluate(prediction, fold, valid, block_side: int = BLOCK_SIDE_PX, *,
             origin=(0, 0), global_shape=None) -> tuple[dict, np.ndarray]:
    """Evaluate one fold and return diagnostic DTI terms on common block coords."""
    p = np.asarray(prediction, np.float64)
    v = np.asarray(valid, bool)
    region = np.asarray(_field(fold, "region"), bool)
    known = np.asarray(_field(fold, "masked_known"), bool)
    truth = np.asarray(_field(fold, "truth"), bool)
    if p.ndim != 2 or any(a.shape != p.shape for a in (v, region, known, truth)):
        raise ValueError("fold/prediction grid shape mismatch")
    if not np.isfinite(p).all() or (p < 0.0).any() or (p > 1.0).any():
        raise ValueError("predictions must be finite in [0,1] before masking")
    active = v & region & ~known
    terms, info = _aligned_terms(p, truth, active, int(block_side),
                                 origin=origin, global_shape=global_shape)
    return info, terms


def auc(feature: np.ndarray, truth: np.ndarray, valid: np.ndarray,
        n_bg: int = 400000, seed: int = 0) -> float:
    """Rank-sum AUC leakage canary for one feature on withheld pixels.

    All positives are used; up to ``n_bg`` valid negatives are sampled without
    replacement. AUC >0.90 is a leakage-suspect result under the standing rule.
    """
    f = np.asarray(feature, np.float64)
    y = np.asarray(truth, bool)
    v = np.asarray(valid, bool)
    if f.ndim != 2 or f.shape != y.shape or f.shape != v.shape:
        raise ValueError("feature, truth and valid must be matching 2-D arrays")
    good = v & np.isfinite(f)
    pos = np.flatnonzero((y & good).ravel())
    neg_pool = np.flatnonzero((~y & good).ravel())
    if pos.size == 0 or neg_pool.size == 0:
        return float("nan")
    rng = np.random.default_rng(seed)
    n_neg = min(int(n_bg), int(neg_pool.size))
    if n_neg <= 0:
        return float("nan")
    neg = rng.choice(neg_pool, size=n_neg, replace=False)
    values = f.ravel()
    a, b = values[pos], values[neg]
    ranks = rankdata(np.concatenate([a, b]), method="average")
    n_pos = int(a.size)
    return float((ranks[:n_pos].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * b.size))
