"""Parker (1973) forward operator and Oldenburg (1974) inversion.

The two anchors are physical, not empirical:

* an infinite Bouguer slab of thickness ``t`` and contrast ``drho`` produces
  exactly ``2*pi*G*drho*t`` mGal, independent of ``z0`` -- the operator must
  reproduce that to floating-point precision;
* a synthetic interface inverted with the same operator returns the interface,
  up to the low-pass taper that the method requires for stability.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import gravity as gv  # noqa: E402


def test_bouguer_slab_is_exact():
    """2*pi*G*drho*t mGal for a uniform slab, to 6 significant figures."""
    relief = np.full((64, 64), 500.0, np.float32)
    for z0 in (2000.0, 3000.0, 5000.0):
        g = gv.parker_forward(relief, 400.0, z0, 100.0, n_terms=6)
        expected = 2 * np.pi * gv.G * 400.0 * 500.0 * 1e5      # mGal
        assert float(g[32, 32]) == pytest.approx(expected, rel=1e-6)


def test_slab_response_is_flat_away_from_the_edges():
    relief = np.full((96, 96), 300.0, np.float32)
    g = gv.parker_forward(relief, 400.0, 3000.0, 100.0, n_terms=6)
    inner = g[20:76, 20:76]
    assert inner.std() / abs(inner.mean()) < 1e-3


def test_highcut_filter_is_a_plateau_then_a_cosine_rolloff():
    from gems61.gravity import highcut_filter, wavenumbers
    k = wavenumbers((64, 64), 100.0)
    f = highcut_filter(k, cutoff_wavelength_m=5000.0, plateau_fraction=0.5)
    assert f.shape == k.shape
    assert float(f.max()) == pytest.approx(1.0)
    assert float(f.min()) >= -1e-6
    # monotone non-increasing in |k|
    order = np.argsort(k.ravel())
    vals = f.ravel()[order]
    assert np.all(np.diff(vals) <= 1e-6)


def test_pure_oldenburg_taper_under_recovers_amplitude():
    """The reason ``plateau_fraction`` defaults to 0.5 and must not be zeroed.

    With no plateau the taper starts attenuating at the very lowest wavenumbers
    and a uniform slab loses most of its amplitude.  This test is the guard
    against 'simplifying' the taper away.
    """
    relief = np.full((128, 128), 500.0, np.float32)
    exact = 2 * np.pi * gv.G * 400.0 * 500.0 * 1e5
    # parker_forward is the plain operator; the taper only enters the inversion.
    g = gv.parker_forward(relief, 400.0, 3000.0, 100.0, n_terms=6, pad=64)
    assert abs(float(g[64, 64]) / exact - 1.0) < 0.02
    # with no plateau the taper attenuates from k = 0 and the slab is lost
    k = gv.wavenumbers((256, 256), 100.0)
    w05 = gv.highcut_filter(k, 5000.0, 0.5)
    w00 = gv.highcut_filter(k, 5000.0, 0.0)
    # a 20 km feature: k = 2pi/20000 sits inside the 0.5*kc plateau of a
    # 5 km cutoff, so the plateau taper passes it untouched while the pure
    # cosine taper has already rolled it off
    i = int(np.argmin(np.abs(k[0] - 2 * np.pi / 20000.0)))
    assert w05[0, i] == pytest.approx(1.0, abs=1e-6)
    assert 0.0 < w00[0, i] < 0.95


def test_inversion_round_trip_recovers_a_smooth_interface():
    rng = np.random.default_rng(3)
    h, w = 128, 128
    yy, xx = np.mgrid[0:h, 0:w]
    # Wavelengths 6.1, 4.3 and 2.9 km; the high-cut keeps wavelengths LONGER
    # than the cutoff, and 1000 m puts all three inside the flat plateau of the
    # taper.  Relief is 135 m against z0 = 2000 m, i.e. |h|/z0 = 0.07, which is
    # the regime in which Parker's power series converges fast enough for the
    # iteration to be exact.  (At |h|/z0 = 0.22 the same test recovers a slope
    # near 1 only if the cutoff is widened; the degradation is a property of
    # the series, not of this implementation.)
    truth = (90.0 * np.sin(2 * np.pi * xx / 61.0) * np.cos(2 * np.pi * yy / 43.0)
             + 45.0 * np.sin(2 * np.pi * (xx + yy) / 29.0)).astype(np.float32)
    g = gv.parker_forward(truth, 400.0, 2000.0, 100.0, n_terms=6, pad=64)
    est, diag = gv.oldenburg_invert(g, 400.0, 2000.0, 100.0, cutoff_wavelength_m=1000.0,
                                    n_iter=25, n_terms=6, pad=64, return_diagnostics=True)
    a = truth[32:96, 32:96].ravel()
    b = est[32:96, 32:96].ravel()
    slope = float(np.polyfit(a, b, 1)[0])
    corr = float(np.corrcoef(a, b)[0, 1])
    assert diag["n_iter_done"] >= 1
    assert slope == pytest.approx(1.0, abs=0.02)
    assert corr > 0.999
    assert float(np.abs(b - a).max()) < 10.0      # metres


def test_depth_from_relief_sign_convention():
    """Positive relief (a basement high) is a *smaller* depth to basement."""
    relief = np.array([[0.0, 500.0]], np.float32)
    depth = gv.depth_from_relief(relief, z0=2000.0)
    assert depth[0, 0] == pytest.approx(2000.0)
    assert depth[0, 1] == pytest.approx(1500.0)
    assert depth[0, 1] < depth[0, 0]


def test_inpaint_fills_holes_and_leaves_valid_cells_untouched():
    rng = np.random.default_rng(5)
    field = rng.normal(0, 1, (64, 64)).astype(np.float32)
    valid = np.ones((64, 64), bool)
    valid[20:30, 20:30] = False
    filled = gv.inpaint(field, valid)
    assert np.isfinite(filled).all()
    np.testing.assert_allclose(filled[valid], field[valid], atol=1e-5)


def test_robust_scale_reports_a_slope_and_a_correlation():
    rng = np.random.default_rng(9)
    ref = rng.normal(500, 200, 4000).astype(np.float32)
    est = ref * 0.9 + rng.normal(0, 50, 4000)
    m = np.ones(4000, bool)
    rep = gv.robust_scale(ref, est, m)
    assert rep["slope"] == pytest.approx(0.9, abs=0.05)
    assert rep["pearson"] > 0.9
    assert rep["rmse_m"] < 120.0
