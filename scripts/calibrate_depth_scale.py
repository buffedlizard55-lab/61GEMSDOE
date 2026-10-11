#!/usr/bin/env python3
"""Calibrate inversion depth scale using the official GP-1012 grid only.

The required reference is the complete NOAA/NCEI-distributed USGS
``br_depth.xyz`` grid. Organizer band 15, static literature quantiles, and
partial downloads are expressly rejected. The source XYZ header does not state a
geodetic datum, so the shared calibrator matches grid-wide depth summaries; it
does not claim pixelwise registration or local fault validation.

The sandbox cannot fetch the NOAA host. Place a complete file at
``data/external/gp1012/br_depth.xyz`` (or set ``GEMS_GP1012_XYZ``) to run this
optional calibration. If it is absent, a blocked-status receipt is written and
no calibration is performed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import buried as B  # noqa: E402
from gems61 import gp1012  # noqa: E402
from gems61 import grid as gd  # noqa: E402


def _coarsen_mean(values: np.ndarray, known: np.ndarray, factor: int = 4):
    """Cell-average finite gravity onto the declared 400 m calibration grid."""
    a = np.asarray(values, np.float32)
    m = np.asarray(known, bool) & np.isfinite(a)
    h = (a.shape[0] // factor) * factor
    w = (a.shape[1] // factor) * factor
    aa = a[:h, :w].reshape(h // factor, factor, w // factor, factor)
    mm = m[:h, :w].reshape(h // factor, factor, w // factor, factor)
    count = mm.sum(axis=(1, 3))
    total = np.where(mm, aa, 0.0).sum(axis=(1, 3), dtype=np.float64)
    out = np.divide(total, count, out=np.zeros_like(total), where=count > 0).astype(np.float32)
    return out, count > 0


def main() -> int:
    source_path = Path(os.environ.get(
        "GEMS_GP1012_XYZ", ROOT / "data" / "external" / "gp1012" / "br_depth.xyz"))
    output = ROOT / "evidence" / "gp1012_calibration.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if not source_path.is_file():
        receipt = dict(
            evidence_class="CALIBRATION-STATUS",
            status="BLOCKED-MISSING-COMPLETE-OFFICIAL-GP1012-GRID",
            generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            required_source_url=gp1012.OFFICIAL_XYZ_URL,
            required_readme_url=gp1012.OFFICIAL_README_URL,
            expected_local_path=str(source_path),
            calibration_performed=False,
            calibration_output=None,
            organizer_band_15_used=False,
            reason=("The complete official XYZ grid is not present locally and the sandbox "
                    "cannot fetch NOAA/NCEI. No scale fit or GP-1012 statistics are asserted."),
            next_step=("Obtain the complete official br_depth.xyz outside this sandbox, place it "
                       "at the expected path, then rerun this script; incomplete grids are rejected."),
        )
        output.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps(receipt, indent=2))
        return 2

    reference = gp1012.read_gp1012_xyz(source_path, require_complete=True)
    g = gd.load_grid()
    gravity = np.asarray(B.load_band(13), np.float32)
    footprint = np.asarray(g.footprint, bool)
    known = np.isfinite(gravity) & footprint
    coarse, coarse_known = _coarsen_mean(gravity, known, factor=4)
    started = time.time()
    calibration = B.calibrate_density_scale(
        coarse, coarse_known, dx=400.0,
        candidates=(-250.0, -300.0, -350.0, -400.0, -450.0, -500.0, -600.0),
        kc_scales=(1.0,), z0_candidates=(300.0, 400.0, 500.0, 700.0, 1000.0),
        gp1012_reference=reference,
    )
    receipt = dict(
        evidence_class="MODEL-CALIBRATION-TO-OFFICIAL-GP1012-SUMMARIES",
        status=calibration["status"],
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        elapsed_seconds=float(time.time() - started),
        source=calibration["reference"],
        calibration=calibration,
        calibration_inputs=dict(gravity_band=13, grid_spacing_m=400,
                                known_cells=int(coarse_known.sum()),
                                organizer_band_15_used=False),
        limitations=calibration["limitations"],
    )
    output.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "best": calibration["best"],
                      "output": str(output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
