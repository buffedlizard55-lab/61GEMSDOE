"""Regression tests for the literal, fail-closed uniqueness protocol."""
import hashlib

import numpy as np
import pytest
import rasterio
from affine import Affine

from gems61.uniqueness import (JACCARD_LIMIT, OVERLAP_LIMIT, RHO_LIMIT,
                               compare_array_to_registry, dot_overlap, surface_rho)

SHAPE = (400, 400)
TRANSFORM = Affine(100, 0, 0, 0, -100, 40000)


def _sparse(seed, n):
    rng = np.random.default_rng(seed)
    a = np.zeros(SHAPE, dtype=np.float32)
    idx = rng.choice(a.size, size=n, replace=False)
    a.ravel()[idx] = 1.0
    return a


def _write(path, values, transform=TRANSFORM):
    with rasterio.open(path, "w", driver="GTiff", height=SHAPE[0], width=SHAPE[1],
                       count=1, dtype="float32", crs="EPSG:32611",
                       transform=transform) as dst:
        dst.write(np.asarray(values, dtype=np.float32), 1)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(path, sha=None, *, complete=True):
    return {
        "declared_scope_complete": complete,
        "organizer_registry_complete": False,
        "errors": [],
        "scope": "test fixture; not organizer registry",
        "rasters": [{"file": path.name, "sources": ["fixture:prior"],
                      "cache_file": str(path),
                      "sha256": sha or hashlib.sha256(path.read_bytes()).hexdigest()}],
    }


def test_negative_full_footprint_spearman_is_not_a_duplicate():
    a = np.zeros(SHAPE, dtype=np.float32)
    b = np.zeros(SHAPE, dtype=np.float32)
    a[:, : SHAPE[1] // 2] = 1
    b[:, SHAPE[1] // 2 :] = 1
    r = surface_rho(a, b, np.ones(SHAPE, bool))
    assert r["spearman_full_footprint"] == pytest.approx(-1.0)
    assert not (r["spearman_full_footprint"] > RHO_LIMIT)
    assert dot_overlap(a, b) < OVERLAP_LIMIT


def test_identical_support_is_seen_by_full_footprint_rho():
    a = _sparse(3, 3000)
    r = surface_rho(a, a.copy(), np.ones(SHAPE, bool))
    assert r["spearman_full_footprint"] == pytest.approx(1.0, abs=1e-9)
    assert r["spearman_full_footprint"] > RHO_LIMIT
    assert np.isnan(r["spearman_on_positive_union"])
    assert r["jaccard_dot_sets"] == pytest.approx(1.0)


def test_empty_prior_does_not_create_false_edge_overlap(tmp_path):
    candidate = np.zeros(SHAPE, dtype=np.float32)
    candidate[0, 0] = 1.0
    empty_prior = np.zeros(SHAPE, dtype=np.float32)
    path = tmp_path / "empty-prior.tif"
    digest = _write(path, empty_prior)
    report = compare_array_to_registry(candidate, _manifest(path, digest),
                                       np.ones(SHAPE, bool))
    row = report["rows"][0]
    assert row["n_other"] == 0
    assert row["my_dots_within_3px_of_theirs"] == 0.0
    assert row["base_rate_within_3px"] == 0.0
    assert report["unique"] is True


def test_any_fractional_positive_support_counts_not_just_values_above_half():
    a = np.zeros(SHAPE, dtype=np.float32)
    b = np.zeros(SHAPE, dtype=np.float32)
    points = [(20 + 20 * y, 20 + 20 * x) for y in range(10) for x in range(10)]
    for y, x in points:
        a[y, x] = 0.1
        b[y, x] = 0.1
    assert dot_overlap(a, b) == pytest.approx(1.0)


def test_dense_reference_literal_one_sided_overlap_is_a_stop(tmp_path):
    """A small candidate inside a much denser prior still trips the 70% rule.

    Jaccard and the reference's density cannot override the user's literal
    one-sided overlap threshold.
    """
    candidate = np.zeros(SHAPE, dtype=np.float32)
    prior = np.zeros(SHAPE, dtype=np.float32)
    points = [(10 + 20 * y, 10 + 20 * x) for y in range(10) for x in range(10)]
    for y, x in points:
        candidate[y, x] = 1.0
        prior[y, x] = 1.0
    extra = [(250 + (i // 20), 10 + 5 * (i % 20)) for i in range(1000)]
    for y, x in extra:
        prior[y, x] = 1.0
    path = tmp_path / "dense-prior.tif"
    digest = _write(path, prior)
    report = compare_array_to_registry(candidate, _manifest(path, digest),
                                       np.ones(SHAPE, bool))
    row = report["rows"][0]
    assert row["my_dots_within_3px_of_theirs"] == pytest.approx(1.0)
    assert row["jaccard_dot_sets"] < JACCARD_LIMIT
    assert row["duplicate_by_overlap"] is True
    assert report["duplicate_count"] == 1
    assert report["unique"] is False
    assert report["verdict"] == "DUPLICATE_LANE_DRIFT"


def test_overlap_rule_is_strictly_more_than_seventy_percent(tmp_path):
    candidate = np.zeros(SHAPE, dtype=np.float32)
    prior = np.zeros(SHAPE, dtype=np.float32)
    points = [(10 + 20 * y, 10 + 20 * x) for y in range(10) for x in range(10)]
    for y, x in points:
        candidate[y, x] = 1.0
    for y, x in points[:70]:
        prior[y, x] = 1.0
    for y, x in [(250 + 20 * (i // 5), 20 + 20 * (i % 5)) for i in range(25)]:
        prior[y, x] = 1.0
    path = tmp_path / "prior.tif"
    digest = _write(path, prior)
    report = compare_array_to_registry(candidate, _manifest(path, digest),
                                       np.ones(SHAPE, bool))
    row = report["rows"][0]
    assert row["my_dots_within_3px_of_theirs"] == pytest.approx(0.70)
    assert row["duplicate_by_overlap"] is False
    assert report["unique"] is True


def test_jaccard_is_diagnostic_only_below_literal_overlap_limit(tmp_path):
    candidate = np.zeros(SHAPE, dtype=np.float32)
    prior = np.zeros(SHAPE, dtype=np.float32)
    points = [(10 + 20 * y, 10 + 20 * x) for y in range(10) for x in range(10)]
    for y, x in points:
        candidate[y, x] = 1.0
    for y, x in points[:65]:
        prior[y, x] = 1.0
    for y, x in [(250 + 20 * (i // 5), 20 + 20 * (i % 5)) for i in range(25)]:
        prior[y, x] = 1.0
    path = tmp_path / "prior.tif"
    digest = _write(path, prior)
    report = compare_array_to_registry(candidate, _manifest(path, digest),
                                       np.ones(SHAPE, bool))
    row = report["rows"][0]
    assert row["my_dots_within_3px_of_theirs"] == pytest.approx(0.65)
    assert row["jaccard_dot_sets"] > JACCARD_LIMIT
    assert row["duplicate_by_jaccard"] is True  # diagnostic flag only
    assert report["jaccard_diagnostic_only"] is True
    assert report["duplicate_count"] == 0 and report["unique"]


def test_incomplete_inventory_fails_closed_even_if_comparisons_pass(tmp_path):
    candidate = _sparse(10, 100)
    prior = _sparse(11, 100)
    path = tmp_path / "prior.tif"
    digest = _write(path, prior)
    report = compare_array_to_registry(candidate, _manifest(path, digest, complete=False),
                                       np.ones(SHAPE, bool))
    assert report["duplicate_count"] == 0
    assert report["unique"] is False
    assert report["verdict"] == "UNCHECKED_INCOMPLETE_INVENTORY"
    assert report["inventory"]["verified"] is False


def test_missing_inventory_file_fails_closed(tmp_path):
    candidate = _sparse(20, 100)
    report = compare_array_to_registry(candidate, {
        "declared_scope_complete": True, "organizer_registry_complete": False,
        "errors": [], "rasters": [{"file": "gone.tif", "cache_file": str(tmp_path / "gone.tif"),
                                    "sha256": "0" * 64}],
    }, np.ones(SHAPE, bool))
    assert report["unique"] is False
    assert report["verdict"] == "UNCHECKED_INCOMPLETE_INVENTORY"
    assert "missing" in report["rows"][0]["error"]


def test_hash_mismatch_and_wrong_grid_fail_closed(tmp_path):
    candidate = _sparse(30, 100)
    prior = _sparse(31, 100)
    path = tmp_path / "prior.tif"
    _write(path, prior)
    expected_wrong = (SHAPE, rasterio.crs.CRS.from_epsg(32611),
                      Affine(100, 0, 1, 0, -100, 40000))
    report_grid = compare_array_to_registry(candidate, _manifest(path), np.ones(SHAPE, bool),
                                            expected_grid=expected_wrong)
    assert report_grid["unique"] is False
    assert report_grid["inventory"]["error_count"] == 1
    assert "transform" in report_grid["rows"][0]["error"]

    report_hash = compare_array_to_registry(candidate, _manifest(path, "f" * 64),
                                            np.ones(SHAPE, bool))
    assert report_hash["unique"] is False
    assert "SHA-256" in report_hash["rows"][0]["error"]


def test_progress_callback_and_expected_grid_are_supported(tmp_path):
    candidate = _sparse(40, 100)
    prior = _sparse(41, 100)
    path = tmp_path / "prior.tif"
    digest = _write(path, prior)
    calls = []
    expected = (SHAPE, rasterio.crs.CRS.from_epsg(32611), TRANSFORM)
    report = compare_array_to_registry(candidate, _manifest(path, digest),
                                       np.ones(SHAPE, bool), expected_grid=expected,
                                       progress=lambda i, n, row: calls.append((i, n, row["file"])))
    assert calls == [(1, 1, "prior.tif")]
    assert report["unique"] is True


def test_empty_or_out_of_footprint_candidate_cannot_be_cleared(tmp_path):
    candidate = np.zeros(SHAPE, dtype=np.float32)
    path = tmp_path / "prior.tif"
    digest = _write(path, _sparse(50, 100))
    report = compare_array_to_registry(candidate, _manifest(path, digest),
                                       np.ones(SHAPE, bool))
    assert report["unique"] is False
    assert report["verdict"] == "INVALID_CANDIDATE"
    assert "candidate has no positive support" in report["candidate_errors"]

    candidate[0, 0] = 1.0
    footprint = np.ones(SHAPE, bool)
    footprint[0, 0] = False
    report = compare_array_to_registry(candidate, _manifest(path, digest), footprint)
    assert report["unique"] is False
    assert any("positive support outside the footprint" in error
               for error in report["candidate_errors"])
