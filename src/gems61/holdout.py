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
