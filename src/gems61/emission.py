"""Belief field -> binary emission (the metric-optimal shape).

The competition metric is a distance-weighted Tversky index; a graded probability
map is strictly dominated by its own thresholded support, so every candidate is
emitted as a binary 0/1 raster.  Emission here is a *budgeted non-maximum
thinning*: rank eligible pixels by belief, keep only local maxima within
``min_sep_px`` (so mass spreads along a ribbon instead of clumping on one step),
then take the top ``budget`` of them.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage


def thin(belief: np.ndarray, eligible: np.ndarray, min_sep_px: int,
         seed: int = 0) -> np.ndarray:
    """Local-maximum thinning of a belief field inside ``eligible``."""
    if min_sep_px <= 0:
        return eligible.copy()
    b = np.where(eligible, belief, -np.inf)
    size = 2 * int(min_sep_px) + 1
    mx = ndimage.maximum_filter(b, size=size, mode="constant", cval=-np.inf)
    rng = np.random.default_rng(seed)
    jitter = rng.random(belief.shape).astype(np.float64) * 1e-9
    return eligible & ((b + jitter) >= (mx + jitter))


def emit(belief: np.ndarray, eligible: np.ndarray, budget: int, min_sep_px: int,
         seed: int = 0) -> np.ndarray:
    """Top-``budget`` thinned pixels, as a boolean mask."""
    cand = thin(belief, eligible, min_sep_px, seed=seed)
    n = int(cand.sum())
    if n == 0:
        return np.zeros(belief.shape, bool)
    if n <= budget:
        return cand
    vals = np.where(cand, belief, -np.inf).ravel()
    # partial sort: the top `budget` values
    idx = np.argpartition(-vals, budget)[:budget]
    out = np.zeros(vals.size, bool)
    out[idx] = True
    return out.reshape(belief.shape)


def ribbon_emit(ribbon: np.ndarray, belief: np.ndarray, eligible: np.ndarray,
                budget: int, min_sep_px: int = 3, seed: int = 0) -> np.ndarray:
    """Emit along ribbon pixels only (multi-line ribbons, budgeted)."""
    return emit(belief, eligible & ribbon, budget, min_sep_px, seed=seed)
