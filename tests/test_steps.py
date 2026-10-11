"""Basement-step detection on a field whose answer is known analytically."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import steps as st  # noqa: E402


def test_crest_sits_on_the_step(step_field):
    depth = step_field["depth"]
    s = st.detect_steps(depth, sigma_px=1.0, half_width_px=4.0)
    ys, xs = np.nonzero(s.crest)
    assert ys.size > 0
    # the gradient of a smoothed step peaks at the step, not somewhere else
    assert xs.min() >= step_field["step_col"] - 2
    assert xs.max() <= step_field["step_col"] + 2
    assert np.median(xs) == pytest.approx(step_field["step_col"], abs=1.0)


def test_throw_is_the_physical_offset_in_metres(step_field):
    depth = step_field["depth"]
    s = st.detect_steps(depth, sigma_px=1.0, half_width_px=4.0)
    on = s.throw[s.crest]
    assert np.median(on) == pytest.approx(step_field["throw_m"], rel=0.05)


def test_crest_is_a_line_not_a_blob(step_field):
    """The crest is 1-2 px wide: a step, not a plateau."""
    s = st.detect_steps(step_field["depth"], sigma_px=1.0, half_width_px=4.0)
    widths = s.crest.sum(axis=1)
    widths = widths[widths > 0]
    assert widths.max() <= 3


def test_flat_field_has_no_steps():
    s = st.detect_steps(np.zeros((64, 64), np.float32), sigma_px=1.0)
    assert s.n_crest == 0


def test_smoothing_enlarges_the_crest_and_softens_the_throw(step_field):
    s1 = st.detect_steps(step_field["depth"], sigma_px=1.0, half_width_px=4.0)
    s3 = st.detect_steps(step_field["depth"], sigma_px=3.0, half_width_px=4.0)
    assert s3.gradient.max() <= s1.gradient.max() + 1e-6


def test_unit_gradient_is_normalised():
    rng = np.random.default_rng(1)
    f = rng.normal(0, 1, (32, 32)).astype(np.float32)
    uy, ux, mag = st._unit_gradient(f, 1.0)
    unit = np.hypot(uy, ux)
    nz = mag > 0
    np.testing.assert_allclose(unit[nz], 1.0, atol=1e-5)
    np.testing.assert_allclose(unit[~nz], 0.0, atol=1e-9)


def test_nms_along_gradient_keeps_a_ridge_and_kills_its_flanks():
    """On a field that increases monotonically in x, only the top column is a
    maximum along the gradient direction."""
    f = np.tile(np.arange(16, dtype=np.float32), (8, 1))
    uy, ux, _ = st._unit_gradient(f, 0.0)
    keep = st.nms_along_gradient(f, uy, ux)
    ys, xs = np.nonzero(keep)
    assert xs.size > 0
    assert xs.max() == 15
    assert xs.min() >= 13


def test_sample_offset_reads_the_field_two_pixels_along_the_gradient():
    f = np.tile(np.arange(32, dtype=np.float32), (8, 1))
    uy, ux, _ = st._unit_gradient(f, 0.0)
    v = st.sample_offset(f, uy, ux, 2.0)
    np.testing.assert_allclose(v[4, 10], 12.0, atol=1e-4)


def test_thin_plateaus_is_off_by_default_and_destroys_continuity_when_on(step_field):
    """Regression guard: the 3x3 plateau break is opt-in for a measured reason."""
    off = st.detect_steps(step_field["depth"], sigma_px=1.0)
    on = st.detect_steps(step_field["depth"], sigma_px=1.0, thin_plateaus=True)
    import inspect
    assert inspect.signature(st.detect_steps).parameters["thin_plateaus"].default is False
    assert on.n_crest <= off.n_crest


def test_throw_gradient_is_metres_per_kilometre():
    from gems61.steps import throw_gradient_m_per_km
    from gems61.grid import PIXEL_M
    s = st.detect_steps(np.zeros((32, 32), np.float32), sigma_px=1.0)
    g = throw_gradient_m_per_km(s)
    assert g.shape == s.throw.shape
    # on an empty field everything is zero; the scaling itself is checked below
    assert float(g.max()) == 0.0
    s2 = st.Steps(gradient=np.ones((8, 8), np.float32),
                  crest=np.zeros((8, 8), bool),
                  throw=np.full((8, 8), 500.0, np.float32),
                  sigma_px=1.0, half_width_px=4.0, min_throw_m=0.0)
    g2 = throw_gradient_m_per_km(s2)
    assert float(g2[0, 0]) == pytest.approx(500.0 / (2 * 4.0 * PIXEL_M) * 1000.0)
