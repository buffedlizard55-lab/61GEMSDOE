#!/usr/bin/env python
"""Create a unique H61-M submission: gravity inversion corridors + magnetic edges.

This is a simplified, fast pipeline that:
1. Inverts gravity to find basement steps
2. Detects magnetic edges (TMI horizontal gradient maxima)
3. Finds magnetic edges within gravity-step corridors
4. Emits multi-line ribbons (3px width)
5. Validates and writes the GeoTIFF

Expected runtime: ~2-3 minutes on CPU.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import buried as B
from gems61 import grid as gridmod
from gems61 import h61m as H
from gems61 import submission_writer

EVID = ROOT / "evidence"
DOWNLOADS = ROOT / "docs" / "downloads"

# Parameters
BUDGET = 40000
CORRIDOR_PX = 10
RIBBON_WIDTH = 1
PRUNE_PX = 2.0
MAG_BAND = 3
MAG_SMOOTH_PX = 2.0


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main():
    start = time.time()
    print("Loading data...", flush=True)
    
    # Load grid and data
    g = gridmod.load_grid()
    grav = np.asarray(B.load_band(13), np.float64)  # isostatic gravity
    mag = np.asarray(B.load_band(MAG_BAND), np.float64)  # TMI
    catalogue = np.asarray(B.load_band(1), np.float64) > 0.5
    
    valid = g.footprint & np.isfinite(grav) & np.isfinite(mag)
    
    print(f"Data loaded in {time.time()-start:.2f}s", flush=True)
    print(f"Grid: {g.shape}, Valid: {valid.sum()}, Catalogue: {catalogue.sum()}")
    
    # Step 1: Invert gravity
    print("Inverting gravity...", flush=True)
    invert_start = time.time()
    invert_result = H.invert_basement(grav, valid)
    depth_small = invert_result["depth_small"]
    dx = invert_result["dx"]
    print(f"Inversion done in {time.time()-invert_start:.2f}s", flush=True)
    print(f"Inversion: {invert_result['inversion']['stage']}")
    
    # Step 2: Find persistent basement steps
    print("Finding basement steps...", flush=True)
    persistent = H.persistent_steps(
        depth_small, 
        dx, 
        scales_px=(0.0, 2.0, 5.0),
        tol_px=(0, 2, 3),
        min_throw_m=H.MIN_THROW_M
    )
    steps_small = persistent["steps"]
    steps_full = H.to_full_grid(steps_small, g.shape)
    print(f"Found {persistent['n_steps']} persistent steps", flush=True)
    
    # Step 3: Find magnetic edges
    print("Finding magnetic edges...", flush=True)
    mag_result = H.magnetic_edges(mag, valid, smooth_px=MAG_SMOOTH_PX)
    mag_edges_full = mag_result["maxima"]
    mag_hgm = mag_result["hgm"]
    print(f"Found {mag_result['n_edges']} magnetic edges", flush=True)
    
    # Step 4: Create corridor around gravity steps
    print("Creating corridor...", flush=True)
    corridor = H.corridor_mask(steps_full, px=CORRIDOR_PX)
    print(f"Corridor covers {corridor.sum()} pixels", flush=True)
    
    # Step 5: Find magnetic edges in corridor
    mag_in_corridor = mag_edges_full & corridor
    print(f"Magnetic edges in corridor: {mag_in_corridor.sum()}", flush=True)
    
    # Step 6: Score by magnetic HGM
    score = np.where(mag_in_corridor, mag_hgm, 0.0)
    
    # Step 7: Create off-catalogue mask
    off_cat = ~ndi.binary_dilation(catalogue, iterations=int(PRUNE_PX))
    allowed = corridor & off_cat & valid
    
    # Step 8: Emit dots
    print("Emitting dots...", flush=True)
    dots = H.dot_thin(score, allowed, BUDGET, tile_px=3)
    ribbons = H.ribbon(dots, half_width_px=RIBBON_WIDTH)
    
    # Ensure ribbons are within footprint and valid
    ribbons = ribbons & g.footprint & valid
    
    print(f"Emitted {dots.sum()} dots, {ribbons.sum()} ribbon pixels", flush=True)
    
    # Step 9: Build GeoTIFF
    print("Building GeoTIFF...", flush=True)
    submission_array = ribbons.astype(np.float32)
    
    # Write to file first, then validate
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    name = f"gems61-h61m-gravmag-corridor-ribbon-{BUDGET}dots-{timestamp}-zeros"
    note = f"H61-M: gravity inversion corridor x magnetic edges; {BUDGET} dots as 3px ribbons; UNSCORED"
    
    tif_path = DOWNLOADS / f"{name}.tif"
    json_path = DOWNLOADS / f"{name}.json"
    
    # Write TIF using grid module
    from gems61.grid import write_submission
    write_result = write_submission(tif_path, submission_array, mode="zeros")
    print(f"Write result: {write_result}", flush=True)
    
    # Validate the written file
    from gems61.validate import validate, assert_submittable
    validate_result = validate(tif_path, footprint=g.footprint, catalogue=catalogue)
    print(f"Validation: {validate_result}", flush=True)
    
    try:
        assert_submittable(validate_result)
        print("All validation checks passed!", flush=True)
    except AssertionError as e:
        print(f"Validation failed: {e}", flush=True)
        sys.exit(1)
    
    # Write receipt
    receipt = {
        "submission_name": name,
        "note": note,
        "sha256": sha256_bytes(submission_array.tobytes()),
        "n_positive_px": int(ribbons.sum()),
        "n_dots": int(dots.sum()),
        "budget": BUDGET,
        "validation": validate_result,
        "timestamp": timestamp,
        "method": {
            "lane": "buried-structure",
            "gravity_band": 13,
            "magnetic_band": MAG_BAND,
            "corridor_px": CORRIDOR_PX,
            "ribbon_width_px": RIBBON_WIDTH,
            "prune_px": PRUNE_PX,
            "inversion": invert_result["inversion"],
            "calibration": invert_result["calibration"]["best"]
        }
    }
    json_path.write_text(json.dumps(receipt, indent=2) + "\n")
    
    # Write evidence
    EVID.mkdir(exist_ok=True)
    evidence = {
        "n_steps": persistent["n_steps"],
        "n_magnetic_edges": mag_result["n_edges"],
        "n_magnetic_edges_in_corridor": int(mag_in_corridor.sum()),
        "n_corridor_px": int(corridor.sum()),
        "n_dots_emitted": int(dots.sum()),
        "n_ribbon_px": int(ribbons.sum()),
        "inversion": invert_result["inversion"],
        "calibration": invert_result["calibration"]["best"],
        "validation": validate_result
    }
    (EVID / "h61m_submission.json").write_text(json.dumps(evidence, indent=2) + "\n")
    
    elapsed = time.time() - start
    print(f"\nDone! Total time: {elapsed:.2f}s", flush=True)
    print(f"\nSubmission file: {tif_path}", flush=True)
    print(f"Receipt: {json_path}", flush=True)
    print(f"\nSubmission name: {name}", flush=True)
    print(f"Note: {note}", flush=True)
    print(f"\nValidation: {validate_result.get('verdict', 'UNKNOWN')}", flush=True)
    print(f"Positive pixels: {int(ribbons.sum())}", flush=True)
    print(f"SHA256: {receipt['sha256']}", flush=True)
    
    # Print submission instructions
    print("\n" + "="*70)
    print("TO SUBMIT TO THE COMPETITION:")
    print("="*70)
    print(f"1. Download: {tif_path}")
    print(f"2. Go to: https://www.drivendata.org/competitions/306/competition-doe-gems/submit/")
    print(f"3. Upload: {tif_path.name}")
    print(f"4. Note: {note}")
    print("5. Click 'Submit'")
    print("="*70)


if __name__ == "__main__":
    main()
