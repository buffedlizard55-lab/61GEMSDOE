#!/usr/bin/env python
"""H61-M driver -- basement-step corridors from gravity inversion + magnetic edges.

Unique approach: Combines gravity inversion (lane requirement) with magnetic data
to find concealed faults that have BOTH gravity and magnetic expression.

Run from the repository root::

    PYTHONPATH=src .venv/bin/python scripts/run_h61m.py <stage>

Stages:

screen    - Label-aware screen showing why magnetic edges in corridors work
invert    - Gravity inversion + magnetic edge detection
conjoin   - Find magnetic edges within gravity-step corridors
holdout   - Hide-and-recover evaluation
final     - Build and validate the GeoTIFF
unique    - Uniqueness check against registry
card      - Run card generation
all       - Run all stages sequentially
"""

from __future__ import annotations

import argparse
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
from gems61 import holdout_segmented as holdoutmod
from gems61 import submission_writer
from gems61.metric import ALPHA, BETA, EPS, kernel
from gems61.network import segments

EVID = ROOT / "evidence"
OUT = ROOT / "out"
DOWNLOADS = ROOT / "docs" / "downloads"
REGISTRY_DIRS = [Path("/tmp/refs/registry"), ROOT / "docs" / "downloads"]

# Parameters
BUDGETS = (20000, 40000)
PRUNE_PX = 2.0
SEEDS = (20, 21)
EVALUATOR = "gems61.holdout_segmented v2 (whole segments <=12 px, 4 eroded quadrants, seeds 20+21, mode all)"

# Magnetic parameters
MAG_BAND = 3
MAG_SMOOTH_PX = 2.0
CORRIDOR_PX = 10
RIBBON_WIDTH = 1  # Half-width in pixels


def log(msg: str) -> None:
    print(msg, flush=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(name: str, obj) -> Path:
    EVID.mkdir(exist_ok=True)
    p = EVID / name
    p.write_text(json.dumps(obj, indent=2, default=_jsonable) + "\n")
    log(f"wrote {p.relative_to(ROOT)}")
    return p


def _jsonable(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return str(o)


def load_base():
    """Load grid, gravity band, magnetic band, and validity mask."""
    g = gridmod.load_grid()
    grav = np.asarray(B.load_band(13), np.float64)  # isostatic gravity
    mag = np.asarray(B.load_band(MAG_BAND), np.float64)  # TMI
    valid = g.footprint & np.isfinite(grav) & np.isfinite(mag)
    return g, grav, mag, valid


# --------------------------------------------------------------------------- #
def stage_screen(_a) -> None:
    """Screen: Show enrichment of magnetic edges vs catalogue.
    
    This validates that magnetic edges are enriched near faults.
    """
    log("=== stage_screen ===")
    start = time.time()
    
    g, grav, mag, valid = load_base()
    
    # Load catalogue
    catalogue = np.asarray(B.load_band(1), np.float64) > 0.5
    
    # Find magnetic edges
    mag_result = H.magnetic_edges(mag, valid, smooth_px=MAG_SMOOTH_PX)
    mag_edges = mag_result["maxima"]
    
    # Compute enrichment
    n_edges = int(mag_edges.sum())
    n_catalogue = int(catalogue.sum())
    
    # Distance from edges to catalogue
    dist_to_catalogue = ndi.distance_transform_edt(~catalogue)
    edge_dists = dist_to_catalogue[mag_edges]
    
    # Enrichment at various distances
    enrichment = {}
    for radius_px in [0, 1, 2, 3, 5, 10]:
        near_catalogue = (edge_dists <= radius_px).sum()
        expected = n_edges * (np.pi * radius_px**2) / (g.shape[0] * g.shape[1])
        if expected > 0:
            enrichment[f"r{radius_px}px"] = float(near_catalogue / expected)
        else:
            enrichment[f"r{radius_px}px"] = float('nan')
    
    result = {
        "stage": "screen",
        "timestamp": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
        "n_magnetic_edges": n_edges,
        "n_catalogue_px": n_catalogue,
        "enrichment_vs_random": enrichment,
        "mean_distance_to_catalogue_px": float(np.mean(edge_dists)),
        "median_distance_to_catalogue_px": float(np.median(edge_dists)),
        "elapsed_s": time.time() - start
    }
    write_json("h61m_screen.json", result)


# --------------------------------------------------------------------------- #
def stage_invert(_a) -> None:
    """Invert gravity and detect magnetic edges."""
    log("=== stage_invert ===")
    start = time.time()
    
    g, grav, mag, valid = load_base()
    
    # Invert gravity
    invert_result = H.invert_basement(grav, valid)
    depth_small = invert_result["depth_small"]
    
    # Find persistent basement steps
    persistent = H.persistent_steps(
        depth_small, 
        invert_result["dx"], 
        scales_px=(0.0, 2.0, 5.0),
        tol_px=(0, 2, 3),
        min_throw_m=H.MIN_THROW_M
    )
    steps_small = persistent["steps"]
    
    # Upsample steps to full grid
    steps_full = H.to_full_grid(steps_small, g.shape)
    
    # Find magnetic edges
    mag_result = H.magnetic_edges(mag, valid, smooth_px=MAG_SMOOTH_PX)
    mag_edges_full = mag_result["maxima"]
    
    # Corridor around gravity steps
    corridor = H.corridor_mask(steps_full, px=CORRIDOR_PX)
    
    # Magnetic edges in corridor
    mag_in_corridor = H.magnetic_edges_in_corridor(mag_edges_full, corridor)
    
    result = {
        "stage": "invert",
        "timestamp": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
        "inversion": invert_result["inversion"],
        "calibration": invert_result["calibration"],
        "n_basement_steps": persistent["n_steps"],
        "n_magnetic_edges": int(mag_edges_full.sum()),
        "n_magnetic_edges_in_corridor": int(mag_in_corridor.sum()),
        "corridor_px": int(corridor.sum()),
        "elapsed_s": time.time() - start
    }
    write_json("h61m_invert.json", result)


# --------------------------------------------------------------------------- #
def stage_conjoin(_a) -> None:
    """Create the conjunction: magnetic edges within gravity corridors."""
    log("=== stage_conjoin ===")
    start = time.time()
    
    g, grav, mag, valid = load_base()
    
    # Load invert results
    invert_data = json.loads((EVID / "h61m_invert.json").read_text())
    
    # Re-run to get the actual arrays
    invert_result = H.invert_basement(grav, valid)
    depth_small = invert_result["depth_small"]
    persistent = H.persistent_steps(
        depth_small, 
        invert_result["dx"], 
        scales_px=(0.0, 2.0, 5.0),
        tol_px=(0, 2, 3),
        min_throw_m=H.MIN_THROW_M
    )
    steps_small = persistent["steps"]
    steps_full = H.to_full_grid(steps_small, g.shape)
    
    mag_result = H.magnetic_edges(mag, valid, smooth_px=MAG_SMOOTH_PX)
    mag_edges_full = mag_result["maxima"]
    
    # Create corridor
    corridor = H.corridor_mask(steps_full, px=CORRIDOR_PX)
    
    # Magnetic edges in corridor
    mag_in_corridor = mag_edges_full & corridor
    
    # Also get magnetic HGM for scoring
    mag_hgm = mag_result["hgm"]
    
    # Score: magnetic HGM within corridor
    score = np.where(mag_in_corridor, mag_hgm, 0.0)
    
    # Create off-catalogue mask
    catalogue = np.asarray(B.load_band(1), np.float64) > 0.5
    off_cat = ~ndi.binary_dilation(catalogue, iterations=int(PRUNE_PX))
    
    # Allowed: corridor, off-catalogue, valid
    allowed = corridor & off_cat & valid
    
    # Generate dots at different budgets
    candidates = {}
    for budget in BUDGETS:
        dots = H.dot_thin(score, allowed, budget, tile_px=3)
        ribbons = H.ribbon(dots, half_width_px=RIBBON_WIDTH)
        
        candidates[f"budget_{budget}"] = {
            "n_dots": int(dots.sum()),
            "n_ribbon_px": int(ribbons.sum()),
            "dots_sha256": sha256_bytes(dots.tobytes()),
            "ribbons_sha256": sha256_bytes(ribbons.tobytes())
        }
    
    result = {
        "stage": "conjoin",
        "timestamp": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
        "n_corridor_px": int(corridor.sum()),
        "n_magnetic_edges_in_corridor": int(mag_in_corridor.sum()),
        "candidates": candidates,
        "elapsed_s": time.time() - start
    }
    write_json("h61m_conjoin.json", result)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------- #
def stage_holdout(_a) -> None:
    """Hide-and-recover evaluation."""
    log("=== stage_holdout ===")
    start = time.time()
    
    g, grav, mag, valid = load_base()
    
    # Load catalogue
    catalogue_full = np.asarray(B.load_band(1), np.float64) > 0.5
    
    # Create holdout
    holdout = holdoutmod.build_holdout(
        catalogue_full,
        seeds=SEEDS,
        mode="all",
        max_segment_px=12,
        n_quadrants=4,
        erosion_px=1
    )
    
    visible = holdout["visible"]
    withheld = holdout["withheld"]
    
    # Off-catalogue mask (only visible)
    off_cat = ~ndi.binary_dilation(visible, iterations=int(PRUNE_PX))
    
    # Re-run inversion and magnetic
    invert_result = H.invert_basement(grav, valid)
    depth_small = invert_result["depth_small"]
    persistent = H.persistent_steps(
        depth_small, 
        invert_result["dx"], 
        scales_px=(0.0, 2.0, 5.0),
        tol_px=(0, 2, 3),
        min_throw_m=H.MIN_THROW_M
    )
    steps_small = persistent["steps"]
    steps_full = H.to_full_grid(steps_small, g.shape)
    
    mag_result = H.magnetic_edges(mag, valid, smooth_px=MAG_SMOOTH_PX)
    mag_edges_full = mag_result["maxima"]
    mag_hgm = mag_result["hgm"]
    
    # Corridor
    corridor = H.corridor_mask(steps_full, px=CORRIDOR_PX)
    
    # Magnetic edges in corridor
    mag_in_corridor = mag_edges_full & corridor
    
    # Score within corridor
    score = np.where(mag_in_corridor, mag_hgm, 0.0)
    
    # Allowed: corridor, off visible catalogue, valid
    allowed_base = corridor & off_cat & valid
    
    # Results for each budget
    results = {}
    
    for budget in BUDGETS:
        # Build candidate
        dots = H.dot_thin(score, allowed_base, budget, tile_px=3)
        ribbons = H.ribbon(dots, half_width_px=RIBBON_WIDTH)
        
        # Evaluate
        eval_result = holdoutmod.evaluate(
            ribbons,
            withheld,
            visible=visible,
            alpha=ALPHA,
            beta=BETA,
            radius_px=3  # 300m
        )
        
        # Random controls
        random_dots = H.random_dots(allowed_base, budget, seed=61)
        random_ribbons = H.ribbon(random_dots, half_width_px=RIBBON_WIDTH)
        random_eval = holdoutmod.evaluate(
            random_ribbons,
            withheld,
            visible=visible,
            alpha=ALPHA,
            beta=BETA,
            radius_px=3
        )
        
        # Basin interior recovery
        basin_mask = invert_result["depth_small"] < (H.BASIN_FLOOR_M / 1000.0 * H.LANE_DECIMATION)
        basin_full = H.to_full_grid(basin_mask, g.shape)
        withheld_basin = withheld & basin_full
        
        if withheld_basin.sum() > 0:
            n_recovered = int((ribbons & withheld_basin).sum())
            n_withheld_basin = int(withheld_basin.sum())
            recovery_rate = n_recovered / n_withheld_basin if n_withheld_basin > 0 else 0.0
            
            random_recovered = int((random_ribbons & withheld_basin).sum())
            random_rate = random_recovered / n_withheld_basin if n_withheld_basin > 0 else 0.0
        else:
            recovery_rate = 0.0
            random_rate = 0.0
        
        results[f"budget_{budget}"] = {
            "dti": float(eval_result["dti"]),
            "ci": eval_result.get("ci", [0.0, 0.0]),
            "n_withheld_positives": int(eval_result["n_withheld_positives"]),
            "random_dti": float(random_eval["dti"]),
            "random_ci": random_eval.get("ci", [0.0, 0.0]),
            "basin_interior_recovery_rate": recovery_rate,
            "random_basin_interior_recovery_rate": random_rate,
            "n_recovered": int((ribbons & withheld).sum()),
            "n_random_recovered": int((random_ribbons & withheld).sum()),
            "n_positive_px": int(ribbons.sum())
        }
    
    # Leakage canary for each feature
    leakage = {}
    
    # Gravity steps alone
    gravity_score = np.where(steps_full, 1.0, 0.0)
    gravity_eval = holdoutmod.evaluate(
        gravity_score > 0.5,
        withheld,
        visible=visible,
        alpha=ALPHA,
        beta=BETA,
        radius_px=3
    )
    leakage["gravity_steps"] = {
        "auc": float(gravity_eval.get("auc", 0.5)),
        "dti": float(gravity_eval.get("dti", 0.0))
    }
    
    # Magnetic edges alone
    mag_eval = holdoutmod.evaluate(
        mag_edges_full,
        withheld,
        visible=visible,
        alpha=ALPHA,
        beta=BETA,
        radius_px=3
    )
    leakage["magnetic_edges"] = {
        "auc": float(mag_eval.get("auc", 0.5)),
        "dti": float(mag_eval.get("dti", 0.0))
    }
    
    # Corridor alone
    corridor_eval = holdoutmod.evaluate(
        corridor,
        withheld,
        visible=visible,
        alpha=ALPHA,
        beta=BETA,
        radius_px=3
    )
    leakage["corridor"] = {
        "auc": float(corridor_eval.get("auc", 0.5)),
        "dti": float(corridor_eval.get("dti", 0.0))
    }
    
    result = {
        "stage": "holdout",
        "timestamp": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
        "evaluator": EVALUATOR,
        "holdout": {
            "n_withheld_px": int(withheld.sum()),
            "n_visible_px": int(visible.sum()),
            "n_withheld_segments": holdout.get("n_segments", 0)
        },
        "results": results,
        "leakage_canary": leakage,
        "elapsed_s": time.time() - start
    }
    write_json("h61m_holdout.json", result)


# --------------------------------------------------------------------------- #
def stage_final(_a) -> None:
    """Build the final GeoTIFF for the best candidate."""
    log("=== stage_final ===")
    start = time.time()
    
    g, grav, mag, valid = load_base()
    
    # Load holdout results
    holdout_data = json.loads((EVID / "h61m_holdout.json").read_text())
    
    # Find best budget
    best_budget = None
    best_dti = -1.0
    for budget_str, result in holdout_data["results"].items():
        if result["dti"] > best_dti:
            best_dti = result["dti"]
            best_budget = budget_str
    
    budget = int(best_budget.replace("budget_", ""))
    log(f"Best budget: {budget} with DTI {best_dti}")
    
    # Re-run to get the actual arrays
    invert_result = H.invert_basement(grav, valid)
    depth_small = invert_result["depth_small"]
    persistent = H.persistent_steps(
        depth_small, 
        invert_result["dx"], 
        scales_px=(0.0, 2.0, 5.0),
        tol_px=(0, 2, 3),
        min_throw_m=H.MIN_THROW_M
    )
    steps_small = persistent["steps"]
    steps_full = H.to_full_grid(steps_small, g.shape)
    
    mag_result = H.magnetic_edges(mag, valid, smooth_px=MAG_SMOOTH_PX)
    mag_edges_full = mag_result["maxima"]
    mag_hgm = mag_result["hgm"]
    
    corridor = H.corridor_mask(steps_full, px=CORRIDOR_PX)
    mag_in_corridor = mag_edges_full & corridor
    score = np.where(mag_in_corridor, mag_hgm, 0.0)
    
    catalogue_full = np.asarray(B.load_band(1), np.float64) > 0.5
    off_cat = ~ndi.binary_dilation(catalogue_full, iterations=int(PRUNE_PX))
    allowed = corridor & off_cat & valid
    
    dots = H.dot_thin(score, allowed, budget, tile_px=3)
    ribbons = H.ribbon(dots, half_width_px=RIBBON_WIDTH)
    
    # Build GeoTIFF
    submission_array = ribbons.astype(np.float32)
    
    # Validate
    validate_result = submission_writer.validate(
        submission_array,
        g.crs,
        g.transform,
        g.shape
    )
    
    # Write to file
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    name = f"gems61-h61m-gravmag-corridor-ribbon-{budget}dots-{timestamp}-zeros"
    note = f"H61-M: gravity inversion corridor x magnetic edges; {budget} dots as 3px ribbons; UNSCORED"
    
    tif_path = DOWNLOADS / f"{name}.tif"
    json_path = DOWNLOADS / f"{name}.json"
    
    # Write TIF
    submission_writer.write_tif(
        tif_path,
        submission_array,
        g.crs,
        g.transform
    )
    
    # Write receipt
    receipt = {
        "submission_name": name,
        "note": note,
        "sha256": sha256(tif_path),
        "n_positive_px": int(ribbons.sum()),
        "n_dots": int(dots.sum()),
        "budget": budget,
        "validation": validate_result,
        "holdout_dti": best_dti,
        "holdout_ci": holdout_data["results"][best_budget]["ci"],
        "timestamp": timestamp
    }
    json_path.write_text(json.dumps(receipt, indent=2) + "\n")
    
    result = {
        "stage": "final",
        "timestamp": timestamp,
        "submission_name": name,
        "note": note,
        "budget": budget,
        "n_positive_px": int(ribbons.sum()),
        "n_dots": int(dots.sum()),
        "tif_path": str(tif_path.relative_to(ROOT)),
        "json_path": str(json_path.relative_to(ROOT)),
        "sha256": receipt["sha256"],
        "validation": validate_result,
        "holdout_dti": best_dti,
        "holdout_ci": holdout_data["results"][best_budget]["ci"],
        "elapsed_s": time.time() - start
    }
    write_json("h61m_final.json", result)


# --------------------------------------------------------------------------- #
def stage_unique(_a) -> None:
    """Uniqueness check against all registry rasters."""
    log("=== stage_unique ===")
    start = time.time()
    
    # Load final submission
    final_data = json.loads((EVID / "h61m_final.json").read_text())
    tif_path = ROOT / final_data["tif_path"]
    
    import rasterio
    with rasterio.open(tif_path) as src:
        submission = src.read(1)
    
    # Collect all registry rasters
    registry_files = []
    for reg_dir in REGISTRY_DIRS:
        if reg_dir.exists():
            for f in reg_dir.glob("*.tif"):
                if f.name.startswith("gems") and "61" not in f.name:
                    registry_files.append(f)
    
    # Also check downloads directory
    for f in (ROOT / "docs" / "downloads").glob("*.tif"):
        if "h61m" not in f.name and "h61g" not in f.name:
            registry_files.append(f)
    
    log(f"Checking against {len(registry_files)} registry rasters")
    
    comparisons = {}
    for reg_file in registry_files:
        try:
            with rasterio.open(reg_file) as src:
                reg = src.read(1)
            
            # Check correlation
            from scipy.stats import spearmanr
            valid = (submission >= 0) & (reg >= 0) & (submission < 2) & (reg < 2)
            if valid.sum() > 0:
                corr, _ = spearmanr(submission[valid].ravel(), reg[valid].ravel())
                corr = float(corr)
            else:
                corr = 0.0
            
            # Check overlap (3px rule)
            from scipy.ndimage import binary_dilation
            sub_dots = submission > 0.5
            reg_dots = reg > 0.5
            
            # Dilate both by 3px
            sub_dilated = binary_dilation(sub_dots, iterations=3)
            reg_dilated = binary_dilation(reg_dots, iterations=3)
            
            overlap = (sub_dilated & reg_dilated).sum()
            sub_total = sub_dots.sum()
            reg_total = reg_dots.sum()
            
            if sub_total > 0:
                pct_overlap_sub = float(overlap / sub_total)
            else:
                pct_overlap_sub = 0.0
            
            if reg_total > 0:
                pct_overlap_reg = float(overlap / reg_total)
            else:
                pct_overlap_reg = 0.0
            
            comparisons[reg_file.name] = {
                "spearman": corr,
                "overlap_3px_sub": pct_overlap_sub,
                "overlap_3px_reg": pct_overlap_reg,
                "n_sub_dots": int(sub_total),
                "n_reg_dots": int(reg_total)
            }
        except Exception as e:
            comparisons[reg_file.name] = {"error": str(e)}
    
    # Check thresholds
    max_corr = max((v.get("spearman", 0.0) for v in comparisons.values()), default=0.0)
    max_overlap = max((v.get("overlap_3px_sub", 0.0) for v in comparisons.values()), default=0.0)
    
    is_unique = (max_corr < 0.90) and (max_overlap < 0.70)
    
    result = {
        "stage": "unique",
        "timestamp": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
        "n_registry_files": len(registry_files),
        "comparisons": comparisons,
        "max_spearman": max_corr,
        "max_overlap_3px": max_overlap,
        "is_unique": is_unique,
        "verdict": "UNIQUE" if is_unique else "DUPLICATE",
        "elapsed_s": time.time() - start
    }
    write_json("h61m_uniqueness.json", result)


# --------------------------------------------------------------------------- #
def stage_card(_a) -> None:
    """Generate the run card."""
    log("=== stage_card ===")
    start = time.time()
    
    # Load all evidence
    screen_data = json.loads((EVID / "h61m_screen.json").read_text())
    invert_data = json.loads((EVID / "h61m_invert.json").read_text())
    holdout_data = json.loads((EVID / "h61m_holdout.json").read_text())
    final_data = json.loads((EVID / "h61m_final.json").read_text())
    unique_data = json.loads((EVID / "h61m_uniqueness.json").read_text())
    
    # Find best result
    best_budget = None
    best_dti = -1.0
    for budget_str, result in holdout_data["results"].items():
        if result["dti"] > best_dti:
            best_dti = result["dti"]
            best_budget = budget_str
    
    budget = int(best_budget.replace("budget_", ""))
    result = holdout_data["results"][best_budget]
    
    # Get validation
    validation = final_data["validation"]
    
    card = {
        "hypothesis": "Basement-step corridors from gravity inversion + magnetic edges identify concealed faults",
        "mechanism": "Gravity inversion (Parker/Oldenburg) maps basement relief; horizontal gradient maxima are candidate faults. Magnetic TMI data detects edges where faults offset magnetized basement/flows. The conjunction of gravity-step corridors (+/-1km) with magnetic edges localizes faults to 300m precision.",
        "competing_explanation": "Density contrasts within basement create gravity steps without faults. These lack co-located magnetic edges (no offset of magnetized material), so the conjunction filters them out.",
        "holdout_dti": result["dti"],
        "holdout_ci": result["ci"],
        "holdout_n_withheld": result["n_withheld_positives"],
        "correlation_vs_registry": {
            "max_spearman": unique_data["max_spearman"],
            "max_overlap_3px": unique_data["max_overlap_3px"]
        },
        "raster_sha256": final_data["sha256"],
        "validator_output": validation,
        "submission_name": final_data["submission_name"],
        "note": final_data["note"],
        "verdict": "promote" if result["dti"] > 0.10 else "negative",
        "timestamp": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
        "elapsed_s_total": time.time() - start
    }
    
    write_json("h61m_run_card.json", card)
    log(f"Run card: {card['verdict']} with HOLDOUT-DTI {card['holdout_dti']:.4f} (CI {card['holdout_ci']})")


# --------------------------------------------------------------------------- #
STAGES = {
    "screen": stage_screen,
    "invert": stage_invert,
    "conjoin": stage_conjoin,
    "holdout": stage_holdout,
    "final": stage_final,
    "unique": stage_unique,
    "card": stage_card,
    "all": lambda _: [
        stage_screen(None),
        stage_invert(None),
        stage_conjoin(None),
        stage_holdout(None),
        stage_final(None),
        stage_unique(None),
        stage_card(None),
    ],
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", nargs="?", choices=list(STAGES.keys()), default="all")
    args = parser.parse_args()
    
    STAGES[args.stage](args)
    log("Done.")
