#!/usr/bin/env python3
"""RETIRED H61-MH card generator.

The historical card contains a legacy UNIQUE verdict superseded by the strict
99.64% final-dot overlap stop. Direct execution is disabled to prevent stale
status from being regenerated; use scripts/build_site_status.py and the current
strict run card instead.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_h61g as R  # noqa: E402


def j(name):
    path = EVID / name
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def main() -> int:
    print("RETIRED: this card generator can restore a legacy H61-MH UNIQUE claim; "
          "strict audit says DUPLICATE_LANE_DRIFT at 99.64%. Use the current H61-L run card.",
          file=sys.stderr)
    return 2

    feat, hold = j("h61m_features.json"), j("h61m_holdout.json")
    e2, e3l, e3s, e4 = (j("h61m2_holdout.json"), j("h61m3_loqo.json"),
                        j("h61m3_sweep.json"), j("h61m4_loqo.json"))
    if e3s:
        card_sweep = dict(
            label="HOLDOUT-DTI configuration sweep (non-spatially-blocked instrument)",
            best=e3s["best_candidate"],
            rows=[dict(name=r["name"], dti=round(r["pooled_dti"], 4),
                       ci95=[round(x, 4) for x in r["ci95_bootstrap_cells"]],
                       coverage=round(r["coverage"], 3),
                       basin=f"{r['segments_recovered_basin_interior']}/"
                             f"{r['segments_withheld_basin_interior']}")
                  for r in e3s["results"]])
    else:
        card_sweep = None
    fin, uni = j("h61m_final.json"), j("h61m_uniqueness.json")

    chosen = next(r for r in hold["results"] if r["name"] == fin["candidate"])
    e2_best = next(r for r in e2["results"] if r["name"] == e2["best_candidate"])
    e4_sum = e4["summary"]

    def ctrl(name_frag, default=None):
        for r in hold["results"]:
            if name_frag in r["name"]:
                return r
        if default is None:
            raise KeyError(name_frag)
        return default

    rl40 = ctrl("CONTROL random lines @ 40000")
    rd40 = ctrl("CONTROL random dots anywhere @ 40000")
    g = j("h61g_run_card.json")
    x2 = None
    if g:
        for row in g.get("controls", []) or g.get("holdout_dti", {}).get("rows", []):
            if isinstance(row, dict) and "X2" in str(row.get("name", "")):
                x2 = row.get("pooled_dti") or row.get("dti")
        x2 = x2 or g.get("holdout_dti", {}).get("previous_session_best_X2")
    n_pos = hold["n_withheld_truth_px"]
    n_seed = [20, 21]  # fixed by gems61.holdout_segmented v2

    # derive the blocked ranges from the LOQO evidence, never hardcode them
    _auc = [r["loqo_canary_auc"] for qd in e4.get("per_quadrant", {}).values() for r in qd.values()]
    _dti = [r["loqo_pooled_dti"] for qd in e4.get("per_quadrant", {}).values() for r in qd.values()]
    AUC_LO, AUC_HI = (min(_auc), max(_auc)) if _auc else (0.0, 0.0)
    DTI_LO, DTI_HI = (min(_dti), max(_dti)) if _dti else (0.0, 0.0)
    AUC_MEAN = e4_sum["logistic"]["mean_loqo_canary_auc"]
    n_cells = hold["n_cells"]

    card = dict(
        session="H61-M (arena/2a87ed28-61gemsdoe, 2026-10-11)",
        hypothesis="A buried normal fault is a step in the GP-1012-calibrated inverted basement "
                   "surface; the step fixes where to look, and an out-of-fold habitat model over 28 "
                   "catalogue-independent features (the 19 supplied bands plus the lane's own inverted "
                   "depth, depth gradient, step throw, step indicator, corridor indicator, basin "
                   "indicator and Euler SI=0 source depth) fixes where to put the dot.",
        mechanism="Basement throw under alluvium -> isostatic-residual gradient maximum (200 m "
                  "Parker/Oldenburg slab inversion, GP-1012-calibrated, Blakely-Simpson maxima, "
                  "measured throw >= 80 m) -> the same gravity products enter a logistic habitat model "
                  "trained on the visible mapped faults -> 40,000 binary dots at 3 px spacing, every "
                  "dot more than 3 px from a mapped trace.",
        named_non_fault_mimic="Density contrasts inside the basement (intrabasement lithologic "
                              "contacts) produce the same isostatic-residual gradient maximum. The lane's "
                              "discriminator is implemented, not asserted: the inverted depth (a basin "
                              "step sits on thick low-density fill) and the Euler SI=0 source depth (a "
                              "basement edge is shallow, an intrabasement contact is deep). Measured "
                              "logistic weights: inv_depth -0.172, inv_depth_hgm -0.204, "
                              "euler_depth -0.053, step_throw -0.046, step_indicator -0.006, "
                              "corridor_indicator +0.194 -- i.e. the lane's instruments are in the model "
                              "and carry almost no marginal information, which is the honest negative "
                              "result for the lane's premise.",
        holdout_dti=dict(
            value=chosen["pooled_dti"], ci95=chosen["ci95_bootstrap_cells"],
            evaluator=hold["evaluator"], n_withheld_positive_px=hold["n_withheld_truth_px"],
            n_dots_per_draw=chosen["n_emitted_per_draw"],
            label=f"HOLDOUT-DTI (gems61.holdout_segmented v2, {n_pos:,} withheld positive px, "
                  f"seeds {'+'.join(str(s) for s in n_seed)}, mode all, "
                  f"pooled alpha {hold['alpha']} beta {hold['beta']} R {hold['kernel_m']} m)",
            random_lines_same_budget=rl40["pooled_dti"],
            random_lines_same_budget_source="evidence/h61m_holdout.json row "
                                            f"'{rl40['name']}'",
            random_dots_same_budget=rd40["pooled_dti"],
            previous_session_best_X2=(g.get("holdout_dti", {}).get("value")
                                      if g else None),
            previous_session_best_X2_source=("evidence/h61g_run_card.json holdout_dti.value "
                                             "(corridor x slope-ridge locator @ 40000)"),
            segments_recovered=chosen["segments_recovered_basin_interior"],
            segments_withheld=chosen["segments_withheld_basin_interior"],
            segments_recovery_rate=chosen["basin_recovery_rate"],
            segments_recovered_ci=chosen["basin_recovery_ci95"],
            segments_recovered_random_lines=(f"{rl40['segments_recovered_basin_interior']}/"
                                             f"{rl40['segments_withheld_basin_interior']} "
                                             f"(CONTROL random lines @ "
                                             f"{rl40['n_emitted_per_draw']:.0f})"),
            basin_interior_segments=f"{chosen['segments_recovered_basin_interior']}/"
                                    f"{chosen['segments_withheld_basin_interior']} recovered "
                                    f"(CI {chosen['basin_recovery_ci95']})",
            basin_interior_random_lines=(f"{rl40['segments_recovered_basin_interior']}/"
                                         f"{rl40['segments_withheld_basin_interior']} "
                                         f"(CONTROL random lines @ "
                                         f"{rl40['n_emitted_per_draw']:.0f})")),
        spatially_blocked_dti=dict(
            label="LOQO-DTI (leave-one-quadrant-out: retrain with no training pixel inside the "
                  "scored quadrant; the honest instrument for a slot decision)",
            logistic=e4_sum["logistic"], gbm=e4_sum["gbm"],
            slope19_only=e4_sum["slope19"], lane_corridor_locator=e4_sum["corridor"],
            verdict=(f"No locator generalises across space: all four sit at {DTI_LO:.2f}-{DTI_HI:.2f} "
                     f"DTI and {AUC_MEAN:.2f}-{e4_sum['corridor']['mean_loqo_canary_auc']:.2f} mean "
                     f"canary AUC, i.e. at or just above the random baseline. The lane's corridor x "
                     f"slope locator has the highest and most consistent blocked AUC "
                     f"({e4_sum['corridor']['mean_loqo_canary_auc']:.3f}) but not the highest blocked "
                     f"DTI.")),
        configuration_sweep=card_sweep,
        leakage_canary=dict(
            logistic_oof_auc=hold["leakage_canary"]["worst_auc"],
            gbm_oof_auc=e2["leakage_canary"]["worst_auc"],
            threshold_auc=0.90,
            finding=(f"IR-61-LEAK-01: the gradient-boosted habitat model's out-of-fold canary AUC was "
                     f"{e2['leakage_canary']['worst_auc']:.3f}, above the 0.90 line. The "
                     f"leave-one-quadrant-out retest shows why: with no training pixel inside the "
                     f"scored quadrant its AUC falls to {AUC_LO:.3f}-{AUC_HI:.3f} and its pooled DTI "
                     f"to the random baseline. The {e2['leakage_canary']['worst_auc']:.3f} was "
                     f"adjacency to the visible traces the model memorised, not skill. The shipped "
                     f"file therefore uses the L2 logistic model, whose canary AUC is "
                     f"{hold['leakage_canary']['worst_auc']:.3f} with no caveat.")),
        correlation_overlap_vs_registry=dict(
            worst_spearman=uni["worst_spearman"], worst_overlap=uni["worst_overlap"],
            n_compared=uni["n_registry_rasters_compared"], verdict=uni["verdict"],
            rho_limit=0.90, overlap_limit=0.70),
        raster_sha256=fin["sha256"], raster_bytes=fin["bytes"],
        validator_output=dict(checks=fin["validator"], all_passed=fin["validator_all_passed"],
                              n_checks=len(fin["validator"])),
        submission_name=fin["submission"], note=fin["note"], note_chars=fin["note_chars"],
        download=dict(tif=fin["download_tif"], zip=fin["download_zip"],
                      receipt=fin["receipt"], sha256=fin["sha256"]),
        dots_distance_to_catalogue_px=fin["dots_distance_to_catalogue_px"],
        inversion=dict(z0_m=feat["inversion_fine"]["z0_m"],
                       delta_rho=feat["inversion_fine"]["delta_rho"],
                       fine_dx_m=feat["inversion_grids"]["fine_px"] * 100,
                       coarse_dx_m=feat["inversion_grids"]["coarse_px"] * 100,
                       fraction_deeper_than_1km=feat["depth_stats_fine"]["fraction_gt_1km"],
                       gp1012_anchor=0.20,
                       rank_correlation_fine_vs_coarse=feat["rank_correlation_fine_vs_coarse"],
                       cross_check_r_vs_band15=feat["cross_check_vs_supplied_band15"]["pearson_r"],
                       corr_depth_vs_gravity=feat["cross_check_vs_supplied_band15"]["corr_depth_vs_gravity"],
                       footprint_cells_lost_at_200m=feat["support"]["footprint_cells_lost_at_200m"],
                       n_steps_200m=feat["steps_fine"]["n_steps"],
                       n_hgm_maxima_200m=feat["steps_fine"]["n_hgm_maxima"]),
        lane_reporting_requirements=dict(
            inverted_isostatic_layer=True,
            gp1012_calibration_only_for_density_depth_scale=True,
            hgm_maxima_of_basement_depth_as_candidates=True,
            multi_line_ribbon_tested=True,
            ribbon_result="3x3 ribbon scores 0.0184 against 0.0409 for the same dots at the same "
                          "budget on the protocol holdout (256,096 emitted px vs 39,794): the metric "
                          "charges 0.2 per extra positive pixel, so the multi-line character is kept "
                          "at field scale (many parallel step lines) and the emission is dots.",
            basin_interior_recovery_vs_random_lines="351/1999 (X2 @ 40000, previous session) and "
                                                    "353/1982 (this session's M2 @ 40000) versus "
                                                    "215/1999 by random lines",
            competing_explanation_tested=True),
        experiments_run=4,
        budget_experiments=3,
        organizer_confirmed_score=None,
        verdict="negative",
        verdict_reason=(f"HOLDOUT-DTI {chosen['pooled_dti']:.4f} (CI "
                        f"{chosen['ci95_bootstrap_cells'][0]:.4f}-"
                        f"{chosen['ci95_bootstrap_cells'][1]:.4f}) beats random lines "
                        f"({rl40['pooled_dti']:.4f}) and the previous session's best lane "
                        f"construction ({(g.get('holdout_dti', {}).get('value') or 0):.4f}) on the "
                        f"protocol holdout, but the spatially blocked leave-one-quadrant-out test "
                        f"puts every locator we have at the random baseline "
                        f"({DTI_LO:.4f}-{DTI_HI:.4f} LOQO-DTI), so this file is a valid, unique, "
                        f"honest negative result rather than a slot candidate. Promotion is a "
                        f"separate selector step."),
    )
    (EVID / "h61m_run_card.json").write_text(json.dumps(card, indent=1) + "\n")
    print(json.dumps({k: card[k] for k in ("hypothesis", "verdict", "verdict_reason")}, indent=1)[:1200])
    print("wrote evidence/h61m_run_card.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
