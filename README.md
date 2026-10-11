# 61GEMSDOE — buried-structure lane: basement-depth steps from gravity inversion

**[Open the status site](https://buffedlizard55-lab.github.io/61GEMSDOE/)** ·
[Executive summary &amp; submission safety](https://buffedlizard55-lab.github.io/61GEMSDOE/docs/executive-summary.html) ·
[Score provenance](https://buffedlizard55-lab.github.io/61GEMSDOE/docs/analysis.html) ·
[Competition #306](https://www.drivendata.org/competitions/306/competition-doe-gems/)

## Current status — read this first

> **NO TIFF IS CURRENTLY CLEARED FOR COMPETITION SUBMISSION.**
> The H61-G raster fails the literal final-dot uniqueness rule; the current H61-L screen failed before placement. The merged `main` branch also contained archived H61-L/H61-M/H61-X and a file under `docs/submissions/`; every one of the 10 local candidate TIFFs fails the strict one-sided overlap stop. Do not upload any repository TIFF.

| Item | Verified result |
|---|---|
| Existing H61-G artifact | `gems61-h61g-x2-gravcorridor-sloperidge-40000dots-20261011T022417Z-0f9408427b88-zeros.tif`; one-band float32, 3730×3292, EPSG:32611, sample transform, finite and within `[0,1]`; **19/19 local format checks pass**. SHA-256: `fdbc7b45443c392cba48413a1122eda00f5394664d68acc9799d7d7e888e4077`. |
| H61-G strict uniqueness | **FAIL — duplicate/lane-drift stop.** `98.5925%` of its positive pixels lie within 3 px of `gems61-lane-buried-step-gravinversion-hgm-r3-k400k-b2zeros.tif`, exceeding the literal `>70%` stop rule. Jaccard `0.007481` is diagnostic only and does not waive the stop. |
| Current-run H61-L surface | Public 3DEP-derived scarp-ribbon surface: 614,556 positive pixels; full-footprint Spearman max `0.172986`; one-sided 3 px overlap `94.6692%` with the HGM prior. **Stopped before holdout, placement, or TIFF writing.** |
| Archived local candidate TIFFs | The refreshed audit tested all **10** TIFFs in `docs/downloads/` and `docs/submissions/` against the same earlier HGM raster. **10/10 fail** the strict `>70%` one-sided overlap rule (range `94.6836%`–`99.8108%`); details in [`evidence/local_artifact_strict_dot_audit.json`](evidence/local_artifact_strict_dot_audit.json). |
| Main-branch H61-L/H61-M/H61-X outputs | Their old “UNIQUE” claims used a dense-reference/Jaccard exception. Rechecked strict one-sided overlaps are H61-L `98.6375%`, H61-M `94.6836%`, H61-X `98.7658%`; all are **NOT CLEARED**. |
| `docs/submissions/61gemsdoe-basement-step-ribbon-20261011T054408Z.tif` | Historical file retained from `main`; strict one-sided overlap is `99.1475%`. The filename/location does **not** indicate approval. **DO NOT SUBMIT.** |
| Download/submission verdict | H61-G remains linked **for audit/learning only; NOT SAFE TO SUBMIT**. No new unique TIFF was generated in this run. No weekly slot was used. |
| Current inventory scope | **21/21** declared public owner-repository paths plus **11** local TIFFs in `docs/downloads/`, `docs/submissions/`, and `out/` (32 indexed records); complete only for this declared/accessed scope, **not** the organizer-side registry. |
| Organizer score | None for this repository's artifacts. The owner-reported H33 value `0.2778` has no located receipt tying exact bytes to an organizer leaderboard row. |

**[↓ Download the H61-G diagnostic TIFF — DO NOT SUBMIT](docs/downloads/gems61-h61g-x2-gravcorridor-sloperidge-40000dots-20261011T022417Z-0f9408427b88-zeros.tif)** ·
[diagnostic ZIP](docs/downloads/gems61-h61g-x2-gravcorridor-sloperidge-40000dots-20261011T022417Z-0f9408427b88-zeros.zip) ·
[format receipt](docs/downloads/gems61-h61g-x2-gravcorridor-sloperidge-40000dots-20261011T022417Z-0f9408427b88-zeros.json) ·
[current run card](evidence/h61l_run_card.json) · [strict uniqueness evidence](evidence/h61g_uniqueness.json) · [H61-L surface stop](evidence/h61l_surface.json)

**Historical file under `docs/submissions/` — DO NOT SUBMIT (99.1475% strict overlap):**
[download archived TIFF](docs/submissions/61gemsdoe-basement-step-ribbon-20261011T054408Z.tif) · [strict local-artifact audit](evidence/local_artifact_strict_dot_audit.json)

The attached 133-character note is `H61-G: GP-1012-calibrated gravity inversion -> basement-step corridor x in-corridor slope ridge; 40000 dots at 3 px spacing; UNSCORED`. It belongs to the archived diagnostic file and must not be reused as a submission note.

## What was done in this continuation

- Replaced the prior dense-reference/Jaccard exception with one literal shared gate: signed full-footprint Spearman `>0.90` **or** more than `70%` of candidate positive pixels within 3 px of any single prior raster. The check counts every strictly positive value, runs before placement and on final output, and fails closed on incomplete inventories, missing files, hash mismatches, or grid errors.
- Rebuilt the declared accessible raster inventory: all **21/21** owner-repository paths in `scripts/registry_sources.tsv` plus **11** local prior GeoTIFFs across `docs/downloads/`, `docs/submissions/`, and `out/` (32 records; `out/` currently adds no TIFF). This is complete for the declared/accessed scope, **not** the organizer-side registry. The H61-G/H61-L run-time receipts retain their original 28-record snapshot at [`evidence/registry_accessible_index_h61g_h61l_run.json`](evidence/registry_accessible_index_h61g_h61l_run.json); H61-G excluded its exact candidate mirror and compared 27 prior rasters.
- Rechecked H61-G final dots: worst one-sided overlap `0.985925` against the 311,617-pixel HGM raster; duplicate stop. Its archived run has no saved pre-placement uniqueness receipt—do not infer a surface pass. The final-dot stop independently prohibits submission; the old exception is retired.
- Audited all 10 locally published candidate TIFFs against that same hash-pinned HGM prior using the literal final-dot rule. Every overlap is `>0.70` (worst range: `0.946836`–`0.998108`); all stop. The archived main-branch H61-L/H61-M/H61-X and the `docs/submissions/` TIFF are historical/unapproved despite old status text. Reproducible receipt: [`evidence/local_artifact_strict_dot_audit.json`](evidence/local_artifact_strict_dot_audit.json); runner: `scripts/audit_local_artifact_dots.py`.
- Verified and fetched the public 12-band USGS-3DEP-derived descriptor raster from GEMSDOE24 by GitHub/API path. Built H61-L once: 614,556 scarp-ribbon pixels inside basement-step corridors and basin fill. Its pre-placement overlap is `0.946692`; per protocol, stopped before holdout or output.
- Corrected the Parker (1973) DOI to `10.1111/j.1365-246X.1973.tb06513.x` and the inversion-method account: production uses the first low-passed Bouguer-slab iterate; a converged nonlinear Parker–Oldenburg solve has not been demonstrated.
- **Experiment-budget irregularity:** the archived H61-G card records 3 candidate/budget experiments, and the H61-L pre-placement screen adds one if counted across the whole workflow (aggregate 4). No additional model/holdout trial or weekly slot was used in this review; do not exceed the budget with more tuning. Legacy `run_lane.py`, `build_candidate.py`, `run_lane61*.py`, `e2_build_candidate.py`, `make_submission.py`, `e3_build_submission.py`, `write_submission.py`, `run_experiment.py`, `e2_holdout.py`, `e2b_instrument.py`, `e2c_canary.py`, and `compare_top_arms.py` CLIs are retired to prevent bypassing the current strict gate or budget. The H61-G direct holdout stage now gates every surface first. Elapsed time was not independently measured.
- Refreshed the public leaderboard on 2026-10-11: #1 was `0.4133`; `0.3195` was rank #8, not the high. [Official leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/).

## Historical HOLDOUT-DTI evidence (not a live score)

The archived H61-G dots had **HOLDOUT-DTI 0.046505** (95% CI `[0.042143, 0.050660]`; 22,641 withheld positives; evaluator `gems61.holdout_segmented v2` with whole segments, four eroded quadrants, seeds 20+21, mode `all`). Same-budget random lines were **HOLDOUT-DTI 0.031414** (95% CI `[0.028243, 0.034092]`; same evaluator and withheld count). The as-published H19-5 dotted reference was **HOLDOUT-DTI 0.101070** (95% CI `[0.086503, 0.117340]`; same evaluator and count). On the same 1,999 withheld basin-interior segments, H61-G recovered 351 (17.56%) versus 215 (10.76%) for equal-budget random lines. These are proxy results on withheld catalogue segments, not organizer scores. The H61-L surface in this branch's current run has **no HOLDOUT-DTI** because its pre-placement gate failed. A separate archived main-branch H61-L output was scored under the older gate: **HOLDOUT-DTI 0.044330** (95% CI `[0.041405, 0.047832]`; 22,641 withheld positives; evaluator `gems61.holdout_segmented v2`). That historical score does not restore eligibility: its final TIFF fails strict overlap at `98.6375%`, and its old “UNIQUE” label is retired.

## Score provenance and leaderboard context

`reports/forensics.json` labels the H33 `0.2778` value as `claimed_score_by_group`; its irregularities section says no organizer receipt ties those bytes to a leaderboard row. Raster forensics do measure that the H33 file is a strict subset of the 44,090-pixel H19-5 core, with 6,436 pixels removed, all within 3 px of the mapped catalogue. That is a verified construction relationship, not independent confirmation of the reported live score. The official board is separate: as fetched 2026-10-11, #1 was 0.4133 and #8 was 0.3195.

## Ranked next hypotheses

Five candidates with layers, physical signatures, catalogue-gap rationale, difference from implemented work, expected-gain ranking, and cost are documented in [the hypotheses page](docs/hypotheses.html) and [`evidence/h61g_hypotheses.json`](evidence/h61g_hypotheses.json). H61-L (3DEP scarp ribbons in a gravity-step corridor) ranked first. The current-run surface failed the literal uniqueness gate, so that candidate was not holdout-scored. A different archived main-branch H61-L variant has historical HOLDOUT-DTI evidence, but its TIFF fails the strict final-dot gate and is not eligible. The remaining hypotheses are projections, not measured scores.

## Reproduce the checks

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
PYTHONPATH=src .venv/bin/python scripts/prepare_data.py --fetch --cache-bands
bash scripts/fetch_registry.sh
PYTHONPATH=src .venv/bin/python scripts/build_registry_index.py --public-cache /tmp/refs/registry
PYTHONPATH=src .venv/bin/python scripts/audit_local_artifact_dots.py
PYTHONPATH=src .venv/bin/python scripts/run_h61g.py unique
PYTHONPATH=src .venv/bin/python -m pytest -q tests
PYTHONPATH=src .venv/bin/python scripts/build_site_h61g.py
```

`prepare_data.py --fetch --cache-bands` was verified in this workspace: all pinned official/external inputs passed and 19 bands were cached. The ignored 12-band lidar descriptor cache is separately SHA-256 pinned in `evidence/h61l_lidar_source.json`. The registry fetch script is driven by the single tracked source list `scripts/registry_sources.tsv`.

## Core values

**Maximize P(Win)** and **Own the Outcome**: the false Jaccard exemption was removed; the duplicate stop is reported instead of hidden; the best novel surface was stopped before any weekly slot; and no unverified score is presented as organizer-confirmed.

---

## The standing brief (verbatim — re-read at the start of every session)

## THE LANE (highest urgency)

MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION. DO NOT COPY A PREVIOUS
SUBMISSION UNLESS IT'S FOR LEARNING AND EDUCATION. BUT WE MUST GENERATE A UNIQUE TIF
SUBMISSION. IT MUST BE OBVIOUS WHETHER IT IS OK TO DOWNLOAD AND SUBMIT THE GENERATED
TIF SUBMISSION.

There should be an easy to download submission tif file as described by the prompt.

**Buried-structure lane: basement-depth steps from gravity inversion.** Alluvial cover
is one reason catalogues miss faults. Parker (1973) and Oldenburg (1974) give the
standard iterative inversion of gravity to basement relief, and Blakely and Jachens
(GSA Bulletin, 1991) applied it to isostatic residual gravity in Nevada to map the
pre-Tertiary surface. Invert the provided isostatic-gravity layer. Use the USGS Basin
and Range basin-depth maps (Saltus and Jachens, GP-1012, 1995) only to calibrate the
density-contrast depth scale, since they are regional (1:2.5M). Map maxima of the
horizontal gradient of basement depth as candidate buried range-front or intrabasin
faults. Gravity resolves such steps only to a few hundred metres at best, so emit
multi-line ribbons rather than thin lines. Report how many withheld basin-interior
segments the steps recover versus random lines. Treat density contrasts within
basement as the competing explanation. Output the standard validated GeoTIFF,
uniqueness-checked against every earlier raster.

## PARALLEL-RUN PROTOCOL

1. **LANE.** Your lane is the single method paragraph above. Stay inside it. If your
   raster's rank-correlation with any registry raster exceeds 0.90, or more than 70% of
   your dots fall within 3 px of one registry raster's dots, you have drifted into
   another lane: log it as a duplicate and stop. Check this on the surface before
   placement AND on the final dots.
2. **REUSE, DON'T REBUILD.** Use the template's cached feature stack,
   `evaluate_holdout.py` and `submission_writer.py`. Holdout = hide-and-recover:
   withhold whole fault segments with a buffer, derive every catalogue-based feature
   only from the visible faults, mask visible faults pixel-exactly, score pooled DTI
   (alpha 0.2, beta 0.8, 300 m triangular kernel). If a shared tool is wrong, fix it
   once in the template and report it; never keep a private fork.
3. **LABEL EVERY NUMBER** as HOLDOUT-DTI (evaluator version, number of withheld
   positives, 95% CI) or ORGANIZER-CONFIRMED (copied from a submission-page receipt).
   A projection is never written as a score.
4. **LEAKAGE CANARY.** Test each feature alone on the holdout before trusting any
   result. AUC above 0.90 means leakage until proven otherwise.
5. **RUN CARD.** End with one JSON card: hypothesis; mechanism; the named non-fault
   process that could mimic it; holdout DTI + CI; correlation/overlap vs registry;
   raster sha256; validator output (no NaN inside the footprint, values in [0,1],
   CRS/shape/transform match); submission name + note of at most 140 characters;
   verdict promote / negative. Negative results are deliverables.
6. **BUDGET.** Stop after 3 experiments or 2 hours. Do not pick submissions: promotion
   to a real slot is a separate selector step, within the weekly cap shown on the
   submission page.

## Standing requirements that apply to every session

- Work line by line verifying from official verified trusted sources; provide links for
  manual review. No manual input; no hallucinations. Flag any irregularities.
- The site must make the download obvious: an easy one-click TIF download in the
  executive summary / at the very beginning of the site, with a clear statement of
  whether it is OK to download and submit.
- Give the submission a unique name and a short note (<= 140 characters) for the
  submission form's Note field.
- Explain exactly how to make a submission into the contest (executive-summary
  subpage).
- Generate 3-5 candidate geological hypotheses not yet tried, naming layers, physical
  signature, why it catches a fault the catalogue lacks, and how it differs from
  anything already implemented; rank by expected DTI improvement and implementation
  cost; validate the top candidate on the spatially-blocked holdout before touching a
  weekly submission slot.
- Put this prompt into the repo README and read it every time we work on the project.
- Core values: **Maximize P(Win)** and **Own the Outcome** - own results end to end,
  treat failure and success as signals, stay accountable for the final outcome.
- Before finishing: run the project's own check over the code you changed, and say what
  you ran and what came back.

## Official links for manual review

| what | link |
| --- | --- |
| competition landing page | https://www.drivendata.org/competitions/306/competition-doe-gems/ |
| problem description + submission format + metric | https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/ |
| about page / resources | https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/ |
| data tab (login required) | https://www.drivendata.org/competitions/306/competition-doe-gems/data/ |
| leaderboard | https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/ |
| official rules PDF | https://docs.nlr.gov/docs/fy26osti/96647.pdf |
| reference solution | https://github.com/drivendataorg/gems-prize-reference-solution |
| GeoDAWN airborne magnetic + radiometric surveys | https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and |
| INGENIOUS (Great Basin conductivity / magnetotelluric project) | https://gbcge.org/current-projects/ingenious/ |
| EPSG:32611 | https://epsg.io/32611 |
| Tversky index | https://en.wikipedia.org/wiki/Tversky_index |
| GDR submission 1391 (competition data mirror) | https://gdr.openei.org/submissions/1391 |

## Sandbox limitation (measured, not assumed)

Egress from the development sandbox admits only `github.com`, `api.github.com`,
`codeload.github.com`, `registry.npmjs.org`, `pypi.org` and `files.pythonhosted.org`.
`drivendata.org`, `docs.nlr.gov`, `usgs.gov`, `earthquake.usgs.gov` and
`raw.githubusercontent.com` all fail (SSL_ERROR_SYSCALL / HTTP 000). The competition
rasters are therefore obtained from the hash-pinned GitHub mirror
`buffedlizard55-lab/6GEMSDOE@main:data/bridge/` and every digest is re-verified
locally against the mirror manifest before use.

### Additional instructions recorded from the 2026-10-11 session task

- Give a PhD-level explanation of why submission `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros` (repository GEMSDOE32, site https://buffedlizard55-lab.github.io/GEMSDOE32/) scored 0.2778 and whether we can beat it; the sibling repositories (GEMSDOE36, GEMSDOE33, GEMSDOE48, GEMSDOE24, GEMSDOE31, 57GEMSDOE, 19GEMSDOE, 20GEMSDOE, GEMSDOE46, GEMSDOE16) are to be studied, never copied.
- The earlier upload error "Predicted values must be in range [0, 1]" must never recur; explain exactly how to submit on an executive-summary subpage.
- Keep a clean GitHub Pages site; run three passes (implement and verify; bug review; full re-check); then create the PR, merge to `main`, and list the remaining work and limitations.
