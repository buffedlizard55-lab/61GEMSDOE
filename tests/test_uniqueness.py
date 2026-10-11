"""Regression tests for the protocol thresholds and diagnostic-only Jaccard."""
import hashlib

import numpy as np
import pytest
import rasterio
from affine import Affine

from gems61.uniqueness import (JACCARD_LIMIT, OVERLAP_LIMIT, RHO_LIMIT,
                               compare_array_to_registry, dot_overlap, surface_rho)

SHAPE = (400, 400)


def _sparse(seed, n):
    rng = np.random.default_rng(seed)
    a = np.zeros(SHAPE, bool)
    a[rng.integers(0, SHAPE[0], n), rng.integers(0, SHAPE[1], n)] = True
    return a


def test_disjoint_sparse_rasters_are_not_flagged_as_duplicates():
    """Two near-disjoint sparse rasters must NOT trip the duplicate screen.

    Their dot-union Spearman is strongly *negative* (phi of two negatively
    associated indicators); the screen must read signed agreement only.
    """
    a = _sparse(1, 3000).astype(np.float32)
    b = _sparse(2, 3000).astype(np.float32)
    valid = np.ones(SHAPE, bool)
    r = surface_rho(a, b, valid)
    assert r["spearman_on_dot_union"] < 0.0, "disjoint supports must give negative rho"
    assert not (r["spearman_on_dot_union"] > RHO_LIMIT)
    assert r["jaccard_dot_sets"] < JACCARD_LIMIT
    assert dot_overlap(a, b) < OVERLAP_LIMIT


def test_dot_union_rho_is_undefined_when_one_support_contains_the_other():
    """A superset relation makes the dot-union statistic constant, hence NaN.

    It must NOT be reported as +1.0, and the screen must not threshold it.
    """
    a = _sparse(3, 3000).astype(np.float32)
    r = surface_rho(a, a.copy(), np.ones(SHAPE, bool))
    assert np.isnan(r["spearman_on_dot_union"])
    # but the full-footprint rank correlation does see the exact copy
    assert r["spearman_full_footprint"] == pytest.approx(1.0, abs=1e-9)
    assert r["spearman_full_footprint"] > RHO_LIMIT
    assert r["jaccard_dot_sets"] == pytest.approx(1.0)


def test_a_90_percent_copy_exceeds_the_jaccard_diagnostic_threshold():
    a = _sparse(4, 4000).astype(np.float32)
    b = a.copy()
    ys, xs = np.nonzero(b)
    rng = np.random.default_rng(9)
    k = len(ys) // 10
    b[ys[:k], xs[:k]] = False
    b[rng.integers(0, SHAPE[0], k), rng.integers(0, SHAPE[1], k)] = True
    r = surface_rho(a, b, np.ones(SHAPE, bool))
    # measured: rho_full = 0.8985 (just under the bar), jaccard = 0.8198.
    # Jaccard highlights a near-copy diagnostically; the protocol's rho/forward-overlap
    # thresholds remain the only uniqueness stop rules.
    assert r["spearman_full_footprint"] == pytest.approx(0.8985, abs=0.01)
    assert r["jaccard_dot_sets"] == pytest.approx(0.8198, abs=0.01)
    assert r["jaccard_dot_sets"] > JACCARD_LIMIT


def test_overlap_is_asymmetric_and_directional():
    a = _sparse(5, 2000).astype(np.float32)
    b = _sparse(6, 2000).astype(np.float32)
    assert 0.0 <= dot_overlap(a, b) <= 1.0
    assert dot_overlap(a, np.zeros(SHAPE, bool)) == 0.0


def test_full_footprint_rho_is_the_degenerate_one():
    """Sanity: on the whole footprint both arrays are ~99 % zero, so rho ~ 0."""
    a = _sparse(7, 3000).astype(np.float32)
    b = _sparse(8, 3000).astype(np.float32)
    r = surface_rho(a, b, np.ones(SHAPE, bool))
    assert abs(r["spearman_full_footprint"]) < 0.05


def test_jaccard_above_diagnostic_threshold_does_not_add_a_stop_rule(tmp_path):
    candidate = np.zeros(SHAPE, dtype=np.float32)
    prior = np.zeros(SHAPE, dtype=np.float32)
    points = [(10 + 20 * x, 10 + 20 * y) for y in range(10) for x in range(10)]
    for y, x in points:
        candidate[y, x] = 1.0
    for y, x in points[:65]:
        prior[y, x] = 1.0
    for y, x in [(250 + 20 * (i // 5), 20 + 20 * (i % 5)) for i in range(25)]:
        prior[y, x] = 1.0

    path = tmp_path / "prior.tif"
    with rasterio.open(path, "w", driver="GTiff", height=SHAPE[0], width=SHAPE[1],
                       count=1, dtype="float32", crs="EPSG:32611",
                       transform=Affine(100, 0, 0, 0, -100, 40000)) as dst:
        dst.write(prior, 1)
    manifest = {
        "complete_accessible_scan": True,
        "errors": [],
        "rasters": [{"repo_first": "fixture", "sources": ["fixture:prior"],
                      "cache_file": str(path),
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}],
    }
    report = compare_array_to_registry(candidate, manifest, np.ones(SHAPE, bool))
    row = report["rows"][0]
    assert row["spearman_full_footprint"] < RHO_LIMIT
    assert row["my_dots_within_3px_of_theirs"] == pytest.approx(0.65)
    assert row["jaccard_dot_sets"] > JACCARD_LIMIT
    assert row["duplicate_by_jaccard"] is True
    assert report["jaccard_diagnostic_only"] is True
    assert report["duplicate_count"] == 0 and report["unique"]


def _dense_reference_with_overlap(candidate, n_overlap):
    """Create a >5x reference whose Jaccard is tiny but forward overlap is exact."""
    prior = np.zeros(SHAPE, dtype=np.float32)
    ys, xs = np.nonzero(candidate)
    for y, x in zip(ys[:n_overlap], xs[:n_overlap]):
        prior[y, x] = 1.0
    # Add distant reference dots so the reference is much denser than the candidate
    # without changing the candidate's within-3-pixel overlap.
    for i in range(1000):
        y = 200 + (i // 40) * 8
        x = 5 + (i % 40) * 8
        prior[y, x] = 1.0
    return prior


def test_dense_reference_does_not_replace_literal_70_percent_overlap_gate(tmp_path):
    candidate = np.zeros(SHAPE, dtype=np.float32)
    points = [(10 + 10 * (i // 10), 10 + 10 * (i % 10)) for i in range(100)]
    for y, x in points:
        candidate[y, x] = 1.0
    path = tmp_path / "dense-prior.tif"
    transform = Affine(100, 0, 0, 0, -100, 40000)
    valid = np.ones(SHAPE, bool)

    for n_overlap, should_duplicate in ((70, False), (71, True)):
        prior = _dense_reference_with_overlap(candidate, n_overlap)
        with rasterio.open(path, "w", driver="GTiff", height=SHAPE[0], width=SHAPE[1],
                           count=1, dtype="float32", crs="EPSG:32611", transform=transform) as dst:
            dst.write(prior, 1)
        manifest = {"complete_accessible_scan": True, "errors": [], "rasters": [
            {"sources": ["fixture:dense-prior"], "cache_file": str(path),
             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]}
        report = compare_array_to_registry(candidate, manifest, valid)
        row = report["rows"][0]
        assert row["my_dots_within_3px_of_theirs"] == pytest.approx(n_overlap / 100)
        assert row["jaccard_dot_sets"] < JACCARD_LIMIT
        assert row["overlap_gate_rule"] == "one-sided 3 px overlap"
        assert row["overlap_gate_exceeded"] is should_duplicate
        assert report["duplicate_count"] == int(should_duplicate)
        assert report["unique"] is (not should_duplicate)


def test_high_positive_rank_correlation_is_an_independent_stop_rule(tmp_path):
    """The rho gate must stop a candidate even when raw dot overlap is <70%."""
    rng = np.random.default_rng(812)
    candidate = rng.uniform(0.0, 0.4, size=SHAPE).astype(np.float32)
    positive_idx = rng.choice(candidate.size, size=1000, replace=False)
    candidate.flat[positive_idx] = rng.uniform(0.6, 0.8, size=positive_idx.size)
    prior = candidate ** 2  # perfectly rank-monotone; a different >0.5 support
    path = tmp_path / "rho-only-prior.tif"
    with rasterio.open(path, "w", driver="GTiff", height=SHAPE[0], width=SHAPE[1],
                       count=1, dtype="float32", crs="EPSG:32611",
                       transform=Affine(100, 0, 0, 0, -100, 40000)) as dst:
        dst.write(prior, 1)
    report = compare_array_to_registry(
        candidate,
        {"complete_accessible_scan": True, "rasters": [
            {"sources": ["fixture:rho-only"], "cache_file": str(path)}]},
        np.ones(SHAPE, bool))
    row = report["rows"][0]
    assert row["spearman_full_footprint"] > RHO_LIMIT
    assert row["my_dots_within_3px_of_theirs"] < OVERLAP_LIMIT
    assert row["duplicate_by_rho"] is True
    assert row["duplicate_by_overlap"] is False
    assert report["duplicate_count"] == 1
    assert report["unique"] is False


def test_partial_registry_never_receives_unique_clearance(tmp_path):
    candidate = _sparse(11, 50).astype(np.float32)
    path = tmp_path / "empty-prior.tif"
    with rasterio.open(path, "w", driver="GTiff", height=SHAPE[0], width=SHAPE[1],
                       count=1, dtype="float32", crs="EPSG:32611",
                       transform=Affine(100, 0, 0, 0, -100, 40000)) as dst:
        dst.write(np.zeros(SHAPE, dtype=np.float32), 1)
    report = compare_array_to_registry(
        candidate,
        {"rasters": [{"sources": ["fixture:empty"], "cache_file": str(path)}]},
        np.ones(SHAPE, bool), scope_complete=False,
        scope={"reason": "fixture inventory is explicitly incomplete"})
    assert report["duplicate_count"] == 0
    assert report["unique_within_available_scope"] is True
    assert report["registry_scope_complete"] is False
    assert report["unique"] is False
    assert report["status"] == "NOT CLEARED — registry scope incomplete"
