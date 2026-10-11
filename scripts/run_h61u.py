#!/usr/bin/env python3
"""Run the frozen H61U-H1 band-13 basement-step experiment and controls once.

This driver consumes only band 13 for candidate construction. It does not read
organizer band 15. GP-1012 calibration is unavailable without the complete
official ``br_depth.xyz`` file, so the registered physical prior stays explicitly
uncalibrated. One primary arm, the HGM-only control, the matched random-line
control, and one synthetic intrabasement-density mimic constitute the single
registered experiment; no parameter sweep is performed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import buried as B  # noqa: E402
from gems61 import emission as EM  # noqa: E402
from gems61 import evaluate_holdout as EH  # noqa: E402
from gems61 import gp1012  # noqa: E402
from gems61 import grid as GRID  # noqa: E402
from gems61 import holdout as HO  # noqa: E402
from gems61 import submission_writer as SW  # noqa: E402
from gems61 import uniqueness as UQ  # noqa: E402

FACTOR = 4
Z0_M = 1000.0
DELTA_RHO = -400.0
DX_M = 400.0
FILTER_ORDER = 2.0
KC_SCALE = 1.0
APERTURES_M = (2000.0, 4000.0)
PERSISTENCE_MIN = 0.60
DEEP_QUANTILE = 0.60
HIDE_FRACTION = 0.20
CONTEXT_BUFFER_PX = 3
PRIMARY_BUDGET = 40000
MIN_SEPARATION_PX = 3
FOLD_SEED = 20261011
BOOTSTRAP_SEED = 520810
RANDOM_LINE_SEED = 20261012
BOOTSTRAP_DRAWS = 1000


def _log(message: str) -> None:
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}Z] {message}", flush=True)


def _json_safe(value):
    """Convert NumPy scalars and non-finite diagnostics to strict JSON values."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _block_mean(values: np.ndarray, known: np.ndarray, footprint: np.ndarray,
                factor: int = FACTOR):
    """Finite-value block mean and masks; trim only the ragged bottom/right edge."""
    a = np.asarray(values, np.float32)
    m = np.asarray(known, bool) & np.isfinite(a) & np.asarray(footprint, bool)
    fp = np.asarray(footprint, bool)
    h = (a.shape[0] // factor) * factor
    w = (a.shape[1] // factor) * factor
    blocks = a[:h, :w].reshape(h // factor, factor, w // factor, factor)
    masks = m[:h, :w].reshape(h // factor, factor, w // factor, factor)
    fp_blocks = fp[:h, :w].reshape(h // factor, factor, w // factor, factor)
    count = masks.sum(axis=(1, 3))
    total = np.where(masks, blocks, 0.0).sum(axis=(1, 3), dtype=np.float64)
    mean = np.divide(total, count, out=np.zeros_like(total), where=count > 0).astype(np.float32)
    return mean, (count > 0), fp_blocks.any(axis=(1, 3)), count.astype(np.uint8)


def _repeat_to_grid(values: np.ndarray, shape: tuple[int, int], factor: int = FACTOR,
                    fill: float = 0.0) -> np.ndarray:
    a = np.asarray(values)
    repeated = np.repeat(np.repeat(a, factor, axis=0), factor, axis=1)
    out = np.full(shape, fill, dtype=a.dtype)
    h, w = min(shape[0], repeated.shape[0]), min(shape[1], repeated.shape[1])
    out[:h, :w] = repeated[:h, :w]
    return out


def _centres_to_grid(mask: np.ndarray, shape: tuple[int, int], factor: int = FACTOR) -> np.ndarray:
    """Place each 400 m crest at its 100 m cell-centre before 3 px dilation."""
    m = np.asarray(mask, bool)
    out = np.zeros(shape, bool)
    ys = np.arange(m.shape[0], dtype=np.int64) * factor + factor // 2
    xs = np.arange(m.shape[1], dtype=np.int64) * factor + factor // 2
    good_y, good_x = ys < shape[0], xs < shape[1]
    if good_y.any() and good_x.any():
        out[np.ix_(ys[good_y], xs[good_x])] = m[np.ix_(good_y, good_x)]
    return out


def _ribbon(centres: np.ndarray) -> np.ndarray:
    return ndi.binary_dilation(np.asarray(centres, bool), structure=np.ones((3, 3), bool), iterations=1)


def _paired_wilson(k: int, n: int, z: float = 1.959963984540054) -> list[float]:
    if n <= 0:
        return [0.0, 0.0]
    p = k / n
    den = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [float(max(0.0, center - half)), float(min(1.0, center + half))]


def _score_arm(dots: np.ndarray, folds: list[HO.Fold], footprint: np.ndarray):
    block_terms = []
    by_fold = {}
    for fold in folds:
        info, terms = EH.evaluate(dots.astype(np.float32), fold, footprint,
                                  block_side=HO.BLOCK_SIDE_PX,
                                  origin=(0, 0), global_shape=footprint.shape)
        block_terms.append(terms)
        by_fold[fold.name] = dict(
            evidence_class="HOLDOUT-DTI", evaluator_version=EH.VERSION,
            dti=float(info["dti"]), withheld_positive_count=int(info["withheld_positive_count"]),
            ci95=None, metric_scope="fold diagnostic; pooled spatial-block CI is authoritative")
    pooled_terms = np.sum(np.stack(block_terms, axis=0), axis=0)
    return pooled_terms, by_fold


def _run_density_mimic() -> dict:
    """Frozen finite-sheet non-fault control; no basement relief is introduced."""
    shape = (512, 512)
    body = np.zeros(shape, bool)
    body[220:292, 252:260] = True  # 28.8 km x 3.2 km at 400 m cells
    g_sheet = B.buried_density_sheet_gravity(
        body, density_contrast_kg_m3=250.0, thickness_m=1500.0,
        depth_m=2500.0, dx=DX_M)
    valid = np.ones(shape, bool)
    inversion = B.slab_solution(g_sheet, valid, delta_rho=DELTA_RHO,
                                z0=Z0_M, dx=DX_M,
                                filter_order=FILTER_ORDER, kc_scale=KC_SCALE)
    depth = np.asarray(inversion["depth_m"], np.float32)
    hgm = B.horizontal_gradient_magnitude(depth, dx=DX_M)
    maxima = B.blakely_simpson_maxima(hgm) & valid
    flank = B.signed_flank_persistence(depth, dx=DX_M,
                                       apertures_m=APERTURES_M,
                                       valid=valid, maxima=maxima)
    filtered = maxima & flank["same_sign"] & (flank["persistence"] >= PERSISTENCE_MIN)
    return dict(
        evidence_class="SYNTHETIC-NONFAULT-MIMIC-CONTROL",
        forward_operator="thin buried density sheet; periodic FFT; no fault displacement or basement relief",
        grid_shape_cells=list(shape), grid_spacing_m=DX_M,
        sheet_geometry_cells="rows 220:292, columns 252:260; centered finite sheet",
        sheet_dimensions_m=[28800.0, 3200.0],
        density_contrast_kg_m3=250.0, thickness_m=1500.0, burial_depth_m=2500.0,
        basement_relief_m=0.0,
        gravity_min_mgal=float(np.min(g_sheet)), gravity_max_mgal=float(np.max(g_sheet)),
        gravity_rms_mgal=float(np.sqrt(np.mean(g_sheet.astype(np.float64) ** 2))),
        inversion_prior=dict(z0_m=Z0_M, delta_rho_kg_m3=DELTA_RHO,
                             dx_m=DX_M, filter_order=FILTER_ORDER, kc_scale=KC_SCALE),
        hgm_maxima_centres=int(maxima.sum()),
        same_sign_persistence_survivors=int(filtered.sum()),
        retention_fraction=float(filtered.sum() / max(int(maxima.sum()), 1)),
        persistence_threshold=PERSISTENCE_MIN, apertures_m=list(APERTURES_M),
        dti_computed=False,
        dti_reason="The synthetic sheet has no fault truth; this is a false-positive mechanism control, not a score.",
        limitation="A finite sheet is one named non-fault mimic, not a complete model of intrabasement geology.")


def _experiment() -> dict:
    started = time.time()
    grid = GRID.load_grid()
    footprint = np.asarray(grid.footprint, bool)
    catalogue = np.asarray(grid.catalogue, bool)
    gravity = np.asarray(B.load_band(13), np.float32)
    if gravity.shape != footprint.shape:
        raise ValueError("band-13 cache does not match the pinned grid")
    known = footprint & np.isfinite(gravity)
    gravity_small, valid_small, footprint_small, coverage_count = _block_mean(
        gravity, known, footprint, FACTOR)
    valid_small &= footprint_small
    if not valid_small.any():
        raise ValueError("no valid band-13 cells on the 400 m inversion grid")

    _log(f"inverting band 13 at 400 m: {int(valid_small.sum())} measured cells")
    inversion = B.slab_solution(
        gravity_small, valid_small, delta_rho=DELTA_RHO, z0=Z0_M, dx=DX_M,
        filter_order=FILTER_ORDER, kc_scale=KC_SCALE)
    depth_small = np.asarray(inversion["depth_m"], np.float32)
    hgm_small = B.horizontal_gradient_magnitude(depth_small, dx=DX_M).astype(np.float32)
    maxima = B.blakely_simpson_maxima(hgm_small) & valid_small
    flank = B.signed_flank_persistence(
        depth_small, dx=DX_M, apertures_m=APERTURES_M,
        valid=valid_small, maxima=maxima)
    h1_ridge_small = (maxima & flank["same_sign"] &
                      (flank["persistence"] >= PERSISTENCE_MIN))
    hgm_ridge_small = maxima

    shape = grid.shape
    depth_full = _repeat_to_grid(depth_small, shape, fill=np.nan).astype(np.float32)
    hgm_full = _repeat_to_grid(hgm_small, shape, fill=0.0).astype(np.float32)
    persistence_full = _repeat_to_grid(flank["persistence"], shape, fill=0.0).astype(np.float32)
    same_sign_full = _repeat_to_grid(flank["same_sign"].astype(np.float32), shape, fill=0.0).astype(np.float32)
    valid_full = _repeat_to_grid(valid_small, shape, fill=False).astype(bool) & footprint
    depth_valid = valid_full & np.isfinite(depth_full)
    deep_mask = HO.basin_interior_mask(depth_full, depth_valid, depth_quantile=DEEP_QUANTILE)

    h1_centres = _centres_to_grid(h1_ridge_small, shape)
    hgm_centres = _centres_to_grid(hgm_ridge_small, shape)
    h1_ribbon = _ribbon(h1_centres) & valid_full & footprint
    hgm_ribbon = _ribbon(hgm_centres) & valid_full & footprint
    h1_score = (hgm_full * persistence_full).astype(np.float32)
    hgm_score = hgm_full
    candidate_surface = np.where(h1_ribbon, h1_score, 0.0).astype(np.float32)
    if not h1_ridge_small.any() or not np.any(candidate_surface > 0):
        return dict(
            status="STOP-EMPTY-PRIMARY-SURFACE",
            elapsed_seconds=float(time.time() - started),
            candidate_surface_sha256=hashlib.sha256(candidate_surface.tobytes()).hexdigest(),
            candidate_support_pixels=int(h1_ridge_small.sum()),
            candidate_tif_created=False,
            stop_rule="Do not run uniqueness or holdout on an empty candidate surface.")
    # Candidate construction is catalogue-independent. Check all accessible
    # registry surfaces before placing even one candidate dot.
    _log("running full accessible-registry pre-placement surface gate")
    pre_gate = UQ.check(candidate_surface, None, footprint, root=ROOT,
                        progress=lambda i, n: _log(f"pre-placement registry {i}/{n}")
                        if i % 100 == 0 else None)
    if pre_gate.get("stop") or pre_gate.get("preplacement_pass") is not True:
        return dict(
            status="STOP-DUPLICATE-OR-UNCLEARED-PREPLACEMENT-SURFACE",
            elapsed_seconds=float(time.time() - started),
            preplacement_uniqueness=pre_gate,
            candidate_surface_sha256=hashlib.sha256(candidate_surface.tobytes()).hexdigest(),
            candidate_tif_created=False,
            stop_rule="Spearman >0.90 against any accessible registry raster; do not place or promote.")

    # Only after surface clearance are positive pixels placed. The mapped-fault
    # mask is applied in each fold's scoring domain and, separately, to the
    # final upload so known traces receive exactly zero prediction mass.
    h1_peaks = EM.thin(h1_score, h1_ribbon, MIN_SEPARATION_PX, seed=FOLD_SEED)
    hgm_peaks = EM.thin(hgm_score, hgm_ribbon, MIN_SEPARATION_PX, seed=FOLD_SEED)
    matched_budget = min(PRIMARY_BUDGET, int(h1_peaks.sum()), int(hgm_peaks.sum()))
    h1_dots = EM.apply_budget(h1_peaks, h1_score, matched_budget)
    hgm_dots = EM.apply_budget(hgm_peaks, hgm_score, matched_budget)
    random_domain = valid_full & footprint
    random_dots = HO.random_lines(
        shape, matched_budget, random_domain,
        np.random.default_rng(RANDOM_LINE_SEED))
    if int(h1_dots.sum()) != int(hgm_dots.sum()) or int(h1_dots.sum()) != int(random_dots.sum()):
        raise AssertionError("candidate/control pixel budgets are not matched")

    _log("building four spatially blocked whole-component folds")
    folds = HO.make_folds(catalogue, footprint, fraction=HIDE_FRACTION,
                          buffer_px=CONTEXT_BUFFER_PX, seed=FOLD_SEED, n_folds=4)
    withheld_truth = np.logical_or.reduce([f.truth for f in folds])
    active_canary = footprint & ~folds[0].visible
    truth_count = int(withheld_truth.sum())
    leakage_features = {
        "inverted_depth_band13": depth_full,
        "basement_depth_hgm": hgm_full,
        "signed_flank_persistence": persistence_full,
        "same_sign_flank": same_sign_full,
        "hgm_only_maxima": hgm_ribbon.astype(np.float32),
        "h1_filtered_ribbon": h1_ribbon.astype(np.float32),
    }
    canary = {}
    for i, (name, feature) in enumerate(leakage_features.items()):
        auc = EH.auc(feature, withheld_truth, active_canary, n_bg=400000,
                     seed=FOLD_SEED + i)
        canary[name] = dict(evidence_class="LEAKAGE-CANARY-AUC",
                            evaluator_version=EH.VERSION, auc=float(auc),
                            withheld_positive_count=truth_count,
                            active_pixel_count=int(active_canary.sum()),
                            threshold=0.90, leakage_suspect=bool(np.isfinite(auc) and auc > 0.90))

    _log("scoring the preregistered arm and matched controls")
    arms = {"H61U-H1": h1_dots, "unfiltered-HGM-maxima": hgm_dots,
            "matched-random-lines": random_dots}
    terms_by_arm = {}
    fold_diagnostics = {}
    for name, dots in arms.items():
        terms, per_fold = _score_arm(dots, folds, footprint)
        terms_by_arm[name] = terms
        fold_diagnostics[name] = per_fold
    pooled = EH.pooled_summary(terms_by_arm, draws=BOOTSTRAP_DRAWS,
                               seed=BOOTSTRAP_SEED, candidate="H61U-H1")

    recovery = {
        name: HO.segment_recovery(dots, folds, R=300.0, res=100.0,
                                  restrict=deep_mask, min_deep_fraction=0.50)
        for name, dots in arms.items()
    }
    for value in recovery.values():
        row = value["pooled"]
        row["ci95_wilson"] = _paired_wilson(row["recovered_segments"], row["eligible_segments"])
        row["evidence_class"] = "HOLDOUT-SEGMENT-RECOVERY"
        row["evaluator_version"] = EH.VERSION
        row["withheld_positive_count"] = truth_count

    mimic = _run_density_mimic()
    leakage = any(r["leakage_suspect"] for r in canary.values())
    paired = pooled["paired_differences"]
    dti_beats_controls = all(
        name in paired and paired[name]["ci95"][0] > 0.0
        for name in ("unfiltered-HGM-maxima", "matched-random-lines"))
    recovery_beats_random = (
        recovery["H61U-H1"]["pooled"]["frac"] >
        recovery["matched-random-lines"]["pooled"]["frac"])
    promote_to_selector = bool(dti_beats_controls and recovery_beats_random and not leakage)

    # Final TIF is separately pruned on the complete public catalogue. This is
    # only an emission-domain constraint; the holdout candidate above was
    # constructed label-blind and scored with fold-visible masks.
    final_support = h1_ribbon & valid_full & footprint & ~catalogue
    final_peaks = EM.thin(h1_score, final_support, MIN_SEPARATION_PX, seed=FOLD_SEED)
    final_budget = min(PRIMARY_BUDGET, int(final_peaks.sum()))
    final_dots = EM.apply_budget(final_peaks, h1_score, final_budget)
    if not final_dots.any():
        return dict(status="NEGATIVE-EMPTY-FINAL-SUPPORT", preplacement_uniqueness=pre_gate,
                    holdout=pooled, recovery=recovery, leakage_canary=canary,
                    synthetic_density_mimic=mimic, candidate_tif_created=False)

    _log("running final-dot uniqueness gate over the same registry")
    final_gate = UQ.check(candidate_surface, final_dots, footprint, root=ROOT,
                          progress=lambda i, n: _log(f"final registry {i}/{n}")
                          if i % 100 == 0 else None)
    if final_gate.get("stop") or final_gate.get("final_uniqueness_pass") is not True:
        return dict(
            status="STOP-DUPLICATE-OR-UNCLEARED-FINAL-DOTS",
            elapsed_seconds=float(time.time() - started),
            preplacement_uniqueness=pre_gate, final_uniqueness=final_gate,
            holdout=pooled, recovery=recovery, leakage_canary=canary,
            synthetic_density_mimic=mimic, candidate_tif_created=False,
            stop_rule="Spearman >0.90 OR >70% final dots within 3 px of any registry raster; do not submit.")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dot_digest = hashlib.sha256(final_dots.tobytes()).hexdigest()
    filename = f"gems61-h61u-h1-signed-flank-40000dots-{stamp}-{dot_digest[:10]}-zeros.tif"
    output_path = ROOT / "docs" / "downloads" / filename
    prediction = final_dots.astype(np.float32)
    note = ("H61U-H1: band-13 basement-step flank persistence at 2/4 km; 3-px ribbons, "
            "40k cap; GP-1012 scale uncalibrated; HOLDOUT only.")
    submission_name = f"GEMS61-H61U-H1-{stamp}"
    writer_receipt = SW.write_submission(
        output_path, prediction, GRID.DATA_DIR / "sample_submission.tif", footprint,
        note=note, name=submission_name, catalogue=catalogue,
        metadata=dict(hypothesis="H61U-H1", calibration="uncalibrated; complete official GP-1012 grid unavailable",
                     feature_band=13, forbidden_band_15_used=False,
                     final_positive_pixels=int(final_dots.sum()),
                     uniqueness_evidence="see evidence/h61u_run_card.json"))

    raster_sha = writer_receipt["sha256"]
    withheld_components = HO.basin_interior_segments(
        np.logical_or.reduce([f.hidden_all for f in folds]), deep_mask, 0.50)
    card = dict(
        evidence_class="H61U-RUN-CARD",
        generated_utc=datetime.now(timezone.utc).isoformat(),
        status="COMPLETED-ONE-PREREGISTERED-EXPERIMENT",
        hypothesis=dict(
            id="H61U-H1", name="Signed one-sided flank-offset persistence of inverted basement steps",
            layers=["band 13: iso_grav_anom only"],
            mechanism=("A concealed normal-fault block boundary can lack an exposed scarp while "
                       "retaining the same signed basement-depth offset at 2 km and 4 km on the "
                       "local HGM normal."),
            physical_threshold=dict(apertures_m=list(APERTURES_M),
                                    persistence_min=PERSISTENCE_MIN,
                                    ribbon_width_px=3, min_dot_separation_px=MIN_SEPARATION_PX,
                                    max_positive_pixels=PRIMARY_BUDGET)),
        named_nonfault_mimic=dict(name="finite-width intrabasement density sheet / intrusive contact",
                                  synthetic_control=mimic),
        inversion=dict(
            gravity_band=13, grid_spacing_m=DX_M, z0_m=Z0_M,
            delta_rho_fill_minus_basement_kg_m3=DELTA_RHO,
            filter=dict(form="W(k)=1/(1+(k/kc)^2)", order=FILTER_ORDER,
                        kc_scale=KC_SCALE, kc_rad_per_m=KC_SCALE/(2.0*Z0_M)),
            stage=inversion["stage"], rms_residual_mgal=float(inversion["rms_residual_mgal"]),
            valid_400m_cells=int(valid_small.sum()), deep_mask_quantile=DEEP_QUANTILE,
            deep_mask_pixels=int(deep_mask.sum()),
            calibration_status="UN-CALIBRATED: complete official GP-1012 grid unavailable",
            permitted_calibration_source=gp1012.OFFICIAL_XYZ_URL,
            organizer_band_15_used=False),
        holdout=dict(
            evidence_class="HOLDOUT-DTI", evaluator_version=EH.VERSION,
            protocol=("Hide 20% of whole 8-connected catalogue components; Euclidean 3 px context "
                      "buffer; four spatial quadrants; visible catalogue pixels masked pixel-exactly; "
                      "pooled alpha=0.2 beta=0.8 DTI with 300 m triangular kernel; paired 20 km "
                      "block percentile bootstrap."),
            fold_seed=FOLD_SEED, fraction_hidden=HIDE_FRACTION,
            context_buffer_px=CONTEXT_BUFFER_PX,
            withheld_positive_count=truth_count,
            withheld_basin_interior_components=int(withheld_components["n_eligible"]),
            matched_emission_budget=int(matched_budget),
            scores=pooled["scores"], paired_differences=pooled["paired_differences"],
            bootstrap=pooled["bootstrap"], per_fold=fold_diagnostics),
        basin_interior_segment_recovery=dict(
            evidence_class="HOLDOUT-SEGMENT-RECOVERY", evaluator_version=EH.VERSION,
            rule=("8-connected withheld component is eligible when >=50% of its pixels are in "
                  "the deepest 40% of the candidate inversion; recovered when a candidate lies "
                  "within 300 m of an in-mask segment pixel."),
            deep_components=withheld_components["component_stats"],
            arms={name: value["pooled"] for name, value in recovery.items()},
            candidate_vs_random_recovered_difference=(
                recovery["H61U-H1"]["pooled"]["recovered_segments"] -
                recovery["matched-random-lines"]["pooled"]["recovered_segments"])),
        leakage_canary=dict(evidence_class="LEAKAGE-CANARY-AUC",
                            evaluator_version=EH.VERSION,
                            threshold=0.90, features=canary,
                            promotion_blocked=bool(leakage)),
        uniqueness=dict(
            preplacement=pre_gate, final=final_gate,
            registry_source="evidence/registry_refreshed.json",
            registry_scope="accessible sibling-repository registry plus local historical prediction TIFFs; not organizer-complete",
            duplicate_rule="rho >0.90 OR >70% of final candidate dots within 3 px of any registry raster",
            pass_before_placement=pre_gate["preplacement_pass"],
            pass_on_final_dots=final_gate["final_uniqueness_pass"]),
        raster=dict(path=str(output_path.relative_to(ROOT)), sha256=raster_sha,
                    bytes=writer_receipt["bytes"], positive_pixels=int(final_dots.sum()),
                    validator=writer_receipt["validator"],
                    template_report=writer_receipt["template_report"],
                    zip_file=writer_receipt["zip_file"],
                    zip_sha256=writer_receipt["zip_sha256"]),
        submission=dict(name=submission_name, note=note, note_characters=len(note),
                       download_permission="OK_TO_DOWNLOAD: locally format-validated, unique TIF",
                       submit_recommendation=("SELECTOR_REVIEW_ONLY; not an approval" if promote_to_selector
                                              else "NOT_RECOMMENDED: did not clear preregistered holdout/control gates"),
                       approved_for_weekly_slot=False, organizer_confirmed_score=None),
        verdict=("PROMOTE-TO-SEPARATE-SELECTOR-REVIEW" if promote_to_selector else "NEGATIVE"),
        decision_rule=dict(dti_candidate_ci_lower_above_both_controls=dti_beats_controls,
                           basin_interior_segment_recovery_exceeds_random=recovery_beats_random,
                           leakage_canaries_clean=not leakage,
                           format_valid=writer_receipt["validator"]["all_checks_passed"],
                           uniqueness_passed=bool(final_gate["final_uniqueness_pass"])),
        run_history=[dict(path="evidence/h61u_first_attempt.json",
                          status="invalid diagnostic attempt; no candidate raster or score retained",
                          reason="shared signed-flank helper intersected the sample-valid domain with the maxima mask, so every flank sample failed; fixed in the shared helper before this valid run")],
        experiment_budget=dict(experiments=1, attempts=2, maximum_experiments=3,
                               elapsed_seconds=float(time.time() - started),
                               maximum_wall_hours=2,
                               arms=["H61U-H1", "unfiltered-HGM-maxima", "matched-random-lines"],
                               synthetic_mimic_is_control_not_additional_tuning=True),
        irregularity_flags=[
            dict(id="IR-61U-GP1012-01", status="open",
                 description="Complete official GP-1012 grid is unavailable; no depth-scale calibration was performed."),
            dict(id="IR-61U-TRUTH-01", status="known limitation",
                 description="Withheld catalogue components are a proxy, not the organizer's undisclosed new-fault truth."),
            dict(id="IR-61U-REGISTRY-01", status="known limitation",
                 description="Uniqueness scan covers the complete accessible public owner-repository inventory, not every private submission."),
            dict(id="IR-61U-SYNTHETIC-01", status="known limitation",
                 description="The finite density sheet represents one plausible non-fault mimic; it does not span all intrusive/contact geometries."),
        ],
        official_sources=[
            dict(name="DrivenData public leaderboard", url="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/"),
            dict(name="DrivenData problem description / metric", url="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/"),
            dict(name="USGS GP-1012 official publication", url="https://pubs.usgs.gov/publication/gp1012"),
            dict(name="NOAA/NCEI GP-1012 depth grid", url=gp1012.OFFICIAL_XYZ_URL),
            dict(name="NOAA/NCEI GP-1012 readme", url=gp1012.OFFICIAL_README_URL),
            dict(name="Oldenburg 1974 DOI", url="https://doi.org/10.1190/1.1440444"),
            dict(name="Parker 1973 DOI", url="https://doi.org/10.1111/j.1365-246X.1973.tb02307.x"),
        ],
        limits=["HOLDOUT-DTI is not an organizer leaderboard score.",
                "GP-1012 regional summary calibration was not possible in this run.",
                "The final submission excludes all known catalogue pixels; holdout arms are label-blind and scored with visible faults masked.",
                "Download permission means local format/uniqueness gates passed; it is not portal acceptance or slot approval."],
    )
    card_path = ROOT / "evidence" / "h61u_run_card.json"
    card_path.write_text(json.dumps(_json_safe(card), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    _log(f"wrote {output_path.name}; candidate HOLDOUT-DTI={pooled['scores']['H61U-H1']['dti']:.6f}; verdict={card['verdict']}")
    return card


def main() -> int:
    evidence = ROOT / "evidence"
    evidence.mkdir(exist_ok=True)
    _log("starting frozen H61U-H1; no parameter search")
    card = _experiment()
    if card.get("status", "").startswith("STOP-") or card.get("candidate_tif_created") is False:
        path = evidence / "h61u_run_card.json"
        path.write_text(json.dumps(_json_safe(card), indent=2, allow_nan=False) + "\n", encoding="utf-8")
        _log(f"stopped: {card.get('status')}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
