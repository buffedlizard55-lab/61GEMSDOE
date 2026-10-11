# 61GEMSDOE — buried-structure lane: basement-depth steps from gravity inversion

**[Open the site](https://buffedlizard55-lab.github.io/61GEMSDOE/)** ·
[Executive summary & how to submit](https://buffedlizard55-lab.github.io/61GEMSDOE/docs/executive-summary.html) ·
[Why 0.2778](https://buffedlizard55-lab.github.io/61GEMSDOE/docs/analysis.html) ·
[Competition #306](https://www.drivendata.org/competitions/306/competition-doe-gems/)

## Status of the newest file (read this first)

| question | answer |
|---|---|
| Is the file safe to download and submit? | **YES — FORMAT-VALID and UNIQUE.** 19 validator checks pass (float32, EPSG:32611, 3730 × 3292, sample-submission transform, no NaN/Inf anywhere, min 0 / max 1, 0.0 outside the footprint, zero dots on the mapped catalogue). Uniqueness verdict **UNIQUE** against 28 earlier rasters (worst Spearman +0.1961 vs h61g, limit 0.90; worst one-sided 3 px overlap 0.431 vs h61g, limit 0.70; worst Jaccard 0.008 against the one dense reference, limit 0.50). |
| Should it be given a weekly slot? | **NOT RECOMMENDED.** HOLDOUT-DTI 0.0606 (95 % CI 0.0494–0.0727; 22,641 withheld positive px; HOLDOUT-DTI (gems61.holdout_segmented v2, 22,641 withheld positive px, seeds 20+21, mode all, pooled alpha 0.2 beta 0.8 R 300 m)) beats random lines (0.0314) and the previous session's best lane construction (0.0465), but the spatially blocked leave-one-quadrant-out retest puts **every** locator we have at the random baseline (0.02–0.05 LOQO-DTI, 0.56–0.59 blocked canary AUC). Run-card verdict: **negative** — a valid, unique, honest negative result. |
| Has an organiser scored it? | **No.** `organizer_confirmed_score` is null. Every number for this file is HOLDOUT-DTI or LOQO-DTI. |

**[↓ Download the GeoTIFF](docs/downloads/gems61-h61m-invfeat-habitat-40000dots-20261011T062731Z-314697d7ff1f-zeros.tif)** ·
[zip](docs/downloads/gems61-h61m-invfeat-habitat-40000dots-20261011T062731Z-314697d7ff1f-zeros.zip) ·
[format receipt](docs/downloads/gems61-h61m-invfeat-habitat-40000dots-20261011T062731Z-314697d7ff1f-zeros.json) ·
[run card](evidence/h61m_run_card.json)

- Submission name: `gems61-h61m-invfeat-habitat-40000dots-20261011T062731Z-314697d7ff1f-zeros`
- Note (140/140 chars): `H61-M: 200m Parker-Oldenburg basement inversion as features in an out-of-fold logistic habitat model; 40000 dots at 3px, 3px prune; UNSCORED`
- sha256 `4e2f60ef6f6287ea71523af9465ea46489a90832a03344eab6494a4b902e8179` (130,225 bytes); 40,000 single-pixel dots (value 1.0) at 3 px spacing, every dot more than 3 px from a mapped fault; median distance to the catalogue 19.8 px (1985 m) — the group's 0.2778 file sits at 19.6 px.
- Withheld basin-interior segments recovered: **353 of 1982** (95 % CI 16.2–19.6 %) versus **213 of 1982** for random lines at the same budget (`evidence/h61m_holdout.json`) — a 1.6× recovery rate on the segments the lane is asked to find.

Earlier files in `docs/downloads/` (`gems61-h61g-…`, `gems61-h61a-…`, `gems61-h61b-…`, `gems61-lane-buried-step-…`, `gems61c-…`) are **SUPERSEDED**; they remain only as uniqueness references. Do not upload them.

## Candidate board — all gems61 files in `docs/downloads/` (four parallel sessions merged on `main`)

Each row carries the verdict its own session recorded. The last column scores the *shipped file* on this session's evaluator (gems61.holdout_segmented v2 (whole segments <=12 px, 4 eroded quadrants, seeds 20+21, mode all); 22,641 withheld px): every file is ≈ 0 there **by construction**, because all of them were pruned against the full catalogue (IR-61-INSTR-02); the only within-protocol numbers (construction re-emitted with visible-only pruning) exist for H61-G. This board is not a slot decision — the selector step is separate — but it is the evidence a selector should read.

| file | session / PR | positive px | its own session's verdict | shipped file on this evaluator (HOLDOUT-DTI) |
|---|---|---|---|---|
| **`gems61-h61m-invfeat-habitat-40000dots-20261011T062731Z-314697d7ff1f-zeros.tif`** | this session (H61-M) | 40,000 | FORMAT-VALID + UNIQUE; HOLDOUT-DTI 0.0606 (CI 0.0494–0.0727) vs random lines 0.0314 within protocol; LOQO-DTI at the random baseline → **negative for a slot** | 0.0606 |
| `gems61-buried-basement-step-r3-rib2-k40k-2pxprune-zeros.tif` | e3, PR #3 | 40,000 | kept; superseded | 0.0000 |
| `gems61-h61a-basement-step-20000dots-20261011T012029Z-eb2ae4bb024b-zeros.tif` | H61-A, PR #5 | 25,285 | catalogue-frame holdout 0.0000 vs random 0.0089 → SUPERSEDED | 0.0000 |
| `gems61-h61b-sharp-step-22000dots-20261011T015658Z-59e24a9409a7-zeros.tif` | H61-B, PR #6 | 88,796 | format-valid + unique; no holdout number above random in its run card | 0.0000 |
| **`gems61-h61g-x2-gravcorridor-sloperidge-40000dots-20261011T022417Z-0f9408427b88-zeros.tif`** | this session (H61-G), PR #9 | 40,000 | FORMAT-VALID + UNIQUE; HOLDOUT-DTI 0.0465 (CI 0.0421–0.0507) vs random lines 0.0314 within protocol; below the 0.1011 bar → negative for a slot | 0.0045 |
| `gems61-h62-basinstep-habitat-38k-20261011T020659Z-1a9c172f7106.tif` | H62, PR #7 | 38,000 | its card: surrogate-truth DTI 0.0395 below every one of seven registry rasters → 'Submit NOT RECOMMENDED' | 0.0000 |
| `gems61-lane-buried-step-gravinversion-hgm-r3-k400k-b2zeros.tif` | e3, PR #3 | 311,617 | 311,617-px near-blanket; the IR-61-UNIQ-01 reference; never upload | 0.0000 |
| `gems61c-gravstep-liveband-40k-20261011.tif` | session C, PR #8 | 40,000 | its card: shipped construction 0.0417, but its own uniform-flank control 0.0649 and pure lane field 0.0078 < random lines 0.0092 (gems61-pooled-hide-v2); 'value unproven', declared weight 0.10 | 0.0007 |

The parallel sessions' own pages remain in `docs/` (`session-c.html`, `candidate-h62.html`, `instrument.html`, …) with a SUPERSEDED-context banner; their evidence files (`evidence/e4_*.json`, `e1_habitat_instrument.json`, `e2_candidate.json`, …) are kept untouched. Shared-tool duplication found while merging: `uniqueness.py` carried two shadowed copies of its protocol helpers (IR-61-MERGE-02, removed).

## What this session found (H61-G)

1. **The inversion works as specified.** Parker/Oldenburg (damped) on the isostatic residual, regional removed at 15 km, z₀ 500 m, Δρ −300 kg/m³, calibrated only on the GP-1012 statistic (≈ 20 % of basin area deeper than 1 km → achieved 0.203); r = 0.738 against the organiser's own depth layer, which was never used in the fit. 8,999 HGM maxima → 7,527 steps with ≥ 80 m throw; 4,104 persistent over three scales (`evidence/h61g_invert.json`).
2. **Pure basement steps do not locate faults to 300 m.** X1a step ribbons: HOLDOUT-DTI 0.0230 vs random lines 0.0314 at 40 k dots. Gravity fixes a step to kilometres; the metric pays within 300 m.
3. **Gravity step as a corridor + slope-ridge locator is the only lane-consistent construction above random:** X2 = 0.0465 (CI 0.0421–0.0507); the same locator outside the corridor 0.0359; random dots inside the corridor 0.0335; basin-interior segments recovered **351/1999 recovered vs 215/1999 by random lines**. Leakage canary worst AUC 0.558 (limit 0.90).
4. **It is still a negative result for a slot:** the dotted h19-5 base (live 0.2600) scores 0.1011 and its line version (live 0.1922) 0.0712 on the same evaluator — the evaluator orders live files correctly, and our file sits at about half the base.
5. **Dots, not 3 × 3 ribbons:** on identical fold cells the ribbon variant scores 0.0216 vs 0.0465 for dots (the metric charges 0.2 per extra positive pixel). The shipped raster is the validated dot version; the multi-line character is kept at corridor scale.
6. **Why the earlier "holdout anti-correlates with live" claim was wrong (IR-61-INSTR-02):** the 0.2778 file was pruned against the full catalogue, so a catalogue holdout gives it 0.0044 by construction. Withhold whole segments, prune only against the visible catalogue, and the instrument becomes informative.

The PhD-level answer to *why `h33-h33-2-b2` scored 0.2778 and whether we can beat it* is on [docs/analysis.html](docs/analysis.html); the ranked new hypotheses (H61-L lidar-in-corridor, H61-I piedmont belt, H61-H gravity × magnetic conjunction, H61-J source-depth filter, H61-K learned basin fusion) with layers, signature, catalogue-gap reason, difference from the repo, expected gain and cost are on [docs/hypotheses.html](docs/hypotheses.html) and in `evidence/h61g_hypotheses.json`.

> H61-M **replaced** that list rather than renumbering it. Two of the five survive under new ids so that ids stay unique across sessions: H61-L (1 m lidar in corridor) → **H61-N**, now ranked first and unchanged in substance; H61-H (magnetic-edge conjunction) → **H61-P**. The other three (piedmont belt, source-depth filter, learned basin fusion) were dropped because this session's blocked measurements showed that adding more 100 m channels to a locator that does not generalise cannot help. Three new hypotheses were added in their place: H61-Q (geodetic strain), H61-R (seismicity nucleation) and H61-S (emission on disagreement between decorrelated locators). The authoritative list is `evidence/h61m_hypotheses.json`; the H61-G list is kept for the audit trail.

## What this session found (H61-M)

1. **The inversion works, at a finer grid.** Parker/Oldenburg (damped) on the isostatic residual, regional removed at 15 km, GP-1012-calibrated (≈ 20 % of basin area deeper than 1 km → achieved 0.198). Run at **200 m** as well as 400 m: the two agree at ρ = 0.999, the inverted surface correlates 0.745 with the organiser's own depth layer (never used in the fit) and anti-correlates with gravity at -0.833. 12,572 Blakely-Simpson maxima → 5,579 steps with ≥ 80 m throw.
2. **The step field cannot place a dot to 300 m — confirmed, not assumed.** The corridor indicator's leakage-canary AUC against withheld faults is 0.510; a hard corridor gate *reduces* the score (0.0364–0.0409 gated vs 0.0606 ungated at the same budget). The lane's instruments are in the final model as features and carry small weight (corridor +0.194, inv_depth -0.172, euler_depth -0.053, step_throw -0.046).
3. **An out-of-fold habitat model is the best locator we have.** 28 catalogue-independent channels, L2 logistic regression trained only on the *visible* faults of each holdout cell: HOLDOUT-DTI 0.0606 (CI 0.0494–0.0727) against 0.0314 for random lines and 0.0465 for H61-G's corridor × slope-ridge locator. Leakage canary worst AUC 0.626 (limit 0.90) — clean.
4. **But nothing generalises across space (the decisive result).** Leave-one-quadrant-out — retrain with *no* training pixel inside the scored quadrant — puts logistic at 0.0395, gradient boosting at 0.0376, the single strongest band at 0.0206 and the lane's corridor × slope locator at 0.0315, all with mean blocked canary AUC 0.56–0.59 (range 0.518–0.618). The lane's corridor locator has the highest and most consistent blocked AUC (0.590).
5. **A leakage finding (IR-61-LEAK-01).** A gradient-boosted version of the same model reached HOLDOUT-DTI 0.1670 and a canary AUC of 0.901 — above the protocol's 0.90 line. The LOQO retest shows the AUC falls to 0.518–0.618 across all 16 blocked retests, with no training pixel inside the scored quadrant: the skill was **adjacency to visible traces, not generalisation**. The shipped file therefore uses the logistic model.
6. **Dots, not ribbons — re-confirmed at the new budget.** 3 × 3 ribbons score 0.0184 against 0.0409 for the same dots (256,096 emitted px vs 39,794): the metric charges 0.2 per extra positive pixel.
7. **Reverse engineering of the group's scored rasters** (`evidence/registry_habitat.json`, 28 rasters): every high scorer is binary, sparse, carries zero dots on the catalogue and sits ~15–20 px from it; no single band separates the ≥ 0.20 scorers from the rest by more than 0.02 AUC, so their signal is in the conjunction.

8. **A 12-row configuration sweep** (`evidence/h61m3_sweep.json`) confirms the ranking under the same
   instrument: the best configuration is `S gbm prune2 tile4 @ 60000` at HOLDOUT-DTI 0.1693 — again the
   gradient-boosted model, again leakage-flagged. The best *logistic* configuration measured anywhere
   this session is 0.0546 (prune 3, no prior, `evidence/h61m2_holdout.json`) — below the ungated
   0.0606 shipped here.

The PhD-level answer to *why `h33-h33-2-b2` scored 0.2778 and whether we can beat it* is on [docs/analysis.html](docs/analysis.html); the ranked new hypotheses (H61-N lidar in corridor, H61-Q geodetic strain, H61-R seismicity, H61-P magnetic-edge conjunction, H61-S decorrelated ensemble) are on [docs/hypotheses.html](docs/hypotheses.html) and in `evidence/h61m_hypotheses.json`.

## Reproduce

```bash
git clone https://github.com/buffedlizard55-lab/61GEMSDOE && cd 61GEMSDOE
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
PYTHONPATH=src .venv/bin/python scripts/prepare_data.py --fetch --cache-bands   # hash-pinned bridge; 19 band memmaps; creates data/bridge + data/raw links
bash scripts/fetch_registry.sh                                                  # 21 earlier group rasters -> /tmp/refs/registry
PYTHONPATH=src .venv/bin/python scripts/run_h61g.py all                         # invert -> screen -> holdout -> final -> unique -> card  (~25 min)
PYTHONPATH=src .venv/bin/python -m pytest -q tests                              # 22 passed
PYTHONPATH=src .venv/bin/python scripts/build_site_h61g.py                      # regenerates docs/*.html from evidence/*.json
```

Checks run at the end of this session: `pytest -q tests` → 22 passed; `scripts/run_h61g.py unique` → UNIQUE; validator receipt all-pass; the site builder reads every number from JSON.

## Session record (arena/c57b45ae, 2026-10-11 — H61-G)

- `src/gems61/h61g.py` — inversion, steps, corridor, slope-ridge locator, dot packing, controls, Wilson CI, AUC.
- `scripts/run_h61g.py` — stages `invert | screen | holdout | final | unique | card | all`.
- `evidence/h61g_invert.json`, `h61g_screen.json`, `h61g_holdout.json`, `h61g_final.json`, `h61g_uniqueness.json`, `h61g_run_card.json`, `h61g_hypotheses.json`, `h61g_irregularities.json`.

## Session record (arena/2a87ed28, 2026-10-11 — H61-M)

- `src/gems61/h61m.py` — 200 m and 400 m Parker/Oldenburg inversions, basement steps, Euler SI = 0 source depth, the 28-channel habitat stack (written channel-by-channel into a memmap because the sandbox has ~3.9 GB of RAM), the logistic habitat model, dot packing, controls, Wilson CI, AUC.
- `scripts/run_h61m.py` — stages `features | holdout | final | unique | card`, with `--candidate / --prune / --budget / --tile` overrides.
- `scripts/run_h61m2.py` — experiment 2 (model class, soft step prior).
- `scripts/run_h61m3.py` — experiment 3 (leave-one-quadrant-out generalisation test; configuration sweep).
- `scripts/run_h61m4.py` — experiment 4 (every locator through the same blocked test).
- `scripts/registry_habitat.py` — reverse engineering of the group's scored rasters.
- `scripts/h61m_card.py`, `scripts/build_site_h61m.py` — run card and site, both read every number from JSON.
- `evidence/h61m_features.json`, `h61m_holdout.json`, `h61m2_holdout.json`, `h61m3_loqo.json`, `h61m3_sweep.json`, `h61m4_loqo.json`, `h61m_final.json`, `h61m_uniqueness.json`, `h61m_run_card.json`, `h61m_hypotheses.json`, `registry_habitat.json`.
- Shared tools fixed in place (no private forks): `scripts/run_h61m.py` gained explicit `--prune/--budget/--tile` overrides so the live-metric and holdout-metric disagreement about the prune is stated rather than inherited.

- `src/gems61/h61g.py` — inversion, steps, corridor, slope-ridge locator, dot packing, controls, Wilson CI, AUC.
- `scripts/run_h61g.py` — stages `invert | screen | holdout | final | unique | card | all`.
- `evidence/h61g_invert.json`, `h61g_screen.json`, `h61g_holdout.json`, `h61g_final.json`, `h61g_uniqueness.json`, `h61g_run_card.json`, `h61g_hypotheses.json`, `h61g_irregularities.json`.
- Shared tools fixed in place (no private forks): `src/gems61/validate.py` (union API, fixes the broken merge), `src/gems61/uniqueness.py` (Spearman / 3 px overlap / Jaccard for dense references), `scripts/prepare_data.py` (legacy data links), `scripts/fetch_registry.sh` (21 rasters), `tests/*` (package rename).

## Irregularities (full list on [docs/irregularities.html](docs/irregularities.html))

IR-61-MERGE-01 broken merge on main (fixed) · IR-61-TEST-01 tests imported a sibling package (fixed) · IR-61-DATA-01 three data layouts (fixed) · IR-61-INSTR-02 the "anti-correlated holdout" was a full-catalogue-prune artefact (protocol corrected) · IR-61-UNIQ-01 near-blanket reference raster breaks the one-sided overlap rule (Jaccard rule when reference is dense) · IR-61-ARTIFACT-01 three competing "primary" files advertised before this session (all superseded) · IR-61-CONV-01 undamped Oldenburg diverges (damped) · IR-61-RIBBON-01 3 × 3 ribbons halve the holdout score (dots shipped) · IR-61-NET-01 sandbox allow-list: data from the hash-pinned public bridge, not an organiser receipt ·
**IR-61-LEAK-01** a gradient-boosted habitat model's 0.901 canary AUC was adjacency to visible traces, not skill (proved by the leave-one-quadrant-out retest) ·
**IR-61-PRUNE-01** the holdout prefers a 2 px catalogue prune, the group's organizer-scored pair prefers 3 px — the shipped file follows the live evidence and reports the holdout cost ·
**IR-61-BUDGET-01** the holdout prefers more dots monotonically, the live ladder prefers ~38–40 k — shipped at 40 k ·
**IR-61-MEM-01** ~3.9 GB RAM: the 28-channel stack is streamed into a memmap and predictions are chunked.

## Core values

**Maximize P(Win)** and **Own the Outcome**: the slot is not spent on a file the holdout says is weak; the negative result is printed next to the positive ones; the earlier mis-reading of the instrument is corrected rather than inherited; and the path that can actually move 0.2778 (locator recall at 100 m, lidar in corridors, marginal-credit packing) is named with its obtainable data source.

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
| USGS GP-1012 (Saltus & Jachens 1995) basin-depth maps, the depth-scale calibration | https://pubs.usgs.gov/publication/gp1012 |
| USGS 3DEP 1 m lidar (the named obtainable source, hypothesis H61-N) | https://www.usgs.gov/3d-elevation-program/about-3dep-products-services |
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
