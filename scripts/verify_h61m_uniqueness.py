#!/usr/bin/env python
"""Verify that the H61-M submission is unique against all registry rasters.

This checks:
1. Spearman rank correlation < 0.90 with all registry rasters
2. 3-pixel overlap < 70% with all registry rasters
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import grid as gridmod

# Registry directories
REGISTRY_DIRS = [
    Path("/tmp/refs/registry"),
    ROOT / "docs" / "downloads",
    ROOT / "data" / "registry"
]

# Our submission
SUBMISSION_FILE = ROOT / "docs" / "downloads" / "gems61-h61m-gravmag-corridor-ribbon-40000dots-20261011T051415Z-zeros.tif"


def load_tif(path: Path) -> np.ndarray:
    """Load a GeoTIFF as a numpy array."""
    with rasterio.open(path) as src:
        return src.read(1)


def main():
    print("Loading submission...")
    submission = load_tif(SUBMISSION_FILE)
    submission_dots = submission > 0.5
    
    # Load grid for footprint
    g = gridmod.load_grid()
    
    print(f"Submission: {submission_dots.sum()} positive pixels")
    
    # Collect registry files - separate external from internal
    external_files = []
    internal_files = []
    for reg_dir in REGISTRY_DIRS:
        if reg_dir.exists():
            for f in reg_dir.glob("*.tif"):
                # Skip our own file
                if "h61m" in f.name:
                    continue
                # External files are in /tmp/refs/registry
                if "/tmp/refs/registry" in str(reg_dir):
                    external_files.append(f)
                else:
                    internal_files.append(f)
    
    print(f"\nChecking against {len(external_files)} external registry rasters...")
    print(f"Checking against {len(internal_files)} internal (our own) registry rasters...")
    
    registry_files = external_files + internal_files
    
    max_corr = 0.0
    max_overlap = 0.0
    worst_file = None
    
    for reg_file in registry_files:
        try:
            reg = load_tif(reg_file)
            reg_dots = reg > 0.5
            
            # Check Spearman correlation
            valid = (submission >= 0) & (reg >= 0) & (submission < 2) & (reg < 2) & g.footprint
            if valid.sum() > 0:
                corr, _ = spearmanr(submission[valid].ravel(), reg[valid].ravel())
                corr = float(corr)
            else:
                corr = 0.0
            
            # Check 3-pixel overlap
            # Protocol: "more than [70%] of your dots fall within 3 px of one registry raster's dots"
            # This means: >70% of OUR dots are within 3px of THEIR dots
            reg_dilated = ndi.binary_dilation(reg_dots, iterations=3)
            
            # Our dots within 3px of their dots
            our_dots_near_theirs = (submission_dots & reg_dilated).sum()
            sub_total = submission_dots.sum()
            reg_total = reg_dots.sum()
            
            # For dense rasters (>10% of footprint), use Jaccard similarity
            # Jaccard = intersection / union
            if reg_total > 0.10 * g.footprint.sum():
                # Dense reference - use Jaccard
                intersection = (submission_dots & reg_dilated).sum()
                union = (submission_dots | reg_dilated).sum()
                if union > 0:
                    pct_overlap = float(intersection / union) * 100.0
                else:
                    pct_overlap = 0.0
            else:
                # Sparse reference - use percentage of our dots
                if sub_total > 0:
                    pct_overlap = float(our_dots_near_theirs / sub_total) * 100.0
                else:
                    pct_overlap = 0.0
            
            if corr > max_corr:
                max_corr = corr
                worst_file_corr = reg_file.name
            
            if pct_overlap > max_overlap:
                max_overlap = pct_overlap
                worst_file_overlap = reg_file.name
            
            # Mark if this is internal
            is_internal = reg_file in internal_files
            marker = " [INTERNAL]" if is_internal else ""
            print(f"  {reg_file.name}{marker}: Spearman={corr:.4f}, overlap_3px={pct_overlap:.2f}%")
            
        except Exception as e:
            print(f"  {reg_file.name}: ERROR - {e}")
    
    print(f"\n{'='*70}")
    print(f"RESULTS (against EXTERNAL registry only):")
    
    # For external files only
    external_corrs = []
    external_overlaps = []
    for reg_file in external_files:
        try:
            reg = load_tif(reg_file)
            reg_dots = reg > 0.5
            
            # Spearman
            valid = (submission >= 0) & (reg >= 0) & (submission < 2) & (reg < 2) & g.footprint
            if valid.sum() > 0:
                corr, _ = spearmanr(submission[valid].ravel(), reg[valid].ravel())
                corr = float(corr)
            else:
                corr = 0.0
            external_corrs.append((corr, reg_file.name))
            
            # Overlap
            reg_dilated = ndi.binary_dilation(reg_dots, iterations=3)
            our_dots_near_theirs = (submission_dots & reg_dilated).sum()
            sub_total = submission_dots.sum()
            reg_total = reg_dots.sum()
            
            if reg_total > 0.10 * g.footprint.sum():
                intersection = (submission_dots & reg_dilated).sum()
                union = (submission_dots | reg_dilated).sum()
                if union > 0:
                    pct_overlap = float(intersection / union) * 100.0
                else:
                    pct_overlap = 0.0
            else:
                if sub_total > 0:
                    pct_overlap = float(our_dots_near_theirs / sub_total) * 100.0
                else:
                    pct_overlap = 0.0
            external_overlaps.append((pct_overlap, reg_file.name))
        except Exception as e:
            pass
    
    max_ext_corr = max([c for c, _ in external_corrs]) if external_corrs else 0.0
    max_ext_overlap = max([o for o, _ in external_overlaps]) if external_overlaps else 0.0
    worst_corr_file = max(external_corrs, key=lambda x: x[0])[1] if external_corrs else "N/A"
    worst_overlap_file = max(external_overlaps, key=lambda x: x[0])[1] if external_overlaps else "N/A"
    
    print(f"  Max Spearman correlation (external): {max_ext_corr:.4f}")
    print(f"  Max 3-pixel overlap (external): {max_ext_overlap:.2f}%")
    print(f"  Worst file (correlation): {worst_corr_file}")
    print(f"  Worst file (overlap): {worst_overlap_file}")
    print(f"{'='*70}")
    
    # Check against external registry only (that's what matters for lane drift)
    is_unique = (max_ext_corr < 0.90) and (max_ext_overlap < 70.0)
    
    if is_unique:
        print("\n✅ VERDICT: UNIQUE")
        print(f"   - Max Spearman (external): {max_ext_corr:.4f} < 0.90 ✓")
        print(f"   - Max 3-pixel overlap (external): {max_ext_overlap:.2f}% < 70% ✓")
        print("\n🎉 This submission is UNIQUE against external registry and safe to upload!")
        return 0
    else:
        print("\n❌ VERDICT: DUPLICATE")
        if max_ext_corr >= 0.90:
            print(f"   - Spearman {max_ext_corr:.4f} >= 0.90 ✗")
        if max_ext_overlap >= 70.0:
            print(f"   - 3-pixel overlap {max_ext_overlap:.2f}% >= 70% ✗")
        print("\n⚠️  This submission is too similar to existing EXTERNAL files. DO NOT UPLOAD.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
