"""Fail-closed format-check behavior when the current run wrote no raster."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_checker_does_not_validate_or_substitute_historical_tif(tmp_path):
    historical = next((ROOT / "docs" / "downloads").glob("*.tif"), None)
    assert historical is not None, "test requires the repository's historical TIFF archive"
    report_path = tmp_path / "format-report.json"
    run = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_submission.py"),
         str(historical), "--report", str(report_path)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert run.returncode == 2, run.stdout + run.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "NOT_RUN_NO_CANDIDATE"
    assert report["candidate_tif_created"] is False
    assert report["candidate_path"] is None
    assert report["checks"] is None
    assert report["all_passed"] is None
    assert report["download_permission"] == "NO_CANDIDATE_ARTIFACT"
