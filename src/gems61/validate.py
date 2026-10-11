"""Submission-format validation, re-derived from the bytes on disk.

The organiser accepts a single-band GeoTIFF (or a zip containing one) whose CRS,
shape and geotransform match the template, with predicted values in ``[0, 1]``.
A local portal rejection ("Predicted values must be in range [0, 1]") is the
reason every check here is run against the *written file*, not the in-memory
array: the file is the deliverable.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from affine import Affine

from . import grid as gd

CHECKS = (
    "single_band", "dtype_float32", "dimensions_3730x3292", "crs_epsg_32611",
    "transform_matches_template", "nodata_unset_or_nan",
    "in_footprint_all_finite", "in_footprint_no_nan", "in_footprint_no_inf",
    "in_footprint_no_sentinel", "in_footprint_range_0_1",
    "outside_footprint_zero", "zero_on_catalogue", "nonempty",
)


def validate(path: str | Path, footprint: np.ndarray, catalogue: np.ndarray) -> dict:
    import hashlib

    p = Path(path)
    with rasterio.open(p) as src:
        arr = src.read(1)
        meta = dict(bands=src.count, dtype=src.dtypes[0], height=src.height, width=src.width,
                    crs=str(src.crs) if src.crs is not None else None,
                    transform=[float(v) for v in tuple(src.transform)[:6]],
                    res=[float(v) for v in src.res], nodata=src.nodata)
    results = {}
    results["single_band"] = meta["bands"] == 1
    results["dtype_float32"] = meta["dtype"] == "float32"
    results["dimensions_3730x3292"] = (meta["height"], meta["width"]) == gd.SHAPE
    results["crs_epsg_32611"] = meta["crs"] == gd.CRS_EPSG
    results["transform_matches_template"] = \
        meta["transform"] == [float(v) for v in tuple(gd.TRANSFORM)[:6]]
    results["nodata_unset_or_nan"] = meta["nodata"] is None or np.isnan(meta["nodata"])

    inside = arr[footprint]
    results["in_footprint_all_finite"] = bool(np.isfinite(inside).all())
    results["in_footprint_no_nan"] = bool(not np.isnan(inside).any())
    results["in_footprint_no_inf"] = bool(not np.isinf(inside).any())
    results["in_footprint_no_sentinel"] = bool(not (np.abs(inside) > 1e30).any())
    results["in_footprint_range_0_1"] = bool(inside.size > 0
                                             and inside.min() >= 0.0 and inside.max() <= 1.0)
    outside = arr[~np.asarray(footprint, bool)]
    results["outside_footprint_zero"] = bool(outside.size == 0 or (outside == 0).all())
    results["zero_on_catalogue"] = bool(not arr[np.asarray(catalogue, bool) & footprint].any())
    results["nonempty"] = bool((inside > 0).any())

    info = dict(
        path=str(p), bytes=p.stat().st_size,
        sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
        positive_pixels=int((arr > 0).sum()),
        positive_in_footprint=int((arr[footprint] > 0).sum()),
        on_catalogue_positive=int((arr[np.asarray(catalogue, bool) & footprint] > 0).sum()),
        unique_positive_values=sorted(float(v) for v in np.unique(arr[arr > 0])[:8]),
        in_footprint_min=float(inside.min()) if inside.size else None,
        in_footprint_max=float(inside.max()) if inside.size else None,
        **meta)
    return dict(checks=results, all_checks_passed=bool(all(results[k] for k in CHECKS)),
                validator_version="gems61-validate-v1", info=info)


def assert_valid(path: str | Path, footprint: np.ndarray, catalogue: np.ndarray) -> dict:
    out = validate(path, footprint, catalogue)
    failed = [k for k, v in out["checks"].items() if not v]
    if failed:
        raise ValueError(f"submission failed local validation: {failed}")
    return out
