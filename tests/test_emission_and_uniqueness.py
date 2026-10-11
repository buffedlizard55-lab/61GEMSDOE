"""Emission geometry and the uniqueness drift gate."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import emission as em, uniqueness as uq  # noqa: E402


# ----------------------------------------------------------------- emission
def test_ribbon_mask_places_lines_on_both_sides_at_the_requested_offsets():
    crest = np.zeros((31, 31), bool)
    crest[:, 15] = True
    mask, d = em.ribbon_mask(crest, offsets_px=(0.0, 3.0))
    cols = sorted(set(np.nonzero(mask)[1].tolist()))
    assert cols == [12, 15, 18]
    # distance to the crest is the requested offset on each added line, 0 on the crest
    assert np.allclose(d[mask][np.isin(np.nonzero(mask)[1], [12, 18])], 3.0)
    assert np.allclose(d[mask][np.isin(np.nonzero(mask)[1], [15])], 0.0)


def test_thin_to_dots_respects_the_requested_separation():
    from scipy.ndimage import distance_transform_edt
    mask = np.zeros((60, 60), bool)
    mask[10, :] = True
    mask[30, :] = True
    score = np.float32(mask)
    dots = em.thin_to_dots(mask, score, 3.0)
    ys, xs = np.nonzero(dots)
    assert ys.size > 0
    # no two dots closer than the separation along a line
    for row in (10, 30):
        c = np.sort(xs[ys == row])
        assert np.all(np.diff(c) >= 3)


def test_dots_land_on_the_high_score_cells():
    mask = np.zeros((20, 20), bool)
    mask[5, :] = True
    score = np.zeros((20, 20), np.float32)
    score[5, 7] = 10.0
    dots = em.thin_to_dots(mask, score, 3.0)
    assert dots[5, 7]


def test_apply_budget_keeps_exactly_the_top_n():
    rng = np.random.default_rng(2)
    mask = rng.random((40, 40)) > 0.5
    score = rng.random((40, 40)).astype(np.float32)
    out = em.apply_budget(mask, score, 100)
    assert int(out.sum()) == min(100, int(mask.sum()))
    kept = score[out]
    dropped = score[mask & ~out]
    if dropped.size:
        assert kept.min() >= dropped.max() - 1e-6


def test_prune_near_removes_dots_on_the_catalogue():
    dots = np.zeros((30, 30), bool)
    dots[10, 10] = True
    dots[20, 20] = True
    cat = np.zeros((30, 30), bool)
    cat[10, 10] = True
    out = em.prune_near(dots, cat, 2)
    assert not out[10, 10]
    assert out[20, 20]


def test_nearest_crest_value_propagates_the_crest_value_outwards():
    crest = np.zeros((20, 20), bool)
    crest[:, 10] = True
    values = np.where(crest, 500.0, 0.0).astype(np.float32)
    v = em.nearest_crest_value(values, crest)
    assert v[0, 12] == pytest.approx(500.0)
    assert v[0, 10] == pytest.approx(500.0)


def test_ribbon_gain_table_is_monotone_in_the_positional_error():
    """Wider ribbons pay only once the positional error is large."""
    rows = em.ribbon_gain_table(sigma_px=(1.0, 3.0), spacings=(3.0,), max_lines=2)
    get = {(r["sigma_px"], r["n_lines"]): r["mean_dti"] for r in rows}
    # at a 1 px error one line beats two; at 3 px two lines beat one
    assert get[(1.0, 1)] > get[(1.0, 2)]
    assert get[(3.0, 2)] > get[(3.0, 1)]
    # k == 1 reproduces the single line exactly
    assert get[(1.0, 1)] == pytest.approx(
        [r["single_line_dti"] for r in rows if r["sigma_px"] == 1.0][0])


# ---------------------------------------------------------- shared strict gate
def test_surface_spearman_is_one_for_a_monotone_transform():
    rng = np.random.default_rng(12)
    a = rng.random((50, 100))
    mask = np.ones(a.shape, bool)
    assert uq.surface_rho(a, a ** 3, mask)["spearman_full_footprint"] == pytest.approx(1.0)
    assert uq.surface_rho(a, -a, mask)["spearman_full_footprint"] == pytest.approx(-1.0)


def test_surface_spearman_detects_a_copy():
    rng = np.random.default_rng(13)
    a = rng.random((50, 100))
    mask = np.ones(a.shape, bool)
    b = a + rng.normal(0, 0.01, a.shape)
    assert uq.surface_rho(a, b, mask)["spearman_full_footprint"] > 0.98


def test_one_sided_overlap_counts_every_positive_and_uses_three_pixels():
    dots = np.zeros((60, 60), bool)
    dots[10, 5:25] = True
    same = np.zeros_like(dots)
    same[13, 5:15] = True  # exactly 3 px from 10 of 20 candidate cells
    assert uq.dot_overlap(dots, dots, px=3.0) == pytest.approx(1.0)
    assert uq.dot_overlap(dots, same, px=3.0) == pytest.approx(0.5)


def test_one_sided_overlap_is_zero_for_disjoint_support():
    a = np.zeros((60, 60), bool)
    a[10, 5:25] = True
    b = np.zeros((60, 60), bool)
    b[50, 5:25] = True
    assert uq.dot_overlap(a, b, px=3.0) == pytest.approx(0.0)
