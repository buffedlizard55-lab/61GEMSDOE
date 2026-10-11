"""Buried-structure lane: basement relief from isostatic gravity, and the steps in it.

This module is the assigned lane's instrument.  It answers one question:

    Where does the *basement surface* step, in places the mapped-fault catalogue
    does not already cover?

Method, in order, with the source that fixes each step:

1. **Invert** the isostatic residual gravity field for depth to basement with the
   Parker (1973) forward series / Oldenburg (1974) iteration.  Oldenburg's paper
   is explicit that the iteration diverges without a low-pass filter; the filter
   used here is a Gaussian tapering the high wavenumbers that the data cannot
   resolve, in the Wiener sense (:func:`lowpass_wiener`).
2. **Calibrate** the density contrast against the published Basin-and-Range
   basin-depth scale of Saltus & Jachens (1995), USGS Geophysical Investigations
   Map **GP-1012**, 1:2,500,000 -- i.e. the *shape* of the published depth
   distribution (median, p90, and the fraction of the map deeper than 1 km,
   which Blakely & Jachens 1991 report as "about 20%" of Nevada).
3. **Find the step lines** as the automatic maxima of the horizontal gradient
   magnitude of the basement surface -- the Blakely & Simpson (1986) procedure
   for locating boundaries of gravity/magnetic sources, not a hand-picked mask.
4. **Keep only real steps.**  A lineament is not a fault (DrivenData problem
   statement, data-sources ledger row DD-ABOUT); a fault has displacement.  The
   throw across each maximum is measured from the depth surface and the
   candidate is kept only above a declared minimum.
5. **Prefer concealed steps** -- the ones under a thick basin fill, i.e. the ones
   the surface-based catalogue is least likely to already contain (this is the
   lane's reason to exist: 80% of Nevada is covered by Cenozoic deposits,
   Blakely & Jachens 1991).

Why the inversion is done at all, rather than reading the supplied
``depth_to_base_surf`` band: the supplied band is a first-order slab conversion
of the same gravity; running the full non-linear series is what makes the
*gradient* of the surface usable, and it lets the whole chain be re-derived and
audited from the pinned gravity band alone.  The supplied band is used only as
an independent check on the inversion (:func:`compare_to_published_depth`).
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
    15: "depth_to_base_surf",
    18: "iso_grav_anom_hg",
    5: "iso_grav_anom_slope",
    11: "iso_grav_anom_vg",
}


def load_band(band: int) -> np.memmap:
    """Memory-mapped float32 band of ``training_features.tif`` (1-based)."""
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
# 2. Calibration against the published Basin-and-Range depth scale
# --------------------------------------------------------------------------- #
# Saltus & Jachens (1995), USGS GP-1012, doi:10.3133/gp1012, 1:2,500,000.
# The anchors are the *shape* statistics of the published depth-to-basement
# surface, used to pick the density contrast.  They are deliberately coarse:
# GP-1012 is a 1:2.5M statewide map, so only its order of magnitude and its
# deep-fraction can be transported to a 100 m grid.
GP1012_ANCHORS = {
    "deep_fraction_gt_1km": 0.20,   # Blakely & Jachens 1991: "thicker than 1 km over only about 20% of the state"
    "median_depth_m_range": (250.0, 700.0),
    "p90_depth_m_range": (900.0, 2000.0),
}


def calibrate_depth_scale(depth_m: np.ndarray, mask: np.ndarray | None = None) -> dict:
    """Statistics of a depth surface, for comparison with :data:`GP1012_ANCHORS`."""
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
                            dx: float = PIXEL_M) -> dict:
    """Pick the density contrast whose inverted depth best matches GP-1012.

    Scoring is the absolute log-ratio error on the two anchors that can be
    transported from a 1:2.5M map: the median depth and the >1 km fraction.
    The published band ``depth_to_base_surf`` is *not* used to choose it (that
    would defeat the point of an independent inversion); it is compared
    afterwards, in :func:`compare_to_published_depth`.
    """
    rows = []
    for dr in candidates:
        inv = parker_oldenburg(np.asarray(gravity_mgal, np.float64), dr, z0, dx=dx)
        st = calibrate_depth_scale(inv["depth_m"], mask)
        lo, hi = GP1012_ANCHORS["median_depth_m_range"]
        med_pen = 0.0 if lo <= st["p50"] <= hi else min(
            abs(math.log(st["p50"] / lo)), abs(math.log(st["p50"] / hi)))
        deep_pen = abs(math.log(max(st["fraction_gt_1km"], 1e-6) /
                                GP1012_ANCHORS["deep_fraction_gt_1km"]))
        rows.append(dict(delta_rho=dr, stats=st, median_penalty=med_pen,
                         deep_fraction_penalty=deep_pen,
                         penalty=med_pen + deep_pen,
                         iterations=inv["iterations"], converged=inv["converged"],
                         rms_residual_mgal=inv["rms_residual_mgal"]))
    best = min(rows, key=lambda r: r["penalty"])
    return dict(best=best, table=rows,
                anchors=GP1012_ANCHORS,
                source="USGS GP-1012 (Saltus & Jachens 1995, doi:10.3133/gp1012); "
                       "Blakely & Jachens 1991 doi:10.1130/0016-7606(1991)103<0795:RSOMRI>2.3.CO;2")


def compare_to_published_depth(band15: np.ndarray, inverted_depth_m: np.ndarray,
                               mask: np.ndarray) -> dict:
    """Independent check of the inversion against the supplied depth band."""
    a = np.asarray(band15, np.float64)
    b = np.asarray(inverted_depth_m, np.float64)
    m = np.asarray(mask, bool) & np.isfinite(a) & np.isfinite(b)
    av, bv = a[m], b[m]
    r = float(np.corrcoef(av, bv)[0, 1]) if av.size > 1 else float("nan")
    # slope of the published band on the inverted one, forced through zero
    slope = float((av * bv).sum() / max((bv * bv).sum(), 1e-9))
    return dict(n=int(av.size), pearson_r=r, slope_published_on_inverted=slope,
                published_p50=float(np.median(av)), inverted_p50=float(np.median(bv)),
                published_p90=float(np.percentile(av, 90)),
                inverted_p90=float(np.percentile(bv, 90)),
                note="a high r with a slope near 1 says the inversion reproduces the "
                     "supplied product; it is a check, not an input")


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
    safe = np.where(finite, f, -np.inf)
    directions = [(1, 0), (0, 1)]
    if extra_directions:
        directions += [(1, 1), (1, -1)]
    votes = np.zeros(f.shape, np.int8)
    for dy, dx in directions:
        a = np.roll(safe, (-dy, -dx), axis=(0, 1))
        b = np.roll(safe, (dy, dx), axis=(0, 1))
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
                     filter_order: float = 4.0, kc_scale: float = 0.5,
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
    known = np.asarray(known, bool)
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
                  dx: float = PIXEL_M, filter_order: float = 4.0,
                  kc_scale: float = 0.25) -> dict:
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

    The low-pass is a Butterworth of ``filter_order`` with corner
    ``kc = kc_scale / (2 z0)``; ``kc_scale`` < 1 is required and is calibrated
    against USGS GP-1012 in :func:`calibrate_density_scale`.
    """
    known = np.asarray(known, bool)
    filled = inpaint_smooth(np.asarray(dg, np.float64), known)
    shape = filled.shape
    k = wavenumbers(shape, dx)
    filt = 1.0 / (1.0 + (k / (kc_scale / (2.0 * z0))) ** filter_order)
    dgv = np.where(known, filled, 0.0)
    # Sign convention, stated once and checked against the supplied product:
    # a basin is a NEGATIVE isostatic residual and LESS dense than basement, so
    # delta_rho < 0 and thickness t = dg * MGAL / (2 pi G delta_rho) is POSITIVE
    # over it.  A stray leading minus here flips the whole surface and was caught
    # by requiring corr(depth, iso_grav_anom) < 0, as the supplied band 15 is
    # (-0.685 measured); see evidence/measure.json.
    lead = sfft.rfft2(dgv) * np.exp(np.minimum(k * z0, 40.0)) * MGAL / (
        2.0 * np.pi * G_SI * delta_rho)
    relief = sfft.irfft2(lead * filt, s=shape)
    depth = z0 + relief
    fwd = parker_forward(relief, delta_rho, z0, k, n_terms=4)
    resid = (filled - fwd)[known] if known.any() else np.array([0.0])
    return dict(relief_m=relief.astype(np.float32), depth_m=depth.astype(np.float32),
                delta_rho=float(delta_rho), z0_m=float(z0),
                filter=f"Butterworth order {filter_order}, kc = {kc_scale/(2.0*z0):.3e} rad/m "
                       f"(kc_scale={kc_scale})",
                rms_residual_mgal=float(np.sqrt(np.mean(resid ** 2))),
                stage="first iterate (low-passed Bouguer slab); non-linear correction rejected "
                      "because it diverges on an isostatic residual",
                source_doi="doi:10.1190/1.1440444")


def calibrate_density_scale(dg: np.ndarray, known: np.ndarray, z0: float = 500.0,
                            dx: float = PIXEL_M,
                            candidates=(-250.0, -300.0, -350.0, -400.0,
                                        -450.0, -500.0, -600.0),
                            kc_scales=(0.5, 0.25, 0.125),
                            z0_candidates=(300.0, 400.0, 500.0, 700.0)) -> dict:
    """Choose (density contrast, filter corner) to match the published GP-1012 scale.

    The two anchors that can be transported from a 1:2,500,000 statewide map are
    the median depth band and the fraction of the province deeper than 1 km
    (Blakely & Jachens 1991: "about 20%").  The penalty is the sum of a log-ratio
    on the deep fraction and a log-ratio on the median outside its band.

    ``z0`` is swept as well as the contrast because Oldenburg's non-uniqueness is
    exactly the (contrast, reference level) pair: the reference level sets the
    median and the contrast sets the amplitude.  Both are free here, so both are
    fitted to the published map rather than assumed.
    """
    rows = []
    lo, hi = GP1012_ANCHORS["median_depth_m_range"]
    for z0 in z0_candidates:
      for dr in candidates:
        for ks in kc_scales:
            sol = slab_solution(dg, known, dr, z0, dx=dx, kc_scale=ks)
            st = calibrate_depth_scale(sol["depth_m"], known)
            med_pen = 0.0 if lo <= st["p50"] <= hi else min(
                abs(math.log(max(st["p50"], 1e-6) / lo)),
                abs(math.log(max(st["p50"], 1e-6) / hi)))
            deep_pen = abs(math.log(max(st["fraction_gt_1km"], 1e-6) /
                                    GP1012_ANCHORS["deep_fraction_gt_1km"]))
            rows.append(dict(z0_m=z0, delta_rho=dr, kc_scale=ks, stats=st,
                             median_penalty=med_pen, deep_fraction_penalty=deep_pen,
                             penalty=med_pen + deep_pen,
                             rms_residual_mgal=sol["rms_residual_mgal"]))
    best = min(rows, key=lambda r: r["penalty"])
    return dict(best=best, table=rows, anchors=GP1012_ANCHORS,
                source="USGS GP-1012 (Saltus & Jachens 1995, doi:10.3133/gp1012); "
                       "Blakely & Jachens 1991 doi:10.1130/0016-7606(1991)103<0795:RSOMRI>2.3.CO;2")
