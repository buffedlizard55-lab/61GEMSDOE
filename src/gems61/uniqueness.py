"""Pre-placement surface gate and final-dot drift gate against every earlier
raster in the family registry.

Two legs, exactly as the parallel-run protocol specifies:

1. **Surface leg (before placement).**  Full-footprint Spearman rank
   correlation between the candidate's *soft* surface and every registry
   raster.  ``> 0.90`` with any earlier raster means the candidate has drifted
   into another lane.
2. **Dot leg (final dots).**  The fraction of the candidate's emitted dots that
   fall within Euclidean 3 px of *one* registry raster's positive cells.
   ``> 0.70`` is a duplicate.

The candidate's own repository is excluded from the registry by construction
(:mod:`scripts.refresh_registry` skips ``61GEMSDOE``).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt

SPEARMAN_LIMIT = 0.90
OVERLAP_LIMIT = 0.70
OVERLAP_RADIUS_PX = 3.0

REPO_ROOT = Path(__file__).resolve().parents[2]


def _rank(a: np.ndarray) -> np.ndarray:
    """Average ranks (ties share the mean rank) of a 1-D float array."""
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(a.size, np.float64)
    sorted_a = a[order]
    i = 0
    n = a.size
    while i < n:
        j = i
        while j + 1 < n and sorted_a[j + 1] == sorted_a[i]:
            j += 1
        ranks[order[i:j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    return ranks


def spearman(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> float:
    """Spearman rank correlation of two fields over ``mask``."""
    x = np.asarray(a, np.float64)[mask]
    y = np.asarray(b, np.float64)[mask]
    if x.size < 3:
        return float("nan")
    if np.all(x == x[0]) or np.all(y == y[0]):
        return 0.0
    rx = _rank(x)
    ry = _rank(y)
    rx -= rx.mean()
    ry -= ry.mean()
    denom = float(np.sqrt((rx * rx).sum() * (ry * ry).sum()))
    return float((rx * ry).sum() / denom) if denom > 0 else 0.0


def dot_overlap(candidate_dots: np.ndarray, registry_positive: np.ndarray,
                radius_px: float = OVERLAP_RADIUS_PX) -> dict:
    """Fraction of candidate dots within ``radius_px`` of a registry raster."""
    c = np.asarray(candidate_dots, bool)
    r = np.asarray(registry_positive, bool)
    n = int(c.sum())
    if n == 0:
        return dict(n_dots=0, within=0, fraction=0.0)
    if not r.any():
        return dict(n_dots=n, within=0, fraction=0.0, note="registry raster has no positives")
    d = distance_transform_edt(~r)
    within = int((d[c] <= float(radius_px)).sum())
    return dict(n_dots=n, within=within, fraction=within / float(n))


def load_registry(root: Path | None = None) -> list[dict]:
    root = Path(root) if root else REPO_ROOT
    path = root / "evidence" / "registry_refreshed.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing; run scripts/refresh_registry.py")
    data = json.loads(path.read_text())
    if not data.get("complete_accessible_scan", False):
        raise ValueError("registry scan is incomplete; the gate must fail closed")
    return data["rasters"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as s:
        for c in iter(lambda: s.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def check(candidate_surface: np.ndarray | None, candidate_dots: np.ndarray | None,
          footprint: np.ndarray, root: Path | None = None,
          limit: int | None = None, progress=None) -> dict:
    """Run both gate legs against every registry raster."""
    import rasterio

    root = Path(root) if root else REPO_ROOT
    rasters = load_registry(root)
    if limit:
        rasters = rasters[:limit]
    worst_rho, worst_rho_id = -1.0, None
    worst_ov, worst_ov_id = -1.0, None
    rows = []
    for i, rec in enumerate(rasters):
        path = root / rec["cache_file"]
        if not path.exists():
            raise FileNotFoundError(f"registry raster missing: {path}")
        with rasterio.open(path) as src:
            arr = src.read(1)
        finite = np.isfinite(arr)
        row = dict(sources=rec["sources"][:3], sha256=rec["sha256"])
        if candidate_surface is not None:
            m = footprint & finite
            rho = spearman(candidate_surface, np.where(finite, arr, 0.0), m)
            row["spearman"] = rho
            if np.isfinite(rho) and rho > worst_rho:
                worst_rho, worst_rho_id = float(rho), rec["sources"][0]
        if candidate_dots is not None:
            ov = dot_overlap(candidate_dots, finite & (arr > 0))
            row["dot_overlap_3px"] = ov["fraction"]
            if ov["fraction"] > worst_ov:
                worst_ov, worst_ov_id = ov["fraction"], rec["sources"][0]
        rows.append(row)
        if progress and (i + 1) % 50 == 0:
            progress(i + 1, len(rasters))
    surface_pass = worst_rho <= SPEARMAN_LIMIT
    dot_pass = worst_ov <= OVERLAP_LIMIT
    return dict(
        evidence_class="UNIQUENESS-CHECK",
        n_registry_rasters=len(rasters),
        worst_spearman=worst_rho, worst_spearman_source=worst_rho_id,
        worst_dot_overlap_3px=worst_ov, worst_dot_overlap_source=worst_ov_id,
        thresholds=dict(spearman=SPEARMAN_LIMIT, dot_overlap=OVERLAP_LIMIT),
        surface_gate_pass=bool(surface_pass),
        dot_gate_pass=bool(dot_pass),
        unique=bool(surface_pass and dot_pass),
        per_raster=rows)
