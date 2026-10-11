"""H61-G: basement-step corridors from gravity inversion, with the step located
inside the corridor by the only 100 m layer that can see a scarp.

Why this exists (the physics, then the metric)
----------------------------------------------
A buried normal fault puts a step in the basement surface.  The step is visible
in isostatic residual gravity as a horizontal-gradient maximum (Blakely &
Simpson 1986) of the inverted basin-depth surface (Parker 1973 / Oldenburg 1974;
Blakely & Jachens 1991; Saltus & Jachens 1995, GP-1012).  But the gravity grid
supplied with the competition resolves such a step only to ~1 km (measured here:
the depth-HGM maxima are *not* enriched within 300 m of mapped faults, see
``evidence/h61g_screen.json``), while the scoring kernel is 300 m wide.  So a
gravity step can say *where to look* but not *where to put the dot*.

The one supplied layer that does carry 300 m positional information in basins
is the slope of the detrended elevation (band 19): an active intrabasin fault
with basement throw propagates up through the fill and produces a subtle,
young scarp at the surface.  H61-G therefore uses the gravity step as a
**corridor prior** (+/- ``CORRIDOR_PX`` of the step line) and places dots on the
slope-maxima ridges *inside* the corridor.  The competing explanation --
density contrasts inside the basement -- produces a gravity step with **no**
surface scarp above it, so the corridor x slope-maximum conjunction is exactly
the test that discriminates a buried fault from an intrabasement contact.

Everything is derived from the pinned feature stack; the mapped catalogue is
used only as an exclusion mask (dots on or next to mapped traces are worthless
because the scored truth is the set of *unmapped* faults) and, in the
hide-and-recover holdout, only its *visible* part is used for that mask.
"""

from __future__ import annotations

import math

import numpy as np
from scipy import ndimage as ndi

from . import buried as B
from .lane61 import decimate_mean, upsample_bilinear

LANE_DECIMATION = 4            # inversion grid: 400 m
CORRIDOR_PX = 10               # +/- 1 km around a basement-step line (100 m px)
MIN_THROW_M = 80.0             # minimum depth difference across one 400 m cell pair
BASIN_FLOOR_M = 100.0          # "basin interior" = inverted depth above this
REGIONAL_SIGMA_KM = 15.0       # regional/residual separation before the slab inversion


# --------------------------------------------------------------------------- #
# 1. Inversion of the supplied isostatic gravity for depth to basement
# --------------------------------------------------------------------------- #
def invert_basement(grav_full: np.ndarray, valid_full: np.ndarray, *,
                    regional_sigma_km: float = REGIONAL_SIGMA_KM,
                    candidates=(-300.0, -350.0, -400.0, -450.0, -500.0, -600.0),
                    z0_candidates=(300.0, 400.0, 500.0, 700.0),
                    kc_scales=(0.5, 0.25, 0.125)) -> dict:
    """Band-pass the isostatic residual, then run the GP-1012-calibrated slab
    inversion on a 400 m grid.

    Blakely & Jachens (1991) separate a smooth *basement* gravity field from the
    short-wavelength *basin* field before inverting.  Without station locations
    on bedrock the separation is done here by a Gaussian regional of
    ``regional_sigma_km`` (wavelengths much longer than any single basin).  The
    density contrast, the reference level and the low-pass corner are then
    chosen by :func:`gems61.buried.calibrate_density_scale` against the only
    external anchor the lane allows -- the published statewide depth scale.
    Positive residuals are basement at the surface, so depth is floored at 0.
    """
    dx = B.PIXEL_M * LANE_DECIMATION
    small = decimate_mean(np.where(valid_full & np.isfinite(grav_full), grav_full, np.nan),
                          LANE_DECIMATION)
    valid = np.isfinite(small)
    filled = B.inpaint_smooth(small, valid)
    sig_px = regional_sigma_km * 1000.0 / dx
    regional = ndi.gaussian_filter(filled, sig_px, mode="nearest") if sig_px > 0 else 0.0
    resid = filled - regional
    calib = B.calibrate_density_scale(resid, valid, dx=dx, candidates=candidates,
                                      kc_scales=kc_scales, z0_candidates=z0_candidates)
    best = calib["best"]
    sol = B.slab_solution(resid, valid, best["delta_rho"], best["z0_m"], dx=dx,
                          kc_scale=best["kc_scale"])
    depth = np.clip(np.asarray(sol["depth_m"], np.float64), 0.0, 8000.0)
    depth[~valid] = np.nan
    return dict(depth_small=depth, valid_small=valid, resid_small=resid, dx=dx,
                calibration=dict(best=best, anchors=calib["anchors"], source=calib["source"],
                                 n_combinations=len(calib["table"])),
                inversion=dict(stage=sol["stage"], filter=sol["filter"],
                               rms_residual_mgal=sol["rms_residual_mgal"],
                               delta_rho=sol["delta_rho"], z0_m=sol["z0_m"],
                               regional_sigma_km=regional_sigma_km,
                               source_doi=sol["source_doi"]))


# --------------------------------------------------------------------------- #
# 2. Steps in the basement surface
# --------------------------------------------------------------------------- #
def basement_steps(depth_small: np.ndarray, dx: float, *, smooth_px: float = 0.0,
                   min_throw_m: float = MIN_THROW_M) -> dict:
    """Blakely-Simpson maxima of |grad depth| with a measured throw filter.

    ``throw`` is the depth range across the 3 x 3 neighbourhood of the maximum
    (one cell either side at ``dx``), i.e. the displacement the step would have
    if it were a single fault.  A maximum below ``min_throw_m`` is a ramp, not a
    step, and is dropped.
    """
    d = np.asarray(depth_small, np.float64)
    finite = np.isfinite(d)
    work = B.inpaint_smooth(d, finite)
    if smooth_px > 0:
        work = ndi.gaussian_filter(work, smooth_px, mode="nearest")
    hgm = B.horizontal_gradient_magnitude(np.where(finite, work, np.nan), dx)
    mx = B.blakely_simpson_maxima(hgm) & finite
    throw = B.step_magnitude(np.where(finite, work, np.nan), mx, window_px=1)
    keep = mx & np.isfinite(throw) & (throw >= min_throw_m)
    return dict(hgm=hgm, maxima=mx, throw=throw, steps=keep,
                n_maxima=int(mx.sum()), n_steps=int(keep.sum()))


def persistent_steps(depth_small: np.ndarray, dx: float, *, scales_px=(0.0, 2.0, 5.0),
                     tol_px=(0, 2, 3), min_throw_m: float = MIN_THROW_M) -> dict:
    """Steps that survive smoothing of the depth surface (Hornby et al. 1999 'worms'
    in spirit): a maximum at the finest scale is kept only if a maximum exists
    within ``tol_px[i]`` at every coarser scale ``scales_px[i]``."""
    base = basement_steps(depth_small, dx, smooth_px=scales_px[0], min_throw_m=min_throw_m)
    keep = base["steps"].copy()
    for s, tol in zip(scales_px[1:], tol_px[1:]):
        coarse = basement_steps(depth_small, dx, smooth_px=s, min_throw_m=min_throw_m)["steps"]
        near = ndi.distance_transform_edt(~coarse) <= tol
        keep &= near
    return dict(steps=keep, n_steps=int(keep.sum()), base=base)


def to_full_grid(mask_small: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """Nearest-neighbour upsample of a 400 m boolean mask to the 100 m grid."""
    m = np.asarray(mask_small, bool)
    up = np.repeat(np.repeat(m, LANE_DECIMATION, axis=0), LANE_DECIMATION, axis=1)
    out = np.zeros(shape, bool)
    h = min(shape[0], up.shape[0]); w = min(shape[1], up.shape[1])
    out[:h, :w] = up[:h, :w]
    return out


def field_to_full_grid(field_small: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    f = np.asarray(field_small, np.float64)
    f = np.where(np.isfinite(f), f, np.nanmean(f))
    return upsample_bilinear(f, shape)


# --------------------------------------------------------------------------- #
# 3. Corridor and in-corridor locator
# --------------------------------------------------------------------------- #
def corridor_mask(steps_full: np.ndarray, px: int = CORRIDOR_PX) -> np.ndarray:
    return ndi.distance_transform_edt(~np.asarray(steps_full, bool)) <= px


def slope_ridges(slope_full: np.ndarray, valid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Blakely-Simpson maxima of the detrended-elevation slope (band 19): the
    100 m expression of a scarp.  Returns (ridge mask, slope value)."""
    s = np.asarray(slope_full, np.float64)
    filled = np.where(valid & np.isfinite(s), s, np.nan)
    filled = np.where(np.isfinite(filled), filled, np.nanmedian(filled))
    mx = B.blakely_simpson_maxima(filled) & valid
    return mx, filled


def rank01(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Rank-normalise ``values`` inside ``mask`` to (0, 1]; 0 elsewhere."""
    out = np.zeros(values.shape, np.float32)
    idx = np.flatnonzero(mask.ravel())
    if idx.size == 0:
        return out
    v = values.ravel()[idx]
    order = np.argsort(v, kind="stable")
    r = np.empty(idx.size, np.float32)
    r[order] = (np.arange(1, idx.size + 1, dtype=np.float32)) / np.float32(idx.size)
    out.ravel()[idx] = r
    return out


def dot_thin(score: np.ndarray, allowed: np.ndarray, budget: int, tile_px: int = 3) -> np.ndarray:
    """At most one dot per ``tile_px`` x ``tile_px`` tile at the tile's argmax of
    ``score``; the ``budget`` highest tiles are emitted.  This is the spacing
    at which two binary dots stop duplicating each other's kernel credit."""
    s = np.where(allowed, np.asarray(score, np.float32), 0.0).astype(np.float32)
    H, W = s.shape
    ph, pw = (-H) % tile_px, (-W) % tile_px
    padded = np.pad(s, ((0, ph), (0, pw)))
    th, tw = padded.shape[0] // tile_px, padded.shape[1] // tile_px
    tiles = padded.reshape(th, tile_px, tw, tile_px).transpose(0, 2, 1, 3).reshape(th * tw, -1)
    tmax = tiles.max(axis=1)
    targ = tiles.argmax(axis=1)
    ids = np.flatnonzero(tmax > 0)
    order = ids[np.argsort(-tmax[ids], kind="stable")][: int(budget)]
    ay = (order // tw) * tile_px + targ[order] // tile_px
    ax = (order % tw) * tile_px + targ[order] % tile_px
    keep = (ay < H) & (ax < W)
    out = np.zeros(s.shape, bool)
    out[ay[keep], ax[keep]] = True
    return out & allowed


def ribbon(dots: np.ndarray, half_width_px: int = 1) -> np.ndarray:
    """8-neighbour dilation of a dot field into a (2w+1)-cell ribbon."""
    return ndi.binary_dilation(np.asarray(dots, bool), np.ones((3, 3), bool),
                               iterations=int(half_width_px)) if half_width_px > 0 else dots.copy()


# --------------------------------------------------------------------------- #
# 4. Controls
# --------------------------------------------------------------------------- #
def random_lines(shape, allowed, n_dots, seed=61, length_px=40, spacing_px=3) -> np.ndarray:
    """Random straight dotted lines inside ``allowed`` at an exact pixel budget.

    The original helper rescanned the full raster with ``out.sum()`` after every
    dot, which made large null controls needlessly quadratic. Track newly set
    cells incrementally, handle an empty domain, and fill the final remainder
    from allowed cells only if line collisions prevent the exact budget.
    """
    allowed = np.asarray(allowed, bool)
    if allowed.ndim != 2 or tuple(shape) != allowed.shape:
        raise ValueError("shape and allowed domain must be matching 2-D arrays")
    out = np.zeros(shape, bool)
    ys, xs = np.nonzero(allowed)
    target = min(max(0, int(n_dots)), int(ys.size))
    if target == 0:
        return out
    rng = np.random.default_rng(seed)
    count = 0
    guard = 0
    max_guard = max(1000, 100 * target)
    while count < target and guard < max_guard:
        guard += 1
        i = int(rng.integers(ys.size))
        y0, x0 = int(ys[i]), int(xs[i])
        th = rng.uniform(0, np.pi)
        for t in range(0, length_px, spacing_px):
            y = y0 + int(round(t * np.sin(th)))
            x = x0 + int(round(t * np.cos(th)))
            if (0 <= y < shape[0] and 0 <= x < shape[1]
                    and allowed[y, x] and not out[y, x]):
                out[y, x] = True
                count += 1
                if count >= target:
                    break
    if count < target:
        remaining = np.flatnonzero(allowed & ~out)
        pick = rng.choice(remaining, size=target - count, replace=False)
        out.ravel()[pick] = True
    return out


def random_dots(allowed, n_dots, seed=62) -> np.ndarray:
    rng = np.random.default_rng(seed)
    idx = np.flatnonzero(allowed.ravel())
    pick = rng.choice(idx, size=min(int(n_dots), idx.size), replace=False)
    out = np.zeros(allowed.shape, bool)
    out.ravel()[pick] = True
    return out


# --------------------------------------------------------------------------- #
# 5. Statistics helpers
# --------------------------------------------------------------------------- #
def wilson(k: float, n: float, z: float = 1.959963985) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def auc_rank(pos: np.ndarray, neg: np.ndarray) -> float:
    """Mann-Whitney AUC via ranks (ties averaged)."""
    from scipy.stats import rankdata
    a = np.concatenate([pos, neg])
    r = rankdata(a)
    n1, n0 = pos.size, neg.size
    if n1 == 0 or n0 == 0:
        return float("nan")
    return float((r[:n1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))
