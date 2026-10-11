#!/usr/bin/env python3
"""RETIRED historical holdout leakage-canary experiment.

The candidate did not pass the current pre-placement gate and the aggregate
experiment budget is exhausted. Existing canary evidence is retained; the CLI is
disabled to prevent new holdout scores from being produced out of protocol.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import io as gio           # noqa: E402
from gems61 import holdout as ho       # noqa: E402
from scipy import ndimage              # noqa: E402

Z0, DRHO = 600, 222


def main() -> int:
    grid = gio.load_grid(verify=True)
    z = np.load(ROOT / "data" / "cache" / f"basement_z{Z0}_dr{DRHO}.npz")
    depth, depth_hp, hgm = z["depth"], z["depth_hp"], z["hgm"]
    folds = ho.make_folds(grid.footprint, grid.catalogue, n_folds=4, collar_px=3, min_px=20)
    truth = np.zeros_like(grid.footprint)
    domain = np.zeros_like(grid.footprint)
    for f in folds:
        truth |= f.hidden & f.domain
        domain |= f.domain
    out = dict(n_truth=int(truth.sum()), n_domain=int(domain.sum()), auc={})
    for name in grid.names:
        b = np.asarray(grid.band(name), dtype=np.float64)
        out["auc"]["band:" + name] = ho.auc(np.where(domain, b, np.nan), truth,
                                            n_bg=300000, seed=1)
    out["auc"]["derived:basement_depth_inverted"] = ho.auc(
        np.where(domain, depth, np.nan), truth, 300000, 1)
    out["auc"]["derived:basement_depth_hp"] = ho.auc(
        np.where(domain, depth_hp, np.nan), truth, 300000, 1)
    out["auc"]["derived:basement_step_hgm_sg3"] = ho.auc(
        np.where(domain, hgm, np.nan), truth, 300000, 1)
    s5 = ndimage.gaussian_filter(depth_hp, 5.0, mode="nearest")
    gy, gx = np.gradient(s5, 100.0)
    out["auc"]["derived:basement_step_hgm_sg5"] = ho.auc(
        np.where(domain, np.hypot(gx, gy), np.nan), truth, 300000, 1)
    out["auc"]["provided:band15_depth_to_basement"] = out["auc"][
        "band:depth_to_basement_surface"]
    out["max_auc"] = max(out["auc"].values())
    out["max_auc_key"] = max(out["auc"], key=out["auc"].get)
    out["threshold"] = 0.90
    out["leakage_detected"] = bool(out["max_auc"] > 0.90)
    (ROOT / "evidence" / "e2c_canary.json").write_text(json.dumps(out, indent=2))
    for k, v in sorted(out["auc"].items(), key=lambda kv: -abs(kv[1] - 0.5)):
        print(f"{k:52s} AUC={v:.4f}")
    print("max", out["max_auc_key"], round(out["max_auc"], 4),
          "leakage:", out["leakage_detected"])
    return 0


if __name__ == "__main__":
    raise SystemExit(
        "Retired: the current candidate failed pre-placement; do not run another "
        "holdout canary or produce a score outside the gate."
    )
