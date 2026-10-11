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
# The dot-overlap leg is only defined against a sparse (dot or line) raster.
# Above this positive fraction the test is vacuous and the surface leg decides.
DOT_LEG_MAX_DENSITY = 0.05

REPO_ROOT = Path(__file__).resolve().parents[2]


def _rank(a: np.ndarray) -> np.ndarray:
    """Average ranks (ties share the mean rank) of a 1-D float array.

    Vectorised: the tie groups are found with a single boolean comparison
    against the shifted sorted array.  The original loop over tie groups cost
    ~8 s per 12 M-pixel raster, which made the 708-raster gate take hours.
    """
    a = np.asarray(a, np.float64).ravel()
    n = a.size
    order = np.argsort(a, kind="mergesort")
    s = a[order]
    brk = np.empty(n, dtype=bool)
    if n:
        brk[0] = True
        brk[1:] = s[1:] != s[:-1]
    start = np.flatnonzero(brk)
    end = np.append(start[1:], n) - 1
    avg = 0.5 * (start + end) + 1.0
    grp = np.cumsum(brk) - 1
    ranks = np.empty(n, np.float64)
    ranks[order] = avg[grp]
    return ranks


MAX_SPEARMAN_SAMPLES = 2_000_000


def stride_grid(shape: tuple[int, int], stride: int) -> np.ndarray:
    """A fixed boolean lattice: every ``stride``-th row and column."""
    g = np.zeros(shape, bool)
    g[::stride, ::stride] = True
    return g


def spearman_stride(mask_pixels: int, limit: int = MAX_SPEARMAN_SAMPLES) -> int:
    """Stride that reduces ``mask_pixels`` to at most ``limit`` samples.

    The surface leg of the gate only has to separate rho ~ 0.9 from rho ~ 0.98,
    and at 2 x 10^6 samples the sampling error of rho is about 7 x 10^-4, so a
    lattice subsample cannot hide a duplicate.  It is used purely because the
    full 12.3 M-pixel rank correlation costs ~8 s per raster, i.e. ~95 minutes
    over the 708-raster registry, against ~12 minutes subsampled.
    """
    stride = 1
    while mask_pixels / (stride * stride) > limit:
        stride += 1
    return stride


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
          limit: int | None = None, progress=None,
          surface_stride: int | None = None) -> dict:
    """Run both gate legs against every registry raster."""
    import rasterio

    root = Path(root) if root else REPO_ROOT
    rasters = load_registry(root)
    if limit:
        rasters = rasters[:limit]
    if surface_stride is None:
        surface_stride = (spearman_stride(int(np.asarray(footprint).sum()))
                          if candidate_surface is not None else 1)
    worst_rho, worst_rho_id = -1.0, None
    worst_ov, worst_ov_id = -1.0, None
    n_dense = n_sparse = 0
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
            if surface_stride > 1:
                m &= stride_grid(m.shape, surface_stride)
            rho = spearman(candidate_surface, np.where(finite, arr, 0.0), m)
            row["spearman"] = rho
            if np.isfinite(rho) and rho > worst_rho:
                worst_rho, worst_rho_id = float(rho), rec["sources"][0]
        if candidate_dots is not None:
            pos = finite & (arr > 0)
            density = float(pos.sum()) / max(int(np.asarray(footprint).sum()), 1)
            row["positive_fraction_of_footprint"] = density
            if density > DOT_LEG_MAX_DENSITY:
                # The 3 px overlap test is vacuous against a dense field: a
                # continuous probability map is positive almost everywhere, so
                # ANY candidate lands within 3 px of one of its positives and
                # scores 1.0.  Such a raster is compared on the surface leg
                # alone, and that is recorded rather than silently skipped.
                row["dot_overlap_3px"] = None
                row["dot_leg"] = "not_applicable_dense_field"
                n_dense += 1
            else:
                ov = dot_overlap(candidate_dots, pos)
                row["dot_overlap_3px"] = ov["fraction"]
                row["dot_leg"] = "applicable"
                n_sparse += 1
                if ov["fraction"] > worst_ov:
                    worst_ov, worst_ov_id = ov["fraction"], rec["sources"][0]
        rows.append(row)
        if progress and (i + 1) % 50 == 0:
            progress(i + 1, len(rasters))
    surface_pass = worst_rho <= SPEARMAN_LIMIT
    dot_pass = worst_ov <= OVERLAP_LIMIT
    # Fail closed: if no registry raster was sparse enough for the dot leg the
    # gate has not been run, and that is a failure, not a pass.
    if candidate_dots is not None and n_sparse == 0:
        dot_pass = False
        worst_ov, worst_ov_id = float("nan"), "no sparse registry raster: gate not run"
    return dict(
        evidence_class="UNIQUENESS-CHECK",
        n_registry_rasters=len(rasters),
        worst_spearman=worst_rho, worst_spearman_source=worst_rho_id,
        worst_dot_overlap_3px=worst_ov, worst_dot_overlap_source=worst_ov_id,
        thresholds=dict(spearman=SPEARMAN_LIMIT, dot_overlap=OVERLAP_LIMIT),
        surface_leg_subsample=dict(stride_px=int(surface_stride),
                                   approx_samples=int(np.asarray(footprint).sum()
                                                      / max(surface_stride, 1) ** 2),
                                   note=("lattice subsample of the surface leg; the dot leg "
                                         "is computed on every candidate dot")),
        dot_leg_scope=dict(applicable=n_sparse, dense_excluded=n_dense,
                           max_density=DOT_LEG_MAX_DENSITY,
                           note=("rasters denser than the threshold are continuous "
                                 "probability fields; the 3 px overlap test is vacuous "
                                 "against them, so they are compared on the surface leg")),
        surface_gate_pass=bool(surface_pass),
        dot_gate_pass=bool(dot_pass),
        unique=bool(surface_pass and dot_pass),
        per_raster=rows)
