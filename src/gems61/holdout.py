"""Shared spatial hide-and-recover holdout utilities.

Protocol: whole 8-connected catalogue components are hidden, a Euclidean
context buffer is removed from the visible catalogue, and the disjoint spatial
quadrants are evaluated with visible-catalogue pixels masked exactly. DTI is
computed by :mod:`gems61.evaluate_holdout` using the common official metric
(alpha=0.2, beta=0.8, 300 m triangular kernel).

This is a catalogue-segment recovery screen, not a leaderboard estimate: the
true unmapped faults are not published. Every reported score must be labelled
HOLDOUT-DTI with evaluator version, withheld-positive count, and a spatial-block
95% confidence interval.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage as ndi

BLOCK_SIDE_PX = 200          # 20 km spatial clusters for the bootstrap
R_M = 300.0
RES = 100.0
ALPHA, BETA = 0.2, 0.8
STRUCT8 = np.ones((3, 3), bool)


@dataclass(frozen=True)
class Fold:
    name: str
    region: np.ndarray        # bool, scored spatial quadrant
    truth: np.ndarray         # bool, withheld pixels within this region
    visible: np.ndarray       # bool, remaining visible catalogue (pixel-exact mask)
    hidden_ids: np.ndarray    # whole 8-connected component ids hidden globally
    n_truth: int
    n_segments: int
    hidden_all: np.ndarray    # full-grid hidden components; needed for segment-level recovery

    @property
    def domain(self) -> np.ndarray:
        """Compatibility alias used by older callers; identical to ``region``."""
        return self.region

    @property
    def hidden(self) -> np.ndarray:
        """Compatibility alias used by older callers; identical to fold truth."""
        return self.truth

    @property
    def masked_known(self) -> np.ndarray:
        return self.visible

    @property
    def n_hidden(self) -> int:
        """Compatibility alias for the number of withheld pixels in this fold."""
        return int(self.truth.sum())

    def __getitem__(self, key: str):
        """Allow older dictionary-style fold consumers without forking the helper."""
        aliases = {"domain": "region", "hidden": "truth", "masked_known": "visible",
                   "n_hidden": "n_truth"}
        field = aliases.get(key, key)
        if field in self.__dataclass_fields__:
            return getattr(self, field)
        raise KeyError(key)


def catalogue_components(catalogue: np.ndarray) -> tuple[np.ndarray, int]:
    """8-connected components of the mapped-fault catalogue."""
    lab, n = ndi.label(np.asarray(catalogue, bool), structure=STRUCT8)
    return lab, int(n)


def _quadrants(shape: tuple[int, int], n_folds: int) -> list[tuple[str, np.ndarray]]:
    h, w = shape
    if n_folds == 2:
        masks = []
        north = np.zeros(shape, bool); north[:h // 2] = True
        south = np.zeros(shape, bool); south[h // 2:] = True
        return [("N", north), ("S", south)]
    if n_folds != 4:
        raise ValueError("n_folds must be 2 or 4")
    rmid, cmid = h // 2, w // 2
    masks = []
    for name, rs, cs in (
        ("NW", (0, rmid), (0, cmid)), ("NE", (0, rmid), (cmid, w)),
        ("SW", (rmid, h), (0, cmid)), ("SE", (rmid, h), (cmid, w)),
    ):
        m = np.zeros(shape, bool)
        m[rs[0]:rs[1], cs[0]:cs[1]] = True
        masks.append((name, m))
    return masks


def make_folds(catalogue: np.ndarray, footprint: np.ndarray, fraction: float = 0.20,
               buffer_px: int = 3, seed: int = 20261011, n_folds: int = 4,
               min_component_px: int = 1, *, collar_px: int | None = None,
               min_px: int | None = None) -> list[Fold]:
    """Hide whole 8-connected segments, buffer visible context, and split spatially.

    The current argument order is ``(catalogue, footprint)``. To keep older
    repository callers working, the helper detects the historical reversed
    ``(footprint, catalogue)`` order when one mask is unambiguously contained in
    the other, accepts ``collar_px``/``min_px`` aliases, and keeps dictionary-style
    field access on :class:`Fold`.

    The same globally hidden component draw is used in each quadrant. Components
    may cross quadrant boundaries, but they are hidden in full before any fold is
    formed; quadrant scoring only partitions their truth pixels for the spatial
    bootstrap. Segment-recovery calculations use ``hidden_all`` and therefore
    count each original component once rather than counting quadrant fragments.
    """
    cat = np.asarray(catalogue, bool)
    fp = np.asarray(footprint, bool)
    if cat.ndim != 2 or cat.shape != fp.shape:
        raise ValueError("catalogue and footprint must be matching 2-D arrays")
    # Historical callers supplied footprint first. Compare the amount of each
    # mask that falls outside the other; reverse only when it is clearly the
    # only ordering consistent with catalogue being a subset of the footprint.
    outside_forward = int((cat & ~fp).sum())
    outside_reverse = int((fp & ~cat).sum())
    if (float(cat.mean()) > float(fp.mean()) and
            outside_reverse < outside_forward):
        cat, fp = fp, cat
    if collar_px is not None:
        buffer_px = collar_px
    if min_px is not None:
        min_component_px = min_px
    if not 0.0 < float(fraction) <= 1.0:
        raise ValueError("fraction must be in (0, 1]")
    if int(buffer_px) < 0:
        raise ValueError("buffer_px must be non-negative")
    if int(min_component_px) < 1:
        raise ValueError("min_component_px must be at least 1")
    cat = cat & fp
    lab, n = catalogue_components(cat)
    sizes = np.bincount(lab.ravel(), minlength=n + 1)
    eligible_ids = np.flatnonzero(sizes[1:] >= int(min_component_px)).astype(np.int32) + 1
    if eligible_ids.size == 0:
        raise ValueError("no catalogue components meet min_component_px")
    rng = np.random.default_rng(seed)
    ids = rng.permutation(eligible_ids)
    n_hide = min(ids.size, max(1, int(round(float(fraction) * ids.size))))
    hidden_ids = np.sort(ids[:n_hide])
    hidden = np.isin(lab, hidden_ids) & cat
    if not hidden.any():
        raise ValueError("withheld draw is empty")
    # Euclidean px buffer matches the metric's distance convention; square
    # binary dilation would over-buffer diagonals beyond the declared radius.
    dist_hidden = ndi.distance_transform_edt(~hidden)
    visible = cat & (dist_hidden > float(buffer_px))

    folds = []
    for name, qmask in _quadrants(cat.shape, n_folds):
        region = qmask & fp
        truth = hidden & region
        if not truth.any():
            continue
        ids_here = np.unique(lab[truth])
        ids_here = ids_here[ids_here > 0]
        folds.append(Fold(name=name, region=region, truth=truth, visible=visible,
                          hidden_ids=hidden_ids, n_truth=int(truth.sum()),
                          n_segments=int(ids_here.size), hidden_all=hidden))
    if not folds:
        raise ValueError("no fold contains withheld positives")
    return folds


def basin_interior_mask(depth: np.ndarray, valid: np.ndarray,
                        depth_quantile: float = 0.60) -> np.ndarray:
    """Deepest ``1-depth_quantile`` fraction of the candidate's own inversion."""
    d = np.asarray(depth, np.float64)
    v = np.asarray(valid, bool)
    if d.ndim != 2 or d.shape != v.shape:
        raise ValueError("depth and valid mask must be matching 2-D arrays")
    if not 0.0 <= depth_quantile <= 1.0:
        raise ValueError("depth_quantile must be in [0,1]")
    m = v & np.isfinite(d)
    if not m.any():
        raise ValueError("no finite depth cells inside valid mask")
    threshold = float(np.quantile(d[m], depth_quantile))
    return m & (d >= threshold)


def basin_interior_segments(hidden: np.ndarray, deep_mask: np.ndarray,
                            min_deep_fraction: float = 0.50) -> dict:
    """Select whole hidden components with >=50% of pixels in the deep mask."""
    h = np.asarray(hidden, bool)
    deep = np.asarray(deep_mask, bool)
    if h.ndim != 2 or h.shape != deep.shape:
        raise ValueError("hidden and deep mask must be matching 2-D arrays")
    if not 0.0 <= min_deep_fraction <= 1.0:
        raise ValueError("min_deep_fraction must be in [0,1]")
    lab, n = catalogue_components(h)
    sizes = np.bincount(lab.ravel(), minlength=n + 1)
    deep_counts = np.bincount(lab[deep].ravel(), minlength=n + 1)
    fractions = np.divide(deep_counts[1:], sizes[1:], out=np.zeros(n, float),
                          where=sizes[1:] > 0)
    keep_ids = np.flatnonzero(fractions >= float(min_deep_fraction)) + 1
    eligible = np.isin(lab, keep_ids) & deep
    rows = [dict(component_id=int(i + 1), pixels=int(sizes[i + 1]),
                  deep_pixels=int(deep_counts[i + 1]),
                  deep_fraction=float(fractions[i])) for i in range(n)
            if fractions[i] >= float(min_deep_fraction)]
    return dict(mask=eligible, labels=lab, eligible_ids=keep_ids.astype(np.int32),
                component_stats=rows, n_components=int(n),
                n_eligible=int(keep_ids.size), min_deep_fraction=float(min_deep_fraction))


def distance_to_mask(mask: np.ndarray, res: float = RES) -> np.ndarray:
    """Euclidean distance in metres to the nearest True cell; +inf if empty."""
    m = np.asarray(mask, bool)
    if not m.any():
        return np.full(m.shape, np.inf, np.float64)
    return ndi.distance_transform_edt(~m, sampling=float(res))


def segment_recovery(pred: np.ndarray, folds: list[Fold], R: float = R_M,
                     res: float = RES, restrict: np.ndarray | None = None,
                     min_deep_fraction: float = 0.50) -> dict:
    """Recover basin-interior segments under the preregistered component rule.

    A component is eligible only when at least ``min_deep_fraction`` of its
    pixels lie in ``restrict`` (the deepest 40% mask). It is recovered if any
    prediction lies within ``R`` metres of one of that component's in-mask
    pixels. The result includes pooled counts and an assignment by the centroid
    quadrant, so a component spanning fold boundaries is never counted twice.
    """
    if not folds:
        raise ValueError("at least one fold is required")
    p = np.asarray(pred, bool)
    shape = folds[0].truth.shape
    if p.shape != shape or any(f.truth.shape != shape for f in folds):
        raise ValueError("prediction/fold shape mismatch")
    hidden_all = np.asarray(folds[0].hidden_all, bool)
    for f in folds[1:]:
        if not np.array_equal(hidden_all, f.hidden_all):
            raise ValueError("folds do not share the same whole-component hidden draw")
    deep = np.ones(shape, bool) if restrict is None else np.asarray(restrict, bool)
    if deep.shape != shape:
        raise ValueError("deep-mask shape mismatch")
    comp = basin_interior_segments(hidden_all, deep, min_deep_fraction)
    ids = comp["eligible_ids"]
    labels = comp["labels"]
    d_pred = distance_to_mask(p, res=float(res))
    by_fold = {f.name: dict(n=0, recovered=0, frac=0.0, eligible_segments=0,
                            recovered_segments=0) for f in folds}
    rows = []
    for cid in ids:
        pixels = labels == int(cid)
        yy, xx = np.nonzero(pixels)
        if yy.size == 0:
            continue
        cy, cx = int(np.round(yy.mean())), int(np.round(xx.mean()))
        owners = [f for f in folds if f.region[cy, cx]]
        if not owners:
            # Centroid may fall outside the scored footprint; assign by largest
            # pixel overlap to the supplied spatial regions, deterministically.
            owners = [max(folds, key=lambda f: int((pixels & f.region).sum()))]
        owner = owners[0]
        in_mask_pixels = pixels & deep
        recovered = bool((d_pred[in_mask_pixels] <= float(R)).any())
        row = dict(component_id=int(cid), total_pixels=int(pixels.sum()),
                   deep_pixels=int(in_mask_pixels.sum()),
                   deep_fraction=float(in_mask_pixels.sum() / max(int(pixels.sum()), 1)),
                   recovered=recovered, fold=owner.name,
                   min_candidate_distance_m=float(d_pred[in_mask_pixels].min()))
        rows.append(row)
        by_fold[owner.name]["n"] += 1
        by_fold[owner.name]["eligible_segments"] += 1
        if recovered:
            by_fold[owner.name]["recovered"] += 1
            by_fold[owner.name]["recovered_segments"] += 1
    for value in by_fold.values():
        value["frac"] = (value["recovered"] / value["n"] if value["n"] else 0.0)
    n = len(rows)
    recovered = sum(int(row["recovered"]) for row in rows)
    pooled = dict(n=n, recovered=recovered, frac=(recovered / n if n else 0.0),
                  eligible_segments=n, recovered_segments=recovered,
                  eligibility_rule=f">={min_deep_fraction:.0%} component pixels in deepest 40%",
                  recovery_distance_m=float(R), withheld_component_count=int(comp["n_components"]))
    result = dict(evidence_class="HOLDOUT-SEGMENT-RECOVERY", pooled=pooled,
                  by_fold=by_fold, segments=rows,
                  min_deep_fraction=float(min_deep_fraction),
                  recovery_distance_m=float(R), resolution_m=float(res))
    # Compatibility for callers that index the result by fold name.
    result.update(by_fold)
    return result


def kernel(d_m: np.ndarray, R: float = R_M) -> np.ndarray:
    return np.clip(1.0 - np.asarray(d_m, np.float64) / float(R), 0.0, 1.0)


def dti(truth: np.ndarray, pred: np.ndarray, domain: np.ndarray,
        R: float = R_M, res: float = RES):
    """Exact binary DTI, returning (coverage, pooled, parts)."""
    T = np.asarray(truth, bool) & np.asarray(domain, bool)
    P = np.asarray(pred, bool) & np.asarray(domain, bool)
    if T.shape != P.shape:
        raise ValueError("truth and prediction shape mismatch")
    n_truth, n_pred = int(T.sum()), int(P.sum())
    if n_truth == 0:
        return 0.0, 0.0, dict(TP=0.0, FP=float(n_pred), FN=0.0,
                              n_truth=0, n_pred=n_pred, mean_d=None)
    if n_pred == 0:
        return 0.0, 0.0, dict(TP=0.0, FP=0.0, FN=float(n_truth),
                              n_truth=n_truth, n_pred=0, mean_d=float("inf"))
    d_pred = ndi.distance_transform_edt(~P, sampling=float(res))
    d_truth = ndi.distance_transform_edt(~T, sampling=float(res))
    tp = float(kernel(d_pred[T], R).sum())
    fn = float(n_truth) - tp
    fp = float((1.0 - kernel(d_truth[P], R)).sum())
    cov = tp / (tp + ALPHA * fp + BETA * fn)
    pooled = tp / (ALPHA * n_pred + BETA * n_truth)
    return float(cov), float(pooled), dict(TP=tp, FP=fp, FN=fn,
        n_truth=n_truth, n_pred=n_pred, mean_d=float(d_pred[T].mean()),
        med_d=float(np.median(d_pred[T])),
        frac_truth_within_R=float((d_pred[T] <= R).mean()))


def segments(catalogue: np.ndarray, min_px: int = 1) -> np.ndarray:
    """8-connected components; labels smaller than ``min_px`` become zero."""
    if min_px < 1:
        raise ValueError("min_px must be >=1")
    lab, n = catalogue_components(catalogue)
    if min_px > 1:
        sizes = np.bincount(lab.ravel(), minlength=n + 1)
        keep = sizes >= int(min_px)
        keep[0] = False
        lab = np.where(keep[lab], lab, 0)
    return lab


def random_lines(shape: tuple[int, int], n_px: int, domain: np.ndarray, rng,
                 seg_len: tuple[int, int] = (8, 40)) -> np.ndarray:
    """Draw random straight segments clipped to a domain at an exact pixel budget."""
    h, w = map(int, shape)
    allowed = np.asarray(domain, bool)
    if allowed.shape != (h, w):
        raise ValueError("domain shape does not match requested output shape")
    budget = int(n_px)
    if budget < 0 or budget > int(allowed.sum()):
        raise ValueError("pixel budget must be between zero and domain size")
    if budget == 0:
        return np.zeros((h, w), bool)
    lo, hi = map(int, seg_len)
    if lo < 2 or hi <= lo:
        raise ValueError("seg_len must be (min>=2, max>min)")
    if not hasattr(rng, "uniform") or not hasattr(rng, "integers"):
        raise TypeError("rng must be a numpy Generator")
    chosen: set[int] = set()
    attempts = 0
    max_attempts = max(10000, budget * 100)
    flat_allowed = np.flatnonzero(allowed)
    while len(chosen) < budget and attempts < max_attempts:
        attempts += 1
        length = int(rng.integers(lo, hi))
        y0 = int(rng.integers(0, h)); x0 = int(rng.integers(0, w))
        theta = float(rng.uniform(0.0, np.pi))
        t = np.arange(length, dtype=np.float64) - (length - 1) / 2.0
        yy = np.rint(y0 + t * np.sin(theta)).astype(np.int64)
        xx = np.rint(x0 + t * np.cos(theta)).astype(np.int64)
        ok = (yy >= 0) & (yy < h) & (xx >= 0) & (xx < w)
        yy, xx = yy[ok], xx[ok]
        if yy.size:
            flat = yy * w + xx
            flat = flat[allowed[yy, xx]]
            chosen.update(int(v) for v in flat)
    if len(chosen) < budget:
        remaining = np.setdiff1d(flat_allowed, np.fromiter(chosen, dtype=np.int64),
                                 assume_unique=False)
        if remaining.size < budget - len(chosen):
            raise RuntimeError("unable to draw requested random-line pixel budget")
        extra = rng.choice(remaining, size=budget - len(chosen), replace=False)
        chosen.update(int(v) for v in extra)
    # If the last random line overshot, trim at random so the budget is exact.
    ids = np.fromiter(chosen, dtype=np.int64)
    if ids.size > budget:
        ids = rng.choice(ids, size=budget, replace=False)
    out = np.zeros((h, w), bool)
    out.ravel()[ids] = True
    return out


def auc(score: np.ndarray, labels: np.ndarray, n_bg: int = 400000, seed: int = 0) -> float:
    """Compatibility wrapper for the shared rank-sum leakage canary."""
    from .evaluate_holdout import auc as shared_auc
    s = np.asarray(score, np.float64)
    y = np.asarray(labels, bool)
    if s.shape != y.shape:
        raise ValueError("score and labels shape mismatch")
    valid = np.isfinite(s)
    return shared_auc(s, y, valid, n_bg=n_bg, seed=seed)
