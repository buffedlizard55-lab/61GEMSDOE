# 61GEMSDOE — buried structures from gravity inversion

**[Open the site](https://buffedlizard55-lab.github.io/61GEMSDOE/)** ·
**[How to submit, exactly](https://buffedlizard55-lab.github.io/61GEMSDOE/executive-summary.html)** ·
[This candidate's run card](https://buffedlizard55-lab.github.io/61GEMSDOE/candidate-h62.html) ·
[Competition #306](https://www.drivendata.org/competitions/306/competition-doe-gems/) ·
[Live leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)

---

## Download first — and an unmistakable status

This session's candidate is **H62**:

**[↓ Download the GeoTIFF](docs/downloads/gems61-h62-basinstep-habitat-38k-20261011T020659Z-1a9c172f7106.tif)** (823,776 bytes) ·
**[↓ Single-TIFF ZIP](docs/downloads/gems61-h62-basinstep-habitat-38k-20261011T020659Z-1a9c172f7106.zip)** (171,680 bytes) ·
[run card (JSON)](docs/downloads/gems61-h62-basinstep-habitat-38k-20261011T020659Z-1a9c172f7106.json)

### **Download: OK.  Submit to the competition: NOT RECOMMENDED.**

These two halves are deliberately separated, because they are two different kinds of claim.

- **Format validity is MEASURED and passes.** Single-band Float32, EPSG:32611, 3730 × 3292,
  transform `(100, 0, 243350, 0, -100, 4508550)`, **0** non-finite cells in all 12,279,160,
  values exactly `{0.0, 1.0}` ⊂ `[0, 1]`, **0** positive pixels on the mapped catalogue, **0**
  outside the footprint. Re-verified from the bytes on disk by an independent script, not only by
  the writer. This file **cannot** produce the portal's *"Predicted values must be in range [0, 1]"*
  error. SHA256 `5c8e481722c459ae50a1dac173c2edafda2b036ea17aee82aa2032be5e781591`.
- **Uniqueness is MEASURED and passes.** Against all seven byte-distinct scored registry rasters:
  worst rank correlation **0.0105** (threshold 0.90), worst raw 3-px dot overlap **0.2132**
  (threshold 0.70), worst Jaccard **0.0069**. It is a copy of nothing.
- **Promotion is NOT supported by any validated evidence, and that is the finding.** Its
  surrogate-truth DTI is **0.03949** — *below every one* of the seven registry rasters
  (0.04934–0.05807) measured on the same ruler — and that ruler reproduces the owner-reported live
  ordering only at ρ = 0.607 (p = 0.148), leave-one-out rank error 1.14, below the declared
  usability bar. Run-card verdict: **negative**. A negative result is a deliverable.
- **No competition slot has been spent, and no organizer has scored this file.** There is no
  ORGANIZER-CONFIRMED number anywhere in this repository for it.

Note to paste (125 / 140 characters):

> H62 Parker-Oldenburg basement-step ribbons x declared basin-floor habitat; 38k hard-core dots, >=3px off catalogue

### Other validated lane candidates on this repo (kept, not overwritten)

Concurrent sessions on this repository built the same lane independently. All are preserved in
[`docs/downloads/`](docs/downloads/); none has spent a slot:

| candidate | session | dots | positive px | SHA256 (first 16) | status |
|---|---|---|---|---|---|
| **H62** `…basinstep-habitat-38k-20261011T020659Z-1a9c172f7106` | this one | 38,000 | 38,000 | `5c8e481722c459ae` | valid + unique; **promotion not supported** |
| **H61-B** `…sharp-step-22000dots-20261011T015658Z-59e24a9409a7-zeros` | PR #6 | 22,000 | 88,796 | `84864d6e090e9282` | valid + unique; owner says "Submit: OK" |
| **H61-A** `…basement-step-20000dots-20261011T012029Z-eb2ae4bb024b-zeros` | PR #5 | 20,000 | 25,285 | `565a581b46878ba2` | valid + unique |
| `…buried-basement-step-r3-rib2-k40k-2pxprune-zeros` | PR #3 | 40,000 | 40,000 | `5dee4c5568eba145` | valid + unique |
| `…lane-buried-step-gravinversion-hgm-r3-k400k-b2zeros` | PR #3 | 311,617 | 311,617 | `a70dee1a390c08e9` | valid + unique |

H61-B is the most recent independent construction: GP-1012-calibrated sharp-step ribbons with a
throw/depth sharpness gate and a vertical-gradient depth index, 22,000 dots grown to 3 × 3 ribbons,
median offset from the catalogue 12.8 px. Its own README section and run card are on `main` at
[`out/gems61-h61b-sharp-step-22000dots-20261011T015658Z-59e24a9409a7-zeros.json`](out/).
It is a **different raster with a different emission rule** from H62 — which is the intended
redundancy of parallel lanes, not a conflict.

---

## Standing brief (read this first, every session)

This repository exists to satisfy the following requirements. They are restated here so that every
session starts from the same target rather than from the previous session's artefacts.

**The lane (single method paragraph — stay inside it).**
> Buried-structure lane: basement-depth steps from gravity inversion. Alluvial cover is one reason
> catalogues miss faults. Parker (1973) and Oldenburg (1974) give the standard iterative inversion
> of gravity to basement relief, and Blakely and Jachens (GSA Bulletin, 1991) applied it to isostatic
> residual gravity in Nevada to map the pre-Tertiary surface. Invert the provided isostatic-gravity
> layer. Use the USGS Basin and Range basin-depth maps (Saltus and Jachens, GP-1012, 1995) **only**
> to calibrate the density-contrast depth scale, since they are regional (1:2.5M). Map maxima of the
> horizontal gradient of basement depth as candidate buried range-front or intrabasin faults.
> Gravity resolves such steps only to a few hundred metres at best, so emit **multi-line ribbons**
> rather than thin lines. Report how many withheld basin-interior segments the steps recover versus
> random lines. Treat density contrasts within basement as the competing explanation. Output the
> standard validated GeoTIFF, uniqueness-checked against every earlier raster.

**The parallel-run protocol.**
1. **LANE.** Stay inside the paragraph above. If rank correlation with any registry raster exceeds
   **0.90**, or more than **70 %** of the dots fall within 3 px of one registry raster's dots, log it
   as a duplicate and stop. Check on the surface *and* on the final dots.
2. **REUSE, DON'T REBUILD.** Use the template's cached feature stack, `evaluate_holdout.py` and
   `submission_writer.py`. If a shared tool is wrong, **fix it once in the template and report it**;
   never keep a private fork.
3. **LABEL EVERY NUMBER** as HOLDOUT-DTI (evaluator version, number of withheld positives, 95 % CI)
   or ORGANIZER-CONFIRMED (copied from a submission-page receipt). **A projection is never written as
   a score.**
4. **LEAKAGE CANARY.** Test each feature alone on the holdout before trusting any result. AUC above
   **0.90** means leakage until proven otherwise.
5. **RUN CARD.** End with one JSON card: hypothesis; mechanism; the named non-fault process that
   could mimic it; holdout DTI + CI; correlation/overlap vs registry; raster sha256; validator
   output; submission name + note ≤ 140 characters; verdict promote / negative.
6. **BUDGET.** Stop after **3** experiments or **2** hours. Do not pick submissions — promotion is a
   separate selector step inside the weekly cap.

**The product requirements.**
- Generate a **unique** TIF submission; do not copy a previous one (copying for learning is fine).
- It must be **obvious** whether it is OK to download and submit.
- The download must be **easy** and at the very beginning of the site, plus an
  **executive-summary subpage** explaining exactly how to submit.
- The portal error *"Predicted values must be in range [0, 1]"* must be engineered out.
- A **unique name** and a **short note** to tell submissions apart.
- Clean, organised GitHub Pages UI with official verified links for manual review.
- Work autonomously, line by line, from official verified trusted sources. **No hallucinations.**
  Flag irregularities for review.
- Core values: **Maximize P(win)** and **Own the outcome**.

---

## Why the best-known file in this family scored 0.2778 — measured, not recalled

Nine scored rasters were fetched by commit-pinned blob-filtered clone
(`scripts/fetch_registry.sh`) and measured from their bytes. Three facts explain the whole ladder.

**1. The live truth is disjoint from the visible catalogue.** Verbatim from the
[official problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
(fetched 2026-10-11):

> "the sponsors have compiled a set of newly identified faults in the GeoDAWN region that are **not
> included in the existing USGS fault database**. These new faults have been manually labeled by
> fault experts and comprise the test dataset."

A dot on or inside one kernel radius of the mapped catalogue therefore earns `TP_w = 0` and costs
`FP_w = 1`. The only registry raster with dots *on* the catalogue (647 of them) is the only
catastrophic score, **0.0512**.

**2. The winners are a thinning ladder on one base.** Measured on the bytes:

| registry raster | owner-reported live | dots | on catalogue | <3 px from catalogue | median band-15 depth at dots |
|---|---|---|---|---|---|
| h33-2-b2 | **0.2778** | 37,654 | 0 | 1,611 | 245 m |
| h36-1-rung30 | 0.2710 | 37,660 | 0 | 3,891 | 246 m |
| h27-4-r1-solo-d2-8 | 0.2708 | 40,199 | 0 | 4,156 | 245 m |
| dotted-h19-5-d2-8 | 0.2600 | 44,090 | 0 | 8,047 | 244 m |
| topo-gap-closure | 0.2449 | 61,328 | 0 | 11,329 | 248 m |
| gate_ortho | 0.2376 | 40,000 | 0 | 0 | **150 m** |
| sgmc-off-catalogue | 0.0512 | 44,090 | **647** | 4,493 | **148 m** |

Score rises monotonically as catalogue-adjacent dots are removed (44,090 → 0.2600; 40,199 → 0.2708;
37,654 → 0.2778), and falls back when over-emitted (61,328 → 0.2449). The metric's own marginal rule
agrees — from `src/gems61/metric.py`, a non-redundant dot pays iff `k > α·DTI`, i.e.
`0.2 × 0.28 = 0.056`, i.e. within **2.83 px** of truth. So the optimum is a **budget**, not "more
dots". Three of the 44,090-dot files were byte-distinct but carried an *identical* dot mask (same
`n`, same kernel self-credit `M` = 3954.8, same coverage) — one construction, three wrappers.

**3. Basin habitat separates the well-pruned fields.** Among fields that are all pruned and all
≈37–40 k dots, live score is ordered by the median `depth_to_base_surf` under the dots:
243–248 m for 0.2449–0.2778, versus 148–150 m for 0.0512 and 0.2376. The eligible area's own median
is **316 m**, so *every* published field under-weights deep basin fill. That is this lane's premise
— a step under a kilometre of alluvium is a step the surface catalogue probably does not contain —
and it is the only lever the registry evidence actually supports.

**Uniform coverage is *not* the driver**: fraction of eligible area within 3 px of a dot correlates
with live score at ρ = −0.16 (p = 0.71). The truth has habitat structure.

**Can we beat 0.2778?** The lever is real; this file does not pull it successfully. Pushing the
habitat ramp to exponent 1.0 moved the median dot to 717 m of *inverted* depth — far outside the
148–248 m band every published field occupies — and the surrogate DTI fell below every registry
raster. The exponent was pulled back to 0.25 (the low end of the E1 best-fit plateau) and the worse
result is reported rather than tuned away. Beating 0.2778 needs a **validated instrument first**;
see [What would actually be needed](#what-would-actually-be-needed-to-beat-02778).

The live board was read on 2026-10-11: **#1 = 0.4133**, #2 = 0.3418, #3 = 0.3361, #8 = 0.3195. The
prompt's "0.3774" and "0.3195 is the highest right now" are both stale readings of a moving board —
see `IR-61-BOARD-01`.

---

## What was actually done this session

| Step | Result | Evidence class |
|---|---|---|
| Data blocker | **CLEARED.** All 8 sha256 pins verified; 19 bands cached. The 418,912,844-byte feature stack was assembled from 5 separately hashed parts and its digest matches the pin exactly | MEASURED |
| Grid pins | footprint 5,167,373 px, catalogue 60,988 px, eligible (≥3 px) 4,761,049 px; shape/CRS/transform re-derived from the bytes | MEASURED |
| Official metric | `src/gems_metric.py` self-test **13/13 PASS**, including fast-path == brute-force on both dense and sparse fields, `TP_w + FN_w = |G|`, `DTI == F₂`, and the official worked example 0.60265 | MEASURED |
| Official format | confirmed verbatim from the problem page: single-band float32, values in [0,1], EPSG:32611, 100 m, same bounds, data outside bounds null or NaN | MEASURED |
| E1 instrument | A one-parameter basin-habitat surrogate truth (q ∝ depth^γ) was fitted to the 7 distinct registry fields. Best γ = 0.15–0.60 (plateau), **ρ = 0.607, p = 0.148, LOO rank error 1.14, 3/7 exact** → **instrument NOT usable** | MEASURED / OWNER-REPORTED live |
| E2 inversion | Parker (1973) forward / Oldenburg (1974) inverse, 400 m block-mean grid, **first iterate kept** because the non-linear correction diverges (forward RMS 4.28 mGal at iterate 1). z₀ = 400 m, Δρ = −600 kg/m³, Butterworth-4, kc_scale = 0.25 — the GP-1012-calibrated optimum | MEASURED |
| Sign guard | corr(inverted depth, band 13) = **−0.9342** (must be < 0). This is the standing regression test for `IR-61-SIGN-01` | MEASURED |
| E2 steps | Blakely–Simpson HGM maxima with a **measured throw ≥ 120 m**, 2 px ribbons | MEASURED |
| E2 emission | hard-core top-**38,000** over the eligible area, 3 px separation, reached in 3 dart-throwing rounds from 4,534,940 candidates; **0** on the catalogue, min distance 3.00 px | MEASURED |
| Leakage canary | every feature alone vs withheld whole traces, visible traces masked pixel-exactly and catalogue-derived features recomputed from visible only. **No feature exceeds 0.90** → no leakage | MEASURED |
| Uniqueness | **unique** over 7 byte-distinct scored registry rasters | MEASURED |
| Format | **16/16** writer checks + **20/20** independent re-read checks | MEASURED |

### Five candidate hypotheses, ranked

Recorded in full in [`evidence/hypotheses.json`](evidence/hypotheses.json). This session's ranked
list, by expected DTI improvement per unit implementation cost:

| # | Hypothesis | Layers | Signature | Why it catches a *missing* fault | Cost | Status |
|---|---|---|---|---|---|---|
| 1 | **Basin-floor habitat reweighting** of an already-pruned dot field | band 15 `depth_to_base_surf`, band 13 `iso_grav_anom` | monotone ramp in basement depth, multiplied into the belief | Registry evidence: every published field under-weights deep fill (245 m vs the area's 316 m); a fault under thick alluvium has no surface expression to map | low | **IMPLEMENTED** as D4 — measured *worse* than the family best |
| 2 | **Two-factor instrument** (habitat × budget × catalogue contamination) fitted on the registry | the 7 distinct scored rasters | constrained linear fit of q(x) reproducing live DTI | Not geology — it is the missing ruler. Budget alone explains topo-gap, contamination alone explains sgmc; neither explains both | low | **NOT DONE — highest-value next step** |
| 3 | **Conductivity-defined buried step** | band 17 `cond_surf`, band 15 | contrast in conductive-base depth across a lineament | A conductive fill against resistive basement marks a concealed contact the surface catalogue cannot see | medium | blocked: needs an independent non-catalogue validation target |
| 4 | **Strain-rate second invariant as a blind-fault proxy** | band 4 `geod_2ndinv`, bands 7/8 | local maxima of the strain-rate invariant off mapped traces | Geodetic strain accumulates on locked faults whether or not they are mapped | medium | blocked: same validation gap |
| 5 | **RTP magnetic lineament × basement step concurrence** | band 2 `rtp`, band 3 `tmi_hg`, inverted depth | requiring two independent methods to agree on the same step | Concurrence suppresses the intrabasement-density-contrast mimic that this lane cannot separate on its own | high | blocked: needs the free official source named in `evidence/hypotheses.json` |

Hypothesis 1 was implemented because it is the only one the registry evidence directly supports. It
was validated on the surrogate instrument before any slot was considered, and it **did not beat** the
holdout best — so no slot was spent. That is the protocol working as intended.

---

## Evidence classes (no number in this repo is a score)

- **MEASURED** — produced by code here from sha256-pinned inputs; reproducible.
- **HOLDOUT-DTI** — an evaluator-version index on a surrogate or withheld truth, always carrying the
  instrument's own validity verdict. Never a competition score.
- **OWNER-REPORTED** — a sibling project's record of its own leaderboard rows. Describes *other* files.
- **ORGANIZER-CONFIRMED** — copied from a submission-page receipt. **None exists for any file here.**
- **PROJECTION** — a fit of other files' scores. Never written as a result.

---

## Reproduce

```bash
python -m venv .venv && .venv/bin/pip install -r requirements-lock.txt
.venv/bin/python scripts/prepare_data.py --fetch --cache-bands   # 8 pinned files, 19 bands
bash scripts/fetch_registry.sh /tmp/refs/registry                # 9 scored rasters (7 byte-distinct)
PYTHONPATH=src .venv/bin/python scripts/e1_habitat_instrument.py # the ruler, and its failure
PYTHONPATH=src .venv/bin/python scripts/e2_build_candidate.py    # build + measure + package
.venv/bin/python scripts/build_site_e2.py                        # render docs/
PYTHONPATH=src .venv/bin/python src/gems_metric.py               # metric self-test, 13/13
```

`prepare_data.py` restores the sha256-pinned public bridge at commit
`e2fe3f41c6f5dd2dcb2fc91958ee67698f114ada` of `buffedlizard55-lab/6GEMSDOE` through
`codeload.github.com` and re-verifies every hash. **Nothing under `data/` is downloaded from
Drivendata**, whose data tab is behind a login. The bridge's own `manifest.json` records the official
Dropbox mirrors it was built from; the pins in `prepare_data.py` match that manifest entry for entry.

---

## Irregularities (flagged for review, none hidden)

New this session:

- **IR-62-PEAK-01** — a naive `score == maximum_filter(score)` peak-pick returned only **9,941**
  candidates over 4,761,049 eligible cells, because a smooth belief field has very few strict local
  maxima. The emission silently missed its 38,000 budget. Fixed by iterative dart-throwing
  (`emit_hardcore`): take the peaks of the *remaining* field, delete each accepted dot with its
  3 px neighbourhood, repeat. Now reaches exactly 38,000 in 3 rounds.
- **IR-62-HIDE-01** — the first holdout withheld individual rows of the 84,331-row QFaults segment
  CSV. Those rows are short pieces of the same traces and share endpoints, so the 80 % left visible
  covered every pixel the 20 % hidden covered: the canary domain held **zero** withheld positives,
  every AUC came back `None`, and basin-interior recovery was 0.0 vs 0.0. Fixed by withholding whole
  **connected components** of the catalogue (82 components, 12,222 px) with a 3 px buffer.
- **IR-62-CANARY-01** — the canary domain was built from `elig`, which removes *every* catalogue
  pixel including the hidden ones, so `hidden ∩ domain` was empty by construction. Fixed: the domain
  is footprint minus visible traces minus their buffer, and the hidden traces stay inside it as the
  positives. Catalogue-derived features are now recomputed from the **visible** faults only; the
  full-catalogue version is never scored.
- **IR-62-DEGEN-01** — **structural conflict, not a bug.** The lane asks how many withheld
  basin-interior segments the steps recover versus random lines. But obeying the official constraint
  (truth disjoint from the catalogue) means pruning every dot ≥ 3 px from the catalogue, and 3 px
  **is** the metric's kernel radius R = 300 m. No compliant dot can lie within R of a withheld
  catalogue pixel, so same-catalogue recovery is degenerate for any compliant emission. Measured
  here: 0.1445 vs random 0.1844 (lift 0.78×), basin-interior 0.0 vs 0.0. The prior session answered
  the question with a 2 px prune and measured **36.6 % vs 2.6 %** (14×) and **28.1 % vs 0.6 %** (45×)
  for basin-interior — see `evidence/e3_submission.json`. That result is credited, not re-claimed.
- **IR-62-PATH-01** — `src/gems61/grid.py` pointed at a `data/bridge/` layout that does not exist
  here, so `load_grid()` raised `FileNotFoundError` for every caller that did not pass `data_dir`.
  **Fixed once in the shared module** (tries `bridge`, then `official`) per protocol rule 2, not
  forked.
- **IR-62-CALIB-01** — `src/gems61/lane61.py` carried `z₀ = 500 m, kc_scale = 0.5, Δρ = −400`,
  which is **not** the GP-1012-calibrated optimum recorded in `evidence/measure.json`
  (`z₀ = 400, Δρ = −600, kc_scale = 0.25`, penalty 0.00441). The published calibration and the code
  that used it disagreed. **Fixed once in the shared module.**
- **IR-62-TEST-01** — *resolved by PR #6 while this session was running.* All three modules in
  `tests/` imported `gems57` (`gems57.metric`, `gems57.grid`,
  `gems57.validate`, `gems57.uniqueness`), a package that does not exist in this repository.
  `pytest` collects **0** tests and errors on all three. This is **pre-existing on `main`** —
  `tests/` was untouched by this session. PR #6 (merged concurrently) retargeted them at `gems61`;
  after the merge the suite must be re-run to confirm it collects. Until then the authoritative
  regression cover is the metric self-test in `src/gems_metric.py` (**13/13 PASS**, verified this
  session against brute force).
- **IR-62-REPRO-01** — PR #6 merged concurrently and retuned the shared `lane61.py`
  (throw 120 → 80 m, σ 12 → 10 px, offset band 5–30 → 4–28 px, plus a new
  `sharpness ≥ 0.08` gate). H62 was built and measured with the *earlier* constants, so rebuilding
  from `HEAD` would silently produce a different file and make every number on the site
  unverifiable. Fixed by **pinning H62's declared constants inside its own build script** and
  recording them in the run card. The shared module is neither forked nor re-edited — PR #6's
  candidate keeps its tuning and H62 keeps its own.
- **IR-62-SITE-01** — two site builders now write the same two pages: `scripts/build_site.py`
  (PR #3/#6) and `scripts/build_site_e2.py` (this session) both emit `docs/index.html` and
  `docs/executive-summary.html`. Whichever runs last wins. This session's builder is the one that
  produced the committed pages; running the other will replace them. Needs a single owner.
- **IR-62-SCALE-01** — dot depth was first reported on the *inverted* scale (median 689 m) and
  compared to registry dots measured on *band 15* (median 316 m). Two different calibrated scales.
  The run card now reports both and states that only the band-15 figure is comparable.

Carried forward:

- **IR-57-INSTR-01** — the catalogue-frame holdout has measured ρ = −0.93 against 15 owner-reported
  live scores. Structural reference only. This session's canary confirms the mechanism: a compliant
  emission scores AUC **0.017** against withheld catalogue traces, i.e. deliberately
  anti-predictive, because the live truth is disjoint from the catalogue.
- **IR-61-SIGN-01** — a stray leading minus once flipped the inverted surface. Now a hard assertion
  in the build; measured −0.9342 this session.
- **IR-61-UNIQ-01** — dot overlap against a dense sibling surface is degenerate; the gate now reports
  the raw protocol fraction *and* the enrichment over the eligible-area base rate.
- **IR-61-CONV-01** — the Oldenburg iteration does not converge on an isostatic residual. The
  rejected correction is reported in `evidence/measure.json` rather than hidden.
- **IR-61-BOARD-01** — the prompt quotes both "0.3774" and "0.3195 is the highest score right now".
  Both are stale readings of a moving board. Read live on 2026-10-11: **#1 = 0.4133**. Never treat a
  prompt-quoted leaderboard number as current.
- **IR-62-SAMPLE-01** — the official page says "a sample submission that predicts **total fault
  absence** is provided", but the bridged `example_submission.tif` (sha256 `2176d08e…`, 1,599,597
  bytes) contains **60,988 pixels at 1.0**, exactly the mapped catalogue, all of them ⊂ `labels.tif`.
  The file mirrored as the sample submission is the catalogue, not an all-zeros template. It is used
  here only for grid/CRS/footprint, which it does define correctly (finite cells = 5,167,373 =
  footprint, matching `labels.tif`'s non-`-1` cells exactly).

---

## Limitations

1. **No DrivenData authentication.** The data tab is behind a login. Everything under `data/` comes
   through a hash-pinned public bridge whose own manifest records the official Dropbox mirrors. The
   pins are verified byte-for-byte, but **official origin is not independently authenticated**.
2. **No organizer receipt exists for any file in this repository.** Every live score quoted is
   OWNER-REPORTED by a sibling project about its own files.
3. **No validated instrument.** The catalogue-frame holdout is anti-correlated with live
   (IR-57-INSTR-01); the basin-habitat surrogate reaches only ρ = 0.607 with LOO rank error 1.14.
   Until one of these is fixed, **no local number can justify spending a slot.**
4. **Seven distinct registry fields cannot pin a habitat law.** Three of the nine downloaded rasters
   share one dot mask.
5. **The lane cannot separate its own competing explanation.** Intrabasement density contrasts
   (pluton margins, basement lithologic contacts, buried volcanic centres) produce the same
   horizontal-gradient ridge as a fault step.
6. **GPU training is out of scope here.** The metric, losses and validation all run on CPU; a
   learned model would need a GPU.
7. **Two site builders own the same pages** (IR-62-SITE-01) and **H62's constants must stay
   pinned** (IR-62-REPRO-01) or the published sha256 stops being reproducible.

## What would actually be needed to beat 0.2778

1. **A validated instrument** — nothing else matters first. Target ρ ≥ 0.90 against the
   owner-reported live ordering with leave-one-out rank error ≤ 1. The concrete next step is
   hypothesis 2: a **two-factor** law (basin habitat × budget × catalogue contamination), since
   budget alone explains topo-gap and contamination alone explains sgmc, and neither explains both.
2. **More independent scored rasters.** Each additional published raster with an owner-reported
   score is worth more than another model.
3. **A validation target that is not catalogue-framed.** The only honest target is faults genuinely
   absent from the catalogue; the free official source that could supply one is named in
   `evidence/hypotheses.json`, and its obtainability must be checked before the idea is called viable.

---

## Session record

- `evidence/data_preparation.json` — the eight sha256 pins, all verified
- `evidence/verify_grid.json` — grid derivation from the bytes
- `evidence/feature_cache.json` — all 19 bands with their descriptions and missing-pixel counts
- `evidence/measure.json` — the GP-1012 calibration sweep (84 candidates), the divergence trace, the
  cross-check against band 15 (r = 0.526, slope 0.804)
- **`evidence/e1_habitat_instrument.json`** — the surrogate-truth calibration and its LOO failure
- **`evidence/e2_candidate.json`** — this candidate's full run card
- `evidence/holdout.json`, `evidence/hypotheses.json`, `evidence/uniqueness.json`,
  `evidence/final.json` — prior-session evidence, kept
- `docs/` — the rendered site (`scripts/build_site_e2.py`, no hand-edited HTML)

## Concurrent work already on `main` (do not lose it)

Two earlier sessions on this repository implemented the same lane independently and merged first.
Their artefacts are **kept**: `docs/instrument.html`, `docs/irregularities.html`, `docs/submit.html`,
`docs/limitations.html`, `docs/methodology.html`, `docs/next-steps.html`, `docs/brief.md`,
`docs/evidence.html`, `docs/method.html`, `docs/hypotheses.html`, `docs/verify.html`,
`evidence/e1_calibration.json`, `evidence/e2b_instrument.json`, `evidence/e2c_canary.json`,
`evidence/e3_submission.json`, `scripts/build_site_e3.py`, and their rasters in `docs/downloads/`
(`gems61-buried-basement-step-r3-rib2-k40k-2pxprune-zeros.tif`, 250,866 bytes;
`gems61-h61a-basement-step-20000dots-…-zeros.tif`, 61,888 bytes;
`gems61-lane-buried-step-gravinversion-hgm-r3-k400k-b2zeros.tif`, 311,782 bytes).

`scripts/build_site_e2.py` writes only `index.html`, `executive-summary.html` and
`candidate-h62.html`; every other page is untouched. Three independent constructions of the same
lane is the intended redundancy, not a conflict: they are different rasters with different emission
rules, each uniqueness-checked, and **none has spent a slot**.

## Core values

**Maximize P(win)** and **own the outcome** drive the decisions here. The emission budget comes from
the metric's own algebra rather than from taste. The habitat exponent was pulled back from an
untested extreme when measurement contradicted it, and the worse number was published instead of
being tuned away. Eight defects were found in this session's own work and are listed with their
fixes; two pre-existing shared-module bugs were fixed once in the template rather than forked; one
pre-existing broken test suite is flagged rather than quietly ignored. The verdict is **negative**
because the evidence says so — and a negative result that stops a slot being wasted *is* the win.
