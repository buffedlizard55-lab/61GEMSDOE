"""Pre-placement surface gate and final-dot drift gate against every earlier
raster in the family registry.

Two fail-closed legs are used by :func:`check`:

1. **Surface leg (before placement).** Spearman rank correlation over a fixed
   lattice subsample of the valid footprint, with full-footprint confirmation
   for near-threshold rows. ``> 0.90`` against any accessible registry raster
   stops placement.
2. **Dot leg (final dots).** The fraction of candidate dots within Euclidean
   3 px of any positive cell in each registry raster. ``> 0.70`` against any
   comparator stops writing. No base-rate, density, enrichment, or Jaccard
   exemption modifies this rule.

The refreshed inventory combines accessible sibling-repository rasters with
local historical prediction TIFFs scanned by :mod:`scripts.refresh_registry`.
Private, inaccessible, and unlisted submissions remain outside its scope.
"""

from __future__ import annotations

import json as _json
import pathlib

import rasterio
from scipy.stats import rankdata
from scipy import ndimage

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


def dot_overlap_stats(candidate_dots: np.ndarray, registry_positive: np.ndarray,
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
    """Compare against every accessible registry raster using the strict stop rule.

    A candidate is a duplicate if ANY comparator has Spearman rho > 0.90 or
    more than 70% of candidate dots within 3 px. Dot overlap is evaluated for
    every comparator with positives; no density/base-rate exception relaxes the
    user's declared threshold. The surface correlation uses the recorded fixed
    lattice subsample for runtime; near-threshold rows must be confirmed on a
    full-footprint calculation before promotion.
    """
    import rasterio

    root = Path(root) if root else REPO_ROOT
    fp = np.asarray(footprint, bool)
    if fp.ndim != 2:
        raise ValueError("footprint must be 2-D")
    surface = None if candidate_surface is None else np.asarray(candidate_surface, np.float64)
    dots = None if candidate_dots is None else np.asarray(candidate_dots, bool)
    if surface is not None and surface.shape != fp.shape:
        raise ValueError("candidate surface and footprint shape mismatch")
    if dots is not None and dots.shape != fp.shape:
        raise ValueError("candidate dots and footprint shape mismatch")
    if dots is not None and np.any(dots & ~fp):
        raise ValueError("candidate dots outside the valid footprint")
    rasters = load_registry(root)
    complete_scan = limit is None
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be positive when supplied")
        rasters = rasters[:int(limit)]
    if surface_stride is None:
        surface_stride = spearman_stride(int(fp.sum())) if surface is not None else 1
    if surface_stride < 1:
        raise ValueError("surface_stride must be >=1")
    lattice = stride_grid(fp.shape, int(surface_stride)) if surface is not None else None
    worst_rho, worst_rho_id = -np.inf, None
    worst_ov, worst_ov_id = -np.inf, None
    n_surface = n_dots = 0
    duplicates: list[dict] = []
    rows = []
    for i, rec in enumerate(rasters):
        path = root / rec["cache_file"]
        if not path.is_file():
            raise FileNotFoundError(f"registry raster missing: {path}")
        if sha256(path) != rec.get("sha256"):
            raise ValueError(f"registry raster hash mismatch: {path}")
        with rasterio.open(path) as src:
            arr = src.read(1)
            if arr.shape != fp.shape:
                raise ValueError(f"registry raster shape mismatch: {path}: {arr.shape} != {fp.shape}")
        finite = np.isfinite(arr)
        row = dict(sources=rec.get("sources", [])[:3], sha256=rec["sha256"],
                   cache_file=rec["cache_file"])
        rho = None
        overlap = None
        if surface is not None:
            m = fp & finite & lattice
            rho_sample = spearman(surface, np.where(finite, arr, 0.0), m)
            rho = rho_sample
            rho_full = None
            # Confirm only ambiguous rows at full footprint resolution. A
            # sampled value already over the stop threshold is conservatively
            # treated as duplicate; a far-below value needs no expensive rerank.
            if np.isfinite(rho_sample):
                n_surface += 1
                if 0.895 <= rho_sample <= SPEARMAN_LIMIT:
                    rho_full = spearman(surface, np.where(finite, arr, 0.0), fp & finite)
                    rho = rho_full
            row["spearman_lattice_sample"] = float(rho_sample)
            row["spearman_full_confirmation"] = (float(rho_full) if rho_full is not None else None)
            row["spearman_sample_stride_px"] = int(surface_stride)
            if np.isfinite(rho) and rho > worst_rho:
                worst_rho, worst_rho_id = float(rho), rec.get("sources", [None])[0]
        if dots is not None:
            n_dots += 1
            pos = fp & finite & (arr > 0)
            ov = dot_overlap_stats(dots, pos, radius_px=OVERLAP_RADIUS_PX)
            overlap = float(ov["fraction"])
            row["dot_overlap_3px"] = overlap
            row["candidate_dots"] = int(dots.sum())
            row["registry_positive_pixels"] = int(pos.sum())
            if overlap > worst_ov:
                worst_ov, worst_ov_id = overlap, rec.get("sources", [None])[0]
        reason = []
        if rho is not None and np.isfinite(rho) and rho > SPEARMAN_LIMIT:
            reason.append("spearman_gt_0.90")
        if overlap is not None and overlap > OVERLAP_LIMIT:
            reason.append("dot_overlap_gt_0.70")
        row["duplicate"] = bool(reason)
        row["duplicate_reasons"] = reason
        if reason:
            duplicates.append(dict(source=rec.get("sources", [None])[0],
                                   sha256=rec["sha256"], reasons=reason,
                                   spearman=rho, dot_overlap_3px=overlap))
        rows.append(row)
        if progress and (i + 1) % 50 == 0:
            progress(i + 1, len(rasters))

    surface_pass = (bool(n_surface == len(rasters) and worst_rho <= SPEARMAN_LIMIT)
                    if surface is not None and rows else None)
    dot_pass = (bool(n_dots == len(rasters) and worst_ov <= OVERLAP_LIMIT)
                if dots is not None and rows else None)
    stage = ("final" if surface is not None and dots is not None else
             "preplacement" if surface is not None else "dots-only")
    unique = (bool(surface_pass and dot_pass and complete_scan)
              if surface_pass is not None and dot_pass is not None else None)
    if not complete_scan:
        surface_pass = False if surface is not None else surface_pass
        dot_pass = False if dots is not None else dot_pass
        unique = False
    return dict(
        evidence_class="UNIQUENESS-CHECK",
        registry_complete=bool(complete_scan), stage=stage,
        n_registry_rasters=len(rasters),
        comparison_scope="all accessible aligned registry rasters",
        worst_spearman=worst_rho if surface is not None else None,
        worst_spearman_source=worst_rho_id,
        worst_dot_overlap_3px=worst_ov if dots is not None else None,
        worst_dot_overlap_source=worst_ov_id,
        thresholds=dict(spearman_strictly_greater_than=SPEARMAN_LIMIT,
                        dot_overlap_strictly_greater_than=OVERLAP_LIMIT,
                        dot_radius_px=OVERLAP_RADIUS_PX),
        surface_method=(dict(method="fixed lattice subsample of full footprint",
                             stride_px=int(surface_stride),
                             sample_count=int((fp & lattice).sum()),
                             near_threshold_full_scan_required=True)
                        if surface is not None else None),
        duplicate_flags=duplicates,
        surface_gate_pass=surface_pass,
        dot_gate_pass=dot_pass,
        preplacement_pass=(surface_pass is True),
        final_uniqueness_pass=unique,
        unique=unique,
        stop=bool(duplicates or not complete_scan or surface_pass is False or dot_pass is False),
        per_raster=rows)


# ---------------------------------------------------------------------------
# merged from the parallel lane on origin/main (names kept only where this
# module did not already define them)
# ---------------------------------------------------------------------------

def _pearson(a, b):
    a = a - a.mean(); b = b - b.mean()
    den = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / den) if den > 0 else float("nan")


def compare(mine: np.ndarray, other: np.ndarray, footprint: np.ndarray,
            px: int = 3, eligible: np.ndarray | None = None) -> dict:
    """Return diagnostic overlap, rank correlation, and geometric base rate.

    This legacy reporting helper does not clear a candidate and its enrichment
    statistic is never a uniqueness exemption. Promotion decisions must use
    :func:`check` or :func:`compare_array_to_registry`, which apply the literal
    ``rho > 0.90 OR raw dot overlap > 0.70`` stop rule regardless of base rate.
    The base-rate fields are retained only for archived diagnostic reports.
    """
    m = mine[footprint].astype(np.float64)
    o = other[footprint].astype(np.float64)
    finite = np.isfinite(m) & np.isfinite(o)
    m, o = m[finite], o[finite]
    rm, ro = rankdata(m, method="average"), rankdata(o, method="average")
    d_other = ndimage.distance_transform_edt(~(other > 0.5) & footprint, sampling=100.0)
    n_mine = int((mine > 0.5).sum())
    within = int(((mine > 0.5) & (d_other <= 100.0 * px)).sum())
    ref = eligible if eligible is not None else footprint
    near = (d_other <= 100.0 * px)
    base = float(near[ref].mean())
    frac = within / n_mine if n_mine else float("nan")
    return dict(pearson=_pearson(m, o), spearman=_pearson(rm, ro),
                n_mine=n_mine, n_other=int((other > 0.5).sum()),
                dots_within_3px=within,
                frac_dots_within_3px=frac,
                eligible_base_rate_within_3px=base,
                enrichment_vs_base_rate=(frac / base) if base > 0 else float("nan"),
                jaccard=float(((mine > 0.5) & (other > 0.5)).sum() /
                              max(((mine > 0.5) | (other > 0.5)).sum(), 1)))


RHO_LIMIT = 0.90


JACCARD_LIMIT = 0.50


OVERLAP_PX = 3


def surface_rho(mine: np.ndarray, other: np.ndarray, footprint: np.ndarray,
                px: int = OVERLAP_PX) -> dict:
    """Signed agreement of two rasters, reported on both informative supports."""
    m = np.asarray(mine, np.float64)
    o = np.asarray(other, np.float64)
    mine_b, other_b = m > 0.5, o > 0.5
    valid = np.asarray(footprint, bool)
    inter = int((mine_b & other_b).sum())
    union = int((mine_b | other_b).sum())
    jacc = inter / union if union else float("nan")
    # full footprint: both arrays are almost all zeros, so this is the degenerate one
    rho_full = float("nan")
    if valid.any():
        a, b = m[valid], o[valid]
        if a.std() > 0 and b.std() > 0:
            rho_full = _pearson(rankdata(a, method="average"), rankdata(b, method="average"))
    # dot union only: the informative support
    idx = mine_b | other_b
    rho_union = float("nan")
    if idx.any():
        a, b = m[idx], o[idx]
        if a.std() > 0 and b.std() > 0:
            rho_union = _pearson(rankdata(a, method="average"), rankdata(b, method="average"))
    return dict(spearman_full_footprint=rho_full,
                spearman_on_dot_union=rho_union,
                jaccard_dot_sets=jacc,
                n_mine=int(mine_b.sum()), n_other=int(other_b.sum()),
                n_intersection=inter, n_union=union)


def compare_array_to_registry(candidate: np.ndarray, manifest: dict,
                              footprint: np.ndarray, px: int = OVERLAP_PX, *,
                              expected_grid=None, progress=None,
                              phase: str = "both") -> dict:
    """Apply the literal rho / forward 3 px overlap stop rules to a manifest.

    ``phase`` may be ``surface`` (Spearman only), ``dots`` (dot overlap only),
    or ``both``. Missing rasters, bad hashes, incomplete manifests, and grid
    mismatches fail closed. Jaccard is diagnostic only; it is not a stop rule.
    """
    arr = np.asarray(candidate)
    fp = np.asarray(footprint, bool)
    if arr.ndim != 2 or fp.shape != arr.shape:
        raise ValueError("candidate and footprint must be matching 2-D arrays")
    if phase not in {"surface", "dots", "both"}:
        raise ValueError("phase must be 'surface', 'dots', or 'both'")
    if px != OVERLAP_PX:
        raise ValueError("the uniqueness overlap radius is fixed at 3 px")
    if not manifest.get("complete_accessible_scan", False):
        raise ValueError("registry manifest is incomplete; uniqueness cannot be cleared")
    items = manifest.get("rasters")
    if not isinstance(items, list) or not items:
        raise ValueError("registry manifest has no rasters")
    rows, duplicates = [], []
    if np.any((arr > 0) & ~fp):
        raise ValueError("candidate positive mass outside the footprint")
    candidate_dots = (arr > 0) & fp
    candidate_surface = arr.astype(np.float64, copy=False)
    root = REPO_ROOT
    for i, item in enumerate(items):
        raw_path = item.get("cache_file")
        if not raw_path:
            raise ValueError(f"registry record {i} has no cache_file")
        path = pathlib.Path(raw_path)
        if not path.is_absolute():
            path = root / path
        if not path.is_file():
            raise FileNotFoundError(f"registry raster missing: {path}")
        actual_sha = sha256(path)
        if item.get("sha256") and actual_sha != item["sha256"]:
            raise ValueError(f"registry raster hash mismatch: {path}")
        with rasterio.open(path) as src:
            other = src.read(1)
            shape = src.shape
            crs = src.crs
            transform = src.transform
        if shape != arr.shape:
            raise ValueError(f"registry raster grid shape mismatch: {path}: {shape} != {arr.shape}")
        if expected_grid is not None:
            exp_shape, exp_crs, exp_transform = expected_grid
            if shape != tuple(exp_shape) or crs != exp_crs or transform != exp_transform:
                raise ValueError(f"registry raster grid metadata mismatch: {path}")
        finite = np.isfinite(other)
        row = dict(file=path.name, source=item.get("sources", []), sha256=actual_sha)
        rho = None
        overlap = None
        st = None
        if phase in {"surface", "both"}:
            st = surface_rho(candidate_surface, other, fp & finite, px=px)
            rho = float(st["spearman_full_footprint"])
            row.update(spearman_full_footprint=rho,
                       spearman_on_dot_union=st["spearman_on_dot_union"],
                       jaccard_dot_sets=st["jaccard_dot_sets"])
        if phase in {"dots", "both"}:
            other_dots = fp & finite & (other > 0.0)
            overlap = dot_overlap(candidate_dots, other_dots, px=px)
            row["my_dots_within_3px_of_theirs"] = float(overlap)
            if st is None:
                inter = int((candidate_dots & other_dots & fp).sum())
                union = int(((candidate_dots | other_dots) & fp).sum())
                row["jaccard_dot_sets"] = inter / union if union else float("nan")
        dup_rho = bool(rho is not None and np.isfinite(rho) and rho > RHO_LIMIT)
        dup_ov = bool(overlap is not None and overlap > OVERLAP_LIMIT)
        dup = dup_rho or dup_ov
        row.update(duplicate_by_rho=dup_rho, duplicate_by_overlap=dup_ov,
                   duplicate_by_jaccard=(row.get("jaccard_dot_sets", 0.0) > JACCARD_LIMIT),
                   duplicate=dup)
        if dup:
            duplicates.append(dict(file=path.name, source=item.get("sources", []),
                                   sha256=actual_sha, rho=rho,
                                   dot_overlap_3px=overlap,
                                   duplicate_by_rho=dup_rho,
                                   duplicate_by_overlap=dup_ov))
        rows.append(row)
        if progress:
            progress(i + 1, len(items), row)
    return dict(evidence_class="UNIQUENESS-CHECK", phase=phase,
                registry_complete=True, n_registry_rasters=len(items), rows=rows,
                duplicate_count=len(duplicates), duplicates=duplicates,
                unique=(len(duplicates) == 0), jaccard_diagnostic_only=True,
                limits=dict(spearman_strictly_greater_than=RHO_LIMIT,
                            dot_overlap_strictly_greater_than=OVERLAP_LIMIT,
                            dot_radius_px=OVERLAP_RADIUS_PX))



# --- from the parallel lane on origin/main (name kept, this module had none) ---

def dot_overlap(mine: np.ndarray, other: np.ndarray, px: int = OVERLAP_PX) -> float:
    """Fraction of MY dots that fall within ``px`` of any dot of ``other``."""
    mine_b = np.asarray(mine) > 0
    n = int(mine_b.sum())
    if n == 0:
        return 0.0
    other_b = np.asarray(other) > 0
    if not other_b.any():
        return 0.0
    d = ndimage.distance_transform_edt(~other_b)
    return float((d[mine_b] <= px).mean())
