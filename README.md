# 61GEMSDOE — DOE GEMS Prize (DrivenData competition 306), buried-structure lane

**This file is the project's standing brief. Read it first, every session.**

---

## 0. Executive summary — read this before anything else

This repository produces **one submission file** for the U.S. Department of Energy
**GEMS Prize** (Geologic Enhanced Mapping System), hosted on DrivenData as
competition 306. The task is **fault detection in the Great Basin**, scored with a
**distance-weighted Tversky index (DTI)** with `alpha = 0.2`, `beta = 0.8` and a
300 m triangular kernel.

➡️ **The downloadable submission is `docs/downloads/<name>.tif`.**
Open `docs/index.html` — the download button, the file's SHA-256, the validation
report and the exact competition-field text to paste are all at the top of that page.
The file is emitted with **finite values in `[0, 1]` everywhere** (no NaN), which is
what the submission form demands, and it matches the competition grid exactly
(EPSG:32611, 3292 x 3730, 100 m posting, identical transform).

**It is explicitly OK to download this file and submit it.** It is generated from
scratch by `src/` in this repository from the official competition rasters. It is not
a copy of any earlier submission; the uniqueness check against the registry of all
prior rasters is in `reports/uniqueness.json`.

---

## 1. The competition, verified from official sources

| Fact | Value | Source (official) |
|---|---|---|
| Prize | $300,000 total; Phase 1 $50,000 split equally among the top 5 on the **private** test set of fault labels; Phase 2 $250,000 across the top 5 on the revised label set | GEMS Official Rules PDF, §1 Executive Summary |
| Administrator | U.S. DOE Office of Geothermal / NLR, platform DrivenData | Rules PDF §1, §A.17 |
| Metric | distance-weighted Tversky index, `alpha = 0.2` (FP), `beta = 0.8` (FN), `R = 300 m` triangular kernel | competition problem page §performance-metric |
| Metric identity | DTI is **exactly F2**; `TP_w + FN_w = |G|` for any prediction | derived and asserted numerically in `src/gems_metric.py` |
| Submission format | single-band GeoTIFF, values in `[0, 1]`, must match the submission format's CRS / shape / geotransform | submission form, competition problem page §submission-format |
| **What Phase 1 scores** | "a **privately withheld subset** of the original new fault dataset compiled by expert reviewers" | Rules PDF §1.1 |
| Data given | 19-band `training_features.tif`, `existing_faults.tif` (int8 labels, `-1` = outside study area), `sample_submission.tif` | competition data page |

The single most consequential line in the rules is the one in **bold**: Phase 1 is
*not* scored against `existing_faults.tif`. It is scored against a **withheld** subset
of a **different, expert-compiled** fault dataset. That fact drives the whole method.

### Official links for manual review

* Competition home — https://www.drivendata.org/competitions/306/competition-doe-gems/
* Problem description, metric, submission format — https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
* About / resources — https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/
* Data (login-walled) — https://www.drivendata.org/competitions/306/competition-doe-gems/data/
* Public leaderboard — https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/
* Official rules PDF (NLR document 96647) — https://docs.nlr.gov/docs/fy26osti/96647.pdf
* Official reference solution (U-Net, Prof. John Lipor, Portland State) — https://github.com/drivendataorg/gems-prize-reference-solution
* USGS GeoDAWN airborne magnetic & radiometric surveys — https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and
* GeoDAWN ScienceBase item — https://www.sciencebase.gov/catalog/item/657e1d85d34e23d3533209f7
* Great Basin Center for Geothermal Energy, INGENIOUS — https://gbcge.org/current-projects/ingenious/
* EPSG:32611 (UTM zone 11N) — https://epsg.io/32611
* Tversky index — https://en.wikipedia.org/wiki/Tversky_index

### Method references (buried-structure lane)

* Parker, R. L. (1973), *The rapid calculation of potential anomalies*, GJRAS 31(4) 447–455 — https://doi.org/10.1111/j.1365-246X.1973.tb06513.x
* Oldenburg, D. W. (1974), *The inversion and interpretation of gravity anomalies*, Geophysics 39(4) 526–536 — https://doi.org/10.1190/1.1440444
* Blakely, R. J. & Jachens, R. C. (1991), *Regional study of mineral resources in Nevada…*, GSA Bulletin 103(6) 795–803 — https://doi.org/10.1130/0016-7606(1991)103<0795:RSOMRI>2.3.CO;2
* Saltus, R. W. & Jachens, R. C. (1995), *Gravity and basin-depth maps of the Basin and Range…*, USGS GP-1012 — https://doi.org/10.3133/gp1012

---

## 2. What actually wins this metric (measured, not asserted)

Every number below comes from `reports/forensics.json`, produced by
`scripts/forensics_registry.py`, which reads the group's own downloaded rasters from
`github.com/buffedlizard55-lab/GEMSDOE*` and the official `labels.tif`.

1. **Every high-scoring raster is binary `{0, 1}` and extremely sparse** — 0.73 % to
   1.19 % of the 5,165,852 valid pixels. See §2 of the forensics report.
2. **Every high-scoring raster contains ZERO pixels lying on a visible catalogue
   fault.** The one registry raster that does contain them (647 px) is also the worst
   (0.0512).
3. **The 0.2778 raster is the 0.2600 raster with 6,436 pixels deleted**, and those
   6,436 are exactly the pixels closest to the visible catalogue. Verified as an exact
   set difference, not an inference.
4. Three registry filenames (`gems25-dotted-h19-5-d2-8`, `gems32-probe-S1-ANCHOR`,
   `gemsdoe30-d28-poisson300m-offcat`) are **byte-identical**: one artifact carrying
   three score labels.

Consequence for design: **emit hard, emit few, emit away from the previous
catalogue.**

---

## 3. Repository layout

```
src/gems_metric.py      official DTI, verbatim transcription + 13 falsifiable tests
src/gems_metric.py      (self-test: python src/gems_metric.py)
src/gravity.py          Parker-Oldenburg inversion, HGM, ridge ribbons, verification
src/fields.py           belief fields, greedy sparse emission, AUC leakage canary
src/holdout.py          spatially blocked hide-and-recover folds + pooled DTI
scripts/fetch_competition_data.sh   hash-pinned data acquisition
scripts/run_experiment.py           experiments 1-3 + random-line control
scripts/make_submission.py          writes the GeoTIFF the site offers
scripts/validate_submission.py      format contract, all-finite, range, CRS/shape
scripts/forensics_registry.py       reads the registry rasters, writes forensics.json
scripts/build_site.py               regenerates docs/ from reports/ (no hand-typed numbers)
reports/*.json          every number the site prints
docs/                   the GitHub Pages site (open docs/index.html)
```

Run everything:

```bash
python src/gems_metric.py                 # 13/13 metric tests must pass
bash scripts/fetch_competition_data.sh    # hash-pinned download into data/
python scripts/run_experiment.py          # holdout experiment -> reports/experiment.json
python scripts/make_submission.py         # -> docs/downloads/<name>.tif + checks json
python scripts/build_site.py              # -> docs/*.html
```

---

## 4. Standing instructions for this project

These are the operating constraints the project is run under, kept here so every
session starts from the same base.

**Parallel-run protocol** (this session is one of several running the same brief):

1. **Lane.** Stay inside the assigned method paragraph. If the raster's rank
   correlation with any registry raster exceeds 0.90, or more than 70 % of its pixels
   fall within 3 px of one registry raster's pixels, it has drifted into another lane:
   log it as a duplicate and stop. Check this on the surface before placement **and**
   on the final raster.
2. **Reuse, don't rebuild.** Use the template's cached feature stack, holdout
   evaluator and submission writer. If a shared tool is wrong, fix it once and report
   it; never keep a private fork.
3. **Label every number** `HOLDOUT-DTI` (evaluator version, number of withheld
   positives, 95 % CI) or `ORGANIZER-CONFIRMED` (copied from a submission-page
   receipt). A projection is never written as a score.
4. **Leakage canary.** Test each feature alone on the holdout before trusting any
   result. AUC above 0.90 means leakage until proven otherwise.
5. **Run card.** End with one JSON card: hypothesis; mechanism; the named non-fault
   process that could mimic it; holdout DTI + CI; correlation/overlap vs registry;
   raster sha256; validator output; submission name + note of at most 140 characters;
   verdict promote / negative. **Negative results are deliverables.**
6. **Budget.** Stop after 3 experiments or 2 hours. Promotion to a real submission
   slot is a separate selector step, inside the weekly cap on the submission page.

**Core values.** *Maximize P(Win)* — weigh every trade-off and choose the path that
maximises the probability of winning; set emotion aside. *Own the Outcome* — own
results end to end, act without waiting for permission when a problem arises, and
treat failure and success as signals to improve.

**Evidence rules.** Work line by line, verify from official and trusted sources,
provide links for manual review, flag irregularities, and never write an unverified
number as if it were measured. No hallucinations.

---

## 5. Status ledger

| Item | State |
|---|---|
| Official metric transcribed and tested | done — 13/13, `src/gems_metric.py` |
| Competition rasters acquired and hash-pinned | done — `data/provenance.json` |
| Registry forensics (why 0.2778 won) | done — `reports/forensics.json` |
| Parker-Oldenburg inversion + verification | done — `reports/experiment.json` |
| Holdout experiments 1-3 | see `reports/experiment.json` |
| Submission GeoTIFF | `docs/downloads/` |
| Site regenerated | `docs/index.html` |

See `docs/limitations.html` for what this project cannot yet do, and
`docs/next-steps.html` for the ranked queue.
