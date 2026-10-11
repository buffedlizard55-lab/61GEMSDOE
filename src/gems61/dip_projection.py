"""Dip projection of a basement step back to its surface fault trace.

The physics this module encodes
-------------------------------
A normal fault that cuts the basement surface is a plane with dip ``delta``.
Write the *surface trace* of that plane at horizontal position ``x = 0``.  The
plane descends into the hanging wall (the basin side), so at a depth ``z`` below
the ground surface the plane sits at horizontal distance

    x(z) = z * cot(delta)                                        (1)

from the trace.  The top of the *basement* is offset across the plane at the
depth where the plane meets it, i.e. at ``z ~= z_b``, so the step in the
basement surface is at ``x(z_b)`` -- **basinward of the surface trace by
``z_b * cot(delta)``**, not directly beneath it.

Blakely & Simpson (1986) horizontal-gradient maxima locate the *basement* step
``x(z_b)``, and the Parker (1973) / Oldenburg (1974) inversion supplies ``z_b``.
Equation (1) is therefore the missing link between the quantity the lane can
measure (a step in an inverted basement surface) and the quantity the metric
scores (the surface fault trace).  It is a *directional* correction of
``z_b * cot(delta)`` toward the footwall, and it is largest exactly where the
lane matters -- under thick basin fill -- because ``z_b`` is largest there.  A
step at zero depth needs no correction, which is the correct limit.

Numbers for the Basin and Range: normal faults there dip 45-70 degrees
(Thompson & Burke 1974; Anderson 1983; Doser 1986), so ``cot(delta)`` lies in
[0.36, 1.0].  At the lane's typical basin depth of 500-1000 m the correction is
180-1000 m, i.e. 2-10 pixels of the 100 m grid.  That is the same order as the
"few hundred metres" placement uncertainty the lane paragraph names, and it is
what makes a symmetric corridor (the previous sessions' choice) the wrong
emitter: the corridor is centred on the step, while the target is offset from
it.  This module replaces the corridor with the projected line.

Datums: ``z`` is measured downward from the ground surface; the inversion
returns depth to basement in metres below the surface, which is the same datum.
``z_b`` is taken as the depth at the step **minus half the throw**, i.e. the
depth of the basement break on the footwall side, which is where the plane
actually intersects the basement surface.

Nothing here is fitted to a score.  ``delta`` is a literature parameter with a
declared default and a reported sensitivity sweep; the weight used for dot
priority is monotone in (throw, concealment) and declared.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage as ndi

from . import buried as B

PIXEL_M = 100.0
DEFAULT_DIP_DEG = 60.0          # Basin and Range normal-fault mode; see module docstring
DIP_SWEEP_DEG = (45.0, 55.0, 60.0, 65.0, 75.0)
N_ANGLES = 48                   # 7.5 degree search for the footwall direction
RADII_PX = (4.0, 8.0, 12.0)     # 400 / 800 / 1200 m: past the step, short of the next one
CAP_PX = 20.0                   # no projection further than 2 km; guard against NaN slivers


@dataclass
class Footwall:
    """Per-step-pixel footwall direction and the basement depth of the break."""

    sy: np.ndarray              # row index of each step pixel
    sx: np.ndarray              # column index of each step pixel
    angle_rad: np.ndarray       # azimuth toward the footwall
    has_direction: np.ndarray   # bool, a finite depth sample existed on at least one radius
    z_step_m: np.ndarray        # inverted depth at the step pixel
    z_b_m: np.ndarray           # footwall basement-break depth used in eq. (1)
    throw_m: np.ndarray


@dataclass
class Projection:
    """Result of :func:`project_steps_to_surface`."""

    trace: np.ndarray           # bool, full grid: projected surface-trace pixels
    parent_step: np.ndarray     # bool, full grid: the step pixels that produced them
    offset_px: np.ndarray       # float32, full grid: |offset| used at each projected pixel
    depth_used_m: np.ndarray    # float32, full grid: z_b used at each projected pixel
    throw_used_m: np.ndarray    # float32, full grid: throw at the parent step pixel
    footwall_deg: np.ndarray    # float32, full grid: azimuth of the footwall direction
    n_steps: int
    n_trace_px: int
    offset_stats: dict = field(default_factory=dict)


def footwall_directions(depth_valid: np.ndarray, sy: np.ndarray, sx: np.ndarray, *,
                        n_angles: int = N_ANGLES, radii=RADII_PX) -> tuple:
    """Azimuth of the *shallower* side of each step pixel, by central difference.

    The footwall of a normal fault is the upthrown block, i.e. the side where the
    inverted basement depth is smaller.  For every trial azimuth ``u`` the routine
    forms the symmetric depth drop

        s(u) = mean_r [ D(p + r*u') - D(p + r*u) ],   u' = u + pi,

    and returns the ``u`` that maximises it.  ``s`` is a central-difference
    estimate of ``-dD/du``, i.e. the direction of steepest descent of the
    inverted basement depth, so this is a difference test across the step and not
    a derivative along it: on a long ridge the along-strike azimuths have
    ``s ~ 0`` and cannot win, which is the failure mode of a plain
    minimum-mean-depth search.

    Returns ``(angles_rad, has_direction, score_by_angle)``.
    """
    h, w = depth_valid.shape
    angles = np.arange(n_angles) * (2.0 * np.pi / n_angles)
    score = np.zeros((sy.size, n_angles), np.float64)
    weight = np.zeros_like(score)
    for r in radii:
        dy = np.round(r * np.sin(angles)).astype(np.int64)
        dx = np.round(r * np.cos(angles)).astype(np.int64)
        y_fw = np.clip(sy[:, None] + dy[None, :], 0, h - 1)
        x_fw = np.clip(sx[:, None] + dx[None, :], 0, w - 1)
        y_hw = np.clip(sy[:, None] - dy[None, :], 0, h - 1)
        x_hw = np.clip(sx[:, None] - dx[None, :], 0, w - 1)
        v_fw = depth_valid[y_fw, x_fw]
        v_hw = depth_valid[y_hw, x_hw]
        ok = np.isfinite(v_fw) & np.isfinite(v_hw)
        score += np.where(ok, v_hw - v_fw, 0.0)
        weight += ok
    score = np.where(weight > 0, score / np.maximum(weight, 1.0), -np.inf)
    best = np.argmax(score, axis=1)
    has_direction = weight.sum(axis=1) > 0
    return angles[best], has_direction, score


def footwall_of_steps(depth_full: np.ndarray, step_mask: np.ndarray,
                      throw_full: np.ndarray, valid: np.ndarray, *,
                      min_margin_px: float = 2.0) -> Footwall:
    """Locate the footwall side of every step pixel (dip-independent)."""
    depth_full = np.asarray(depth_full, np.float64)
    valid = np.asarray(valid, bool)
    step_mask = np.asarray(step_mask, bool) & valid
    work = B.inpaint_smooth(np.where(valid, depth_full, np.nan), valid)
    smooth = ndi.gaussian_filter(work, 1.5, mode="nearest")
    depth_valid = np.where(valid, smooth, np.nan)

    h, w = step_mask.shape
    margin = int(np.ceil(max(RADII_PX) + min_margin_px))
    inner = np.zeros_like(step_mask)
    inner[margin:h - margin, margin:w - margin] = True
    sy, sx = np.nonzero(step_mask & inner)

    if sy.size == 0:
        empty = np.zeros(0)
        return Footwall(sy, sx, empty, np.zeros(0, bool), empty, empty, empty)

    ang, has_dir, _ = footwall_directions(depth_valid, sy, sx)
    z_step = smooth[sy, sx]
    thr = np.asarray(throw_full, np.float64)[sy, sx]
    thr = np.where(np.isfinite(thr), thr, 0.0)
    z_b = np.maximum(z_step - 0.5 * thr, 0.0)
    good = has_dir & np.isfinite(z_step) & np.isfinite(ang)
    # where there is no finite depth within 1.2 km the direction test is undefined:
    # fall back to zero offset (no projection) rather than an arbitrary azimuth.
    z_b = np.where(good, z_b, 0.0)
    return Footwall(sy, sx, ang, good, z_step, z_b, thr)


def project_from_footwall(fw: Footwall, shape: tuple[int, int], *,
                          dip_deg: float = DEFAULT_DIP_DEG,
                          cap_px: float = CAP_PX) -> Projection:
    """Apply eq. (1) to a computed footwall field.  Cheap; call it per dip."""
    cot = 1.0 / np.tan(np.radians(float(dip_deg)))
    h, w = shape
    trace = np.zeros(shape, bool)
    parent = np.zeros(shape, bool)
    offset_px = np.zeros(shape, np.float32)
    depth_used = np.zeros(shape, np.float32)
    throw_used = np.zeros(shape, np.float32)
    fw_deg = np.zeros(shape, np.float32)
    n = int(fw.sy.size)
    if n == 0:
        return Projection(trace, parent, offset_px, depth_used, throw_used, fw_deg, 0, 0,
                          dict(dip_deg=float(dip_deg), cot=float(cot), n_step_px=0,
                               n_projected=0, n_zero_offset=0, cap_hits=0))
    off = np.clip(fw.z_b_m * cot / PIXEL_M, 0.0, float(cap_px))
    capped = (fw.z_b_m * cot / PIXEL_M) > float(cap_px)
    py = np.clip(np.round(fw.sy + off * np.sin(fw.angle_rad)).astype(np.int64), 0, h - 1)
    px_ = np.clip(np.round(fw.sx + off * np.cos(fw.angle_rad)).astype(np.int64), 0, w - 1)
    keep = fw.has_direction
    trace[py[keep], px_[keep]] = True
    parent[fw.sy[keep], fw.sx[keep]] = True
    offset_px[py[keep], px_[keep]] = off[keep].astype(np.float32)
    depth_used[py[keep], px_[keep]] = fw.z_b_m[keep].astype(np.float32)
    throw_used[py[keep], px_[keep]] = fw.throw_m[keep].astype(np.float32)
    fw_deg[py[keep], px_[keep]] = np.degrees(fw.angle_rad[keep]).astype(np.float32)
    o = off[keep]
    stats = dict(
        dip_deg=float(dip_deg), cot=float(cot), n_step_px=n,
        n_projected=int(keep.sum()), n_zero_offset=int((o < 0.5).sum()),
        n_undefined_direction=int((~keep).sum()), cap_hits=int(capped.sum()),
        offset_px_p50=float(np.median(o)) if o.size else None,
        offset_px_p90=float(np.percentile(o, 90)) if o.size else None,
        offset_px_max=float(o.max()) if o.size else None,
        offset_m_p50=float(np.median(o) * PIXEL_M) if o.size else None,
        offset_m_p90=float(np.percentile(o, 90) * PIXEL_M) if o.size else None,
        z_b_p50_m=float(np.median(fw.z_b_m[keep])) if keep.any() else None,
        z_b_p90_m=float(np.percentile(fw.z_b_m[keep], 90)) if keep.any() else None,
        throw_p50_m=float(np.median(fw.throw_m[keep])) if keep.any() else None)
    return Projection(trace, parent, offset_px, depth_used, throw_used, fw_deg,
                      n, int(trace.sum()), stats)


def project_steps_to_surface(depth_full: np.ndarray, step_mask: np.ndarray,
                             throw_full: np.ndarray, valid: np.ndarray, *,
                             dip_deg: float = DEFAULT_DIP_DEG,
                             cap_px: float = CAP_PX,
                             min_margin_px: float = 2.0) -> Projection:
    """Move every basement-step pixel toward its footwall by ``z_b * cot(dip)``."""
    fw = footwall_of_steps(depth_full, step_mask, throw_full, valid,
                           min_margin_px=min_margin_px)
    return project_from_footwall(fw, np.asarray(step_mask).shape, dip_deg=dip_deg,
                                 cap_px=cap_px)


def sampled_ribbon(mask: np.ndarray, half_width_px: int = 1) -> np.ndarray:
    """The lane's "multi-line ribbon", expressed as emission support.

    ``H.ribbon`` dilates the mask into a solid ``(2w+1)``-cell band.  The metric
    charges ``0.2`` for every positive cell, and ``dot_thin`` already guarantees
    one dot per 3 x 3 tile, so painting a solid band can only inflate the false
    positive term unless the extra cells change which tile maxima are chosen.
    This helper exists so that claim can be *measured* (arm ``P60r``) instead of
    asserted; the primary arm emits the projected line itself.
    """
    if half_width_px <= 0:
        return np.array(mask, bool)
    return ndi.binary_dilation(np.asarray(mask, bool), np.ones((3, 3), bool),
                               iterations=int(half_width_px))


def step_priority(throw_used_m: np.ndarray, depth_m: np.ndarray, trace: np.ndarray, *,
                  throw_only: bool = False, floor_m: float = 100.0,
                  cap_m: float = 1500.0) -> np.ndarray:
    """Dot priority on the projected trace, monotone in throw and in concealment.

    Both terms are declared, not fitted:

    * throw rank in (0, 1] -- a bigger basement step is a better fault candidate;
    * ``0.5 + 0.5 * concealment`` in [0.5, 1.0] -- the lane's premise is that the
      catalogue misses faults under thick fill, and the platform evidence
      (0.2600 -> 0.2778 when dots near the mapped traces were deleted) says dots
      far from the catalogue are worth more.  ``throw_only`` drops the second
      factor and is reported as an ablation.
    """
    from .h61g import rank01

    w = rank01(np.where(trace, throw_used_m, 0.0), trace)
    if throw_only:
        return w
    conceal = B.concealment_prior(depth_m, floor_m=floor_m, cap_m=cap_m)
    return w * (0.5 + 0.5 * conceal)
