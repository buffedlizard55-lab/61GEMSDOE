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
