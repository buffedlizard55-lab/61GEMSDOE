"""H61-M: basement-step corridors from gravity inversion + magnetic edges.

Unique hypothesis: Gravity inversion identifies basement steps (potential buried faults),
but cannot localize them precisely (<~1km resolution). Magnetic data (TMI from band 3)
can detect edges at higher resolution where faults offset magnetized basement or
volcanic flows. By finding magnetic horizontal-gradient maxima WITHIN gravity-step
corridors, we identify concealed faults that have both gravity AND magnetic expression.

This differs from all previous submissions:
- H61-G used only gravity + slope (topography)
- Magnetic-only submissions (e.g., from GEMSDOE40) didn't use gravity corridors
- This is the first gravity+magnetic conjunction in the buried-structure lane

Competing explanation: Density contrasts within basement can create gravity steps
WITHOUT faults. But these won't have co-located magnetic edges (no offset of
magnetized material), so the conjunction filters them out.
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

# Magnetic parameters
MAG_BAND = 3                   # TMI (Total Magnetic Intensity)
MAG_SMOOTH_PX = 2.0            # Smoothing for magnetic edge detection


def invert_basement(grav_full: np.ndarray, valid_full: np.ndarray, *,
                    regional_sigma_km: float = REGIONAL_SIGMA_KM,
                    candidates=(-300.0, -400.0, -500.0),
                    z0_candidates=(400.0, 500.0),
                    kc_scales=(0.25,)) -> dict:
    """Band-pass the isostatic residual, then run the GP-1012-calibrated slab
    inversion on a 400 m grid.
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


def basement_steps(depth_small: np.ndarray, dx: float, *, smooth_px: float = 0.0,
                   min_throw_m: float = MIN_THROW_M) -> dict:
    """Blakely-Simpson maxima of |grad depth| with a measured throw filter."""
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
    """Steps that survive smoothing of the depth surface."""
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


def magnetic_edges(mag_full: np.ndarray, valid_full: np.ndarray, *,
                  smooth_px: float = MAG_SMOOTH_PX) -> dict:
    """Find horizontal gradient maxima in TMI data (magnetic edges).

    Uses the same Blakely-Simpson approach as for gravity, but on magnetic data.
    These represent locations where magnetized material changes abruptly,
    which happens at faults that offset magnetic basement or volcanic flows.
    """
    m = np.asarray(mag_full, np.float64)
    valid = np.asarray(valid_full, bool) & np.isfinite(m)

    # Fill invalid areas with inpaint
    filled = B.inpaint_smooth(np.where(valid, m, np.nan), valid)

    # Smooth to reduce noise
    if smooth_px > 0:
        filled = ndi.gaussian_filter(filled, smooth_px, mode="nearest")

    # Compute horizontal gradient magnitude
    hgm = B.horizontal_gradient_magnitude(filled, B.PIXEL_M)

    # Find Blakely-Simpson maxima
    mx = B.blakely_simpson_maxima(hgm) & valid

    return dict(hgm=hgm, maxima=mx, n_edges=int(mx.sum()))


def corridor_mask(steps_full: np.ndarray, px: int = CORRIDOR_PX) -> np.ndarray:
    """Create a corridor mask around basement steps."""
    return ndi.distance_transform_edt(~np.asarray(steps_full, bool)) <= px


def magnetic_edges_in_corridor(mag_edges: np.ndarray, corridor: np.ndarray) -> np.ndarray:
    """Find magnetic edges that fall within gravity-step corridors."""
    return mag_edges & corridor


def ribbon(dots: np.ndarray, half_width_px: int = 1) -> np.ndarray:
    """8-neighbour dilation of a dot field into a (2w+1)-cell ribbon.

    As required by the lane: "Gravity resolves such steps only to a few hundred metres
    at best, so emit multi-line ribbons rather than thin lines."
    """
    return ndi.binary_dilation(np.asarray(dots, bool), np.ones((3, 3), bool),
                               iterations=int(half_width_px)) if half_width_px > 0 else dots.copy()


def dot_thin(score: np.ndarray, allowed: np.ndarray, budget: int, tile_px: int = 3) -> np.ndarray:
    """At most one dot per tile_px x tile_px tile at the tile's argmax of score."""
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


def rank01(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Rank-normalise values inside mask to (0, 1]; 0 elsewhere."""
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


def random_lines(shape, allowed, n_dots, seed=61, length_px=40, spacing_px=3) -> np.ndarray:
    """Random straight dotted lines inside allowed with the same dot count."""
    rng = np.random.default_rng(seed)
    out = np.zeros(shape, bool)
    ys, xs = np.nonzero(allowed)
    guard = 0
    while out.sum() < n_dots and guard < 1000 * n_dots:
        guard += 1
        i = int(rng.integers(ys.size))
        y0, x0 = int(ys[i]), int(xs[i])
        th = rng.uniform(0, np.pi)
        for t in range(0, length_px, spacing_px):
            y = y0 + int(round(t * np.sin(th)))
            x = x0 + int(round(t * np.cos(th)))
            if 0 <= y < shape[0] and 0 <= x < shape[1] and allowed[y, x]:
                out[y, x] = True
                if out.sum() >= n_dots:
                    break
    return out


def random_dots(allowed, n_dots, seed=62) -> np.ndarray:
    rng = np.random.default_rng(seed)
    idx = np.flatnonzero(allowed.ravel())
    pick = rng.choice(idx, size=min(int(n_dots), idx.size), replace=False)
    out = np.zeros(allowed.shape, bool)
    out.ravel()[pick] = True
    return out


def wilson(k: float, n: float, z: float = 1.959963985) -> tuple[float, float]:
    """Wilson score interval for binomial proportion."""
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))
