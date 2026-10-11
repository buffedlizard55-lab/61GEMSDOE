# 61GEMSDOE — buried-structure lane

**Read this file at the start of every work session.** This repository investigates buried fault steps using basement-depth inversion of gravity. The task prompt is preserved in the standing brief below; do not change lanes without a new explicit decision.

- [Current site and executive guide](https://buffedlizard55-lab.github.io/61GEMSDOE/)
- [Current run card](docs/run-card.html)
- [Official competition #306](https://www.drivendata.org/competitions/306/competition-doe-gems/)
- [Official rules](https://docs.nlr.gov/docs/fy26osti/96647.pdf)

## Current outcome — read first (2026-10-11)

### No candidate TIFF exists

The only authorized experiment, **H61U-H1**, completed its spatial holdout but stopped on the strict final-dot uniqueness gate. The runner stopped before writing a candidate GeoTIFF. **There is no current H61U TIFF, ZIP, submission name, note, raster SHA-256, byte-level format validation, upload, or artifact-linked organizer score.** Older files in `docs/downloads/` and `docs/submissions/` are historical artifacts and are not this run's candidate.

| Decision | Current answer |
|---|---|
| Okay to download a current candidate? | **NO — no cleared candidate artifact was written.** No one-click link is provided. |
| Recommended to submit H61U-H1? | **NO.** Final-dot uniqueness failed; H1 also did not demonstrate an improvement over unfiltered HGM maxima in the local holdout. |
| Weekly slot approved? | **NO.** Slot selection is separate and is not implied by this local research result. |
| Organizer-confirmed score? | **None.** No artifact-linked submission receipt exists. |

The pre-placement surface comparison passed all **748 aligned rasters in the accessible sibling-repository registry**: worst Spearman rank correlation **0.030846** (stop threshold is strictly greater than 0.90). The final-dot comparison failed: **70 registry entries** crossed the strictly greater than 70% within-3-pixel overlap limit; worst overlap was **1.0**. The worst-overlap raster is recorded in the full receipt. This result means the dots are insufficiently distinct under the requested rule; it does **not** establish that any file was copied. The registered fail-closed stop was respected: no post-hoc pruning or threshold tuning, no TIF write, and no format-validation claim.

### Local holdout outcome (not an organizer score)

Every DTI value below is labelled **HOLDOUT-DTI · evaluator `gems61-pooled-hide-v2` · 12,074 withheld positives**. Pooled α=0.2, β=0.8, 300 m triangular kernel; 95% CIs use 1,000 paired percentile bootstrap draws over 161 globally aligned 20 km blocks (seed 520810), conditional on fixed folds and catalogue truth.

| Arm/control | HOLDOUT-DTI | 95% CI |
|---|---:|---|
| H61U-H1 signed flank persistence | 0.041351 | 0.035332–0.048100 |
| Unfiltered basement-depth HGM maxima | 0.044359 | 0.036847–0.051764 |
| Matched random lines | 0.016030 | 0.010328–0.021541 |

H61U-H1 beat the random-line control but did **not** show a gain over unfiltered HGM maxima: paired H1−HGM delta **−0.003009**, 95% CI **−0.010105 to +0.004951**. For segment recovery, **HOLDOUT-SEGMENT-RECOVERY · `gems61-pooled-hide-v2` · 12,074 withheld positives**: H1 recovered 128/318 eligible basin-interior segments (40.25%, Wilson 95% CI 35.01%–45.73%); unfiltered HGM recovered 138/318 (43.40%); matched random lines 40/318 (12.58%). These proxy-label results do not estimate an organizer score or private new-fault recovery.

All six **LEAKAGE-CANARY-AUC · `gems61-pooled-hide-v2` · 12,074 withheld positives** were below 0.90 (maximum 0.555204). The synthetic intrabasement density-sheet mimic generated 21,252 HGM maxima; 172 survived the same-sign persistence filter (0.81%). It has no fault truth, so no DTI was computed.

### Full evidence and review pages

- [Executive guide](docs/executive-summary.html) · [holdout and segment recovery](docs/holdout.html) · [method](docs/method.html)
- [Run card](docs/run-card.html) · [compact JSON outcome](docs/data/h61u_outcome_summary.json) · [full registry-linked receipt](docs/data/h61u_run_card.json)
- [Three ranked hypotheses](docs/hypotheses.html) · [provenance and obtainability](docs/data-sources.html) · [irregularities](docs/irregularities.html)
- [Leaderboard reconciliation](docs/analysis.html) · [review passes](docs/review-passes.html) · [review-pass JSON](docs/data/review_passes_2026-10-11.json) · [remaining work](docs/next-steps.html)
- The earlier invalid attempt is documented at `evidence/h61u_first_attempt.json`; its transient metrics and empty-surface uniqueness result are invalid and discarded.

## Standing task brief

Review and improve the GEMS buried-structure lane by inverting isostatic gravity for basement depth, using GP-1012 only to calibrate depth scale, identifying basement-depth horizontal-gradient maxima as candidate buried fault steps, emitting multi-line ribbons, comparing withheld basin-interior segment recovery against matched random lines, and testing intrabasement density contrasts as a non-fault mimic.

### Standing constraints

1. **Do not leave the lane.** Do not use organizer band 15 (`depth_to_base_surf`) as a calibration reference or prediction feature. The only permitted depth-scale calibration is the complete official USGS GP-1012 / NOAA-NCEI `br_depth.xyz` grid. The full grid is not currently local; say calibration is blocked and the inversion is uncalibrated. Never substitute literature quantiles or organizer band 15.
2. **Pre-register 3–5 genuinely untried hypotheses before implementation.** Record their input layers, physical signature, why a catalogue-missing fault could produce it, differences from local and sibling methods, expected DTI/cost ranking, and obtainability of required official data. Only the frozen H61U-H1 was authorized and tested in this run. H61U-H2 and H61U-H3 are prospective and are not post-hoc fallbacks. H61U-H4 was withdrawn after prior-art review.
3. **Spatial holdout:** hide whole 8-connected catalogue components with a context buffer; derive catalogue features only from visible faults; pixel-exactly mask visible faults in the scored domain. Reuse the shared `evaluate_holdout.py`, shared cached features, `submission_writer.py`, and evaluator. Fix shared-tool defects in place; preserve `make_folds` caller compatibility and update stale callers.
4. **Metric labels:** every local DTI must be labelled `HOLDOUT-DTI` with evaluator version, withheld-positive count, and 95% CI. Only an artifact-linked organizer receipt supports `ORGANIZER-CONFIRMED`. A projection is never a score. Run single-feature leakage canaries; AUC >0.90 is leakage-suspect until explained.
5. **Uniqueness gate:** compare the soft surface against the full accessible sibling registry before placement and compare final dots against it and local historical TIFFs again. If Spearman rank correlation is >0.90 or >70% of candidate dots are within 3 px of any registry raster's dots, log the duplicate and stop. The manifest used for H61U excluded this repository's historical TIFFs and all private/inaccessible rasters; the shared refresh tool now includes local archives on future refreshes, but no global uniqueness claim is possible.
6. **Run card:** include hypothesis, physical mechanism, named non-fault mimic, holdout DTI + CI, registry correlation/overlap, raster SHA-256, format-validator result, submission name and short note, and promote/negative verdict. When no artifact is emitted, explicitly set raster hash/name/note to null and say validation was not run; do not invent values.
7. **Budget:** stop at three experiments or two hours. A negative result is a deliverable. Slot promotion is a separate selector decision.
8. **Download, submit, slot:** explicitly state separately whether a TIF is okay to download, whether submission is recommended, and whether a weekly slot is approved. Do not upload or imply slot approval. Never copy an earlier submission.
9. **Core values:** **Maximize P(Win)** and **Own the Outcome**. Cite trustworthy official sources, flag irregularities, do three review passes, run repository checks, and report limitations and remaining work. Do not invent source verification or scores.

## H61U-H1 method and protocol

**Frozen hypothesis:** a concealed basement fault has a persistent one-sided depth offset across the local horizontal-gradient maximum of an inverted basement-depth surface. H61U used band 13 only, 400 m grid, fixed `z0=1000 m`, fill-minus-basement density contrast `−400 kg/m³`, order-2 low-pass filter `W(k)=1/(1+(k/kc)^2)`, `kc=1/(2*z0)`, and the **first low-pass Bouguer-slab iterate only**—not later nonlinear Oldenburg correction iterations. It sampled signed offsets at 2 km and 4 km, required same polarity and persistence ratio ≥0.60, and registered 3-pixel ribbons under a 40,000-pixel budget. The physical priors were fixed and not fitted to the holdout; absolute depth/throw remains uncalibrated.

Holdout parameters: evaluator `gems61-pooled-hide-v2`, 20% whole-component hide, 3 px buffer, four quadrants, seed 20261011; pooled DTI α=0.2, β=0.8, 300 m triangular kernel; paired percentile bootstrap over aligned 20 km blocks, 1,000 draws, seed 520810. The named non-fault control is a finite buried intrabasement density sheet with zero basement relief. HGM maxima alone and same-budget random lines are the matched controls.

## Official links and obtainability

| Source | Link | Role / limitation |
|---|---|---|
| Competition overview | [DrivenData #306](https://www.drivendata.org/competitions/306/competition-doe-gems/) | Official challenge overview. |
| Problem, metric, submission format | [DrivenData problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) | Public task and evaluation description. |
| Official competition rules | [NLR/DOE rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf) | Submission, weekly limit, and selector process. |
| Public leaderboard | [DrivenData leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) | Public account-best scores, not artifact receipts. |
| USGS GP-1012 | [USGS publication](https://pubs.usgs.gov/publication/gp1012) | Permitted depth-scale calibration reference only. |
| NOAA/NCEI GP-1012 grid | [Official `br_depth.xyz`](https://www.ngdc.noaa.gov/mgg/gravity/1999/data/grids/basinrng/br_depth.xyz) | Complete grid absent locally; coordinate registration unresolved. |
| NOAA/NCEI grid readme | [Official readme](https://www.ngdc.noaa.gov/mgg/gravity/1999/data/grids/basinrng/readme.txt) | Needed with complete grid for validation. |
| Parker (1973) | [DOI](https://doi.org/10.1111/j.1365-246X.1973.tb02307.x) | Potential-field forward calculation. |
| Oldenburg (1974) | [DOI](https://doi.org/10.1190/1.1440444) | Gravity inversion method context. |
| Blakely & Jachens (1991) | [DOI](https://doi.org/10.1130/0016-7606(1991)103%3C0795:RSOMRI%3E2.3.CO;2) | Regional Nevada gravity/magnetics context. |
| Official reference solution | [DrivenData GitHub](https://github.com/drivendataorg/gems-prize-reference-solution) | Reference for contest format/evaluation. |

Competition training bytes available in this checkout are from a hash-pinned public bridge copy; the data tab is login-walled, so these hashes do not prove a fresh organizer-authenticated download. See [data sources](docs/data-sources.html) and `docs/data/sources.json`.

## Leaderboard attribution rule

The official public page fetched 2026-10-11 showed xiaofanhu #1 at 0.4133; DARD #9 at 0.3195 (ranked #1 in the 2026-10-03 snapshot); extradr19 #23 at 0.2778; smrtdoog5 #36 at 0.2708; SDCF9 #46 at 0.2600; and MSU-Laskowski-GEMS #50 at 0.2448. These are account-level public rows, not filename-level receipts. In particular, the `extradr19` 0.2778 row does not establish that H33-2-B2 earned it; the sibling owner audit labels H33-2-B2 `UNSCORED` and calls 0.274673 a projection. See [dated reconciliation](docs/analysis.html) and `evidence/leaderboard_reconciliation_2026-10-11.json`.

## Submitting a future eligible artifact

There is **no current file to submit**. A future, independently reviewed TIF should only be considered after it passes the frozen spatial holdout, accessible sibling-registry uniqueness gates plus an explicit comparison to this repository's archived TIFFs, and byte-level validation against the official sample grid. Then the eligible team should: sign in to the official competition page; open the competition's submission interface; upload the exact validated `.tif`; enter the registered submission name and ≤140-character note; follow the active weekly submission cap/selector process; submit only after the separate slot decision; and save the organizer's artifact-linked receipt and checksum. A public leaderboard account row alone is not an artifact receipt. Consult the [official rules](https://docs.nlr.gov/docs/fy26osti/96647.pdf). No upload or slot choice is performed by this repository.

## Checks and reproducibility

The frozen experiment has completed; **do not rerun it or alter its output based on the failed uniqueness result.** A future experiment requires a new preregistration. Repository checks for this work include:

```bash
python -m pytest tests -q
python scripts/check_site.py
python scripts/check_submission.py --report evidence/h61u_format_validation.json  # expected exit 2: NOT_RUN_NO_CANDIDATE
python -m compileall -q src scripts tests

git diff --check
```

The submission-byte checker cannot validate H61U because no file was written. It must not silently validate one of the historical rasters in its place. Its expected exit 2 is only a no-candidate report, not a passing GeoTIFF-format validation; the JSON receipt is `evidence/h61u_format_validation.json`. Current run evidence: `evidence/h61u_run_card.json`, with a compact copy at `docs/data/h61u_outcome_summary.json`. The static site is checked by `.github/workflows/pages.yml`; unit tests are checked by `.github/workflows/verify.yml`.

## Repository areas

- `scripts/run_h61u.py` — frozen H61U run driver; it passed the pre-placement surface test, completed the spatial holdout, then stopped at the final-dot gate.
- `src/gems61/uniqueness.py`, `scripts/refresh_registry.py`, `evidence/registry_refreshed.json` — strict comparison; the checked-in H61U manifest has 748 sibling rasters, and future refreshes also include local historical TIFFs.
- `src/gems61/buried.py`, `src/gems61/holdout.py`, `src/gems61/evaluate_holdout.py`, `src/gems61/submission_writer.py` — shared physical, evaluation, and writer modules.
- `evidence/h61u_preregistration.json`, `evidence/h61u_first_attempt.json`, `evidence/h61u_run_card.json` — frozen plan, invalid attempt, and final stop receipt.
- `docs/` — current public evidence pages and JSON. Historical TIFs are retained for provenance but not linked as current downloads.
- `FINAL_REPORT.md`, `SUBMISSION_READY.md`, `SESSION_SUMMARY.md` — current outcome summaries; none authorizes a download or submission.

## Core values

**Maximize P(Win)** and **Own the Outcome**. A strict duplicate gate and a no-gain comparison are not reasons to manufacture a candidate. The responsible outcome for this run is to stop, report the local evidence with its limitations, and preserve a negative result rather than spend a weekly slot on an unqualified file.
