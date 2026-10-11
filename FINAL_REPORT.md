# Final report — H61U buried-structure lane (2026-10-11)

## Decision

**Negative; no candidate GeoTIFF was written.** The only authorized experiment, H61U-H1, completed the spatial holdout and then stopped at the final-dot uniqueness gate. Its candidate did not pass the required registry comparison. There is no TIF, ZIP, raster SHA-256, byte-level format-validation receipt, submission name/note, upload, or artifact-linked organizer score.

| Decision | Answer |
|---|---|
| Okay to download a current candidate? | **No.** No cleared artifact exists. |
| Recommended to submit? | **No.** The final-dot gate failed; the holdout did not establish an improvement over HGM maxima. |
| Weekly slot approved? | **No.** Slot promotion is a separate selector decision. |
| Organizer-confirmed score? | **None.** |

Do not substitute one of the historical TIFFs retained under `docs/downloads/` or `docs/submissions/`.

## Frozen method

H61U-H1 inverted band-13 isostatic gravity to estimate basement geometry on a 400 m grid using fixed `z0=1000 m`, density contrast `−400 kg/m³`, and an order-2 low-pass filter. The run used the first low-pass Bouguer-slab iterate only—not later nonlinear Oldenburg correction iterations. At horizontal-gradient maxima of the inverted basement-depth surface, it sampled signed depth offsets at 2 km and 4 km across the local normal, required the same polarity and persistence ratio ≥0.60, and registered 3-pixel ribbons with a 40,000-pixel budget. The priors were fixed before holdout and the depth scale remains uncalibrated. GP-1012 was permitted only as a future calibration reference; the complete official NOAA/NCEI grid is not local. Organizer band 15 was not used as a feature or calibration substitute.

The named non-fault mimic was a finite buried intrabasement density sheet with zero basement relief. Unfiltered HGM maxima and matched random lines were the holdout controls. H61U-H2 and H61U-H3 remain untested prospective hypotheses, not fallbacks.

## HOLDOUT-DTI

All values below are **HOLDOUT-DTI · evaluator `gems61-pooled-hide-v2` · 12,074 withheld positives**. Pooled α=0.2, β=0.8, 300 m triangular kernel; 95% CIs are from 1,000 paired percentile bootstrap draws over 161 globally aligned 20 km blocks (seed 520810), conditional on the fixed spatial folds and catalogue truth.

| Arm/control | HOLDOUT-DTI | 95% CI |
|---|---:|---|
| H61U-H1 | 0.0413507559 | 0.0353324448–0.0481004262 |
| Unfiltered HGM maxima | 0.0443593581 | 0.0368469195–0.0517639813 |
| Matched random lines | 0.0160303679 | 0.0103278486–0.0215411549 |

The paired H1-minus-HGM difference was −0.0030086022 (95% CI −0.0101048834 to +0.0049512141); the interval includes zero and the point estimate favors HGM. H1 exceeded the random-line baseline, but did not beat the strongest comparable control.

### HOLDOUT-SEGMENT-RECOVERY

**HOLDOUT-SEGMENT-RECOVERY · evaluator `gems61-pooled-hide-v2` · 12,074 withheld positives.** Eligible segments have at least half their component pixels in the deepest 40% of that method's own inversion; recovery requires a candidate pixel within 300 m. Wilson 95% CIs:

| Arm/control | Recovered / eligible | Rate | 95% CI |
|---|---:|---:|---|
| H61U-H1 | 128 / 318 | 40.25% | 35.01%–45.73% |
| Unfiltered HGM maxima | 138 / 318 | 43.40% | 38.06%–48.89% |
| Matched random lines | 40 / 318 | 12.58% | 9.38%–16.68% |

These are catalogue-proxy holdout results, not organizer scores or private-new-fault predictions.

## Uniqueness result and stop

The pre-placement continuous-surface check covered all **748 aligned rasters in the accessible sibling-repository registry** and passed: worst Spearman rho was **0.0308462361**. The final-dot gate failed: **70 registry entries** were flagged above the strict >0.70 within-3-pixel overlap threshold; worst overlap was **1.0**. The worst-comparison path is in `evidence/h61u_run_card.json` and the public copy at `docs/data/h61u_run_card.json`.

The stop means the dots were insufficiently distinct under the registered rule. It is not proof of copying. The runner did not prune or alter dots after seeing the result, did not write a TIFF, and did not reach byte-level validation.

## Mechanism and leakage controls

All six **LEAKAGE-CANARY-AUC · evaluator `gems61-pooled-hide-v2` · 12,074 withheld positives** were below 0.90; maximum AUC was 0.555204. The synthetic non-fault control was a 512×512, 400 m grid with a 28.8×3.2 km finite sheet, +250 kg/m³ contrast, 1.5 km thickness, and 2.5 km burial. It produced 21,252 HGM maxima; 172 survived H1's same-sign persistence test (0.81%). No DTI was computed because this sheet has no fault truth. This one geometry does not rule out all intrabasement contacts or bodies.

## Public leaderboard and score attribution

The official public leaderboard snapshot fetched 2026-10-11 is an account-level display, not a filename-level receipt. It showed xiaofanhu #1/0.4133, DARD #9/0.3195, and extradr19 #23/0.2778. The 0.2778 row does not identify H33-2-B2. The sibling audit calls H33-2-B2 `UNSCORED` and labels 0.274673 a projection. No H61U organizer receipt or score exists. See [`docs/analysis.html`](docs/analysis.html) and `evidence/leaderboard_reconciliation_2026-10-11.json`.

## Remaining work and limitations

1. Obtain the complete official NOAA/NCEI GP-1012 grid and readme; validate metadata and missing cells; establish spatial registration before depth-scale calibration. Do not substitute band 15 or literature quantiles.
2. The spatial holdout uses a proxy catalogue; it does not measure organizer recovery of undisclosed new faults.
3. One synthetic density-sheet geometry cannot characterize every non-fault source.
4. The manifest used by H61U scans accessible sibling repositories but excludes 61GEMSDOE archived TIFFs, private uploads, and inaccessible files. H61U failed the sibling-registry gate. The shared refresh code now adds local archives for future runs; no current-run comparison is retroactively claimed.
5. Any future H2/H3 experiment requires a new preregistration; do not tune or prune H1 after its failed final-dot comparison.
6. Check/test, review-pass, and PR/merge status must be reported from actual repository and GitHub results, not assumed.

## Core values

**Maximize P(Win)** and **Own the Outcome**: the result is negative, the uniqueness stop is honored, and no artifact, score, calibration, or slot approval is fabricated.
