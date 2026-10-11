#!/usr/bin/env python3
"""Reverse-engineer the habitat of the group's highest-scoring published rasters.

Reads the published bytes of every registry raster that the group reports a score
for, and measures, for each one, where its dots sit relative to

  * the mapped catalogue (distance buckets),
  * every one of the 19 supplied feature bands (lift of the band mean at the dots
    over the footprint mean, plus a rank-based AUC of dot-vs-random),
  * the lane's own gravity-inversion products.

This is LEARNING FROM PUBLISHED BYTES (explicitly allowed by the standing brief);
nothing here is copied into a submission.  The output is the evidence for which
physical signature the high-scoring files actually encode.

Writes evidence/registry_habitat.json.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import buried as B            # noqa: E402
from gems61 import grid as gridmod        # noqa: E402
from gems61.metric import kernel          # noqa: E402

EVID = ROOT / "evidence"
CACHE = ROOT / ".cache" / "h61g"
REGISTRY_DIRS = [Path("/tmp/refs/registry"), ROOT / "docs" / "downloads"]

# Scores the group reports on its own pages.  These are owner reports, not
# organizer receipts (IR-61-SCORE-01); they are used only to ORDER the analysis.
CLAIMED = {
    "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif": 0.2778,
    "gemsdoe36-anderson-geothermal-pinn-38854-20261004T230000Z-9b9ea4e6-zeros.tif": 0.2750,
    "gemsdoe31-h27-4-solo-d28-20261004-8acb75e1-allfinite.tif": 0.2708,
    "gems28-h36-1-rung30-blind-r1-20261003-b531dae0a36f-allfinite.tif": 0.2710,
    "gems28-h38-1-hf-euler-r30-r1-20261003-56a9f473edc7-nan.tif": 0.2707,
    "gems28-h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc-allfinite.tif": 0.2708,
    "gems25-dotted-h19-5-d2-8-20261002-e56ea318af89-zeros.tif": 0.2600,
    "gemsdoe30-d28-poisson300m-offcat-44090-20261003T233156Z-91eae1ca.tif": 0.2600,
    "gemsdoe33-h33d-analog-tip-stepover-r30-20261004-cb490425926e.tif": 0.2632,
    "gemsdoe29-wormrank-d28-20261003-59dcaf6dd11d-zeros.tif": 0.2560,
    "gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif": 0.2477,
    "gems27-topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-allfinite.tif": 0.2449,
    "gems49-gate_ortho_w0.25-40k-20261006T213721Z-zeros.tif": 0.2376,
    "gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-allfinite.tif": 0.1922,
    "gems19-h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-allfinite.tif": 0.1894,
    "gems20-h20-1-sarnnpu-powerlaw-pi0363-tilt-wingcrack-20260930-be0e8f6b-allfinite.tif": 0.1890,
    "gems28-h32-1-prethin-tip-euler-d2-8-20261003-31e35eee884e-nan.tif": 0.2649,
    "gemsdoe29-sgmc-off-catalogue-44k-20261003-c8dcd780e3fd-nan.tif": 0.0512,
}


def sha256(p: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    t0 = time.time()
    g = gridmod.load_grid()
    fp = g.footprint
    cat = g.catalogue
    dcat = ndi.distance_transform_edt(~cat)
    kcat = kernel(dcat)

    meta = json.loads((ROOT / "data/cache/bands_meta.json").read_text())
    names = meta["names"]
    bands = np.load(ROOT / "data/cache/bands.f32.npy", mmap_mode="r")

    # ---- lane products (already computed by the previous session) ------------
    depth_full = np.load(CACHE / "depth_full.npy").astype(np.float64)
    hgm_full = np.load(CACHE / "hgm_full.npy").astype(np.float64)
    steps_full = np.load(CACHE / "steps_full.npy")

    # ---- collect registry rasters ------------------------------------------
    seen, files = set(), []
    for d in REGISTRY_DIRS:
        for p in sorted(d.glob("*.tif")):
            if p.name in seen:
                continue
            seen.add(p.name)
            files.append(p)
    rows = []
    rng = np.random.default_rng(11)
    neg_idx = np.flatnonzero(fp.ravel())
    neg_pick = rng.choice(neg_idx, size=200_000, replace=False)

    for p in files:
        try:
            with rasterio.open(p) as src:
                if (src.height, src.width) != g.shape:
                    continue
                a = src.read(1)
        except Exception as exc:  # noqa: BLE001
            print(f"  skip {p.name}: {exc}")
            continue
        a = np.nan_to_num(np.asarray(a, np.float64), nan=0.0, posinf=0.0, neginf=0.0)
        m = (a > 0.5) & fp
        n = int(m.sum())
        if n < 500:
            continue
        idx = np.flatnonzero(m.ravel())
        sub = rng.choice(idx, size=min(200_000, idx.size), replace=False)
        d = dcat.ravel()[sub]
        row = dict(
            file=p.name, sha256=sha256(p), claimed=CLAIMED.get(p.name), n_dots=n,
            frac_of_footprint=n / float(fp.sum()),
            on_catalogue=int((m & cat).sum()),
            median_dist_cat=float(np.median(d)),
            mean_kernel_cat=float(kcat.ravel()[sub].mean()),
            frac_within_3px=float((d <= 3).mean()),
            frac_within_10px=float((d <= 10).mean()),
            frac_gt_30px=float((d > 30).mean()),
        )
        # per-band lift: AUC of (dot value vs random footprint value) and mean lift
        band_rows = {}
        for i, nm in enumerate(names):
            v = np.asarray(bands[:, :, i], np.float64).ravel()
            pv = np.nan_to_num(v[sub], nan=0.0)
            nv = np.nan_to_num(v[neg_pick], nan=0.0)
            auc = float((rankdata(np.concatenate([pv, nv]))[: pv.size].sum()
                         - pv.size * (pv.size + 1) / 2) / (pv.size * nv.size))
            band_rows[nm] = dict(auc_vs_random=round(auc, 4),
                                 mean_at_dots=round(float(pv.mean()), 4),
                                 mean_footprint=round(float(nv.mean()), 4))
        row["bands"] = band_rows
        # lane products
        row["lane"] = dict(
            mean_inverted_depth_m=round(float(depth_full.ravel()[sub].mean()), 1),
            mean_inverted_depth_hgm=round(float(hgm_full.ravel()[sub].mean()), 4),
            frac_on_step_px=round(float(steps_full.ravel()[sub].mean()), 4),
            frac_depth_gt_300m=round(float((depth_full.ravel()[sub] > 300).mean()), 4),
        )
        rows.append(row)
        print(f"  {p.name[:64]:64s} n={n:7d} claimed={CLAIMED.get(p.name)} "
              f"dist_med={row['median_dist_cat']:.1f} kcat={row['mean_kernel_cat']:.4f}", flush=True)

    # ---- which bands separate the top scorers from the rest? ----------------
    top = [r for r in rows if r["claimed"] is not None and r["claimed"] >= 0.20]
    rest = [r for r in rows if r["claimed"] is not None and r["claimed"] < 0.20]
    contrast = {}
    if top and rest:
        for nm in names:
            t = np.mean([r["bands"][nm]["auc_vs_random"] for r in top])
            s = np.mean([r["bands"][nm]["auc_vs_random"] for r in rest])
            contrast[nm] = dict(top_mean_auc=round(t, 4), rest_mean_auc=round(s, 4),
                                separation=round(t - s, 4))
    out = dict(
        evidence_class="MEASURED (reverse engineering of published bytes; learning only)",
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        scope="every raster reachable in the group's public GitHub repos plus this repo's docs/downloads",
        n_rasters=len(rows), n_top=len(top), n_rest=len(rest),
        rows=rows, band_contrast_top_vs_rest=contrast,
        elapsed_s=round(time.time() - t0, 1),
    )
    EVID.mkdir(exist_ok=True)
    (EVID / "registry_habitat.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote evidence/registry_habitat.json  ({len(rows)} rasters, {time.time()-t0:.0f}s)")
    if contrast:
        print("\nband separation (top>=0.20 minus rest):")
        for nm, v in sorted(contrast.items(), key=lambda kv: -abs(kv[1]["separation"])):
            print(f"  {nm:34s} top={v['top_mean_auc']:.3f} rest={v['rest_mean_auc']:.3f} sep={v['separation']:+.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
