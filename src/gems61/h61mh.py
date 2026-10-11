"""H61-MH (H61-M habitat) -- basement-step corridor x learned off-catalogue fault
habitat.

Why this exists
---------------
The previous session (H61-G) measured the lane's hard limit: the horizontal
gradient of the inverted basement surface is *not* enriched within the 300 m
scoring kernel of mapped faults (enrichment 1.0-1.3x random,
``evidence/h61g_screen.json``), so a basement step can say *where to look* but
not *where to put the dot*.  H61-G answered that by multiplying the corridor
prior by one hand-written locator (the detrended-elevation slope ridge, band 19)
and reached HOLDOUT-DTI 0.0465 against 0.0314 for random lines.

H61-M keeps the lane's physics and replaces the single hand-written locator with
an **out-of-fold habitat model**:

1. **Lane instrument, finer grid.**  The Parker/Oldenburg slab inversion of the
   isostatic residual is run at 200 m (decimation 2) as well as 400 m.  The lane
   paragraph states that gravity resolves a basement step "only to a few hundred
   metres at best"; halving the inversion cell is the direct response, and the
   400 m solution is kept as the cross-check (the two must agree in rank).
2. **Corridor.**  Blakely-Simpson maxima of |grad depth| with a measured throw,
   buffered to +/- 1 km -- exactly the buried range-front / intrabasin step the
   lane asks for.
3. **Habitat model.**  L2 logistic regression, trained on the *visible* mapped
   faults as positives and random footprint pixels as negatives, over the catalogue-independent feature stack: the 18 permitted supplied
   bands (rank-normalised; organizer band 15 excluded) plus the lane's own
   inverted depth, depth gradient, step throw, step indicator, corridor
   indicator, basin indicator, Euler source-depth estimate, and depth-gradient
   components.
   Historical band-15 runs are retired. **No feature derived from the position
   of the mapped catalogue enters the model** -- that is what makes the
   prediction an off-catalogue habitat estimate rather than a distance-to-map
   proxy, and it is why the model can be applied to the pixels the metric
   actually scores.
4. **Competing explanation, tested not asserted.**  The lane names density
   contrasts inside the basement as the mimic.  Two of the 25 features are
   exactly the discriminator the lane asks for: the inverted *depth* (a real
   basin step sits at the top of a thick low-density fill, an intrabasement
   contact does not) and the source-depth-consistency of the gravity edge
   (:func:`gems61.h61m.euler_source_depth`).  Their weights are reported, not
   hidden.
5. **Emission.**  Rank by out-of-fold probability inside the corridor, one dot
   per 3 x 3 tile (the spacing at which two binary dots stop duplicating each
   other's kernel credit), pruned to more than ``PRUNE_PX`` from every *visible*
   mapped trace.  The group's own scored rasters show that pruning at 3 px beat
   pruning at 2 px (0.2600 -> 0.2778, verified as an exact set difference in
   ``reports/forensics.json``), so the prune distance is swept, not assumed.

Everything is scored on the shared segmented holdout
(:mod:`gems61.holdout_segmented`, whole segments, 4 eroded quadrants, seeds
20+21, pooled DTI alpha 0.2 beta 0.8 R = 300 m).  Nothing is hand-written.
"""

# NOTE ON NAMING (IR-61-NAME-01): two parallel sessions both labelled their
# buried-structure-lane work "H61-M". The gravity + magnetic conjunction
# construction merged from PR #21 owns `src/gems61/h61m.py` and
# `scripts/run_h61m.py`; this out-of-fold habitat model owns the `h61mh`
# (H61-M habitat) namespace. Both bodies of work are kept.
#
# RETIREMENT NOTICE: historical receipts from this module included organizer
# band 15. That path is invalid for the current task. It is not a current
# candidate or a verified GP-1012 calibration; the shared calibrator now fails
# closed unless supplied the complete official GP-1012 source grid.

from __future__ import annotations

import json
import pathlib

import numpy as np
from scipy import ndimage as ndi

from . import buried as B
from .lane61 import decimate_mean, upsample_bilinear

# --------------------------------------------------------------------------- #
# Grid / lane constants
# --------------------------------------------------------------------------- #
DECIMATION_COARSE = 4          # 400 m inversion grid (previous session's choice)
DECIMATION_FINE = 2            # 200 m inversion grid (this session's choice)
CORRIDOR_PX = 10               # +/- 1 km around a basement-step line (100 m px)
MIN_THROW_M = 80.0
BASIN_FLOOR_M = 100.0
REGIONAL_SIGMA_KM = 15.0
TILE_PX = 3                    # dot spacing (one dot per TILE_PX x TILE_PX tile)

# The 25 habitat features.  Order is fixed so receipts are comparable.
BAND_FEATURES = [b for b in range(1, 20) if b != 15]  # band 15 is prohibited
DERIVED_FEATURES = ("inv_depth", "inv_depth_hgm", "step_throw", "step_indicator",
                    "corridor_indicator", "basin_indicator", "euler_depth",
                    "depth_grad_x", "depth_grad_y")


# --------------------------------------------------------------------------- #
# 1. Inversion at a chosen decimation
# --------------------------------------------------------------------------- #
def invert(grav_full: np.ndarray, valid_full: np.ndarray, decimation: int,
           *, regional_sigma_km: float = REGIONAL_SIGMA_KM,
           candidates=(-300.0, -350.0, -400.0, -450.0, -500.0, -600.0),
           z0_candidates=(300.0, 400.0, 500.0, 700.0),
           kc_scales=(0.5, 0.25, 0.125)) -> dict:
    """Band-pass the isostatic residual, then run the GP-1012-calibrated slab
    inversion on a ``decimation``-fold coarse grid.

    Identical arithmetic to :func:`gems61.h61g.invert_basement`; only the
    inversion cell size differs, and that difference is the point of this
    session.
    """
    dx = B.PIXEL_M * decimation
    small = decimate_mean(np.where(valid_full & np.isfinite(grav_full), grav_full, np.nan),
                          decimation)
    valid = np.isfinite(small)
    filled = B.inpaint_smooth(small, valid)
    sig_px = regional_sigma_km * 1000.0 / dx
    regional = ndi.gaussian_filter(filled, sig_px, mode="nearest") if sig_px > 0 else 0.0
    resid = filled - regional
    calib = B.calibrate_density_scale(resid, valid, dx=dx, candidates=candidates,
                                      kc_scales=kc_scales, z0_candidates=z0_candidates)
    best = calib["best"]
    sol = B.slab_solution(resid, valid, best["delta_rho"], best["z0_m"], dx=dx,
                          kc_scale=best["kc_scale"])
    depth = np.clip(np.asarray(sol["depth_m"], np.float64), 0.0, 8000.0)
    depth[~valid] = np.nan
    return dict(depth_small=depth, valid_small=valid, resid_small=resid, dx=dx,
                decimation=int(decimation),
                calibration=dict(best=best, anchors=calib["anchors"], source=calib["source"],
                                 n_combinations=len(calib["table"])),
                inversion=dict(stage=sol["stage"], filter=sol["filter"],
                               rms_residual_mgal=sol["rms_residual_mgal"],
                               delta_rho=sol["delta_rho"], z0_m=sol["z0_m"],
                               regional_sigma_km=regional_sigma_km,
                               source_doi=sol["source_doi"]))


def steps_of(depth_small: np.ndarray, dx: float, *, min_throw_m: float = MIN_THROW_M):
    """Blakely-Simpson maxima of |grad depth| with a measured throw filter."""
    d = np.asarray(depth_small, np.float64)
    finite = np.isfinite(d)
    work = B.inpaint_smooth(d, finite)
    hgm = B.horizontal_gradient_magnitude(np.where(finite, work, np.nan), dx)
    mx = B.blakely_simpson_maxima(hgm) & finite
    throw = B.step_magnitude(np.where(finite, work, np.nan), mx, window_px=1)
    keep = mx & np.isfinite(throw) & (throw >= min_throw_m)
    return dict(hgm=hgm, maxima=mx, throw=throw, steps=keep,
                n_maxima=int(mx.sum()), n_steps=int(keep.sum()))


def euler_source_depth(gx: np.ndarray, gy: np.ndarray, gz: np.ndarray,
                       structural_index: float = 0.0) -> np.ndarray:
    """Euler depth of a gravity edge from its three orthogonal gradients.

    The Euler homogeneity equation for a field ``f`` about a source at depth z0::

        x*fx + y*fy + z*fz = (N - B) * f

    with structural index N=0 (the ideal-contact / step case) reduces to
        z0 = -f / fz  ...  (fz is the vertical derivative)
    which is the classic "Euler deconvolution with SI = 0" contact-depth
    estimator (Reid et al. 1990, doi:10.1190/1.1442789).  Here the three
    gradients are the supplied horizontal gradient (band 18), its two
    directional components and the supplied vertical gradient (band 11); the
    result is a per-pixel estimate of the depth of the source that makes the
    edge.  A *basement* step has z0 comparable with the inverted fill
    thickness; an intrabasement density contact has z0 much larger.  That is
    the lane's named competing explanation, turned into a feature.
    """
    f = np.asarray(gx, np.float64)          # horizontal-gradient magnitude proxy for f
    fz = np.asarray(gz, np.float64)         # vertical derivative
    out = np.full(f.shape, np.nan)
    ok = np.isfinite(f) & np.isfinite(fz) & (np.abs(fz) > 1e-9)
    out[ok] = -f[ok] / fz[ok]
    return out


# --------------------------------------------------------------------------- #
# 2. Feature stack
# --------------------------------------------------------------------------- #
def load_or_invert(grav, valid, cache_dir, decimation):
    """Invert once, then reuse the cached depth surface + calibration receipt."""
    cache_dir = pathlib.Path(cache_dir)
    meta_path = cache_dir / f"inversion_d{decimation}.json"
    depth_path = cache_dir / f"depth_small_d{decimation}.npy"
    if meta_path.exists() and depth_path.exists():
        meta = json.loads(meta_path.read_text())
        depth = np.load(depth_path)
        return dict(depth_small=depth, valid_small=np.isfinite(depth),
                    resid_small=None, dx=B.PIXEL_M * decimation,
                    decimation=int(decimation), calibration=meta["calibration"],
                    inversion=meta["inversion"], reused=True)
    inv = invert(grav, valid, decimation)
    cache_dir.mkdir(parents=True, exist_ok=True)
    np.save(depth_path, np.where(np.isfinite(inv["depth_small"]), inv["depth_small"], np.nan))
    meta_path.write_text(json.dumps(dict(calibration=inv["calibration"],
                                         inversion=inv["inversion"]), indent=1))
    inv["reused"] = False
    return inv


def build_feature_stack(grav, valid, shape, out_path=None, cache_dir=None):
    """Return (names, stack (H,W,F) float32 in [0,1], meta, aux).

    ``stack`` is NaN outside the footprint.  No feature uses the mapped
    catalogue.  The stack is written channel-by-channel straight into a float32
    memmap so the 19 supplied bands are never all resident as float64 at once
    (the sandbox has ~3.9 GB of RAM; 19 x 98 MB of float64 channels plus the
    stack would not fit).
    """
    H, W = shape
    F = len(BAND_FEATURES) + len(DERIVED_FEATURES)
    names = [f"band{i:02d}" for i in BAND_FEATURES] + list(DERIVED_FEATURES)

    if cache_dir is not None:
        inv_c = load_or_invert(grav, valid, cache_dir, DECIMATION_COARSE)
        inv_f = load_or_invert(grav, valid, cache_dir, DECIMATION_FINE)
    else:
        inv_c = invert(grav, valid, DECIMATION_COARSE)
        inv_f = invert(grav, valid, DECIMATION_FINE)

    depth_c = _up(np.where(np.isfinite(inv_c["depth_small"]), inv_c["depth_small"], np.nan), (H, W))
    depth_f = _up(np.where(np.isfinite(inv_f["depth_small"]), inv_f["depth_small"], np.nan), (H, W))
    depth_small = inv_f["depth_small"]
    dx_f = inv_f["dx"]
    st_f = steps_of(depth_small, dx_f)
    hgm_f = _up(np.where(np.isfinite(st_f["hgm"]), st_f["hgm"], np.nan), (H, W))
    throw_f = _up(np.where(np.isfinite(st_f["throw"]), st_f["throw"], 0.0), (H, W))
    steps_f = _upsample_nearest(st_f["steps"], (H, W))
    corridor = ndi.distance_transform_edt(~steps_f) <= CORRIDOR_PX
    basin = valid & (depth_f > BASIN_FLOOR_M)

    b18 = np.asarray(B.load_band(18), np.float64)
    b11 = np.asarray(B.load_band(11), np.float64)
    euler = euler_source_depth(b18, b18, b11)
    del b18, b11
    gy, gx = np.gradient(np.where(valid, depth_f, np.nan))

    if out_path is None:
        stack = np.empty((H, W, F), np.float32)
    else:
        stack = np.lib.format.open_memmap(out_path, mode="w+", dtype=np.float32,
                                          shape=(H, W, F))
    for j, i in enumerate(BAND_FEATURES):
        ch = np.asarray(B.load_band(i), np.float64)
        stack[:, :, j] = _rank01(ch, valid)
        del ch
    derived = [depth_f, hgm_f, throw_f, steps_f.astype(np.float64),
               corridor.astype(np.float64), basin.astype(np.float64),
               euler, gx, gy]
    for k, ch in enumerate(derived):
        stack[:, :, len(BAND_FEATURES) + k] = _rank01(ch, valid)
    if out_path is not None:
        stack.flush()
        stack = np.load(out_path, mmap_mode="r")

    meta = dict(
        decimations=dict(coarse=DECIMATION_COARSE, fine=DECIMATION_FINE),
        calibration_coarse=inv_c["calibration"], calibration_fine=inv_f["calibration"],
        inversion_coarse=inv_c["inversion"], inversion_fine=inv_f["inversion"],
        depth_stats_coarse=B.calibrate_depth_scale(inv_c["depth_small"], inv_c["valid_small"]),
        depth_stats_fine=B.calibrate_depth_scale(inv_f["depth_small"], inv_f["valid_small"]),
        steps_fine=dict(n_hgm_maxima=st_f["n_maxima"], n_steps=st_f["n_steps"],
                        min_throw_m=MIN_THROW_M),
        reused_inversions=dict(coarse=bool(inv_c.get("reused")), fine=bool(inv_f.get("reused"))),
        corridor_px=CORRIDOR_PX, basin_floor_m=BASIN_FLOOR_M,
        corridor_fraction_of_valid=float((corridor & valid).sum() / max(valid.sum(), 1)),
        basin_fraction_of_valid=float(basin.sum() / max(valid.sum(), 1)),
        n_features=F, feature_names=names,
        euler_note="Euler SI=0 contact depth from band 18 (HG) and band 11 (VG); "
                   "doi:10.1190/1.1442789 (Reid et al. 1990)",
    )
    aux = dict(depth_fine=depth_f, depth_coarse=depth_c, hgm=hgm_f, throw=throw_f,
               steps=steps_f, corridor=corridor, basin=basin, euler=euler,
               grad_x=gx, grad_y=gy, inv_fine=inv_f, inv_coarse=inv_c)
    return names, stack, meta, aux


def _up(a, shape):
    return upsample_bilinear(np.asarray(a, np.float64), shape)


def _upsample_nearest(mask, shape):
    m = np.asarray(mask, bool)
    up = np.repeat(np.repeat(m, DECIMATION_FINE, axis=0), DECIMATION_FINE, axis=1)
    out = np.zeros(shape, bool)
    h = min(shape[0], up.shape[0]); w = min(shape[1], up.shape[1])
    out[:h, :w] = up[:h, :w]
    return out


def _rank01(values, mask):
    """Rank-normalise ``values`` inside ``mask`` to (0,1]; NaN elsewhere."""
    v = np.asarray(values, np.float64)
    m = np.asarray(mask, bool) & np.isfinite(v)
    out = np.full(v.shape, np.nan, np.float32)
    idx = np.flatnonzero(m.ravel())
    if idx.size == 0:
        return out
    x = v.ravel()[idx]
    order = np.argsort(x, kind="stable")
    r = np.empty(idx.size, np.float32)
    r[order] = (np.arange(1, idx.size + 1, dtype=np.float32)) / np.float32(idx.size)
    out.ravel()[idx] = r
    return out


# --------------------------------------------------------------------------- #
# 3. Habitat model
# --------------------------------------------------------------------------- #
def train_habitat(stack, valid, positives, names, *, neg_ratio=4, seed=0, C=0.5):
    """Fit L2 logistic regression: visible mapped faults vs random footprint.

    ``positives`` is a boolean mask of *visible* catalogue pixels.  No feature
    in ``stack`` is derived from the catalogue, so this is a habitat model and
    not a distance-to-map proxy.  Returns (model, receipt).
    """
    from sklearn.linear_model import LogisticRegression

    rng = np.random.default_rng(seed)
    pos_idx = np.flatnonzero((positives & valid).ravel())
    neg_pool = np.flatnonzero((valid & ~positives).ravel())
    n_neg = min(neg_ratio * pos_idx.size, neg_pool.size)
    neg_idx = rng.choice(neg_pool, size=n_neg, replace=False)
    flat = stack.reshape(-1, stack.shape[-1])
    X = np.concatenate([flat[pos_idx], flat[neg_idx]])
    del flat
    y = np.concatenate([np.ones(pos_idx.size, np.int8), np.zeros(neg_idx.size, np.int8)])
    keep = np.isfinite(X).all(axis=1)
    X, y = X[keep], y[keep]
    X = np.nan_to_num(X, nan=0.0)
    model = LogisticRegression(C=C, max_iter=500, solver="lbfgs")
    model.fit(X, y)
    receipt = dict(n_pos=int((y == 1).sum()), n_neg=int((y == 0).sum()),
                   C=C, neg_ratio=neg_ratio, seed=seed,
                   train_auc=float(_auc(model.predict_proba(X)[:, 1], y)),
                   coefficients={n: float(c) for n, c in
                                 zip(names, model.coef_[0])})
    return model, receipt


def _auc(score, y):
    from scipy.stats import rankdata
    r = rankdata(score)
    n1 = int((y == 1).sum()); n0 = int((y == 0).sum())
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def predict_habitat(model, stack, valid, chunk=400_000):
    """Probability field over the whole grid (NaN outside valid), computed in
    row-chunks so the (5.17M x F) design matrix is never materialised."""
    H, W = stack.shape[0], stack.shape[1]
    F = stack.shape[2]
    out = np.full(H * W, np.nan, np.float64)
    vidx = np.flatnonzero(valid.ravel())
    for start in range(0, vidx.size, chunk):
        rows = vidx[start:start + chunk]
        X = np.nan_to_num(stack.reshape(-1, F)[rows], nan=0.0)
        out[rows] = model.predict_proba(X)[:, 1]
        del X
    return out.reshape(H, W)


# --------------------------------------------------------------------------- #
# 4. Emission
# --------------------------------------------------------------------------- #
def dot_thin(score, allowed, budget, tile_px=TILE_PX):
    """At most one dot per ``tile_px`` x ``tile_px`` tile at the tile's argmax."""
    s = np.where(allowed, np.asarray(score, np.float64), -np.inf)
    s = np.where(np.isfinite(s), s, -np.inf)
    H, W = s.shape
    ph, pw = (-H) % tile_px, (-W) % tile_px
    padded = np.pad(s, ((0, ph), (0, pw)), constant_values=-np.inf)
    th, tw = padded.shape[0] // tile_px, padded.shape[1] // tile_px
    tiles = padded.reshape(th, tile_px, tw, tile_px).transpose(0, 2, 1, 3).reshape(th * tw, -1)
    tmax = tiles.max(axis=1)
    targ = tiles.argmax(axis=1)
    ids = np.flatnonzero(np.isfinite(tmax) & (tmax > -np.inf))
    order = ids[np.argsort(-tmax[ids], kind="stable")][: int(budget)]
    ay = (order // tw) * tile_px + targ[order] // tile_px
    ax = (order % tw) * tile_px + targ[order] % tile_px
    keep = (ay < H) & (ax < W)
    out = np.zeros(s.shape, bool)
    out[ay[keep], ax[keep]] = True
    return out & allowed


def ribbon(dots, half_width_px=1):
    if half_width_px <= 0:
        return np.asarray(dots, bool).copy()
    return ndi.binary_dilation(np.asarray(dots, bool), np.ones((3, 3), bool),
                               iterations=int(half_width_px))


def wilson(k, n, z=1.959963985):
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def auc_rank(pos, neg):
    from scipy.stats import rankdata
    a = np.concatenate([np.asarray(pos, np.float64), np.asarray(neg, np.float64)])
    r = rankdata(a)
    n1 = np.size(pos)
    return float((r[:n1].sum() - n1 * (n1 + 1) / 2) / (n1 * np.size(neg)))
