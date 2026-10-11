# Session summary — H61U buried-structure lane (2026-10-11)

## Final result

**H61U-H1 was evaluated but did not produce a submission artifact.** The run completed its frozen spatial holdout, then its accessible sibling-registry final-dot comparison failed the strict uniqueness rule. It stopped before writing a TIFF. There is no current H61U TIF, ZIP, submission name/note, raster SHA-256, byte-level format-validation receipt, upload, or artifact-linked organizer score.

- **Okay to download a current candidate?** No; no cleared candidate file exists.
- **Recommended to submit H61U-H1?** No; final-dot uniqueness failed and H1 did not demonstrate a holdout gain over unfiltered HGM maxima.
- **Weekly slot approved?** No; selector approval is separate and not recorded.
- **Organizer-confirmed score?** None.

Do not treat files retained in `docs/downloads/` or `docs/submissions/` as this run's candidate. They are historical artifacts from earlier work and are intentionally not linked as active downloads.

## Frozen method and controls

The sole authorized hypothesis was H61U-H1: invert band-13 isostatic gravity into an uncalibrated basement-depth surface, find horizontal-gradient maxima, sample same-polarity signed depth offsets at 2 km and 4 km on opposing flanks, require persistence ratio ≥0.60, and propose 3-pixel ribbons with a 40,000-pixel budget. It used the first low-pass Bouguer-slab iterate only, not later nonlinear Oldenburg corrections. GP-1012 was calibration-only and the complete official grid is unavailable locally. Organizer band 15 and literature quantiles were not used.

A named non-fault mimic was a finite buried intrabasement density sheet with zero basement relief. Unfiltered HGM maxima and same-budget random lines were the comparisons. H61U-H2 and H61U-H3 remain prospective, untested alternatives and were not used as fallbacks.

## Holdout results

All DTI values are **HOLDOUT-DTI · evaluator `gems61-pooled-hide-v2` · 12,074 withheld positives**. Pooled α=0.2, β=0.8, 300 m triangular kernel; 95% CIs from 1,000 paired percentile bootstrap draws over 161 globally aligned 20 km blocks (seed 520810). These are local catalogue-holdout metrics, not leaderboard scores.

| Arm/control | HOLDOUT-DTI | 95% CI |
|---|---:|---|
| H61U-H1 | 0.041351 | 0.035332–0.048100 |
| Unfiltered HGM maxima | 0.044359 | 0.036847–0.051764 |
| Matched random lines | 0.016030 | 0.010328–0.021541 |

The paired H1−HGM difference was **−0.003009** (95% CI **−0.010105 to +0.004951**), so no gain over the simple HGM control was demonstrated. H1 was above the random-line baseline. For **HOLDOUT-SEGMENT-RECOVERY · evaluator `gems61-pooled-hide-v2` · 12,074 withheld positives**, H1 recovered 128/318 eligible basin-interior segments (40.25%, Wilson 95% CI 35.01%–45.73%); HGM recovered 138/318 (43.40%); random lines 40/318 (12.58%).

The maximum of six **LEAKAGE-CANARY-AUC · evaluator `gems61-pooled-hide-v2` · 12,074 withheld positives** was 0.555204, below the 0.90 suspect threshold. In the synthetic non-fault control, 172 of 21,252 HGM maxima survived the same-sign persistence filter (0.81%); no DTI was computed because the control has no fault truth.

## Uniqueness stop

The pre-placement surface comparison passed all 748 aligned rasters in the accessible sibling-repository registry, which excludes this repository's archives; worst Spearman rho was 0.030846. The final-dot gate failed: 70 registry entries exceeded the strict >70% overlap limit within 3 px, and the maximum overlap was 1.0. The complete per-raster record is retained in `evidence/h61u_run_card.json` and copied for the site at `docs/data/h61u_run_card.json`. This stop is not proof of copying; it means the dots were not sufficiently distinct under the requested comparison. The code did not prune or adjust dots after the result.

## Earlier invalid attempt

Attempt one was invalid because the shared flank interpolation mask mistakenly required flank samples themselves to be HGM maxima. Its empty-surface uniqueness clearance and transient holdout calculations are discarded. The shared helper was fixed and regression-tested before the unchanged H61U-H1 retry. See `evidence/h61u_first_attempt.json`.

## Repository work in this session

- Recorded the H61U preregistration, final stop, holdout, paired comparisons, segment recovery, canaries, density-sheet mimic, and sibling-registry result with its stated scope limitation.
- Updated the current public pages and root status files to distinguish download permission, submission recommendation, weekly slot approval, and organizer confirmation.
- Preserved old TIFFs as historical references but removed current-page download links to them and added archive notices.
- Reconciled the 2026-10-11 official public leaderboard: the 0.2778 row for extradr19 is account-level, not an artifact receipt. The sibling audit labels H33-2-B2 UNSCORED and calls 0.274673 a projection.
- Withdrew unsupported H61-M calibration, score, and readiness claims in archived reports. `SUBMISSION_READY.md` now explicitly says NOT READY.
- Three agent self-review passes are recorded at `docs/review-passes.html`; 83 unit tests, the 23-page site check, compilation, and diff checks passed. The no-candidate checker returned its expected exit 2. PR and merge status are pending the requested GitHub operation.

## Remaining work and limitations

1. Obtain the complete official NOAA/NCEI GP-1012 `br_depth.xyz` and readme, validate metadata/missing cells, and establish spatial registration before any depth-scale calibration. Do not substitute band 15 or literature quantiles.
2. The public catalogue is a proxy; blocked recovery does not establish performance on undisclosed new faults.
3. A single synthetic density-sheet geometry does not cover all intrabasement sources, intrusions, alteration, or lithologic contacts.
4. The 748-raster manifest used for H61U excludes this repository's historical TIFFs, private uploads, and inaccessible rasters; the H61U final-dot gate failed within the sibling registry. The shared refresh tool now includes local archives on future refreshes; no current-run comparison is retroactively claimed.
5. Public leaderboard rows do not name TIFFs; an artifact-linked official receipt is required for an organizer score.
6. H2/H3 need a new preregistration before any future test. Do not continue by post-hoc tuning H1 or pruning its observed dots.
7. Local site/tests/checker/review outcomes are recorded. The requested PR, its CI checks, and merge outcome are reported in the final session response from actual GitHub results.

## Core values

**Maximize P(Win)** and **Own the Outcome**. We did not evade the uniqueness stop or manufacture an alternate artifact. The valid result is negative, explicitly bounded, and preserved as evidence.
