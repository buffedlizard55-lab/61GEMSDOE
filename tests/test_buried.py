"""Band-13-only basement-step transforms and non-fault mimic."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import buried as B  # noqa: E402


def test_preregistered_wiener_corner_and_first_iterate_are_exact():
    dg = np.zeros((32, 32), np.float32)
    valid = np.ones_like(dg, bool)
    sol = B.slab_solution(dg, valid, delta_rho=-400.0, z0=1000.0,
                          dx=400.0, filter_order=2.0, kc_scale=1.0)
    assert sol["filter"].startswith("Wiener order 2.0, kc = kc_scale/(2*z0)")
    assert sol["stage"].startswith("first iterate")
    assert np.allclose(sol["depth_m"], 1000.0)
    with pytest.raises(ValueError, match="positive"):
        B.slab_solution(dg, valid, delta_rho=-400.0, z0=1000.0,
                        dx=400.0, kc_scale=0.0)


def test_signed_flank_persistence_detects_same_sign_step():
    depth = np.full((80, 100), 1000.0, np.float32)
    depth[:, 50:] = 1800.0
    result = B.signed_flank_persistence(depth, dx=100.0,
                                        apertures_m=(400.0, 800.0))
    assert result["persistence"][40, 49] == pytest.approx(1.0, abs=1e-5)
    assert result["same_sign"][40, 49]
    assert result["signed_deltas"][:, 40, 49].tolist() == pytest.approx([800.0, 800.0])


def test_signed_flank_maxima_do_not_require_the_flank_samples_to_be_maxima():
    depth = np.full((100, 160), 1000.0, np.float32)
    depth[:, 80:] = 1800.0
    valid = np.ones_like(depth, bool)
    maxima = np.zeros_like(valid)
    maxima[50, 79] = True
    result = B.signed_flank_persistence(depth, dx=100.0,
                                        apertures_m=(2000.0, 4000.0),
                                        valid=valid, maxima=maxima)
    assert result["valid"][50, 79]
    assert result["same_sign"][50, 79]
    assert result["persistence"][50, 79] == pytest.approx(1.0)
    assert result["signed_deltas"][:, 50, 79].tolist() == pytest.approx([800.0, 800.0])


def test_density_sheet_mimic_is_finite_and_has_no_depth_displacement_input():
    body = np.zeros((64, 64), bool)
    body[24:40, 24:40] = True
    gravity = B.buried_density_sheet_gravity(
        body, density_contrast_kg_m3=250.0, thickness_m=500.0,
        depth_m=1500.0, dx=400.0)
    assert gravity.shape == body.shape
    assert np.isfinite(gravity).all()
    assert float(np.max(np.abs(gravity))) > 0.0
    # This control contains only a density sheet; no basement-depth step is
    # passed to the forward operator.


def test_blakely_maxima_do_not_wrap_across_grid_edges_or_promote_border_peaks():
    field = np.zeros((9, 9), np.float32)
    field[4, 0] = 5.0
    field[4, 4] = 10.0
    maxima = B.blakely_simpson_maxima(field)
    assert not maxima[4, 0]
    assert maxima[4, 4]
