#!/usr/bin/env python3
"""E1 - calibrate a surrogate truth ("instrument") that reproduces the LIVE ordering.

Why this exists
---------------
The catalogue-frame hide-and-recover holdout shipped with this template is measured
to be ANTI-correlated with the live board (rho = -0.93, ``evidence/e2b_instrument.json``,
irregularity ``IR-57-INSTR-01``).  The reason is now documented from the official
problem page (fetched 2026-10-11,
https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/):

    "the sponsors have compiled a set of newly identified faults in the GeoDAWN
     region that are NOT INCLUDED IN THE EXISTING USGS fault database.  These new
     faults have been manually labeled by fault experts and comprise the test
     dataset for the competition."

So the live truth G is DISJOINT from the visible catalogue.  A holdout that hides
segments of the visible catalogue and rewards dots placed on them is scoring the
opposite of the live target.  This script builds an instrument that respects that
fact: the surrogate truth lives only in the ELIGIBLE area (footprint, >= 3 px from
the visible catalogue) and is weighted by a habitat law fitted on rasters whose
live scores are OWNER-REPORTED.

Method
------
For a binary dot field P and a surrogate truth density q (summing to N = |G|):

    T(q, P) = sum_x q(x) * max_{p in P} k(d(x, p))      (linear in q)
    M(q, P) = sum_{p in P} max_g k(d(p, g)) ~ sum_x q(x) * k_P(x)   (same surrogate)
    DTI     = T / (0.2*(T + n - M) + 0.8*N)

exactly the algebra in ``src/gems61/metric.py``.  Because T is linear in q we can
scan a one-parameter habitat family cheaply:

    q_gamma(x) propto depth_to_base_surf(x)^gamma   on the eligible area

gamma = 0 is "truth uniformly spread over the eligible area"; gamma > 0 pushes it
into deep basement (basin floor under alluvial cover).  We report, for each gamma,
the Spearman rank correlation between surrogate DTI and the owner-reported live
scores, plus a LEAVE-ONE-OUT check: the gamma chosen on 6 fields must also rank the
7th.  Nothing here is a leaderboard prediction for anyone; it calibrates a ruler.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import rasterio
from scipy import stats
from scipy.ndimage import distance_transform_edt

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = Path(os.environ.get("GEMS61_REGISTRY", "/tmp/refs/registry"))
OUT = ROOT / "evidence" / "e1_habitat_instrument.json"

ALPHA, BETA, R = 0.2, 0.8, 3.0

# Owner-reported live scores for registry rasters, copied from the GEMSDOE group's
# published submission pages (see README "Evidence classes").  The three 44090-dot
# entries below were measured BYTE-DISTINCT but with an IDENTICAL dot mask, so only
# one of them is kept as an independent observation.
LIVE = {
    "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif": 0.2778,
    "gems28-h36-1-rung30-blind-r1-20261003-b531dae0a36f-allfinite.tif": 0.2710,
    "gems28-h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc-allfinite.tif": 0.2708,
    "gems25-dotted-h19-5-d2-8-20261002-e56ea318af89-zeros.tif": 0.2600,
    "gems27-topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-allfinite.tif": 0.2449,
    "gems49-gate_ortho_w0.25-40k-20261006T213721Z-zeros.tif": 0.2376,
    "gemsdoe29-sgmc-off-catalogue-44k-20261003-c8dcd780e3fd-nan.tif": 0.0512,
}


def kernel(d):
    return np.maximum(1.0 - np.asarray(d, np.float64) / R, 0.0)


def load_fields():
    """Return {name: bool dot mask} for every registry raster with a live score."""
    fields = {}
    for name in LIVE:
        path = REGISTRY / name
        if not path.exists():
            raise FileNotFoundError(f"registry raster missing: {path} (run scripts/fetch_registry.sh)")
        a = np.nan_to_num(rasterio.open(path).read(1).astype(np.float64))
        fields[name] = a > 0
    return fields


def main() -> int:
    lab = rasterio.open(ROOT / "data/official/labels.tif").read(1)
    foot = lab >= 0
    cat = lab > 0.5
    dcat = distance_transform_edt(~cat)
    elig = foot & (dcat >= R)

    depth = np.load(ROOT / ".cache/features/band-15.npy")   # depth_to_base_surf, m
    if not np.isfinite(depth[foot]).any():
        raise ValueError("band 15 has no finite values inside the footprint")

    fields = load_fields()

    # Per-field: k_P(x) = max kernel credit an eligible pixel receives from field P,
    # and the field's own self-credit against the surrogate (same clipped convolution).
    kp = {n: kernel(distance_transform_edt(~(m & foot))) for n, m in fields.items()}
    n_dots = {n: int((m & foot).sum()) for n, m in fields.items()}

    elig_idx = np.nonzero(elig)
    dep_e = depth[elig_idx]
    dep_e = np.where(np.isfinite(dep_e), dep_e, 0.0)
    dep_e = np.clip(dep_e, 0.0, None)
    kp_e = {n: kp[n][elig_idx] for n in fields}
    dot_mask = {n: (m & foot) for n, m in fields.items()}
    dep_full = np.clip(np.where(np.isfinite(depth), depth, 0.0), 0.0, None)

    # kernel used for the dot self-credit convolution (the 29 offsets at R = 3)
    offs = [(j, i, float(kernel(np.hypot(j, i)))) for j in range(-3, 4) for i in range(-3, 4)
            if kernel(np.hypot(j, i)) > 0]

    gammas = np.round(np.arange(0.0, 1.61, 0.05), 3)
    rows = []
    H, W = depth.shape
    for g in gammas:
        w = dep_e ** g
        Z = w.sum()
        if Z <= 0:
            continue
        # N = |G| is unknown; DTI depends on N only through n/N, so scan it too.
        best = None
        for N in (30_000, 60_988, 120_000, 250_000, 500_000):
            # surrogate truth density: q on the full grid, zero outside the eligible area
            Q = np.zeros((H, W), np.float64)
            Q[elig_idx] = N * w / Z
            # dot self-credit = (q * kernel)(p), clipped at 1 (a dot cannot earn more than 1)
            Qk = np.zeros((H, W), np.float64)
            for j, i, k in offs:
                ys0, ys1 = max(0, j), min(H, H + j)
                xs0, xs1 = max(0, i), min(W, W + i)
                Qk[ys0:ys1, xs0:xs1] += Q[max(0, -j):min(H, H - j),
                                          max(0, -i):min(W, W - i)] * k
            dtis = []
            for n in fields:
                T = float((Q * kp[n]).sum())                       # exact: sum_x q(x) max_p k
                M = float(np.minimum(Qk[dot_mask[n]], 1.0).sum())  # clipped convolution surrogate
                dti = T / (ALPHA * (T + n_dots[n] - M) + BETA * N + 1e-12)
                dtis.append(dti)
            live = np.array([LIVE[n] for n in fields])
            rho, p = stats.spearmanr(dtis, live)
            rec = dict(gamma=float(g), N=int(N), rho=float(rho), p=float(p),
                       dti={n: round(d, 5) for n, d in zip(fields, dtis)})
            if best is None or rec["rho"] > best["rho"]:
                best = rec
        rows.append(best)

    rows.sort(key=lambda r: -r["rho"])
    top = rows[0]

    # ---- leave-one-out: pick gamma on 6 fields, check the 7th is ranked correctly
    loo = []
    names = list(fields)
    for held in names:
        sub = [n for n in names if n != held]
        bg, brho = None, -2.0
        for r in rows:
            d = np.array([r["dti"][n] for n in sub]); l = np.array([LIVE[n] for n in sub])
            rho = stats.spearmanr(d, l).statistic
            if np.isfinite(rho) and rho > brho:
                bg, brho = r, rho
        held_dti = bg["dti"][held]
        # how many of the 6 does the held-out field beat, vs how many should it beat?
        pred_rank = 1 + sum(1 for n in sub if bg["dti"][n] < held_dti)
        true_rank = 1 + sum(1 for n in sub if LIVE[n] < LIVE[held])
        loo.append(dict(held=held, live=LIVE[held], gamma=bg["gamma"], N=bg["N"],
                        fit_rho_on_6=round(float(brho), 4),
                        predicted_rank_among_7=pred_rank + (0 if pred_rank <= true_rank else 0),
                        true_rank_among_7=1 + sum(1 for n in names if LIVE[n] < LIVE[held]),
                        rank_error=abs(pred_rank - true_rank)))
    loo_mae = float(np.mean([r["rank_error"] for r in loo]))
    loo_exact = int(sum(1 for r in loo if r["rank_error"] == 0))

    rep = dict(
        evidence_class="MEASURED on registry bytes; live scores are OWNER-REPORTED",
        purpose="calibrate a surrogate truth that reproduces the LIVE ordering, because the "
                "catalogue-frame holdout is measured anti-correlated with live (IR-57-INSTR-01)",
        official_basis="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/ "
                       "- test set is 'newly identified faults ... NOT INCLUDED IN THE EXISTING "
                       "USGS fault database', so the live truth is disjoint from the visible catalogue",
        eligible_pixels=int(elig.sum()),
        footprint_pixels=int(foot.sum()),
        catalogue_pixels=int(cat.sum()),
        habitat_layer="band 15 depth_to_base_surf (m), q ~ depth^gamma on the eligible area",
        n_registry_fields=len(fields),
        best=dict(gamma=top["gamma"], N=top["N"], spearman_rho=round(top["rho"], 4),
                  p_value=top["p"], surrogate_dti=top["dti"],
                  live={n: LIVE[n] for n in fields}),
        gamma_scan_top10=[{k: v for k, v in r.items() if k != "dti"} for r in rows[:10]],
        leave_one_out=dict(rows=loo, mean_absolute_rank_error=loo_mae,
                           exact_rank_recoveries=f"{loo_exact}/{len(loo)}"),
        verdict=("instrument usable" if top["rho"] >= 0.80 and loo_mae <= 1.0
                 else "instrument NOT usable - do not promote on it"),
    )
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(rep, indent=1, allow_nan=False) + "\n")
    print(json.dumps({k: rep[k] for k in
                      ("eligible_pixels", "best", "leave_one_out", "verdict")}, indent=1)[:3000])
    print(f"\n[wrote] {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
