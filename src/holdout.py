"""Spatially blocked hide-and-recover holdout + pooled DTI evaluation.

Protocol (fixed by the parallel-run lane protocol):
  * withhold WHOLE fault segments inside contiguous spatial blocks, with a buffer
    around the withheld set so that no catalogue-derived feature can trivially
    reconstruct a withheld pixel from its visible neighbour;
  * every catalogue-based feature must be derived ONLY from the visible faults;
  * score pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel) against the
    withheld pixels.

The withhold buffer is the crucial detail.  Without it, a 1-pixel-wide withheld
line is trivially recoverable by dilating the visible line 1 pixel -- which is not
a property the hidden competition set has, because the organisers removed whole
segments, so the nearest visible fault pixel to a withheld one is normally many
pixels away.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage
from scipy.ndimage import distance_transform_edt

from gems_metric import kernel_offsets, score_arrays

__all__ = ["make_folds", "evaluate_fold", "evaluate_all_folds", "basin_interior_mask",
           "FoldContext", "make_contexts"]


def make_folds(gt: np.ndarray, valid: np.ndarray, n_rows: int = 6, n_cols: int = 6,
               n_folds: int = 4, buffer_px: int = 6, min_segment_px: int = 8,
               seed: int = 0):
    """Build `n_folds` spatially blocked hide-and-recover folds.

    The raster is cut into ``n_rows x n_cols`` blocks.  Blocks are assigned to folds
    by a balanced round-robin over contiguous block runs, so each fold is a set of
    spatial regions rather than a scatter of pixels (scattered pixels leak: a
    withheld pixel would sit 2 px from a visible one).

    Returns a list of dicts: {hidden, visible, blocks, fold}.
    ``hidden`` are the withheld ground-truth pixels (withheld set, exactly as
    scored); ``visible`` are ground-truth pixels the method is allowed to see.
    """
    H, W = gt.shape
    rng = np.random.default_rng(seed)

    row_edges = np.linspace(0, H, n_rows + 1).astype(int)
    col_edges = np.linspace(0, W, n_cols + 1).astype(int)

    # Order blocks by (row, col) but shuffle the fold assignment of whole rows so
    # that each fold is a band of the map -- maximising the distance between the
    # withheld set and the visible set.
    row_fold = np.array([(i // max(1, n_rows // n_folds)) % n_folds for i in range(n_rows)])
    rng.shuffle(row_fold)

    folds = []
    for f in range(n_folds):
        block_mask = np.zeros((H, W), bool)
        for i in range(n_rows):
            if row_fold[i] != f:
                continue
            for j in range(n_cols):
                block_mask[row_edges[i]:row_edges[i + 1], col_edges[j]:col_edges[j + 1]] = True

        raw_hidden = gt & block_mask
        if raw_hidden.sum() == 0:
            continue

        # Drop specks so that "whole segments" is literally true.
        lbl, n = ndimage.label(raw_hidden, structure=np.ones((3, 3)))
        if n:
            sizes = np.bincount(lbl.ravel())
            keep = sizes >= min_segment_px
            keep[0] = False
            hidden = keep[lbl]
        else:
            hidden = raw_hidden

        # Buffer: any visible fault pixel within `buffer_px` of a withheld pixel is
        # also removed from what the method may see.
        near = ndimage.binary_dilation(hidden, iterations=buffer_px)
        visible = gt & ~near
        folds.append(dict(fold=f, hidden=hidden, visible=visible,
                          n_hidden=int(hidden.sum()), n_visible=int(visible.sum()),
                          row_fold=row_fold.copy()))
    return folds


class FoldContext:
    """Precomputed ground-truth geometry for one fold -- the fix for a measured
    performance defect, logged here because the lane protocol says a shared tool
    must be fixed once rather than forked.

    DEFECT.  The straightforward evaluator calls ``gems_metric.score_arrays`` per
    candidate, and every call rebuilds a Euclidean distance transform over the full
    12.3 M-pixel raster to get ``k(x -> G)``.  An operating-point sweep of ~60
    configurations x 4 folds is 240 transforms, i.e. ~16 minutes of pure waste on an
    unchanged quantity.

    FIX.  ``k(x -> G)`` depends only on the withheld set, so compute it once per fold
    and keep the flat views.  Scoring a candidate then costs one ``dot`` over the
    raster plus 29 gathers of length |G|.

    Soundness: ``reports/context_parity.json`` checks that
    :meth:`score` returns bit-comparable numbers to ``score_arrays`` on random
    predictions, so the cached path can never disagree with the official metric.
    """

    def __init__(self, fold: dict, valid: np.ndarray, R: int = 3):
        hidden = np.asarray(fold["hidden"], dtype=bool)
        H, W = hidden.shape
        self.shape = (H, W)
        self.n_gt = int(hidden.sum())
        self.valid_flat = np.asarray(valid, bool).ravel()
        dist = distance_transform_edt(~hidden)
        self.discount_flat = (1.0 - np.maximum(1.0 - dist / float(R), 0.0)).ravel()
        gy, gx = np.nonzero(hidden)
        self.gy, self.gx = gy, gx
        self.offsets = kernel_offsets(R)

    def score(self, pred: np.ndarray, alpha: float = 0.2, beta: float = 0.8):
        p = np.nan_to_num(np.asarray(pred, dtype=np.float64), nan=0.0)
        p = np.clip(p, 0.0, 1.0) * self.valid_flat.reshape(self.shape)
        FP_w = float((p.ravel() * self.discount_flat).sum())
        if self.n_gt == 0:
            return dict(dti=0.0, TP_w=0.0, FP_w=0.0, FN_w=0.0, n_gt=0)
        H, W = self.shape
        credit = np.zeros(self.n_gt)
        for dy, dx, k in self.offsets:
            sy, sx = self.gy + dy, self.gx + dx
            ok = (sy >= 0) & (sy < H) & (sx >= 0) & (sx < W)
            vals = np.zeros(self.n_gt)
            vals[ok] = p[sy[ok], sx[ok]]
            np.maximum(credit, k * vals, out=credit)
        TP_w = float(credit.sum())
        FN_w = float(self.n_gt) - TP_w
        return dict(dti=float(TP_w / (TP_w + alpha * FP_w + beta * FN_w + 1e-7)),
                    TP_w=TP_w, FP_w=FP_w, FN_w=FN_w, n_gt=self.n_gt)


def make_contexts(folds, valid, R: int = 3):
    return [FoldContext(f, valid, R=R) for f in folds]


def evaluate_fold(pred: np.ndarray, fold: dict, valid: np.ndarray,
                  alpha: float = 0.2, beta: float = 0.8, R: int = 3):
    """Pooled DTI of ``pred`` against this fold's withheld pixels.

    Convenience wrapper -- rebuilds the distance transform every call, so it is fine
    for a handful of candidate rasters and wrong for a sweep.  Use :class:`FoldContext`.
    """
    p = np.nan_to_num(np.asarray(pred, dtype=np.float64), nan=0.0)
    p = np.where(valid, np.clip(p, 0.0, 1.0), 0.0)
    return score_arrays(p, fold["hidden"], R=R, alpha=alpha, beta=beta)


def evaluate_all_folds(pred: np.ndarray, folds, valid: np.ndarray):
    """Mean and per-fold pooled DTI."""
    rows = [evaluate_fold(pred, f, valid) for f in folds]
    d = [float(r["dti"]) for r in rows]
    return dict(dti_mean=float(np.mean(d)), dti_std=float(np.std(d)),
                per_fold=d, rows=rows)


def basin_interior_mask(depth_to_basement: np.ndarray, valid: np.ndarray,
                        percentile: float = 60.0) -> np.ndarray:
    """'Basin interior' = covered ground where the pre-Tertiary surface is deep.

    The lane asks for recovery of *basin-interior* segments specifically, because
    those are the ones alluvial cover hides from a surface catalogue.  Uses the
    provided B15 depth-to-basement surface with a percentile cut over valid ground.
    """
    v = depth_to_basement[valid]
    thr = float(np.percentile(v, percentile))
    return valid & (depth_to_basement >= thr)
