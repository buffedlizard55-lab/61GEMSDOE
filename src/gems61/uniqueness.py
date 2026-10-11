"""Literal pre-submission duplicate gate for raster candidates.

A candidate is a duplicate when rank correlation is > 0.90 OR more than 70%
of its positive dots lie within 3 pixels of one registry raster. Jaccard and
base-rate enrichment are useful diagnostics, but never replace that rule.
"""
from __future__ import annotations

import pathlib

import numpy as np
import rasterio
from scipy import ndimage
from scipy.stats import rankdata

RHO_LIMIT = 0.90
OVERLAP_LIMIT = 0.70
OVERLAP_PX = 3
JACCARD_LIMIT = 0.50  # diagnostic only; not a duplicate threshold


def _pearson(a, b):
    a = a - a.mean(); b = b - b.mean()
    den = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / den) if den > 0 else float("nan")


def compare(mine: np.ndarray, other: np.ndarray, footprint: np.ndarray,
            px: int = OVERLAP_PX, eligible: np.ndarray | None = None) -> dict:
    """Diagnostic overlap statistics, including the spatial base rate.

    ``frac_dots_within_3px`` is the fraction of the candidate's dots within
    ``px`` of any reference dot. ``eligible_base_rate_within_3px`` is the
    fraction of eligible area that is within that distance. The base rate
    explains the geometry but does not waive the literal overlap gate.
    """
    mine = np.asarray(mine)
    other = np.asarray(other)
    footprint = np.asarray(footprint, bool)
    if mine.shape != other.shape or mine.shape != footprint.shape:
        raise ValueError("candidate, reference and footprint grids must match")
    mine_b = np.isfinite(mine) & (mine > 0.5) & footprint
    other_b = np.isfinite(other) & (other > 0.5) & footprint
    d_other = ndimage.distance_transform_edt(~other_b)
    n_mine = int(mine_b.sum())
    within = int((mine_b & (d_other <= px)).sum())
    ref = footprint if eligible is None else (np.asarray(eligible, bool) & footprint)
    if ref.shape != footprint.shape:
        raise ValueError("eligible mask grid must match footprint")
    base = float((d_other[ref] <= px).mean()) if ref.any() else float("nan")
    frac = within / n_mine if n_mine else float("nan")
    inter = int((mine_b & other_b).sum())
    union = int((mine_b | other_b).sum())
    return dict(dots_within_3px=within,
                frac_dots_within_3px=frac,
                eligible_base_rate_within_3px=base,
                enrichment_vs_base_rate=(frac / base) if base > 0 else float("nan"),
                jaccard=inter / union if union else float("nan"))


def surface_rho(mine: np.ndarray, other: np.ndarray, footprint: np.ndarray,
                px: int = OVERLAP_PX) -> dict:
    """Rank agreement over the footprint and on the informative dot union."""
    m = np.asarray(mine, np.float64)
    o = np.asarray(other, np.float64)
    valid = np.asarray(footprint, bool)
    if m.shape != o.shape or m.shape != valid.shape:
        raise ValueError("candidate, reference and footprint grids must match")
    mine_b, other_b = (m > 0.5) & valid, (o > 0.5) & valid
    inter = int((mine_b & other_b).sum())
    union = int((mine_b | other_b).sum())
    rho_full = float("nan")
    if valid.any():
        a, b = m[valid], o[valid]
        if a.std() > 0 and b.std() > 0:
            rho_full = _pearson(rankdata(a, method="average"), rankdata(b, method="average"))
    idx = mine_b | other_b
    rho_union = float("nan")
    if idx.any():
        a, b = m[idx], o[idx]
        if a.std() > 0 and b.std() > 0:
            rho_union = _pearson(rankdata(a, method="average"), rankdata(b, method="average"))
    return dict(spearman_full_footprint=rho_full,
                spearman_on_dot_union=rho_union,
                jaccard_dot_sets=inter / union if union else float("nan"),
                n_mine=int(mine_b.sum()), n_other=int(other_b.sum()),
                n_intersection=inter, n_union=union)


def dot_overlap(mine: np.ndarray, other: np.ndarray, px: int = OVERLAP_PX) -> float:
    """Forward overlap: fraction of candidate dots within ``px`` of reference."""
    mine_b = np.isfinite(mine) & (np.asarray(mine) > 0.5)
    n = int(mine_b.sum())
    if n == 0:
        return 0.0
    other_b = np.isfinite(other) & (np.asarray(other) > 0.5)
    if not other_b.any():
        return 0.0
    d = ndimage.distance_transform_edt(~other_b)
    return float((d[mine_b] <= px).mean())


def gate_pair(mine: np.ndarray, other: np.ndarray, footprint: np.ndarray,
              px: int = OVERLAP_PX) -> dict:
    """Apply both literal stop rules to one candidate/reference pair."""
    mine = np.asarray(mine, np.float64)
    other = np.asarray(other, np.float64)
    footprint = np.asarray(footprint, bool)
    if mine.shape != other.shape or mine.shape != footprint.shape:
        raise ValueError("candidate, reference and footprint grids must match")
    mine = np.where(footprint & np.isfinite(mine), mine, 0.0)
    other = np.where(footprint & np.isfinite(other), other, 0.0)
    stats = surface_rho(mine, other, footprint, px=px)
    diagnostics = compare(mine, other, footprint, px=px)
    overlap = dot_overlap(mine, other, px=px)
    by_rho = bool(np.isfinite(stats["spearman_full_footprint"]) and
                  stats["spearman_full_footprint"] > RHO_LIMIT)
    by_overlap = bool(overlap > OVERLAP_LIMIT)
    return dict(**stats,
                eligible_base_rate_within_3px=diagnostics["eligible_base_rate_within_3px"],
                enrichment_vs_base_rate=diagnostics["enrichment_vs_base_rate"],
                my_dots_within_3px_of_theirs=overlap,
                duplicate_by_rho=by_rho,
                duplicate_by_overlap=by_overlap,
                duplicate_by_jaccard=bool(stats["jaccard_dot_sets"] > JACCARD_LIMIT),
                duplicate=(by_rho or by_overlap),
                overlap_gate_rule="one-sided 3 px overlap",
                overlap_gate_value=overlap,
                overlap_gate_limit=OVERLAP_LIMIT,
                overlap_gate_exceeded=by_overlap,
                jaccard_diagnostic_only=True)


def load_registry(paths, footprint_shape=None):
    out = {}
    for p in paths:
        with rasterio.open(p) as src:
            if footprint_shape is not None and src.shape != tuple(footprint_shape):
                raise ValueError(f"registry grid mismatch: {p}")
            out[pathlib.Path(p).name] = src.read(1)
    return out


def compare_array_to_registry(candidate: np.ndarray, manifest: dict,
                              footprint: np.ndarray, px: int = OVERLAP_PX, *,
                              scope_complete: bool | None = None,
                              scope: dict | None = None) -> dict:
    """Apply the literal duplicate screen to each raster in ``manifest``.

    Missing/unreadable rows remain visible in the report. ``scope_complete``
    is a separate assertion about inventory completeness: a clean comparison
    against a partial list is NOT a uniqueness clearance.
    """
    if scope_complete is None:
        scope_complete = bool(manifest.get("complete_accessible_scan", True))
    footprint = np.asarray(footprint, bool)
    candidate = np.asarray(candidate, np.float64)
    if candidate.shape != footprint.shape:
        raise ValueError("candidate and footprint grids must match")
    if not np.isfinite(candidate).all():
        raise ValueError("candidate surface must be finite before registry comparison")
    rows, errors = [], []
    for item in manifest.get("rasters", []):
        path = item.get("cache_file")
        if not path or not pathlib.Path(path).exists():
            msg = f"registry raster missing: {path or item.get('sources', ['?'])[0]}"
            errors.append(msg)
            rows.append(dict(file=pathlib.Path(path).name if path else "<missing>", error=msg))
            continue
        try:
            with rasterio.open(path) as src:
                if src.shape != candidate.shape:
                    raise ValueError(f"grid mismatch: {src.shape} != {candidate.shape}")
                raw = src.read(1)
            nonfinite = int((~np.isfinite(raw)).sum())
            other = np.where(np.isfinite(raw), raw, 0.0)
            stats = gate_pair(candidate, other, footprint, px=px)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)[:200]
            errors.append(f"{path}: {msg}")
            rows.append(dict(file=pathlib.Path(path).name, error=msg))
            continue
        rows.append(dict(file=pathlib.Path(path).name,
                         source=item.get("sources", []),
                         sha256=item.get("sha256"),
                         reference_nonfinite_pixels=nonfinite,
                         spearman_full_footprint=stats["spearman_full_footprint"],
                         spearman_on_dot_union=stats["spearman_on_dot_union"],
                         my_dots_within_3px_of_theirs=stats["my_dots_within_3px_of_theirs"],
                         eligible_base_rate_within_3px=stats["eligible_base_rate_within_3px"],
                         enrichment_vs_base_rate=stats["enrichment_vs_base_rate"],
                         jaccard_dot_sets=stats["jaccard_dot_sets"],
                         n_mine=stats["n_mine"], n_other=stats["n_other"],
                         n_intersection=stats["n_intersection"], n_union=stats["n_union"],
                         overlap_gate_rule=stats["overlap_gate_rule"],
                         overlap_gate_value=stats["overlap_gate_value"],
                         overlap_gate_limit=stats["overlap_gate_limit"],
                         overlap_gate_exceeded=stats["overlap_gate_exceeded"],
                         duplicate_by_rho=stats["duplicate_by_rho"],
                         duplicate_by_overlap=stats["duplicate_by_overlap"],
                         duplicate_by_jaccard=stats["duplicate_by_jaccard"],
                         byte_identical=(bool(item.get("sha256")) and
                                         item.get("sha256") == item.get("candidate_sha256"))))
    comparable = [r for r in rows if "spearman_full_footprint" in r]
    duplicate_count = sum(bool(r["duplicate_by_rho"] or r["duplicate_by_overlap"])
                          for r in comparable)
    no_invalid_rows = not errors and len(comparable) == len(manifest.get("rasters", []))
    unique_in_scope = bool(comparable) and duplicate_count == 0 and no_invalid_rows
    cleared = unique_in_scope and bool(scope_complete)
    status = ("DUPLICATE — DO NOT SUBMIT" if duplicate_count else
              "NOT CLEARED — registry scope incomplete" if not cleared else "UNIQUE")
    return dict(evidence_class="MEASURED", rows=rows,
                duplicate_count=duplicate_count,
                unique_within_available_scope=unique_in_scope,
                registry_scope_complete=bool(scope_complete),
                unique=cleared, status=status,
                errors=errors, scope=scope or {},
                jaccard_diagnostic_only=True,
                limits=dict(rho=RHO_LIMIT, overlap=OVERLAP_LIMIT,
                            jaccard_diagnostic=JACCARD_LIMIT, overlap_px=px))
