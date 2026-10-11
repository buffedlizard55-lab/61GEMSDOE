"""Emission: from basement-step crests to a sparse binary dot field.

Why ribbons, and how many lines
-------------------------------
Gravity recovers a basement step only to a few hundred metres, so a single
1-px line would place the prediction at the *estimated* crest and lose the
kernel credit whenever the true step is more than ~150 m away.  Emitting
several parallel lines spaced by the kernel radius ``R = 3 px`` trades false
positive mass for positional insurance.

The exact arithmetic (``alpha = 0.2``, unit prediction, one truth pixel per
unit length of fault) makes the trade-off closed-form.  With a single line at
distance ``u`` the score is ``DTI = k`` with ``k = 1 - u/3``.  Adding a second
line at spacing ``s`` is profitable iff

    ``k_s > 1.2*k_0 - 0.2*k_0**2``

so the second line pays only where the first line is already weak
(``k_0 <~ 0.53``, i.e. ``u >~ 1.6 px``).  :func:`ribbon_gain_table` evaluates
this for a Gaussian positional error and is used to choose the number of lines
from the measured resolution instead of by taste.

Why dots
--------
A graded probability map is strictly dominated by its own thresholded support
under this metric, and redundant predictions inside one kernel cost
``alpha`` each while adding no new truth credit.  The crest lines are therefore
thinned to isolated dots at the kernel-radius spacing, which is the shape every
competitive artifact in this family has shipped.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import distance_transform_edt, maximum_filter

from .metric import RADIUS_PX


def disk(radius: float) -> np.ndarray:
    r = int(np.ceil(radius))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    return (xx * xx + yy * yy) <= radius * radius + 1e-9


def ribbon_mask(crest: np.ndarray, offsets_px=(0.0, 3.0, 6.0), band_half_width: float = 0.5):
    """Parallel copies of a 1-px crest line at ``offsets_px`` on *both* sides.

    Uses the unsigned Euclidean distance to the crest, so ``offset = 3`` emits
    one line 300 m to each side.  Returns ``(mask, distance_to_crest)``.
    """
    crest = np.asarray(crest, bool)
    if not crest.any():
        return np.zeros_like(crest), np.full(crest.shape, np.inf)
    d = distance_transform_edt(~crest)
    mask = np.zeros(crest.shape, bool)
    for o in offsets_px:
        if float(o) <= 0.0:
            mask |= crest
        else:
            mask |= np.abs(d - float(o)) <= band_half_width
    return mask, d


def nearest_crest_value(values: np.ndarray, crest: np.ndarray) -> np.ndarray:
    """Value of ``values`` at the nearest crest cell (0 off-crest is preserved)."""
    crest = np.asarray(crest, bool)
    if not crest.any():
        return np.zeros_like(values)
    _, (ny, nx) = distance_transform_edt(~crest, return_indices=True)
    return np.asarray(values)[ny, nx]


def thin_to_dots(mask: np.ndarray, score: np.ndarray, separation_px: float,
                 seed: int = 61011) -> np.ndarray:
    """Keep a maximal set of ``mask`` cells separated by ~``separation_px``.

    Implemented as local maxima of ``score`` under a disk maximum filter, with
    a deterministic sub-metre jitter so ties along a constant-throw crest break
    reproducibly.
    """
    mask = np.asarray(mask, bool)
    if not mask.any():
        return np.zeros_like(mask)
    rng = np.random.default_rng(seed)
    jitter = np.zeros(score.shape, np.float32)
    jitter[mask] = rng.random(int(mask.sum())).astype(np.float32)
    ranked = np.where(mask, np.asarray(score, np.float32) + 1e-3 * jitter, -np.inf)
    peak = maximum_filter(ranked, footprint=disk(separation_px), mode="constant", cval=-np.inf)
    return mask & (ranked >= peak)


def apply_budget(dots: np.ndarray, score: np.ndarray, budget: int) -> np.ndarray:
    """Keep the ``budget`` highest-scoring dots."""
    idx = np.flatnonzero(dots.ravel())
    if idx.size <= budget:
        return dots.astype(bool)
    s = np.asarray(score, np.float32).ravel()[idx]
    keep = idx[np.argsort(-s, kind="stable")[:int(budget)]]
    out = np.zeros(dots.size, bool)
    out[keep] = True
    return out.reshape(dots.shape)


def prune_near(dots: np.ndarray, target: np.ndarray, buffer_px: int) -> np.ndarray:
    """Delete dots within ``buffer_px`` of ``target`` (the mapped catalogue).

    A prediction on a mapped fault is masked out of every term of the official
    metric, so mass within the kernel of the catalogue is at best worthless.
    """
    if buffer_px <= 0:
        return dots
    target = np.asarray(target, bool)
    if not target.any():
        return dots
    d = distance_transform_edt(~target)
    return dots & (d > float(buffer_px))


def ribbon_gain_table(sigma_px=(1.0, 1.5, 2.0, 2.5, 3.0), spacings=(3.0,),
                      max_lines: int = 3, radius: float = RADIUS_PX,
                      n_samples: int = 120001) -> list[dict]:
    """Closed-form DTI of a multi-line ribbon under Gaussian positional error.

    One truth pixel per unit fault length, unit binary predictions, lines at
    ``0, +-s, +-2s, ...``; the true step sits at a Gaussian offset of
    ``sigma_px`` from the estimated crest.
    """
    u = np.abs(np.linspace(0.0, 6.0, n_samples))
    out = []
    for sigma in sigma_px:
        w = np.exp(-0.5 * (u / sigma) ** 2)
        w = w / w.sum()
        for s in spacings:
            for k in range(1, max_lines + 1):
                offsets = [round(i * s, 6) for i in range(-(k - 1), k)]
                offsets = sorted(set(offsets))
                kall = np.maximum(1.0 - np.abs(u[:, None] - np.array(offsets)[None, :]) / radius, 0.0)
                tp = kall.max(axis=1)                       # credit of the best line
                fp = (1.0 - kall).sum(axis=1)               # FP mass of all lines
                denom = tp + 0.2 * fp + 0.8
                dti = float((tp / denom * w).sum())
                single = np.maximum(1.0 - u / radius, 0.0)
                base = float(((single / (single + 0.2 * (1 - single) + 0.8)) * w).sum())
                out.append(dict(sigma_px=float(sigma), spacing_px=float(s), n_lines=k,
                                offsets_px=offsets, mean_dti=dti, single_line_dti=base,
                                gain_vs_single=dti - base,
                                emitted_lines_per_unit=float(k)))
    return out


# ---------------------------------------------------------------------------
# merged from the parallel lane on origin/main (names kept only where this
# module did not already define them)
# ---------------------------------------------------------------------------

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

