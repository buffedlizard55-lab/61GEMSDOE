"""Buried-structure lane: basement relief from isostatic gravity, and its steps.

This module supports the assigned lane: invert band 13 isostatic gravity,
locate candidate basement-depth steps, and distinguish structural offset from
intrabasement density contrasts. Parker (1973) / Oldenburg (1974) supply the
potential-field model and its stabilizing filter; Blakely & Simpson (1986)
supply the gradient-edge construction.

Calibration policy is fail-closed. The only permitted depth-scale reference is
the actual official GP-1012 grid distributed by NOAA/NCEI (``br_depth.xyz``).
The complete grid is not present in this checkout. The organizer's band 15 and
static literature-derived quantiles are not substitutes and are not used by
current methods. A fixed prior may be used to test scale-invariant step
geometry, but it must be labelled uncalibrated.

Band 15 ``depth_to_base_surf`` is not a prediction feature and is not a
calibration target. Older experiment receipts that compared to it are
historical diagnostics only and must not be described as GP-1012 calibration.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy import fft as sfft

# --------------------------------------------------------------------------- #
# Physical constants and grid pins
# --------------------------------------------------------------------------- #
G_SI = 6.67430e-11           # m^3 kg^-1 s^-2  (CODATA 2018)
MGAL = 1.0e-5                # 1 mGal in m/s^2
PIXEL_M = 100.0              # competition grid spacing
CRS_EPSG = 32611
SHAPE = (3730, 3292)
TRANSFORM = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)

REPO_ROOT = Path(__file__).resolve().parents[2]
BAND_CACHE = REPO_ROOT / ".cache" / "features"

# Band numbers are 1-based, as used in evidence/feature_cache.json.
BANDS = {
    13: "iso_grav_anom",
    18: "iso_grav_anom_hg",
    5: "iso_grav_anom_slope",
    11: "iso_grav_anom_vg",
}


def load_band(band: int) -> np.memmap:
    """Memory-mapped feature band, with organizer depth band 15 fail-closed."""
    if int(band) == 15:
        raise PermissionError("organizer band 15 is prohibited for calibration and prediction features")
    path = BAND_CACHE / f"band-{band:02d}.npy"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing -- run scripts/prepare_data.py")
    return np.load(path, mmap_mode="r")


# --------------------------------------------------------------------------- #
# 1. Parker-Oldenburg inversion
# --------------------------------------------------------------------------- #
def wavenumbers(shape: tuple[int, int], dx: float = PIXEL_M) -> np.ndarray:
    """Radial wavenumber field in rad/m for ``rfft2`` output layout."""
    ny, nx = shape
    kx = 2.0 * np.pi * np.fft.rfftfreq(nx, d=dx)
    ky = 2.0 * np.pi * np.fft.fftfreq(ny, d=dx)
    return np.hypot(ky[:, None], kx[None, :])


def lowpass_wiener(k: np.ndarray, z0: float, order: float = 2.0) -> np.ndarray:
    """Oldenburg's stabilising low-pass, written as a Wiener-style weighting.

    Oldenburg (1974), Geophysics 39(4) 526-536, doi:10.1190/1.1440444: the
    iteration ``h_{n+1} = ...`` is unstable because the downward-continuation
    factor ``exp(+k z0)`` amplifies noise without bound; the paper's remedy is a
    low-pass filter whose cut-off is set by the source depth.  The filter used
    here is

        W(k) = 1 / (1 + (k / kc)^order),      kc = 1 / (2 z0)

    which is unity for the long wavelengths that carry the relief and decays as
    a power law above the cut-off.  It is applied to the *correction* terms, so
    the long-wavelength solution is untouched.
    """
    kc = 1.0 / (2.0 * z0)
    return 1.0 / (1.0 + (k / kc) ** order)


def parker_forward(h: np.ndarray, delta_rho: float, z0: float, k: np.ndarray,
                   n_terms: int = 10) -> np.ndarray:
    """Parker (1973) forward series: gravity of relief ``h`` on an interface.

    ``F[dg] = 2 pi G drho exp(-k z0) sum_n (-k)^(n-1)/n! * F[h^n]``

    ``h`` is the depth deviation (m, positive down) from the reference level
    ``z0`` (m, positive down).  ``delta_rho`` is the density contrast across the
    interface in kg/m^3 (basin fill minus basement, hence negative for a basin).
    Returns the anomaly in mGal on the same grid.
    """
    H = sfft.rfft2(np.asarray(h, np.float64))
    total = np.zeros_like(H)
    power = np.ones_like(k)
    for n in range(1, n_terms + 1):
        if n > 1:
            power = power * (-k)
        Fhn = H if n == 1 else sfft.rfft2(np.asarray(h, np.float64) ** n)
        total += power / math.factorial(n) * Fhn
    dg = 2.0 * np.pi * G_SI * delta_rho * np.exp(-k * z0) * total
    return sfft.irfft2(dg, s=h.shape) / MGAL


def parker_oldenburg(dg_mgal: np.ndarray, delta_rho: float, z0: float,
                     dx: float = PIXEL_M, n_terms: int = 10, max_iter: int = 60,
                     tol_m: float = 1.0, order: float = 2.0) -> dict:
    """Oldenburg (1974) iterative inversion of ``dg_mgal`` for interface relief.

    Returns ``h`` (m of relief, positive down from ``z0``) plus a receipt with
    the per-iteration change and the forward-model residual.

    Convergence: the first iterate is the slab (Bouguer) solution; each further
    iterate recomputes the forward anomaly of the current relief and subtracts
    it from the observed field before re-solving for the correction, filtered by
    :func:`lowpass_wiener`.
    """
    dg = np.asarray(dg_mgal, np.float64)
    shape = dg.shape
    k = wavenumbers(shape, dx)
    filt = lowpass_wiener(k, z0, order)
    lead = sfft.rfft2(dg) * np.exp(np.minimum(k * z0, 40.0)) * MGAL / (
        2.0 * np.pi * G_SI * delta_rho)
    h = sfft.irfft2(lead * filt, s=shape)
    trace = []
    converged = False
    for it in range(max_iter):
        dg_fwd = parker_forward(h, delta_rho, z0, k, n_terms=n_terms)
        resid = dg - dg_fwd
        correction = sfft.rfft2(resid) * np.exp(np.minimum(k * z0, 40.0)) * MGAL / (
            2.0 * np.pi * G_SI * delta_rho)
        h_new = h + sfft.irfft2(correction * filt, s=shape)
        change = float(np.max(np.abs(h_new - h)))
        trace.append(dict(iteration=it + 1, max_change_m=change,
                          rms_residual_mgal=float(np.sqrt(np.mean(resid ** 2)))))
        h = h_new
        if change < tol_m:
            converged = True
            break
    dg_fwd = parker_forward(h, delta_rho, z0, k, n_terms=n_terms)
    resid = dg - dg_fwd
    return dict(
        relief_m=h.astype(np.float32),
        depth_m=(z0 + h).astype(np.float32),
        iterations=len(trace), converged=converged, trace=trace,
        rms_residual_mgal=float(np.sqrt(np.mean(resid ** 2))),
        delta_rho=float(delta_rho), z0_m=float(z0), n_terms=int(n_terms),
        filter=f"1/(1+(k/kc)^{order}) with kc=1/(2*z0)",
        filter_form="Oldenburg 1974 low-pass (divergence without it)",
        source_doi="doi:10.1190/1.1440444 (Oldenburg 1974); doi:10.1111/j.1365-246X.1973.tb02307.x (Parker 1973)",
    )


# --------------------------------------------------------------------------- #
# 2. GP-1012 depth-scale calibration (requires the actual official grid)
# --------------------------------------------------------------------------- #
# The old static values below were not extracted from GP-1012 and are retired.
# In particular, a literature statement about a regional deep fraction is not a
# substitute for the official gridded reference.
GP1012_ANCHORS = None


def calibrate_depth_scale(depth_m: np.ndarray, mask: np.ndarray | None = None) -> dict:
    """Summary statistics of an inverted depth surface; not a calibration."""
    d = np.asarray(depth_m, np.float64)
    m = np.isfinite(d) if mask is None else (np.asarray(mask, bool) & np.isfinite(d))
    if m.sum() == 0:
        raise ValueError("no finite depth cells inside mask")
    v = d[m]
    return dict(n=int(v.size), p50=float(np.median(v)),
                p90=float(np.percentile(v, 90)), p99=float(np.percentile(v, 99)),
                mean=float(v.mean()), vmax=float(v.max()),
                fraction_gt_1km=float((v > 1000.0).mean()),
                fraction_gt_2km=float((v > 2000.0).mean()))


def choose_density_contrast(gravity_mgal: np.ndarray, mask: np.ndarray,
                            z0: float, candidates=(-250.0, -300.0, -350.0, -400.0,
                                                  -450.0, -500.0, -600.0),
                            dx: float = PIXEL_M, *, gp1012_reference=None) -> dict:
    """Select density contrast only from an actual parsed GP-1012 grid.

    The former hard-coded quantile anchors were not measured from GP-1012 and
    are retired. Pass a complete :class:`gems61.gp1012.GP1012Grid`; passing band
    15 or a hand-built anchor dictionary is rejected by the shared calibrator.
    """
    if gp1012_reference is None:
        raise RuntimeError("GP-1012 calibration blocked: pass the complete official br_depth.xyz grid")
    return calibrate_density_scale(gravity_mgal, mask, z0=z0, dx=dx,
                                   candidates=candidates,
                                   gp1012_reference=gp1012_reference)


def compare_to_published_depth(*_args, **_kwargs) -> dict:
    """Retired band-15 comparator; band 15 is not a calibration reference or feature."""
    raise RuntimeError(
        "organizer band 15 is prohibited for calibration/features; use the official GP-1012 grid"
    )


# --------------------------------------------------------------------------- #
# 3. Automatic maxima of the horizontal gradient (Blakely & Simpson 1986)
# --------------------------------------------------------------------------- #
def horizontal_gradient_magnitude(field: np.ndarray, dx: float = PIXEL_M) -> np.ndarray:
    """``|grad field|`` in field-units per metre, NaN-preserving."""
    f = np.asarray(field, np.float64)
    gy, gx = np.gradient(f, dx)
    return np.hypot(gy, gx)


def blakely_simpson_maxima(hgm: np.ndarray, extra_directions: bool = True) -> np.ndarray:
    """Accept a cell as a HGM maximum if it exceeds *at least two* neighbours.

    Blakely & Simpson (1986), Geophysics 51(7) 1494-1498,
    doi:10.1190/1.1442197, "Approximating edges of source bodies from magnetic
    or gravity anomalies".  Their rule is deliberately permissive -- requiring
    only two of the four neighbours to be smaller -- because the ridge of the
    horizontal gradient is one cell wide and a strict 4-neighbour test breaks it
    wherever the ridge steps diagonally.  The two diagonal directions are
    included here (``extra_directions``) as the paper does for gridded data.
    """
    f = np.asarray(hgm, np.float64)
    finite = np.isfinite(f)
    # Missing cells and off-grid neighbours are treated as unavailable, not as
    # artificial low values that would create boundary maxima.
    safe = np.where(finite, f, np.inf)
    directions = [(1, 0), (0, 1)]
    if extra_directions:
        directions += [(1, 1), (1, -1)]
    votes = np.zeros(f.shape, np.int8)
    for dy, dx in directions:
        # Constant +inf padding prevents wraparound and prevents missing
        # neighbours at grid edges from falsely counting as lower values.
        a = ndi.shift(safe, shift=(-dy, -dx), order=0, mode="constant",
                      cval=np.inf, prefilter=False)
        b = ndi.shift(safe, shift=(dy, dx), order=0, mode="constant",
                      cval=np.inf, prefilter=False)
        votes += ((safe > a) & (safe > b)).astype(np.int8)
    return (votes >= 2) & finite


def step_magnitude(depth_m: np.ndarray, maxima: np.ndarray,
                   window_px: int = 2) -> np.ndarray:
    """Throw across the step line: range of depth in a small window at each maximum.

    This is the operational form of "a fault is a structure with displacement"
    (DrivenData data-sources ledger, row DD-ABOUT): the gradient of a depth
    surface peaks over a *slope break*, which may be a scarp or may be a smooth
    ramp.  Requiring a minimum depth difference across the window keeps the ones
    that are steps and drops the ones that are ramps.
    """
    d = np.asarray(depth_m, np.float64)
    finite = np.isfinite(d)
    w = int(window_px)
    if w < 1:
        raise ValueError("window_px must be >= 1")
    size = 2 * w + 1
    mx = ndi.maximum_filter(np.where(finite, d, -np.inf), size=size, mode="nearest")
    mn = ndi.minimum_filter(np.where(finite, d, np.inf), size=size, mode="nearest")
    throw = mx - mn
    throw = np.where(np.isfinite(throw), throw, np.nan)
    return np.where(np.asarray(maxima, bool), throw, np.nan)


def signed_flank_persistence(depth_m: np.ndarray, *, dx: float,
                             apertures_m: tuple[float, ...] = (2000.0, 4000.0),
                             valid: np.ndarray | None = None,
                             maxima: np.ndarray | None = None) -> dict:
    """Measure sign-consistent basement-depth offsets across HGM normals.

    For each cell, the local gradient normal defines opposite flanks. At every
    requested aperture ``r``, ``delta_r = D(x+r*n) - D(x-r*n)`` is sampled with
    bilinear interpolation. ``persistence`` is ``min(abs(delta_r)) / max(abs(delta_r))``;
    ``same_sign`` requires all apertures to have the same non-zero sign. Samples
    whose interpolation stencil leaves ``valid`` are excluded. No catalogue or
    band 15 values are read.

    The returned arrays have the input shape; ``signed_deltas`` is stacked in
    the same order as ``apertures_m``. This operator is scale-invariant under a
    positive multiplicative depth-scale change, but its absolute relief remains
    uncalibrated until the official GP-1012 grid is used.
    """
    d = np.asarray(depth_m, np.float64)
    if d.ndim != 2 or not np.isfinite(dx) or dx <= 0:
        raise ValueError("depth must be 2-D and dx must be positive")
    apertures = tuple(float(r) for r in apertures_m)
    if not apertures or any(not np.isfinite(r) or r <= 0 for r in apertures):
        raise ValueError("apertures_m must contain positive finite distances")
    finite = np.isfinite(d)
    sample_domain = finite if valid is None else (np.asarray(valid, bool) & finite)
    if sample_domain.shape != d.shape:
        raise ValueError("valid mask shape does not match depth")
    candidate = sample_domain
    if maxima is not None:
        mx = np.asarray(maxima, bool)
        if mx.shape != d.shape:
            raise ValueError("maxima mask shape does not match depth")
        candidate = sample_domain & mx
    # Compute a stable normal only at candidate cells with non-zero gradient.
    safe = np.where(finite, d, 0.0)
    gy, gx = np.gradient(safe, float(dx))
    mag = np.hypot(gx, gy)
    nz = mag > np.finfo(np.float64).eps
    nx = np.divide(gx, mag, out=np.zeros_like(gx), where=nz)
    ny = np.divide(gy, mag, out=np.zeros_like(gy), where=nz)
    yy, xx = np.indices(d.shape, dtype=np.float32)
    ds = np.where(finite, d, 0.0).astype(np.float32)
    vm = sample_domain.astype(np.float32)
    deltas = []
    sample_valid = candidate & nz
    for aperture in apertures:
        off = np.float32(aperture / float(dx))
        yp = yy + ny.astype(np.float32) * off
        xp = xx + nx.astype(np.float32) * off
        ym = yy - ny.astype(np.float32) * off
        xm = xx - nx.astype(np.float32) * off
        plus = ndi.map_coordinates(ds, [yp, xp], order=1, mode="constant", cval=0.0)
        minus = ndi.map_coordinates(ds, [ym, xm], order=1, mode="constant", cval=0.0)
        vp = ndi.map_coordinates(vm, [yp, xp], order=1, mode="constant", cval=0.0)
        vmn = ndi.map_coordinates(vm, [ym, xm], order=1, mode="constant", cval=0.0)
        sample_valid &= (vp >= 0.999) & (vmn >= 0.999)
        deltas.append((plus - minus).astype(np.float32))
    delta = np.stack(deltas, axis=0)
    abs_delta = np.abs(delta)
    max_abs = abs_delta.max(axis=0)
    min_abs = abs_delta.min(axis=0)
    same_sign = ((delta > 0).all(axis=0) | (delta < 0).all(axis=0)) & sample_valid
    persistence = np.divide(min_abs, max_abs, out=np.zeros_like(max_abs),
                            where=(max_abs > 1e-6) & sample_valid)
    persistence[~same_sign] = 0.0
    return dict(persistence=persistence.astype(np.float32), same_sign=same_sign,
                valid=sample_valid, signed_deltas=delta,
                gradient_magnitude=mag.astype(np.float32),
                apertures_m=list(apertures))


def buried_density_sheet_gravity(mask: np.ndarray, *, density_contrast_kg_m3: float,
                                 thickness_m: float, depth_m: float,
                                 dx: float) -> np.ndarray:
    """Gravity of a laterally variable, buried thin density sheet (mGal).

    This is a synthetic *non-fault* mimic: a sheet with no interface relief
    produces ``F[g] = 2*pi*G*exp(-|k|*depth)*F[delta_rho*thickness]``. The
    periodic FFT is appropriate for a centered, boundary-padded synthetic test;
    this helper is not a forward model for the real survey.
    """
    m = np.asarray(mask, bool)
    if m.ndim != 2 or dx <= 0 or thickness_m <= 0 or depth_m < 0:
        raise ValueError("mask must be 2-D; dx/thickness must be positive and depth non-negative")
    k = wavenumbers(m.shape, float(dx))
    sheet_mass = m.astype(np.float64) * float(density_contrast_kg_m3) * float(thickness_m)
    spectrum = 2.0 * np.pi * G_SI * np.exp(-k * float(depth_m)) * sfft.rfft2(sheet_mass)
    return (sfft.irfft2(spectrum, s=m.shape) / MGAL).astype(np.float32)


def ribbonize(mask: np.ndarray, half_width_px: int = 2) -> np.ndarray:
    """Grow a one-cell ridge into a ribbon of ``2*half_width+1`` cells.

    The competition's emission literature is explicit that multi-line ribbons
    beat thin lines at this kernel width (300 m = 3 px): a 3-5 px ribbon keeps
    the whole band inside the triangular kernel, so a dot anywhere in the band
    still pays.
    """
    m = np.asarray(mask, bool)
    if half_width_px <= 0:
        return m.copy()
    st = np.ones((3, 3), bool)
    return ndi.binary_dilation(m, st, iterations=int(half_width_px))


def concealment_prior(depth_m: np.ndarray, floor_m: float = 250.0,
                      cap_m: float = 1500.0) -> np.ndarray:
    """Weight in [0,1] favouring steps under thick basin fill.

    The lane's whole premise is that a step under a kilometre of fill is one the
    surface-mapping catalogue probably does not already contain.  The weight is
    a declared, monotone ramp in depth -- not fitted to any score.
    """
    d = np.asarray(depth_m, np.float64)
    w = (d - float(floor_m)) / max(float(cap_m) - float(floor_m), 1e-9)
    return np.clip(w, 0.0, 1.0)


def local_density(mask: np.ndarray, sigma_px: float) -> np.ndarray:
    """Gaussian kernel density of a binary mask, in units of the kernel peak."""
    m = np.asarray(mask, np.float32)
    g = ndi.gaussian_filter(m, sigma_px, mode="constant")
    peak = 1.0 / (2.0 * np.pi * sigma_px * sigma_px)
    return np.clip(g / peak, 0.0, 1.0)


def distance_to_mask(mask: np.ndarray) -> np.ndarray:
    """Euclidean distance in cells to the nearest set cell of ``mask``."""
    return ndi.distance_transform_edt(~np.asarray(mask, bool))


def offset_band_weight(dist_px: np.ndarray, near_px: float = 2.0,
                       far_px: float = 24.0) -> np.ndarray:
    """Weight peaking in the ``[near_px, far_px]`` offset band around a mask.

    This encodes the one placement fact the live portfolio supports strongly:
    published dot fields score better the further their dots sit from the mapped
    catalogue, but dots *on* it earn nothing because catalogue cells are masked
    out of scoring.  The band is declared from that evidence, not fitted to any
    local holdout.
    """
    d = np.asarray(dist_px, np.float64)
    rise = np.clip(d / max(near_px, 1e-9), 0.0, 1.0)
    fall = np.clip(1.0 - (d - far_px) / max(far_px, 1e-9), 0.0, 1.0)
    return np.clip(rise * fall, 0.0, 1.0)


# --------------------------------------------------------------------------- #
# NaN-safe working-grid preparation (measured requirement, see evidence/)
# --------------------------------------------------------------------------- #
def inpaint_smooth(values: np.ndarray, known: np.ndarray,
                   sigmas: tuple[float, ...] = (4.0, 8.0, 16.0, 32.0, 64.0, 128.0)
                   ) -> np.ndarray:
    """Fill unknown cells from a multi-scale normalised convolution of the known ones.

    A constant fill was measured to be fatal here: the GeoDAWN gravity band is
    NaN over 58% of the rectangle, so a mean fill puts a several-mGal step along
    the whole survey boundary, and the Oldenburg leading term (which multiplies
    by ``exp(+k z0)``) turns that step into tens of kilometres of fake relief and
    an overflow.  Normalised convolution,

        fill(x) = sum_s K_s * (v * known) / sum_s K_s * known,

    reproduces the regional field across the gap with no step at the edge.
    """
    v = np.asarray(values, np.float64)
    k = np.asarray(known, bool) & np.isfinite(v)
    num = np.zeros_like(v)
    den = np.zeros_like(v)
    src = np.where(k, v, 0.0)
    kf = k.astype(np.float64)
    for s in sigmas:
        num += ndi.gaussian_filter(src, s, mode="nearest")
        den += ndi.gaussian_filter(kf, s, mode="nearest")
    filled = np.where(den > 1e-12, num / np.maximum(den, 1e-12), float(np.nanmean(v[k])) if k.any() else 0.0)
    return np.where(k, v, filled)


def robust_inversion(dg: np.ndarray, known: np.ndarray, delta_rho: float, z0: float,
                     dx: float = PIXEL_M, n_terms: int = 6, max_iter: int = 40,
                     tol_m: float = 1.0, relief_clip_m: float = 8000.0,
                     filter_order: float = 2.0, kc_scale: float = 1.0,
                     relaxation: float = 0.7) -> dict:
    """Parker-Oldenburg inversion of a NaN-punched gravity grid.

    Adds three guards that the textbook form does not need on a complete grid but
    that this data set requires:

    * a smooth fill over the survey gap (:func:`inpaint_smooth`),
    * a clip on the relief at every iteration, so a single bad wavenumber cannot
      overflow ``h**n`` and poison the whole solution,
    * the low-pass gain reported per iteration, so divergence is visible rather
      than silent.
    """
    if z0 <= 0 or dx <= 0 or kc_scale <= 0 or filter_order <= 0:
        raise ValueError("z0, dx, kc_scale, and filter_order must be positive")
    known = np.asarray(known, bool)
    if known.shape != np.asarray(dg).shape:
        raise ValueError("known mask shape does not match gravity")
    filled = inpaint_smooth(np.asarray(dg, np.float64), known)
    shape = filled.shape
    k = wavenumbers(shape, dx)
    filt = 1.0 / (1.0 + (k / (kc_scale / (2.0 * z0))) ** filter_order)
    lead = -sfft.rfft2(filled) * np.exp(np.minimum(k * z0, 40.0)) * MGAL / (
        2.0 * np.pi * G_SI * delta_rho)
    h = np.clip(sfft.irfft2(lead * filt, s=shape), -relief_clip_m, relief_clip_m)
    trace = []
    converged = False
    for it in range(max_iter):
        dg_fwd = parker_forward(h, delta_rho, z0, k, n_terms=n_terms)
        resid = np.where(known, filled - dg_fwd, 0.0)
        correction = sfft.rfft2(resid) * np.exp(np.minimum(k * z0, 40.0)) * MGAL / (
            2.0 * np.pi * G_SI * delta_rho)
        h_new = np.clip(h + relaxation * sfft.irfft2(correction * filt, s=shape),
                        -relief_clip_m, relief_clip_m)
        change = float(np.max(np.abs(h_new - h)))
        trace.append(dict(iteration=it + 1, max_change_m=change,
                          max_abs_relief_m=float(np.max(np.abs(h_new))),
                          rms_residual_mgal=float(np.sqrt(np.mean(
                              resid[known] ** 2))) if known.any() else float("nan")))
        h = h_new
        if change < tol_m:
            converged = True
            break
    resid = np.where(known, filled - parker_forward(h, delta_rho, z0, k, n_terms=n_terms), 0.0)
    return dict(relief_m=h.astype(np.float32), depth_m=(z0 + h).astype(np.float32),
                iterations=len(trace), converged=converged, trace=trace,
                rms_residual_mgal=float(np.sqrt(np.mean(resid[known] ** 2))) if known.any()
                else float("nan"),
                delta_rho=float(delta_rho), z0_m=float(z0), n_terms=int(n_terms),
                filter=f"Butterworth order {filter_order}, kc = kc_scale/(2 z0) = "
                       f"{kc_scale / (2.0 * z0):.3e} rad/m, relaxation {relaxation}",
                source_doi="doi:10.1190/1.1440444 (Oldenburg 1974)")


def slab_solution(dg: np.ndarray, known: np.ndarray, delta_rho: float, z0: float,
                  dx: float = PIXEL_M, filter_order: float = 2.0,
                  kc_scale: float = 1.0, *, _pre_filled: np.ndarray | None = None) -> dict:
    """First iterate of the Oldenburg iteration: the low-passed Bouguer slab depth.

    **This is the operator the lane uses, and the reason is a measurement.**
    Running the full non-linear series on this data set does not converge: the
    leading term leaves a 23.8 mGal forward residual, the first correction raises
    it to 39.7 mGal, and the sequence then grows without bound (recorded in
    ``evidence/measure.json``, ``divergence_trace``).  That is the expected
    behaviour when the input is an *isostatic residual* -- it carries crustal-
    and mantle-scale field, and the Parker series can only put that field into
    relief on one interface, so it does.  The first iterate is therefore kept and
    the non-linear correction is reported as rejected rather than hidden.

    The low-pass is the declared Wiener form
    ``W(k)=1/(1+(k/kc)^order)``. For the preregistered candidate,
    ``filter_order=2`` and ``kc_scale=1`` give ``kc=1/(2*z0)`` exactly.
    A different corner or order is a different hypothesis and must be frozen
    before evaluation. Only the absolute depth scale can be calibrated against
    the actual official GP-1012 grid in :func:`calibrate_density_scale`.
    """
    if z0 <= 0 or dx <= 0 or kc_scale <= 0 or filter_order <= 0:
        raise ValueError("z0, dx, kc_scale, and filter_order must be positive")
    if delta_rho == 0:
        raise ValueError("density contrast must be nonzero")
    known = np.asarray(known, bool)
    if known.shape != np.asarray(dg).shape:
        raise ValueError("known mask shape does not match gravity")
    filled = _pre_filled if _pre_filled is not None else inpaint_smooth(np.asarray(dg, np.float64), known)
    shape = filled.shape
    k = wavenumbers(shape, dx)
    filt = 1.0 / (1.0 + (k / (kc_scale / (2.0 * z0))) ** filter_order)
    dgv = np.where(known, filled, 0.0)
    # Physical sign convention: a basin is a negative gravity anomaly and the
    # fill is less dense than basement (delta_rho < 0), so the slab response has
    # positive depth relief. This uses gravity physics only; organizer band 15
    # is neither read nor used as a sign/calibration check.
    lead = sfft.rfft2(dgv) * np.exp(np.minimum(k * z0, 40.0)) * MGAL / (
        2.0 * np.pi * G_SI * delta_rho)
    relief = sfft.irfft2(lead * filt, s=shape)
    depth = z0 + relief
    fwd = parker_forward(relief, delta_rho, z0, k, n_terms=4)
    resid = (filled - fwd)[known] if known.any() else np.array([0.0])
    return dict(relief_m=relief.astype(np.float32), depth_m=depth.astype(np.float32),
                delta_rho=float(delta_rho), z0_m=float(z0),
                filter=f"Wiener order {filter_order}, kc = kc_scale/(2*z0) = "
                       f"{kc_scale/(2.0*z0):.3e} rad/m (kc_scale={kc_scale})",
                rms_residual_mgal=float(np.sqrt(np.mean(resid ** 2))),
                stage="first iterate (low-passed Bouguer slab); non-linear correction rejected "
                      "because it diverges on an isostatic residual",
                source_doi="doi:10.1190/1.1440444")


def calibrate_density_scale(dg: np.ndarray, known: np.ndarray, z0: float = 500.0,
                            dx: float = PIXEL_M,
                            candidates=(-250.0, -300.0, -350.0, -400.0,
                                        -450.0, -500.0, -600.0),
                            kc_scales=(1.0,),
                            z0_candidates=(300.0, 400.0, 500.0, 700.0),
                            *, gp1012_reference=None) -> dict:
    """Calibrate the inversion's depth scale against the complete official grid.

    The comparison is intentionally distributional because the 2 km GP-1012
    grid's header lacks a declared geodetic datum; pixel-exact reprojection and
    correlation are not supportable from the published metadata. The tested
    parameters are reference level, density contrast, and only the predeclared
    filter scales supplied by the caller. Band 15 and static literature anchors
    are never consulted. No calibration is possible without a parsed, complete
    :class:`gems61.gp1012.GP1012Grid`.
    """
    from .gp1012 import GP1012Grid
    if not isinstance(gp1012_reference, GP1012Grid):
        raise RuntimeError(
            "GP-1012 calibration blocked: pass read_gp1012_xyz() of the complete official br_depth.xyz; "
            "band 15 and static anchors are prohibited"
        )
    if not candidates or not kc_scales or not z0_candidates:
        raise ValueError("calibration candidate grids must be non-empty")
    reference = gp1012_reference.summary()
    target_p50 = float(reference["p50_m"])
    target_p90 = float(reference["p90_m"])
    target_deep = float(reference["fraction_gt_1km"])
    pre_filled = inpaint_smooth(np.asarray(dg, np.float64), np.asarray(known, bool))
    rows = []
    for z_ref in z0_candidates:
        for dr in candidates:
            if float(dr) >= 0:
                raise ValueError("basin fill-minus-basement density contrast must be negative")
            for ks in kc_scales:
                if float(ks) <= 0:
                    raise ValueError("kc_scale must be positive")
                sol = slab_solution(dg, known, float(dr), float(z_ref), dx=dx,
                                    kc_scale=float(ks), _pre_filled=pre_filled)
                # Depth is positive down; negative results are above the datum
                # and are assigned zero basement depth only for grid-wide
                # quantile comparison, never for candidate-feature generation.
                depth_for_stats = np.maximum(np.asarray(sol["depth_m"], np.float64), 0.0)
                st = calibrate_depth_scale(depth_for_stats, np.asarray(known, bool))
                # Weighted log-ratio objective over the global depth-scale
                # summary. It selects amplitude/scale, not pixelwise alignment.
                penalties = dict(
                    p50=abs(math.log(max(st["p50"], 1.0) / max(target_p50, 1.0))),
                    p90=abs(math.log(max(st["p90"], 1.0) / max(target_p90, 1.0))),
                    fraction_gt_1km=abs(math.log(max(st["fraction_gt_1km"], 1e-6) /
                                                  max(target_deep, 1e-6))),
                )
                rows.append(dict(z0_m=float(z_ref), delta_rho_kg_m3=float(dr),
                                 kc_scale=float(ks), stats=st, penalties=penalties,
                                 penalty=float(sum(penalties.values())),
                                 rms_residual_mgal=sol["rms_residual_mgal"]))
    best = min(rows, key=lambda row: row["penalty"])
    return dict(
        status="CALIBRATED-TO-OFFICIAL-GP1012-GRID-WIDE-SUMMARIES",
        best=best, table=rows, reference=reference,
        calibration_scope="grid-wide p50, p90, and fraction >1 km; no pixel alignment",
        source_url=reference["source_url"], source_sha256=reference["source_sha256"],
        limitations=["GP-1012 is a 2 km low-pass regional model, not a 100 m label",
                     "XYZ header gives Lambert parameters but no geodetic datum",
                     "summary-distribution calibration does not validate local fault-step geometry"],
    )
