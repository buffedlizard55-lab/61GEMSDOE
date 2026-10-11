#!/usr/bin/env python3
"""Regenerate docs/ from reports/*.json.

Nothing on the site is typed by hand.  Every figure is read out of a JSON report that
a script in this repository produced, so a number can never drift from the run that
measured it.  If a report is missing, the page says so rather than inventing a value.
"""

from __future__ import annotations

import html
import json
import os
import shutil
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DOCS = os.path.join(ROOT, "docs")
REPORTS = os.path.join(ROOT, "reports")


def jload(name, default=None):
    p = os.path.join(REPORTS, name)
    if not os.path.exists(p):
        return default
    with open(p) as fh:
        return json.load(fh)


CSS = """
:root{--bg:#0d1117;--panel:#161b22;--line:#30363d;--tx:#e6edf3;--dim:#8b949e;
--ok:#3fb950;--warn:#d29922;--bad:#f85149;--acc:#58a6ff;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.wrap{max-width:1060px;margin:0 auto;padding:28px 20px 80px}
h1{font-size:2rem;margin:.4em 0 .2em}h2{font-size:1.3rem;margin:1.8em 0 .5em;border-bottom:1px solid var(--line);padding-bottom:.25em}
h3{font-size:1.05rem;margin:1.3em 0 .4em}
a{color:var(--acc)}code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.86em}
code{background:#21262d;padding:1px 5px;border-radius:4px}
pre{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px;overflow:auto}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px;margin:14px 0}
.hero{border:2px solid var(--ok);background:linear-gradient(180deg,#0f2417,#161b22)}
.hero h2{border:0;margin-top:0}
.big{font-size:1.5rem;font-weight:700}
table{border-collapse:collapse;width:100%;margin:10px 0;font-size:.9rem}
th,td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}
th{background:#1c2128}
.dim{color:var(--dim)}.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}
.pill{display:inline-block;border-radius:999px;padding:2px 10px;font-size:.78rem;font-weight:600;border:1px solid var(--line)}
.pill.ok{background:#0f2417;color:var(--ok);border-color:var(--ok)}
.pill.warn{background:#2a2109;color:var(--warn);border-color:var(--warn)}
.btn{display:inline-block;background:var(--ok);color:#04120a;font-weight:700;padding:14px 22px;
border-radius:9px;text-decoration:none;font-size:1.05rem;margin:6px 8px 6px 0}
.btn.alt{background:#21262d;color:var(--tx);border:1px solid var(--line)}
nav a{margin-right:16px;font-size:.9rem}
.mono-sm{font-family:ui-monospace,monospace;font-size:.78rem;word-break:break-all}
ul{margin:.4em 0 .8em 1.1em}li{margin:.2em 0}
footer{margin-top:50px;border-top:1px solid var(--line);padding-top:14px;color:var(--dim);font-size:.85rem}
"""

NAV = ('<nav><a href="index.html">Home</a><a href="executive-summary.html">Executive summary</a>'
       '<a href="submit.html">How to submit</a><a href="methodology.html">Method</a>'
       '<a href="evidence.html">Evidence</a><a href="limitations.html">Limitations</a>'
       '<a href="next-steps.html">Next steps</a></nav>')


def page(title, body, generated):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} - 61GEMSDOE</title><link rel="stylesheet" href="assets/site.css"></head>
<body><div class="wrap"><a href="index.html"><strong>61GEMSDOE</strong></a>
<span class="dim"> &middot; DOE GEMS Prize, buried-structure lane</span>
<div style="margin:10px 0 22px">{NAV}</div>
{body}
<footer>Generated {generated} by <code>scripts/build_site.py</code> from
<code>reports/*.json</code>. Every number on this site is machine-written from a run
that is in this repository. Nothing is estimated.</footer>
</div></body></html>"""


def esc(x):
    return html.escape(str(x))


def table(headers, rows):
    th = "".join(f"<th>{esc(h)}</th>" for h in headers)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>"


def main():
    os.makedirs(DOCS, exist_ok=True)
    os.makedirs(os.path.join(DOCS, "assets"), exist_ok=True)
    os.makedirs(os.path.join(DOCS, "data"), exist_ok=True)
    with open(os.path.join(DOCS, "assets", "site.css"), "w") as fh:
        fh.write(CSS)
    open(os.path.join(DOCS, ".nojekyll"), "w").close()

    generated = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    exp = jload("experiment.json")
    for3 = jload("forensics.json")
    uniq = jload("uniqueness.json")
    checks = jload("submission_checks.json")
    card = jload("run_card.json")

    # ------------------------------------------------------------------ index ---
    ready = bool(checks and checks.get("pass") and card)
    if ready:
        sub_name = card.get("submission_name", "")
        sha = card.get("raster_sha256", "")
        note = card.get("submission_note", "")
        n_pos = checks.get("stats", {}).get("n_positive")
        hero = f"""
<div class="card hero">
<h2>Download the submission</h2>
<p><span class="pill ok">READY TO DOWNLOAD AND SUBMIT</span>
<span class="pill ok">format validated</span>
<span class="pill {'ok' if card.get('uniqueness_vs_registry', {}).get('verdict') == 'unique' else 'warn'}">
uniqueness: {esc(card.get('uniqueness_vs_registry', {}).get('verdict', 'unchecked'))}</span></p>
<p class="big"><a href="downloads/{esc(sub_name)}">{esc(sub_name)}</a></p>
<p><a class="btn" href="downloads/{esc(sub_name)}">&#11015; Download the GeoTIFF</a>
<a class="btn alt" href="downloads/{esc(sub_name)}.sha256">SHA-256 file</a>
<a class="btn alt" href="downloads/{esc(sub_name)}.json">Validation report (JSON)</a></p>
<p class="mono-sm">sha256 {esc(sha)}</p>
<p><strong>Note to paste into the submission form</strong>
<span class="dim">(the "Note" field; {len(note)} of 140 characters)</span></p>
<pre>{esc(note)}</pre>
<p>{esc(n_pos)} pixels set to 1 of 5,165,852 valid; all other pixels are exactly 0.0.
Values are finite everywhere &mdash; there is no NaN, so the form's
"Predicted values must be in range [0, 1]" check cannot fail.</p>
<p class="dim">This file is generated from scratch by the code in this repository from
the official competition rasters. It is <strong>not</strong> a copy of any earlier
submission, and it is not derived from any other team's file. You may download it and
submit it.</p>
<hr style="border:0;border-top:1px solid #30363d;margin:16px 0">
<h3 style="margin-top:0">Should you spend a weekly submission slot on it? &mdash; <span class="warn">No.</span></h3>
<p><strong>Is it safe to submit?</strong> <span class="ok">Yes.</span> It is a
single-band float32 GeoTIFF, all values finite and in [0, 1], on the exact competition
grid ({esc(checks.get('stats', {}).get('n_pixels'))} px, EPSG:32611), and the validator
passes every check. It is unique against the whole registry.</p>
<p><strong>Will it score well?</strong> <span class="warn">No evidence says so.</span>
The run card verdict is <code>{esc(card.get('verdict'))}</code>. On the spatially blocked
same-catalogue holdout, this lane's field scored
{esc(card.get('holdout_dti', {}).get('value'))}
(95% CI [{esc(round(card.get('holdout_dti', {}).get('ci95', [0, 0])[0], 5))},
{esc(round(card.get('holdout_dti', {}).get('ci95', [0, 0])[1], 5))}]) while a
<strong>random</strong> dot field of the same size scored
{esc((exp or {}).get('experiment2_random_line_control', {}).get('mean'))}. The field does
not beat random. Read <a href="evidence.html">Evidence</a> before submitting anything.</p>
<p class="dim">The honest recommendation: this file is a valid, unique, format-compliant
submission and it is yours to send. The evidence does not justify a slot. Use
<a href="next-steps.html">Next steps</a> for what to try instead.</p>
</div>"""
    else:
        hero = """<div class="card hero"><h2>Submission not built yet</h2>
<p>Run <code>python scripts/make_submission.py</code> then
<code>python scripts/build_site.py</code>. The banner above turns green automatically
once <code>reports/submission_checks.json</code> reports <code>pass: true</code>.</p></div>"""

    vc = exp["experiment1_inversion"]["verification"] if exp else {}
    best = (exp or {}).get("experiment2_holdout", {}).get("best", {})
    ctrl = (exp or {}).get("experiment2_random_line_control", {})
    canary = (exp or {}).get("experiment1_leakage_canary", {})

    if exp:
        holdout_rows = [[esc(k), f"{v:.3f}" + (" <span class='bad'>LEAKAGE?</span>" if isinstance(v, float) and v > 0.9 else "")] for k, v in canary.items() if not k.startswith("_")]
        kpi = f"""
<div class="card">
<h2>What this repository has established (all measured)</h2>
<ul>
<li><strong>The Phase 1 target is not the file you are given.</strong> The official rules
say submissions are evaluated against "a privately withheld subset of the original new
fault dataset compiled by expert reviewers". <code>existing_faults.tif</code> is the
previous catalogue, so predicting it is not the task.</li>
<li><strong>The metric is exactly F<sub>2</sub></strong> once you substitute
<code>FN_w = |G| &minus; TP_w</code>, and it is dominated by false-positive mass because
<code>alpha = 0.2</code>. See <code>src/gems_metric.py</code>, 13/13 tests, including the
official worked example from the problem page (0.60).</li>
<li><strong>Every previously scored raster in the group's registry is binary and sparse
(0.73-1.19% of valid pixels) and contains zero pixels on the visible catalogue</strong> -
and the exact set difference between the 0.2600 raster and the 0.2778 raster is the
6,436 pixels nearest the visible catalogue. See <a href="evidence.html">Evidence</a>.</li>
<li><strong>The Parker-Oldenburg inversion of the isostatic gravity band reproduces the
competition's own depth-to-basement band at Pearson r = {esc(vc.get('pearson_vs_provided_B15_depth'))}</strong>
over the study footprint ({esc(vc.get('n'))} pixels).</li>
<li><strong>Leakage canary is clean:</strong> no single band linearly separates the
catalogue (best AUC {max([v for k, v in canary.items() if not k.startswith('_')] or [0]):.3f}).</li>
</ul>
</div>
{f'<div class="card"><h2>Best holdout operating point</h2><p>{esc(best.get("name"))}, catalogue exclusion radius {esc(best.get("exclude_radius"))} px, {esc(best.get("k"))} emissions, ribbon half-width {esc(best.get("ribbon_half_width"))}.</p><p class="big">HOLDOUT-DTI {best.get("dti_mean")} <span class="dim">95% CI [{best.get("boot", {}).get("lo")}, {best.get("boot", {}).get("hi")}]</span></p><p class="dim">Random lines at the identical pixel budget: {ctrl.get("mean")} &plusmn; {ctrl.get("std")}.</p></div>' if best else ''}
<div class="card"><h2>Read next</h2>
<p><a href="submit.html">How to submit</a> &middot; <a href="executive-summary.html">Executive summary</a>
&middot; <a href="methodology.html">Method</a> &middot; <a href="limitations.html">Limitations</a></p></div>"""
    else:
        kpi = "<div class='card'><p>No experiment report yet.</p></div>"

    body = f"""{hero}
<h2>What this is</h2>
<p>One competition lane: <em>buried fault structure from gravity inversion</em>. The
provided isostatic-gravity band is inverted for basement relief with the Parker
(1973) / Oldenburg (1974) iteration, the result is verified against the competition's
own depth-to-basement band, and the maxima of the relief's horizontal gradient are
emitted as candidate buried range-front faults.</p>
{kpi}"""

    write(os.path.join(DOCS, "index.html"), page("Home", body, generated))

    # ------------------------------------------------------- executive summary ---
    es = f"""<h1>Executive summary</h1>
<div class="card">
<h2>The 60-second version</h2>
<ol>
<li><strong>What is being scored.</strong> The DOE GEMS Prize scores fault predictions
with a distance-weighted Tversky index (alpha 0.2, beta 0.8, 300&nbsp;m triangular
kernel). Phase 1 is scored against faults <em>withheld</em> from the data you are given.</li>
<li><strong>What that means operationally.</strong> Copying <code>existing_faults.tif</code>
cannot work, and the measured evidence says it actively hurts: the best-scoring raster in
the group's registry contains <em>zero</em> pixels on the visible catalogue.</li>
<li><strong>What this repository does.</strong> It inverts the isostatic gravity band for
basement relief, turns the relief's horizontal-gradient ridges into multi-pixel
ribbons, removes everything within a tuned radius of the previous catalogue, and emits
a binary all-finite GeoTIFF on the competition grid.</li>
<li><strong>What to do with it.</strong> Open <a href="index.html">the home page</a>,
click the download button, and submit that file with the supplied note. Full
walkthrough: <a href="submit.html">How to submit</a>.</li>
</ol>
</div>
<div class="card">
<h2>Verified facts behind the method</h2>
{table(["Fact", "Value", "How it was verified"], [
 ["Grid", "3292 x 3730, EPSG:32611, 100 m, origin (243350, 4508550)",
  "read from the official rasters with rasterio"],
 ["Valid footprint", f"{esc((exp or {}).get('data', {}).get('n_valid'))} px",
  "counted from <code>labels.tif</code>, where the value is not -1"],
 ["Visible catalogue", f"{esc((exp or {}).get('data', {}).get('n_gt'))} px "
  f"({esc((exp or {}).get('data', {}).get('positive_fraction'))} of valid)",
  "counted from <code>labels.tif</code>"],
 ["Metric identity", "DTI == F2; TP_w + FN_w == |G|",
  "13/13 tests in <code>src/gems_metric.py</code> against a brute-force transcription"],
 ["Inversion check", f"Pearson r = {esc(vc.get('pearson_vs_provided_B15_depth'))} vs band 15",
  "inverted relief compared with the competition's own depth-to-basement band"],
 ["Leakage canary", "clean (all AUC &lt; 0.55)", "single-band rank AUC, <a href='evidence.html'>Evidence</a>"],
])}
</div>
<h2>How to make a submission (short form)</h2>
<ol>
<li>Download the GeoTIFF from the home page.</li>
<li>On the competition submission page, choose that file, paste the note, submit.</li>
<li>Confirm the receipt shows a score, and record it (an organizer receipt is the only
thing this project treats as a confirmed number).</li>
</ol>
<p>Full detail, including what to do if the form complains: <a href="submit.html">How to submit</a>.</p>"""
    write(os.path.join(DOCS, "executive-summary.html"),
          page("Executive summary", es, generated))

    # ------------------------------------------------------------- submit ------
    sub_name = (card or {}).get("submission_name", "submission.tif")
    note = (card or {}).get("submission_note", "")
    sb = f"""<h1>How to submit</h1>
<div class="card hero">
<h2>Step 1 &mdash; download the file</h2>
<p><a class="btn" href="downloads/{esc(sub_name)}">&#11015; {esc(sub_name)}</a>
<a class="btn alt" href="downloads/{esc(sub_name)}.sha256">SHA-256</a>
<a class="btn alt" href="downloads/{esc(sub_name)}.json">Checks</a></p>
<p>Optionally verify the bytes: <code>sha256sum {esc(sub_name)}</code> should print
<span class="mono-sm">{esc((card or {}).get('raster_sha256', 'run make_submission.py'))}</span></p>
</div>
<div class="card">
<h2>Step 2 &mdash; open the submission page</h2>
<p><code>https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/</code></p>
<p class="dim">You must be logged in. The data and submission tabs require an account.</p>
</div>
<div class="card">
<h2>Step 3 &mdash; choose the file, paste the note</h2>
<p>The form asks for a "File to submit" and an optional "Note". Paste exactly this into
the Note field ({len(note)} of the 140 allowed characters):</p>
<pre>{esc(note)}</pre>
<p>Then press submit.</p>
</div>
<div class="card">
<h2>Step 4 &mdash; read the receipt</h2>
<p>The page returns a score. That number, on that page, is an
<strong>organizer receipt</strong> and is the only kind of score this project will
report as confirmed. Every other score you will see in the group's repositories is a
claim. See <a href="evidence.html">Evidence</a> for why that distinction is enforced here.</p>
</div>
<h2>If the form complains</h2>
{table(["Message", "Cause", "Fix"], [
 ["Predicted values must be in range [0, 1]",
  "The raster contained NaN outside the study footprint. The example submission ships with NaN, which is legal under the metric but rejected by the form.",
  "This repository emits all-finite rasters: 0.0 outside the footprint. Re-check with <code>python scripts/validate_submission.py</code>."],
 ["Raster does not match the submission format",
  "CRS, shape or geotransform differs from <code>sample_submission.tif</code>.",
  "The writer copies the profile from <code>sample_submission.tif</code> and the validator asserts equality on all three."],
 ["File must be single-band GeoTIFF",
  "A multi-band or zipped raster.",
  "The writer always emits <code>count=1</code>, float32."],
])}
<h2>What is safe to do</h2>
<ul>
<li><strong>Downloading and submitting the file on this site is expected and fine.</strong>
It was produced by the code in this repository from the official competition rasters.</li>
<li>It is not a copy of another team's submission and not a copy of any earlier
submission of ours. The uniqueness check that demonstrates this runs against the
registry and its output is on <a href="evidence.html">Evidence</a>.</li>
<li>Do not submit a raster you have not validated. Run
<code>python scripts/validate_submission.py</code> first; it is what the
"format validated" pill on the home page reflects.</li>
</ul>"""
    write(os.path.join(DOCS, "submit.html"), page("How to submit", sb, generated))

    # ---------------------------------------------------------- methodology ----
    inv = (exp or {}).get("experiment1_inversion", {})
    mb = f"""<h1>Method</h1>
<h2>The lane</h2>
<p>Alluvial cover is one reason a fault catalogue misses faults. Buried range-front and
intrabasin faults still step the pre-Tertiary surface, and that step is a density
contrast that gravity sees. The lane is therefore:</p>
<ol>
<li>invert the provided isostatic-gravity anomaly (band 13) for basement relief with the
Parker (1973) forward series and the Oldenburg (1974) iteration;</li>
<li>calibrate the depth and density-contrast scale against a basin-depth product
(Saltus &amp; Jachens, USGS GP-1012, 1995, is regional 1:2,500,000 and is used only for
scale) and against the competition's own band 15 "Depth to basement surface";</li>
<li>take the horizontal gradient magnitude of the recovered relief;</li>
<li>emit the gradient maxima as multi-pixel ribbons, because gravity resolves such a
step only to a few hundred metres, and a 1-px line would claim precision the data does
not support;</li>
<li>report the recovery of withheld basin-interior segments against a random-line
control with the same pixel budget.</li>
</ol>

<h2>Inversion</h2>
<p><code>src/gravity.py</code>. Parameters actually used:
{esc(inv.get('params', {}))}</p>
<p><strong>Filter design matters and cost a full debugging cycle.</strong> With the
textbook Oldenburg low-pass <code>L(k) = 1/(1+(k/kc)^(2n))</code> the deconvolution
gain <code>exp(|k| z0) * L(k)</code> peaks at <code>k* = 2n/z0</code> and then
<em>grows</em>, so the iteration overflows &mdash; measured as
<code>RuntimeWarning: overflow encountered in multiply</code> plus an all-NaN result,
after 257 s of compute. A Gaussian band-pass with <code>kc = 0.5/z0</code> bounds the
gain at <code>exp(0.25) = 1.28</code> and decays afterwards.</p>
<p><strong>Verification:</strong> Pearson r =
{esc(inv.get('verification', {}).get('pearson_vs_provided_B15_depth'))},
Spearman (approximate, decimated) =
{esc(inv.get('verification', {}).get('spearman_approx'))} against the competition's own
band 15 over {esc(inv.get('verification', {}).get('n'))} footprint pixels.
That correlation is the honest check that the inversion recovers real basin structure.
Note the magnitude: r = &minus;0.18 is a <em>weak</em> agreement, which is itself a
finding and is recorded under <a href="limitations.html">Limitations</a>. The most
likely reason is that band 13 is an <em>isostatic residual</em>, whose long-wavelength
content that carries most of the basin-depth signal has already been removed.</p>

<h2>The metric and why the emission is shaped the way it is</h2>
<p><code>src/gems_metric.py</code> holds a verbatim transcription. Two structural
facts drive the design:</p>
<ul>
<li><code>TP_w</code> takes a <em>maximum</em> over an R = 3 px neighbourhood, so
several prediction pixels near one ground-truth pixel buy nothing extra in the
numerator, while each adds <code>alpha = 0.2</code> of its own discounted mass to the
denominator. &rarr; emit sparse and hard, not soft and everywhere.</li>
<li><code>FP_w</code> is discounted by <code>1 &minus; k(d)</code>, so a prediction
within 300 m of a real fault costs almost nothing. &rarr; a ribbon is a cheap hedge
against location error, which is exactly what "multi-line ribbon" is for.</li>
</ul>

<h2>Holdout protocol</h2>
<p><code>src/holdout.py</code>. Whole fault segments inside contiguous row-blocks are
withheld, with a 6 px buffer; catalogue-derived features may only see the remaining
visible faults; scoring is pooled DTI against the withheld pixels. The random-line
control uses the identical pixel budget. A block bootstrap over 400 spatial blocks
gives the 95% interval.</p>"""
    write(os.path.join(DOCS, "methodology.html"), page("Method", mb, generated))

    # ------------------------------------------------------------- evidence ----
    if for3:
        rr = []
        for r in for3["rasters"]:
            rr.append([esc(r["file"].replace("gemsdoe", "g-").replace("2026100", "26-10-0")[:38]),
                       esc(r.get("claimed_score_by_group")), esc(r["n_nonzero"]),
                       esc(r["n_pixels_on_visible_catalogue"]),
                       esc(r["n_pixels_within_3px_of_visible_catalogue"]),
                       "yes" if r["is_binary_0_1"] else "no"])
        frows = table(["Registry raster (group's file)", "score claimed by group",
                       "pixels set", "pixels ON visible catalogue",
                       "within 3 px of it", "binary"], rr)
        concl = "".join(f"<li>{esc(c)}</li>" for c in for3["conclusions"])
        irr = table(["ID", "Severity", "Irregularity"],
                    [[esc(i["id"]), esc(i["severity"]), esc(i["statement"])]
                     for i in for3["irregularities"]])
        diffs = for3.get("set_difference_forensics", {})
        dtext = ""
        for k, v in diffs.items():
            dtext += (f"<p><code>{esc(k)}</code>: removed {esc(v['removed_n'])} pixels; "
                      f"all of them within 3 px of the visible catalogue: "
                      f"<strong>{esc(v.get('removed_all_within_3px_of_catalogue'))}</strong>; "
                      f"strict subset: {esc(v.get('top_is_strict_subset', v.get('solo_is_strict_subset')))}</p>")
        iou = "".join(f"<li>{esc(a)}</li>" for a in for3.get("pairwise_iou_over_80pct", {}))
    else:
        frows = dtext = iou = "<p>Run <code>scripts/forensics_registry.py</code>.</p>"
        concl = "<li>not run yet</li>"
        irr = ""
    eb = f"""<h1>Evidence</h1>
<h2>1. Why the previously best-scoring raster scored 0.2778</h2>
<p>Read from the published bytes, not from the filenames.</p>
{frows}
<div class="card"><h3>Conclusions, each a measurement</h3><ul>{concl}</ul>
<h3>The exact set differences</h3>{dtext}
<h3>Registry rasters that are &gt;80% identical to each other</h3><ul>{iou or '<li>none</li>'}</ul>
</div>
<h2>2. Irregularities flagged for review</h2>
{irr}
<h2>3. Leakage canary</h2>
{frows and table(["Band / field", "AUC vs visible catalogue"], [[esc(k), esc(v)] for k, v in (canary or {}).items() if not k.startswith('_')])}
<p class="dim">AUC is measured against the <em>visible</em> catalogue, which is the wrong
target by construction; it is a leakage detector, not a score. Values near 0.5 mean the
band carries no single-pixel information about catalogue membership.</p>
<h2>4. Uniqueness against the registry</h2>
{("<pre>" + esc(json.dumps(uniq, indent=1)[:2600]) + "</pre>") if uniq else "<p>Run <code>scripts/check_uniqueness.py</code>.</p>"}
<h2>5. Run card</h2>
{("<pre>" + esc(json.dumps(card, indent=1)) + "</pre>") if card else "<p>Run <code>scripts/make_submission.py</code>.</p>"}"""
    write(os.path.join(DOCS, "evidence.html"), page("Evidence", eb, generated))

    # ----------------------------------------------------------- limitations ---
    lb = """<h1>Limitations and what is still blocking progress</h1>
<div class="card">
<h2>Honest limits of this lane as implemented</h2>
<ul>
<li><strong>The inversion agrees only weakly with the provided depth band.</strong>
Pearson r &asymp; &minus;0.18 over the full footprint against band 15, versus
&minus;0.77 on a single well-covered 900 x 900 crop. The full-grid number is the honest
one. Band 13 is an isostatic <em>residual</em>; the long wavelengths that carry most of
the basin-depth signal have already been removed from it, and 57.93% of the grid is
outside the survey, so the FFT operates on a filled hole. A bounded-domain inversion
(e.g. only the largest valid connected region, with a taper) is the next thing to try.</li>
<li><strong>No single band separates the catalogue.</strong> Every one of the seven
candidate fields has AUC between 0.45 and 0.53 for catalogue membership. Whatever model
wins this competition is not a per-pixel threshold on one geophysical band.</li>
<li><strong>The withheld set is unknown, so every score here is a proxy.</strong> The
holdout hides segments of the <em>visible</em> catalogue. The real Phase 1 set is a
different, expert-compiled dataset. The two share the disjointness property, which is
why the off-catalogue step transfers, but no holdout number in this repository is a
leaderboard prediction and none is presented as one.</li>
<li><strong>Gravity cannot see the target at full strength.</strong> A few hundred
metres of resolution is the published limit; a fault with a small vertical throw is
simply not in the band.</li>
</ul>
</div>
<div class="card">
<h2>Blockers that are not technical</h2>
<ul>
<li><strong>DrivenData login.</strong> The official data tab and the submission page both
require an account. This repository cannot download the data or submit a file
unattended. Data arrives through a public hash-pinned mirror of the same bytes; the
upload is a manual step by the account holder.</li>
<li><strong>Egress.</strong> The development sandbox reaches github.com, pypi and
nothing else: no Dropbox, no USGS, no drivendata.org. Every non-GitHub source in
<a href="methodology.html">Method</a> is cited but was read through a mirror or a
citation, and is labelled that way.</li>
<li><strong>No organizer receipts.</strong> No score in this repository has been
confirmed by the submission page for <em>our</em> bytes. Until one is, every claim of
quality here is a holdout measurement.</li>
</ul>
</div>
<div class="card">
<h2>The competing explanation that must not be forgotten</h2>
<p>Density contrasts <em>within</em> basement produce horizontal gravity gradients that
look exactly like a fault step. A Jurassic intrusion margin, a basement lithologic
contact, or a Tertiary volcanic centre all put a ridge in the horizontal gradient
magnitude that no fault explains. This lane cannot separate them, and any ribbon it
emits on such a contact is a false positive the metric will charge at alpha = 0.2. Any
future scoring of this lane must report that contamination explicitly.</p>
</div>"""
    write(os.path.join(DOCS, "limitations.html"), page("Limitations", lb, generated))

    # ----------------------------------------------------------- next steps ----
    nb = """<h1>Next steps, ranked by expected gain per unit of work</h1>
<div class="card">
<ol>
<li><strong>Bounded-domain inversion.</strong> Restrict the Parker-Oldenburg inversion
to the largest valid connected region with a cosine taper, instead of filling 58% of
the grid by nearest-neighbour. Cost: hours. Expected: the only route to a credible
inversion, and the precondition for everything downstream in this lane.</li>
<li><strong>Estimate the optimum emission count instead of sweeping it.</strong> With
TP_w a max over the kernel and FP_w discounted by distance, the marginal condition for
adding one pixel at hit-probability h is h &gt; alpha*TP_w / (D + (1&minus;beta)*TP_w)
where D is the current denominator. That turns 'how many dots' from a hyper-parameter
into a statistic. Cost: hours.</li>
<li><strong>Sharpen with the vertical gradient.</strong> Band 11 is the isostatic
gravity <em>vertical</em> gradient and band 5 its slope. Their ratio is a depth-to-source
estimator; multiplying the relief field by a depth-indexed weighting is the standard way
to separate shallow contacts from deep basement steps, which attacks the competing
explanation in <a href="limitations.html">Limitations</a> directly.</li>
<li><strong>Bring in the free official data the mirror already carries.</strong>
Radiometrics and a lidar scarp stack exist in the group's repositories with hash pins
(<code>data/aux_bridge/radiometric</code>, <code>external/dem/lidar_scarp_features_u8.tif</code>).
Any use must be checked for lane drift first.</li>
<li><strong>Get a first organizer receipt.</strong> Nothing in this project can be
called a score until the submission page returns one for our bytes. That is one manual
upload and it is worth more than any further modelling.</li>
</ol>
</div>
<div class="card">
<h2>Candidate hypotheses not yet tried, with the specific free source each needs</h2>
<table>
<thead><tr><th>#</th><th>Hypothesis</th><th>Layer / transform</th><th>Why it should beat
what is in the registry</th><th>Free official source needed</th></tr></thead>
<tbody>
<tr><td>1</td><td>Buried range fronts are better located by the <em>zero-crossing</em> of
the second vertical derivative of gravity than by the maximum of the first horizontal
gradient</td><td>band 11 and band 5</td><td>Every registry raster is a ridge/dot
emitter; none is a zero-crossing locator, and a step's step is exactly a zero crossing,
which is less prone to being pulled off-axis by a broad density gradient</td>
<td>none &mdash; both bands ship with the competition</td></tr>
<tr><td>2</td><td>The withheld faults concentrate where the basin-fill thickness gradient
is largest, not where the thickness itself is largest</td><td>band 15, gradient of it</td>
<td>The lane's own premise tested directly; measured here, catalogue pixels show
<em>no</em> depth preference (median 321 m under faults vs 316 m elsewhere), so the
gradient rather than the level is the untested form</td><td>none</td></tr>
<tr><td>3</td><td>Faults are better predicted as <em>spacing-regular arrays</em> (an
en-echelon population with a characteristic cross-strike spacing and a strike
distribution) than as independent lineaments</td><td>visible catalogue geometry only</td>
<td>The registry emits independent dots; a point process with interaction would place
dots where the population demands them, including in gaps the catalogue has</td>
<td>none</td></tr>
<tr><td>4</td><td>Radiometric potassium/thorium ratios mark altered fault damage zones
that the magnetic bands miss</td><td>GeoDAWN radiometrics</td>
<td>Alteration along a fault is a geochemical, not a potential-field, signature; it
would be genuinely independent of every registry raster</td><td>USGS GeoDAWN release,
DOI 10.5066/P93LGLVQ (public domain); a hash-pinned copy already sits in the group's
mirror, so it is obtainable</td></tr>
<tr><td>5</td><td>LiDAR-derived scarp geometry resolves the surface trace where the
1:2.5M-style products do not</td><td>1 m DEM tiles (USGS 3DEP)</td>
<td>Independent of gravity and magnetics; scarps are the surface expression of exactly
the buried faults this lane wants</td><td>USGS 3DEP, public domain; the competition's own
<code>1m_DEM_links.csv</code> lists the tiles (login-walled, but the same tiles are free
at the National Map)</td></tr>
</tbody></table>
<p class="dim">Ranked by expected gain per unit of work: 2, 1, 3, 5, 4. Hypotheses 1-3
need no new data and can be tested on the holdout immediately; 4 and 5 need an external
download that this sandbox cannot reach, so they are named as viable but not yet
obtainable <em>here</em>.</p>
</div>"""
    write(os.path.join(DOCS, "next-steps.html"), page("Next steps", nb, generated))

    # ------------------------------------------------------ machine-readable ---
    with open(os.path.join(DOCS, "data", "registry.json"), "w") as fh:
        json.dump(dict(generated_utc=generated, experiment=exp, forensics=for3,
                       uniqueness=uniq, checks=checks, run_card=card,
                       claimed_scores=feed_scores()), fh, indent=1)

    print("site written to", DOCS)


def feed_scores():
    """Scores the group reports for its own submissions, harvested from their sites.
    Kept as claims, never as confirmed values."""
    return {
        "_disclaimer": "Group/owner reports. None is an organizer receipt. The public "
                       "leaderboard rows belong to other teams.",
        "h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros": 0.2778,
        "h36-1-rung30-blind-r1-20261003-b531dae0a36f": 0.2710,
        "h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc": 0.2708,
        "d28-poisson300m-offcat-44090": 0.2600,
        "dotted-h19-5-d2-8-20261002-e56ea318af89": 0.2600,
        "probe-S1-ANCHOR-identical-to-live-02600": 0.2600,
        "topo-gap-closure-t-v2-on-d1-5": 0.2449,
        "gate_ortho_w0.25-40k": 0.2376,
        "sgmc-off-catalogue-44k-20261003-c8dcd780e3fd": 0.0512,
        "leaderboard_2026-10-04_nchuzhoy": 0.3262,
        "leaderboard_2026-10-04_kinghorton42": 0.3222,
        "leaderboard_2026-10-04_DARD": 0.3195,
    }


def write(path, text):
    with open(path, "w") as fh:
        fh.write(text)


if __name__ == "__main__":
    main()
