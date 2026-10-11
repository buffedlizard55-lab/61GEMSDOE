"""Basement-depth steps -> candidate buried faults.

Pipeline:
  isostatic gravity anomaly (band 13, mGal)
    -> Parker-Oldenburg basement relief h (m)
    -> basement depth D = z0 - h, regional tilt removed
    -> horizontal-gradient magnitude |grad D| smoothed at the gravity resolution
    -> directional non-maximum suppression  = ridge (the step trace)
    -> morphological dilation               = multi-line ribbon
    -> alluvial-cover gate                  = the part a surface catalogue cannot see
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from .parker_oldenburg import ParkerOldenburg


def regional_remove(x: np.ndarray, sigma_px: float) -> np.ndarray:
    """Remove wavelengths longer than ~2*pi*sigma (regional tilt / basin sag)."""
    return x - ndimage.gaussian_filter(x, sigma_px, mode="nearest")


def hgm(x: np.ndarray, dx: float = 100.0, sigma_px: float = 3.0) -> np.ndarray:
    """Horizontal-gradient magnitude of a surface, pre-smoothed at ``sigma_px``."""
    s = ndimage.gaussian_filter(x, sigma_px, mode="nearest")
    gy, gx = np.gradient(s, dx)
    return np.hypot(gx, gy)


def directional_nms(field: np.ndarray, dx: float, dy: float, size: int = 3) -> np.ndarray:
    """Sub-pixel non-maximum suppression along the local gradient direction.

    A pixel survives if ``field`` is a maximum at +/- 1 px along the unit gradient
    vector (gx, gy).  This traces the *strike* of a step rather than its width.
    """
    mag = np.hypot(dx, dy)
    mag = np.where(mag < 1e-12, 1.0, mag)
    ux, uy = dx / mag, dy / mag
    H, W = field.shape
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    coords_fwd = np.array([np.clip(yy + uy, 0, H - 1), np.clip(xx + ux, 0, W - 1)])
    coords_bwd = np.array([np.clip(yy - uy, 0, H - 1), np.clip(xx - ux, 0, W - 1)])
    f_fwd = ndimage.map_coordinates(field, coords_fwd, order=1, mode="nearest")
    f_bwd = ndimage.map_coordinates(field, coords_bwd, order=1, mode="nearest")
    return (field >= f_fwd) & (field >= f_bwd) & (field > 0)


def step_throw(D_hp: np.ndarray, sigma_px: float = 3.0, baseline_px: float = 3.0):
    """Apparent basement step height across the step, measured along the gradient.

    ``|grad D|`` grows without bound as the smoothing scale shrinks, so it ranks
    sharp noise above genuine offsets.  The throw is the depth *difference* over a
    fixed baseline (2 * baseline_px * 100 m) measured along the local gradient
    direction; for a real step it saturates at the offset height, for a smooth
    ramp it stays small.  Returns (throw, gx, gy, mag).
    """
    from scipy import ndimage as nd

    s = nd.gaussian_filter(D_hp, sigma_px, mode="nearest")
    gy, gx = np.gradient(s, 100.0)
    mag = np.hypot(gx, gy)
    m = np.where(mag < 1e-12, 1.0, mag)
    ux, uy = gx / m, gy / m
    H, W = s.shape
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    cp = np.array([np.clip(yy + baseline_px * uy, 0, H - 1),
                   np.clip(xx + baseline_px * ux, 0, W - 1)])
    cm = np.array([np.clip(yy - baseline_px * uy, 0, H - 1),
                   np.clip(xx - baseline_px * ux, 0, W - 1)])
    Dp = nd.map_coordinates(s, cp, order=1, mode="nearest")
    Dm = nd.map_coordinates(s, cm, order=1, mode="nearest")
    return np.abs(Dp - Dm), gx, gy, mag


def disk(radius_px: float) -> np.ndarray:
    r = int(np.ceil(radius_px))
    y, x = np.mgrid[-r:r + 1, -r:r + 1]
    return (x * x + y * y) <= radius_px ** 2 + 1e-9


def ribbon(ridge: np.ndarray, radius_px: float) -> np.ndarray:
    """Dilate a 1-px ridge into a ribbon of half-width ``radius_px``."""
    return ndimage.binary_dilation(ridge, structure=disk(radius_px))


@dataclass
class InversionResult:
    relief: np.ndarray      # h, m, positive up (shallow basement)
    depth: np.ndarray       # D = z0 - h, m below datum
    depth_hp: np.ndarray    # regional tilt removed
    hgm: np.ndarray         # |grad D_hp|, m of step per m
    ridge: np.ndarray       # bool
    ribbon: np.ndarray      # bool
    po: ParkerOldenburg


def invert_basement(g_mgal: np.ndarray, valid: np.ndarray, z0: float, drho: float,
                    cutoff_m: float, sigma_reg: float, sigma_step: float,
                    nms: bool = True, **kw) -> InversionResult:
    po = ParkerOldenburg(z0=z0, drho=drho, cutoff_m=cutoff_m, **kw)
    h = po.invert(g_mgal, valid=valid)
    D = z0 - h
    D_hp = regional_remove(D, sigma_reg)
    s = ndimage.gaussian_filter(D_hp, sigma_step, mode="nearest")
    gy, gx = np.gradient(s, 100.0)
    mag = np.hypot(gx, gy)
    ridge = directional_nms(mag, gx, gy) if nms else (mag > 0)
    return InversionResult(relief=h, depth=D, depth_hp=D_hp, hgm=mag,
                           ridge=ridge, ribbon=ridge.copy(), po=po)


def calibrate_z0(g_mgal, valid, reference, z0_grid, drho, cutoff_m, sigma_reg,
                 sigma_step, **kw):
    """Choose the mean interface depth by agreement with a regional basement map.

    ``reference`` is the regional basin-depth layer (competition band 15, itself the
    Saltus & Jachens 1995 1:2.5 M product regridded by the organisers).  Only the
    *depth scale* is calibrated here; the reference is never used to place a fault.
    """
    from scipy.stats import spearmanr

    m = valid & np.isfinite(reference)
    out = []
    for z0 in z0_grid:
        r = invert_basement(g_mgal, valid, z0=z0, drho=drho, cutoff_m=cutoff_m,
                            sigma_reg=sigma_reg, sigma_step=sigma_step, **kw)
        rho = float(spearmanr(r.depth[m].ravel()[::7], reference[m].ravel()[::7]).statistic)
        # amplitude calibration: D_ref ~ a + b * D_inv  ->  b is the depth-scale factor
        b, a = np.polyfit(r.depth[m][::7], reference[m][::7], 1)
        out.append(dict(z0=float(z0), spearman=rho, scale=float(b), offset=float(a),
                        rms_mgal=r.po.log.get("rms_mgal"),
                        h_std=r.po.log.get("h_std")))
    return out
