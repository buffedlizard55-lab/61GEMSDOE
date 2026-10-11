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


# --------------------------------------------------------------- uniqueness
def test_spearman_is_one_for_a_monotone_transform():
    rng = np.random.default_rng(12)
    a = rng.random(5000)
    m = np.ones(5000, bool)
    assert uq.spearman(a, a ** 3, m) == pytest.approx(1.0)
    assert uq.spearman(a, -a, m) == pytest.approx(-1.0)


def test_spearman_detects_a_copy():
    rng = np.random.default_rng(13)
    a = rng.random(5000)
    m = np.ones(5000, bool)
    # a copy with 5 % pixel noise must still read as a copy
    b = a + rng.normal(0, 0.01, 5000)
    assert uq.spearman(a, b, m) > 0.98


def test_dot_overlap_is_one_for_identical_dots():
    dots = np.zeros((50, 50), bool)
    dots[10, 5:25] = True
    assert uq.dot_overlap(dots, dots, 3.0)["fraction"] == pytest.approx(1.0)


def test_dot_overlap_is_zero_for_disjoint_dots():
    a = np.zeros((60, 60), bool)
    a[10, 5:25] = True
    b = np.zeros((60, 60), bool)
    b[50, 5:25] = True
    assert uq.dot_overlap(a, b, 3.0)["fraction"] == pytest.approx(0.0)


def test_dot_overlap_partial_case():
    a = np.zeros((60, 60), bool)
    a[10, 0:20] = True          # 20 dots
    b = np.zeros((60, 60), bool)
    b[13, 0:10] = True          # 3 px directly above the first 10, 3.16 px from #11
    assert uq.dot_overlap(a, b, 3.0)["fraction"] == pytest.approx(0.5)


def test_sha256_is_stable():
    import hashlib
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False) as fh:
        fh.write(b"61GEMSDOE")
        name = fh.name
    assert uq.sha256(Path(name)) == hashlib.sha256(b"61GEMSDOE").hexdigest()


def test_missing_registry_fails_closed(tmp_path):
    """An empty registry is not evidence of uniqueness."""
    with pytest.raises(Exception):
        uq.check(np.zeros((10, 10), np.float32), None, np.ones((10, 10), bool),
                 root=tmp_path)


# ------------------------------------------------------- dot-leg scope rule
def _fake_registry(tmp_path, rasters):
    """Write a minimal but complete registry: check() must fail closed without one."""
    import json
    import rasterio
    from affine import Affine

    (tmp_path / "evidence").mkdir(exist_ok=True)
    (tmp_path / "cache").mkdir(exist_ok=True)
    recs = []
    for i, arr in enumerate(rasters):
        name = f"cache/r{i}.tif"
        with rasterio.open(tmp_path / name, "w", driver="GTiff", height=arr.shape[0],
                           width=arr.shape[1], count=1, dtype="float32",
                           crs="EPSG:32611",
                           transform=Affine(100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)) as dst:
            dst.write(arr.astype(np.float32), 1)
        recs.append(dict(sha256=f"sha{i}", cache_file=name, sources=[f"repo{i}:f{i}.tif"],
                         comparable=True, reason=""))
    (tmp_path / "evidence/registry_refreshed.json").write_text(
        json.dumps(dict(complete_accessible_scan=True, rasters=recs)))
    return tmp_path


def test_dot_leg_is_skipped_for_a_dense_probability_field(tmp_path):
    """A continuous probability map is positive almost everywhere, so the 3 px
    overlap test would score 1.0 against ANY candidate.  It must be excluded
    from the dot leg and compared on the surface leg instead."""
    fp = np.ones((40, 40), bool)
    dense = np.linspace(0.001, 1.0, 1600).reshape(40, 40).astype(np.float32)
    dots = np.zeros((40, 40), bool)
    dots[5, 5:15] = True
    _fake_registry(tmp_path, [dense])
    out = uq.check(np.zeros((40, 40), np.float32), dots, fp, root=tmp_path)
    assert out["dot_leg_scope"]["applicable"] == 0
    assert out["dot_leg_scope"]["vacuous_excluded"] == 1
    assert out["per_raster"][0]["dot_overlap_3px"] is None
    # and the gate fails closed rather than reporting a vacuous pass
    assert out["dot_gate_pass"] is False
    assert out["unique"] is False


def test_dot_leg_is_skipped_for_a_uniform_lattice(tmp_path):
    """A 5 px lattice is only 4 % dense but lies within 3 px of ~100 % of the
    footprint, so the raw overlap test is just as vacuous as for a dense map.
    Density alone is not the right criterion; footprint coverage is."""
    fp = np.ones((40, 40), bool)
    lattice = np.zeros((40, 40), np.float32)
    lattice[::5, ::5] = 1.0
    assert 0.0 < lattice.mean() < 0.05                 # sparse by density ...
    dots = np.zeros((40, 40), bool)
    dots[5, 5:15] = True
    _fake_registry(tmp_path, [lattice])
    out = uq.check(np.zeros((40, 40), np.float32), dots, fp, root=tmp_path)
    assert out["per_raster"][0]["footprint_coverage_within_3px"] > 0.9   # ... not by coverage
    assert out["dot_leg_scope"]["applicable"] == 0
    assert out["per_raster"][0]["dot_overlap_3px"] is None


def test_dot_leg_runs_for_a_sparse_raster(tmp_path):
    fp = np.ones((40, 40), bool)
    sparse = np.zeros((40, 40), np.float32)
    sparse[20, 5:25] = 1.0
    dots = np.zeros((40, 40), bool)
    dots[20, 5:25] = True
    _fake_registry(tmp_path, [sparse])
    out = uq.check(np.zeros((40, 40), np.float32), dots, fp, root=tmp_path)
    assert out["dot_leg_scope"]["applicable"] == 1
    assert out["per_raster"][0]["dot_overlap_3px"] == pytest.approx(1.0)
    assert out["dot_gate_pass"] is False          # a copy is not unique
