"""Write and validate a competition-conformant submission GeoTIFF.

The competition form rejects anything that is not a single-band GeoTIFF whose CRS,
shape and geotransform match the submission format, and it rejects values outside
[0, 1] with the message:

    "Predicted values must be in range [0, 1]"

The example submission that ships with the competition data expresses "outside the
study area" as NaN.  NaN is legal under the stated input contract (the official
metric treats it as zero credit and zero penalty) but it is what trips the form's
range check in practice, so this project emits **all-finite** rasters: 0.0 outside
the footprint, and evidence in [0, 1] inside it.  The registry rasters in the group's
own repositories carry this in their filenames: `-zeros` and `-allfinite` variants
are the ones that survive the form, `-nan` variants are the ones that do not.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np
import rasterio
from rasterio.crs import CRS

__all__ = ["write_submission", "validate_submission", "sha256_file", "write_checks"]

EXPECTED_CRS = CRS.from_epsg(32611)
EXPECTED_SHAPE = (3730, 3292)
EXPECTED_TRANSFORM = rasterio.Affine(100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def write_submission(path: str, field: np.ndarray, valid: np.ndarray,
                     template: str, threshold: float | None = 0.5) -> dict:
    """Write ``field`` as a single-band float32 GeoTIFF copied from ``template``'s grid.

    ``field`` is the belief field; ``threshold`` binarises it (None keeps probabilities).
    Outside the footprint the output is 0.0 -- never NaN -- so the submission form's
    [0, 1] range check cannot fail.
    """
    if threshold is not None:
        data = ((np.asarray(field, np.float64) >= threshold) & valid).astype(np.float32)
    else:
        data = np.where(valid, np.clip(field, 0.0, 1.0), 0.0).astype(np.float32)
    data = np.nan_to_num(data, nan=0.0, posinf=1.0, neginf=0.0)
    np.clip(data, 0.0, 1.0, out=data)

    with rasterio.open(template) as t:
        profile = t.profile.copy()
    profile.update(driver="GTiff", dtype="float32", count=1, nodata=None,
                   compress="deflate", predictor=2, tiled=False, crs=EXPECTED_CRS)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)
        dst.update_tags(AREA_OR_POINT="Area")
    return dict(path=path, n_positive=int((data > 0).sum()),
                n_features={"unique_values": [float(v) for v in np.unique(data)[:8]]})


def validate_submission(path: str, template: str) -> dict:
    """Check every contract item the submission form enforces.  Returns a report."""
    out = {"path": path, "checks": {}, "pass": True}
    with rasterio.open(path) as s, rasterio.open(template) as t:
        arr = s.read(1)
        finite = np.isfinite(arr)
        c = out["checks"]
        c["single_band"] = (s.count == 1, s.count)
        c["dtype_float"] = (s.dtypes[0] in ("float32", "float64"), s.dtypes[0])
        c["crs_matches_template"] = (s.crs == t.crs, str(s.crs))
        c["crs_is_epsg32611"] = (s.crs == EXPECTED_CRS, str(s.crs))
        c["shape_matches_template"] = ((s.height, s.width) == (t.height, t.width),
                                       [s.height, s.width])
        c["shape_is_expected"] = ((s.height, s.width) == EXPECTED_SHAPE, list(EXPECTED_SHAPE))
        c["transform_matches_template"] = (s.transform == t.transform, list(s.transform)[:6])
        c["no_nan_anywhere"] = (bool(finite.all()), int((~finite).sum()))
        c["min_ge_0"] = (float(arr.min()) >= 0.0, float(arr.min()))
        c["max_le_1"] = (float(arr.max()) <= 1.0, float(arr.max()))
        c["all_values_in_0_1"] = (bool(((arr >= 0) & (arr <= 1)).all()), None)
        out["stats"] = dict(n_positive=int((arr > 0).sum()),
                            n_pixels=int(arr.size),
                            positive_fraction=round(float((arr > 0).mean()), 6),
                            unique_values_leq_8=[float(v) for v in np.unique(arr)[:8]],
                            min=float(arr.min()), max=float(arr.max()),
                            n_unique=int(np.unique(arr).size))
    out["pass"] = all(bool(v[0]) for v in out["checks"].values())
    out["sha256"] = sha256_file(path)
    return out


def write_checks(validation: dict, out_path: str, extra: dict | None = None) -> None:
    payload = dict(validation)
    if extra:
        payload.update(extra)
    with open(out_path, "w") as fh:
        json.dump(payload, fh, indent=1)
