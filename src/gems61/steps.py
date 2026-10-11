"""Basement-depth step detection: horizontal-gradient maxima of the inverted
pre-Tertiary surface, with a physical throw in metres.

A buried range-front or intrabasin normal fault offsets the basement surface.
On a 100 m grid that offset appears as a **step** in the basement-depth field,
and the step is located at the **maximum of the horizontal gradient** of that
field.

Two different quantities are used, on purpose:

* **location** -- the gradient magnitude of the Gaussian-smoothed depth,
  suppressed along the gradient direction (the Canny non-maximum-suppression
  construction, applied to a potential-field interface rather than to an
  image).  The gradient of a smoothed step peaks exactly at the step, so this
  is what localises the crest.
* **amplitude** -- the *throw*: the depth difference sampled at ±``L`` pixels
  on the two sides of the crest, in metres.  ``|d(x+L) - d(x-L)|`` is a plateau
  of width ``2L`` over a sharp step, which makes it useless for location but
  ideal for measuring how many metres of basement offset the step represents.
  Throw is the physically interpretable quantity and is what the emitter ranks
  on.

Gravity resolves such a step only to a few hundred metres, which is why the
emitter spreads each crest into several parallel lines (see
:mod:`gems61.emission`) rather than emitting a single thin line.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates, maximum_filter

from .grid import PIXEL_M


@dataclass(frozen=True)
class Steps:
    gradient: np.ndarray     # |grad depth| of the smoothed field, m per pixel
    crest: np.ndarray        # bool, non-maximum-suppressed gradient maxima
    throw: np.ndarray        # metres of basement offset across the step (0 off-crest)
    sigma_px: float
    half_width_px: float
    min_throw_m: float

    @property
    def n_crest(self) -> int:
        return int(self.crest.sum())


def _unit_gradient(field: np.ndarray, sigma: float):
    """Gaussian-smoothed central-difference gradient; returns (uy, ux, mag)."""
    f = gaussian_filter(field.astype(np.float32), sigma, mode="nearest") if sigma > 0 \
        else np.asarray(field, np.float32)
    gy, gx = np.gradient(f)
    mag = np.hypot(gx, gy).astype(np.float32)
    nz = mag > 0
    uy = np.where(nz, gy / np.where(nz, mag, 1.0), 0.0)
    ux = np.where(nz, gx / np.where(nz, mag, 1.0), 0.0)
    return uy.astype(np.float32), ux.astype(np.float32), mag


def nms_along_gradient(field: np.ndarray, uy: np.ndarray, ux: np.ndarray,
                       step: float = 1.0) -> np.ndarray:
    """Suppress every pixel that is not a strict maximum along the gradient.

    ``step`` is the sampling distance (px) for the two comparison samples;
    1.0 reproduces the classic Canny test on the 8-neighbourhood.
    """
    h, w = field.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)

    def sample(sign: float) -> np.ndarray:
        sy = np.clip(yy + sign * step * uy, 0, h - 1)
        sx = np.clip(xx + sign * step * ux, 0, w - 1)
        return map_coordinates(field, [sy, sx], order=1, mode="nearest")

    return (field > 0) & (field >= sample(+1.0)) & (field >= sample(-1.0))


def sample_offset(field: np.ndarray, uy: np.ndarray, ux: np.ndarray,
                  offset_px: float) -> np.ndarray:
    """Bilinearly sample ``field`` at ±``offset_px`` along the unit gradient."""
    h, w = field.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    sy = np.clip(yy + offset_px * uy, 0, h - 1)
    sx = np.clip(xx + offset_px * ux, 0, w - 1)
    return map_coordinates(np.asarray(field, np.float32), [sy, sx], order=1, mode="nearest")


def detect_steps(depth: np.ndarray, sigma_px: float = 2.0, half_width_px: float = 4.0,
                 valid: np.ndarray | None = None, min_throw_m: float = 0.0,
                 thin_plateaus: bool = False) -> Steps:
    """Locate basement steps and measure the throw of each one.

    ``thin_plateaus=True`` additionally requires each crest pixel to be the
    maximum of its 3x3 neighbourhood.  On the smooth, band-limited depth field
    produced by this inversion that test keeps only ~2 % of the ridge (it
    deletes the along-strike continuity of every step), so it is OFF by
    default; redundancy is removed later by the dot-thinning step, which is the
    operation the metric actually rewards.

    ``depth`` is the depth to basement in metres.  ``half_width_px`` is the
    half-window (px) over which the throw is measured; the default 4 px samples
    the depth 400 m to each side, so the throw is the basement offset across an
    800 m aperture.
    """
    depth = np.asarray(depth, dtype=np.float32)
    uy, ux, gradient = _unit_gradient(depth, float(sigma_px))
    crest = nms_along_gradient(gradient, uy, ux, step=1.0)
    if thin_plateaus:
        # Break plateaus: keep only the local maximum of a 3x3 window.
        crest &= gradient >= maximum_filter(gradient, size=3)
    if valid is not None:
        crest &= np.asarray(valid, bool)

    plus = sample_offset(depth, uy, ux, +float(half_width_px))
    minus = sample_offset(depth, uy, ux, -float(half_width_px))
    throw = np.abs(plus - minus).astype(np.float32)
    if min_throw_m > 0:
        crest &= throw >= float(min_throw_m)
    throw = np.where(crest, throw, 0.0).astype(np.float32)
    return Steps(gradient=gradient, crest=crest, throw=throw,
                 sigma_px=float(sigma_px), half_width_px=float(half_width_px),
                 min_throw_m=float(min_throw_m))


def throw_gradient_m_per_km(steps: Steps) -> np.ndarray:
    """Throw expressed as a depth gradient (m/km) across the sampling aperture."""
    return steps.throw.astype(np.float32) * (1000.0 / (2.0 * steps.half_width_px * PIXEL_M))
