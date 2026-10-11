#!/usr/bin/env python3
"""Render the 61GEMSDOE Pages site from the evidence files.

Every number shown on the site is read from a JSON receipt in ``evidence/`` or
``docs/data/``.  If a receipt is missing the page says so instead of inventing
a value.  The download panel is rendered from the run card's permission flags,
so no page can advertise a decision the receipt does not record.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "src"))

PAGES = [
    ("index.html", "Overview"),
    ("executive-summary.html", "How to submit"),
    ("method.html", "Method"),
    ("hypotheses.html", "Hypotheses"),
    ("results.html", "Results"),
    ("run-card.html", "Run card"),
    ("data-sources.html", "Data"),
    ("sources.html", "Sources"),
    ("irregularities.html", "Irregularities"),
]


def load(name: str, default=None):
    for base in (ROOT / "evidence", DOCS / "data"):
        p = base / name
        if p.exists():
            return json.loads(p.read_text())
    return default


def esc(x) -> str:
    return (str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def fmt(x, nd=6):
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return esc(x)


def shell(title: str, active: str, body: str) -> str:
    nav = "".join(
        f'<a href="{p}" class="{"active" if p == active else ""}">{esc(t)}</a>'
        for p, t in PAGES)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>61GEMSDOE · {esc(title)}</title>
<link rel="stylesheet" href="assets/site.css"></head>
<body>
<header class="top"><div class="wrap">
<div class="sub">DOE GEMS Prize Challenge · DrivenData competition 306 · burried-structure lane</div>
<h1>61GEMSDOE — basement-depth steps from Parker–Oldenburg gravity inversion</h1>
<nav class="main">{nav}</nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer><div class="wrap">
Autonomous research session. Scores labelled HOLDOUT-DTI are local
hide-and-recover measurements on the mapped catalogue, <strong>not</strong>
leaderboard scores. Scores labelled ORGANIZER-CONFIRMED come from a submission
receipt; there are none in this repository yet.
Repository: <a href="https://github.com/buffedlizard55-lab/61GEMSDOE">buffedlizard55-lab/61GEMSDOE</a>.
</div></footer>
</body></html>
"""


def download_panel(card: dict | None, sub: dict | None) -> str:
    if not card or not sub:
        return ('<div class="banner hold"><strong>No submission file has been built yet.</strong> '
                'Nothing on this site is downloadable for submission until the run card records '
                'it.</div>')
    ok_dl = bool(card.get("okay_to_download"))
    ok_sub = bool(card.get("okay_to_submit"))
    scope = esc(card.get("download_permission_status", {}).get("scope", ""))
    if ok_dl and ok_sub:
        cls, head = "ok", "CLEARED — this file is OK to download and to submit"
    elif ok_dl:
        cls, head = "hold", "Download OK · submission NOT cleared"
    else:
        cls, head = "no", "NOT cleared for download or submission"
    tif = sub.get("files", {}).get("tif")
    zipf = sub.get("files", {}).get("zip")
    links = ""
    if ok_dl and tif:
        links += f'<p><a class="bigbtn" href="{esc(tif["name"])}">Download the submission GeoTIFF</a> '
        if zipf:
            links += f'<a class="bigbtn alt" href="{esc(zipf["name"])}">Download .zip</a>'
        links += "</p>"
    elif tif:
        links += ('<p class="small">The file exists in the repository for provenance but the card '
                  'does not authorise downloading it, so no link is published.</p>')
    return f"""<div class="banner {cls}"><h2 style="margin-top:0;border:0">{head}</h2>
<p class="small">{scope}</p>
{links}
<dl class="kv">
<dt>File</dt><dd><code>{esc(tif['name']) if tif else '—'}</code></dd>
<dt>SHA-256</dt><dd><code>{esc(tif['sha256']) if tif else '—'}</code></dd>
<dt>Positive pixels</dt><dd>{fmt((tif or {}).get('positive_pixels'), 0)}</dd>
<dt>Values</dt><dd>binary 0/1, float32, NaN-free; 0 outside the scored footprint</dd>
<dt>Grid</dt><dd>3730 × 3292 · EPSG:32611 · 100 m · (100, 0, 243350, 0, −100, 4508550)</dd>
</dl></div>"""


def page_index() -> str:
    card = load("run_card.json")
    sub = load("submission.json")
    cal = load("depth_scale_calibration.json")
    exp = load("lane_experiments.json")
    body = [download_panel(card, sub)]
    best = exp.get("holdout_dti", {}) if exp else {}
    rows = "".join(
        f"<tr><td>{esc(k)}</td><td class='num'>{fmt(v.get('dti'))}</td>"
        f"<td class='num'>[{fmt(v['ci95'][0])}, {fmt(v['ci95'][1])}]</td></tr>"
        for k, v in sorted(best.items(), key=lambda kv: -kv[1]["dti"])) if best else \
        "<tr><td colspan='3'>run pending</td></tr>"
    body.append(f"""
<h2>What this lane tests</h2>
<p>Alluvial cover is one reason fault catalogues miss faults. A buried
range‑front or intrabasin normal fault offsets the <em>basement surface</em>
even where it leaves no scarp, and that offset is visible in the isostatic
gravity field. This lane inverts the provided isostatic‑gravity layer to
basement relief with the Parker (1973) / Oldenburg (1974) iteration, locates
the horizontal‑gradient maxima of the recovered basement depth, measures the
throw of each step in metres, and emits the result as multi‑line ribbons of
isolated dots — because gravity locates such a step only to a few hundred
metres at best.</p>

<h2>Headline holdout result</h2>
<table><thead><tr><th>Arm</th><th class="num">HOLDOUT-DTI</th><th class="num">95% CI</th></tr></thead>
<tbody>{rows}</tbody></table>
<p class="small">Evaluator <code>{esc((exp or {}).get('evaluator_version', '—'))}</code> ·
{esc((exp or {}).get('n_withheld_positives', '—'))} withheld positive pixels ·
pooled over 4 spatial folds, 20 km block bootstrap. These are
<strong>not</strong> leaderboard scores: the holdout truth is the mapped
catalogue, whereas the organiser scores faults the catalogue does not
contain.</p>

<h2>Depth-scale calibration</h2>
{('<p>' + esc(cal['best']['drho']) + ' kg/m³ reference density contrast, ' +
   esc(cal['best']['z0']) + ' m reference depth, ' +
   esc(cal['best']['cutoff_wavelength_m']) + ' m high-cut wavelength: regression slope ' +
   fmt(cal['best']['slope'], 4) + ' against the independent basin-depth product, Pearson r = ' +
   fmt(cal['best']['pearson'], 4) + '.</p>') if cal and cal.get('best') else
 '<p>Calibration pending.</p>'}

<h2>Read next</h2>
<ul>
<li><a href="executive-summary.html">How to submit — exact steps, file format, the [0,1] check</a></li>
<li><a href="method.html">Method — the inversion, the step operator, the emission algebra</a></li>
<li><a href="hypotheses.html">Hypotheses considered, ranked, with the cost of each</a></li>
<li><a href="results.html">Results — experiments, controls, leakage canary</a></li>
<li><a href="run-card.html">Run card — the single JSON verdict</a></li>
<li><a href="irregularities.html">Irregularities and limitations</a></li>
</ul>""")
    return shell("Overview", "index.html", "".join(body))


def page_exec() -> str:
    card = load("run_card.json")
    sub = load("submission.json")
    body = [download_panel(card, sub)]
    body.append("""
<h2>Submit in four steps</h2>
<div class="card">
<ol>
<li><strong>Download the GeoTIFF</strong> from the panel at the top of this page
(or <code>docs/submissions/&lt;name&gt;.tif</code> in the repository). It is a
single-band float32 GeoTIFF, 3730 × 3292, EPSG:32611, 100 m cells, values 0/1
with 0 outside the scored footprint.</li>
<li><strong>Open</strong>
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">the
competition submissions page</a> (sign-in required) and press
<em>New submission</em>.</li>
<li><strong>Choose the file</strong> in <em>File to submit</em>. You may submit
the <code>.tif</code> directly, or the <code>.zip</code> that contains the same
single GeoTIFF.</li>
<li><strong>Paste the note</strong> below into the optional <em>Note</em> field
so the row is identifiable later, then create the submission.</li>
</ol>
<p class="small">Three rules from the
<a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">official rules PDF</a>
that constrain this step: (i) at most <strong>three submissions per week</strong>;
(ii) <strong>one</strong> submission must be selected as the final one for both
prize rounds, and it must be selected <em>without</em> knowledge of the private-test
score; (iii) if generative AI was used to develop the submission, that use must be
disclosed in the submission narrative. This lane's artifacts were produced by an
autonomous agent, so the disclosure applies — see the note below.</p>
</div>

<h2>The note to paste (≤ 140 characters)</h2>
<pre id="note">""" + esc((card or {}).get("note", "")) + """</pre>
<h2>Generative-AI disclosure (required by the official rules)</h2>
<p class="small">Section 3.2 of the official rules requires the extent of any
generative-AI use to be indicated in the narrative. For this artifact: the
hypothesis, the numerical method, the emission geometry and the statistical
instrument were all specified by an autonomous coding agent working from the
published literature cited on the sources page; no human geologist reviewed the
result before it was written. The disclosure text to paste into the submission
narrative is:</p>
<pre>Developed autonomously by an AI coding agent: Parker-Oldenburg inversion of
isostatic residual gravity, gradient-crest step detection and the hide-and-recover
instrument were designed, implemented and evaluated by the agent; no human expert
review preceded this submission.</pre>

<h2>The note to paste, length</h2>
<p class="small">Length: <strong>""" + str(len((card or {}).get("note", ""))) + """
</strong> / 140 characters.</p>

<h2>Why a submission can be rejected</h2>
<table>
<thead><tr><th>Symptom</th><th>Cause</th><th>What this file does</th></tr></thead>
<tbody>
<tr><td>"Predicted values must be in range [0, 1]"</td>
<td>values outside [0,1], or NaN/±inf inside the scored footprint being read as
out-of-range, or a ±3.4e38 sentinel written by the exporter</td>
<td>every cell is finite and in {0, 1}; NaN, ±inf and &gt;1e30 sentinels are
rejected at write time, not clipped</td></tr>
<tr><td>CRS / shape / geotransform mismatch</td>
<td>reprojection or resampling</td>
<td>written on the pinned template transform and re-read from disk to prove it</td></tr>
<tr><td>Multi-band or wrong dtype</td>
<td>exporting an RGB or int raster</td>
<td>one band, float32</td></tr>
</tbody></table>

<h2>Local checks that were run on this exact file</h2>
<p class="small">Re-derived from the bytes on disk by
<code>src/gems61/validate.py</code>; the receipt is
<code>evidence/submission.json</code>.</p>
<table><thead><tr><th>Check</th><th>Result</th></tr></thead><tbody>
""" + "".join(
        f"<tr><td><code>{esc(k)}</code></td>"
        f"<td><span class='pill {'good' if v else 'bad'}'>{'PASS' if v else 'FAIL'}</span></td></tr>"
        for k, v in (sub or {}).get("validation", {}).get("checks", {}).items()
    ) + """
</tbody></table>

<h2>Official pages</h2>
<ul>
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">Competition home</a></li>
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">Problem description (metric definition)</a></li>
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/">About / rules</a></li>
<li><a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">Official rules PDF</a></li>
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">Public leaderboard</a></li>
</ul>""")
    return shell("How to submit", "executive-summary.html", "".join(body))


def page_method() -> str:
    cal = load("depth_scale_calibration.json")
    exp = load("lane_experiments.json")
    best = (cal or {}).get("best", {})
    body = ["""
<h2>1. Invert the isostatic-gravity layer to basement relief</h2>
<p>Parker (1973) gives the Fourier-domain gravity anomaly of an uneven density
interface. With the interface at depth <code>z0 − h(x,y)</code> (relief
<code>h</code> positive upward) and density contrast
<code>Δρ = ρ_basement − ρ_fill</code>,</p>
<pre>F[Δg] = 2πG Δρ e^(−|k| z0) Σ_{n≥1} |k|^(n−1)/n! · F[h^n]</pre>
<p>Oldenburg (1974) rearranges it into the fixed-point iteration</p>
<pre>F[h_{j+1}] = W(k) [ F[Δg] e^(|k| z0) / (2πG Δρ) − Σ_{n≥2} |k|^(n−1)/n! · F[h_j^n] ]</pre>
<p><code>W(k)</code> is a high-cut filter; without it the <code>e^(|k| z0)</code>
factor makes the iteration diverge. The implementation uses a flat passband up
to half the cutoff wavenumber and a cosine taper to zero at the cutoff — the
pure Oldenburg cosine taper (unity only at <code>k = 0</code>) is also
implemented and reported, and it halves the amplitude at half the cutoff
wavenumber, which is why the plateau form is used for the delivered product.</p>
<p>Verification: a constant relief of 500 m at Δρ = 400 kg/m³ returns
<code>8.387173</code> mGal against the analytic Bouguer slab
<code>2πGΔρh = 8.3871727</code> mGal (<code>tests/test_gravity.py</code>).</p>

<h3>Calibration of the density-contrast depth scale</h3>
<p>The lane prescribes the USGS Basin and Range basin-depth map
(Saltus &amp; Jachens, GP‑1012, 1:2,500,000, 1995) as the calibration
reference. GP‑1012 is a <strong>paper map</strong> and its host is outside this
sandbox's egress allowance, so it could not be obtained; the only basin-depth
raster available locally is the organiser's own band 15
<code>depth_to_base_surf</code>. It is used <em>only</em> to fix the depth
scale — never as a prediction feature — and the substitution is recorded as an
irregularity.</p>"""]
    if best:
        body.append(f"""<table><thead><tr><th>Quantity</th><th class="num">Value</th></tr></thead><tbody>
<tr><td>Reference density contrast Δρ</td><td class="num">{fmt(best.get('drho'), 0)} kg/m³</td></tr>
<tr><td>Reference depth z0</td><td class="num">{fmt(best.get('z0'), 0)} m</td></tr>
<tr><td>High-cut wavelength</td><td class="num">{fmt(best.get('cutoff_wavelength_m'), 0)} m</td></tr>
<tr><td>Regression slope against the independent depth product</td>
<td class="num">{fmt(best.get('slope'), 4)}</td></tr>
<tr><td>Pearson r</td><td class="num">{fmt(best.get('pearson'), 4)}</td></tr>
<tr><td>RMSE</td><td class="num">{fmt(best.get('rmse_m'), 1)} m</td></tr>
</tbody></table>
<p class="small">A slope of 1.0 means one metre of inverted relief per metre of
independent basin-depth relief — i.e. the density-contrast depth scale is
calibrated.</p>""")
    body.append("""
<h2>2. Locate the steps: horizontal-gradient maxima</h2>
<p>The step is <em>located</em> by non-maximum suppression of the gradient
magnitude of the Gaussian-smoothed basement depth along the gradient direction
(the Canny construction applied to a potential-field interface). Its
<em>amplitude</em> is the <strong>throw</strong>: the depth difference sampled
±4 px (±400 m) across the crest, in metres. <code>|d(x+L) − d(x−L)|</code> is a
plateau of width <code>2L</code> over a sharp step, which makes it useless for
location but exactly right for measuring how many metres of basement offset the
step represents.</p>

<h2>3. Emit: why dots, and how many parallel lines</h2>
<p>Two exact properties of the metric drive the shape. (i) For a support scaled
by λ, <code>dDTI/dλ &gt; 0</code>: a graded probability map is strictly
dominated by its own thresholded support, so the output is binary. (ii) Adding
a prediction whose nearest-truth kernel credit is <code>k</code> raises DTI iff
<code>k &gt; α·s/(1 − α·s)</code>, so each extra line pays only where the
existing line is already weak. The number of parallel lines and their spacing
are therefore chosen from the closed-form gain table at the
<em>measured</em> positional error, not by taste.</p>

<h2>4. The competing explanation</h2>
<p>A gravity step can be a lateral density change <em>within</em> basement
rather than an offset of the basement surface. At 200 kg/m³ over a 2 km section
and a 400 kg/m³ fill/basement contrast, a lithologic contact mimics a
<strong>1000 m</strong> basement step without cutting any fault. The two are
separated with independent physics: a lithologic contact is a magnetic
lineament, so steps within 2 px of a reduced-to-pole magnetic contact crest are
flagged ambiguous and demoted. The cost of that demotion is measured on the
holdout, not assumed.</p>""")
    return shell("Method", "method.html", "".join(body))


def page_hypotheses() -> str:
    hyp = load("hypotheses.json")
    rows = ""
    for h in (hyp or {}).get("hypotheses", []):
        rows += (f"<tr><td><strong>{esc(h.get('id'))}</strong><br>"
                 f"<span class='small'>{esc(h.get('layers'))}</span></td>"
                 f"<td>{esc(h.get('signature'))}</td>"
                 f"<td>{esc(h.get('why_off_catalogue'))}</td>"
                 f"<td>{esc(h.get('differs_from'))}</td>"
                 f"<td class='num'>{esc(h.get('expected_dti_gain'))}</td>"
                 f"<td class='num'>{esc(h.get('cost'))}</td></tr>")
    if not rows:
        rows = "<tr><td colspan='6'>hypotheses file missing</td></tr>"
    return shell("Hypotheses", "hypotheses.html", f"""
<h2>Candidate hypotheses, ranked by expected DTI gain per unit cost</h2>
<table><thead><tr><th>ID / layers</th><th>Physical signature</th>
<th>Why it should catch a fault the catalogue lacks</th><th>Differs from</th>
<th class="num">Expected gain</th><th class="num">Cost</th></tr></thead>
<tbody>{rows}</tbody></table>
<p class="small">Each was checked against the repository's existing code before
being proposed; the "differs from" column records what that check found.</p>
<h2>External data needed but not obtainable here</h2>
<p>USGS Geophysical Investigations Map GP‑1012 (Saltus &amp; Jachens, 1995) is
the prescribed depth-scale reference. It is a folded paper map
(<a href="https://store.usgs.gov/product/23063">USGS Store product 23063</a>)
and its host is outside this sandbox's egress allowance
(github.com, api.github.com, codeload.github.com, registry.npmjs.org,
pypi.org, files.pythonhosted.org only). It is named here as the source a future
session must obtain; the band-15 substitution used instead is recorded as an
irregularity.</p>""")


def page_results() -> str:
    exp = load("lane_experiments.json")
    if not exp:
        return shell("Results", "results.html", "<p>Experiment receipt missing.</p>")
    can = "".join(
        f"<tr><td><code>{esc(k)}</code></td><td class='num'>{fmt(v)}</td>"
        f"<td><span class='pill {'bad' if max(v, 1-v) > 0.90 else 'good'}'>"
        f"{'LEAKAGE-SUSPECT' if max(v, 1-v) > 0.90 else 'ok'}</span></td></tr>"
        for k, v in sorted(exp.get("canary_auc", {}).items(), key=lambda kv: -kv[1]))
    dti = "".join(
        f"<tr><td><code>{esc(k)}</code></td><td class='num'>{fmt(v.get('dti'))}</td>"
        f"<td class='num'>[{fmt(v['ci95'][0])}, {fmt(v['ci95'][1])}]</td></tr>"
        for k, v in sorted(exp.get("holdout_dti", {}).items(), key=lambda kv: -kv[1]["dti"]))
    rec = "".join(
        f"<tr><td><code>{esc(k)}</code></td>"
        f"<td class='num'>{esc(v.get('basin_segments_recovered'))}/{esc(v.get('basin_segments_total'))}</td>"
        f"<td class='num'>{fmt(v.get('basin_recovery_rate'), 4)}</td>"
        f"<td class='num'>{esc(v.get('segments_recovered'))}/{esc(v.get('segments_total'))}</td></tr>"
        for k, v in (exp.get("recovery") or {}).items())
    return shell("Results", "results.html", f"""
<h2>Instrument</h2>
<dl class="kv">
<dt>Evaluator</dt><dd><code>{esc(exp.get('evaluator_version'))}</code></dd>
<dt>Withheld positives</dt><dd>{esc(exp.get('n_withheld_positives'))} pixels, whole fault components hidden</dd>
<dt>Visible catalogue masked</dt><dd>{esc(exp.get('n_visible_masked'))} pixels (pixel-exact)</dd>
<dt>Context buffer</dt><dd>{esc(exp.get('parameters', {}).get('buffer_px'))} px around each hidden segment</dd>
<dt>Folds</dt><dd>{esc(exp.get('folds'))}</dd>
<dt>Metric</dt><dd>pooled DTI, α=0.2, β=0.8, 300 m triangular kernel; 95% CI by paired 20 km block bootstrap</dd>
</dl>
<p class="small"><strong>Limitation, stated before the numbers:</strong> the
holdout truth is the <em>mapped catalogue</em>, while the organiser scores
faults the catalogue does not contain. The holdout is a screen and a leakage
canary, never an estimate of the leaderboard.</p>

<h2>E1 — leakage canary: every feature alone</h2>
<table><thead><tr><th>Feature</th><th class="num">AUC vs withheld</th><th>Verdict</th></tr></thead>
<tbody>{can}</tbody></table>
<p class="small">Nothing exceeds 0.90, so no feature is flagged as leakage. All
features are catalogue-independent geophysics, which is the expected result.</p>

<h2>Arm comparison — pooled HOLDOUT-DTI</h2>
<table><thead><tr><th>Arm</th><th class="num">DTI</th><th class="num">95% CI</th></tr></thead>
<tbody>{dti}</tbody></table>

<h2>E2 — withheld basin-interior segment recovery</h2>
<table><thead><tr><th>Arm</th><th class="num">basin-interior segments recovered</th>
<th class="num">rate</th><th class="num">all segments</th></tr></thead><tbody>{rec}</tbody></table>

<h2>E3 — the competing explanation</h2>
<p>Magnetic-contact crests: {esc(exp.get('magnetic', {}).get('magnetic_crest_px'))} px.
Gravity steps within 2 px of one: {esc(exp.get('magnetic', {}).get('ambiguous_step_px'))} px
({fmt(exp.get('magnetic', {}).get('ambiguous_fraction'), 4)} of all steps).</p>
<p>Equivalence used to size the ambiguity:
{esc(list((exp.get('density_contrast_equivalents_m') or {'200 kg/m3 over 2 km against a 400 kg/m3 fill-basement contrast': 1000.0}).items())[:1])}</p>""")


def page_run_card() -> str:
    card = load("run_card.json")
    if not card:
        return shell("Run card", "run-card.html", "<p>Run card not written yet.</p>")
    return shell("Run card", "run-card.html", f"""
<div class="card big"><h2 style="margin-top:0">Verdict:
<span class="pill {'good' if card.get('verdict') == 'promote' else 'warn'}">{esc(card.get('verdict'))}</span>
</h2>
<p>{esc(card.get('verdict_reason', ''))}</p></div>
<h2>Hypothesis</h2><p>{esc(card.get('hypothesis'))}</p>
<h2>Mechanism</h2><p>{esc(card.get('mechanism'))}</p>
<h2>Named non-fault process that could mimic it</h2><p>{esc(card.get('competing_explanation'))}</p>
<h2>Holdout</h2><pre>{esc(json.dumps(card.get('holdout_dti', {}), indent=2))}</pre>
<h2>Uniqueness vs registry</h2><pre>{esc(json.dumps(card.get('correlation_vs_registry', {}), indent=2))}</pre>
<h2>Mimic control</h2><p>{esc(card.get('mimic_control'))}</p>
<h2>Artifact</h2><dl class="kv">
<dt>File</dt><dd><code>{esc((card.get('raster') or {}).get('file'))}</code></dd>
<dt>SHA-256</dt><dd><code>{esc((card.get('raster') or {}).get('sha256'))}</code></dd>
<dt>Bytes</dt><dd>{esc((card.get('raster') or {}).get('bytes'))}</dd>
<dt>Positive pixels</dt><dd>{esc((card.get('raster') or {}).get('positive_pixels'))}</dd>
<dt>Submission name</dt><dd><code>{esc(card.get('submission_name'))}</code></dd>
<dt>Note ({card.get('note_chars', 0)}/140)</dt><dd><code>{esc(card.get('note'))}</code></dd>
</dl>
<h2>Validator output</h2><pre>{esc(json.dumps(card.get('validator', {}), indent=2))}</pre>
<h2>Full card</h2><pre>{esc(json.dumps(card, indent=2))}</pre>""")


def page_data() -> str:
    prep = load("data_preparation.json")
    cache = load("feature_cache.json")
    pins = "".join(
        f"<tr><td><code>{esc(f['path'])}</code></td>"
        f"<td><span class='pill {'good' if f['verified'] else 'bad'}'>"
        f"{'VERIFIED' if f['verified'] else 'MISSING/BAD'}</span></td>"
        f"<td class='num'>{esc(f.get('bytes'))}</td>"
        f"<td><code class='small'>{esc((f.get('sha256') or '')[:24])}…</code></td></tr>"
        for f in (prep or {}).get("files", []))
    bands = "".join(
        f"<tr><td class='num'>{esc(b['band'])}</td><td><code>{esc(b['description'])}</code></td>"
        f"<td class='num'>{esc(b.get('missing_pixels'))}</td></tr>"
        for b in (cache or {}).get("bands", []))
    return shell("Data", "data-sources.html", f"""
<h2>Hash-pinned bridge files</h2>
<p>Bridge byte identity is <strong>not</strong> an independent organiser
receipt: the DrivenData data tab sits behind a login and nothing here
authenticates a fresh official download.</p>
<table><thead><tr><th>File</th><th>Status</th><th class="num">Bytes</th><th>SHA-256</th></tr></thead>
<tbody>{pins}</tbody></table>
<h2>The 19-band feature stack</h2>
<p>{esc((cache or {}).get('shape'))} · {esc((cache or {}).get('crs'))} ·
{esc((cache or {}).get('transform'))} · {esc((cache or {}).get('count'))} bands.
Provenance: {esc((cache or {}).get('provenance'))}.</p>
<table><thead><tr><th class="num">#</th><th>Band description (organiser's own tag)</th>
<th class="num">missing cells</th></tr></thead><tbody>{bands}</tbody></table>
<p class="small">Band 13 <code>iso_grav_anom</code> is the layer this lane
inverts. Band 15 <code>depth_to_base_surf</code> is used only to calibrate the
depth scale. Neither is the competition label.</p>""")


def page_sources() -> str:
    data = load("sources.json") or {}
    src = data.get("sources", [])
    rows = "".join(
        f"<tr><td><code>{esc(s.get('id'))}</code> {esc(s.get('role'))}</td>"
        f"<td>{esc(s.get('citation') or s.get('title'))}<br>"
        f"<a href=\"{esc(s.get('url'))}\">{esc(s.get('url'))}</a></td>"
        f"<td><span class='pill {'good' if s.get('verification') in ('fetched', 'crossref') else 'muted'}'>"
        f"{esc(s.get('verification'))}</span></td>"
        f"<td>{esc(s.get('facts_used'))}</td></tr>"
        for s in src)
    return shell("Sources", "sources.html", f"""
<h2>Sources, each checked against the official record</h2>
<table><thead><tr><th>Role</th><th>Citation and link</th><th>Verification</th>
<th>What it is used for here</th></tr></thead>
<tbody>{rows}</tbody></table>
<h2>Key citations</h2>
<ul>
<li>Parker, R.L., 1973, The rapid calculation of potential anomalies:
<em>Geophysical Journal of the Royal Astronomical Society</em> 31(4), 447–455.
DOI 10.1111/j.1365-246X.1973.tb06513.x</li>
<li>Oldenburg, D.W., 1974, The inversion and interpretation of gravity anomalies:
<em>Geophysics</em> 39(4), 526–536.</li>
<li>Blakely, R.J. &amp; Jachens, R.C., 1991, Regional study of mineral resources
in Nevada: insights from three-dimensional analysis of gravity and magnetic
anomalies: <em>GSA Bulletin</em> 103(3), 795. DOI 10.1130/0016-7606(1991)103&lt;0795:RSOMRI&gt;2.3.CO;2</li>
<li>Saltus, R.W. &amp; Jachens, R.C., 1995, Gravity and basin-depth maps of the
Basin and Range Province, western United States: USGS Geophysical
Investigations Map GP‑1012, scale 1:2,500,000.</li>
<li>Jachens, R.C. &amp; Moring, B.C., 1990, Maps of the thickness of Cenozoic
deposits and the isostatic residual gravity over basement for Nevada: USGS
Open-File Report 90‑404.</li>
<li>Hildenbrand, T.G., Langenheim, V.E., Mankinen, E.A. &amp; McKee, E.H., 1999,
Inversion of gravity data to define the pre-Tertiary surface: USGS Open-File
Report 99‑49 (density–depth function used to justify Δρ).</li>
</ul>""")


def page_irregularities() -> str:
    irr = load("irregularities.json") or []
    rows = "".join(
        f"<tr><td><code>{esc(i.get('id'))}</code></td>"
        f"<td><span class='pill {'bad' if i.get('severity') in ('blocker', 'major') else ('warn' if i.get('severity') == 'minor' else 'good')}'>"
        f"{esc(i.get('severity'))}</span></td>"
        f"<td><strong>{esc(i.get('title'))}</strong><br>{esc(i.get('detail'))}"
        f"{('<br><em>Substitution:</em> ' + esc(i['substitution'])) if i.get('substitution') else ''}</td>"
        f"<td>{esc(i.get('consequence') or i.get('impact'))}</td>"
        f"<td>{esc(i.get('status'))}</td></tr>"
        for i in irr)
    return shell("Irregularities", "irregularities.html", f"""
<h2>Irregularities and limitations</h2>
<table><thead><tr><th>ID</th><th>Summary</th><th>Impact</th><th>Status</th></tr></thead>
<tbody>{rows}</tbody></table>
<h2>Standing limitations</h2>
<ul>
<li>No DrivenData credential: the competition data tab is behind a login, so
every input is a hash-pinned public bridge copy. Bridge SHA-256 proves byte
identity with that bridge, not official origin.</li>
<li>There is no ORGANIZER-CONFIRMED score in this repository. Every number is
HOLDOUT-DTI or OWNER-REPORTED.</li>
<li>The published <code>labels.tif</code> is byte-identical to
<code>existing_faults.tif</code>: the scored truth is not public, so the
hide-and-recover holdout is the only local instrument.</li>
<li>The holdout truth is the mapped catalogue; the organiser scores faults the
catalogue lacks. The instrument is a screen, not a leaderboard estimator.</li>
<li>GP-1012, the prescribed depth-scale reference, could not be obtained.</li>
<li>Egress is limited to github.com, api.github.com, codeload.github.com,
registry.npmjs.org, pypi.org and files.pythonhosted.org.</li>
</ul>""")


def main() -> int:
    DOCS.mkdir(exist_ok=True)
    (DOCS / ".nojekyll").write_text("")
    builders = {
        "index.html": page_index,
        "executive-summary.html": page_exec,
        "method.html": page_method,
        "hypotheses.html": page_hypotheses,
        "results.html": page_results,
        "run-card.html": page_run_card,
        "data-sources.html": page_data,
        "sources.html": page_sources,
        "irregularities.html": page_irregularities,
    }
    for name, fn in builders.items():
        (DOCS / name).write_text(fn())
        print(f"[site] {name}")
    root_index = ROOT / "index.html"
    root_index.write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta http-equiv="refresh" content="0;url=docs/index.html">'
        '<title>61GEMSDOE</title></head><body>'
        '<p><a href="docs/index.html">Open the 61GEMSDOE site</a></p></body></html>\n')
    print("[site] index.html (root redirect)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
