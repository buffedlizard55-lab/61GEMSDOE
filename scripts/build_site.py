#!/usr/bin/env python
"""Render docs/ (GitHub Pages) from the evidence files.  No hand-edited HTML."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
DOCS = ROOT / "docs"
DOWNLOADS = DOCS / "downloads"

CSS = """
:root{--ink:#10202b;--mut:#5a6b78;--line:#d8e0e6;--ok:#0b7a3b;--warn:#b45309;--bad:#b42318;--bg:#fbfcfd}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:900px;margin:0 auto;padding:28px 20px 80px}
h1{font-size:30px;line-height:1.2;margin:.2em 0 .3em}
h2{font-size:21px;margin:2em 0 .5em;border-bottom:1px solid var(--line);padding-bottom:.25em}
h3{font-size:17px;margin:1.4em 0 .35em}
p,li{color:var(--ink)}
small,.mut{color:var(--mut)}
.banner{border-radius:12px;padding:18px 20px;margin:18px 0;border:1px solid}
.ok{background:#eefaf1;border-color:#b6e2c5}
.warn{background:#fff8ec;border-color:#f2d6a8}
.bad{background:#fdeeed;border-color:#f3c2bd}
.banner strong{display:block;font-size:19px;margin-bottom:6px}
.ok strong{color:var(--ok)} .warn strong{color:var(--warn)} .bad strong{color:var(--bad)}
a.btn{display:inline-block;background:#0b5cff;color:#fff;text-decoration:none;padding:12px 20px;border-radius:9px;font-weight:600;margin:6px 8px 6px 0}
a.btn.alt{background:#fff;color:#0b5cff;border:1px solid #0b5cff}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:14.5px}
th,td{border:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}
th{background:#f1f5f8}
code{background:#f1f5f8;padding:1px 5px;border-radius:4px;font-size:13.5px}
nav a{margin-right:14px}
ul.tight li{margin:.15em 0}
.pill{display:inline-block;font-size:12.5px;padding:2px 8px;border-radius:99px;background:#eef2f6;color:var(--mut);margin-left:6px}
"""


def read(name, default=None):
    p = EVID / name
    return json.loads(p.read_text()) if p.exists() else default


def page(title, body, nav=True):
    links = ('<nav>' + (
        '<a href="index.html">Home</a>'
        '<a href="executive-summary.html">How to submit</a>'
        '<a href="method.html">Method</a>'
        '<a href="hypotheses.html">Hypotheses</a>'
        '<a href="verify.html">Verification</a>'
        '<a href="instrument.html">Instrument study</a>'
        '<a href="evidence.html">Evidence</a>'
        '<a href="irregularities.html">Irregularities</a>'
        '<a href="limitations.html">Limitations</a>'
        '<a href="next-steps.html">Next steps</a>'
    ) + '</nav>') if nav else ""
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{title}</title><style>{CSS}</style></head><body><main>{links}"
            f"<h1>{title}</h1>{body}</main></body></html>")


def fmt(x, n=3):
    try:
        return f"{float(x):.{n}f}"
    except Exception:                                    # noqa: BLE001
        return "—"


def main() -> None:
    final = read("final.json", {})
    uniq = read("uniqueness.json", {})
    meas = read("measure.json", {})
    hold = read("holdout.json", {})
    hyp = read("hypotheses.json", {})
    ver = read("verify_grid.json", {})
    if not final:
        raise SystemExit("evidence/final.json missing -- run the final stage first")

    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    tif_src = ROOT / final["tif"]
    tif_name = tif_src.name
    shutil.copy2(tif_src, DOWNLOADS / tif_name)
    zip_src = ROOT / final["zip"]
    shutil.copy2(zip_src, DOWNLOADS / zip_src.name)
    json_src = ROOT / final["receipt"]
    if json_src.exists():
        shutil.copy2(json_src, DOWNLOADS / json_src.name)
    (DOWNLOADS / f"{tif_name}.sha256").write_text(
        f"{final['writer_receipt']['sha256']}  {tif_name}\n"
    )
    rows = uniq.get("rows", [])
    ok_rho = uniq.get("worst_spearman_full_footprint", 1.0) < 0.90
    ok_ov = uniq.get("worst_overlap_gate_value", 1.0) < 0.70
    unique = uniq.get("verdict") == "unique"
    props = final["live_property_vector"]

    banner = (f'<div class="banner {"ok" if unique and ok_rho and ok_ov else "warn"}">'
              f'<strong>{"Download: OK. Submit to competition: OK." if unique else "Download: OK. Submit: CHECK THE EVIDENCE FIRST."}</strong>'
              f'This GeoTIFF passed every local format gate and is <b>{uniq.get("verdict","?")}</b> '
              f'against all {uniq.get("corpus_rasters_compared","?")} sibling rasters that could be '
              f'downloaded and compared (worst rank correlation '
              f'{fmt(uniq.get("worst_spearman_full_footprint"))}, worst dot overlap '
              f'{fmt(uniq.get("worst_overlap_gate_value"))}; thresholds 0.90 and 0.70). '
              f'No competition slot has been spent and no organizer has scored this file.'
              f'</div>')

    p_cross = meas.get("cross_check_vs_published_depth", {})
    div = meas.get("divergence_trace", [])
    body = f"""
{banner}
<p><a class="btn" href="downloads/{tif_name}">↓ Download the GeoTIFF ({final['writer_receipt']['bytes']:,} bytes)</a>
<a class="btn alt" href="downloads/{Path(final['zip']).name}">↓ Single-TIFF ZIP</a>
<a class="btn alt" href="downloads/{Path(final['tif']).stem}.json">Run card (JSON)</a></p>

<h2>What you are downloading</h2>
<table>
<tr><th>File</th><td><code>{tif_name}</code></td></tr>
<tr><th>SHA256</th><td><code>{final['writer_receipt']['sha256']}</code></td></tr>
<tr><th>Type</th><td>single-band Float32 GeoTIFF, EPSG:32611, 3730 × 3292, 100 m,
    transform <code>(100, 0, 243350, 0, -100, 4508550)</code></td></tr>
<tr><th>Values</th><td>{final['writer_receipt']['validator'].get('min','0')} to
    {final['writer_receipt']['validator'].get('max','1')}; every cell finite;
    {final['writer_receipt']['validator'].get('n_nan',0)} NaN;
    {'0' if final['writer_receipt']['validator'].get('n_nan',0)==0 else 'non-zero'} non-finite;
    zero positive mass outside the footprint; <b>zero</b> positive pixels on the mapped-fault catalogue</td></tr>
<tr><th>Emitted</th><td>{final['writer_receipt']['validator'].get('emitted_positive_pixels', props['n_dots']):,} positive pixels
    ({props['n_dots']:,} selected dots, then each grown to a 3 × 3 ribbon)</td></tr>
<tr><th>Suggested name</th><td><code>{final['submission']}</code></td></tr>
<tr><th>Suggested note</th><td>{final['note']} <span class="pill">{final['writer_receipt']['note_chars']} / 140 characters</span></td></tr>
</table>
<p class="mut">{final['verdict']}</p>
<h2>Other submissions in this repository</h2>
<p>A parallel session on this repository built the same lane independently and merged first. Its
artifacts are kept and are <i>not</i> replaced by this page: see
<a href="instrument.html">the instrument study</a>,
<a href="downloads/">the E3 candidate in <code>docs/downloads/</code></a>
(<code>…basement-step-r3-rib2-k40k-2pxprune-zeros.tif</code>) and its receipts in
<code>evidence/e1_calibration.json</code>, <code>e2b_instrument.json</code>,
<code>e2c_canary.json</code>, <code>e3_submission.json</code>. Two independent constructions of one
lane is the intended redundancy; neither file has spent a competition slot.</p>

<h2>Where the dots sit — measured, not claimed</h2>
<table>
<tr><th>Property of the emitted dots</th><th>This file</th><th>Best-known live file (owner-reported 0.2778)</th></tr>
<tr><td>number of dots</td><td>{props['n_dots']:,}</td><td>37,654</td></tr>
<tr><td>median offset from the mapped catalogue</td><td>{fmt(props['median_distance_px'],1)} px</td><td>19.6 px</td></tr>
<tr><td>mean offset from the mapped catalogue</td><td>{fmt(props['mean_distance_px'],1)} px</td><td>29.0 px</td></tr>
<tr><td>dots within 2 px of the catalogue</td><td>{fmt(props['frac_within_2px']*100,2)} %</td><td>0.0 %</td></tr>
<tr><td>dots on the catalogue</td><td>{fmt(props['frac_on_catalogue']*100,2)} %</td><td>0.0 %</td></tr>
</table>
<p class="mut">The right-hand column is <b>OWNER-REPORTED</b>: those numbers come from a sibling
project's record of its own leaderboard rows. Over its 15 scored rasters the owner reports
Spearman ρ = −0.81 between dot count and live score and +0.85 between mean offset and live score.
No number in either column is a score for this file.</p>

<h2>How it was made (short version)</h2>
<ol class="tight">
<li>Invert the supplied isostatic residual gravity (band 13) for depth to basement with the
    Parker–Oldenburg operator, at 400 m, using the first iterate — the low-passed Bouguer slab —
    because the non-linear correction is measured to diverge here
    (forward residual {fmt(div[0]['rms_residual_mgal'],2) if div else '—'} mGal after one
    iteration, {fmt(div[-1]['rms_residual_mgal'],2) if div else '—'} mGal at iteration
    {len(div) if div else '—'}).</li>
<li>Calibrate the reference level and the density contrast against USGS <b>GP-1012</b>
    (Saltus &amp; Jachens 1995) — the published map on which basin fill is thicker than 1 km
    over about 20 % of the province. Selected: z<sub>0</sub> = {meas.get('chosen',{}).get('z0_m','—')} m,
    Δρ = {meas.get('chosen',{}).get('delta_rho','—')} kg/m³, giving
    {fmt(meas.get('chosen',{}).get('stats',{}).get('fraction_gt_1km',0)*100,1)} % deeper than 1 km.</li>
<li>Take the automatic maxima of the horizontal gradient of that surface
    (Blakely &amp; Simpson 1986) and <b>keep only the ones with measured throw</b> ≥
    80 m across an 800 m (9 × 9 px) baseline and buried-scarp sharpness
    <code>throw / max(depth, 0.5·z<sub>0</sub>) ≥ 0.08</code> — a lineament is not a fault; a fault has displacement.</li>
<li>Fuse that evidence with the offset band around the mapped traces and the supplied gravity
    horizontal/vertical gradient depth-index (<code>|HG| / (|VG| + ε)</code>, bands 18 &amp; 11),
    and emit dots on a 2 × 2 px decimated ranking where the competition metric's own marginal test says a dot pays.</li>
</ol>
<p>Cross-check: the inverted surface correlates <b>r = {fmt(p_cross.get('pearson_r'))}</b>
(slope {fmt(p_cross.get('slope_published_on_inverted'))}) with the competition's own
<code>depth_to_base_surf</code> band — two independently derived depth surfaces agreeing on the
broad pattern, not a copy of one another.</p>

<h2>What this file does NOT claim</h2>
<ul class="tight">
<li>It has <b>not</b> been scored. There is no organizer receipt for it. Nothing here is a leaderboard score.</li>
<li>The catalogue-frame holdout scores it <b>{fmt(hold.get('lane_vs_control',{}).get('lane',0),4)}</b> and a random-line control <b>{fmt(hold.get('lane_vs_control',{}).get('control',0),4)}</b>
    {f"(n = {hold.get('n_withheld_truth_px','—'):,} withheld truth px)" if isinstance(hold.get('n_withheld_truth_px'), int) else ""}.
    That instrument hides mapped traces and rewards dots placed <i>on</i> them; this file is
    deliberately placed off them, so the instrument cannot rank it. The disagreement is
    irregularity <code>IR-57-INSTR-01</code>, restated here rather than tuned away.</li>
<li>The promotion argument therefore rests on the owner-reported statistics in the table above,
    which are statistics about <i>other people's files</i>, not about this one.</li>
</ul>
"""
    (DOCS / "index.html").write_text(page("61GEMSDOE — buried structures from gravity inversion", body))

    sub = f"""
<div class="banner ok"><strong>Two minutes, start to finish.</strong> Download the GeoTIFF at the
top of the <a href="index.html">home page</a>, then paste the name and the note into the
submission dialog. Nothing else is needed.</div>
<h2>1 · Download</h2>
<p>On the <a href="index.html">home page</a>, click <b>Download the GeoTIFF</b>. The file is
<code>{tif_name}</code>. If the portal prefers a ZIP, use <b>Single-TIFF ZIP</b> instead — it
contains exactly one GeoTIFF and nothing else. Do not upload the JSON run card, this page, or a
ZIP of the repository.</p>
<h2>2 · Check it is the file you think it is (optional, 10 seconds)</h2>
<p>Re-hash it. On macOS/Linux: <code>shasum -a 256 {tif_name}</code> — it must print</p>
<p><code>{final['writer_receipt']['sha256']}</code></p>
<h2>3 · Fill in the dialog</h2>
<table>
<tr><th>Field</th><th>Value</th></tr>
<tr><td>Name</td><td><code>{final['submission']}</code></td></tr>
<tr><td>Note (≤ 140 characters)</td><td>{final['note']} <span class="pill">{final['writer_receipt']['note_chars']} / 140</span></td></tr>
<tr><td>File</td><td><code>{tif_name}</code> (or the single-TIFF ZIP)</td></tr>
</table>
<h2>4 · What happens next, and what does not</h2>
<ul class="tight">
<li>Uploading spends one of the three weekly submission slots. <b>This repository has not spent
    one.</b> Promotion to a slot is your decision.</li>
<li>When a score comes back, write it down with the date. That number, and only that number, is
    a competition score; everything on this site is labelled MEASURED, HOLDOUT-DTI or
    OWNER-REPORTED and none of those is a score.</li>
<li>If the portal rejects the file, capture the exact error text and add it to
    <code>evidence/</code> — a rejection is evidence, and the range error reported against an
    earlier site's download is the reason every value here is checked to be finite and inside
    [0, 1] before the file is written.</li>
</ul>
<h2>Why the file is shaped the way it is</h2>
<p>The competition metric is
<code>DTI = TP_w / (TP_w + 0.2·FP_w + 0.8·FN_w)</code> with a triangular kernel of radius 300 m,
and the mapped-fault catalogue is masked out of scoring. Two consequences decide the shape of
this file: <b>a dot on a mapped trace earns nothing</b> (the pixel is not scored), and
<b>a dot only pays if it lands within about 280 m of a hidden truth pixel</b> at the scores
currently on the board. That is why the dots sit in a band a few pixels off the mapped traces
rather than on them, and why they are dots and ribbons rather than a smooth probability surface.</p>
"""
    (DOCS / "executive-summary.html").write_text(
        page("How to make a submission, exactly", sub))

    tbl = "".join(
        f"<tr><td>{r['z0_m']:.0f}</td><td>{r['delta_rho']:.0f}</td><td>{r['kc_scale']:.3f}</td>"
        f"<td>{r['stats']['p50']:.0f}</td><td>{r['stats']['p90']:.0f}</td>"
        f"<td>{r['stats']['fraction_gt_1km']*100:.1f} %</td>"
        f"<td>{r['rms_residual_mgal']:.2f}</td><td>{r['penalty']:.3f}</td></tr>"
        for r in meas.get("calibration", {}).get("table", [])[::4])
    dtbl = "".join(f"<tr><td>{t['iteration']}</td><td>{t['max_change_m']:.0f}</td>"
                   f"<td>{t['max_abs_relief_m']:.0f}</td>"
                   f"<td>{t['rms_residual_mgal']:.2f}</td></tr>" for t in div)
    meth = f"""
<h2>The method, and why each choice was forced</h2>
<h3>1 · Invert the gravity for depth to basement</h3>
<p>Input is band 13, <code>iso_grav_anom</code>, of the pinned
<code>training_features.tif</code>. The operator is Parker (1973) forward / Oldenburg (1974)
iterative, on a 400 m block-mean grid (the field is band-limited to tens of kilometres; 100 m
sampling would add nothing but noise). The gravity band is NaN over 58 % of the rectangle, so the
gap is filled by multi-scale normalised convolution — a constant fill puts a step along the whole
survey boundary and the downward-continuation factor turns that step into tens of kilometres of
fake relief.</p>
<h3>2 · The non-linear correction is rejected, on measurement</h3>
<p>Oldenburg's iteration does not converge on an <i>isostatic residual</i>. The trace is below:
iteration 1 leaves the smallest forward residual; every later correction makes it worse and the
relief grows without bound. An isostatic residual carries crustal- and mantle-scale field, and a
single-interface Parker series can only absorb that field as relief — so it does. The lane
therefore keeps the <b>first iterate</b> (the low-passed Bouguer slab) and reports the rejected
correction rather than hiding it.</p>
<table><tr><th>iteration</th><th>max change (m)</th><th>max |relief| (m)</th><th>forward RMS (mGal)</th></tr>{dtbl}</table>
<h3>3 · Calibrate against the published map, not against the supplied band</h3>
<p>The two free parameters are exactly the pair Oldenburg identifies as non-unique: the density
contrast and the reference level. Both are fitted to USGS <b>GP-1012</b>, whose published scale is
1 : 2,500,000 and whose only transportable quantities are the median depth band and the fraction
of the province deeper than 1 km ("about 20 %", Blakely &amp; Jachens 1991). A subset of the
21-point sweep:</p>
<table><tr><th>z₀ (m)</th><th>Δρ (kg/m³)</th><th>kc scale</th><th>median (m)</th><th>p90 (m)</th>
<th>&gt; 1 km</th><th>forward RMS (mGal)</th><th>penalty</th></tr>{tbl}</table>
<p>Selected: z₀ = {meas.get('chosen',{}).get('z0_m','—')} m, Δρ =
{meas.get('chosen',{}).get('delta_rho','—')} kg/m³, kc scale =
{meas.get('chosen',{}).get('kc_scale','—')}, giving
{fmt(meas.get('chosen',{}).get('stats',{}).get('fraction_gt_1km',0)*100,1)} % deeper than 1 km.
The high apparent contrast is expected for an isostatic residual: the topographic and isostatic
masses are already removed, so the residual sees a larger effective contrast than a raw Bouguer
slab.</p>
<h3>4 · Steps, not lineaments (H61-B sharpness + VG depth-index)</h3>
<p>Maxima of the horizontal gradient magnitude of the depth surface, accepted on the
Blakely &amp; Simpson (1986) "greater than at least two neighbours" rule. Each accepted maximum then
has its <b>throw</b> measured — the depth range across the ridge in a 9 × 9 window (800 m baseline = ±1 inversion cell) — and only the
ones with throw ≥ 80 m and sharpness <code>throw / max(depth, 0.5·z<sub>0</sub>) ≥ 0.08</code> survive,
weighted by the horizontal-to-vertical gravity gradient depth-index <code>|HG| / (|VG| + ε)</code> (bands 18 and 11).
The DrivenData problem statement's own ledger row DD-ABOUT is
explicit that a lineament is not a fault and that a fault is a structure with displacement; this
step is where that is enforced rather than asserted.</p>
<h3>5 · Emission under the metric, not by eye</h3>
<p>Dots are chosen by a greedy allocation whose decision rule is the metric's own marginal test,
<code>dT · D &gt; 0.2 · T · (dT + 1 − k)</code>, with a minimum separation so no truth cell is paid
for twice. The result is binary, because a graded field is strictly dominated by its own thresholded
support.</p>

<h2>Sources</h2>
<ul class="tight">
<li>Parker, R. L. (1973), <i>The rapid calculation of potential anomalies</i>, GJI 31, 447–455.</li>
<li>Oldenburg, D. W. (1974), <i>The inversion and interpretation of gravity anomalies</i>,
    Geophysics 39(4), 526–536, <a href="https://doi.org/10.1190/1.1440444">doi:10.1190/1.1440444</a>.</li>
<li>Blakely, R. J. &amp; Simpson, R. W. (1986), <i>Approximating edges of source bodies from
    magnetic or gravity anomalies</i>, Geophysics 51(7), 1494–1498,
    <a href="https://doi.org/10.1190/1.1442197">doi:10.1190/1.1442197</a>.</li>
<li>Blakely, R. J. &amp; Jachens, R. C. (1991), <i>Regional study of mineral resources in Nevada</i>,
    GSA Bulletin 103, 795–803,
    <a href="https://doi.org/10.1130/0016-7606(1991)103&lt;0795:RSOMRI&gt;2.3.CO;2">doi:10.1130/0016-7606(1991)103&lt;0795:RSOMRI&gt;2.3.CO;2</a>.</li>
<li>Saltus, R. W. &amp; Jachens, R. C. (1995), <i>Gravity and basin-depth maps of the Basin and
    Range Province, western United States</i>, USGS GP-1012,
    <a href="https://doi.org/10.3133/gp1012">doi:10.3133/gp1012</a> (1 : 2,500,000).</li>
<li>Jachens, R. C. &amp; Moring, B. C. (1990), USGS OFR 90-404; and USGS OFR 99-49,
    <a href="https://pubs.usgs.gov/of/1999/0049/pdf/of99-49.pdf">pubs.usgs.gov/of/1999/0049</a>
    — the practice of reducing with 2,670 kg/m³ and stepping basin fill 1,900–2,450 kg/m³.</li>
</ul>
<h2>Gates on this page</h2>
<table>
<tr><th>Gate</th><th>Result</th></tr>
<tr><td>Grid pins (CRS, shape, transform)</td>
<td>{'PASS' if ver.get('all_pins_match') else 'FAIL'} — {ver.get('grid',{}).get('shape','—')},
<code>{ver.get('grid',{}).get('crs','—')}</code>, footprint
{ver.get('grid',{}).get('footprint_px',0):,} px, catalogue {ver.get('grid',{}).get('catalogue_px',0):,} px</td></tr>
<tr><td>On-disk format, range, finiteness, masked catalogue</td>
<td>PASS (the writer refuses to emit a file that fails any of these)</td></tr>
<tr><td>Uniqueness vs the {uniq.get('corpus_rasters_compared','—')} comparable sibling rasters</td>
<td>{uniq.get('verdict','—').upper()} — worst rank correlation
{fmt(uniq.get('worst_spearman_full_footprint'))}, worst dot overlap
{fmt(uniq.get('worst_overlap_gate_value'))}, byte-identical to none</td></tr>
<tr><td>Catalogue-frame holdout (structural fidelity)</td>
<td>{fmt(hold.get('lane_vs_control',{}).get('lane',0),4)} vs control
{fmt(hold.get('lane_vs_control',{}).get('control',0),4)} — <b>the instrument cannot rank this
file</b>; see IR-57-INSTR-01</td></tr>
</table>
"""
    (DOCS / "method.html").write_text(page("Method", meth))

    cards = []
    for h in hyp.get("hypotheses", []):
        cards.append(f"""
<div class="banner {'ok' if h['rank']==1 else 'warn'}">
<strong>#{h['rank']} · {h['id']} · {h['title']}</strong>
<span class="pill">{h['status']}</span></div>
<table>
<tr><th>Supplied layers used</th><td>{'<br>'.join(h['layers'])}</td></tr>
<tr><th>Physical signature</th><td>{h['physical_signature']}</td></tr>
<tr><th>Why it catches a fault the catalogue misses</th><td>{h['why_missing_from_catalogue']}</td></tr>
<tr><th>How it differs from everything already implemented</th><td>{h['differs_from_existing']}</td></tr>
<tr><th>Cost</th><td>{h['cost']}</td></tr>
{f"<tr><th>Blocked on</th><td>{h['blocked_on']}</td></tr>" if h.get('blocked_on') else ''}
<tr><th>Sources</th><td>{'<br>'.join(h.get('sources',[])) or '—'}</td></tr>
</table>""")
    hyp_body = (f"<p>{hyp.get('note','')}</p><p><b>Ranking rule:</b> {hyp.get('ranking_rule','')}</p>"
                + "".join(cards))
    (DOCS / "hypotheses.html").write_text(page("Hypotheses", hyp_body))

    ver_body = (f"<h2>Every number, with the evidence class</h2><table><tr><th>File</th>"
                f"<th>Class</th><th>What it is</th></tr>"
                + "".join(f"<tr><td><code>{n}</code></td><td>{read(n,{}).get('evidence_class','—')}</td>"
                          f"<td>{read(n,{}).get('note','') or '—'}</td></tr>"
                          for n in ("verify_grid.json", "measure.json", "hypotheses.json",
                                    "holdout.json", "final.json", "uniqueness.json"))
                + "</table><h2>Irregularities carried forward</h2><ul class='tight'>"
                  "<li><code>IR-57-INSTR-01</code> — the catalogue-frame holdout ranks placements by "
                  "coverage of a large population and has measured ρ = −0.93 against 15 owner-reported "
                  "live scores. It is used for structural fidelity only.</li>"
                  "<li><code>IR-61-SIGN-01</code> — the first build of the inversion had a stray leading "
                  "minus, giving corr(depth, gravity) = +0.63 where the supplied band gives −0.685. "
                  "Caught by requiring the sign, not by inspecting a picture; fixed and re-run.</li>"
                  "<li><code>IR-61-UNIQ-01</code> — dot-overlap against a dense sibling surface is "
                  "degenerate (2.7 M positive cells covers half the footprint), so the uniqueness gate "
                  "uses Jaccard when the reference is dense and the one-sided fraction only when it is "
                  "sparse.</li></ul>")
    (DOCS / "verify.html").write_text(page("Verification and irregularities", ver_body))
    print(f"site written: {DOCS}/index.html, executive-summary.html, method.html, "
          f"hypotheses.html, verify.html, downloads/{tif_name}")


if __name__ == "__main__":
    main()
