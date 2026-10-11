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


RHO_LIMIT = 0.90
OVERLAP_LIMIT = 0.70
JACCARD_LIMIT = 0.50


def dot_overlap(mine: np.ndarray, other: np.ndarray, px: int = 3) -> float:
    sa = np.asarray(mine) > 0.5
    sb = np.asarray(other) > 0.5
    n_mine = int(sa.sum())
    if n_mine == 0:
        return 0.0
    if not sb.any():
        return 0.0
    d_other = ndimage.distance_transform_edt(~sb)
    return float((sa & (d_other <= px)).sum() / n_mine)


def surface_rho(mine: np.ndarray, other: np.ndarray, valid: np.ndarray) -> dict:
    from scipy.stats import spearmanr
    a = np.asarray(mine, dtype=np.float64)
    b = np.asarray(other, dtype=np.float64)
    v = np.asarray(valid, dtype=bool)
    av, bv = a[v], b[v]
    rho_full = float(spearmanr(av, bv).statistic) if (av.std() > 0 and bv.std() > 0) else float("nan")
    sa = (a > 0) & v
    sb = (b > 0) & v
    union = sa | sb
    au, bu = a[union], b[union]
    rho_union = float(spearmanr(au, bu).statistic) if (union.any() and au.std() > 0 and bu.std() > 0) else float("nan")
    inter = int((sa & sb).sum())
    jaccard = float(inter / max(int(union.sum()), 1))
    return dict(spearman_full_footprint=rho_full,
                spearman_on_dot_union=rho_union,
                jaccard_dot_sets=jaccard)


def compare_array_to_registry(candidate: np.ndarray, manifest: dict, valid: np.ndarray) -> dict:
    rows = []
    dups = 0
    for item in manifest.get("rasters", []):
        with rasterio.open(item["cache_file"]) as src:
            prior = src.read(1)
        sr = surface_rho(candidate, prior, valid)
        ov3 = dot_overlap(candidate, prior, px=3)
        dup_rho = bool(sr["spearman_full_footprint"] > RHO_LIMIT)
        dup_ov = bool(ov3 > OVERLAP_LIMIT)
        dup_jac = bool(sr["jaccard_dot_sets"] > JACCARD_LIMIT)
        if dup_rho or dup_ov:
            dups += 1
        rows.append(dict(
            repo=item.get("repo_first"),
            sources=item.get("sources", []),
            sha256=item.get("sha256"),
            spearman_full_footprint=sr["spearman_full_footprint"],
            spearman_on_dot_union=sr["spearman_on_dot_union"],
            my_dots_within_3px_of_theirs=ov3,
            jaccard_dot_sets=sr["jaccard_dot_sets"],
            duplicate_by_jaccard=dup_jac,
        ))
    return dict(
        rows=rows,
        jaccard_diagnostic_only=True,
        duplicate_count=dups,
        unique=(dups == 0),
    )


def load_registry(paths, footprint_shape=None):
    out = {}
    for p in paths:
        with rasterio.open(p) as src:
            out[pathlib.Path(p).name] = src.read(1)
    return out
