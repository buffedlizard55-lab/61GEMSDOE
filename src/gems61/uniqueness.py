"""Lane-drift / uniqueness check against registry rasters.

Run-brief thresholds: Spearman > 0.90 against any registry raster, or > 70% of my
dots falling within 3 px of one registry raster's dots, means the lane has drifted
into another lane's hypothesis and the candidate must be logged as a duplicate.
"""
from __future__ import annotations

import pathlib

import numpy as np
import rasterio
from scipy import ndimage
from scipy.stats import rankdata


def _pearson(a, b):
    a = a - a.mean(); b = b - b.mean()
    den = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / den) if den > 0 else float("nan")


def compare(mine: np.ndarray, other: np.ndarray, footprint: np.ndarray,
            px: int = 3, eligible: np.ndarray | None = None) -> dict:
    """Overlap + rank correlation, with the base rate made explicit.

    ``frac_dots_within_3px`` is only interpretable next to the base rate: the
    fraction of the *eligible area* that is itself within ``px`` of the other
    raster.  Against a very dense raster the base rate approaches 1 and the raw
    fraction carries no duplication evidence, so the enrichment
    (fraction / base rate) is reported as well.
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


def load_registry(paths, footprint_shape=None):
    out = {}
    for p in paths:
        with rasterio.open(p) as src:
            out[pathlib.Path(p).name] = src.read(1)
    return out


# ---------------------------------------------------------------------------
# Protocol helpers used by tests/test_uniqueness.py and the drivers (IR-61-MERGE-02:
# an earlier merge carried a second, shadowed copy of these functions; removed).
# They are thin wrappers over `compare` so that the protocol thresholds live in
# exactly one place; Jaccard is *diagnostic only* and never a stop rule
# (IR-61-UNIQ-01: dot overlap is degenerate against a dense sibling surface).
# ---------------------------------------------------------------------------
RHO_LIMIT = 0.90
OVERLAP_LIMIT = 0.70
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


def dot_overlap(mine: np.ndarray, other: np.ndarray, px: int = OVERLAP_PX) -> float:
    """Fraction of MY dots that fall within ``px`` of any dot of ``other``."""
    mine_b = np.asarray(mine) > 0.5
    n = int(mine_b.sum())
    if n == 0:
        return 0.0
    other_b = np.asarray(other) > 0.5
    if not other_b.any():
        return 0.0
    d = ndimage.distance_transform_edt(~other_b)
    return float((d[mine_b] <= px).mean())


def compare_array_to_registry(candidate: np.ndarray, manifest: dict,
                              footprint: np.ndarray, px: int = OVERLAP_PX) -> dict:
    """Apply the protocol screen to every raster named in ``manifest``.

    Stop rules: |full-footprint Spearman| > RHO_LIMIT, or forward dot overlap >
    OVERLAP_LIMIT, against any single registry raster.  Jaccard is reported and
    flagged, never a stop rule.
    """
    rows, dupes = [], 0
    for item in manifest.get("rasters", []):
        path = item.get("cache_file")
        if not path or not pathlib.Path(path).exists():
            continue
        with rasterio.open(path) as src:
            other = src.read(1)
        st = surface_rho(candidate, other, footprint, px=px)
        ov = dot_overlap(candidate, other, px=px)
        dup_rho = abs(st["spearman_full_footprint"]) > RHO_LIMIT
        dup_ov = ov > OVERLAP_LIMIT
        if dup_rho or dup_ov:
            dupes += 1
        rows.append(dict(file=pathlib.Path(path).name, source=item.get("sources", []),
                         sha256=item.get("sha256"),
                         spearman_full_footprint=st["spearman_full_footprint"],
                         spearman_on_dot_union=st["spearman_on_dot_union"],
                         my_dots_within_3px_of_theirs=ov,
                         jaccard_dot_sets=st["jaccard_dot_sets"],
                         duplicate_by_rho=dup_rho, duplicate_by_overlap=dup_ov,
                         duplicate_by_jaccard=st["jaccard_dot_sets"] > JACCARD_LIMIT))
    return dict(evidence_class="MEASURED", rows=rows, duplicate_count=dupes,
                unique=dupes == 0, jaccard_diagnostic_only=True,
                limits=dict(rho=RHO_LIMIT, overlap=OVERLAP_LIMIT, jaccard=JACCARD_LIMIT))
