# Submission status — NOT READY

**Current candidate:** none. **Download permission:** NO. **Submission recommendation:** NOT RECOMMENDED. **Weekly slot approved:** NO. **Organizer-confirmed score:** none.

The frozen H61U-H1 experiment completed the spatial holdout, but its final-dot comparison exceeded the strict uniqueness threshold in the accessible sibling registry, which excludes this repository's historical TIFFs. The runner stopped before writing a TIFF. Do not download or submit an older file in `docs/downloads/` or `docs/submissions/` as a replacement; those are historical artifacts from other runs.

## What the evidence says

Every metric below is a local holdout result, not an organizer score.

| Arm/control | Evidence label | Value and interval |
|---|---|---|
| H61U-H1 | HOLDOUT-DTI · evaluator `gems61-pooled-hide-v2` · 12,074 withheld positives | 0.041351; 95% CI 0.035332–0.048100 |
| Unfiltered HGM maxima | HOLDOUT-DTI · evaluator `gems61-pooled-hide-v2` · 12,074 withheld positives | 0.044359; 95% CI 0.036847–0.051764 |
| Matched random lines | HOLDOUT-DTI · evaluator `gems61-pooled-hide-v2` · 12,074 withheld positives | 0.016030; 95% CI 0.010328–0.021541 |

H1 beat random lines, but the paired H1-minus-HGM difference was **−0.003009** (95% CI **−0.010105 to +0.004951**): there is no demonstrated gain over the strongest simple control.

The accessible sibling-repository registry contained 748 aligned rasters and excluded this repository's archived TIFFs. Pre-placement surface comparison passed (worst Spearman rho 0.030846). Final-dot uniqueness **failed**: 70 registry entries crossed the strictly greater-than-70% overlap rule; maximum overlap within three pixels was 1.0. This is a fail-closed duplicate stop under the preregistered rule, not proof of copying. No post-hoc dot pruning, tuning, writer invocation, format validation, or upload followed.

## Artifact fields

| Field | Value |
|---|---|
| TIF / ZIP | None; no candidate artifact written |
| Raster SHA-256 | None |
| Byte-level format validator | Not run; no candidate bytes exist |
| Submission name | None |
| Submission note | None |
| Organizer receipt / score | None |

## Separate decisions

- **Is it okay to download a current candidate?** No. No candidate passed the final uniqueness gate, and no H61U TIF exists.
- **Is H61U-H1 recommended for submission?** No. The uniqueness stop is decisive; H1 also did not show a holdout gain over unfiltered HGM maxima.
- **Is a weekly slot approved?** No. A selector decision is separate from local evaluation and none is recorded.

## Evidence and next responsible work

- [Current site status](docs/index.html)
- [Executive guide](docs/executive-summary.html)
- [H61U run card](docs/run-card.html)
- Full receipt: `evidence/h61u_run_card.json`; compact outcome: `evidence/h61u_outcome_summary.json`
- Frozen registration: `evidence/h61u_preregistration.json`
- Invalid first attempt (transient metrics discarded): `evidence/h61u_first_attempt.json`

GP-1012 remains unavailable in full locally, so absolute depth-scale calibration is blocked. Organizer band 15 and literature quantiles were not substituted. H61U-H2 and H61U-H3 are prospective, untested hypotheses—not authorized fallbacks. A later experiment needs a new preregistration and a new blinded evaluation; it must not tune the dots based on this failed uniqueness scan.

## If a future candidate is authorized

Only after an independently registered candidate passes spatial holdout, the accessible sibling-registry surface and dot gates plus comparison against this repository's archived TIFFs, and byte-level validation against the official template should the eligible team sign in to [DrivenData competition #306](https://www.drivendata.org/competitions/306/competition-doe-gems/), open its submission interface, upload the exact validated TIFF, enter the approved submission name and ≤140-character note, and follow the active weekly cap/selector process. Retain the artifact-linked receipt and SHA-256. This repository has not uploaded any file and does not approve a weekly slot.
