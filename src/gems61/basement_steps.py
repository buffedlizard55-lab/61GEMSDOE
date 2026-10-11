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
    """Calibrate a depth scale from the complete official GP-1012 XYZ grid.

    ``reference`` must be a parsed ``GP1012Grid``. Because the 1995 2 km grid's
    published header does not declare a geodetic datum, this legacy inversion
    path compares global depth summaries only; it will not align, correlate, or
    regress against organizer band 15. The returned scale statistics do not
    validate local candidate-fault geometry.
    """
    from .gp1012 import GP1012Grid

    if not isinstance(reference, GP1012Grid):
        raise RuntimeError(
            "GP-1012 calibration blocked: provide a complete read_gp1012_xyz() grid; "
            "organizer band 15 is prohibited"
        )
    target = reference.summary()
    target_p50 = float(target["p50_m"])
    target_p90 = float(target["p90_m"])
    target_deep = float(target["fraction_gt_1km"])
    m = np.asarray(valid, bool)
    if m.shape != np.asarray(g_mgal).shape:
        raise ValueError("valid mask shape does not match gravity")
    out = []
    for z0 in z0_grid:
        r = invert_basement(g_mgal, m, z0=z0, drho=drho, cutoff_m=cutoff_m,
                            sigma_reg=sigma_reg, sigma_step=sigma_step, **kw)
        depth = np.maximum(np.asarray(r.depth, np.float64), 0.0)
        values = depth[m & np.isfinite(depth)]
        if values.size == 0:
            raise ValueError("no valid inverted depths for GP-1012 calibration")
        stats = dict(p50_m=float(np.median(values)), p90_m=float(np.percentile(values, 90)),
                     fraction_gt_1km=float((values > 1000.0).mean()))
        penalties = dict(
            p50=abs(np.log(max(stats["p50_m"], 1.0) / max(target_p50, 1.0))),
            p90=abs(np.log(max(stats["p90_m"], 1.0) / max(target_p90, 1.0))),
            fraction_gt_1km=abs(np.log(max(stats["fraction_gt_1km"], 1e-6) /
                                       max(target_deep, 1e-6))),
        )
        out.append(dict(z0_m=float(z0), stats=stats, penalties=penalties,
                        penalty=float(sum(penalties.values())),
                        rms_mgal=r.po.log.get("rms_mgal"),
                        h_std=r.po.log.get("h_std")))
    return dict(status="CALIBRATED-TO-OFFICIAL-GP1012-GRID-WIDE-SUMMARIES",
                best=min(out, key=lambda item: item["penalty"]), candidates=out,
                reference=target,
                calibration_scope="grid-wide p50, p90, fraction >1 km; no spatial alignment",
                limitations=["GP-1012 is a 2 km low-pass model, not a 100 m label",
                             "no geodetic datum is specified; no pixelwise comparison",
                             "scale fit does not validate local fault geometry"])
