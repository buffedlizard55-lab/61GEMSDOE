"""Grid, footprint, catalogue and band access for the 61GEMSDOE lane.

Every raster touched here is hash-pinned in ``evidence/data_receipt.json``.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
from dataclasses import dataclass

import numpy as np
import rasterio

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" if (ROOT / "data" / "raw").exists() else ROOT / "data" / "official"
CACHE = ROOT / "data" / "cache"

FEATURES_TIF = RAW / "training_features.tif"
LABELS_TIF = RAW / "existing_faults.tif"
TEMPLATE_TIF = RAW / "example_submission.tif" if (RAW / "example_submission.tif").exists() else RAW / "sample_submission.tif"

PINS = {
    "training_features.tif": "4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5",
    "existing_faults.tif": "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    "example_submission.tif": "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc",
}

RES = 100.0  # metres per pixel, verified from the template transform


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 22), b""):
            h.update(blk)
    return h.hexdigest()


def verify_pins() -> dict:
    out = {}
    for name, pin in PINS.items():
        p = RAW / name
        out[name] = dict(exists=p.exists(), sha256=sha256(p) if p.exists() else None,
                         pin=pin, ok=p.exists() and sha256(p) == pin,
                         bytes=p.stat().st_size if p.exists() else 0)
    return out


@dataclass
class Grid:
    """The competition grid: footprint mask, catalogue mask, band cache."""

    height: int
    width: int
    footprint: np.ndarray  # bool, template-finite pixels (the scoring domain)
    catalogue: np.ndarray  # bool, USGS/INGENIOUS fault pixels (masked from scoring)
    bands: np.ndarray  # (H, W, 19) float32 memmap, NaN where the TIFF sentinel sits
    names: list[str]
    transform: tuple
    crs: str

    def band(self, name: str) -> np.ndarray:
        if name not in self.names:
            raise KeyError(f"unknown band {name!r}; have {self.names}")
        return np.asarray(self.bands[:, :, self.names.index(name)], dtype=np.float32)

    def index(self, name: str) -> int:
        return self.names.index(name)


def load_grid(verify: bool = True) -> Grid:
    meta = json.loads((CACHE / "bands_meta.json").read_text())
    bands = np.load(CACHE / "bands.f32.npy", mmap_mode="r")
    with rasterio.open(TEMPLATE_TIF) as src:
        tmpl = src.read(1)
        transform = tuple(src.transform)[:6]
        crs = str(src.crs)
        H, W = src.height, src.width
    with rasterio.open(LABELS_TIF) as src:
        lab = src.read(1)
    footprint = np.isfinite(tmpl)
    catalogue = lab == 1
    if verify:
        # the template NaN mask and the label nodata mask must be identical
        assert np.array_equal(~footprint, lab == -1), "template/label mask mismatch"
        pins = verify_pins()
        for k, v in pins.items():
            assert v["ok"], f"pin failure for {k}: {v}"
    return Grid(height=H, width=W, footprint=footprint, catalogue=catalogue,
                bands=bands, names=meta["names"], transform=transform, crs=crs)


def finite(grid: Grid, name: str) -> np.ndarray:
    """Footprint pixels where the band is finite (the sentinel sits on 3,061 of them)."""
    return grid.footprint & np.isfinite(grid.band(name))
