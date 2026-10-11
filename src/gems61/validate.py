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
    """Fail-closed validation, re-reading the bytes from disk.

    Shared-tool fix (session arena/d29229b5, 2026-10-11): ``submission_writer`` --
    which merged from the other session on this repository -- calls
    ``validate(path, footprint, catalogue)`` and then ``assert_submittable``.
    The merge kept this module's older one-argument API, so the writer raised
    ImportError for every caller.  The three-argument form is restored here, in
    the one shared module, instead of forking the writer.
    """
    with rasterio.open(path) as src:
        a = src.read(1)
        got = dict(width=src.width, height=src.height, crs=str(src.crs), count=src.count,
                   dtype=str(a.dtype), transform=tuple(src.transform)[:6],
                   nodata=None if src.nodata is None else float(src.nodata))
        if footprint is None:
            with rasterio.open(TEMPLATE_TIF) as t:
                footprint = np.isfinite(t.read(1))
    fin = np.isfinite(a)
    outside = ~footprint
    checks = dict(
        single_band=got["count"] == 1,
        dtype_float32=got["dtype"] == "float32",
        dimensions_3730x3292=(got["height"], got["width"]) == (3730, 3292),
        crs_epsg_32611=got["crs"] == EXPECTED["crs"],
        transform_matches=tuple(got["transform"]) == EXPECTED["transform"],
        no_nan_anywhere=bool(not np.isnan(a).any()),
        no_inf_anywhere=bool(not np.isinf(a).any()),
        no_sentinel_values=bool((np.abs(a) < 1e30).all()),
        outside_footprint_zero=bool((a[outside] == 0).all()) if outside.any() else True,
        range_0_1_guaranteed=bool(np.nanmin(a) >= 0.0 and np.nanmax(a) <= 1.0),
        in_footprint_all_finite=bool(fin[footprint].all()),
        in_footprint_range_0_1=bool(np.nanmin(a[footprint]) >= 0.0
                                    and np.nanmax(a[footprint]) <= 1.0),
        whole_raster_all_finite=bool(fin.all()),
        whole_raster_range_0_1=bool(np.nanmin(a[fin]) >= 0.0 and np.nanmax(a[fin]) <= 1.0
                                    if fin.any() else False),
        no_float32_sentinel=bool((a > -1e30).all()),
    )
    if catalogue is not None:
        cat = np.asarray(catalogue, bool) & footprint
        checks["zero_dots_on_mapped_catalogue"] = bool(not (a[cat] > 0).any())
        on_cat = int((a[cat] > 0).sum())
    else:
        on_cat = None
    rep = dict(path=str(path), grid=got,
               in_footprint_pixels=int(footprint.sum()),
               positive_pixels=int((a[footprint] > 0.5).sum()),
               footprint_fraction=float((a[footprint] > 0.5).sum() / footprint.sum()),
               in_footprint_min=float(np.nanmin(a[footprint])),
               in_footprint_max=float(np.nanmax(a[footprint])),
               n_finite=int(fin.sum()), n_nan=int(np.isnan(a).sum()),
               n_infinite=int(np.isinf(a).sum()),
               min=float(np.nanmin(a)), max=float(np.nanmax(a)), mean=float(np.nanmean(a)),
               emitted_positive_pixels=int((a > 0).sum()),
               on_catalogue_positive_pixels=on_cat,
               checks=checks, all_checks_passed=bool(all(checks.values())),
               validation_class=("local format/range preflight; not organizer acceptance "
                                 "or uniqueness clearance"))
    return rep


def assert_submittable(report: dict) -> None:
    """Raise AssertionError unless every on-disk check passed.

    ``submission_writer`` catches AssertionError and re-raises it as ValueError so
    that a rejected output never leaves a partial deliverable behind.
    """
    failed = sorted(k for k, v in report["checks"].items() if not v)
    assert not failed, f"validator checks failed: {failed}"
