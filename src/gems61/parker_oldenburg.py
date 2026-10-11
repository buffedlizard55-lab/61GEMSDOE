"""Parker (1973) / Oldenburg (1974) inversion of gravity to basement relief.

Parker, R. L. (1973). The rapid calculation of potential anomalies.
    Geophysical Journal of the Royal Astronomical Society 31(4), 447-455.
Oldenburg, D. W. (1974). The inversion and interpretation of gravity anomalies.
    Geophysics 39(4), 526-536.

Fourier-domain forward relation for an interface at mean depth ``z0`` with relief
``h(x, y)`` (positive *up*, i.e. shallower basement) and density contrast
``drho = rho_basement - rho_fill > 0``:

    F[dg](k) = 2*pi*G*drho * exp(-|k| z0) * sum_{n>=1} |k|^(n-1)/n! * F[h^n](k)

Oldenburg inverts this by fixed-point iteration, damping the exponentially growing
``exp(+|k| z0)`` factor with a low-pass filter.  Units: ``dg`` in mGal, ``h``/``z0``
in metres, ``drho`` in kg/m^3, ``G = 6.674e-11`` SI (1 mGal = 1e-5 m/s^2, so the
Bouguer-slab factor is 2*pi*G/1e-5 = 4.1932e-5 mGal per (kg/m^3 * m)).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

G_SI = 6.674e-11
MGAL = 1e-5
BOUGUER = 2.0 * np.pi * G_SI / MGAL  # 4.1932e-5 mGal per (kg/m^3 * m)


@dataclass
class ParkerOldenburg:
    z0: float = 400.0          # mean interface depth below datum, m
    drho: float = 222.0        # density contrast, kg/m^3
    dx: float = 100.0          # grid spacing, m
    n_iter: int = 5            # Oldenburg iterations
    order: int = 3             # highest Parker term retained
    cutoff_m: float = 2500.0   # low-pass cutoff wavelength, m
    h_clip: float = 4000.0     # relief clamp for stability, m
    log: dict = field(default_factory=dict)

    # -- internals ---------------------------------------------------------
    def _k_grid(self, shape):
        H, W = shape
        kx = 2 * np.pi * np.fft.fftfreq(W, d=self.dx)
        ky = 2 * np.pi * np.fft.fftfreq(H, d=self.dx)
        KX, KY = np.meshgrid(kx, ky)
        return np.sqrt(KX * KX + KY * KY)

    def _lowpass(self, K):
        kc = 2 * np.pi / self.cutoff_m
        return np.exp(-(K / kc) ** 2)

    # -- public ------------------------------------------------------------
    def invert(self, dg_mgal: np.ndarray, valid: np.ndarray | None = None) -> np.ndarray:
        """Return basement relief ``h`` (m, positive up) for an anomaly grid in mGal."""
        g = np.array(dg_mgal, dtype=np.float64)
        if valid is not None:
            g = np.where(valid, g, np.nan)
        # NaN-safe fill: iterative local-mean fill (avoids FFT ringing from holes)
        nan = ~np.isfinite(g)
        if nan.any():
            g = _fill_nan(g, max_iter=25)
        K = self._k_grid(g.shape)
        LP = self._lowpass(K)
        down = np.exp(-np.minimum(K * self.z0, 60.0))     # Parker's attenuation factor
        up = np.exp(np.minimum(K * self.z0, 60.0)) * LP   # damped deconvolution operator
        coef = BOUGUER * self.drho                        # mGal per metre of relief

        Fg = np.fft.fft2(g)                               # work in mGal
        h = np.real(np.fft.ifft2(Fg * up / coef))
        h = np.clip(h, -self.h_clip, self.h_clip)
        misfit = []
        for _ in range(self.n_iter):
            # higher-order (non-linear) Parker terms for the current relief estimate
            corr = np.zeros_like(Fg)
            hn = np.ones_like(h)
            for m in range(2, self.order + 1):
                hn = hn * h
                corr = corr + (K ** (m - 1)) / math.factorial(m) * np.fft.fft2(hn)
            h_new = np.real(np.fft.ifft2((Fg - coef * down * corr) * up / coef))
            h_new = np.clip(h_new, -self.h_clip, self.h_clip)
            misfit.append(float(np.nanstd(h_new - h)))
            h = h_new
        # forward-model residual of the converged solution (mGal)
        corr = np.zeros_like(Fg)
        hn = np.ones_like(h)
        Fh = np.fft.fft2(h)
        for m in range(2, self.order + 1):
            hn = hn * h
            corr = corr + (K ** (m - 1)) / math.factorial(m) * np.fft.fft2(hn)
        pred = np.real(np.fft.ifft2(coef * down * (Fh + corr)))
        rms_mgal = float(np.sqrt(np.nanmean((pred - g) ** 2)))
        self.log = dict(n_iter=self.n_iter, order=self.order, z0=self.z0,
                        drho=self.drho, cutoff_m=self.cutoff_m,
                        rms_step_per_iter=misfit,
                        h_mean=float(np.nanmean(h)), h_std=float(np.nanstd(h)),
                        h_min=float(np.nanmin(h)), h_max=float(np.nanmax(h)))
        return h


def _fill_nan(a: np.ndarray, max_iter: int = 25) -> np.ndarray:
    """Fill NaNs with the mean of finite 8-neighbours, iteratively."""
    from scipy import ndimage

    out = a.copy()
    w = np.ones((3, 3))
    w[1, 1] = 0
    for _ in range(max_iter):
        nan = ~np.isfinite(out)
        if not nan.any():
            break
        filled = np.where(nan, 0.0, out)
        s = ndimage.convolve(filled, w, mode="nearest")
        n = ndimage.convolve((~nan).astype(float), w, mode="nearest")
        mean = np.where(n > 0, s / np.maximum(n, 1e-9), 0.0)
        out = np.where(nan & (n > 0), mean, out)
    out[~np.isfinite(out)] = float(np.nanmedian(out)) if np.isfinite(out).any() else 0.0
    return out
