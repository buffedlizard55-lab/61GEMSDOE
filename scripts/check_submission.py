#!/usr/bin/env python3
"""Independently validate the current run card's submission GeoTIFF.

The checker never substitutes an older TIF when the current run card has no
candidate. For a real candidate it re-reads bytes from disk and checks the
organizer's template, values, footprint, catalogue mask, and recorded SHA-256.
Exit 0 means every artifact check passed; exit 1 means validation failed; exit
2 means no current candidate exists, so validation was not run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

import numpy as np
import rasterio

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61.io import TEMPLATE_TIF as TEMPLATE  # noqa: E402
from gems61.io import RAW  # noqa: E402

LABELS = RAW / "existing_faults.tif"
if not LABELS.exists():
    LABELS = RAW / "labels.tif"


def _load_card(card_path: str | None) -> dict:
    """Load the current H61U card by default; explicit older cards are selectable."""
    candidates = ([card_path] if card_path else
                  ["evidence/h61u_run_card.json", "evidence/h61m_run_card.json",
                   "evidence/h61g_run_card.json", "evidence/e3_submission.json"])
    for c in candidates:
        cp = ROOT / c
        if cp.exists():
            return json.loads(cp.read_text())
    raise FileNotFoundError("no run card found")


def _write_report(report: dict, report_path: str | None) -> None:
    text = json.dumps(report, indent=2, allow_nan=False)
    print(text)
    if report_path:
        p = pathlib.Path(report_path)
        if not p.is_absolute():
            p = ROOT / p
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text + "\n", encoding="utf-8")


def main(path: str | None = None, card_path: str | None = None,
         report_path: str | None = None) -> int:
    try:
        card = _load_card(card_path)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        _write_report({
            "evidence_class": "FORMAT-VALIDATION",
            "status": "NOT_RUN_NO_CURRENT_RUN_CARD",
            "reason": str(exc),
            "all_passed": None,
        }, report_path)
        return 2

    raster = card.get("raster") or {}
    candidate_path = raster.get("path")
    submission_name = card.get("submission_name")
    candidate_written = card.get("candidate_tif_created")
    if candidate_written is False or (not candidate_path and not submission_name):
        _write_report({
            "evidence_class": "FORMAT-VALIDATION",
            "status": "NOT_RUN_NO_CANDIDATE",
            "reason": "The current run stopped before writing a candidate TIFF; historical rasters are not substituted.",
            "candidate_tif_created": False,
            "candidate_path": None,
            "raster_sha256": None,
            "checks": None,
            "all_passed": None,
            "download_permission": "NO_CANDIDATE_ARTIFACT",
            "submit_recommendation": card.get("submission", {}).get(
                "submit_recommendation", "NOT_RECOMMENDED"),
            "weekly_slot_approved": False,
        }, report_path)
        return 2

    tif_name = pathlib.Path(candidate_path).name if candidate_path else (
        submission_name if str(submission_name).endswith(".tif") else str(submission_name) + ".tif")
    tif = pathlib.Path(path) if path else ROOT / "docs" / "downloads" / tif_name
    expected_sha = raster.get("sha256") or card.get("raster_sha256")
    if not expected_sha:
        _write_report({
            "evidence_class": "FORMAT-VALIDATION",
            "status": "NOT_RUN_MISSING_CARD_SHA256",
            "reason": "A candidate path is recorded but the run card has no expected raster SHA-256.",
            "path": str(tif),
            "checks": None,
            "all_passed": None,
        }, report_path)
        return 2

    with rasterio.open(TEMPLATE) as t:
        tmpl = t.read(1)
        exp = dict(width=t.width, height=t.height, crs=str(t.crs), count=t.count,
                   transform=tuple(t.transform)[:6])
    footprint = np.isfinite(tmpl)
    with rasterio.open(tif) as s:
        a = s.read(1)
        got = dict(width=s.width, height=s.height, crs=str(s.crs), count=s.count,
                   dtype=str(a.dtype), transform=tuple(s.transform)[:6],
                   nodata=None if s.nodata is None else float(s.nodata))
    with rasterio.open(LABELS) as l:
        cat = l.read(1) == 1
    file_sha = hashlib.sha256(tif.read_bytes()).hexdigest()
    checks = {
        "single_band": got["count"] == 1,
        "dtype_float32": got["dtype"] == "float32",
        "width_matches_template": got["width"] == exp["width"],
        "height_matches_template": got["height"] == exp["height"],
        "crs_matches_template": got["crs"] == exp["crs"],
        "crs_is_epsg_32611": got["crs"].endswith("32611"),
        "transform_matches_template": got["transform"] == exp["transform"],
        "no_nan_anywhere": bool(np.isfinite(a).all()),
        "no_inf_anywhere": bool(np.isfinite(a).all()),
        "no_float32_sentinel": bool((a > -1e30).all()),
        "in_footprint_min_ge_0": bool(a[footprint].min() >= 0.0),
        "in_footprint_max_le_1": bool(a[footprint].max() <= 1.0),
        "outside_footprint_all_zero": bool((a[~footprint] == 0).all()),
        "values_are_binary": set(np.unique(a).tolist()) <= {0.0, 1.0},
        "zero_dots_on_catalogue": bool((a[cat] == 0).all()),
        "sha256_matches_card": file_sha == expected_sha,
    }
    rep = dict(evidence_class="FORMAT-VALIDATION", status="CHECKED",
               path=str(tif), grid=got, checks=checks,
               n_positive=int((a[footprint] > 0.5).sum()),
               footprint_pixels=int(footprint.sum()),
               min=float(a[footprint].min()), max=float(a[footprint].max()),
               sha256=file_sha, all_passed=bool(all(checks.values())))
    _write_report(rep, report_path)
    return 0 if rep["all_passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", help="explicit TIFF path; still checked against the current run card")
    parser.add_argument("card", nargs="?", help="explicit run-card JSON path")
    parser.add_argument("--report", help="also write the JSON report to this path")
    args = parser.parse_args()
    raise SystemExit(main(args.path, args.card, args.report))
