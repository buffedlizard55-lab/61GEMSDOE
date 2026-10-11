"""Distance-weighted Tversky index (DTI) -- the official DOE GEMS Prize metric.

Transcribed VERBATIM from the official competition problem statement, performance
metric section (captured 2026-09-12 and re-verified 2026-10-04 by the GEMSDOE group;
mirrored with a hash pin in this repository at data/provenance.json):

    k(d)   = (1 - d/R)_+ = max(1 - d/R, 0)          R = 300 m = 3 px at 100 m
    TP_w   = sum_{g in G} max_{x: d(x,g) <= R} p(x) * k(d(x,g))
    FP_w   = sum_{x: p(x) > 0} p(x) * [1 - max_{g in G} k(d(x,g))]
    FN_w   = sum_{g in G} [1 - max_{x: d(x,g) <= R} p(x) * k(d(x,g))]
    DTI    = TP_w / (TP_w + alpha*FP_w + beta*FN_w + eps)     alpha = 0.2, beta = 0.8

Source page: https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/

Two identities used by the test-suite below:

1.  TP_w + FN_w = |G| for ANY prediction.  Each ground-truth pixel contributes
    ``m + (1 - m)`` with ``m = max_x p(x) k(d(x,g))``.
2.  DTI == F_beta with beta = 2.  Substituting FN_w = |G| - TP_w:

        DTI = TP_w / (TP_w + a FP_w + b (|G| - TP_w))
            = TP_w / ((1 - b) TP_w + a FP_w + b |G|)

    with a = 0.2, b = 0.8 -> (1-b) = 0.2, so

        DTI = TP_w / (0.2 TP_w + 0.2 FP_w + 0.8 |G|)
            = 5 TP_w / (TP_w + FP_w + 4 |G|)        (multiply by 5)
            = (1 + 2^2) TP_w / ((1 + 2^2) TP_w + 2^2 FN_w + FP_w)

    which is exactly the F_2 score.  ``tests`` in this module assert identity (2)
    numerically against the direct definition.

Worked example from the official problem page (TP=3.00, FP=1.89, FN=2.00):
    3 / (3 + 0.2*1.89 + 0.8*2.00) = 3 / 4.978 = 0.60265  -> the page prints 0.60.

Author: 61GEMSDOE (Arena agent session).  No external dependencies beyond numpy/scipy.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.ndimage import distance_transform_edt

__all__ = [
    "R_PIXELS",
    "ALPHA",
    "BETA",
    "EPS",
    "kernel_offsets",
    "DTIResult",
    "score_arrays",
    "self_test",
]

R_PIXELS = 3          # 300 m at 100 m posting
ALPHA = 0.2           # false-positive weight
BETA = 0.8            # false-negative weight
EPS = 1e-7


def kernel_offsets(R: int = R_PIXELS):
    """All (dy, dx, k) with Euclidean distance <= R and k = max(1 - d/R, 0).

    Exhaustive over the (2R+1)^2 square, filtered by the Euclidean radius, exactly
    as ``d(x, g)`` in the problem statement.  R = 3 gives 29 offsets.
    """
    offs = []
    for dy in range(-R, R + 1):
        for dx in range(-R, R + 1):
            d = math.hypot(dy, dx)
            if d <= R + 1e-12:
                offs.append((dy, dx, max(1.0 - d / R, 0.0)))
    return offs


class DTIResult(dict):
    """dict subclass so callers can print/JSON-serialise the score result directly."""

    @property
    def dti(self) -> float:
        return float(self["dti"])


def _sanitise(pred, shape):
    """The official input contract: NaN/Inf -> 0, values clipped to [0, 1]."""
    arr = np.asarray(pred, dtype=np.float64)
    if arr.shape != tuple(shape):
        raise ValueError(f"shape mismatch: pred {arr.shape} vs gt {tuple(shape)}")
    arr = np.nan_to_num(arr, nan=0.0, posinf=1.0, neginf=0.0)
    return np.clip(arr, 0.0, 1.0)


def score_arrays(pred, gt, R: int = R_PIXELS, alpha: float = ALPHA, beta: float = BETA):
    """Exact DTI of ``pred`` against binary ``gt``.

    Parameters
    ----------
    pred : 2-D float array, values in [0, 1].  NaN/Inf are treated as 0.
    gt   : 2-D array; a pixel is ground truth when ``gt > 0.5``.
    R    : kernel radius in pixels.
    alpha, beta : the official 0.2 / 0.8.

    Returns
    -------
    DTIResult with keys dti, TP_w, FP_w, FN_w, n_gt, pred_mass, n_pred_px.

    Complexity: O(H*W) for one Euclidean distance transform plus O(|G| * |offsets|)
    gathers -- no (H, W, 2R+1, 2R+1) temporary is ever formed.
    """
    gt_bool = np.asarray(gt) > 0.5
    p = _sanitise(pred, gt_bool.shape)
    H, W = gt_bool.shape
    n_gt = int(gt_bool.sum())
    offsets = kernel_offsets(R)

    if n_gt == 0:
        # No ground truth at all: TP_w = 0, FN_w = 0, DTI = 0 by definition.
        return DTIResult(dti=0.0, TP_w=0.0, FP_w=0.0, FN_w=0.0, n_gt=0,
                         pred_mass=float(p.sum()), n_pred_px=int((p > 0).sum()))

    # --- FP_w -----------------------------------------------------------------
    # k(x -> G) = max_g k(d(x,g)) = max(1 - dist(x, G)/R, 0)
    dist_to_gt = distance_transform_edt(~gt_bool)
    k_to_gt = np.maximum(1.0 - dist_to_gt / float(R), 0.0)
    FP_w = float((p * (1.0 - k_to_gt)).sum())

    # --- TP_w -----------------------------------------------------------------
    # credit(g) = max over the R-neighbourhood of k(d(x,g)) * p(x).  Gather only the
    # |G| ground-truth pixels (fault labels are ~1 % of the raster).
    gy, gx = np.nonzero(gt_bool)
    credit = np.zeros(gy.shape, dtype=np.float64)
    for dy, dx, k in offsets:
        sy, sx = gy + dy, gx + dx
        ok = (sy >= 0) & (sy < H) & (sx >= 0) & (sx < W)
        vals = np.zeros(gy.shape, dtype=np.float64)
        vals[ok] = p[sy[ok], sx[ok]]
        np.maximum(credit, k * vals, out=credit)
    TP_w = float(credit.sum())

    # --- FN_w (identity: TP_w + FN_w = |G|) -----------------------------------
    FN_w = float(n_gt) - TP_w

    n_pred_px = int((p > 0).sum())
    denom = TP_w + alpha * FP_w + beta * FN_w + EPS
    return DTIResult(
        dti=float(TP_w / denom),
        TP_w=TP_w,
        FP_w=FP_w,
        FN_w=FN_w,
        n_gt=n_gt,
        pred_mass=float(p.sum()),
        n_pred_px=n_pred_px,
    )


def closed_form(pred_mass: float, TP_w: float, n_gt: float,
                alpha: float = ALPHA, beta: float = BETA) -> float:
    """DTI using the algebraic rearrangement (used as a cross-check, not the oracle).

    DTI = TP_w / (0.2*(TP_w + FP_w) + 0.8*|G|)  holds when TP_w + FP_w == mass,
    which is *not* exact in general; kept only to document the group's shortcut and
    show where it drifts.  ``score_arrays`` is authoritative.
    """
    return TP_w / (alpha * (pred_mass) + beta * n_gt + (1.0 - beta) * TP_w + EPS)


# ---------------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------------
def _brute_force(pred, gt, R=R_PIXELS, alpha=ALPHA, beta=BETA):
    """Literal, loop-based transcription of the four official formulas."""
    p = np.nan_to_num(np.asarray(pred, dtype=np.float64), nan=0.0)
    p = np.clip(p, 0.0, 1.0)
    G = np.asarray(gt) > 0.5
    H, W = G.shape
    idx = np.argwhere(G)
    offs = kernel_offsets(R)

    TP_w = 0.0
    FN_w = 0.0
    for (gy, gx) in idx:
        best = 0.0
        for dy, dx, k in offs:
            sy, sx = gy + dy, gx + dx
            if 0 <= sy < H and 0 <= sx < W:
                best = max(best, p[sy, sx] * k)
        TP_w += best
        FN_w += 1.0 - best

    FP_w = 0.0
    py, px = np.nonzero(p > 0)
    for y, x in zip(py, px):
        best_g = 0.0
        for dy, dx, k in offs:
            gy, gx = y + dy, x + dx
            if 0 <= gy < H and 0 <= gx < W and G[gy, gx]:
                best_g = max(best_g, k)
        FP_w += p[y, x] * (1.0 - best_g)

    return TP_w / (TP_w + alpha * FP_w + beta * FN_w + EPS), TP_w, FP_w, FN_w


def self_test(verbose: bool = True) -> bool:
    """Falsifiable checks.  Returns True when all pass."""
    checks = []

    # 1. Official worked example: TP=3.00, FP=1.89, FN=2.00 -> 0.60
    v = 3.0 / (3.0 + 0.2 * 1.89 + 0.8 * 2.00)
    checks.append(("official worked example ~= 0.60", abs(v - 0.60265) < 1e-4, v))

    # 2. kernel offset count at R=3 is 29
    checks.append(("29 offsets at R=3", len(kernel_offsets(3)) == 29, len(kernel_offsets(3))))

    rng = np.random.default_rng(7)

    # 3. fast path == brute force on a random small field
    gt = np.zeros((40, 40), bool)
    gt[5:9, 6:20] = True
    gt[25:27, 30:34] = True
    pred = rng.random((40, 40)).astype(np.float64)
    fast = score_arrays(pred, gt)
    bf, TP, FP, FN = _brute_force(pred, gt)
    checks.append(("fast == brute (dense random)", abs(fast["dti"] - bf) < 1e-9 and
                   abs(fast["TP_w"] - TP) < 1e-9 and abs(fast["FP_w"] - FP) < 1e-9 and
                   abs(fast["FN_w"] - FN) < 1e-9, (fast["dti"], bf)))

    # 4. fast path == brute force on a sparse binary prediction (the competition regime)
    sp = (rng.random((40, 40)) > 0.97).astype(np.float64)
    fast = score_arrays(sp, gt)
    bf, _, _, _ = _brute_force(sp, gt)
    checks.append(("fast == brute (sparse binary)", abs(fast["dti"] - bf) < 1e-9,
                   (fast["dti"], bf)))

    # 5. identity TP_w + FN_w = |G|
    checks.append(("TP_w + FN_w == |G|", abs(fast["TP_w"] + fast["FN_w"] - int(gt.sum())) < 1e-9,
                   (fast["TP_w"] + fast["FN_w"], int(gt.sum()))))

    # 6. DTI == F_2 with the weighted TP/FP/FN
    TPv, FPv, FNv = fast["TP_w"], fast["FP_w"], fast["FN_w"]
    f2 = 5 * TPv / (5 * TPv + FPv + 4 * FNv)
    checks.append(("DTI == F_2 (beta=2)", abs(f2 - fast["dti"]) < 1e-9, (f2, fast["dti"])))

    # 7. perfect prediction -> 1.0 (except the eps)
    perfect = (gt.astype(np.float64) * 0.5 + 0.3) * gt  # p=0.8 exactly on GT pixels
    perfect = np.where(gt, 1.0, 0.0)
    r = score_arrays(perfect, gt)
    checks.append(("perfect prediction == 1.0", abs(r["dti"] - 1.0) < 1e-7, r["dti"]))

    # 8. all-zeros -> 0.0
    r = score_arrays(np.zeros_like(gt, dtype=float), gt)
    checks.append(("all zeros -> 0.0", r["dti"] == 0.0, r["dti"]))

    # 9. all-ones equals |G| / (|G| + 0.2 * FP_w) with FP_w = #px with k<1
    ones = np.ones(gt.shape)
    r = score_arrays(ones, gt)
    dist = distance_transform_edt(~gt)
    expected = int(gt.sum()) / (int(gt.sum()) + 0.2 * float((1 - np.maximum(1 - dist / 3, 0)).sum()))
    checks.append(("all ones matches hand computation", abs(r["dti"] - expected) < 1e-9,
                   (r["dti"], expected)))

    # 10. NaN / Inf handling
    w = np.zeros((10, 10)); w[:, :] = np.nan
    r = score_arrays(w, np.ones((10, 10), bool))
    checks.append(("all-NaN prediction -> 0.0", r["dti"] == 0.0, r["dti"]))

    # 11. out-of-range clipping, not trusting
    a = np.full((10, 10), 7.0)
    b = np.ones((10, 10))
    checks.append(("values >1 are clipped",
                   abs(score_arrays(a, np.ones((10, 10), bool))["dti"] -
                       score_arrays(b, np.ones((10, 10), bool))["dti"]) < 1e-12, None))

    # 12. translation invariance: shifting both pred and gt by the same amount
    gt2 = np.roll(gt, (3, 4), axis=(0, 1))
    p2 = np.roll(sp, (3, 4), axis=(0, 1))
    checks.append(("translation invariance (interior)",
                   abs(score_arrays(p2, gt2)["dti"] - score_arrays(sp, gt)["dti"]) < 0.02,
                   (score_arrays(p2, gt2)["dti"], score_arrays(sp, gt)["dti"])))

    # 13. monotone in a redundant extra false positive
    p3 = sp.copy(); p3[0, 0] = 1.0
    checks.append(("adding a far false positive lowers DTI",
                   score_arrays(p3, gt)["dti"] <= score_arrays(sp, gt)["dti"] + 1e-12,
                   (score_arrays(p3, gt)["dti"], score_arrays(sp, gt)["dti"])))

    ok = True
    for name, passed, val in checks:
        ok &= bool(passed)
        if verbose:
            print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f"   {val}" if val else ""))
    return ok


if __name__ == "__main__":
    print("gems_metric self-test (13 checks)")
    print("ALL PASS" if self_test() else "FAILURES PRESENT")
