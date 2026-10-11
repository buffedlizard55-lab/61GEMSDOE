#!/usr/bin/env python3
"""Cache the 19 competition feature bands into a memmap-able float32 array.

Source: data/raw/training_features.tif (sha256-pinned, see evidence/data_receipt.json).
Output: data/cache/bands.f32.npy  (H, W, 19) float32, NaN where the TIFF sentinel sits.
"""
from __future__ import annotations
import hashlib, json, pathlib, sys
import numpy as np
import rasterio

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "data/raw/training_features.tif"
OUT = ROOT / "data/cache/bands.f32.npy"
META = ROOT / "data/cache/bands_meta.json"


def sha256(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 22), b""):
            h.update(blk)
    return h.hexdigest()


def main() -> int:
    digest = sha256(SRC)
    expected = "4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5"
    if digest != expected:
        print(f"FATAL sha256 mismatch {digest}", file=sys.stderr)
        return 1
    with rasterio.open(SRC) as src:
        H, W, N = src.height, src.width, src.count
        sentinel = src.nodata
        names, cats, descs = [], [], []
        for i in range(1, N + 1):
            t = src.tags(i)
            descs.append(t.get("description", ""))
            cats.append(t.get("data_category", ""))
            names.append(descs[-1].split(" - ")[0].split(" (")[0].strip().lower().replace(" ", "_"))
        arr = np.lib.format.open_memmap(
            OUT, mode="w+", dtype=np.float32, shape=(H, W, N))
        for i in range(1, N + 1):
            b = src.read(i)
            b = np.where(b <= -1e38, np.nan, b).astype(np.float32)
            arr[:, :, i - 1] = b
            print(f"band {i:2d} {names[i-1]:28s} finite={int(np.isfinite(b).sum()):8d} "
                  f"min={np.nanmin(b):12.3f} max={np.nanmax(b):12.3f} "
                  f"mean={np.nanmean(b):10.3f}", flush=True)
        arr.flush()
        meta = dict(path=str(OUT.relative_to(ROOT)), shape=[H, W, N], names=names,
                    categories=cats, descriptions=descs, src_sha256=digest,
                    sentinel=float(sentinel), transform=list(src.transform)[:6],
                    crs=str(src.crs), nodata=float(src.nodata))
    META.write_text(json.dumps(meta, indent=2))
    print("wrote", OUT, OUT.stat().st_size, "bytes; meta", META)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
