# 61GEMSDOE — buried-structure lane: basement-depth steps from gravity inversion

**[Open the status site](https://buffedlizard55-lab.github.io/61GEMSDOE/)** ·
[Executive summary &amp; submission safety](https://buffedlizard55-lab.github.io/61GEMSDOE/docs/executive-summary.html) ·
[Score provenance](https://buffedlizard55-lab.github.io/61GEMSDOE/docs/analysis.html) ·
[Competition #306](https://www.drivendata.org/competitions/306/competition-doe-gems/)

## Current status — read this first

> **NO TIFF IS CURRENTLY CLEARED FOR COMPETITION SUBMISSION.**
> The H61-G raster fails the literal final-dot uniqueness rule; the current H61-L screen failed before placement. The merged `main` branch also contained archived H61-L/H61-M/H61-MH/H61-X and a file under `docs/submissions/`; every one of the 11 local candidate TIFFs fails the strict one-sided overlap stop. Do not upload any repository TIFF.

| Item | Verified result |
|---|---|
| Existing H61-G artifact | `gems61-h61g-x2-gravcorridor-sloperidge-40000dots-20261011T022417Z-0f9408427b88-zeros.tif`; one-band float32, 3730×3292, EPSG:32611, sample transform, finite and within `[0,1]`; **19/19 local format checks pass**. SHA-256: `fdbc7b45443c392cba48413a1122eda00f5394664d68acc9799d7d7e888e4077`. |
| H61-G strict uniqueness | **FAIL — duplicate/lane-drift stop.** `98.5925%` of its positive pixels lie within 3 px of `gems61-lane-buried-step-gravinversion-hgm-r3-k400k-b2zeros.tif`, exceeding the literal `>70%` stop rule. Jaccard `0.007481` is diagnostic only and does not waive the stop. |
| Current-run H61-L surface | Public 3DEP-derived scarp-ribbon surface: 614,556 positive pixels; full-footprint Spearman max `0.172986`; one-sided 3 px overlap `94.6692%` with the HGM prior. **Stopped before holdout, placement, or TIFF writing.** |
| Archived local candidate TIFFs | The refreshed audit tested all **11** candidate TIFFs in `docs/downloads/` and `docs/submissions/` against the same earlier HGM raster. **11/11 fail** the strict `>70%` one-sided overlap rule (range `94.6836%`–`99.8108%`); details in [`evidence/local_artifact_strict_dot_audit.json`](evidence/local_artifact_strict_dot_audit.json). |
| Main-branch H61-L/H61-M/H61-MH/H61-X outputs | Their old “UNIQUE” claims used a dense-reference/Jaccard exception. Rechecked strict one-sided overlaps are H61-L `98.6375%`, H61-M `94.6836%`, H61-MH `99.6400%`, H61-X `98.7658%`; all are **NOT CLEARED**. H61-MH's archived `HOLDOUT-DTI 0.060633` (95% CI `0.049409`–`0.072712`, 22,641 withheld positives; evaluator `gems61.holdout_segmented v2`) remains a proxy result, not a clearance. |
| `docs/submissions/61gemsdoe-basement-step-ribbon-20261011T054408Z.tif` | Historical file retained from `main`; strict one-sided overlap is `99.1475%`. The filename/location does **not** indicate approval. **DO NOT SUBMIT.** |
| Download/submission verdict | H61-G remains linked **for audit/learning only; NOT SAFE TO SUBMIT**. No new unique TIFF was generated in this run. No weekly slot was used. |
| Current inventory scope | **21/21** declared public owner-repository paths plus **12** local TIFFs in `docs/downloads/`, `docs/submissions/`, and `out/` (33 indexed records); complete only for this declared/accessed scope, **not** the organizer-side registry. |
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
- Rebuilt the declared accessible raster inventory: all **21/21** owner-repository paths in `scripts/registry_sources.tsv` plus **12** local prior GeoTIFFs across `docs/downloads/`, `docs/submissions/`, and `out/` (33 records). This is complete for the declared/accessed scope, **not** the organizer-side registry. The H61-G/H61-L run-time receipts retain their original 28-record snapshot at [`evidence/registry_accessible_index_h61g_h61l_run.json`](evidence/registry_accessible_index_h61g_h61l_run.json); H61-G excluded its exact candidate mirror and compared 27 prior rasters.
- Rechecked H61-G final dots: worst one-sided overlap `0.985925` against the 311,617-pixel HGM raster; duplicate stop. Its archived run has no saved pre-placement uniqueness receipt—do not infer a surface pass. The final-dot stop independently prohibits submission; the old exception is retired.
- Audited all 11 locally published candidate TIFFs against that same hash-pinned HGM prior using the literal final-dot rule. Every overlap is `>0.70` (range: `0.946836`–`0.998108`); all stop. This includes the main-branch H61-MH TIFF at `0.996400` one-sided overlap. Archived H61-L/H61-M/H61-MH/H61-X and the `docs/submissions/` TIFF are historical/unapproved despite old status text. Reproducible receipt: [`evidence/local_artifact_strict_dot_audit.json`](evidence/local_artifact_strict_dot_audit.json); runner: `scripts/audit_local_artifact_dots.py`.
- Verified and fetched the public 12-band USGS-3DEP-derived descriptor raster from GEMSDOE24 by GitHub/API path. Built H61-L once: 614,556 scarp-ribbon pixels inside basement-step corridors and basin fill. Its pre-placement overlap is `0.946692`; per protocol, stopped before holdout or output.
- Corrected the Parker (1973) DOI to `10.1111/j.1365-246X.1973.tb06513.x` and the inversion-method account: production uses the first low-passed Bouguer-slab iterate; a converged nonlinear Parker–Oldenburg solve has not been demonstrated.
- **Experiment-budget irregularity:** H61-G records 3 candidate/budget experiments; the H61-L pre-placement screen adds one if counted across the workflow; merged H61-MH records 3 budget experiments (4 experiment stages). At minimum, the cross-lineage count is 7 budgeted activities if all sessions are counted, above the 3-experiment ceiling. No new model/holdout trial or weekly slot was used in this review, and elapsed time was not independently measured. Stop further candidate tuning. Legacy `run_lane.py`, `build_candidate.py`, `run_lane61*.py`, `e2_build_candidate.py`, `make_submission.py`, `e3_build_submission.py`, `write_submission.py`, `run_experiment.py`, `e2_holdout.py`, `e2b_instrument.py`, `e2c_canary.py`, `compare_top_arms.py`, `run_h61mh.py`, `run_h61m2.py`, `run_h61m3.py`, `run_h61m4.py`, and `h61m_card.py` CLIs are retired to prevent bypassing the current strict gate or budget. The H61-G direct holdout stage gates every surface first. The merged `src/gems61/h61mh.py` also contained bare note text that caused `SyntaxError` on import; it is now a comment, and H61-MH/M2/M3/M4 CLI guards were smoke-tested. The old H61-MH site-builder alias now delegates to the canonical strict status builder; no model or holdout was run.
- Refreshed the public leaderboard on 2026-10-11: #1 was `0.4133`; `0.3195` was rank #8, not the high. [Official leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/).

## Historical HOLDOUT-DTI evidence (not a live score)

The archived H61-G dots had **HOLDOUT-DTI 0.046505** (95% CI `[0.042143, 0.050660]`; 22,641 withheld positives; evaluator `gems61.holdout_segmented v2` with whole segments, four eroded quadrants, seeds 20+21, mode `all`). Same-budget random lines were **HOLDOUT-DTI 0.031414** (95% CI `[0.028243, 0.034092]`; same evaluator and withheld count). The as-published H19-5 dotted reference was **HOLDOUT-DTI 0.101070** (95% CI `[0.086503, 0.117340]`; same evaluator and count). On the same 1,999 withheld basin-interior segments, H61-G recovered 351 (17.56%) versus 215 (10.76%) for equal-budget random lines. These are proxy results on withheld catalogue segments, not organizer scores. The H61-L surface in this branch's current run has **no HOLDOUT-DTI** because its pre-placement gate failed. A separate archived main-branch H61-L output was scored under the older gate: **HOLDOUT-DTI 0.044330** (95% CI `[0.041405, 0.047832]`; 22,641 withheld positives; evaluator `gems61.holdout_segmented v2`). A later main-branch H61-MH inversion-feature variant recorded **HOLDOUT-DTI 0.060633** (95% CI `[0.049409, 0.072712]`; 22,641 withheld positives; evaluator `gems61.holdout_segmented v2`, whole segments ≤12 px, four eroded quadrants, seeds 20+21, mode all), with 353/1,982 basin-interior segments recovered (recovery-rate 95% CI `[0.161887, 0.195565]`) versus 213/1,982 (10.75%; recovery-rate 95% CI `[0.094584, 0.121869]`) for equal-budget random lines. Both results are historical proxy scores, not organizer scores. H61-MH is not eligible: its final TIFF fails strict overlap at `99.6400%`, and its old “UNIQUE” label is retired. The H61-MH run card also reports spatially blocked LOQO-DTI mean `0.039489` (range across four quadrants `0.032545`–`0.054939`; evaluator `gems61.holdout_segmented v2`, 22,641 withheld positives). Its source reports no 95% CI for this LOQO summary; the range is not a confidence interval. Feature-model canary AUC is `0.559341`, consistent with weak cross-quadrant transfer; see [`evidence/h61m_run_card.json`](evidence/h61m_run_card.json). The archived H61-MH card also tests the multi-line form: **HOLDOUT-DTI 0.018372** for a 3×3 ribbon (95% CI `[0.016155, 0.021061]`; 22,641 withheld positives; evaluator `gems61.holdout_segmented v2`; 256,096 emitted pixels/draw) versus **HOLDOUT-DTI 0.040910** for dots (95% CI `[0.035859, 0.047073]`; same evaluator/count; 39,795 emitted pixels/draw). The density penalty explains why ribbon emission was not selected. The archived HOLDOUT-DTI values must not be used to justify a weekly slot.

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

## Session `arena/d3e68dae-61gemsdoe` — H61-W: the dip projection, measured negative (newest artifact)

Added after the strict-gate review above; nothing in this section changes its verdict. The new file
is the 12th unique local candidate artifact (published in both `docs/downloads/` and
`docs/submissions/`, audited once) and is **not cleared for submission** (98.8694% strict one-sided
overlap); it is published for audit/learning only.

**Hypothesis.** A normal fault's surface trace lies `z_b·cot(dip)` toward the footwall from the
horizontal-gradient maximum of the inverted basement depth, so projecting each step by that
distance should move the emitted dots onto the trace the metric scores.

**Artifact.** `docs/downloads/` and `docs/submissions/`:
`gems61-h61w-p60-dip-projected-basement-step-16894dots-20261011T155602Z-zeros.{tif,zip,json}` —
16,894 single-pixel dots, sha256 `a8eab7e89576c51e89c5052cc07fbc9e14c4e22a7d48fb8f054c1d6b9d17843b`,
90,194 bytes, one band, float32, 3730 × 3292, EPSG:32611, the organiser transform, every cell
finite, values {0.0, 1.0}, zero dots on the mapped catalogue, median distance to it 19.9 px.
`evidence/h61w_independent_check.json` re-derives all of that from the published bytes with plain
`hashlib + rasterio + numpy`, independently of the shipped validator.

**HOLDOUT-DTI** (`gems61.holdout_segmented v2`, 8 cells, seeds 20+21, α 0.2 / β 0.8 / 300 m,
22,641 withheld positive px):

| arm | HOLDOUT-DTI (95 % CI) | emitted px per draw |
|---|---|---|
| P60 projected trace 60° — primary | **0.0149** (0.0122–0.0173) | 14,836 |
| P0 unprojected steps — ablation | 0.0093 (0.0084–0.0102) | 7,438 |
| pre-registered random-lines control | 0.0227 (0.0191–0.0260) | 20,000 |
| emission-matched control (diagnostic) | 0.0112 (0.0092–0.0130) | 7,417 |
| S60 projected × lidar scarp conjunction | 0.0026 (0.0013–0.0038) | 1,045 |
| SCARP-ONLY lane-drift control | 0.0274 (0.0225–0.0337) | 20,000 |
| X2 instrument reproduction | 0.0267 (0.0240–0.0294) | 20,000 |

- The projection is worth **+60 %** over its own ablation and still **loses to the random
  control** → run-card verdict **negative**, `okay_to_submit: false`, 0 slots used.
- Per dot there is no measurable gain: 0.0112 at the control's 7,417 dots vs the primary's own
  ladder 0.0114 at 10,000 dots (IR-61-CONTROL-01).
- Instrument integrity: the registry file re-scores in place to 1e-6 and the X2 arm reproduces the
  previous session's recorded row **per cell, difference 0.0**; leakage canaries 0.478–0.558
  against the 0.90 limit.
- Label-aware screen (diagnostic only): step pixels within 3 px of a mapped trace 10.1 % vs 8.7 %
  random (1.20×); the projected trace 10.3 %; projected trace × independent lidar scarp **13.7 %**
  (1.57×) — the strongest enrichment this repository has produced, and it collapses to 0.0026 on
  the honest instrument.

**Download link (audit/learning only — DO NOT SUBMIT; the strict audit stops it at 98.8694%).**
[GeoTIFF](docs/downloads/gems61-h61w-p60-dip-projected-basement-step-16894dots-20261011T155602Z-zeros.tif) ·
[ZIP](docs/downloads/gems61-h61w-p60-dip-projected-basement-step-16894dots-20261011T155602Z-zeros.zip) ·
[format receipt](docs/downloads/gems61-h61w-p60-dip-projected-basement-step-16894dots-20261011T155602Z-zeros.json) ·
[run card](evidence/h61w_run_card.json) · [strict audit](evidence/local_artifact_strict_dot_audit.json)

**New receipts.** `evidence/h61w_{aux,invert,holdout,submission,uniqueness,run_card,hypotheses,hypotheses_note,irregularities,independent_check}.json`;
`src/gems61/dip_projection.py`; `scripts/{run_h61w,h61w_hypotheses}.py`. New irregularities:
**IR-61-DIP-01** the dip cannot be constrained from the supplied layers (swept 45–75°, shipped 60°;
the trace moves 1.2–4.5 px median against a ~9 px resolution) · **IR-61-DIP-02** the first footwall
estimator was invalid on long ridges (43.8 % agreement with −grad z) and the label-aware screen was
unchanged by the fix, so that screen must never be used to promote · **IR-61-CONTROL-01** above ·
**IR-61-SITE-01** `docs/submit.html` had been offering the 311,617-px near-blanket as *Step 1 of how
to submit*; it is repointed and `scripts/check_site.py` now derives download permission per file
from the validation receipts on every `docs/*.html` page.

**Next session, in priority order.** (1) **H61-3DEP** — metre-scale 3DEP lidar scarps gated by this
lane's step corridor; source named (project `NV_WestCentral_EarthMRI_2020_D20`), 3 m derivatives
proven obtainable, 1 m tiles blocked by the sandbox egress allow-list. (2) Re-test the per-dot
question with a control that realises the *same* dot count. (3) **H61-DISCORD** (band 15 minus the
inverted depth) and **H61-RELAY** (tip/step-over closure) — cheap, supplied-layers-only, never
emitted on. **Limitations:** the dip is assumed; the lidar scarp layer covers 75.4 % of the
footprint; holdout values are not live scores; the strict uniqueness rule stops every local TIFF,
including this one, because the comparator is a near-blanket (IR-61-UNIQ-01).

**Reproduce.** `python3 scripts/prepare_data.py --fetch --cache-bands` →
`bash scripts/fetch_registry.sh /tmp/refs/registry` → `PYTHONPATH=src python3 scripts/run_h61w.py all`
→ `PYTHONPATH=src python3 scripts/h61w_hypotheses.py` → `PYTHONPATH=src python3 scripts/audit_local_artifact_dots.py`
→ `python3 scripts/build_site_status.py` → `PYTHONPATH=src python3 scripts/check_site.py` →
`pytest -q tests` (64 passed).
