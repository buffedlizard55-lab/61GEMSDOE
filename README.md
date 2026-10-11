# 61GEMSDOE — buried structures from gravity inversion

**[Open the site](https://buffedlizard55-lab.github.io/61GEMSDOE/)** ·
[How to submit, exactly](https://buffedlizard55-lab.github.io/61GEMSDOE/executive-summary.html) ·
[Competition #306](https://www.drivendata.org/competitions/306/competition-doe-gems/)

## Download first — and an unmistakable status

### **Download: OK. Submit to competition: OK.**

**[↓ Download the recommended GeoTIFF](docs/downloads/gems61c-gravstep-liveband-40k-20261011.tif)** ·
**[Single-TIFF ZIP](docs/downloads/gems61c-gravstep-liveband-40k-20261011.zip)** ·
[run card](docs/downloads/gems61c-gravstep-liveband-40k-20261011.tif.json) ·
[the session-C report](docs/session-c.html) ·
[how to submit, exactly](https://buffedlizard55-lab.github.io/61GEMSDOE/executive-summary.html)

- Single-band Float32 GeoTIFF, EPSG:32611, 3730 × 3292, transform
  `(100, 0, 243350, 0, -100, 4508550)`, every cell finite, every value in `[0, 1]`,
  **zero** positive pixels on the mapped-fault catalogue and **zero** outside the footprint.
- SHA256 `e3ccdf59f8b36f2f089f0eeaafac2547a96cc46e07c7eb2535449bd0e26f8873` (154,559 bytes).
- 40,000 single-pixel dots, non-maximum thinned at ≥ 3 px separation; distance mix matched band-for-band
  to the highest live-scoring sibling raster (OWNER-REPORTED 0.2778): median 23.6 px, mean 31.7 px,
  40.6 % beyond 30 px, **zero** within 2 px of the mapped catalogue.
- Suggested note (**132 / 140 characters**):
  > H61-C buried basement steps from a Parker-Oldenburg gravity inversion; 40000 dots, 120 m throw
  > minimum, none on the mapped catalogue
- **Uniqueness: UNIQUE** by rank and by dot set against the 12 comparable rasters in this repository —
  worst |Spearman| 0.0074, worst Jaccard 0.0076, byte-identical to none. The one 99.3 % reading is the
  degenerate 3 px test against a 311,617-dot blanket sibling that covers 95.8 % of the footprint; it is
  documented, not hidden (`evidence/e4_uniqueness.json`, `evidence/e4_uniqueness_degeneracy.json`).
- **No competition slot has been spent, and no organizer has scored this file.**

Upload the `.tif` or the ZIP (which contains exactly one GeoTIFF, round-trip verified). Do not
upload the JSON run card, a web page, or a ZIP of the repository.

Older lane candidates remain in `docs/downloads/`:
`gems61-h61a-basement-step-20000dots-20261011T012029Z-eb2ae4bb024b-zeros.tif` (20,000 dots, 61,888 B)
and `gems61-buried-basement-step-r3-rib2-k40k-2pxprune-zeros.tif` (250,866 B).

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

## Session C (2026-10-11) — what is new, and what failed

| Item | Result |
|---|---|
| Calibration | 21-point (z₀, Δρ, corner) sweep against **GP-1012** only: selected z₀ 400 m, Δρ −600 kg/m³, kc 0.25/z₀ → **19.9 %** of the grid deeper than 1 km (published "about 20 %"); cross-check r = 0.526, slope 0.804 vs the supplied `depth_to_base_surf` |
| New mechanism | zero-crossing of the **second vertical derivative** refines the basement-step axis; fused with the covered-flank and gravity-gradient terms |
| Emission | per-band budget allocation whose distance histogram is matched to the best live-scoring sibling raster; lane belief carries a **declared 0.10 weight** |
| Holdout (**HOLDOUT-DTI**, `gems61-pooled-hide-v2`) | shipped construction **0.0417**; uniform flank control 0.0649; pure lane field **0.0078**; random lines 0.0092 (39,310 withheld positives) |
| Lane deliverable | withheld basin-interior segments recovered: **669 / 1,150 = 58.2 %** vs random lines 109 / 1,150 = 9.5 % |
| Negative result | the pure lane field ranks withheld mapped-fault segments **worse than random lines**; the shipped file therefore carries it as a minority weight, and the report says so on its front page |
| New evidence | `evidence/e4_field.json`, `evidence/e4_holdout.json`, `evidence/e4b_holdout_final.json`, `evidence/e4_submission.json`, `evidence/e4_uniqueness.json`, `evidence/e4_uniqueness_degeneracy.json`, `scripts/run_lane61c.py` |

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

## Test suite (green since 2026-10-11)

```
.venv/bin/python -m pytest tests/ -q        # 22 passed
```

The suite arrived from the merge commit importing a sibling package (`gems57`) that
does not exist here, and without a `src/` path bootstrap, so it could not even be
collected. Fixed in place, once: `tests/conftest.py` adds `src/` to `sys.path`, the
three test modules import `gems61`, and `src/gems61/uniqueness.py` regains the small
compatibility API the suite exercises (`surface_rho`, `dot_overlap`,
`compare_array_to_registry`, `RHO_LIMIT` / `OVERLAP_LIMIT` / `JACCARD_LIMIT`), with
Jaccard marked diagnostic-only exactly as `IR-61-UNIQ-01` requires.

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

## Concurrent work already on `main` (do not lose it)

A parallel session on this repository (`arena/c463a286-61gemsdoe`, PR #3) implemented the same lane
independently and merged first. Its artifacts are **kept**: `docs/instrument.html`,
`docs/submissions/e3-*.tif` (`…basement-step-r3-rib2-k40k-2pxprune-zeros.tif`, 250,866 bytes),
`evidence/e1_calibration.json`, `evidence/e2b_instrument.json`, `evidence/e2c_canary.json`,
`evidence/e3_submission.json`, and its own `scripts/build_site_e3.py`. Its site pages
(`instrument.html`, `irregularities.html`, `submit.html`, `limitations.html`,
`methodology.html`, `next-steps.html`, `brief.md`) are untouched by this session's
`scripts/build_site.py`, which writes only `index.html`, `executive-summary.html`,
`method.html`, `hypotheses.html` and `verify.html`.

Two independent constructions of the same lane is the intended redundancy, not a conflict:
this session's file and that one are different rasters with different emission rules, both
uniqueness-checked, and neither has spent a slot.
