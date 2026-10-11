"""Parker (1973) forward modelling and Oldenburg (1974) iterative inversion of
a density interface, specialised to the GEMS 100 m competition grid.

Theory
------
Let the interface (top of pre-Tertiary basement) lie at depth ``z0 - h(x, y)``
where ``h`` is the relief measured **positive upward** (a basement high), so
``h > 0`` means the dense basement is shallower than the reference depth ``z0``
and the dense material added relative to the reference slab has thickness ``h``.
For a constant density contrast ``drho = rho_basement - rho_fill > 0`` Parker
(1973, *The rapid calculation of potential anomalies*, Geophys. J. R. astr. Soc.
31, 447-455) gives the Fourier-domain anomaly

.. math::

    \\mathcal{F}[\\Delta g] = 2\\pi G \\Delta\\rho\\, e^{-|k| z_0}
        \\sum_{n=1}^{\\infty} \\frac{|k|^{n-1}}{n!}\\,\\mathcal{F}[h^n]

The ``n = 1`` term is the Bouguer slab: a constant ``h`` gives
``\\Delta g = 2\\pi G \\Delta\\rho\\,h``, which is the sanity check used in the
unit tests.

Oldenburg (1974, *The inversion and interpretation of gravity anomalies*,
Geophysics 39, 526-536) rearranges it into the fixed-point iteration

.. math::

    \\mathcal{F}[h_{j+1}] = W(k)\\left[
        \\frac{\\mathcal{F}[\\Delta g]\\,e^{|k| z_0}}{2\\pi G \\Delta\\rho}
        - \\sum_{n=2}^{N} \\frac{|k|^{n-1}}{n!}\\,\\mathcal{F}[h_j^n] \\right]

``W(k)`` is a high-cut filter.  Without it the ``e^{|k| z_0}`` factor amplifies
short wavelengths without bound and the iteration diverges; with it the
recovered relief is band-limited, which is exactly the physical statement that
gravity resolves a basement step to a few hundred metres and no better.  The
filter used here is Oldenburg's cosine taper

.. math::

    W(k) = \\tfrac12\\left(1 + \\cos(\\pi k / k_c)\\right),\\quad k \\le k_c;
    \\qquad W = 0 \\text{ otherwise}

with ``k_c = 2\\pi / \\lambda_c``.

Blakely & Jachens (GSA Bulletin 103, 395-405, 1991) applied this inversion to
**isostatic residual** gravity in the Basin and Range to map the pre-Tertiary
surface, which is the use made of band 13 ``iso_grav_anom`` here.

Units
-----
SI throughout: metres, kg m^-3, m s^-2.  Gravity is converted from the product's
mGal (1 mGal = 1e-5 m s^-2) on the way in and back on the way out.
"""

from __future__ import annotations

import math

import numpy as np
from scipy import fft as sp_fft
from scipy.ndimage import gaussian_filter

G = 6.67430e-11            # m^3 kg^-1 s^-2 (CODATA 2018)
MGal = 1.0e-5              # m s^-2 per mGal
TWO_PI_G = 2.0 * np.pi * G


# --------------------------------------------------------------------------- #
# grid / FFT helpers
# --------------------------------------------------------------------------- #
def wavenumbers(shape: tuple[int, int], cell: float, dtype=np.float32):
    """Radial wavenumber ``|k|`` (rad/m) laid out for ``rfft2`` of ``shape``."""
    ny, nx = shape
    ky = 2.0 * np.pi * sp_fft.fftfreq(ny, d=cell)
    kx = 2.0 * np.pi * sp_fft.rfftfreq(nx, d=cell)
    kyy, kxx = np.meshgrid(ky, kx, indexing="ij")
    return np.hypot(kxx, kyy).astype(dtype, copy=False)


def highcut_filter(k: np.ndarray, cutoff_wavelength_m: float,
                   plateau_fraction: float = 0.5) -> np.ndarray:
    """High-cut filter for the Oldenburg iteration.

    ``plateau_fraction = 0`` reproduces Oldenburg's (1974) pure cosine taper,
    which is unity only at ``k = 0`` and already halves the amplitude at half
    the cutoff wavenumber.  The default keeps a flat passband up to
    ``plateau_fraction * k_c`` and tapers cosinusoidally to zero at ``k_c``, so
    wavelengths that the inversion is meant to recover keep their amplitude
    while the divergent short-wavelength band is still removed.  Both variants
    are used: the taper is the textbook form, the plateau is what makes the
    recovered *depth scale* interpretable, and the difference is reported.
    """
    kc = 2.0 * np.pi / float(cutoff_wavelength_m)
    plateau = float(np.clip(plateau_fraction, 0.0, 0.95)) * kc
    w = np.zeros_like(k)
    w[k <= plateau] = 1.0
    band = (k > plateau) & (k <= kc)
    w[band] = 0.5 * (1.0 + np.cos(np.pi * (k[band] - plateau) / (kc - plateau)))
    return w


def reflect_pad(a: np.ndarray, pad: int) -> np.ndarray:
    """Mirror-pad so the periodic FFT sees a continuous field."""
    if pad <= 0:
        return a
    return np.pad(a, ((pad, pad), (pad, pad)), mode="reflect")


def inpaint(field: np.ndarray, valid: np.ndarray, sigmas=(64.0, 32.0, 16.0, 8.0, 4.0, 2.0),
            passes: int = 12) -> np.ndarray:
    """Fill invalid cells by multi-scale diffusion (a discrete harmonic fill).

    Repeated ``blur -> copy into the hole`` at decreasing scale is a standard
    cheap Laplace interpolation.  It is used only to make a rectangular,
    wrap-safe array for the FFT: every result in this lane is evaluated inside
    ``valid`` (and inside the eroded emission domain) so the fill never decides
    a prediction by itself.
    """
    out = np.array(field, dtype=np.float32, copy=True)
    holes = ~np.asarray(valid, bool)
    if not holes.any():
        return out
    out[holes] = 0.0
    finite_mean = float(np.mean(field[valid])) if valid.any() else 0.0
    out[holes] = finite_mean
    for sigma in sigmas:
        for _ in range(passes):
            blurred = gaussian_filter(out, sigma, mode="nearest")
            out[holes] = blurred[holes]
    return out


# --------------------------------------------------------------------------- #
# forward / inverse
# --------------------------------------------------------------------------- #
def parker_forward(relief: np.ndarray, drho: float, z0: float, cell: float,
                   n_terms: int = 8, pad: int = 0) -> np.ndarray:
    """Gravity anomaly (mGal) of a relief field ``h`` (m, positive upward)."""
    a = reflect_pad(np.asarray(relief, np.float32), pad)
    k = wavenumbers(a.shape, cell)
    spec = np.zeros(sp_fft.rfft2(a).shape, dtype=np.complex128)
    power = a                                   # n = 1 -> F[h]
    for n in range(1, int(n_terms) + 1):
        term = sp_fft.rfft2(power)
        if n > 1:
            term = term * (k ** (n - 1)) / math.factorial(n)
        spec = spec + term
        power = power * a                       # h^(n+1) for the next term
    spec = spec * (TWO_PI_G * drho * np.exp(-k * z0))
    out = sp_fft.irfft2(spec, s=a.shape).astype(np.float32)
    if pad:
        out = out[pad:-pad, pad:-pad]
    return out / MGal


def oldenburg_invert(gravity_mgal: np.ndarray, drho: float, z0: float, cell: float,
                     cutoff_wavelength_m: float = 8000.0, n_terms: int = 8,
                     n_iter: int = 25, pad: int = 96, tol: float = 1e-3,
                     relief_clip_fraction: float = 0.45, return_diagnostics: bool = False,
                     plateau_fraction: float = 0.5):
    """Iteratively invert an isostatic-gravity anomaly to basement relief.

    Returns ``relief`` in metres, positive upward, with zero mean (the DC term
    of the anomaly is a datum, not a relief).  ``depth = z0 - relief`` is the
    depth to the basement surface.
    """
    a = reflect_pad(np.asarray(gravity_mgal, np.float32), pad)
    ny, nx = a.shape
    k = wavenumbers(a.shape, cell)
    w = highcut_filter(k, cutoff_wavelength_m, plateau_fraction)

    g = (a.astype(np.float64) - float(np.mean(a))) * MGal      # m s^-2, zero mean
    gspec = sp_fft.rfft2(g.astype(np.float32))
    gspec[0, 0] = 0.0                                          # remove the datum

    # The exponential is only ever used inside the passband (W = 0 outside),
    # so clip the exponent there and keep the iteration numerically tame.
    kc = 2.0 * np.pi / float(cutoff_wavelength_m)
    k_exp = np.minimum(k, kc)
    scale = TWO_PI_G * float(drho)
    rhs0 = gspec * np.exp(k_exp * float(z0)) / scale

    relief = sp_fft.irfft2(rhs0 * w, s=(ny, nx)).astype(np.float32)
    limit = relief_clip_fraction * float(z0)
    np.clip(relief, -limit, limit, out=relief)

    history = []
    factorial = float(1.0)
    for _ in range(int(n_iter)):
        power = relief * relief                                # n = 2 seed
        series = np.zeros_like(gspec)
        for n in range(2, int(n_terms) + 1):
            if n == 2:
                factorial = 2.0
            else:
                factorial *= n
                power = power * relief
            series = series + sp_fft.rfft2(power) * (k_exp ** (n - 1)) / factorial
        new = sp_fft.irfft2((rhs0 - series) * w, s=(ny, nx)).astype(np.float32)
        np.clip(new, -limit, limit, out=new)
        delta = float(np.sqrt(np.mean((new - relief) ** 2)))
        relief = new
        history.append(delta)
        if delta < tol:
            break

    if pad:
        relief = relief[pad:-pad, pad:-pad]
    relief = relief - float(np.mean(relief))
    if return_diagnostics:
        return relief, dict(rms_update_m=history, n_iter_done=len(history),
                            cutoff_wavelength_m=float(cutoff_wavelength_m),
                            plateau_fraction=float(plateau_fraction),
                            drho=float(drho), z0=float(z0), n_terms=int(n_terms))
    return relief


def depth_from_relief(relief: np.ndarray, z0: float) -> np.ndarray:
    """Depth to the basement surface (m), ``depth = z0 - relief``."""
    return np.asarray(z0, dtype=np.float64) - np.asarray(relief, np.float64)


# --------------------------------------------------------------------------- #
# calibration of the density-contrast depth scale
# --------------------------------------------------------------------------- #
def robust_scale(reference: np.ndarray, estimate: np.ndarray, mask: np.ndarray) -> dict:
    """Least-squares slope/intercept and correlation of ``estimate`` on ``reference``.

    The slope is the *depth scale*: 1.0 means one metre of inverted relief per
    metre of independent basin-depth relief.
    """
    r = np.asarray(reference, np.float64)[mask]
    e = np.asarray(estimate, np.float64)[mask]
    if r.size < 100:
        raise ValueError("calibration mask too small")
    slope, intercept = np.polyfit(r, e, 1)
    corr = float(np.corrcoef(r, e)[0, 1])
    residual = e - (slope * r + intercept)
    return dict(n=int(r.size), slope=float(slope), intercept=float(intercept),
                pearson=corr, rmse_m=float(np.sqrt(np.mean(residual ** 2))),
                median_abs_error_m=float(np.median(np.abs(residual))))


def calibrate_depth_scale(gravity_mgal: np.ndarray, gp1012_reference, mask: np.ndarray,
                          cell: float,
                          drho_grid=(250.0, 300.0, 350.0, 400.0, 450.0, 500.0, 600.0, 700.0),
                          z0_grid=(500.0, 1000.0, 1500.0, 2000.0, 3000.0),
                          cutoff_grid=(4000.0, 8000.0, 16000.0),
                          n_iter: int = 12, n_terms: int = 6, pad: int = 64) -> dict:
    """Calibrate depth scale against a complete official GP-1012 source grid.

    GP-1012 is a 2 km regional model and its distributed XYZ header does not
    declare a geodetic datum, so this routine compares global summary statistics
    only. It refuses numpy arrays (including organizer band 15) rather than
    silently treating an unrelated grid as the calibration target. The resulting
    scale fit does not validate local candidate-fault geometry.
    """
    from .gp1012 import GP1012Grid

    if not isinstance(gp1012_reference, GP1012Grid):
        raise RuntimeError(
            "GP-1012 calibration blocked: pass a complete read_gp1012_xyz() grid; "
            "organizer band 15 is prohibited"
        )
    observed = np.asarray(gravity_mgal, np.float32)
    valid = np.asarray(mask, bool)
    if observed.ndim != 2 or observed.shape != valid.shape:
        raise ValueError("gravity and mask must be matching 2-D arrays")
    if cell <= 0:
        raise ValueError("cell spacing must be positive")
    target = gp1012_reference.summary()
    target_p50, target_p90 = float(target["p50_m"]), float(target["p90_m"])
    target_deep = float(target["fraction_gt_1km"])
    results = []
    for drho in drho_grid:
        if float(drho) <= 0:
            raise ValueError("drho is basement-minus-fill and must be positive")
        for z0 in z0_grid:
            for cutoff in cutoff_grid:
                relief, diag = oldenburg_invert(
                    observed, drho, z0, cell, cutoff_wavelength_m=cutoff,
                    n_iter=n_iter, n_terms=n_terms, pad=pad, return_diagnostics=True)
                depth = np.maximum(depth_from_relief(relief, z0), 0.0)
                values = depth[valid & np.isfinite(depth)]
                if values.size == 0:
                    raise ValueError("no valid inverted depths for calibration")
                stats = dict(p50_m=float(np.median(values)),
                             p90_m=float(np.percentile(values, 90)),
                             fraction_gt_1km=float((values > 1000.0).mean()))
                penalties = dict(
                    p50=abs(np.log(max(stats["p50_m"], 1.0) / max(target_p50, 1.0))),
                    p90=abs(np.log(max(stats["p90_m"], 1.0) / max(target_p90, 1.0))),
                    fraction_gt_1km=abs(np.log(max(stats["fraction_gt_1km"], 1e-6) /
                                               max(target_deep, 1e-6))),
                )
                results.append(dict(drho_kg_m3=float(drho), z0_m=float(z0),
                                    cutoff_wavelength_m=float(cutoff), stats=stats,
                                    penalties=penalties, penalty=float(sum(penalties.values())),
                                    n_iter_done=diag["n_iter_done"],
                                    last_update_m=(diag["rms_update_m"][-1]
                                                   if diag["rms_update_m"] else None)))
    results.sort(key=lambda row: row["penalty"])
    return dict(evidence_class="MODEL-CALIBRATION-TO-OFFICIAL-GP1012-SUMMARIES",
                reference=target, best=results[0], grid_search=results,
                calibration_scope="grid-wide p50, p90, fraction >1 km; no pixel alignment",
                limitations=["GP-1012 is a 2 km low-pass model, not a 100 m label",
                             "distributed header lacks geodetic datum; no pixelwise comparison",
                             "global-scale fit does not validate local fault geometry"])
