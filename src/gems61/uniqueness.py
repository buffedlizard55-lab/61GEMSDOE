"""Lane-drift / uniqueness check against registry rasters.

Run-brief thresholds (parallel-run protocol, rule 1): Spearman > 0.90 against any
registry raster, or > 70% of my dots falling within 3 px of one registry raster's
dots, means the lane has drifted into another lane's hypothesis and the candidate
must be logged as a duplicate.  Jaccard of the two dot sets is reported as a
*diagnostic* only (it is not one of the protocol's stop rules).
"""
from __future__ import annotations

import hashlib
import pathlib

import numpy as np
import rasterio
from scipy import ndimage
from scipy.stats import rankdata

RHO_LIMIT = 0.90          # protocol stop rule: rank correlation on the footprint
OVERLAP_LIMIT = 0.70      # protocol stop rule: my dots within 3 px of theirs
JACCARD_LIMIT = 0.50      # diagnostic only
PX_M = 100.0


def _pearson(a, b):
    a = a - a.mean(); b = b - b.mean()
    den = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / den) if den > 0 else float("nan")


def _spearman(a, b):
    if a.size < 2:
        return float("nan")
    ra, rb = rankdata(a, method="average"), rankdata(b, method="average")
    if ra.std() == 0 or rb.std() == 0:
        return float("nan")
    return _pearson(ra, rb)


def surface_rho(mine: np.ndarray, other: np.ndarray, valid: np.ndarray) -> dict:
    """Rank agreement between two rasters on ``valid``.

    ``spearman_full_footprint`` is the protocol statistic (for two binary dot
    fields it equals the phi coefficient).  ``spearman_on_dot_union`` restricts
    the comparison to cells where either raster is positive; it is NaN when one
    support contains the other (the statistic is then constant) and negative for
    disjoint supports, so it is never thresholded -- it is reported so a
    near-copy can be *seen*.
    """
    v = np.asarray(valid, bool)
    m = np.where(np.isfinite(mine), mine, 0.0).astype(np.float64)
    o = np.where(np.isfinite(other), other, 0.0).astype(np.float64)
    full = _spearman(m[v], o[v])
    sm, so = (m > 0.5) & v, (o > 0.5) & v
    union = sm | so
    on_union = _spearman(m[union], o[union]) if union.any() else float("nan")
    inter = int((sm & so).sum())
    jac = inter / max(int(union.sum()), 1)
    return dict(spearman_full_footprint=full, spearman_on_dot_union=on_union,
                jaccard_dot_sets=float(jac), n_mine=int(sm.sum()), n_other=int(so.sum()),
                n_intersection=inter)


def dot_overlap(mine: np.ndarray, other: np.ndarray, px: int = 3) -> float:
    """Fraction of my positive cells lying within ``px`` cells of one of theirs."""
    sm = np.asarray(mine) > 0.5
    so = np.asarray(other) > 0.5
    n = int(sm.sum())
    if n == 0 or not so.any():
        return 0.0
    near = ndimage.distance_transform_edt(~so) <= px
    return float(near[sm].sum() / n)


def compare(mine: np.ndarray, other: np.ndarray, footprint: np.ndarray,
            px: int = 3, eligible: np.ndarray | None = None) -> dict:
    """Overlap + rank correlation, with the base rate made explicit.

    ``frac_dots_within_3px`` is only interpretable next to the base rate: the
    fraction of the *eligible area* that is itself within ``px`` of the other
    raster.  Against a very dense raster the base rate approaches 1 and the raw
    fraction carries no duplication evidence, so the enrichment
    (fraction / base rate) is reported as well.
    """
    fp = np.asarray(footprint, bool)
    rho = surface_rho(mine, other, fp)
    d_other = ndimage.distance_transform_edt(~((other > 0.5) & fp), sampling=PX_M)
    n_mine = int((mine > 0.5).sum())
    within = int(((mine > 0.5) & (d_other <= PX_M * px)).sum())
    ref = eligible if eligible is not None else fp
    near = (d_other <= PX_M * px)
    base = float(near[ref].mean())
    frac = within / n_mine if n_mine else float("nan")
    return dict(pearson=_pearson(np.where(np.isfinite(mine), mine, 0.0)[fp].astype(np.float64),
                                 np.where(np.isfinite(other), other, 0.0)[fp].astype(np.float64)),
                spearman=rho["spearman_full_footprint"],
                spearman_on_dot_union=rho["spearman_on_dot_union"],
                n_mine=n_mine, n_other=int((other > 0.5).sum()),
                dots_within_3px=within,
                frac_dots_within_3px=frac,
                eligible_base_rate_within_3px=base,
                enrichment_vs_base_rate=(frac / base) if base > 0 else float("nan"),
                jaccard=rho["jaccard_dot_sets"])


def load_registry(paths, footprint_shape=None):
    out = {}
    for p in paths:
        with rasterio.open(p) as src:
            if footprint_shape is not None and (src.height, src.width) != tuple(footprint_shape):
                continue
            out[pathlib.Path(p).name] = src.read(1)
    return out


def compare_array_to_registry(candidate: np.ndarray, manifest: dict, valid: np.ndarray,
                              px: int = 3) -> dict:
    """Apply the protocol's two stop rules to every raster listed in ``manifest``.

    ``manifest["rasters"]`` rows carry ``cache_file`` (a GeoTIFF path) and
    ``sha256``; a hash mismatch is recorded as an error rather than silently
    compared.  Jaccard is diagnostic only and never changes ``unique``.
    """
    rows, errors = [], list(manifest.get("errors", []))
    cand = np.asarray(candidate, np.float32)
    v = np.asarray(valid, bool)
    for entry in manifest.get("rasters", []):
        path = pathlib.Path(entry["cache_file"])
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if entry.get("sha256") and digest != entry["sha256"]:
                raise ValueError(f"sha256 mismatch for {path.name}")
            with rasterio.open(path) as src:
                other = src.read(1)
            if other.shape != cand.shape:
                raise ValueError(f"shape {other.shape} != candidate {cand.shape}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path.name}: {exc}")
            continue
        rho = surface_rho(cand, other, v)
        ov = dot_overlap(cand, other, px)
        dup_rho = bool(rho["spearman_full_footprint"] == rho["spearman_full_footprint"]
                       and rho["spearman_full_footprint"] > RHO_LIMIT)
        dup_ov = bool(ov > OVERLAP_LIMIT)
        rows.append(dict(repo_first=entry.get("repo_first"), sources=entry.get("sources"),
                         file=path.name, sha256=digest,
                         spearman_full_footprint=rho["spearman_full_footprint"],
                         spearman_on_dot_union=rho["spearman_on_dot_union"],
                         my_dots_within_3px_of_theirs=ov,
                         jaccard_dot_sets=rho["jaccard_dot_sets"],
                         duplicate_by_rho=dup_rho, duplicate_by_overlap=dup_ov,
                         duplicate_by_jaccard=bool(rho["jaccard_dot_sets"] > JACCARD_LIMIT),
                         duplicate=dup_rho or dup_ov))
    dup = sum(1 for r in rows if r["duplicate"])
    return dict(rows=rows, errors=errors, duplicate_count=dup, unique=(dup == 0),
                rho_limit=RHO_LIMIT, overlap_limit=OVERLAP_LIMIT, jaccard_limit=JACCARD_LIMIT,
                jaccard_diagnostic_only=True,
                complete_accessible_scan=bool(manifest.get("complete_accessible_scan", False)) and not errors)
