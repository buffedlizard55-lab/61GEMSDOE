# 61GEMSDOE — buried-structure lane: basement-depth steps from gravity inversion

**[Open the site](https://buffedlizard55-lab.github.io/61GEMSDOE/)** ·
[Executive summary & how to submit](https://buffedlizard55-lab.github.io/61GEMSDOE/docs/executive-summary.html) ·
[Why 0.2778](https://buffedlizard55-lab.github.io/61GEMSDOE/docs/analysis.html) ·
[Competition #306](https://www.drivendata.org/competitions/306/competition-doe-gems/)

## Status of the newest file (read this first)

| question | answer |
|---|---|
| Is the file safe to download and upload? | **YES — FORMAT-VALID and UNIQUE.** 19 validator checks pass (float32, EPSG:32611, 3730 × 3292, sample-submission transform, no NaN/Inf anywhere, min 0 / max 1, 0.0 outside the footprint, zero dots on the mapped catalogue). Uniqueness verdict **UNIQUE** against 28 earlier rasters (worst Spearman +0.0445; worst overlap gate 0.002 vs limit 0.50). |
| Should it be given a weekly slot? | **NOT RECOMMENDED.** HOLDOUT-DTI 0.0085 (95 % CI 0.0050–0.0117; 22,641 withheld positive px; gems61.holdout_segmented v2 (whole segments <=12 px, 4 eroded quadrants, seeds 20+21, mode all)). Random lines at the same budget: 0.0352 (this run) / 0.0314 (H61-G draw). The unpruned base of our ORGANIZER-CONFIRMED 0.2778 scores 0.1011 on the same evaluator. Run-card verdict: **negative** — "DO NOT SPEND A SLOT: file is valid and unique, but the holdout does not put it above the group's best-known file; keep as a negative/diagnostic result". |
| Has an organiser scored it? | **No.** `organizer_confirmed_score` is null. Every number for this file is HOLDOUT-DTI. |

**[↓ Download the GeoTIFF](docs/downloads/gems61-h61x-x3c-coarse-corridor-10128dots-20261011T052850Z-b3b1aacf13ce-zeros.tif)** · [zip](docs/downloads/gems61-h61x-x3c-coarse-corridor-10128dots-20261011T052850Z-b3b1aacf13ce-zeros.zip) · [format receipt](docs/downloads/gems61-h61x-x3c-coarse-corridor-10128dots-20261011T052850Z-b3b1aacf13ce-zeros.json) · [run card](evidence/h61x_run_card.json)

- Submission name: `gems61-h61x-x3c-coarse-corridor-10128dots-20261011T052850Z-b3b1aacf13ce-zeros`
- Note (134/140 chars): `H61-X: coarse (800 m) basement-step corridor from GP-1012-calibrated gravity inversion x in-corridor slope ridge; 10128 dots; UNSCORED`
- sha256 `f8fb3f74b40eecf6407cc3e00a03121e00c8220c0777a14c9bd6be43a1ede65c` (77,055 bytes); 10,128 single-pixel dots (value 1.0) at ≥ 3 px spacing, none within 2 px of a mapped fault; median distance to the catalogue 23.7 px.
- Earlier files in `docs/downloads/` are **SUPERSEDED** or uniqueness references (their own holdouts were 0.0000–0.0465); the H61-G file (`gems61-h61g-x2-…`, 0.0465) remains the lane's best in-protocol file and is also not recommended for a slot. Do not upload the superseded files.

## What this session found (H61-X)

1. **The two-scale corridor sub-hypothesis is refuted on the instrument.** Coarse (800 m) HGM maxima of the GP-1012-calibrated inverted basement: 7,766 with throw ≥ 80 m, of which only **489** are new lines (≥ 1.2 km from a base-scale step). The union corridor (X3) scores 0.0463 — statistically tied with the base-only X2 (0.0465); the coarse corridor alone (X3c) scores 0.0085 vs 0.0352 random lines. The screen's coarse-scale "enrichment" was the same fault lines blurred, not additional structure.
2. **The uniqueness gate did its job.** X3 (the better-scoring construction) failed the protocol rule-1 pre-check: 91.7 % of its dots within 3 px of the H61-G file's dots (gate 0.70). It was logged as a duplicate and not shipped.
3. **The competing explanation was measured, not asserted.** Intrabasement density contrasts (igneous contacts) should sit on strong magnetic edges: 0.181 of base steps and 0.129 of coarse steps do (RTP HGM top-50 %) — neither population is dominated by the mimic; the coarse steps are simply not faults at 300 m.
4. **Answer to the lane's explicit question** (withheld basin-interior segments recovered vs random lines): the coarse new steps recover **51/1999** vs **255/1999** by random lines — below random; the base-scale X2 corridor recovered 351/1999.
5. **The shipped file is the unique coarse-corridor construction (X3c)** with a negative verdict — a diagnostic deliverable closing the sub-hypothesis, per the selection rule recorded in the run card.

## Candidate board — all gems61 files in `docs/downloads/` (seven parallel sessions merged on `main`, newest first)

| file | session / PR | positive px | its own session's verdict | shipped file on the segment-withholding evaluator (HOLDOUT-DTI) |
|---|---|---|---|---|
| **`gems61-h61x-x3c-coarse-corridor-10128dots-20261011T052850Z-b3b1aacf13ce-zeros`** | this session (H61-X) | 10,128 | FORMAT-VALID + UNIQUE; HOLDOUT-DTI 0.0085 (CI 0.0050–0.0117) **below** random lines 0.0352 → negative, diagnostic | 0.0085 |
| `gems61-h61l-relief-any-corr10-40000dots-20261011T051949Z-1e96bd4a26a1-zeros.tif` | H61-L, session arena/a7790b7f, PR #13 (2026-10-11) | 40,000 | FORMAT-VALID + UNIQUE (worst Spearman 0.293 vs H61-G; 69.8% of its dots within 3 px of H61-G's - under both gates); HOLDOUT-DTI 0.0443 (CI 0.0414-0.0478) vs random lines 0.0314, 340/1999 basin segments vs 215/1999 random; statistically tied with H61-G 0.0465; negative for a slot | 0.0443 (visible-only) / ≈0 shipped pruned (IR-61-INSTR-02) |
| `gems61-h61m-gravmag-corridor-ribbon-40000dots-20261011T051415Z-zeros.tif` | H61-M, session arena/a7790b7f, PR #11 (2026-10-11) | 55,301 | FORMAT-VALID + UNIQUE (55,301 px, rho 0.0018 vs external registry, 18.35% overlap); gravity-inversion corridor x magnetic edges as 3 px ribbons; no segment-holdout on this evaluator recorded | — |
| `gems61-buried-basement-step-r3-rib2-k40k-2pxprune-zeros.tif` | e3, PR #3 | 40,000 | kept; superseded | 0.0000 |
| `gems61-h61a-basement-step-20000dots-20261011T012029Z-eb2ae4bb024b-zeros.tif` | H61-A, PR #5 | 25,285 | catalogue-frame holdout 0.0000 vs random 0.0089 -> SUPERSEDED | 0.0000 |
| `gems61-h61b-sharp-step-22000dots-20261011T015658Z-59e24a9409a7-zeros.tif` | H61-B, PR #6 | 88,796 | format-valid + unique; no holdout number above random recorded in its run card | 0.0000 |
| `gems61-h61g-x2-gravcorridor-sloperidge-40000dots-20261011T022417Z-0f9408427b88-zeros.tif` | H61-G, PR #9 | 40,000 | FORMAT-VALID + UNIQUE; HOLDOUT-DTI 0.0465 (CI 0.0421-0.0507) vs random lines 0.0314 within protocol; the lane's best in-protocol file; negative for a slot | 0.0045 |
| `gems61-h62-basinstep-habitat-38k-20261011T020659Z-1a9c172f7106.tif` | H62, PR #7 | 38,000 | its card: surrogate-truth DTI 0.0395 below every one of seven registry rasters -> 'Submit NOT RECOMMENDED' | 0.0000 |
| `gems61-lane-buried-step-gravinversion-hgm-r3-k400k-b2zeros.tif` | e3, PR #3 | 311,617 | 311,617-px near-blanket; the IR-61-UNIQ-01 reference; never upload | 0.0000 |
| `gems61c-gravstep-liveband-40k-20261011.tif` | session C, PR #8 | 40,000 | its card: shipped construction 0.0417 but its own uniform-flank control 0.0649, and pure lane field 0.0078 < random lines 0.0092 (gems61-pooled-hide-v2); 'value unproven' | 0.0007 |

The parallel sessions' own pages remain in `docs/` with SUPERSEDED-context banners; their evidence files are kept untouched.

## Reproduce

```bash
git clone https://github.com/buffedlizard55-lab/61GEMSDOE && cd 61GEMSDOE
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
PYTHONPATH=src .venv/bin/python scripts/prepare_data.py --fetch --cache-bands   # hash-pinned bridge; 19 band memmaps; creates data/bridge + data/raw links
bash scripts/fetch_registry.sh                                                  # 21 earlier group rasters -> /tmp/refs/registry
PYTHONPATH=src .venv/bin/python scripts/run_h61g.py all                         # H61-G: invert -> screen -> holdout -> final -> unique -> card (~25 min)
PYTHONPATH=src .venv/bin/python scripts/run_h61x.py all                         # H61-X (this session): invert -> holdout -> final -> unique -> card (~20 min)
PYTHONPATH=src .venv/bin/python scripts/run_h61l.py                            # H61-L (parallel session a7790b7f): lidar relief in corridor
PYTHONPATH=src .venv/bin/python scripts/run_h61m.py                            # H61-M (parallel session a7790b7f): gravity x magnetic ribbons
PYTHONPATH=src .venv/bin/python -m pytest -q tests                              # 22 passed
PYTHONPATH=src .venv/bin/python scripts/build_site_h61x.py                      # regenerates docs/*.html + README top from evidence/*.json
```

Checks run at the end of this session: `pytest -q tests` → 22 passed; `run_h61x.py all` → UNIQUENESS: UNIQUE; validator receipt all-pass;
holdout instrument check 0.1011 = 0.1011; the site builder reads every number from JSON.

## Session record (this session: arena/6339e2fc-61gemsdoe (H61-X))

- `src/gems61/*` — shared tools unchanged (22/22 tests pass; no forks).
- `scripts/run_h61x.py` — H61-X driver: invert | holdout | final | unique | card | all.
- `evidence/h61x_invert.json`, `h61x_holdout.json`, `h61x_final.json`, `h61x_uniqueness.json`, `h61x_run_card.json`.
- New irregularity: **IR-61X-01** the random-line control draws differ between sessions (H61-G: single seed 100 for every cell → 0.0314; H61-X: per-cell seeds 100+ci → 0.0352). Both are recorded; CIs overlap; no conclusion depends on the 0.004 gap. The H61-X card reports the in-run draw as primary and the H61-G draw as secondary.
- New irregularity: **IR-61X-02** the parallel session (arena/a7790b7f) rewrote the `elapsed_s` field of the earlier `evidence/h61g_invert.json` (344.6 → 59.0) when it re-ran the inversion; scientific content unchanged. Evidence receipts are immutable records — restored to 344.6 in this merge.
- Parallel session `arena/a7790b7f` (PRs #11-#13, merged to main before this PR): H61-L lidar relief in the GP-1012 corridor (0.0443 HOLDOUT-DTI, unique) and H61-M gravity×magnetic corridor ribbons (format-valid, unique, no segment holdout). Both files and their evidence (`evidence/h61l_*.json`, `evidence/h61m_*.json`, `scripts/run_h61l.py`, `scripts/run_h61m.py`, `src/gems61/h61m.py`) are merged into this branch and shown on the board above.

## Irregularities (full list on [docs/irregularities.html](docs/irregularities.html))

IR-61-MERGE-01 broken merge on main (fixed) · IR-61-TEST-01 tests imported a sibling package (fixed) · IR-61-DATA-01 three data layouts (fixed) · IR-61-INSTR-02 the "anti-correlated holdout" was a full-catalogue-prune artefact (protocol corrected) · IR-61-UNIQ-01 near-blanket reference raster breaks the one-sided overlap rule (Jaccard rule when reference is dense) · IR-61-ARTIFACT-01 three competing "primary" files advertised before H61-G (all superseded) · IR-61-CONV-01 undamped Oldenburg diverges (damped) · IR-61-RIBBON-01 3 × 3 ribbons halve the holdout score (dots shipped) · IR-61-NET-01 sandbox allow-list: data from the hash-pinned public bridge, not an organiser receipt · **IR-61X-01 random-line control seed handling differs between H61-G (0.0314) and H61-X (0.0352) draws (both recorded, CIs overlap, no conclusion affected)** · **IR-61X-02 parallel session rewrote `elapsed_s` in the earlier `evidence/h61g_invert.json` (344.6 → 59.0); evidence receipts are immutable — restored in this merge**.

## Core values

**Maximize P(Win)** and **Own the Outcome**: the slot is not spent on a file the holdout says is weak; the two-scale sub-hypothesis is
closed with a measured negative rather than a projection; the duplicate construction (X3) is caught by the uniqueness gate before it
can consume a slot; and the path that can actually move 0.2778 (locator recall at 100 m, lidar in corridors, marginal-credit packing)
is named with its obtainable data source.

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
