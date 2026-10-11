"""The registry refresh must include local prior submissions as well as siblings."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import refresh_registry as registry  # noqa: E402


def test_local_prediction_scan_includes_archives_and_excludes_inputs_and_registry_cache(tmp_path):
    included = [
        tmp_path / "docs" / "downloads" / "older.tif",
        tmp_path / "docs" / "submissions" / "earlier.tiff",
        tmp_path / "out" / "prediction.tif",
        tmp_path / "evidence" / "historical.tif",
        tmp_path / "reports" / "archived.tif",
    ]
    excluded = [
        tmp_path / "docs" / "downloads" / "sample_submission.tif",
        tmp_path / "docs" / "submissions" / "existing_faults.tif",
        tmp_path / "registry" / "cache" / "sibling-cache.tif",
        tmp_path / "data" / "external" / "source.tif",
    ]
    for path in included + excluded:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test-only path fixture")

    found = registry.local_prediction_rasters(tmp_path)
    assert found == sorted(included, key=lambda p: p.relative_to(tmp_path).as_posix())
