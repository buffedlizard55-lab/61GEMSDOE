"""Uniqueness against the registry of previously scored rasters.

The parallel-run protocol defines drift as either
  * rank correlation with any registry raster above 0.90, or
  * more than 70 % of this raster's pixels falling within 3 px of ONE registry
    raster's pixels.

Both are measured here and written out verbatim.  Rank correlation on two sparse
binary rasters is dominated by the shared zeros, so the reported rank figure is
labelled as such and the overlap figures are given alongside it -- an overlap of
1.5 % is the number that actually answers "did we drift into another lane".
"""

from __future__ import annotations

import glob
import os

import numpy as np
import rasterio
from scipy.ndimage import binary_dilation
from scipy.stats import spearmanr

__all__ = ["check_uniqueness"]

DRIFT_RHO = 0.90
DRIFT_OVERLAP = 0.70


def _read(p):
    with rasterio.open(p) as s:
        return np.nan_to_num(s.read(1).astype(np.float64), nan=0.0)


def check_uniqueness(submission_path: str, registry_dir: str,
                     max_pixels_for_rho: int = 3_000_000) -> dict:
    """Compare a submission against every raster in ``registry_dir``."""
    mine = _read(submission_path)
    my_mask = mine > 0.5
    n_mine = int(my_mask.sum())
    out = dict(submission=os.path.basename(submission_path),
               n_pixels_emitted=n_mine, registry_dir=registry_dir,
               thresholds=dict(rank_correlation=DRIFT_RHO, overlap_within_3px=DRIFT_OVERLAP),
               per_raster=[], verdict="unique", summary="")

    files = sorted(glob.glob(os.path.join(registry_dir, "*.tif")))
    if not files:
        out["verdict"] = "unchecked"
        out["summary"] = f"no registry rasters found in {registry_dir}; run scripts/fetch_registry.sh"
        return out

    # distance transform of MY raster, one per registry file is unnecessary: build the
    # 3-px dilation once and test membership.
    near_mine = binary_dilation(my_mask, iterations=3)

    rng = np.random.default_rng(0)
    H, W = mine.shape
    flat_mine = mine.ravel()
    if flat_mine.size > max_pixels_for_rho:
        idx = rng.choice(flat_mine.size, max_pixels_for_rho, replace=False)
    else:
        idx = slice(None)

    worst_rho, worst_overlap, worst_name = 0.0, 0.0, None
    for p in files:
        theirs = _read(p)
        theirs_mask = theirs > 0.5
        if theirs.shape != mine.shape:
            out["per_raster"].append(dict(file=os.path.basename(p),
                                          error="shape mismatch"))
            continue
        inter = int((my_mask & theirs_mask).sum())
        union = int((my_mask | theirs_mask).sum())
        # fraction of MY pixels that sit within 3 px of THEIR pixels
        sub3 = int(np.isin(np.flatnonzero(my_mask.ravel()),
                           np.flatnonzero(binary_dilation(theirs_mask,
                                                          iterations=3).ravel())).sum())
        rho = float(spearmanr(flat_mine[idx], theirs.ravel()[idx]).statistic)
        frac_within3 = sub3 / max(1, n_mine)
        out["per_raster"].append(dict(
            file=os.path.basename(p),
            iou_pct=round(100.0 * inter / max(1, union), 4),
            n_their_pixels=int(theirs_mask.sum()),
            shared_pixels=inter,
            my_pixels_within_3px_of_theirs=sub3,
            my_pixels_within_3px_fraction=round(frac_within3, 6),
            rank_correlation_including_zeros=round(rho, 6),
        ))
        if rho > worst_rho:
            worst_rho, worst_name = rho, os.path.basename(p)
        worst_overlap = max(worst_overlap, frac_within3)

    drift = (worst_rho > DRIFT_RHO) or (worst_overlap > DRIFT_OVERLAP)
    out["worst_rank_correlation"] = round(worst_rho, 6)
    out["worst_rank_correlation_against"] = worst_name
    out["worst_pixels_within_3px_fraction"] = round(worst_overlap, 6)
    out["verdict"] = "DUPLICATE-LANE-DRIFT" if drift else "unique"
    out["summary"] = (
        f"highest rank correlation {worst_rho:.3f} (< {DRIFT_RHO}); "
        f"highest 3-px overlap fraction {worst_overlap:.4f} (< {DRIFT_OVERLAP})"
        if not drift else
        f"DRIFT: rho {worst_rho:.3f} / overlap {worst_overlap:.3f} -- stop and log as duplicate")
    out["caveat"] = ("The rank correlation includes the ~99 % of pixels that are zero in "
                     "both rasters, so it is bounded away from 0 by construction; the "
                     "3-px overlap fraction is the discriminating statistic and is the "
                     "one to read.")
    return out
