"""Submission writer + fail-closed validator for the DrivenData GEMS portal.

Official submission format (competition problem description,
https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/):
  * single-band 32-bit float GeoTIFF, values in [0, 1]
  * same CRS as the training data (UTM zone 11 N, EPSG:32611)
  * same 100 m resolution, same bounds as the training data
  * data outside the bounds null or NaN

Two mechanisms produce the portal error "Predicted values must be in range [0, 1]":
  1. the feature raster's float32 sentinel (-3.4028234663852886e+38) leaking through,
  2. a footprint mask derived from a feature band leaving 3,061 scored pixels as NaN.
Both are engineered out here: the writer re-reads the file from disk and aborts
unless every one of the 12,279,160 cells is finite and inside [0, 1].
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import rasterio

from .io import TEMPLATE_TIF, RES

EXPECTED = dict(width=3292, height=3730, crs="EPSG:32611", count=1, dtype="float32",
                transform=(100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0))


def template_meta():
    """Return (rasterio write-meta, footprint mask) for the organiser template."""
    with rasterio.open(TEMPLATE_TIF) as src:
        return (dict(driver="GTiff", height=src.height, width=src.width,
                     count=1, dtype="float32", crs=src.crs, transform=src.transform),
                np.isfinite(src.read(1)))


def write_submission(pred: np.ndarray, path: pathlib.Path, outside: str = "zeros",
                     footprint: np.ndarray | None = None) -> dict:
    """Write a portal-valid GeoTIFF. ``outside`` is 'zeros' (all-finite) or 'nan'."""
    meta, fp = template_meta()
    if footprint is None:
        footprint = fp
    if pred.shape != (meta["height"], meta["width"]):
        raise ValueError(f"shape {pred.shape} != template")
    if not np.isfinite(pred[footprint]).all():
        raise ValueError("non-finite prediction inside the footprint")
    if pred[footprint].min() < 0 or pred[footprint].max() > 1:
        raise ValueError("prediction outside [0, 1] inside the footprint")
    if outside == "nan":
        out = np.full(pred.shape, np.nan, np.float32)
        out[footprint] = pred[footprint]
        meta = dict(meta, nodata=float("nan"))
    elif outside == "zeros":
        out = np.zeros(pred.shape, np.float32)
        out[footprint] = pred[footprint]
    else:
        raise ValueError("outside must be 'zeros' or 'nan'")
    with rasterio.open(path, "w", compress="deflate", **meta) as dst:
        dst.write(out, 1)
    return validate(path, footprint=fp)


def validate(path: pathlib.Path, footprint: np.ndarray | None = None,
             catalogue: np.ndarray | None = None) -> dict:
    """Fail-closed validation, re-reading the bytes from disk."""
    import hashlib
    path = pathlib.Path(path)
    with rasterio.open(path) as src:
        a = src.read(1)
        got = dict(width=src.width, height=src.height, crs=str(src.crs), count=src.count,
                   dtype=str(a.dtype), transform=tuple(src.transform)[:6],
                   nodata=None if src.nodata is None else float(src.nodata))
        if footprint is None:
            with rasterio.open(TEMPLATE_TIF) as t:
                footprint = np.isfinite(t.read(1))
    fin = np.isfinite(a)
    on_cat = int(((a > 0) & catalogue).sum()) if catalogue is not None else 0
    checks = dict(
        single_band=got["count"] == 1,
        dtype_float32=got["dtype"] == "float32",
        dimensions_3730x3292=(got["height"], got["width"]) == (3730, 3292),
        crs_epsg_32611=got["crs"] == EXPECTED["crs"],
        transform_matches=tuple(got["transform"]) == EXPECTED["transform"],
        transform_matches_sample_submission=tuple(got["transform"]) == EXPECTED["transform"],
        no_nan_anywhere=bool(fin.all()),
        no_inf_anywhere=bool(np.isfinite(a).all()),
        no_sentinel_values=bool((a > -1e30).all()),
        range_0_1_guaranteed=bool(fin.all() and np.min(a) >= 0.0 and np.max(a) <= 1.0),
        min_ge_0=bool(np.nanmin(a) >= 0.0),
        max_le_1=bool(np.nanmax(a) <= 1.0),
        in_footprint_all_finite=bool(fin[footprint].all()),
        in_footprint_range_0_1=bool(np.nanmin(a[footprint]) >= 0.0
                                    and np.nanmax(a[footprint]) <= 1.0),
        outside_footprint_zero=bool(((a > 0) & ~footprint).sum() == 0),
        zero_dots_on_mapped_catalogue=bool(on_cat == 0),
        whole_raster_all_finite=bool(fin.all()),
        whole_raster_range_0_1=bool(np.nanmin(a[fin]) >= 0.0 and np.nanmax(a[fin]) <= 1.0
                                    if fin.any() else False),
        no_float32_sentinel=bool((a > -1e30).all()),
    )
    pos_px = int((a[footprint] > 0).sum())
    rep = dict(path=str(path), file=str(path),
               bytes=path.stat().st_size,
               sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
               grid=got,
               meta=dict(crs=got["crs"], shape=[got["height"], got["width"]],
                         dtype=got["dtype"], count=got["count"], nodata=got["nodata"],
                         transform=list(got["transform"]), profile_compress="deflate"),
               n_finite=int(fin.sum()),
               n_nan=int(np.isnan(a).sum()),
               n_infinite=int(np.isinf(a).sum()),
               min=float(np.nanmin(a)),
               max=float(np.nanmax(a)),
               mean=float(np.nanmean(a)),
               emitted_positive_pixels=pos_px,
               on_catalogue_positive_pixels=on_cat,
               in_footprint_positive_pixels=pos_px,
               in_footprint_pixels=int(footprint.sum()),
               positive_pixels=pos_px,
               footprint_fraction=float(pos_px / footprint.sum()),
               in_footprint_min=float(np.nanmin(a[footprint])),
               in_footprint_max=float(np.nanmax(a[footprint])),
               checks=checks, all_checks_passed=bool(all(checks.values())),
               validation_class="local format/range preflight; not organizer acceptance or uniqueness clearance")
    return rep


def assert_submittable(rep: dict) -> None:
    """Raise AssertionError if any validation check in ``rep`` failed."""
    if not rep.get("all_checks_passed", False):
        bad = [k for k, v in rep.get("checks", {}).items() if not v]
        raise AssertionError(f"failed submission validation checks: {bad}")
