# Submission status — NOT READY

**As of 2026-10-11: NO TIFF IN THIS REPOSITORY IS CLEARED FOR COMPETITION SUBMISSION. Do not upload any repository TIFF or spend a weekly slot.**

The archived H61-G file fails the literal final-dot uniqueness rule. The current-run H61-L surface failed before placement and produced no TIFF. After merging `main`, a hash-checked audit found that all 11 local candidate TIFF artifacts exceed the strict `>70%` one-sided overlap stop against an earlier basement-HGM raster. The old dense-reference/Jaccard exceptions and “UNIQUE” labels are retired.

## Prominent archival warning

`docs/submissions/61gemsdoe-basement-step-ribbon-20261011T054408Z.tif` is a historical file, **not** an approved submission. A strict recheck measured **99.1475%** one-sided positive-pixel overlap within 3 px of the prior HGM raster. **DO NOT SUBMIT.**

The archived H61-L, H61-M, H61-X, and H61-MH files also fail the strict one-sided final-dot gate. H61-MH has a historical `HOLDOUT-DTI` of 0.060633 (95% CI 0.049409–0.072712; 22,641 withheld positives; evaluator `gems61.holdout_segmented v2`), but its TIFF overlaps the pinned comparator by 99.64%, so the result is not submission eligibility. The exact measurements and SHA-256 pins are in [`evidence/local_artifact_strict_dot_audit.json`](evidence/local_artifact_strict_dot_audit.json). The index covers 21 declared public paths and 12 local TIFFs (33 raster records); it is not the organizer's complete registry.

- [Current run card](evidence/h61l_run_card.json)
- [Current accessible raster index](evidence/registry_accessible_index.json)
- [Original H61-G/H61-L run-time index snapshot](evidence/registry_accessible_index_h61g_h61l_run.json)
- [Current status and detailed remaining work](README.md)

## Future upload procedure — only after an eligible run card clears

1. Wait for a new candidate to pass both strict uniqueness phases and local format validation, then beat the holdout best under the recorded selector. Promotion to a weekly slot remains a separate decision.
2. Download only the exact GeoTIFF path and SHA-256 named by that cleared run card; use only its note (maximum 140 characters).
3. Sign in to the [official DrivenData submissions page](https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/), upload that GeoTIFF, paste the note, and save the receipt.
4. Label a score ORGANIZER-CONFIRMED only when a receipt ties it to those exact bytes.

No competition slot has been used and no artifact-bound organizer receipt exists for this repository.
