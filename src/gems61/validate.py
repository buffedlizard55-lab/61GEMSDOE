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


def validate(path: pathlib.Path, footprint: np.ndarray | None = None) -> dict:
    """Fail-closed validation, re-reading the bytes from disk."""
    with rasterio.open(path) as src:
        a = src.read(1)
        got = dict(width=src.width, height=src.height, crs=str(src.crs), count=src.count,
                   dtype=str(a.dtype), transform=tuple(src.transform)[:6],
                   nodata=None if src.nodata is None else float(src.nodata))
        if footprint is None:
            with rasterio.open(TEMPLATE_TIF) as t:
                footprint = np.isfinite(t.read(1))
    fin = np.isfinite(a)
    checks = dict(
        single_band=got["count"] == 1,
        dtype_float32=got["dtype"] == "float32",
        dimensions_3730x3292=(got["height"], got["width"]) == (3730, 3292),
        crs_epsg_32611=got["crs"] == EXPECTED["crs"],
        transform_matches=tuple(got["transform"]) == EXPECTED["transform"],
        in_footprint_all_finite=bool(fin[footprint].all()),
        in_footprint_range_0_1=bool(np.nanmin(a[footprint]) >= 0.0
                                    and np.nanmax(a[footprint]) <= 1.0),
        whole_raster_all_finite=bool(fin.all()),
        whole_raster_range_0_1=bool(np.nanmin(a[fin]) >= 0.0 and np.nanmax(a[fin]) <= 1.0
                                    if fin.any() else False),
        no_float32_sentinel=bool((a > -1e30).all()),
    )
    rep = dict(path=str(path), grid=got,
               in_footprint_pixels=int(footprint.sum()),
               positive_pixels=int((a[footprint] > 0.5).sum()),
               footprint_fraction=float((a[footprint] > 0.5).sum() / footprint.sum()),
               in_footprint_min=float(np.nanmin(a[footprint])),
               in_footprint_max=float(np.nanmax(a[footprint])),
               checks=checks, all_checks_passed=bool(all(checks.values())))
    return rep
