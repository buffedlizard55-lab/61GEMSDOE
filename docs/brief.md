# Standing brief — 61GEMSDOE buried-structure lane

Read `README.md` and this brief before every work session. Current code and evidence receipts control; summaries must match `evidence/h61u_run_card.json` and `evidence/h61u_outcome_summary.json`.

## Current run result

H61U-H1 was the only authorized experiment. It completed spatial holdout and stopped at the strict final-dot uniqueness gate. **No candidate TIFF exists.** Download permission is NO; submission is not recommended; weekly-slot approval is NO; no organizer receipt/score exists. Do not use or link an older archived TIFF as a replacement.

The pre-placement surface gate passed against 748 accessible sibling-repository rasters (worst Spearman rho 0.030846); the refresh excludes local historical TIFFs and private/inaccessible submissions. Final dots failed: 70 registry entries crossed the >70% within-3-px overlap limit; maximum overlap was 1.0. No post-hoc pruning or threshold change followed.

## Task

Invert isostatic gravity for basement depth, use official GP-1012/NOAA-NCEI only to calibrate depth scale, identify basement-depth HGM maxima as candidate buried fault steps, emit multi-line ribbons, compare withheld basin-interior segment recovery against matched random lines, and test intrabasement density contrasts as a non-fault mimic.

## Standing constraints

- Organizer band 15 (`depth_to_base_surf`) is prohibited as a calibration target/reference or prediction feature. Complete GP-1012 grid is not local; do not claim calibration or substitute band 15/literature quantiles.
- Hide whole 8-connected catalogue components with buffer; derive any catalogue features only from visible faults; pixel-exactly mask visible faults during scoring; use `gems61-pooled-hide-v2`, pooled DTI α=0.2/β=0.8, 300 m triangular kernel, and spatial-block 95% CI.
- Label every metric `HOLDOUT-DTI` with evaluator version, withheld-positive count, and CI, or `ORGANIZER-CONFIRMED` only from an artifact-linked official receipt. A projection is never a score. Single-feature AUC >0.90 is leakage-suspect.
- For any future candidate, run Spearman against the full accessible sibling registry before placement, then strict dot overlap against that registry and all local historical TIFFs. Stop on rho >0.90 or >70% within 3 px; no global/private uniqueness claim.
- Reuse shared cached features, `evaluate_holdout.py`, and `submission_writer.py`; fix shared-tool defects in place, preserve `make_folds` compatibility, and update stale callers.
- Stop after three experiments or two hours. H2/H3 are prospective, not H1 fallbacks. Weekly slot selection is separate.
- Run card includes hypothesis, mechanism, named mimic, HOLDOUT-DTI+CI, registry results, raster SHA-256, format validation, submission name/note, and verdict. If no artifact is written, hash/name/note are null and format validation is NOT RUN.
- State download permission, submit recommendation, and slot approval separately. Never copy an earlier raster.
- Preserve **Maximize P(Win)** and **Own the Outcome**; cite official data, flag irregularities, run three review passes and repository checks, and report limitations.

## H61U results

**HOLDOUT-DTI · `gems61-pooled-hide-v2` · 12,074 withheld positives:** H1 0.041351 (95% CI 0.035332–0.048100); unfiltered HGM 0.044359 (0.036847–0.051764); matched random lines 0.016030 (0.010328–0.021541). Paired H1−HGM difference −0.003009 (95% CI −0.010105 to +0.004951), so no gain was demonstrated over the simple HGM control.

**HOLDOUT-SEGMENT-RECOVERY · `gems61-pooled-hide-v2` · 12,074 withheld positives:** H1 128/318 (40.25%, Wilson 95% CI 35.01%–45.73%); HGM 138/318 (43.40%); random 40/318 (12.58%). These catalogue-holdout results are not organizer scores.

**LEAKAGE-CANARY-AUC · `gems61-pooled-hide-v2` · 12,074 withheld positives:** maximum single-feature AUC 0.555204, below the 0.90 blocker. The synthetic density-sheet control retained 172/21,252 HGM maxima (0.81%); no DTI was computed because the control has no fault truth.

## Official references

- [Competition](https://www.drivendata.org/competitions/306/competition-doe-gems/)
- [Problem and metric](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
- [Rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf)
- [Leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)
- [USGS GP-1012](https://pubs.usgs.gov/publication/gp1012)
- [NOAA/NCEI grid](https://www.ngdc.noaa.gov/mgg/gravity/1999/data/grids/basinrng/br_depth.xyz)
- [NOAA/NCEI readme](https://www.ngdc.noaa.gov/mgg/gravity/1999/data/grids/basinrng/readme.txt)
- [Parker (1973)](https://doi.org/10.1111/j.1365-246X.1973.tb02307.x) · [Oldenburg (1974)](https://doi.org/10.1190/1.1440444)

The official page fetch on 2026-10-11 showed xiaofanhu #1/0.4133, DARD #9/0.3195, and extradr19 #23/0.2778. Those rows do not identify artifacts; H33-2-B2 remains unscored in its owner audit. See [score audit](analysis.html).
