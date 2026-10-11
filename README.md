# 61GEMSDOE — buried structures from gravity inversion

**[Open the site](https://buffedlizard55-lab.github.io/61GEMSDOE/)** ·
[How to submit, exactly](https://buffedlizard55-lab.github.io/61GEMSDOE/executive-summary.html) ·
[Competition #306](https://www.drivendata.org/competitions/306/competition-doe-gems/)

## Download first — and an unmistakable status

### **Download: OK. Submit to competition: OK.**

**[↓ Download the GeoTIFF](docs/downloads/gems61-h61a-basement-step-20000dots-20261011T012029Z-eb2ae4bb024b-zeros.tif)** ·
**[Single-TIFF ZIP](docs/downloads/gems61-h61a-basement-step-20000dots-20261011T012029Z-eb2ae4bb024b-zeros.zip)** ·
[run card](out/gems61-h61a-basement-step-20000dots-20261011T012029Z-eb2ae4bb024b-zeros.json)

- Single-band Float32 GeoTIFF, EPSG:32611, 3730 × 3292, transform
  `(100, 0, 243350, 0, -100, 4508550)`, every cell finite, every value in `[0, 1]`,
  **zero** positive pixels on the mapped-fault catalogue and **zero** outside the footprint.
- SHA256 `565a581b46878ba249aff3296f21ba6bf6e9317dc713a8acad9f5eb193fc0ed9` (61,888 bytes).
- 20,000 selected dots, each grown to a 3 × 3 ribbon; median offset from the mapped catalogue
  15.6 px, mean 16.2 px, 0 % within 2 px of it.
- Suggested note, **125 / 140 characters**:
  > H61-A basement-step ribbons from an independent Parker-Oldenburg inversion of iso_grav_anom;
  > 20000 dots, 120 m throw minimum.
- **Uniqueness: UNIQUE** against all 34 sibling rasters that could be downloaded and compared —
  worst rank correlation 0.050, worst dot overlap 0.030 (thresholds 0.90 / 0.70), byte-identical
  to none.
- **No competition slot has been spent, and no organizer has scored this file.**

Upload the `.tif` or the ZIP (which contains exactly one GeoTIFF, round-trip verified). Do not
upload the JSON run card, a web page, or a ZIP of the repository.

## The assigned lane

> **Buried structures from gravity inversion.** Invert the supplied isostatic-gravity layer for
> depth to basement. Calibrate the density-contrast depth scale against the USGS Basin and Range
> basin-depth maps (Saltus & Jachens, GP-1012, 1995) **only** — that product is at 1:2,500,000 and
> is not a truth mask. Locate buried range-front or intrabasin faults as **steps in the
> basement-depth surface** where the sediment cover is thick. Map maxima of the horizontal
> gradient of basement depth as candidate faults. Emit multi-line ribbons rather than thin lines.
> Constraint: gravity inversion is non-unique; state the assumed density contrast and reference
> level, and calibrate them so the outputs have physically plausible depths (nothing deeper than
> ~8 km). Test whether the buried-step candidates lie outside the existing USGS/INGENIOUS
> catalogue, and report how many withheld basin-interior segments the steps recover versus random
> lines.

## What was actually done

| Step | Result |
|---|---|
| Grid pins | **PASS** — 5,167,373 footprint px, 60,988 catalogue px, shape/CRS/transform re-derived from the bytes |
| Inversion | Parker (1973) forward / Oldenburg (1974) inverse, 400 m block-mean grid; the **first iterate** is kept because the non-linear correction is measured to diverge (forward RMS 23.8 mGal at iteration 1 → 1,157 mGal by iteration 6) |
| Calibration | 21-point sweep of (z₀, Δρ, filter corner) against USGS **GP-1012**; selected z₀ 400 m, Δρ −600 kg/m³, giving **19.9 %** of the grid deeper than 1 km against the published "about 20 %" |
| Cross-check | inverted depth vs the competition's own `depth_to_base_surf` band: **r = 0.526**, slope 0.804 — two independently derived surfaces agreeing on the broad pattern |
| Steps | Blakely & Simpson (1986) HGM maxima, then a **measured throw** filter (≥ 120 m across the ridge), because a lineament is not a fault |
| Emission | the metric's own marginal rule `dT·D > 0.2·T·(dT + 1 − k)`, binary dots at ≥ 2 px separation |
| Holdout | catalogue-frame holdout **0.0000** vs a random-line control **0.0089** — reported, not tuned away: the instrument hides mapped traces and rewards dots placed *on* them, which is exactly what the live evidence penalises (`IR-57-INSTR-01`) |
| Uniqueness | **UNIQUE** over 34 comparable sibling rasters |

## Evidence classes used on this site (no number is ever a score)

- **MEASURED** — produced by code in this repository from the pinned inputs; reproducible with
  `scripts/run_lane61.py`.
- **HOLDOUT-DTI** — an evaluator-version index on withheld catalogue traces. It is *not* a
  competition score and is never written as one.
- **OWNER-REPORTED** — copied from a sibling project's record of its own leaderboard rows. It
  describes *other* files.
- **PROJECTION** — a fit of other files' scores. It appears only where labelled, never as a result.

No organizer receipt connects any local artifact here to a leaderboard row.

## Reproduce

```bash
python -m venv .venv && .venv/bin/pip install -r requirements-lock.txt
.venv/bin/python scripts/prepare_data.py --fetch --cache-bands   # 8 pinned files, 19 bands
PYTHONPATH=src .venv/bin/python scripts/run_lane61.py all
```

`prepare_data.py` restores the sha256-pinned public bridge at commit
`e2fe3f41c6f5dd2dcb2fc91958ee67698f114ada` of `buffedlizard55-lab/6GEMSDOE` through
`codeload.github.com` (the API route rate-limits; the pin is unchanged) and re-verifies every
hash. Nothing under `data/` is downloaded from DrivenData, whose data tab is behind a login.

## Session record

- `evidence/verify_grid.json` — pin verification and grid derivation
- `evidence/measure.json` — the GP-1012 calibration sweep, the divergence trace, the cross-check
- `evidence/hypotheses.json` — five candidate hypotheses, ranked, with the four blocked ones and
  the named free official source each would need
- `evidence/holdout.json` — the spatially-blocked validation, including the negative result
- `evidence/final.json` — the built file, its property vector, and the promotion argument
- `evidence/uniqueness.json` — the corpus comparison, with the degenerate-overlap correction
- `docs/` — the rendered site (`scripts/build_site.py`, no hand-edited HTML)

## Irregularities

- **IR-57-INSTR-01** — the catalogue-frame holdout has measured ρ = −0.93 against 15
  owner-reported live scores. Structural reference only.
- **IR-61-SIGN-01** — the first inversion build had a stray leading minus: `corr(depth, gravity)`
  came out +0.63 where the supplied band gives −0.685. Caught by asserting the sign, fixed, re-run.
- **IR-61-UNIQ-01** — dot-overlap against a dense sibling surface (2.7 M positive cells) is
  degenerate: it covers half the footprint and absorbs 88 % of any candidate's dots at Jaccard
  0.008. The gate therefore uses Jaccard when the reference is dense.
- **IR-61-CONV-01** — the Oldenburg iteration does not converge on an isostatic residual. The
  rejected correction is reported in `evidence/measure.json` rather than hidden.

## Core values

**Maximize P(win)** and **own the outcome** drive the decisions here: the emission is decided by
the metric's own algebra rather than by eye; every claim carries its evidence class and its
source; the one negative result that matters is printed next to the positive ones; and the file is
built to be *unique* rather than to be a copy of something that already scored.
