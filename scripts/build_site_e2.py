#!/usr/bin/env python
"""Render this session's candidate pages into docs/ from evidence/e2_candidate.json.

No hand-edited HTML.  This builder writes ONLY:
    docs/index.html            (landing page - the download is the first thing on it)
    docs/executive-summary.html(exactly how to submit, step by step)
    docs/candidate-h62.html    (the full run card, rendered)
and copies the .tif / .zip / .json into docs/downloads/.

It deliberately does not touch the pages another session on this repo owns
(instrument.html, irregularities.html, submit.html, limitations.html,
methodology.html, next-steps.html, brief.md, method.html, hypotheses.html,
verify.html, evidence.html) - concurrent work is kept, not overwritten.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
DOCS = ROOT / "docs"
DL = DOCS / "downloads"

CSS = """
:root{--ink:#10202b;--mut:#5a6b78;--line:#d8e0e6;--ok:#0b7a3b;--warn:#b45309;--bad:#b42318;--bg:#fbfcfd}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:940px;margin:0 auto;padding:26px 20px 80px}
h1{font-size:30px;line-height:1.2;margin:.2em 0 .3em}
h2{font-size:21px;margin:2em 0 .5em;border-bottom:1px solid var(--line);padding-bottom:.25em}
h3{font-size:17px;margin:1.4em 0 .35em}
small,.mut{color:var(--mut)}
.banner{border-radius:12px;padding:18px 20px;margin:16px 0;border:1px solid}
.ok{background:#eefaf1;border-color:#b6e2c5}.warn{background:#fff8ec;border-color:#f2d6a8}.bad{background:#fdeeed;border-color:#f3c2bd}
.banner strong{display:block;font-size:20px;margin-bottom:6px}
.ok strong{color:var(--ok)}.warn strong{color:var(--warn)}.bad strong{color:var(--bad)}
a.btn{display:inline-block;background:#0b5cff;color:#fff;text-decoration:none;padding:13px 22px;border-radius:9px;font-weight:600;margin:6px 8px 6px 0;font-size:17px}
a.btn.alt{background:#fff;color:#0b5cff;border:1px solid #0b5cff}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:14.5px}
th,td{border:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}
th{background:#f1f5f8}
code{background:#f1f5f8;padding:1px 5px;border-radius:4px;font-size:13.5px;word-break:break-all}
nav a{margin-right:14px}
.pill{display:inline-block;font-size:12.5px;padding:2px 8px;border-radius:99px;background:#eef2f6;color:var(--mut);margin-left:6px}
.bad-pill{background:#fdeeed;color:var(--bad)}
ol li,ul li{margin:.3em 0}
"""

NAV = ('<nav><a href="index.html">Home</a>'
       '<a href="executive-summary.html">How to submit</a>'
       '<a href="candidate-h62.html">This candidate</a>'
       '<a href="method.html">Method</a><a href="hypotheses.html">Hypotheses</a>'
       '<a href="verify.html">Verification</a><a href="irregularities.html">Irregularities</a>'
       '<a href="limitations.html">Limitations</a></nav>')


def page(title, body):
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{title}</title><style>{CSS}</style></head><body><main>{NAV}"
            f"<h1>{title}</h1>{body}</main></body></html>")


def f(x, n=4):
    try:
        return f"{float(x):.{n}f}"
    except Exception:
        return "—"


def main() -> None:
    c = json.loads((EVID / "e2_candidate.json").read_text())
    e1 = json.loads((EVID / "e1_habitat_instrument.json").read_text())
    DL.mkdir(parents=True, exist_ok=True)

    tif = ROOT / c["tif"]
    zp = ROOT / c["zip"]
    card = ROOT / "out" / f"{c['submission_name']}.json"
    for src in (tif, zp, card):
        shutil.copy2(src, DL / src.name)
    (DL / f"{c['submission_name']}.tif.sha256").write_text(
        f"{c['raster_sha256']}  {tif.name}\n")

    v = c["validator"]
    rho_e1 = e1["best"]["spearman_rho"]
    chks = v["checks"]
    n_pass = sum(1 for x in chks.values() if x)
    uniq = c["uniqueness"]
    hdti = c["holdout_dti"]
    prop = c["property_vector"]
    rec = c["withheld_segment_recovery"]
    can = c["leakage_canary"]
    is_unique = uniq["verdict"] == "unique"
    fmt_ok = v["all_checks_passed"]

    # The status must be unmistakable, and it must not overclaim.  Format validity is
    # MEASURED; promotion is NOT supported by any validated instrument.
    status_cls = "warn"
    status_head = "Download: OK. Submit to the competition: NOT RECOMMENDED — no validated evidence supports promoting it."
    status_body = (
        f"This file passes <b>{n_pass}/{len(chks)}</b> local format checks, is "
        f"<b>{uniq['verdict']}</b> against every registry raster that could be downloaded "
        f"(worst rank correlation {f(uniq['worst_rank_correlation'])}, worst raw 3-px dot "
        f"overlap {f(uniq['worst_raw_3px_fraction'])}; protocol thresholds 0.90 and 0.70), "
        f"and is safe to upload — it cannot produce the portal's "
        f"<i>“Predicted values must be in range [0, 1]”</i> error. "
        f"But its surrogate-truth DTI, <b>{f(hdti['value'],5)}</b>, is <b>below every one of the "
        f"seven registry rasters</b> (0.0493–0.0581) measured on that same ruler, and that ruler "
        f"is itself <b>not validated</b> (it reproduces the owner-reported live ordering at "
        f"ρ = {f(e1['best']['spearman_rho'],3)}, p = {f(e1['best']['p_value'],3)}). "
        f"Spending a weekly slot on it is not justified by the evidence in this repository. "
        f"No slot has been spent and no organizer has scored this file.")

    banner = f'<div class="banner {status_cls}"><strong>{status_head}</strong>{status_body}</div>'

    buttons = (f'<p><a class="btn" href="downloads/{tif.name}">↓ Download the submission GeoTIFF '
               f'({tif.stat().st_size:,} bytes)</a>'
               f'<a class="btn alt" href="downloads/{zp.name}">↓ Single-TIFF ZIP '
               f'({zp.stat().st_size:,} bytes)</a>'
               f'<a class="btn alt" href="downloads/{card.name}">Run card (JSON)</a></p>')

    body = f"""
{banner}
{buttons}
<p class="mut">Submission name to paste into the portal: <code>{c['submission_name']}</code><br>
Note to paste ({c['note_chars']}/140 characters): <code>{c['submission_note']}</code></p>

<h2>The one-paragraph version</h2>
<p>Lane: <b>buried structures from gravity inversion</b>. Band 13 (<code>iso_grav_anom</code>) is
inverted for depth to basement with the Parker (1973) forward series and the Oldenburg (1974)
iteration, keeping the <b>first iterate</b> because the non-linear correction is measured to
diverge on an isostatic residual. The depth scale is calibrated <i>only</i> against USGS
<b>GP-1012</b> (Saltus &amp; Jachens 1995), which is 1:2,500,000 and is a scale anchor, not a truth
mask. Buried range-front and intrabasin faults are then taken as maxima of the horizontal gradient
of basement depth that also carry a <b>measured throw ≥ 120 m</b>, and emitted as a hard-core dot
field of {prop['n_dots']:,} pixels, every one of them at least 3 px (300 m) from the mapped
catalogue — because the official problem page says the test truth is
<i>“newly identified faults … NOT INCLUDED IN THE EXISTING USGS fault database”</i>.</p>

<h2>Why the best-known file in this family scored 0.2778</h2>
<p>Measured directly on the registry bytes (nine rasters fetched by commit-pinned clone, hashes
checked), not inferred from filenames:</p>
<table>
<tr><th>registry raster</th><th>owner-reported live</th><th>dots</th><th>dots on catalogue</th>
<th>dots &lt;3 px from catalogue</th><th>median band-15 depth at dots</th></tr>
<tr><td>h33-2-b2</td><td><b>0.2778</b></td><td>37,654</td><td>0</td><td>1,611</td><td>245 m</td></tr>
<tr><td>h36-1-rung30</td><td>0.2710</td><td>37,660</td><td>0</td><td>3,891</td><td>246 m</td></tr>
<tr><td>h27-4-r1-solo-d2-8</td><td>0.2708</td><td>40,199</td><td>0</td><td>4,156</td><td>245 m</td></tr>
<tr><td>dotted-h19-5-d2-8</td><td>0.2600</td><td>44,090</td><td>0</td><td>8,047</td><td>244 m</td></tr>
<tr><td>topo-gap-closure</td><td>0.2449</td><td>61,328</td><td>0</td><td>11,329</td><td>248 m</td></tr>
<tr><td>gate_ortho</td><td>0.2376</td><td>40,000</td><td>0</td><td>0</td><td><b>150 m</b></td></tr>
<tr><td>sgmc-off-catalogue</td><td>0.0512</td><td>44,090</td><td><b>647</b></td><td>4,493</td><td><b>148 m</b></td></tr>
</table>
<p>Three things follow, and they are the whole story:</p>
<ol>
<li><b>The truth is disjoint from the visible catalogue</b> (official page, verbatim). The only
raster with dots <i>on</i> the catalogue is the only catastrophic score, 0.0512.</li>
<li><b>The winners are a thinning ladder on one base.</b> 44,090 dots → 0.2600; 40,199 → 0.2708;
37,660 → 0.2710; 37,654 → 0.2778. Over-emission (61,328) falls back to 0.2449. The metric's own
marginal rule agrees: a non-redundant dot pays iff <code>k &gt; α·DTI</code> = 0.2 × 0.28 = 0.056,
i.e. within 2.83 px of truth — so the optimum is a budget, not “more dots”.</li>
<li><b>Basin habitat separates the well-pruned fields.</b> Among fields that are all pruned and all
≈37–40 k dots, live score is ordered by the median basement depth under the dots: 243–248 m for
0.2449–0.2778, versus 148–150 m for 0.0512 and 0.2376. The eligible area's own median is 316 m, so
<i>every</i> published field under-weights deep basin fill. That is this lane's premise, and it is
the only lever the registry evidence actually supports.</li>
</ol>
<p><b>Can we beat 0.2778?</b> The lever is real but this file does not pull it successfully:
pushing the habitat ramp to exponent 1.0 moved the median dot to 717 m of inverted depth, outside
anything published, and the surrogate DTI fell <i>below</i> every registry raster. The exponent was
pulled back to 0.25 and the result is reported as measured, not tuned away. Beating 0.2778 needs a
<b>validated</b> instrument first — see <a href="candidate-h62.html">the run card</a>.</p>

<h2>What is in the file</h2>
<table>
<tr><th>SHA256</th><td><code>{c['raster_sha256']}</code></td></tr>
<tr><th>Bands / dtype</th><td>{v['grid']['count']} band, {v['grid']['dtype']}</td></tr>
<tr><th>CRS</th><td>{v['grid']['crs']} (UTM zone 11 N)</td></tr>
<tr><th>Shape</th><td>{v['grid']['height']} × {v['grid']['width']}</td></tr>
<tr><th>Transform</th><td><code>{v['grid']['transform']}</code></td></tr>
<tr><th>Positive pixels</th><td>{v['positive_pixels']:,}
    ({100*v['footprint_fraction']:.3f} % of the {5167373:,}-pixel footprint)</td></tr>
<tr><th>Value range</th><td>{v['in_footprint_min']} … {v['in_footprint_max']} — inside [0, 1]</td></tr>
<tr><th>Non-finite cells</th><td>0 anywhere in the 12,279,160-cell raster</td></tr>
<tr><th>Dots on the mapped catalogue</th><td>0</td></tr>
<tr><th>Validator</th><td><b>{n_pass}/{len(chks)} checks passed</b> —
    {"PASS" if fmt_ok else "FAIL"} (re-read from the bytes on disk, fail-closed)</td></tr>
</table>

<h2>Evidence classes — no number here is a score</h2>
<table>
<tr><th>Label</th><th>Meaning</th></tr>
<tr><td><b>MEASURED</b></td><td>produced by code in this repository from sha256-pinned inputs;
    reproducible with <code>scripts/e2_build_candidate.py</code></td></tr>
<tr><td><b>HOLDOUT-DTI</b></td><td>an evaluator-version index on a surrogate truth. Carries the
    instrument's own validity verdict. Never a competition score.</td></tr>
<tr><td><b>OWNER-REPORTED</b></td><td>a sibling project's record of its own leaderboard rows.
    Describes <i>other</i> files, never this one.</td></tr>
<tr><td><b>ORGANIZER-CONFIRMED</b></td><td>copied from a submission-page receipt.
    <b>None exists for this file.</b></td></tr>
</table>

<h2>Reproduce</h2>
<pre><code>python -m venv .venv &amp;&amp; .venv/bin/pip install -r requirements-lock.txt
.venv/bin/python scripts/prepare_data.py --fetch --cache-bands   # 8 pinned files, 19 bands
bash scripts/fetch_registry.sh /tmp/refs/registry                # 9 scored rasters
PYTHONPATH=src .venv/bin/python scripts/e1_habitat_instrument.py
PYTHONPATH=src .venv/bin/python scripts/e2_build_candidate.py</code></pre>

<p class="mut">Live leaderboard read 2026-10-11 from
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">the
official leaderboard</a>: #1 = 0.4133. Official metric and format from
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">the problem
page</a>. Both fetched, not recalled.</p>
"""
    (DOCS / "index.html").write_text(page("61GEMSDOE — buried basement steps from gravity inversion", body))

    # ---------------- executive summary ---------------- #
    checks_rows = "".join(
        f"<tr><td><code>{k}</code></td><td>{'✅ PASS' if val else '❌ FAIL'}</td></tr>"
        for k, val in chks.items())
    es = f"""
<div class="banner ok"><strong>How to submit, exactly</strong>
Everything below is verified against the official submission format on
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">the problem
page</a> and against the portal's own field text. No step needs judgement.</div>

<h2>Step 1 — download the file</h2>
{buttons}
<p>Either the <code>.tif</code> or the <code>.zip</code> is accepted. The ZIP contains
<b>exactly one</b> GeoTIFF and was round-trip verified (its member's sha256 equals the standalone
file's). Do <b>not</b> upload the JSON run card, a web page, or a ZIP of this repository.</p>

<h2>Step 2 — check it is the right file</h2>
<table>
<tr><th>Expected SHA256</th><td><code>{c['raster_sha256']}</code></td></tr>
<tr><th>Expected size</th><td>{tif.stat().st_size:,} bytes</td></tr>
</table>
<p>Verify locally with <code>sha256sum {tif.name}</code>.</p>

<h2>Step 3 — paste the name and the note</h2>
<table>
<tr><th>“Note (optional)”</th><td><code>{c['submission_note']}</code><br>
    <span class="mut">{c['note_chars']} of the 140 characters the portal allows.</span></td></tr>
<tr><th>File name</th><td><code>{tif.name}</code><br>
    <span class="mut">The portal does not ask for a separate name; the file name and this note are
    what distinguish submissions later.</span></td></tr>
</table>

<h2>Step 4 — submit, and respect the weekly cap</h2>
<p>Upload at the
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">competition page</a>.
Promotion to a real slot is a separate selector step inside the weekly cap shown on the submission
page; nothing in this repository spends a slot.</p>

<h2>Why this file cannot trigger “Predicted values must be in range [0, 1]”</h2>
<p>That portal error has two known causes and both are engineered out. The writer never clips,
fills or repairs: it validates in memory, writes, then <b>re-reads the bytes from disk</b> and
aborts unless every one of the 12,279,160 cells is finite and inside [0, 1].</p>
<ol>
<li>The feature stack's float32 sentinel (<code>-3.4028234663852886e+38</code>) is stripped at
cache time and re-checked as <code>no_float32_sentinel</code>.</li>
<li>A footprint mask derived from a feature band can leave scored pixels NaN. The footprint here is
taken from the pinned <code>sample_submission.tif</code> itself (5,167,373 finite cells), and cells
outside it are written as explicit <b>zeros</b>, not NaN — so the whole raster is finite.</li>
</ol>
<table>{checks_rows}</table>

<h2>Read this before you spend a slot</h2>
<div class="banner warn"><strong>The evidence does not support promoting this file.</strong>
Its surrogate-truth DTI is {f(hdti['value'],5)}, below all seven registry rasters (0.0493–0.0581) on
the same ruler, and that ruler reproduces the owner-reported live ordering only at
ρ = {f(rho_e1,3)}.
The run card's verdict is <b>negative</b>. It is a deliverable, including as a
negative result — not a recommended slot.</div>

<h2>Where the numbers live</h2>
<ul>
<li><code>evidence/e2_candidate.json</code> — this candidate's full run card</li>
<li><code>evidence/e1_habitat_instrument.json</code> — the surrogate-truth calibration and its
    leave-one-out failure</li>
<li><code>evidence/verify_grid.json</code>, <code>evidence/data_preparation.json</code> — the eight
    sha256 pins</li>
<li><code>evidence/measure.json</code> — the GP-1012 calibration sweep and the divergence trace</li>
</ul>
"""
    (DOCS / "executive-summary.html").write_text(page("How to make a submission", es))

    # ---------------- full run card ---------------- #
    uniq_rows = "".join(
        f"<tr><td><code>{u['file'][:52]}</code></td><td>{u['n_other']:,}</td>"
        f"<td>{u['shared_pixels']:,}</td><td>{f(u['jaccard'],5)}</td>"
        f"<td>{f(u['frac_my_dots_within_3px'],4)}</td><td>{f(u['eligible_base_rate_within_3px'],4)}</td>"
        f"<td>{f(u['enrichment'],3)}</td><td>{f(u['rank_correlation'],4)}</td></tr>"
        for u in uniq["per_raster"])
    reg_rows = "".join(
        f"<tr><td><code>{k[:48]}</code></td><td>{f(v2['owner_reported_live'],4)}</td>"
        f"<td>{f(v2['surrogate_dti'],5)}</td><td>{v2['n_dots']:,}</td></tr>"
        for k, v2 in sorted(hdti["registry_reference"].items(),
                            key=lambda kv: -kv[1]["owner_reported_live"]))
    can_rows = "".join(f"<tr><td><code>{k}</code></td><td>{f(v2,4)}</td>"
                       f"<td>{'⚠ LEAKAGE' if v2 and v2 > 0.90 else 'ok'}</td></tr>"
                       for k, v2 in can["auc_per_feature_alone"].items())
    ra = rec.get("random_lines_all") or {}
    rb = rec.get("random_lines_basin_interior") or {}
    rho_e1 = e1["best"]["spearman_rho"]
    p_e1 = e1["best"]["p_value"]
    loo_e1 = e1["leave_one_out"]["mean_absolute_rank_error"]
    loo_exact = e1["leave_one_out"]["exact_rank_recoveries"]
    rc = f"""
<h2>Run card (protocol item 5)</h2>
<table>
<tr><th>Hypothesis</th><td>{c['hypothesis']}</td></tr>
<tr><th>Mechanism</th><td>{c['mechanism']}</td></tr>
<tr><th>Named non-fault process that could mimic it</th><td>{c['competing_non_fault_process']}</td></tr>
<tr><th>Inversion</th><td>z₀ = {c['inversion']['z0_m']} m, Δρ = {c['inversion']['delta_rho']} kg/m³,
    {c['inversion']['filter']}, forward RMS {f(c['inversion']['rms_residual_mgal'],2)} mGal.<br>
    Stage: {c['inversion']['stage']}.<br>
    Sign guard: corr(inverted depth, band 13) = {f(c['inversion']['sign_guard_corr_depth_vs_band13'],4)}
    (must be &lt; 0 — this is the IR-61-SIGN-01 regression test).<br>
    Calibration source: {c['inversion']['calibration_source']}</td></tr>
<tr><th>Declared design</th><td><code>{json.dumps(c['declared_design'])}</code></td></tr>
<tr><th>Holdout DTI + CI</th><td><b>{f(hdti['value'],5)}</b> — {hdti['label']}<br>
    Instrument: {hdti['evaluator']}<br>
    γ = {hdti['instrument_gamma']}, N = {hdti['instrument_N']:,};
    in-sample ρ vs live = {f(hdti['instrument_in_sample_spearman_vs_live'],3)};
    LOO mean rank error = {f(hdti['instrument_loo_mean_rank_error'],2)}<br>
    Withheld positives = {hdti['withheld_positives']:,}<br>
    <b>No 95 % CI is quoted</b>: a CI on an unvalidated instrument would imply a precision the
    ruler does not have. That absence is deliberate.</td></tr>
<tr><th>Correlation / overlap vs registry</th><td>
    worst rank correlation <b>{f(uniq['worst_rank_correlation'],4)}</b> (threshold 0.90)<br>
    worst raw 3-px dot overlap <b>{f(uniq['worst_raw_3px_fraction'],4)}</b> (threshold 0.70)<br>
    worst Jaccard <b>{f(uniq['worst_jaccard'],5)}</b><br>
    verdict: <b>{uniq['verdict']}</b></td></tr>
<tr><th>Raster sha256</th><td><code>{c['raster_sha256']}</code></td></tr>
<tr><th>Validator output</th><td>{sum(1 for x in chks.values() if x)}/{len(chks)} checks passed;
    no NaN inside the footprint (0 non-finite cells in the whole raster); values in
    [{v['in_footprint_min']}, {v['in_footprint_max']}] ⊂ [0, 1];
    CRS {v['grid']['crs']}, shape {v['grid']['height']} × {v['grid']['width']},
    transform {v['grid']['transform']} — all match the pinned template.</td></tr>
<tr><th>Submission name</th><td><code>{c['submission_name']}</code></td></tr>
<tr><th>Submission note</th><td><code>{c['submission_note']}</code>
    <span class="mut">({c['note_chars']}/140)</span></td></tr>
<tr><th>Verdict</th><td><b class="pill bad-pill">negative</b> — valid and unique, but not
    evidence-backed for promotion. Reported as a deliverable.</td></tr>
</table>

<h2>Surrogate-truth DTI against the registry, same ruler</h2>
<table><tr><th>registry raster</th><th>owner-reported live</th><th>surrogate DTI</th><th>dots</th></tr>
{reg_rows}
<tr><td><b>THIS CANDIDATE</b></td><td><i>unscored</i></td><td><b>{f(hdti['value'],5)}</b></td>
<td>{prop['n_dots']:,}</td></tr></table>
<p class="mut">The candidate sits below every registry raster on this ruler. The ruler is not
validated (ρ = {f(rho_e1,3)}), so this is a measurement, not a prediction — but
it is the measurement that decides the verdict.</p>

<h2>Uniqueness, per raster</h2>
<table><tr><th>registry raster</th><th>their dots</th><th>shared</th><th>Jaccard</th>
<th>raw 3-px frac</th><th>eligible base rate</th><th>enrichment</th><th>rank corr</th></tr>
{uniq_rows}</table>
<p class="mut">{uniq['note']}</p>

<h2>Leakage canary — each feature alone</h2>
<p>Withheld: {can['withheld_positives']:,} pixels in 82 whole connected traces of the catalogue
(20 % of catalogue mass), buffered 3 px; visible traces masked pixel-exactly; every
catalogue-derived feature recomputed from the <b>visible</b> faults only. Domain
{can['domain_pixels']:,} px. Threshold: AUC &gt; 0.90 is leakage until proven otherwise.</p>
<table><tr><th>feature</th><th>AUC alone</th><th>flag</th></tr>{can_rows}</table>
<p><b>Reading this honestly.</b> No feature exceeds 0.90, so nothing leaks. But
<code>final_score</code> scores AUC {f(can['auc_per_feature_alone'].get('final_score'),4)} and
<code>fused_p</code> {f(can['auc_per_feature_alone'].get('fused_p'),4)} — far <i>below</i> 0.5, i.e.
deliberately anti-predictive of withheld <i>catalogue</i> traces. That is not a defect: the
emission is hard-pruned ≥ 3 px from the whole catalogue, so by construction it cannot sit on a
withheld catalogue pixel. It is the same structural fact as IR-57-INSTR-01 — a catalogue-frame
holdout measures the opposite of the live target, whose truth is disjoint from the catalogue.</p>

<h2>The lane's required test — and why it is degenerate here</h2>
<table>
<tr><th>withheld segments scored</th><td>{rec.get('n_segments_scored','—')}</td></tr>
<tr><th>candidate recovered within 300 m</th><td>{f(rec.get('candidate_all'),4)}</td></tr>
<tr><th>random lines, same budget</th><td>{f(ra.get('mean'),4)} ± {f(ra.get('std'),4)} ({ra.get('n_draws','?')} draws)</td></tr>
<tr><th>lift</th><td>{f(rec.get('lift_all'),2)} ×</td></tr>
<tr><th>basin-interior</th><td>{f(rec.get('candidate_basin_interior'),4)} vs
    {f(rb.get('mean'),4)} — <b>degenerate</b></td></tr>
</table>
<div class="banner bad"><strong>IR-62-DEGEN-01 — structural conflict, reported not hidden.</strong>
The lane asks how many withheld <i>basin-interior</i> segments the steps recover versus random
lines. But obeying the official constraint (truth disjoint from the catalogue) means pruning every
dot ≥ 3 px from the catalogue — and 3 px <b>is</b> the metric's kernel radius R = 300 m. So no
compliant dot can ever lie within R of a withheld catalogue pixel, and recovery is ≤ the fraction
of a segment that falls outside its own component. The test cannot be answered by a
same-catalogue holdout once the official constraint is obeyed. A previous session on this repository
answered it with a 2 px prune instead and measured <b>36.6 % of withheld segments recovered versus
2.6 % for random lines</b> (14 ×), and <b>28.1 % versus 0.6 %</b> for basin-interior segments
(45 ×) — see <code>evidence/e3_submission.json</code>. That is the geological validation of this
lane; it is a different emission from the one on this page, and it is credited, not re-claimed.</div>

<h2>What would actually be needed to beat 0.2778</h2>
<ol>
<li><b>A validated instrument.</b> Nothing else matters until a surrogate truth reproduces the
owner-reported live ordering at ρ ≥ 0.9 with leave-one-out rank error ≤ 1. The single-parameter
depth-habitat law fitted here reaches only ρ = {f(rho_e1,3)}
(LOO {f(loo_e1,2)}, {loo_exact} exact).
The obvious next step is a two-factor law — basin habitat <i>and</i> budget — fitted on the seven
distinct registry fields, since budget alone explains topo-gap and contamination alone explains
sgmc.</li>
<li><b>More independent scored rasters.</b> Seven distinct fields cannot pin a habitat law. Every
additional published raster with an owner-reported score is worth more than another model.</li>
<li><b>A habitat test that is not catalogue-framed.</b> The only honest validation target is
faults that are genuinely absent from the catalogue; the free official source that could supply one
is named in <code>evidence/hypotheses.json</code>.</li>
</ol>
"""
    (DOCS / "candidate-h62.html").write_text(page(f"Candidate {c['submission_name']}", rc))

    print(f"[site] index.html, executive-summary.html, candidate-h62.html")
    print(f"[site] copied {tif.name}, {zp.name}, {card.name} -> docs/downloads/")


if __name__ == "__main__":
    main()
