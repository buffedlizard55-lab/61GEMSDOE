"""Integration tests for the public lane uniqueness wrapper."""
import hashlib

import numpy as np
import rasterio
from affine import Affine

from gems61.gates import lane_uniqueness_report


def _write(path, array):
    with rasterio.open(path, "w", driver="GTiff", height=array.shape[0], width=array.shape[1],
                       count=1, dtype="float32", crs="EPSG:32611",
                       transform=Affine(100, 0, 0, 0, -100, array.shape[0] * 100)) as dst:
        dst.write(array.astype(np.float32), 1)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_lane_wrapper_accepts_expected_grid_and_progress_and_fails_closed(tmp_path):
    shape = (40, 50)
    sample = tmp_path / "sample.tif"
    prior = tmp_path / "prior.tif"
    candidate = np.zeros(shape, np.float32)
    candidate[5:10, 5:10] = 1.0
    other = np.zeros(shape, np.float32)
    other[25:30, 25:30] = 1.0
    sample_sha = _write(sample, np.zeros(shape, np.float32))
    prior_sha = _write(prior, other)
    footprint = np.ones(shape, bool)
    manifest = {
        "declared_scope_complete": True,
        "organizer_registry_complete": False,
        "errors": [],
        "scope": "test fixture",
        "rasters": [{"file": prior.name, "cache_file": str(prior),
                      "sha256": prior_sha, "sources": ["fixture"]}],
    }
    seen = []
    report = lane_uniqueness_report(
        candidate, footprint, sample=sample, phase="surface", registry_index=manifest,
        log=lambda message: seen.append(message),
    )
    assert report["phase"] == "surface"
    assert report["ok"] is True
    assert report["duplicate"] is False
    assert report["inventory"]["verified"] is True
    assert seen and "surface registry gate 1/1" in seen[0]

    manifest["declared_scope_complete"] = False
    failed = lane_uniqueness_report(
        candidate, footprint, sample=sample, phase="dots", registry_index=manifest,
    )
    assert failed["ok"] is False
    assert failed["stop"] is True
    assert failed["verdict"] == "UNCHECKED_INCOMPLETE_INVENTORY"

    manifest["declared_scope_complete"] = True
    manifest["errors"] = []
    manifest["rasters"] = [{"file": prior.name, "cache_file": str(prior),
                            "sources": ["fixture"]}]
    unhashed = lane_uniqueness_report(
        candidate, footprint, sample=sample, phase="surface", registry_index=manifest,
    )
    assert unhashed["ok"] is False
    assert unhashed["inventory"]["verified"] is False
    assert "SHA-256 pin" in unhashed["inventory"]["errors"][0]["error"]

    manifest["rasters"] = [None]
    malformed = lane_uniqueness_report(
        candidate, footprint, sample=sample, phase="surface", registry_index=manifest,
    )
    assert malformed["ok"] is False
    assert malformed["inventory"]["verified"] is False
    assert malformed["inventory"]["errors"][0]["error"] == "inventory row is not an object"

    manifest["errors"] = None
    manifest["rasters"] = [{"file": prior.name, "cache_file": str(prior),
                            "sha256": prior_sha, "sources": ["fixture"]}]
    malformed_errors = lane_uniqueness_report(
        candidate, footprint, sample=sample, phase="surface", registry_index=manifest,
    )
    assert malformed_errors["ok"] is False
    assert malformed_errors["inventory"]["verified"] is False
    assert malformed_errors["inventory"]["errors"][0]["error"] == "inventory errors field is not a list"
