"""Hide-and-recover holdout + pooled distance-weighted Tversky index (DTI).

Protocol (from the run brief):
  * withhold *whole* catalogue fault segments (connected components) with a buffer;
  * derive every catalogue-based feature only from the *visible* faults;
  * mask visible fault pixels out of the scored domain;
  * score pooled DTI with alpha = 0.2, beta = 0.8 and a 300 m triangular kernel.

Metric, written out exactly (k(d) = max(1 - d/R, 0), R = 300 m):

    TP = sum_{g in truth} k(d(g, P))          truth coverage, each truth pixel once
    FN = |truth| - TP
    FP = sum_{p in pred} min(d(p, truth)/R, 1)
    DTI = TP / (TP + 0.2*FP + 0.8*FN)

The prediction-credit variant used by some earlier sessions is also returned
(``dti_pooled``) so that rankings can be checked for convention dependence.

This is a *proxy*: the live scorer's truth is expert-labelled faults that are not
in the catalogue, whereas this truth is a withheld subset of catalogue faults, i.e.
faults that were mappable from the surface.  Every number produced here is labelled
HOLDOUT-DTI and is never a score.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage

R_M = 300.0
RES = 100.0
ALPHA, BETA = 0.2, 0.8


def kernel(d_m: np.ndarray, R: float = R_M) -> np.ndarray:
    return np.clip(1.0 - d_m / R, 0.0, 1.0)


def dti(truth: np.ndarray, pred: np.ndarray, domain: np.ndarray,
        R: float = R_M, res: float = RES):
    """Return (dti_coverage, dti_pooled, parts) for binary masks on one grid."""
    T = truth & domain
    P = pred & domain
    n_truth = int(T.sum())
    n_pred = int(P.sum())
    if n_truth == 0 or n_pred == 0:
        return 0.0, 0.0, dict(TP=0.0, FP=float(n_pred), FN=float(n_truth),
                              n_truth=n_truth, n_pred=n_pred, mean_d=None)
    # distance from every truth pixel to the nearest prediction pixel
    d_pred = ndimage.distance_transform_edt(~P, sampling=res)
    d_truth = ndimage.distance_transform_edt(~T, sampling=res)
    k_truth = kernel(d_pred[T], R)
    k_pred = kernel(d_truth[P], R)
    TP = float(k_truth.sum())
    FN = n_truth - TP
    FP = float((1.0 - k_pred).sum())
    dti_cov = TP / (TP + ALPHA * FP + BETA * FN)
    dti_pool = float(k_pred.sum()) / (ALPHA * n_pred + BETA * n_truth)
    parts = dict(TP=TP, FP=FP, FN=FN, n_truth=n_truth, n_pred=n_pred,
                 mean_d=float(d_pred[T].mean()), med_d=float(np.median(d_pred[T])),
                 frac_truth_within_R=float((d_pred[T] <= R).mean()))
    return float(dti_cov), float(dti_pool), parts


def segments(catalogue: np.ndarray, min_px: int = 1) -> np.ndarray:
    """8-connected components of the catalogue = individual mapped fault segments."""
    lab, n = ndimage.label(catalogue, structure=np.ones((3, 3), bool))
    if min_px > 1:
        sizes = np.bincount(lab.ravel())
        keep = np.zeros(len(sizes), bool)
        keep[1:] = sizes[1:] >= min_px
        lab = np.where(keep[lab], lab, 0)
    return lab


@dataclass
class Fold:
    name: str
    hidden: np.ndarray       # withheld truth (segment pixels)
    visible: np.ndarray      # visible catalogue pixels (masked from scoring)
    domain: np.ndarray       # scored domain
    n_segments: int = 0


def make_folds(footprint: np.ndarray, catalogue: np.ndarray, n_folds: int = 4,
               collar_px: int = 3, min_px: int = 20, seed: int = 0) -> list[Fold]:
    """Spatially-blocked folds: whole segments are withheld, never split.

    Blocks are quadrants of the grid so that a withheld fold is a contiguous region
    (spatial blocking), which is the honest generalisation test for a geophysical
    surface that has kilometre-scale autocorrelation.
    """
    lab = segments(catalogue, min_px=min_px)
    ids = np.unique(lab[lab > 0])
    H, W = footprint.shape
    com = ndimage.center_of_mass(np.ones_like(lab, dtype=np.float64), lab, list(ids))
    cy = np.array([c[0] for c in com])
    cx = np.array([c[1] for c in com])
    if n_folds == 4:
        quad = ((cy >= H / 2).astype(int) * 2) + (cx >= W / 2).astype(int)
        assign = {0: "NW", 1: "NE", 2: "SW", 3: "SE"}
        fold_of = np.array([assign[q] for q in quad])
    else:
        rng = np.random.default_rng(seed)
        perm = rng.permutation(n_folds)
        fold_of = perm[np.arange(len(ids)) % n_folds]
    st = ndimage.generate_binary_structure(2, 2)
    folds = []
    for f in np.unique(fold_of):
        sel = np.isin(lab, ids[fold_of == f])
        hidden = sel & catalogue
        visible = catalogue & ~hidden
        collar = ndimage.binary_dilation(visible, st, iterations=collar_px)
        domain = footprint & ~collar
        folds.append(Fold(name=str(f), hidden=hidden, visible=visible, domain=domain,
                          n_segments=int((fold_of == f).sum())))
    return folds


def segment_recovery(pred: np.ndarray, folds: list[Fold], R: float = R_M,
                     res: float = RES, restrict: np.ndarray | None = None):
    """Fraction of withheld segments with >= 1 prediction within R metres."""
    out = {}
    for fo in folds:
        hidden = fo.hidden if restrict is None else (fo.hidden & restrict)
        lab = segments(hidden, min_px=1)
        ids = np.unique(lab[lab > 0])
        if len(ids) == 0:
            out[fo.name] = dict(n=0, recovered=0, frac=0.0)
            continue
        d = ndimage.distance_transform_edt(~(pred & fo.domain), sampling=res)
        hits = ndimage.minimum(d, lab, ids)
        out[fo.name] = dict(n=len(ids), recovered=int((np.array(hits) <= R).sum()),
                            frac=float((np.array(hits) <= R).mean()))
    return out


def random_lines(shape, n_px: int, domain: np.ndarray, rng, seg_len=(8, 40)):
    """Control: random straight segments until the pixel budget is spent."""
    H, W = shape
    out = np.zeros(shape, bool)
    drawn = 0
    guard = 0
    while drawn < n_px and guard < 200000:
        guard += 1
        L = int(rng.integers(*seg_len))
        y0 = float(rng.integers(0, H)); x0 = float(rng.integers(0, W))
        th = rng.uniform(0, np.pi)
        yy = np.clip(np.round(y0 + np.arange(L) * np.sin(th)).astype(int), 0, H - 1)
        xx = np.clip(np.round(x0 + np.arange(L) * np.cos(th)).astype(int), 0, W - 1)
        out[yy, xx] = True
        drawn += L
    out &= domain
    return out


def auc(score: np.ndarray, labels: np.ndarray, n_bg: int = 400000, seed=0) -> float:
    """AUC of ``score`` for separating label pixels from random background pixels."""
    rng = np.random.default_rng(seed)
    pos = np.flatnonzero(labels.ravel())
    neg_pool = np.flatnonzero((~labels).ravel())
    if len(pos) == 0 or len(neg_pool) == 0:
        return float("nan")
    neg = rng.choice(neg_pool, size=min(n_bg, len(neg_pool)), replace=False)
    s = score.ravel()
    a = s[pos]; b = s[neg]
    a = a[np.isfinite(a)]; b = b[np.isfinite(b)]
    if len(a) == 0 or len(b) == 0:
        return float("nan")
    from scipy.stats import rankdata

    allv = np.concatenate([a, b])
    ranks = rankdata(allv, method="average")
    ra = ranks[: len(a)].sum()
    return float((ra - len(a) * (len(a) + 1) / 2.0) / (len(a) * len(b)))
