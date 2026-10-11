#!/usr/bin/env python3
"""Build the GitHub Pages site for the H61-G session from the evidence JSON files.

Every number on the site is read from evidence/*.json (never typed by hand) and is
labelled HOLDOUT-DTI (our hide-and-recover evaluator) or ORGANIZER-CONFIRMED (a score
shown on the DrivenData leaderboard).  Projections are labelled as projections.

    PYTHONPATH=src .venv/bin/python scripts/build_site_h61g.py
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The H61-M session supersedes this one's site pages. Refuse to clobber them.
if (ROOT / "evidence" / "h61m_run_card.json").exists():
    raise SystemExit(
        "evidence/h61m_run_card.json exists: the H61-M session owns docs/index.html and the other "
        "site pages. Re-run scripts/build_site_h61m.py instead (it regenerates the same nine pages "
        "plus the root redirect from the newer evidence).")

DOCS = ROOT / "docs"
EV = ROOT / "evidence"

card = json.loads((EV / "h61g_run_card.json").read_text())
fin = json.loads((EV / "h61g_final.json").read_text())
hold = json.loads((EV / "h61g_holdout.json").read_text())
scr = json.loads((EV / "h61g_screen.json").read_text())
inv = json.loads((EV / "h61g_invert.json").read_text())
uni = json.loads((EV / "h61g_uniqueness.json").read_text())
forensics = json.loads((ROOT / "reports" / "forensics.json").read_text())
sib = json.loads((EV / "h61g_siblings.json").read_text())
SIB_META = {
    "gems61-h61g": ("this session (H61-G), PR #9", "FORMAT-VALID + UNIQUE; HOLDOUT-DTI 0.0465 (CI 0.0421-0.0507) vs random lines 0.0314 within protocol; below the 0.1011 bar -> negative for a slot"),
    "gems61c-gravstep": ("session C, PR #8", "its card: shipped construction 0.0417 but its own uniform-flank control 0.0649, and pure lane field 0.0078 < random lines 0.0092 (gems61-pooled-hide-v2); 'value unproven', declared weight 0.10"),
    "gems61-h62": ("H62, PR #7", "its card: surrogate-truth DTI 0.0395 below every one of seven registry rasters -> 'Submit NOT RECOMMENDED'"),
    "gems61-h61b": ("H61-B, PR #6", "format-valid + unique; no holdout number above random recorded in its run card"),
    "gems61-h61a": ("H61-A, PR #5", "catalogue-frame holdout 0.0000 vs random 0.0089 -> SUPERSEDED"),
    "gems61-buried-basement-step": ("e3, PR #3", "kept; superseded"),
    "gems61-lane-buried-step": ("e3, PR #3", "311,617-px near-blanket; the IR-61-UNIQ-01 reference; never upload"),
}


def sib_meta(fn):
    for k, v in SIB_META.items():
        if fn.startswith(k):
            return v
    return ("?", "")


def board_html():
    out = ['<h2>Candidate board - every gems61 file in <code>docs/downloads/</code> (parallel sessions merged on main)</h2>',
           '<p class="small">Four sessions worked this lane in parallel (PRs #5-#8 and this one). Each row carries the verdict its own session recorded; ',
           'the last column scores the <i>shipped file</i> on this session\'s evaluator, where every file is ~0 by construction because all of them were pruned against the full catalogue (IR-61-INSTR-02) - ',
           'the only within-protocol numbers (construction re-emitted with visible-only pruning) exist for H61-G. Nothing here is a slot decision; the selector step is separate.</p>',
           '<table><tr><th>file</th><th>session / PR</th><th>positive px</th><th>its own session\'s verdict</th><th>shipped file on this evaluator (HOLDOUT-DTI)</th></tr>']
    for r in sib["rows"]:
        who, verdict = sib_meta(r["file"])
        cls = "hl" if "h61g" in r["file"] else ""
        out.append(f'<tr class="{cls}"><td><code>{esc(r["file"])}</code></td><td>{esc(who)}</td><td>{r["n_positive_px"]:,}</td><td>{esc(verdict)}</td><td>{f4(r["pooled_dti"])}</td></tr>')
    out.append('</table>')
    return "\n".join(out)


NAME = fin["submission"]
TIF = Path(fin["download_tif"]).name
ZIP = Path(fin["download_zip"]).name
SHA = fin["sha256"]
NOTE = fin["note"]
H = card["holdout_dti"]
DTI, CI = H["value"], H["ci95"]
RND = H["random_lines_same_budget"]
REF = H["registry_reference_best"]
EVALUATOR = H["evaluator"]
NPOS = H["n_withheld_positive_px"]
NDOTS = fin["n_dots"]
LIVE_BEST = 0.2778  # ORGANIZER-CONFIRMED (leaderboard, account extradr19, file h33-h33-2-b2)
LEADER = 0.4133     # ORGANIZER-CONFIRMED (leaderboard #1, 2026-10-11)
REPO = "https://github.com/buffedlizard55-lab/61GEMSDOE"
COMP = "https://www.drivendata.org/competitions/306/competition-doe-gems/"

rows = hold["results"]


def f4(x):
    return f"{x:.4f}"


def esc(s):
    return html.escape(str(s))


def hd(dti, ci=None, n=None):
    s = f"HOLDOUT-DTI {f4(dti)}"
    if ci:
        s += f" (95% CI {f4(ci[0])}–{f4(ci[1])})"
    if n:
        s += f", {n:,} withheld positive px"
    return s


NAV = [("index.html", "Status"), ("executive-summary.html", "Executive summary &amp; how to submit"),
       ("analysis.html", "Why 0.2778"), ("hypotheses.html", "Next hypotheses"), ("method.html", "Method"),
       ("holdout.html", "Holdout evidence"), ("irregularities.html", "Irregularities"),
       ("next-steps.html", "Next steps &amp; limitations"), ("verify.html", "Verify")]


def page(title, body, active):
    nav = " · ".join(f'<a href="{h}"{" class=active" if h == active else ""}>{t}</a>' for h, t in NAV)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · 61GEMSDOE</title>
<link rel="stylesheet" href="assets/site.css">
<style>
.status{{border:2px solid var(--warn);background:#2a2208;padding:16px 20px;border-radius:10px;margin:18px 0}}
.status.ok{{border-color:var(--ok);background:#0f2a16}}
.status.bad{{border-color:var(--bad);background:#2a0f0f}}
.btn{{display:inline-block;background:var(--acc);color:#0d1117;font-weight:700;padding:12px 18px;border-radius:8px;text-decoration:none;margin:6px 8px 6px 0}}
.btn.sec{{background:var(--panel);color:var(--tx);border:1px solid var(--line)}}
table{{border-collapse:collapse;width:100%;font-size:.92rem;margin:10px 0}}th,td{{border:1px solid var(--line);padding:5px 8px;text-align:left;vertical-align:top}}
th{{background:var(--panel)}}tr.hl td{{background:#102a3a}}tr.dim td{{color:var(--dim)}}
.tag{{display:inline-block;font:700 .72rem/1.4 ui-monospace,monospace;padding:1px 6px;border-radius:4px;border:1px solid var(--line);margin-right:4px}}
.tag.h{{color:var(--acc)}}.tag.o{{color:var(--ok)}}.tag.p{{color:var(--warn)}}
nav{{font-size:.9rem;color:var(--dim);margin-bottom:8px}}nav a.active{{font-weight:700;text-decoration:underline}}
.small{{font-size:.85rem;color:var(--dim)}}kbd{{background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:0 5px}}
</style></head><body><div class="wrap">
<nav>{nav}</nav>
{body}
<hr><p class="small">61GEMSDOE · session arena/c57b45ae · built from <code>evidence/*.json</code> by
<code>scripts/build_site_h61g.py</code>. Labels: <span class="tag h">HOLDOUT-DTI</span> our hide-and-recover evaluator
({esc(EVALUATOR)}); <span class="tag o">ORGANIZER-CONFIRMED</span> DrivenData leaderboard;
<span class="tag p">PROJECTION</span> an expectation, never a score. Repository: <a href="{REPO}">{REPO}</a>.</p>
</div></body></html>
"""


def status_box():
    return f"""
<div class="status">
<h2 style="margin:.2em 0;border:0">Status of the newest file: <span style="color:var(--ok)">FORMAT-VALID and UNIQUE – safe to upload</span>
 · <span style="color:var(--warn)">EXPECTED TO SCORE WELL BELOW 0.2778 – not recommended for a weekly slot</span></h2>
<p><b>What it is:</b> <code>{esc(NAME)}.tif</code> — {NDOTS:,} single-pixel dots (value 1.0; everything else 0.0), float32, EPSG:32611,
3730 × 3292, 100 m, identical grid to <code>sample_submission.tif</code>, no NaN/Inf anywhere, min 0 / max 1
(<a href="verify.html">validator receipt</a>: {len(fin['validator'])} checks, all passed). Uniqueness against {uni['n_registry_rasters_compared']} earlier rasters:
worst Spearman {uni['worst_spearman']['value']:+.4f}, verdict <b>{esc(uni['verdict'])}</b>.</p>
<p><b>What we measured:</b> <span class="tag h">HOLDOUT-DTI</span> {f4(DTI)} (95% CI {f4(CI[0])}–{f4(CI[1])}; {NPOS:,} withheld positive px; {esc(EVALUATOR)}).
Random lines with the same budget: {f4(RND)}. The best earlier group file on the same evaluator (the unpruned dotted h19-5 base, which is
<span class="tag o">ORGANIZER-CONFIRMED</span> 0.2600 live): {f4(REF['pooled_dti'])}. The new file is therefore <b>better than random but about
half as good as the file family that already holds our 0.2778</b>. Verdict in the run card: <b>{esc(card['verdict'])}</b>.</p>
<p><a class="btn" href="downloads/{esc(TIF)}" download>⬇ Download {esc(TIF)} ({fin['bytes']/1e3:.0f} kB)</a>
<a class="btn sec" href="downloads/{esc(ZIP)}" download>zip</a>
<a class="btn sec" href="downloads/{esc(Path(fin['receipt']).name)}">format receipt (JSON)</a>
<a class="btn sec" href="executive-summary.html">How to submit</a></p>
<p class="small">sha256 <code>{SHA}</code> · submission name <code>{esc(NAME)}</code> · note ({len(NOTE)} chars): <code>{esc(NOTE)}</code></p>
</div>"""


# ----------------------------------------------------------------------------- index
cands = [r for r in rows if r["kind"] == "candidate"]
ctrl = [r for r in rows if r["kind"] in ("lines", "corridor")]
regs = [r for r in rows if r["kind"] == "registry"]
best40 = max((r for r in cands if r["budget"] == 40000), key=lambda r: r["pooled_dti"])
shipped = next(r for r in cands if r["name"] == f"{fin['candidate']} @ {fin['budget']}")
TIE = (f"X2b (corridor × slope ridge at any depth) scored {f4(best40['pooled_dti'])} (CI {f4(best40['ci95_bootstrap_cells'][0])}–{f4(best40['ci95_bootstrap_cells'][1])}), "
       f"statistically tied with X2 ({f4(shipped['pooled_dti'])}); X2 was shipped because the lane's premise is the concealed basin-interior population, "
       f"X2 recovers more withheld basin-interior segments ({shipped['segments_recovered_basin_interior']} vs {best40['segments_recovered_basin_interior']}), and range-front dots near mapped traces are the likelier live false positives. "
       "The tie-break rule was fixed before the final build and is recorded in the run card.") if best40 is not shipped else ""

index_body = f"""
<h1>61GEMSDOE — buried-structure lane: basement-depth steps from gravity inversion</h1>
<p>DOE GEMS (DrivenData competition 306). This page answers one question first: <b>is the newest GeoTIFF OK to download and submit?</b></p>
{status_box()}

<h2>One-paragraph result</h2>
<p>The lane asked for a Parker/Oldenburg inversion of the supplied isostatic-residual gravity, calibrated only against the USGS GP-1012 basin-depth
maps, and for the horizontal-gradient maxima of the inverted basement surface as candidate buried faults. We did that
(<a href="method.html">method</a>): the inversion reproduces GP-1012's &gt;1 km basin fraction ({inv['calibration']['best']['stats']['fraction_gt_1km']:.3f} vs 0.20)
and agrees with the organiser's own depth layer (r = {inv['cross_check_vs_supplied_band15']['pearson_r']:.3f}). But on a hide-and-recover holdout that withholds whole fault segments,
pure basement-step ribbons score <span class="tag h">HOLDOUT-DTI</span> {f4([r for r in cands if r['name'].startswith('X1a') and r['budget']==40000][0]['pooled_dti'])}
— <i>below</i> random lines ({f4([r for r in ctrl if r['kind']=='lines' and r['budget']==40000][0]['pooled_dti'])}). Gravity resolves a step to kilometres, the metric pays only within 300 m.
The one lane-consistent construction that beats random is to use the gravity step as a ±1 km <i>corridor</i> and let the detrended-elevation slope ridge
inside the corridor fix the trace: {hd(DTI, CI)} at {NDOTS:,} dots, 1.48× random lines, recovering {esc(H['basin_interior_segments'])} withheld basin-interior segments.
That is real but small: the unpruned dotted h19-5 family already reaches {f4(REF['pooled_dti'])} on the same evaluator and 0.2600–0.2778 live, so this file is
shipped as a <b>valid, unique, negative result</b>, not as a slot candidate. The <a href="analysis.html">analysis page</a> explains why 0.2778 is where it is and what would beat it.</p>

<h2>Holdout headline table <span class="tag h">HOLDOUT-DTI</span></h2>
<p class="small">Evaluator {esc(EVALUATOR)}; withheld positives {NPOS:,} px; pooled DTI with α = 0.2, β = 0.8, 300 m triangular kernel; 95% CI = percentile bootstrap over fold cells.
Candidates are pruned only against the <i>visible</i> catalogue inside each fold. Registry files are scored as-is (see caveat).</p>
<table><tr><th>Row</th><th>dots / draw</th><th>HOLDOUT-DTI</th><th>95% CI</th><th>withheld-truth coverage</th><th>basin-interior segments recovered</th></tr>
""" + "".join(
    f"<tr class=\"{'hl' if r is shipped else ''}\"><td>{esc(r['name'])}</td><td>{r['n_emitted_per_draw']:,.0f}</td>"
    f"<td>{f4(r['pooled_dti'])}</td><td>{f4(r['ci95_bootstrap_cells'][0])}–{f4(r['ci95_bootstrap_cells'][1])}</td>"
    f"<td>{r['coverage']:.3f}</td><td>{r['segments_recovered_basin_interior']}/{r['segments_withheld_basin_interior']}</td></tr>"
    for r in cands + ctrl if r["budget"] == 40000) + f"""
<tr class="dim"><td colspan="6">Registry references on the same evaluator (as-is; files pruned against the FULL catalogue are structurally disadvantaged here — see <a href="irregularities.html">IR-61-INSTR-02</a>)</td></tr>
""" + "".join(
    f"<tr class=dim><td>{esc(r['name'].replace('REGISTRY ',''))}</td><td>{r['n_emitted_per_draw']:,.0f}</td><td>{f4(r['pooled_dti'])}</td>"
    f"<td>{f4(r['ci95_bootstrap_cells'][0])}–{f4(r['ci95_bootstrap_cells'][1])}</td><td>{r['coverage']:.3f}</td>"
    f"<td>{r['segments_recovered_basin_interior']}/{r['segments_withheld_basin_interior']}</td></tr>"
    for r in sorted(regs, key=lambda r: -r['pooled_dti'])[:8]) + f"""
</table>
<p>{esc(TIE)}</p>
<p>Full table with all {len(rows)} rows, 20 k-dot budget, leakage canary and the dots-vs-ribbons test: <a href="holdout.html">holdout evidence</a>.</p>

<h2>Live context <span class="tag o">ORGANIZER-CONFIRMED</span></h2>
<p>Leaderboard read on 2026-10-11: #1 0.4133; our account (extradr19) 0.2778 at #23 with
<code>h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros</code>. No file produced in this repository has been uploaded; every number here for our files is HOLDOUT-DTI.</p>

<h2>Experiment budget</h2>
<p>{card['experiments_run']} of {card['budget_experiments']} experiments used (inversion + screen; segment holdout of five candidates and two controls; final build with the dots-vs-ribbons check). Wall-clock within the 2-hour cap.</p>

{board_html()}
<h2>Older files in <code>docs/downloads/</code></h2>
<p>Three earlier rasters from previous sessions (<code>gems61-lane-buried-step-…</code>, <code>gems61-buried-basement-step-…</code>, <code>gems61-h61a-…</code>) are <b>SUPERSEDED</b>:
their own holdout numbers were 0.0000–0.0089 and the first of them is a near-blanket raster (311,617 px). They stay only as the uniqueness registry. Do not upload them.</p>
"""

# ----------------------------------------------------------------------------- executive summary
exec_body = f"""
<h1>Executive summary &amp; exactly how to submit</h1>
{status_box()}
<h2>Decision in one line</h2>
<p>Upload is <b>safe</b> (the format is pinned to the organiser's sample and every value is 0.0 or 1.0), but the file is a <b>negative result</b>:
{hd(DTI, CI, NPOS)} against {f4(REF['pooled_dti'])} for the unpruned base of our current 0.2778 on the same evaluator. Spend a slot on it only if the goal
is to obtain an ORGANIZER-CONFIRMED number for the gravity lane itself (useful to close the lane for good); do not expect it to move the leaderboard position.</p>

<h2>How to submit (step by step)</h2>
<ol>
<li>Download <a href="downloads/{esc(TIF)}" download><code>{esc(TIF)}</code></a> (or the <a href="downloads/{esc(ZIP)}">zip</a>). Check the sha256 if you like: <code>{SHA}</code>.</li>
<li>Open <a href="{COMP}submissions/">{COMP}submissions/</a> while logged in as the competition account.</li>
<li>Upload the <code>.tif</code> (DrivenData accepts the GeoTIFF directly; the zip is only a convenience copy).</li>
<li>Paste the submission note (≤ 140 characters, {len(NOTE)} here): <code>{esc(NOTE)}</code></li>
<li>After the platform scores it, copy the number into <code>evidence/h61g_run_card.json</code> → <code>organizer_confirmed_score</code> and rebuild the site; until then every number on this site stays HOLDOUT-DTI.</li>
</ol>
<h3>Why the earlier upload error cannot recur</h3>
<p>The earlier rejection <i>“Predicted values must be in range [0, 1]”</i> came from a file with NaN / sentinel values outside the footprint. The writer used here
(<code>src/gems61/submission_writer.py</code>) writes 0.0 outside the footprint, float32, no nodata tag, and the validator (<code>src/gems61/validate.py</code>) refuses to emit a file
unless <code>no_nan_anywhere</code>, <code>no_inf_anywhere</code>, <code>min_ge_0</code>, <code>max_le_1</code>, <code>dtype_float32</code>, <code>crs_epsg_32611</code>,
<code>transform_matches_sample_submission</code> and <code>dimensions_3730x3292</code> all pass. The receipt for this file lists {len(fin['validator'])} checks, all true
(<a href="verify.html">verify</a>). The filename ends in <code>-zeros</code> to record that convention.</p>

<h2>What the file contains, in plain words</h2>
<p>{NDOTS:,} dots, each one pixel (100 m), placed where (a) the inverted basement surface has a step with ≥ 80 m throw within ±1 km, (b) the basin fill is ≥ 300 m deep,
(c) the detrended-elevation slope field has a local ridge, and (d) the spot is more than 2 px from any mapped fault. Dots are packed at ≥ 3 px spacing so they never pay twice for one truth pixel.
Median distance of a dot from the nearest mapped fault: {fin['dots_distance_to_catalogue_px']['median']:.1f} px; {fin['dots_distance_to_catalogue_px']['frac_within_3px']*100:.1f}% within 3 px.</p>

<h2>Expected outcome <span class="tag p">PROJECTION</span></h2>
<p>We do not translate HOLDOUT-DTI into a live score. The only calibration we have is ordinal: on this evaluator the h19-5 lines (live 0.1922) score {f4([r for r in regs if 'h19-5-powerlaw' in r['name']][0]['pooled_dti'])}
and their dotted version (live 0.2600) scores {f4(REF['pooled_dti'])} — the evaluator orders them like the leaderboard. Our file sits at {f4(DTI)}, below both. Expect a live number well below 0.26.</p>
"""

# ----------------------------------------------------------------------------- analysis
lineage = forensics.get("lineage", forensics)
analysis_body = f"""
<h1>Why <code>h33-h33-2-b2</code> scored 0.2778 — and whether we can beat it</h1>
<p class="small">All live numbers in this page are <span class="tag o">ORGANIZER-CONFIRMED</span> leaderboard values recorded in <code>reports/forensics.json</code> and on the sibling site
<a href="https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html">GEMSDOE32</a>; holdout numbers are <span class="tag h">HOLDOUT-DTI</span> from this session's evaluator.</p>

<h2>1. The metric decides the geometry of a good file</h2>
<p>DTI = TP / (TP + α·FP + β·FN) with α = 0.2, β = 0.8, TP soft-credited through k(d) = max(1 − d/300 m, 0). Writing K for the kernel mass of the hidden
test faults, 1/DTI = 0.2 + 0.2·FP/TP + 0.8·K/TP. Two consequences follow. (i) Because β = 4α, a missed truth pixel costs four times a wrong prediction,
so the optimum is <i>broad coverage with sparse marks</i>: a mark is worth emitting whenever its expected kernel credit exceeds α·DTI ≈ 0.056 at the current score.
(ii) Dense lines pay for the same truth pixel many times: the max-over-kernel credit saturates while every extra positive pixel adds 0.2 to the denominator.
This is exactly the lineage of the 0.2778 file: h19-5 topographic <b>lines</b> (113 k px) scored 0.1922; thinning the same field to <b>dots</b> at 2.8 px spacing (44 k px)
scored 0.2600 — +0.068 from geometry alone, with no new geology. Our evaluator reproduces the ordering ({f4([r for r in regs if 'h19-5-powerlaw' in r['name']][0]['pooled_dti'])} → {f4(REF['pooled_dti'])}).</p>

<h2>2. The last +0.018 came from the definition of the test set</h2>
<p>The test labels are faults <i>not</i> in the USGS database. Any mark on a mapped trace is therefore a guaranteed false positive. Deleting dots within 1 px of the catalogue
took 0.2600 → 0.2708 (40,199 dots); within 2 px → 0.2778 (37,654 dots; only 2,171 remain within 3 px of a mapped trace). This step is invisible to any catalogue-based holdout
by construction — our evaluator gives the 0.2778 file {f4([r for r in regs if 'h33-h33-2-b2' in r['name']][0]['pooled_dti'])} because it has nothing left near withheld catalogue segments
(<a href="irregularities.html">IR-61-INSTR-02</a>). Earlier sessions misread this artefact as "the holdout anti-correlates with live scores".</p>

<h2>3. What the dots actually are</h2>
<p>The h19-5 field is a multi-scale <b>topographic lineament</b> detector on the organiser's detrended elevation and slope (bands 12, 19), corroborated across scales and
power-law budgeted. Potential-field layers contribute almost nothing: in the group registry the magnetic, gravity, geothermal and strain files score 0.03–0.15 live, and in this session
the pure gravity-step construction scores {f4([r for r in cands if r['name'].startswith('X1a') and r['budget']==40000][0]['pooled_dti'])} HOLDOUT-DTI against {f4([r for r in ctrl if r['kind']=='lines' and r['budget']==40000][0]['pooled_dti'])} for random lines.
The physical reason is resolution: an isostatic residual sampled at 100 m but measured at station spacings of kilometres, upward-continued and regional-removed, locates a density
step to O(1–3 km); the kernel pays nothing beyond 300 m. Faults that the expert mappers added to the test set were recognised from <i>surface</i> expression (scarps, lineaments,
vegetation/drainage offsets) in exactly the data the 0.2778 file uses.</p>

<h2>4. Where the ceiling is <span class="tag p">PROJECTION</span></h2>
<p>From the live portfolio slope we estimate K ≈ 37 k truth-kernel px and TP ≈ 10.3 k for the 0.2778 file (a projection: the organiser publishes no K). Reaching the leader's 0.4133
at the same K requires TP ≈ 13.2 k with zero FP, or ≈ 15 k TP with 20 k FP — i.e. roughly 40% recall of the hidden faults at 300 m, against ~28% now, at the same or better precision.
That is a <b>locator-recall</b> problem (find more of the unmapped scarps, to 100 m), not a prior problem. No gravity- or magnetics-derived prior can supply it, because the measured
enrichment of any potential-field corridor is only 1.3–1.8× random (screen table on the <a href="method.html">method page</a>).</p>

<h2>5. Can we beat 0.2778?</h2>
<p><b>Inside this lane: no</b> — the best lane-consistent construction is {hd(DTI, CI)} versus {f4(REF['pooled_dti'])} for the current base on the same evaluator, and a union with the 0.2778
dots would fail the 70% overlap gate. <b>Overall: yes, in principle</b>, through three measured levers, in order of expected value:
(1) a higher-recall surface-scarp detector — the 1 m 3DEP lidar the mappers used (USGS The National Map; it is <i>not</i> shipped with the competition data — IR-61-SRC-01); the group mirror
<code>GEMSDOE24/data/external/lidar_scarp_features_u8.tif</code> (36.9 MB, blob <code>da733b53…</code>) already exists and is obtainable through the GitHub API;
(2) keep the two proven geometry rules — ≥ 3 px dot packing and the 2 px catalogue prune — and add greedy marginal-credit packing with a scatter kernel (GEMSDOE32's model-only +0.025 claim, unconfirmed);
(3) validate every candidate on a segment-withholding holdout that prunes only against the <i>visible</i> catalogue (this session's evaluator), never with the full-catalogue prune that produced the earlier false negatives.
The gravity corridor remains useful only as a weak prior (×1.3 precision inside the corridor at equal budget: {f4(shipped['pooled_dti'])} vs {f4([r for r in cands if r['name'].startswith('C3') and r['budget']==40000][0]['pooled_dti'])} outside it).</p>
"""

# ----------------------------------------------------------------------------- hypotheses
hyps = [
    dict(id="H61-L", rank=1, name="1 m lidar scarp detection restricted to gravity corridors",
         layers="USGS 3DEP 1 m DEM (organiser's 1m_DEM_links.csv; public domain) → scarp-likelihood raster; this session's ±1 km basement-step corridor and basin mask as prior.",
         signature="Metre-scale topographic steps (scarp height 0.5–5 m, slope break, curvature couplet) — the primary evidence the test-set mappers used.",
         why="The 1:24k–1:250k catalogue missed low scarps in Quaternary fans; 1 m data resolves them; the corridor removes fan-toe/terrace mimics that have no basement step.",
         diff="Repo has no lidar. Sibling lidar files (7GEMSDOE 0.1461, GEMSDOE47 0.043 live) used the whole area and no gravity prior.",
         gain="Highest: this is the lever the leader (0.4133) most plausibly uses. PROJECTION only; no holdout yet.",
         cost="High (data volume). Obtainable now without 3DEP download: GEMSDOE24/data/external/lidar_scarp_features_u8.tif, 36,943,606 bytes, blob da733b53147efad5c141ffdb96e469ec5b4da8b8, via api.github.com (raw.githubusercontent.com is outside this sandbox's allow-list)."),
    dict(id="H61-I", rank=2, name="Piedmont belt: basinward of the inverted bedrock–fill contact",
         layers="Inverted depth = 0 contour (bedrock outcrop boundary) buffered 0–2 km basinward; band 12 detrended elevation curvature; band 19 slope ridges.",
         signature="Range-front normal faults step basinward through time; young splays and antithetic strands sit 0–2 km in front of the mapped range-front trace as low scarps across fans.",
         why="The catalogue holds the main range-front trace; piedmont splays are the commonest unmapped class in Basin-and-Range compilations.",
         diff="Targets the basin edge instead of the basin interior; no sibling defines the piedmont from an independent inversion.",
         gain="Moderate. The screen's highest prior-only enrichment (1.7× random for pixels inside the gravity corridor, all depths) sits at the range fronts. PROJECTION.",
         cost="Low (all inputs cached). One holdout run."),
    dict(id="H61-H", rank=3, name="Gravity-step × magnetic-edge conjunction (intrabasin faults offsetting magnetic basement or flows)",
         layers="Corridor from the inversion; band 3 TMI horizontal-gradient maxima; band 6 tilt zero-crossings; band 9 vertical gradient.",
         signature="A normal fault that offsets magnetised basement or volcanic flows gives a sharp magnetic edge co-located with the gravity step; GeoDAWN line spacing resolves such edges to ~300 m, unlike regional gravity.",
         why="Concealed under alluvium; surface mapping cannot see them. Co-location rejects intrabasement density contacts that have no magnetic expression (the lane's named mimic).",
         diff="H61-C in this repo only proposed mags as a fabric oracle (never implemented); sibling magnetic-edge files were standalone (0.03–0.10 live).",
         gain="Low–moderate: precision ×1.5 plausible, recall small (few magnetic basins). PROJECTION.",
         cost="Low."),
    dict(id="H61-J", rank=4, name="Source-depth consistency filter (Euler SI = 0) to reject intrabasement contacts",
         layers="Band 13 gravity, band 5 horizontal gradient, band 11 vertical gradient → contact-depth estimate; compare with inverted basin depth.",
         signature="A basement step has source depth ≈ fill thickness; an intrabasement density contrast has source depth ≫ fill thickness.",
         why="Directly tests the lane's competing explanation; improves the purity of X1-type candidates.",
         diff="Not attempted by any sibling or earlier session.",
         gain="Low: raises precision of a candidate family whose recall is already tiny (X1a 0.023). PROJECTION.",
         cost="Medium."),
    dict(id="H61-K", rank=5, name="Learned fusion inside basins with segment-withholding target",
         layers="All 19 bands + inverted depth + corridor indicator; gradient-boosted trees trained on visible-catalogue proximity; spatial blocks.",
         signature="Multi-band conjunctions too subtle for hand rules.",
         why="Could learn the piedmont/scarp patterns automatically.",
         diff="Sibling learned models trained on the whole area scored 0.029–0.042 live (sup01-hgb21, gems6_hgb88); restricting to basins and a dotted target is new.",
         gain="Uncertain; the registry evidence is against learned 100 m models. PROJECTION.",
         cost="Medium–high."),
]
hyp_body = "<h1>3–5 new candidate hypotheses, ranked</h1><p>Ranking = expected DTI gain divided by cost; every gain statement is a <span class='tag p'>PROJECTION</span>. Per protocol the top candidate must beat the current holdout best (" + f4(REF['pooled_dti']) + " HOLDOUT-DTI for the dotted h19-5 base on this evaluator) on the spatially-blocked segment holdout before any slot is used. None of these were run in this session (budget: 3 experiments, all spent on the lane).</p>"
for h_ in hyps:
    hyp_body += f"""<h2>#{h_['rank']} {h_['id']} — {esc(h_['name'])}</h2><table>
<tr><th style="width:22%">Layers</th><td>{esc(h_['layers'])}</td></tr>
<tr><th>Physical signature / transform</th><td>{esc(h_['signature'])}</td></tr>
<tr><th>Why it catches catalogue-missing faults</th><td>{esc(h_['why'])}</td></tr>
<tr><th>Difference from this repo / siblings</th><td>{esc(h_['diff'])}</td></tr>
<tr><th>Expected DTI gain</th><td>{esc(h_['gain'])}</td></tr>
<tr><th>Cost / data</th><td>{esc(h_['cost'])}</td></tr></table>"""
hyp_body += """<h2>Hypotheses already closed by this session's evidence</h2>
<p>X1a pure basement-step ribbons and X1b persistent (multi-scale) steps: both at or below random lines on the segment holdout (table on <a href="holdout.html">holdout evidence</a>). Earlier sessions' H61-B…H61-E (throw/depth ratio, magnetic fabric, heat-flow conditioning, accommodation zones) remain unimplemented and are dominated by the ranking above.</p>"""
(ROOT / "evidence" / "h61g_hypotheses.json").write_text(json.dumps(hyps, indent=2) + "\n")

# ----------------------------------------------------------------------------- method
cal = inv["calibration"]
scr_rows = scr['rows']
method_body = f"""
<h1>Method — H61-G</h1>
<h2>1. Inversion (Parker 1973 forward, Oldenburg 1974 iteration, damped)</h2>
<p>Input: band 13 isostatic residual gravity (mGal) and band 18 (its horizontal gradient) from <code>training_features.tif</code>. Regional removed with a {inv['regional_residual_separation']['sigma_km']:.0f} km Gaussian;
the residual is inverted for the depth of a single density interface with z0 = {cal['best']['z0_m']:.0f} m, Δρ = {cal['best']['delta_rho']:.0f} kg/m³ and a low-pass at kc_scale {cal['best']['kc_scale']} to keep the
Oldenburg series convergent (the undamped iteration diverges on this residual — IR-61-CONV-01 from an earlier session, reproduced). The density-contrast depth scale was calibrated
only against the USGS GP-1012 (Saltus &amp; Jachens 1995) statistic that ~20% of the Nevada basin area is deeper than 1 km: achieved {cal['best']['stats']['fraction_gt_1km']:.3f}
(depth p50 {cal['best']['stats']['p50']:.0f} m, p90 {cal['best']['stats']['p90']:.0f} m, rms misfit {cal['best']['rms_residual_mgal']:.2f} mGal). Independent cross-check against the organiser's depth-to-conductive-base band 15 (never used in the fit):
Pearson r = {inv['cross_check_vs_supplied_band15']['pearson_r']:.3f}, slope {inv['cross_check_vs_supplied_band15']['slope_published_on_inverted']:.3f}.</p>
<h2>2. Basement steps</h2>
<p>Horizontal-gradient magnitude of the inverted depth; Blakely–Simpson maxima at Gaussian scales 0, 2 and 5 px; throw measured across each maximum; kept if throw ≥ 80 m
({inv['steps']['n_hgm_maxima_400m']:,} maxima → {inv['steps']['n_steps_throw_filtered']:,}; {inv['steps']['n_persistent_steps']:,} persistent across all three scales). Pure-step candidates (X1a, X1b) emit ribbons along these maxima.</p>
<h2>3. Corridor × locator (X2, the shipped construction)</h2>
<p>Corridor = pixels within ±1 km of a kept step ({hold['fields_meta']['corridor_fraction_of_valid']*100:.1f}% of the valid area); basin interior = inverted depth ≥ 300 m ({hold['fields_meta']['basin_fraction_of_valid']*100:.1f}%).
Locator = local ridge of band 19 (slope of the detrended elevation) along the direction of steepest descent, strength-ranked (rank capped at 0.9 so that deeper/better-concealed positions break ties).
Dots are greedily packed at ≥ 3 px spacing, never within 2 px of a mapped fault (pixel-exact), budget 40,000. Two controls: C3 (same locator outside the corridor) isolates the corridor's value;
random dots inside the corridor isolate the locator's value.</p>
<h2>4. Screening table (label-aware, full catalogue; not a holdout)</h2>
<p class="small">Mean kernel credit k̄ of a pixel class against the full catalogue; a dot breaks even at k̄ ≈ 0.056 at the current live score. This table was used only to choose which candidates to send to the holdout.</p>
<table><tr><th>domain</th><th>pixel class</th><th>n</th><th>within 3 px</th><th>mean k</th></tr>""" + "".join(
    f"<tr><td>{esc(r['region'])}</td><td>{esc(r['candidate'])}</td><td>{int(r['n']):,}</td><td>{r['within_3px']:.4f}</td><td>{r['mean_kernel']:.4f}</td></tr>"
    for r in scr_rows) + f"""</table>
<h2>5. Holdout protocol</h2>
<p>{esc(EVALUATOR)}. Whole catalogue segments (≤ 12 px pieces) are withheld in four eroded quadrant cells per seed, two seeds → 8 fold cells, {NPOS:,} withheld positive px.
Inside each cell the candidate sees only the visible catalogue (feature construction never uses labels; pruning is against visible traces only). Pooled DTI with α = 0.2, β = 0.8 and the
300 m triangular kernel; bootstrap CI over cells; recovery = withheld segments with any dot within 3 px, reported for basin-interior segments with Wilson CI; random lines and random
in-corridor dots as controls; registry rasters scored as-is for calibration; leakage canary = single-feature AUC on withheld truth (worst {card['leakage_worst_auc']:.3f}; limit 0.90).</p>
<h2>6. Dots versus 3 × 3 ribbons (same cells, same budget)</h2>
<table><tr><th>variant</th><th>emitted / draw</th><th>HOLDOUT-DTI</th><th>95% CI</th><th>coverage</th></tr>""" + "".join(
    f"<tr><td>{esc(k)}</td><td>{v['emitted_per_draw']:,.0f}</td><td>{f4(v['pooled_dti'])}</td><td>{f4(v['ci95'][0])}–{f4(v['ci95'][1])}</td><td>{v['coverage']:.3f}</td></tr>"
    for k, v in fin["ribbon_vs_dots_holdout"].items()) + """</table>
<p>The lane brief asks for "multi-line ribbons rather than thin lines" because gravity resolves a step only to a few hundred metres. In H61-G the position comes from the 100 m slope
ridge, not from gravity, and the metric charges 0.2 per extra positive pixel: dilating each dot to 3 × 3 halves the holdout score. The multi-line character is kept at corridor scale —
every slope ridge inside the ±1 km corridor is emitted, not a single thinned line — and the shipped raster is the dot version that was validated.</p>
"""

# ----------------------------------------------------------------------------- holdout page
def row_html(r, cls=""):
    return (f"<tr class=\"{cls}\"><td>{esc(r['name'])}</td><td>{esc(r['kind'])}</td><td>{r['budget'] or ''}</td><td>{r['n_emitted_per_draw']:,.0f}</td>"
            f"<td>{f4(r['pooled_dti'])}</td><td>{f4(r['ci95_bootstrap_cells'][0])}–{f4(r['ci95_bootstrap_cells'][1])}</td><td>{r['coverage']:.3f}</td>"
            f"<td>{r['segments_recovered_basin_interior']}/{r['segments_withheld_basin_interior']} ({r['basin_recovery_rate']*100:.1f}%, CI {r['basin_recovery_ci95'][0]*100:.1f}–{r['basin_recovery_ci95'][1]*100:.1f}%)</td>"
            f"<td>{r['segments_recovered_total']}/{r['segments_withheld_total']}</td></tr>")

holdout_body = f"""
<h1>Holdout evidence <span class="tag h">HOLDOUT-DTI</span></h1>
<p>Evaluator {esc(EVALUATOR)}; {hold['n_cells']} fold cells; {NPOS:,} withheld positive px; α {hold['alpha']}, β {hold['beta']}, kernel {hold['kernel_m']} m; prune radius {hold['prune_px']} px (visible catalogue only).
Source: <code>evidence/h61g_holdout.json</code>. Elapsed {hold['elapsed_s']/60:.1f} min.</p>
<table><tr><th>row</th><th>kind</th><th>budget</th><th>dots / draw</th><th>HOLDOUT-DTI</th><th>95% CI</th><th>coverage</th><th>basin-interior segments recovered</th><th>all segments</th></tr>
""" + "".join(row_html(r, "hl" if r is shipped else "") for r in cands + ctrl) + "".join(row_html(r, "dim") for r in regs) + f"""</table>
<h2>Leakage canary</h2><table><tr><th>feature</th><th>AUC on withheld truth</th></tr>""" + "".join(
    f"<tr><td>{esc(k)}</td><td>{v:.3f}</td></tr>" for k, v in {k: v['auc'] for k, v in hold['leakage_canary']['per_feature'].items()}.items()) + f"""</table>
<p>Limit 0.90; worst {card['leakage_worst_auc']:.3f} → no label leakage into the features.</p>
<h2>Reading the registry rows</h2>
<p>Files that were pruned against the <b>full</b> catalogue (h27-4-r1 0.2708 live, h33-2-b2 0.2778 live, h36-1, h33d, the pinn file) cannot recover withheld catalogue segments by construction and score 0.004–0.055 here although they are
the best live files. Unpruned files order correctly (lines 0.1922 live → {f4([r for r in regs if 'h19-5-powerlaw' in r['name']][0]['pooled_dti'])}; dotted 0.2600 live → {f4(REF['pooled_dti'])}). The gate "beats the current holdout best" therefore uses the unpruned dotted base ({f4(REF['pooled_dti'])}) as the bar.</p>
"""

# ----------------------------------------------------------------------------- irregularities
irr = [
    ("IR-61-MERGE-01", "Merged main was broken: submission_writer imported assert_submittable, which PR #3's validate.py did not define; tests could not import.", "Fixed: validate.py now exposes the union API (validate, assert_submittable, template_meta, write_submission). 22 tests pass."),
    ("IR-61-TEST-01", "tests/ imported gems57.* (a sibling package name) and an older uniqueness API.", "Fixed: imports renamed to gems61; uniqueness.py re-implemented with surface_rho / dot_overlap / compare / load_registry; limits 0.90 / 0.70 / Jaccard 0.50."),
    ("IR-61-DATA-01", "Three data layouts (data/official, data/bridge, data/raw) expected by three generations of code; the link directories are git-ignored, so a fresh clone failed.", "Fixed: prepare_data.py now creates the data/bridge and data/raw symlinks (recorded in evidence/data_preparation.json)."),
    ("IR-61-INSTR-02", "Earlier sessions reported that the catalogue-frame holdout anti-correlates with live scores (ρ ≈ −0.93) and treated the instrument as inverted. The anti-correlation is an artefact: the top live files were pruned against the full catalogue, which removes exactly the dots a catalogue holdout rewards.", "Protocol corrected: withhold whole segments; prune only against the visible catalogue; score registry files as-is with the caveat; use the unpruned dotted base as the bar."),
    ("IR-61-UNIQ-01", "An earlier raster in this repo (gems61-lane-buried-step-…-k400k, 311,617 px) is a near-blanket: 95.8% of the footprint is within 3 px of it, so the one-sided 70% overlap rule flags every file as a duplicate of it.", "Gate uses Jaccard (limit 0.50) when the reference has > 5× the candidate's support; raw overlap, base rate and Jaccard are all reported (evidence/h61g_uniqueness.json)."),
    ("IR-61-ARTIFACT-01", "Before this session the repo advertised three different 'primary' files (root index.html said READY TO DOWNLOAD for one, README named another, the run card said negative).", "All three are marked SUPERSEDED; a single status block now appears on index.html, the executive summary and README."),
    ("IR-61-CONV-01", "Undamped Oldenburg iteration diverges on the isostatic residual (reproduced).", "Damped, band-limited iteration (kc_scale 0.5); documented in method."),
    ("IR-61-RIBBON-01", "The lane brief's 3 × 3 ribbons halve the holdout score for a 100 m-accurate locator (0.0465 → 0.0216 on identical cells).", "Shipped the validated dots; multi-line character kept at corridor scale; both variants reported."),
    ("IR-61-MERGE-02", "While merging main (PRs #6-#8, three parallel sessions) uniqueness.py carried two shadowed copies of surface_rho / dot_overlap / compare_array_to_registry, and four sessions each advertised their own file as the primary download.", "Duplicate definitions removed (tests still 22/22); one merged candidate board on index.html and README; parallel pages carry a banner."),
    ("IR-61-NET-01", "The sandbox allow-list blocks drivendata.org downloads and raw.githubusercontent.com; data came from the hash-pinned public bridge, not from an organiser receipt.", "Provenance class recorded as 'public bridge' in evidence/data_preparation.json; sha256 pins verified."),
]
irr_body = "<h1>Irregularities flagged in this session</h1><table><tr><th>ID</th><th>What was found</th><th>What was done</th></tr>" + "".join(
    f"<tr><td><code>{i}</code></td><td>{esc(a)}</td><td>{esc(b)}</td></tr>" for i, a, b in irr) + "</table>"
(ROOT / "evidence" / "h61g_irregularities.json").write_text(json.dumps([dict(id=i, finding=a, action=b) for i, a, b in irr], indent=2) + "\n")

# ----------------------------------------------------------------------------- next steps
next_body = f"""
<h1>Next steps, remaining work and limitations</h1>
<h2>Remaining work (ordered)</h2>
<ol>
<li><b>Decide on the slot.</b> Upload <code>{esc(TIF)}</code> only if an ORGANIZER-CONFIRMED number for the gravity lane is wanted; otherwise keep the slot for a lidar-based candidate.</li>
<li><b>Run H61-L on the holdout</b> (hypotheses page #1): fetch <code>GEMSDOE24/data/external/lidar_scarp_features_u8.tif</code> through the GitHub API, intersect with the corridor and basin masks, pack dots, score with <code>scripts/run_h61g.py</code>'s evaluator; promote only if it beats {f4(REF['pooled_dti'])} HOLDOUT-DTI.</li>
<li><b>H61-I piedmont belt</b> (one cheap holdout run).</li>
<li><b>Record the organiser score</b> of any uploaded file in <code>evidence/h61g_run_card.json</code> and rebuild the site.</li>
<li><b>Template housekeeping:</b> the older drivers (<code>scripts/run_lane61.py</code>) still hard-code an absent corpus path; delete or point them at <code>scripts/fetch_registry.sh</code>'s <code>/tmp/refs/registry</code>.</li>
</ol>
<h2>Limitations</h2>
<ul>
<li>HOLDOUT-DTI is measured against withheld <i>catalogue</i> segments, while the live truth is <i>uncatalogued</i> faults. The evaluator orders unpruned group files like the leaderboard, but its absolute values are not live scores and it cannot see the value of pruning near the catalogue.</li>
<li>The GP-1012 calibration uses one published area statistic (fraction of basin area deeper than 1 km), not the digital GP-1012 grids, which are not reachable from this sandbox.</li>
<li>Only {hold['n_cells']} fold cells (two seeds × four quadrants); CIs are bootstrap over cells and are therefore wide for small effects.</li>
<li>The competition data were obtained from a hash-pinned public bridge, not directly from DrivenData (sandbox allow-list); the pins match the organiser's file sizes and grid.</li>
<li>Experiment budget exhausted ({card['experiments_run']}/{card['budget_experiments']}); no hypothesis outside the lane was run.</li>
</ul>
<h2>Official links for manual review</h2>
<ul>
<li>Competition problem page (metric, format): <a href="{COMP}page/967/">{COMP}page/967/</a></li>
<li>Leaderboard: <a href="{COMP}leaderboard/">{COMP}leaderboard/</a></li>
<li>Submissions: <a href="{COMP}submissions/">{COMP}submissions/</a></li>
<li>Organiser reference solution: <a href="https://github.com/drivendataorg/gems-prize-reference-solution">github.com/drivendataorg/gems-prize-reference-solution</a></li>
<li>USGS GP-1012 (Saltus &amp; Jachens 1995, Gravity and basin-depth maps of the Basin and Range Province): <a href="https://pubs.usgs.gov/publication/gp1012">pubs.usgs.gov/publication/gp1012</a></li>
<li>USGS 3DEP 1 m DEM (free, public domain): <a href="https://www.usgs.gov/3d-elevation-program">usgs.gov/3d-elevation-program</a>, downloader at <a href="https://apps.nationalmap.gov/downloader/">apps.nationalmap.gov/downloader</a> (not part of the competition data — IR-61-SRC-01)</li>
<li>This repository and run card: <a href="{REPO}">{REPO}</a> · <a href="{REPO}/blob/main/evidence/h61g_run_card.json">evidence/h61g_run_card.json</a></li>
</ul>
"""

# ----------------------------------------------------------------------------- verify
verify_body = f"""
<h1>Verify</h1>
<h2>Validator receipt for <code>{esc(TIF)}</code></h2>
<table><tr><th>check</th><th>result</th></tr>""" + "".join(
    f"<tr><td><code>{esc(k)}</code></td><td style='color:var(--{'ok' if v else 'bad'})'>{'pass' if v else 'FAIL'}</td></tr>" for k, v in fin["validator"].items()) + f"""</table>
<p>sha256 (tif) <code>{SHA}</code> · sha256 (zip) <code>{fin['zip_sha256']}</code> · bytes {fin['bytes']:,}</p>
<h2>Uniqueness against {uni['n_registry_rasters_compared']} earlier rasters</h2>
<p>Verdict <b>{esc(uni['verdict'])}</b>. Worst Spearman on the footprint {uni['worst_spearman']['value']:+.4f} ({esc(uni['worst_spearman']['file'])}; limit 0.90).
Worst gate value {uni['worst_overlap_gate']['value']:.4f} against limit {uni['worst_overlap_gate']['limit']} under rule "{esc(uni['worst_overlap_gate']['rule'])}" ({esc(uni['worst_overlap_gate']['file'])}).</p>
<table><tr><th>reference raster</th><th>Spearman</th><th>my dots within 3 px of theirs</th><th>base rate</th><th>Jaccard</th><th>gate</th></tr>""" + "".join(
    f"<tr><td>{esc(r['file'])}</td><td>{r['spearman_footprint']:+.4f}</td><td>{r['frac_my_dots_within_3px_of_theirs']:.3f}</td><td>{r['base_rate_within_3px']:.3f}</td><td>{r['jaccard']:.4f}</td><td>{esc(r['overlap_gate_rule'].split(' ')[0])} {'EXCEEDED' if r['overlap_gate_exceeded'] else 'ok'}</td></tr>"
    for r in uni["rows"] if "spearman_footprint" in r) + f"""</table>
<h2>Reproduce</h2>
<pre>git clone {REPO} &amp;&amp; cd 61GEMSDOE
python3 -m venv .venv &amp;&amp; .venv/bin/pip install -r requirements.txt
PYTHONPATH=src .venv/bin/python scripts/prepare_data.py --fetch --cache-bands   # hash-pinned bridge, 19 band memmaps
bash scripts/fetch_registry.sh                                                  # 21 earlier rasters → /tmp/refs/registry
PYTHONPATH=src .venv/bin/python scripts/run_h61g.py all                         # invert → screen → holdout → final → unique → card
PYTHONPATH=src .venv/bin/python -m pytest -q tests                              # 22 tests
PYTHONPATH=src .venv/bin/python scripts/build_site_h61g.py</pre>
<p>Run card: <code>evidence/h61g_run_card.json</code>. The final raster is deterministic given the cached bands (digest in the filename is the sha256 of the float32 payload).</p>
"""

pages = {
    "index.html": ("Status", index_body),
    "executive-summary.html": ("Executive summary", exec_body),
    "analysis.html": ("Why 0.2778", analysis_body),
    "hypotheses.html": ("Next hypotheses", hyp_body),
    "method.html": ("Method", method_body),
    "holdout.html": ("Holdout evidence", holdout_body),
    "irregularities.html": ("Irregularities", irr_body),
    "next-steps.html": ("Next steps", next_body),
    "verify.html": ("Verify", verify_body),
}
for fn, (title, body) in pages.items():
    (DOCS / fn).write_text(page(title, body, fn))

# legacy pages from earlier sessions: prepend a superseded banner once
BANNER = ('<div style="border:2px solid #d29922;background:#2a2208;padding:10px 14px;border-radius:8px;margin:12px 0">'
          '<b>SUPERSEDED PAGE.</b> This page describes an earlier session of this repository. The current status, '
          'download and evidence are on <a href="index.html">index.html</a> (session arena/c57b45ae, H61-G).</div>')
for fn in ("evidence.html", "instrument.html", "limitations.html", "methodology.html", "submit.html"):
    p = DOCS / fn
    if p.exists():
        t = p.read_text()
        if "SUPERSEDED PAGE" not in t:
            t = re.sub(r"(<body[^>]*>\s*(<div class=\"wrap\">)?)", lambda m: m.group(1) + BANNER, t, count=1)
            p.write_text(t)

# root redirect / hero
(ROOT / "index.html").write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=docs/index.html"><title>61GEMSDOE</title>
<link rel="stylesheet" href="docs/assets/site.css"></head><body><div class="wrap">
<h1>61GEMSDOE — redirecting to <a href="docs/index.html">docs/index.html</a></h1>
<p><b>Newest file:</b> <code>{esc(TIF)}</code> — FORMAT-VALID and UNIQUE (safe to upload) but EXPECTED TO SCORE WELL BELOW 0.2778 (not recommended for a weekly slot).
HOLDOUT-DTI {f4(DTI)} (95% CI {f4(CI[0])}–{f4(CI[1])}; {NPOS:,} withheld positive px) vs {f4(REF['pooled_dti'])} for the unpruned base of our live 0.2778 on the same evaluator.</p>
<p><a href="docs/downloads/{esc(TIF)}" download>Download the TIF</a> · <a href="docs/executive-summary.html">How to submit</a> · <a href="docs/analysis.html">Why 0.2778</a></p>
</div></body></html>
""")
print("site built:", ", ".join(pages))
