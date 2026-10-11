#!/usr/bin/env python3
"""Calibrate the density-contrast depth scale of the Parker-Oldenburg inversion.

The lane prescribes the USGS Basin and Range basin-depth map (Saltus & Jachens,
USGS Geophysical Investigations Map GP-1012, 1:2,500,000, 1995) as the
calibration reference.  GP-1012 is **not** reachable from this sandbox: egress
is limited to github.com, api.github.com, codeload.github.com, registry.npmjs.org,
pypi.org and files.pythonhosted.org, and the USGS publication/ ScienceBase hosts
are outside that set.  The only basin-depth raster available locally is the
organiser's own band 15 ``depth_to_base_surf``; it is used here **only** to fix
the depth scale of the inversion, never as a prediction feature, and the
substitution is recorded in the receipt and the run card.

Both the inverted relief and the reference are reduced to *anomalies* by
removing a 6 km regional, because the inversion is band-limited and carries no
absolute datum.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import gravity as gv          # noqa: E402
from gems61 import grid as gd             # noqa: E402
from scipy.ndimage import gaussian_filter  # noqa: E402


def main() -> int:
    g = gd.load_grid()
    b15 = np.array(gd.load_band(15))
    cache = ROOT / ".cache"
    filled_path = cache / "b13_filled.npy"
    if filled_path.exists():
        filled = np.load(filled_path)
    else:
        b13 = np.array(gd.load_band(13))
        t0 = time.time()
        filled = gv.inpaint(np.where(np.isfinite(b13), b13, 0.0), np.isfinite(b13))
        np.save(filled_path, filled.astype(np.float32))
        print(f"[cal] inpainted in {time.time()-t0:.0f}s", flush=True)

    ref = gv.inpaint(np.where(np.isfinite(b15), b15, 0.0), np.isfinite(b15))
    ref_anom = (b15 - gaussian_filter(ref, 60.0, mode="nearest")).astype(np.float32)
    mask = g.footprint & np.isfinite(ref_anom) & np.isfinite(b15)

    rows = []
    t0 = time.time()
    for drho in (300.0, 400.0, 500.0, 650.0):
        for z0 in (750.0, 1250.0, 2000.0, 3000.0):
            for cutoff in (2000.0, 3000.0, 5000.0):
                relief, diag = gv.oldenburg_invert(
                    filled, drho, z0, 100.0, cutoff_wavelength_m=cutoff,
                    n_iter=15, n_terms=5, pad=96, return_diagnostics=True)
                depth = -relief.astype(np.float64)
                est_anom = (depth - gaussian_filter(depth, 60.0, mode="nearest")).astype(np.float32)
                fit = gv.robust_scale(ref_anom, est_anom, mask)
                fit.update(drho=float(drho), z0=float(z0), cutoff_wavelength_m=float(cutoff),
                           n_iter_done=diag["n_iter_done"],
                           last_update_m=float(diag["rms_update_m"][-1]),
                           relief_std_m=float(np.std(relief[mask])))
                fit["objective"] = float(abs(np.log(max(abs(fit["slope"]), 1e-6)))
                                         - fit["pearson"])
                rows.append(fit)
                print(f"[cal] drho={drho:5.0f} z0={z0:6.0f} lc={cutoff:6.0f} "
                      f"slope={fit['slope']:7.4f} pearson={fit['pearson']:+.4f} "
                      f"rmse={fit['rmse_m']:7.1f} obj={fit['objective']:+.4f} "
                      f"[{time.time()-t0:5.0f}s]", flush=True)
    rows.sort(key=lambda r: r["objective"])
    # Linear baseline: -gravity / (2 pi G drho) as a Bouguer slab, no inversion.
    lin = -(filled.astype(np.float64)) / (gv.TWO_PI_G * 400.0) * gv.MGal
    lin_anom = (lin - gaussian_filter(lin, 60.0, mode="nearest")).astype(np.float32)
    baseline = gv.robust_scale(ref_anom, lin_anom, mask)
    baseline["note"] = "Bouguer-slab baseline: -g/(2 pi G * 400 kg/m3), no iterative inversion"
    out = dict(evidence_class="MODEL-CALIBRATION",
               generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               reference_used="band 15 depth_to_base_surf (GP-1012 unreachable from this sandbox)",
               reference_intended=("Saltus, R.W. & Jachens, R.C., 1995, Gravity and basin-depth "
                                   "maps of the Basin and Range Province, western United States: "
                                   "USGS Geophysical Investigations Map GP-1012, scale 1:2,500,000"),
               regional_wavelength_m=6000.0,
               mask_pixels=int(mask.sum()),
               best=rows[0], grid_search=rows, linear_baseline=baseline)
    (ROOT / "evidence").mkdir(exist_ok=True)
    (ROOT / "evidence/depth_scale_calibration.json").write_text(
        json.dumps(out, indent=2, allow_nan=False) + "\n")
    print("[cal] BEST", json.dumps(rows[0], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
