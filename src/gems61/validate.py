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
Both are engineered out here: the validator re-reads the file from disk and reports
whether every one of the 12,279,160 cells is finite and inside [0, 1].

History (irregularity IR-61-MERGE-01): two parallel sessions each shipped a
``validate`` module; the merge kept the one *without* ``assert_submittable`` and
the ``catalogue`` argument, which broke ``submission_writer`` on ``main``.  This
file is the union of both: the old signature ``validate(path, footprint)`` still
works, and ``validate(path, footprint, catalogue)`` adds the on-catalogue check
the writer relies on.
"""
from __future__ import annotations

import hashlib
import pathlib

import numpy as np
import rasterio

from .io import TEMPLATE_TIF, RES  # noqa: F401  (RES re-exported for callers)

EXPECTED = dict(width=3292, height=3730, crs="EPSG:32611", count=1, dtype="float32",
                transform=(100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0))
FLOAT32_SENTINEL_LIMIT = -1e30


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


def _sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def validate(path: pathlib.Path, footprint: np.ndarray | None = None,
             catalogue: np.ndarray | None = None) -> dict:
    """Fail-closed validation, re-reading the bytes from disk.

    ``footprint`` defaults to the finite cells of the organiser template.  When
    ``catalogue`` (the mapped-fault mask) is given, the report also states how
    many positive cells sit on mapped traces -- those earn nothing because the
    scored truth is the set of *unmapped* faults.
    """
    path = pathlib.Path(path)
    with rasterio.open(path) as src:
        a = src.read(1)
        got = dict(width=src.width, height=src.height, crs=str(src.crs), count=src.count,
                   dtype=str(a.dtype), transform=tuple(src.transform)[:6],
                   nodata=None if src.nodata is None or not np.isfinite(src.nodata) else float(src.nodata),
                   compress=src.profile.get("compress"))
        descriptions = list(src.descriptions)
    if footprint is None:
        with rasterio.open(TEMPLATE_TIF) as t:
            footprint = np.isfinite(t.read(1))
    footprint = np.asarray(footprint, bool)
    fin = np.isfinite(a)
    inside = a[footprint]
    outside = a[~footprint]
    n_nan = int(np.isnan(a).sum())
    n_inf = int(np.isinf(a).sum())
    in_min = float(np.nanmin(inside)) if np.isfinite(inside).any() else float("nan")
    in_max = float(np.nanmax(inside)) if np.isfinite(inside).any() else float("nan")
    whole_ok = bool(fin.all() and a.min() >= 0.0 and a.max() <= 1.0)
    checks = dict(
        single_band=got["count"] == 1,
        dtype_float32=got["dtype"] == "float32",
        dimensions_3730x3292=(got["height"], got["width"]) == (3730, 3292),
        crs_epsg_32611=got["crs"] == EXPECTED["crs"],
        transform_matches_sample_submission=tuple(got["transform"]) == EXPECTED["transform"],
        no_nan_anywhere=n_nan == 0,
        no_inf_anywhere=n_inf == 0,
        no_sentinel_values=bool((np.where(fin, a, 0.0) > FLOAT32_SENTINEL_LIMIT).all()),
        range_0_1_guaranteed=whole_ok,
        min_ge_0=bool(np.nanmin(a) >= 0.0) if fin.any() else False,
        max_le_1=bool(np.nanmax(a) <= 1.0) if fin.any() else False,
        in_footprint_all_finite=bool(np.isfinite(inside).all()),
        in_footprint_range_0_1=bool(np.isfinite(in_min) and in_min >= 0.0 and in_max <= 1.0),
        outside_footprint_zero=bool((np.where(np.isfinite(outside), outside, 0.0) == 0.0).all()),
        # kept for callers written against the other session's names
        transform_matches=tuple(got["transform"]) == EXPECTED["transform"],
        whole_raster_all_finite=bool(fin.all()),
        whole_raster_range_0_1=whole_ok,
        no_float32_sentinel=bool((np.where(fin, a, 0.0) > FLOAT32_SENTINEL_LIMIT).all()),
    )
    on_cat = None
    if catalogue is not None:
        cat = np.asarray(catalogue, bool)
        on_cat = int(((a > 0) & cat & fin).sum())
        checks["zero_dots_on_mapped_catalogue"] = on_cat == 0
    positive = int(((a > 0) & footprint & fin).sum())
    return dict(
        file=str(path), bytes=path.stat().st_size, sha256=_sha256(path),
        meta=dict(crs=got["crs"], shape=[got["height"], got["width"]], dtype=got["dtype"],
                  count=got["count"], nodata=got["nodata"], transform=list(got["transform"]),
                  profile_compress=got["compress"]),
        grid=got, band_description=descriptions,
        n_finite=int(fin.sum()), n_nan=n_nan, n_infinite=n_inf,
        min=float(np.nanmin(a)) if fin.any() else None,
        max=float(np.nanmax(a)) if fin.any() else None,
        mean=float(np.nanmean(a)) if fin.any() else None,
        emitted_positive_pixels=positive,
        in_footprint_pixels=int(footprint.sum()),
        in_footprint_positive_pixels=positive,
        positive_pixels=positive,
        footprint_fraction=float(positive / max(int(footprint.sum()), 1)),
        in_footprint_min=in_min, in_footprint_max=in_max,
        on_catalogue_positive_pixels=on_cat,
        checks=checks, all_checks_passed=bool(all(checks.values())),
        validation_class="local format/range preflight; not organizer acceptance or uniqueness clearance")


def assert_submittable(report: dict) -> None:
    """Raise ``AssertionError`` naming every failed check (fail closed)."""
    failed = [k for k, v in report.get("checks", {}).items() if not v]
    if failed or not report.get("all_checks_passed", False):
        raise AssertionError(f"submission validator failed: {failed or ['all_checks_passed is False']}")
