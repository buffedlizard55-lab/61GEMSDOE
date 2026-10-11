"""Hide-and-recover holdout: withhold whole mapped-fault segments with a
context buffer, and score against the withheld pixels.

Design (fixed before any result is looked at)
---------------------------------------------
* The catalogue is split into 8-connected **components** (physical fault
  segments).  A seeded random 20 % of components is withheld *whole* -- a
  segment is never split, so no part of a withheld fault can be inferred from
  its own continuation.
* A 3 px (300 m) **buffer** around each withheld segment removes the adjacent
  catalogue pixels from the *visible* set as well.  This is the context buffer:
  the visible catalogue that would otherwise point straight at the withheld
  segment is not available.  (This lane uses no catalogue-derived feature at
  all, so the buffer is a conservative extra, not a repair.)
* Scoring follows the live setting: ``active = footprint & ~visible``. Mass
  placed on a *visible* catalogue pixel is masked out of every metric term --
  exactly what the organiser does with mapped faults -- and the withheld
  segments are the only truth.
* Pooled over four spatially blocked folds; the confidence interval comes from
  resampling 20 km spatial blocks, so a single long fault is one cluster and
  not hundreds of independent pixels.

Limitation carried explicitly: this instrument's truth is *catalogue* pixels,
whereas the live truth is faults the catalogue does not contain.  It is a
screen and a leakage canary, never a leaderboard estimate (see the run card).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import binary_dilation, distance_transform_edt, label

BLOCK_SIDE_PX = 200          # 20 km spatial clusters for the bootstrap


@dataclass(frozen=True)
class Fold:
    name: str
    region: np.ndarray        # bool, scored region of this fold
    truth: np.ndarray         # bool, withheld segment pixels (global)
    visible: np.ndarray       # bool, catalogue pixels that remain visible (masked from scoring)
    hidden_ids: np.ndarray
    n_truth: int


STRUCT8 = np.ones((3, 3), bool)


def catalogue_components(catalogue: np.ndarray) -> tuple[np.ndarray, int]:
    """8-connected components of the mapped-fault catalogue."""
    lab, n = label(np.asarray(catalogue, bool), structure=STRUCT8)
    return lab, int(n)


def make_folds(catalogue: np.ndarray, footprint: np.ndarray, fraction: float = 0.20,
               buffer_px: int = 3, seed: int = 20261011, n_folds: int = 4) -> list[Fold]:
    """Withhold whole components and split the result into spatial folds."""
    lab, n = catalogue_components(catalogue)
    if n == 0:
        raise ValueError("empty catalogue")
    rng = np.random.default_rng(seed)
    ids = rng.permutation(np.arange(1, n + 1))
    n_hide = max(1, int(round(fraction * n)))
    hidden_ids = np.sort(ids[:n_hide])
    hidden = np.isin(lab, hidden_ids)

    buffer = binary_dilation(hidden, structure=STRUCT8, iterations=int(buffer_px))
    visible = (catalogue & ~buffer)

    h, w = footprint.shape
    # The four quadrants partition the WHOLE grid: 2 row bands x 2 column bands.
    # (Splitting the rows into ``n_folds`` bands and then using only the first
    # two would leave the southern half of the grid inside no fold at all, so
    # half the catalogue could never be withheld.  That bug is pinned by
    # tests/test_holdout.py::test_folds_cover_the_whole_grid.)
    if n_folds == 2:
        quadrants = [("N", np.arange(h)[: h // 2], np.arange(w)),
                     ("S", np.arange(h)[h // 2:], np.arange(w))]
    else:
        fold_rows = np.array_split(np.arange(h), 2)
        fold_cols = np.array_split(np.arange(w), 2)
        quadrants = [("NW", fold_rows[0], fold_cols[0]), ("NE", fold_rows[0], fold_cols[1]),
                     ("SW", fold_rows[1], fold_cols[0]), ("SE", fold_rows[1], fold_cols[1])]

    folds = []
    for name, rows, cols in quadrants:
        region = np.zeros(footprint.shape, bool)
        region[np.ix_(rows, cols)] = True
        region &= footprint
        truth = hidden & region
        if not truth.any():
            continue
        folds.append(Fold(name=name, region=region, truth=truth, visible=visible,
                          hidden_ids=hidden_ids, n_truth=int(truth.sum())))
    if not folds:
        raise ValueError("no fold contains withheld positives")
    return folds


def basin_interior_mask(depth: np.ndarray, valid: np.ndarray,
                        depth_quantile: float = 0.60) -> np.ndarray:
    """Cells under thick cover (deep basement) -- the 'buried' domain.

    The lane's target population is faults concealed by alluvium, so the
    lane-specific recovery test is restricted to withheld segments that sit in
    the deep half of the basement-depth distribution.
    """
    d = np.asarray(depth, np.float64)
    m = np.asarray(valid, bool) & np.isfinite(d)
    thr = float(np.quantile(d[m], depth_quantile))
    return m & (d >= thr)


def distance_to_mask(mask: np.ndarray) -> np.ndarray:
    """Euclidean distance (px) to the nearest True cell; +inf for an empty mask."""
    mask = np.asarray(mask, bool)
    if not mask.any():
        return np.full(mask.shape, np.inf)
    return distance_transform_edt(~mask)


# ---------------------------------------------------------------------------
# merged from the parallel lane on origin/main (names kept only where this
# module did not already define them)
# ---------------------------------------------------------------------------

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

