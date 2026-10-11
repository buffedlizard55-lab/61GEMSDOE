#!/usr/bin/env python3
"""Experiment 1 - Parker-Oldenburg basement inversion + basement-step surface.

Caches the inversion products so later experiments do not pay the FFT cost again.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import io as gio                      # noqa: E402
from gems61.basement_steps import invert_basement  # noqa: E402
from gems61.parker_oldenburg import BOUGUER        # noqa: E402

# --- calibration constants (see evidence/calibration.json) -------------------
DRHO = 222.0        # kg/m^3, from the g-vs-basin-depth regression (see below)
Z0 = 600.0          # m, the value at which the inverted depth has zero offset
                    #    against the regional basin-depth layer
CUTOFF_M = 2500.0   # low-pass cutoff wavelength, m
SIGMA_REG = 100.0   # px (10 km) - regional tilt / basin sag removed
SIGMA_STEP = 3.0    # px (300 m) - the gravity resolution floor


def main() -> int:
    raise SystemExit("RETIRED: Retired historical inversion: it calibrated against organizer band 15. GP-1012 alone is permitted for depth-scale calibration.")
    t0 = time.time()
    grid = gio.load_grid(verify=True)
    g = np.asarray(grid.band("isostatic_gravity_anomaly"), dtype=np.float32)
    ref = np.asarray(grid.band("depth_to_basement_surface"), dtype=np.float32)
    valid = grid.footprint & np.isfinite(g)

    # --- density-contrast calibration against the regional basin-depth layer ---
    m = valid & np.isfinite(ref) & (ref >= 0) & (ref < 6000)
    slope, intercept = np.polyfit(ref[m][::7], g[m][::7], 1)
    drho_fit = abs(slope) / BOUGUER
    rep = dict(
        regression=dict(slope_mgal_per_m=float(slope), intercept_mgal=float(intercept),
                        n=int(m.sum()), pearson=float(np.corrcoef(ref[m][::7], g[m][::7])[0, 1]),
                        drho_from_regression_kg_m3=float(drho_fit)),
        chosen=dict(drho=DRHO, z0=Z0, cutoff_m=CUTOFF_M, sigma_reg=SIGMA_REG,
                    sigma_step=SIGMA_STEP, n_iter=4, order=3),
    )

    out = ROOT / "data" / "cache" / f"basement_z{int(Z0)}_dr{int(DRHO)}.npz"
    if out.exists():
        z = np.load(out)
        relief, depth, depth_hp, hgm = z["relief"], z["depth"], z["depth_hp"], z["hgm"]
        log = json.loads(str(z["log"]))
        print("cached inversion loaded", out.name)
    else:
        t = time.time()
        r = invert_basement(g, valid, z0=Z0, drho=DRHO, cutoff_m=CUTOFF_M,
                            sigma_reg=SIGMA_REG, sigma_step=SIGMA_STEP,
                            n_iter=4, order=3)
        relief, depth, depth_hp, hgm = r.relief, r.depth, r.depth_hp, r.hgm
        log = r.po.log
        np.savez_compressed(out, relief=relief.astype(np.float32),
                            depth=depth.astype(np.float32),
                            depth_hp=depth_hp.astype(np.float32),
                            hgm=hgm.astype(np.float32), log=json.dumps(log))
        print(f"inversion done in {time.time()-t:.1f}s -> {out.name}")
    rep["inversion_log"] = log
    rep["seconds_total"] = time.time() - t0

    # --- descriptive statistics of the inverted surface -----------------------
    f = valid
    rep["stats"] = dict(
        depth=dict(mean=float(depth[f].mean()), std=float(depth[f].std()),
                   p1=float(np.percentile(depth[f], 1)), p99=float(np.percentile(depth[f], 99))),
        depth_hp=dict(std=float(depth_hp[f].std()),
                      p1=float(np.percentile(depth_hp[f], 1)),
                      p99=float(np.percentile(depth_hp[f], 99))),
        hgm=dict(mean=float(hgm[f].mean()), std=float(hgm[f].std()),
                 p90=float(np.percentile(hgm[f], 90)),
                 p99=float(np.percentile(hgm[f], 99)),
                 max=float(hgm[f].max())),
    )
    # agreement of the inverted depth with the regional layer, at full footprint
    from scipy.stats import spearmanr
    idx = np.flatnonzero((valid & np.isfinite(ref)).ravel())[::7]
    rep["stats"]["spearman_depth_vs_regional"] = float(
        spearmanr(depth.ravel()[idx], ref.ravel()[idx]).statistic)
    (ROOT / "evidence" / "e1_calibration.json").write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep["stats"], indent=2))
    print(f"total {rep['seconds_total']:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
