#!/usr/bin/env python3
"""Score every gems61* raster in docs/downloads on the H61-G segment holdout (same cells,
same evaluator) so the candidate board compares like with like.  Writes
evidence/h61g_siblings.json.  Files pruned against the FULL catalogue are structurally
disadvantaged here (IR-61-INSTR-02) -- the board says so next to each number."""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import numpy as np, rasterio
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import run_h61g as R  # noqa: E402

def main() -> None:
    g, grav, valid = R.load_base()
    ctx = R.holdoutmod.build_holdout(g, hide_frac=0.20, seeds=R.SEEDS, modes=("all",))
    rows = []
    for p in sorted((ROOT / "docs" / "downloads").glob("*.tif")):
        with rasterio.open(p) as src:
            if (src.height, src.width) != g.shape:
                continue
            a = src.read(1)
        m = np.isfinite(a) & (a > 0.5)
        parts = []
        for cell in ctx.cells:
            part, _ = R._score_crop(cell, m[cell.bbox]); parts.append(part)
        pooled = R._pool(parts)
        rows.append(dict(file=p.name, n_positive_px=int(m.sum()), pooled_dti=pooled["pooled_dti"],
                         ci95=R._boot_ci(parts), coverage=pooled["coverage"],
                         sha256=R.sha256(p)))
        print(f"  {p.name[:72]:72s} n={int(m.sum()):7d} HOLDOUT-DTI={pooled['pooled_dti']:.4f} CI{[round(x,4) for x in rows[-1]['ci95']]}", flush=True)
    R.write_json("h61g_siblings.json", dict(evidence_class="HOLDOUT-DTI", evaluator=R.EVALUATOR,
                 n_withheld_truth_px=int(sum(c.n_truth for c in ctx.cells)), rows=rows,
                 caveat="rasters pruned against the full catalogue cannot recover withheld catalogue segments (IR-61-INSTR-02)",
                 stamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))

if __name__ == "__main__":
    main()
