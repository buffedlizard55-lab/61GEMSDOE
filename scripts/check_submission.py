#!/usr/bin/env python3
"""Independent post-hoc verification of the shipped submission GeoTIFF.

Re-reads the bytes from disk and compares them, cell for cell and tag for tag,
against the organiser's own template.  Nothing here is inherited from the writer.
Exit code 0 = every check passed.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import numpy as np
import rasterio

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "data" / "raw" / "example_submission.tif"
LABELS = ROOT / "data" / "raw" / "existing_faults.tif"


def _load_card(card_path: str | None) -> dict:
    """Newest run card by default (H61-G); the e3 card remains selectable."""
    candidates = [card_path] if card_path else ["evidence/h61g_run_card.json", "evidence/e3_submission.json"]
    for c in candidates:
        cp = ROOT / c
        if cp.exists():
            card = json.loads(cp.read_text())
            name = card["submission_name"]
            card["_tif_name"] = name if name.endswith(".tif") else name + ".tif"
            return card
    raise FileNotFoundError("no run card found")


def main(path: str | None = None, card_path: str | None = None) -> int:
    card = _load_card(card_path)
    tif = pathlib.Path(path) if path else ROOT / "docs" / "downloads" / card["_tif_name"]
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
        "sha256_matches_card": hashlib.sha256(tif.read_bytes()).hexdigest() == card["raster_sha256"],
    }
    rep = dict(path=str(tif), grid=got, checks=checks,
               n_positive=int((a[footprint] > 0.5).sum()),
               footprint_pixels=int(footprint.sum()),
               min=float(a[footprint].min()), max=float(a[footprint].max()),
               sha256=hashlib.sha256(tif.read_bytes()).hexdigest(),
               all_passed=bool(all(checks.values())))
    print(json.dumps(rep, indent=2))
    return 0 if rep["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else None, sys.argv[2] if len(sys.argv) > 2 else None))
