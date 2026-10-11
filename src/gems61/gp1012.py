"""Reader for the official NCEI ASCII GP-1012 Basin and Range depth grid.

The source is Saltus & Jachens' official ``br_depth.xyz`` product.  It is a
2 km, low-pass model grid, not the competition's 100 m label and not a
prediction feature.  This module intentionally exposes only its values and
summary statistics; the published text does not state a geodetic datum for its
Lambert coordinates, so it does not claim pixel-exact reprojection to the
competition grid.

Official references:
* https://www.ngdc.noaa.gov/mgg/gravity/1999/data/grids/basinrng/br_depth.xyz
* https://www.ngdc.noaa.gov/mgg/gravity/1999/data/grids/basinrng/readme.txt
"""
from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
from pathlib import Path

import numpy as np

OFFICIAL_XYZ_URL = (
    "https://www.ngdc.noaa.gov/mgg/gravity/1999/data/grids/basinrng/br_depth.xyz"
)
OFFICIAL_README_URL = (
    "https://www.ngdc.noaa.gov/mgg/gravity/1999/data/grids/basinrng/readme.txt"
)
EXPECTED_ROWS = 596
EXPECTED_COLUMNS = 504
MISSING_FLAG = 9999.0


def _normalise_key(line: str) -> str:
    # The HTML text extractor escapes underscores in the official ASCII header;
    # accept either the literal file spelling or its escaped representation.
    return line.strip().replace("\\_", "_")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


@dataclass(frozen=True)
class GP1012Grid:
    """Parsed GP-1012 depth grid in km; row zero is y-index 1 (the south edge)."""

    depth_km: np.ndarray
    metadata: dict[str, str]
    source_path: str
    source_sha256: str

    @property
    def valid(self) -> np.ndarray:
        return np.isfinite(self.depth_km)

    def summary(self) -> dict:
        """Measured grid-wide depth statistics, in metres, with source identity."""
        m = self.valid
        if not m.any():
            raise ValueError("GP-1012 grid has no valid depth cells")
        values_m = np.asarray(self.depth_km[m], np.float64) * 1000.0
        return dict(
            evidence_class="OFFICIAL-SOURCE-GRID-MEASUREMENT",
            source="USGS GP-1012 Basin and Range modeled basin-depth grid, distributed by NOAA/NCEI",
            source_url=OFFICIAL_XYZ_URL,
            source_readme_url=OFFICIAL_README_URL,
            source_path=self.source_path,
            source_sha256=self.source_sha256,
            rows=int(self.depth_km.shape[0]),
            columns=int(self.depth_km.shape[1]),
            valid_cells=int(values_m.size),
            missing_cells=int((~m).sum()),
            units="m",
            p50_m=float(np.median(values_m)),
            p90_m=float(np.percentile(values_m, 90)),
            p99_m=float(np.percentile(values_m, 99)),
            mean_m=float(values_m.mean()),
            fraction_gt_1km=float((values_m > 1000.0).mean()),
            fraction_gt_2km=float((values_m > 2000.0).mean()),
            min_m=float(values_m.min()),
            max_m=float(values_m.max()),
            calibration_scope="grid-wide summary only; not a pixel-aligned comparison",
            projection_metadata=dict(self.metadata),
            datum_warning=("The official readme/XYZ header specify Lambert Conformal Conic "
                           "parameters but no geodetic datum. No geospatial reprojection "
                           "or per-pixel correlation is asserted."),
        )


def read_gp1012_xyz(path: str | Path, *, require_complete: bool = True) -> GP1012Grid:
    """Read ``xindex,yindex,depth`` records and validate the official grid layout.

    The official header declares a 596 by 504 grid, 2 km spacing, values in km,
    lower-left origin, left-right-up ordering, and a 9999 missing flag.  Missing
    values become NaN.  Incomplete grids are rejected by default so they cannot
    silently calibrate the depth scale from a partial download.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(p)
    metadata: dict[str, str] = {}
    records: list[tuple[int, int, float]] = []
    saw_header = False
    with p.open("r", encoding="ascii", errors="strict", newline="") as f:
        for raw in f:
            line = _normalise_key(raw)
            if not line:
                continue
            low = line.lower()
            if low.startswith("xindex,"):
                saw_header = True
                continue
            if "=" in line and not line.lstrip().startswith(("+", "-", ".")):
                key, value = line.split("=", 1)
                metadata[key.strip().lower()] = value.strip()
                continue
            try:
                fields = next(csv.reader([line], skipinitialspace=True))
                if len(fields) != 3:
                    continue
                x_f, y_f, d_f = (float(s.strip()) for s in fields)
            except (ValueError, csv.Error):
                continue
            if not (x_f.is_integer() and y_f.is_integer()):
                raise ValueError(f"non-integer GP-1012 cell index in {line!r}")
            records.append((int(x_f), int(y_f), d_f))

    if not saw_header:
        raise ValueError("GP-1012 XYZ header 'xindex,yindex,depth' is missing")
    required = {
        "number_of_rows": str(EXPECTED_ROWS),
        "number_of_columns": str(EXPECTED_COLUMNS),
        "grid_unit": "kilometer",
        "grid_size(x)": "2",
        "grid_size(y)": "2",
        "grid_origin": "lowerleft",
        "grid_sequence": "left_right_up",
        "data_value_unit": "kilometers",
    }
    for key, expected in required.items():
        got = metadata.get(key, "").strip().lower()
        if got != expected.lower():
            raise ValueError(f"unexpected GP-1012 metadata {key}={got!r}; expected {expected!r}")
    rows = int(metadata["number_of_rows"])
    cols = int(metadata["number_of_columns"])
    missing = float(metadata.get("missing_flag", MISSING_FLAG))
    values = np.full((rows, cols), np.nan, np.float32)
    seen = np.zeros((rows, cols), bool)
    for xidx, yidx, depth in records:
        if not (1 <= xidx <= cols and 1 <= yidx <= rows):
            raise ValueError(f"GP-1012 index outside declared grid: ({xidx}, {yidx})")
        r, c = yidx - 1, xidx - 1
        if seen[r, c]:
            raise ValueError(f"duplicate GP-1012 cell ({xidx}, {yidx})")
        seen[r, c] = True
        if np.isfinite(depth) and not np.isclose(depth, missing, rtol=0.0, atol=1e-6):
            values[r, c] = np.float32(depth)
    expected_records = rows * cols
    if require_complete and (len(records) != expected_records or not seen.all()):
        raise ValueError(
            f"incomplete GP-1012 grid: {len(records)} records / {int(seen.sum())} unique cells, "
            f"expected {expected_records}; partial data are not a calibration reference")
    if len(records) == 0:
        raise ValueError("no GP-1012 data records found")
    return GP1012Grid(depth_km=values, metadata=metadata,
                      source_path=str(p), source_sha256=_sha256(p))
