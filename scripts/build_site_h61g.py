#!/usr/bin/env python3
"""Build the GitHub Pages site for the H61-G session from the evidence JSON files.

H61-G measurements and validation statistics are read from evidence/*.json. Dated
external leaderboard observations and cross-run benchmark values are explicitly labeled
with their source/version; account rows are not attributed to artifacts without receipts.
HOLDOUT-DTI, ORGANIZER-CONFIRMED, OWNER-REPORTED and projections are kept distinct.

    PYTHONPATH=src .venv/bin/python scripts/build_site_h61g.py
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EV = ROOT / "evidence"

card = json.loads((EV / "h61g_run_card.json").read_text())
fin = json.loads((EV / "h61g_final.json").read_text())
hold = json.loads((EV / "h61g_holdout.json").read_text())
scr = json.loads((EV / "h61g_screen.json").read_text())
inv = json.loads((EV / "h61g_invert.json").read_text())
uni = json.loads((EV / "h61g_uniqueness.json").read_text())
shared_holdout = json.loads((EV / "e4b_holdout_final.json").read_text())
shared_baseline = shared_holdout["pooled"]["scores"]["uniform_flank"]
SHARED_BASE_DTI = shared_baseline["dti"]
SHARED_BASE_CI = shared_baseline["ci95"]
SHARED_NPOS = shared_baseline["withheld_positive_pixels"]
SHARED_EVALUATOR = shared_holdout["evaluator_version"]
forensics = json.loads((ROOT / "reports" / "forensics_current.json").read_text())
lineage = forensics["set_difference_forensics"]
core_to_solo = lineage["solo_minus_core"]
core_to_top = lineage["top_minus_core"]
sib = json.loads((EV / "h61g_siblings.json").read_text())
SIB_META = {
    "gems61-h61g": ("this session (H61-G), PR #9", "FORMAT-VALID, but DUPLICATE under the literal gate: 98.5925% raw 3-px overlap > 70%; do not submit. HOLDOUT-DTI 0.0465 is version-specific and below its same-evaluator 0.1011 HOLDOUT-DTI reference."),
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
# Leaderboard values are reported only as dated account-level context below; no file hash is linked to 0.2778.
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
<hr><p class="small">61GEMSDOE · H61-G experiment run card dated 2026-10-11; uniqueness/forensics audit refreshed 2026-10-11 · built from <code>evidence/*.json</code> by
<code>scripts/build_site_h61g.py</code>. Labels: <span class="tag h">HOLDOUT-DTI</span> our hide-and-recover evaluator
({esc(EVALUATOR)}); <span class="tag o">ORGANIZER-CONFIRMED</span> DrivenData leaderboard;
<span class="tag p">PROJECTION</span> an expectation, never a score. Repository: <a href="{REPO}">{REPO}</a>.</p>
</div></body></html>
"""


def status_box():
    failing = uni["worst_overlap"]
    pct = 100 * float(failing["value"])
    matched = int(round(NDOTS * float(failing["value"])))
    return f"""
<div class="status bad">
<h2 style="margin:.2em 0;border:0">Submission status: <span style="color:var(--bad)">BLOCKED — DUPLICATE; DO NOT SUBMIT</span>
 · <span style="color:var(--warn)">format-valid is not a uniqueness clearance</span></h2>
<p><b>Artifact:</b> <code>{esc(TIF)}</code>. Its local format receipt passes {len(fin['validator'])} checks
(Float32, EPSG:32611, 3730 × 3292, matching transform, finite values throughout, range [0,1], zeros outside the footprint).
This proves format compatibility only.</p>
<p><b>Literal registry gate:</b> <b>{matched:,}/{NDOTS:,} = {pct:.4f}%</b> of candidate dots fall within 3 px of
<code>{esc(failing['file'])}</code>; the required stop threshold is &gt;70%. The raw fraction is the gate. The reference's high
eligible-area base rate ({100*float(failing['base_rate']):.4f}%) explains why this near-blanket surface captures most dots, but it does not waive the rule.
Jaccard {float(failing['jaccard_diagnostic']):.6f} is diagnostic only. The measured rank correlation remains below 0.90.</p>
<p><b>Scope limitation:</b> the check compared {uni['n_registry_rasters_compared']} accessible prior rasters (21 explicitly listed sibling blobs plus
{uni['scope']['prior_project_downloads']} earlier project downloads). The list is not proven exhaustive and the organizer-side registry was unavailable;
therefore no full-registry uniqueness claim is made.</p>
<p><b>Scientific result, not a score:</b> <span class="tag h">HOLDOUT-DTI</span> {f4(DTI)}
(95% CI {f4(CI[0])}–{f4(CI[1])}; {NPOS:,} withheld positive px; {esc(EVALUATOR)}), versus random lines {f4(RND)} on the same evaluator.
No organizer receipt exists for this artifact. Its verdict is negative for both slot promotion and submission.</p>
<p><b>Download status:</b> the TIFF remains accessible below as an <b>audit/reproduction artifact only</b>, not as a submission candidate.
Do not upload it.</p>
<p><a class="btn sec" href="downloads/{esc(TIF)}" download>Download audit copy — NOT FOR SUBMISSION</a>
<a class="btn sec" href="verify.html">Inspect format and duplicate-gate evidence</a>
<a class="btn sec" href="executive-summary.html">How to submit a future cleared file</a></p>
<p class="small">sha256 <code>{SHA}</code> · name <code>{esc(NAME)}</code> · stored note ({len(NOTE)} chars; do not use for this file): <code>{esc(NOTE)}</code></p>
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
<p>The lane asked for a Parker/Oldenburg inversion of supplied isostatic-residual gravity, with depth scale calibrated only against the USGS GP-1012 basin-depth statistic, then basement-step maxima as candidate buried faults. The inversion reaches {inv['calibration']['best']['stats']['fraction_gt_1km']:.3f} of basin area deeper than 1 km (GP-1012 anchor ≈0.20) and has Pearson r={inv['cross_check_vs_supplied_band15']['pearson_r']:.3f} against supplied band 15, which was not used in fitting. Pure-step ribbons score HOLDOUT-DTI {f4([r for r in cands if r['name'].startswith('X1a') and r['budget']==40000][0]['pooled_dti'])}, below same-budget random lines ({f4([r for r in ctrl if r['kind']=='lines' and r['budget']==40000][0]['pooled_dti'])}). Adding the slope-ridge locator gives {hd(DTI, CI)}. This is an evaluator result, not a competition score. Basin-interior segment recovery (not a score): {esc(H['basin_interior_segments'])}. Crucially, the final dots overlap an earlier near-blanket raster at {100*float(uni['worst_overlap']['value']):.4f}%, above the literal 70% stop threshold; the candidate is a duplicate and must not be submitted. No new submission TIFF is cleared.</p>

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

<h2>Leaderboard context <span class="tag o">ORGANIZER-CONFIRMED ACCOUNT ROWS</span></h2>
<p>Public <a href="{COMP}leaderboard/">leaderboard</a> snapshot read 2026-10-11: global #1 0.4133; DARD showed 0.3195 at #8; account <code>extradr19</code> showed 0.2778 at #23. This confirms account-level leaderboard entries only, not a score for a specific raster. The public <a href="https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html">GEMSDOE32 page</a> labels H33-2-B2 UNSCORED and says no artifact there has an organizer score. No submission-page receipt links H33-2-B2 to the 0.2778 row; the attribution remains unverified. No file produced in this repository has an organizer receipt.</p>

<h2>Experiment budget</h2>
<p>{card['experiments_run']} of {card['budget_experiments']} experiments used (inversion + screen; segment holdout of five candidates and two controls; final build with the dots-vs-ribbons check). Wall-clock within the 2-hour cap.</p>

{board_html()}
<h2>Archived artifacts in <code>docs/downloads/</code></h2>
<p>These are retained for reproducibility and registry comparisons, not promoted submissions. H61-G is specifically blocked by the literal raw-overlap gate above; other historical files carry their own stale or incompatible run cards. Do not treat a file in this directory as cleared unless the current verification page says so.</p>
"""

# ----------------------------------------------------------------------------- executive summary
exec_body = f"""
<h1>Executive summary &amp; exactly how to submit</h1>
{status_box()}
<h2>Decision in one line</h2>
<p><b>Do not submit any current 61GEMSDOE TIFF.</b> The newest H61-G artifact is format-valid but fails the literal duplicate gate ({100*float(uni['worst_overlap']['value']):.4f}% &gt;70% raw 3-px overlap), and the accessible registry inventory is not proven exhaustive. The H61-G holdout result is a negative <span class="tag h">HOLDOUT-DTI</span> finding, not a leaderboard score. The experiment budget is exhausted (3/3); this turn did not run a new geological hypothesis or make a replacement TIFF.</p>

<h2>How to submit a future, cleared TIFF</h2>
<ol>
<li>Only proceed when the home page and <a href="verify.html">verification page</a> explicitly say <b>submission eligible</b>, the literal rank-correlation and raw &gt;70% 3-px overlap gates pass, and registry coverage is documented. A format-valid file alone is not enough.</li>
<li>Download the newly cleared <code>.tif</code> named on that status page, not an older file in <code>docs/downloads/</code>. Verify its published SHA-256 and keep the ≤140-character submission note shown beside it.</li>
<li>Log in to the competition account and open <a href="{COMP}submissions/">the DOE GEMS submissions page</a>.</li>
<li>Upload the single-band GeoTIFF directly. Paste the exact note into the Note field; do not upload the ZIP unless the portal explicitly requires one.</li>
<li>After the portal returns a submission receipt and score, preserve the receipt (including the submitted filename/hash) and only then record a file-specific value as <span class="tag o">ORGANIZER-CONFIRMED</span>. Until then, use HOLDOUT-DTI or OWNER-REPORTED labels as appropriate.</li>
</ol>
<p><b>Current H61-G file:</b> <a href="downloads/{esc(TIF)}">audit-only copy</a>; <b>do not upload it</b>. Its submission name and note are archived for reproducibility, not cleared for use.</p>

<h2>Why the earlier upload error said values must be in [0,1]</h2>
<p>The archived sibling raster <code>gemsdoe29-sgmc-off-catalogue-44k-20261003-c8dcd780e3fd-nan.tif</code> (SHA-256 <code>9b83158bde01cd5d42e38229d70d01e67cecd2514eeb5fa8d1f3ab6851469dad</code>) has TIFF nodata set to NaN. A raw audit found <b>7,111,787 NaN cells</b>, all outside the sample-submission footprint. Its finite cells range from 0 to 1, but the whole raster is not finite and therefore fails a full-raster [0,1] check: NaN is not in that interval. This is the measured mechanism that best explains the historical message. We did not find an organizer receipt with the rejected file's hash, so exact attribution to that upload remains unverified; see <a href="https://github.com/buffedlizard55-lab/61GEMSDOE/blob/main/evidence/prior_range_error_audit.json">the raw-value audit</a>.</p>
<p>The current writer <code>src/gems61/submission_writer.py</code> writes zeros outside the footprint and float32 values. The validator checks finiteness and range across the whole raster (not just inside the footprint), plus CRS, shape, transform and catalogue mask. H61-G passes those <b>format</b> checks; it still fails the separate uniqueness gate.</p>

<h2>What the buried-structure work established</h2>
<p>The isostatic-gravity inversion was calibrated to the USGS GP-1012 statewide depth statistic (fraction deeper than 1 km: {inv['calibration']['best']['stats']['fraction_gt_1km']:.3f} versus the ≈0.20 anchor); band 15 was only an independent cross-check (Pearson r={inv['cross_check_vs_supplied_band15']['pearson_r']:.3f}). Pure basement-step ribbons did not beat random lines on the H61-G holdout. The gravity corridor plus band-19 slope-ridge locator did beat random lines on that same evaluator, but its emitted raster is a duplicate under the literal registry rule and must not be submitted.</p>
<p>Intrabasement density contrasts remain a live competing explanation: the same gravity edge can arise from a lithologic contact without a fault. The H61-G corridor/slope conjunction was intended to discriminate, but no independent density/lithology evidence was used to show that it actually removes those mimics. H61-J (source-depth consistency) remains an untested hypothesis.</p>

<h2>Reported 0.2778</h2>
<p>The official leaderboard showed <code>extradr19</code> at 0.2778/#23 on 2026-10-11; that is an account-level observation. Public project evidence labels H33-2-B2 UNSCORED and supplies no receipt connecting its bytes to that row. Treat the raster attribution as unverified. The <a href="analysis.html">analysis page</a> separates the measured byte-level dot-pruning history from owner-reported score claims and explains what can—and cannot—be inferred.</p>
"""

# ----------------------------------------------------------------------------- analysis
analysis_body = f"""
<h1>The reported 0.2778: what is measured, what is claimed, and what remains unknown</h1>
<p>This page deliberately does <b>not</b> claim that a specific TIFF earned 0.2778. On the official <a href="{COMP}leaderboard/">leaderboard</a> snapshot read 2026-10-11, global #1 showed 0.4133, DARD showed 0.3195 at #8, and account <code>extradr19</code> showed 0.2778 at #23. That is an account-level leaderboard observation. The sibling project's public page labels H33-2-B2 <b>UNSCORED</b>; no organizer receipt or submission-hash mapping has been found. Therefore the requested file-to-score attribution is <b>unverified</b>.</p>

<h2>Evidence ledger</h2>
<table><tr><th>Statement</th><th>Class</th><th>What the evidence supports</th></tr>
<tr><td><code>extradr19</code> showed 0.2778/#23 (snapshot 2026-10-11)</td><td><span class="tag o">ORGANIZER-CONFIRMED account row</span></td><td>A score was displayed for the account. It does not identify the scored file.</td></tr>
<tr><td>H33-2-B2 was said to be 0.2778</td><td>OWNER-REPORTED</td><td>The sibling page/records contain the claimed association, but its public status is UNSCORED and no portal receipt exists.</td></tr>
<tr><td>H33-2-B2 TIFF has {core_to_top['top_n']:,} positive pixels; SHA-256 <code>c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9</code></td><td>MEASURED FILE FACT</td><td>The archived all-finite raster is binary in [0,1] and has zero positive pixels on the visible catalogue traces. This does not prove what file the portal scored.</td></tr>
<tr><td>The 0.2778-labelled candidate is an exact set difference from the owner-reported 0.2600 candidate</td><td>MEASURED BYTE/PIXEL RELATIONSHIP; scores remain OWNER-REPORTED</td><td>The surviving dots are a subset; removed dots were within 3 px of the visible catalogue. This is compatible with a submission rule that rewards avoiding mapped traces, but does not establish the live score's cause.</td></tr>
</table>

<h2>Why catalogue pruning is a plausible mechanism—not proof of the score</h2>
<p>The competition's DTI penalises false positives with α=0.2 and misses with β=0.8; soft true-positive credit falls linearly to zero at 300 m. Thus a broad locator can benefit from sparse placement, while every extra dot has a denominator cost. The measured raster lineage starts with {core_to_top['core_n']:,} dots, removes {core_to_solo['removed_n']:,} dots within 3 px of the visible catalogue to reach {core_to_solo['solo_n']:,}, then removes another {core_to_top['removed_n']:,} such dots to reach {core_to_top['top_n']:,}. The last raster is a strict subset of its predecessor, verified by an exact set difference in <code>reports/forensics_current.json</code> (machine-readable audit linked from <a href="next-steps.html">sources and limitations</a>). Because the competition target is described as unmapped faults, suppressing mapped catalogue traces is a reasonable modeling rule; however, the organizer's private test labels and file-specific score are not available here, so its causal contribution to the displayed 0.2778 is not verified.</p>
<p>There is a second instrument caveat. If validation hides catalogue segments but a candidate was pruned against the <i>full</i> catalogue, the candidate has already removed dots near withheld positives. It can then score artificially low on that particular holdout. The corrected H61-G evaluator withholds whole segments and permits candidate construction/pruning against only the visible traces; this fixes that specific leakage/selection bias, not the missing receipt or hidden-test uncertainty.</p>

<h2>How H61-G relates to that account score</h2>
<p>H61-G inverts supplied isostatic-residual gravity using a Parker/Oldenburg basement model, calibrating the depth scale against the USGS GP-1012 regional statistic; it tests basement-step ribbons and a step-corridor × slope-ridge locator. Its X2 result is {hd(DTI, CI, NPOS)} versus random lines {f4(RND)} under <code>{esc(EVALUATOR)}</code>. It is not directly comparable to an organizer score, nor to numbers from another holdout version. It is also not a submission candidate: the final 40,000-dot raster has {100*float(uni['worst_overlap']['value']):.4f}% raw forward overlap within 3 px of a prior near-blanket raster, exceeding the literal &gt;70% duplicate gate. Its format is valid; its uniqueness is not cleared.</p>

<h2>Can this project beat the 0.2778 account row?</h2>
<p><b>Unknown; no defensible numeric projection is available.</b> The account score is not tied to a verified artifact, and H61-G has neither an organizer receipt nor a cleared unique TIFF. The official leaderboard #1 was 0.4133 in the cited snapshot; that number is context, not a target calibrated against these internal holdouts.</p>
<p>Potential next research paths are ranked on <a href="hypotheses.html">the hypotheses page</a>. The highest-ranked idea (1 m surface-scarp detection from free USGS 3DEP elevation, optionally conditioned on the gravity corridor) is only a conditional idea: target tile coverage, licensing/format, and reachable data must be checked before it can be called viable. The local sibling mirror is not a substitute for official-source availability. Even if data are obtained, H61-L must beat the current shared evaluator baseline on the exact spatially held-out folds before consuming a slot. No experiment slot remains in this run card.</p>
"""

# ----------------------------------------------------------------------------- hypotheses
hyps = [
    dict(id="H61-L", rank=1, name="Metre-scale surface-scarp locator, conditioned on basement-step corridors",
         layers="Potentially USGS 3DEP 1 m DEM (free/public-domain, official source; target-tile coverage not checked), plus supplied detrended elevation bands 12 and 19, inverted basement-depth step corridors and basin mask.",
         signature="Paired curvature break and metre-scale relief edge, with a persistent slope/ridge signature on Quaternary fans; score candidate pixels by local scarp geometry, then pack sparse dots.",
         why="Low scarps and piedmont splays are plausible catalogue omissions, and the 1 m surface may resolve their expression better than the 100 m competition grid. This is a catalogue-gap rationale, not proof of coverage or detection ability.",
         diff="Not implemented in this repo. Existing sibling lidar-derived rasters are owner-published mirrors and do not establish that official 3DEP tiles cover this competition footprint; do not copy or treat them as verified source data.",
         gain=f"Rank 1 on qualitative potential per cost only; no HOLDOUT-DTI gain measured and no live-score projection. It must exceed the same-version shared baseline ({SHARED_EVALUATOR} uniform_flank: {SHARED_BASE_DTI:.6f}, 95% CI {SHARED_BASE_CI[0]:.6f}–{SHARED_BASE_CI[1]:.6f}, {SHARED_NPOS:,} withheld positives) on identical folds before any slot is considered.",
         cost="High. Official USGS/Data.gov metadata confirms the 1 m collection is public-domain, but exact target-tile coverage, tile-specific CRS/metadata and downloadable-file reachability were not verified; the sandbox network allowlist prevented a direct footprint/tile check. Data viability is UNVERIFIED. Then build leakage-safe features and run the shared evaluator."),
    dict(id="H61-I", rank=2, name="Piedmont relay belt: basinward splays beyond the mapped range front",
         layers="H61-G inverted depth 0-contour and ≥300 m fill mask; band 12 detrended elevation/curvature and band 19 slope-ridge orientation; visible catalogue traces only for per-fold pruning.",
         signature="A narrow, depth-conditioned belt 0–2 km basinward of a range-front step, with aligned but discontinuous short slope ridges marking young relay or antithetic splays.",
         why="Main range-front faults are mapped more often than low-relief basinward splays; the target signature is a spatially distinct class rather than another copy of the main trace.",
         diff="No current repo candidate defines this offset belt from the inverted contact; H61-G's X2 uses an in-corridor slope ridge broadly, not a basinward relay geometry.",
         gain=f"Rank 2, medium qualitative potential; no score estimate. Compare against the exact {SHARED_BASE_DTI:.6f} shared-evaluator baseline with identical spatial folds and budget.",
         cost="Medium. Existing layers are cached, but mask/feature construction must be repeated from visible faults per holdout fold; one pre-registered test only after an authorized run card."),
    dict(id="H61-H", rank=3, name="Gravity step × magnetic edge, restricted to basin-interior contacts",
         layers="H61-G inverted gravity-step corridor; supplied total magnetic intensity band 3, tilt band 6 and vertical-gradient band 9; basin-depth mask.",
         signature="A candidate fault that offsets magnetic basement or a magnetic flow may align a magnetic gradient/tilt edge with the gravity step; a nonmagnetic lithologic density contact may not.",
         why="Tests whether independent magnetic texture supports a fault interpretation where gravity alone has a named intrabasement-density-contact mimic. A missing magnetic edge does not rule out a nonmagnetic fault or contrast, so the test is asymmetric.",
         diff="Earlier H61-C only proposed magnetic fabric as an oracle; H61-G did not use the magnetic stack. This would be a conjunction rather than a standalone magnetic detector.",
         gain=f"Rank 3, low-to-medium qualitative potential; intrabasement contrasts are not resolved by the current evidence, and no score projection is justified. Must beat the same-version {SHARED_BASE_DTI:.6f} baseline on identical folds.",
         cost="Medium. Bands are cached; feature leakage and alignment must be checked per fold. Do not claim it removes density mimics without independent lithology/density evidence."),
    dict(id="H61-J", rank=4, name="Gravity source-depth consistency filter for basement versus intrabasement contacts",
         layers="Isostatic gravity band 13, horizontal/vertical derivatives bands 5 and 11, H61-G inverted fill-depth surface; only derive catalogue-conditioned features from visible faults.",
         signature="Estimate contact/source depth from gravity derivatives; retain step maxima whose source depth is compatible with local basin-fill thickness, and flag deeper sources as possible intrabasement contrasts.",
         why="Directly interrogates the lane's named competing mechanism rather than assuming every basement-depth step is a fault.",
         diff="Not implemented in this repo or measured in the H61-G experiment; it is a new falsification test of X1-type structures, not another slope-ridge locator.",
         gain=f"Rank 4, uncertain/low until source-depth calibration is validated; no score projection. Any retained candidate must beat the same-version {SHARED_BASE_DTI:.6f} baseline on identical folds.",
         cost="High scientific validation cost. Euler/depth estimates from regional, upward-continued gravity may be non-identifiable; test against GP-1012 and synthetic contacts before holdout use."),
    dict(id="H61-K", rank=5, name="Leakage-safe multi-band ranking of basin-interior scarp candidates",
         layers="Supplied 19-band stack plus H61-G depth/corridor rasters; train only on visible-catalogue distance labels within each spatial training fold; independent whole fault segments for validation.",
         signature="Nonlinear conjunction of topographic, magnetic and gravity texture around sparse ridge candidates, with calibrated probability and fixed-budget greedy placement.",
         why="May combine weak surface signatures for unmapped faults, but can also learn the visible catalogue rather than fault geology; therefore must use strict whole-segment holdout and feature leakage canary.",
         diff="No learned model is used in H61-G; this differs from hand-coded geometric rules. Earlier sibling models are not copied and do not establish this model's efficacy.",
         gain=f"Rank 5, highly uncertain; no score projection. Require a pre-registered improvement over the exact {SHARED_BASE_DTI:.6f} same-version baseline, with paired CI and canary AUC <0.90.",
         cost="High. Spatial nested validation, calibration and ablations required; three-experiment cap means this waits for an authorized new run card."),
]
hyp_body = f'''<h1>Ranked, distinct candidate hypotheses</h1><p>Ranks are qualitative expected information/utility per implementation cost—not measured gains or leaderboard projections. All five are unrun. The current shared evaluator benchmark in <code>evidence/e4b_holdout_final.json</code> is uniform_flank = {SHARED_BASE_DTI:.6f} HOLDOUT-DTI (95% CI {SHARED_BASE_CI[0]:.6f}–{SHARED_BASE_CI[1]:.6f}; {SHARED_NPOS:,} withheld positives; <code>{SHARED_EVALUATOR}</code>). A proposed top candidate must beat that benchmark on the same folds, scoring code and budget before any slot is considered. H61-G's 0.0465 uses a different evaluator version and is not directly comparable. The standing H61-G run card is 3/3 experiments used; no experiment or slot is authorized here. H61-L's official source is free USGS 3DEP, but target-footprint tile availability has not been verified, so it is conditional—not yet a viable data-dependent candidate.</p>'''
for h_ in hyps:
    hyp_body += f"""<h2>#{h_['rank']} {h_['id']} — {esc(h_['name'])}</h2><table>
<tr><th style="width:22%">Layers</th><td>{esc(h_['layers'])}</td></tr>
<tr><th>Physical signature / transform</th><td>{esc(h_['signature'])}</td></tr>
<tr><th>Why it catches catalogue-missing faults</th><td>{esc(h_['why'])}</td></tr>
<tr><th>Difference from this repo / siblings</th><td>{esc(h_['diff'])}</td></tr>
<tr><th>Expected DTI gain</th><td>{esc(h_['gain'])}</td></tr>
<tr><th>Cost / data</th><td>{esc(h_['cost'])}</td></tr></table>"""
hyp_body += """<h2>What is actually ruled out</h2>
<p>Only the tested H61-G variants are evaluated: pure basement-step ribbons did not beat random lines under that run's evaluator, while the corridor × slope-ridge locator did. These results do not falsify other buried-fault hypotheses. Earlier H61-B…H61-E ideas remain unimplemented; this ranking does not claim they are dominated. Intrabasement density contrasts remain unresolved and are an explicit interpretation risk.</p>"""
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
only against the official USGS <a href="https://doi.org/10.3133/gp1012">GP-1012</a> (Saltus &amp; Jachens 1995) regional statistic that ~20% of the Nevada basin area is deeper than 1 km: achieved {cal['best']['stats']['fraction_gt_1km']:.3f}
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
<h2>Interpretation limit: intrabasement density contrasts remain unresolved</h2>
<p>A sharp edge in isostatic-residual gravity can arise from a basement relief step, but also from a lateral density contrast within basement. The GP-1012 statistic calibrates the depth scale; it does not identify the cause of an individual edge. The corridor × slope-ridge conjunction is a proposed locator, not proof that the gravity step is a fault or that the surface ridge is its scarp. No independent density/lithology model was used to reject this mimic. H61-H and H61-J on the <a href="hypotheses.html">hypotheses page</a> are untested falsification ideas, not resolved findings.</p>
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
<p><span class="tag h">HOLDOUT-DTI</span> evaluator {esc(EVALUATOR)}; {hold['n_cells']} fold cells; {NPOS:,} withheld positive px; α {hold['alpha']}, β {hold['beta']}, kernel {hold['kernel_m']} m; prune radius {hold['prune_px']} px (visible catalogue only).
Source: <code>evidence/h61g_holdout.json</code>. Elapsed {hold['elapsed_s']/60:.1f} min. These values are not competition scores and are not numerically interchangeable with <code>gems61-pooled-hide-v2</code> in <code>evidence/e4b_holdout_final.json</code>.</p>
<table><tr><th>row</th><th>kind</th><th>budget</th><th>dots / draw</th><th>HOLDOUT-DTI</th><th>95% CI</th><th>coverage</th><th>basin-interior segments recovered</th><th>all segments</th></tr>
""" + "".join(row_html(r, "hl" if r is shipped else "") for r in cands + ctrl) + "".join(row_html(r, "dim") for r in regs) + f"""</table>
<h2>Leakage canary</h2><table><tr><th>feature</th><th>AUC on withheld truth</th></tr>""" + "".join(
    f"<tr><td>{esc(k)}</td><td>{v:.3f}</td></tr>" for k, v in {k: v['auc'] for k, v in hold['leakage_canary']['per_feature'].items()}.items()) + f"""</table>
<p>Limit 0.90; worst {card['leakage_worst_auc']:.3f} → no label leakage into the features.</p>
<h2>Reading the registry rows</h2>
<p>Any raster pruned against the <b>full</b> catalogue loses dots near segments later hidden by this evaluator; its low score here is a known construction bias, not a measurement of its organizer score. Rows are useful only as instrument diagnostics. Within this H61-G evaluator, the unpruned dotted h19-5 registry reference is {f4(REF['pooled_dti'])} HOLDOUT-DTI and served as a local comparator. Separately, the current shared <code>{SHARED_EVALUATOR}</code> benchmark is uniform_flank = {SHARED_BASE_DTI:.6f} (95% CI {SHARED_BASE_CI[0]:.6f}–{SHARED_BASE_CI[1]:.6f}; {SHARED_NPOS:,} withheld positives), recorded in <code>evidence/e4b_holdout_final.json</code>. Because the evaluator versions and folds differ, do not compare these values or treat either as a leaderboard score.</p>
"""

# ----------------------------------------------------------------------------- irregularities
irr = [
    ("IR-61-MERGE-01", "A prior merge left submission_writer importing an API absent from validate.py; several tests could not import.", "The shared validate/writer API was reconciled; current project tests are run below and reported in the session summary."),
    ("IR-61-TEST-01", "Legacy tests referenced sibling package names and a previous uniqueness API.", "Tests and shared uniqueness helpers now use the gems61 package; regression cases cover exact 70% versus 71% raw overlap, the independent rho stop rule, and incomplete-registry clearance."),
    ("IR-61-DATA-01", "Multiple historical data layouts (data/official, data/bridge, data/raw) are used by different scripts; ignored link directories can make a fresh clone fail.", "prepare_data.py documents and recreates the data links; data source/hash provenance remains in evidence/data_preparation.json."),
    ("IR-61-INSTR-02", "A full-catalogue-pruned raster loses dots near segments subsequently hidden by a catalogue holdout, making its holdout result artificially low.", "H61-G hides whole segments and derives/prunes catalogue features only from visible faults. Registry rasters are shown with a construction-bias caveat."),
    ("IR-61-UNIQ-01", "A prior near-blanket raster has a 95.8182% eligible-area base rate. H61-G's 40,000 dots have 98.5925% raw one-sided 3-px overlap (39,437 dots) with it, far above the literal >70% stop rule, despite Jaccard 0.007481 and rho +0.001844.", "The raw overlap is the gate; Jaccard/base rate are diagnostic only. H61-G is logged DUPLICATE — DO NOT SUBMIT. The updated pipeline now gates before writer and after re-reading a newly written TIFF; this historical raster was instead checked by the separate `unique` audit stage."),
    ("IR-61-SCOPE-01", "The fetched list contains 21 explicitly named sibling rasters; accessible local downloads add 6. Neither proves completeness of all earlier files or the organizer-side registry.", "uniqueness reports full_registry_coverage=false and fails closed; no global uniqueness claim is made."),
    ("IR-61-REGISTRY-01", "docs/data/registry.json is a historical snapshot generated by an earlier builder from reports/*.json, not evidence of H61-G's complete submission registry.", "Provenance is recorded in evidence/registry_snapshot_provenance.json; current audit uses the fetched finite list plus accessible project downloads."),
    ("IR-61-SCORE-01", "The 2026-10-11 public leaderboard showed account extradr19 at 0.2778/#23, but no portal receipt or artifact hash maps that row to H33-2-B2.", "Keep the account row ORGANIZER-CONFIRMED; treat the file association as OWNER-REPORTED/unverified. Public sibling page labels H33-2-B2 UNSCORED."),
    ("IR-61-FORMAT-01", "An archived prior TIFF has 7,111,787 NaNs, all outside the official sample footprint; finite cells are [0,1], but a whole-raster range/finiteness check fails.", "Raw audit saved at evidence/prior_range_error_audit.json. This plausibly explains the earlier [0,1] message, but no receipt/hash confirms that exact file was historically rejected. New validator checks the full raster."),
    ("IR-61-MIMIC-01", "Intrabasement lithologic density contrasts can produce gravity edges that resemble basement relief; no independent density/lithology evidence was used to discriminate them.", "Explicitly unresolved in method and run card; H61-H/H61-J remain hypotheses, not conclusions."),
    ("IR-61-ARTIFACT-01", "Historical README/site text called H61-G unique and safe to upload before the literal raw-overlap check was recomputed.", "Current site and run card mark it FORMAT-VALID but DUPLICATE / audit-only / do not submit; the TIFF is not cleared."),
    ("IR-61-CONV-01", "Undamped Oldenburg iteration diverges on the isostatic residual.", "Damped, band-limited inversion is documented; value remains model-dependent."),
    ("IR-61-RIBBON-01", "3×3 raster ribbons scored 0.0216 versus 0.0465 for dots under the same H61-G fold cells; metric penalizes extra positive pixels.", "Dots are retained for this internal candidate; the H61-G artifact is nevertheless blocked by uniqueness."),
    ("IR-61-3DEP-01", "USGS 3DEP 1 m DEM is an official free/public-domain source, but exact target-footprint tile availability was not checked.", "H61-L is conditional only; no availability or performance claim until official tile IDs, dates, CRS and hashes are checked."),
    ("IR-61-NET-01", "Direct DrivenData/USGS endpoints are not reachable from this sandbox; competition raster inputs came from a hash-pinned public bridge.", "Source class is documented in evidence/data_preparation.json; bridge bytes are not an organizer receipt."),
    ("IR-61-BUDGET-01", "H61-G run card records 3/3 experiments used; the research budget is exhausted.", "No experiment, candidate rebuild, slot use, or organizer score claim was made; further science requires a new authorized run card/scope."),
]
irr_body = "<h1>Irregularities flagged in this session</h1><table><tr><th>ID</th><th>What was found</th><th>What was done</th></tr>" + "".join(
    f"<tr><td><code>{i}</code></td><td>{esc(a)}</td><td>{esc(b)}</td></tr>" for i, a, b in irr) + "</table>"
(ROOT / "evidence" / "h61g_irregularities.json").write_text(json.dumps([dict(id=i, finding=a, action=b) for i, a, b in irr], indent=2) + "\n")

# ----------------------------------------------------------------------------- next steps
next_body = f"""
<h1>Next steps, remaining work and limitations</h1>
<div class="status bad"><b>No current TIFF is cleared for competition submission.</b> H61-G is format-valid but fails the literal duplicate gate; the accessible registry list is incomplete. No experiment or upload is authorized by this page.</div>
<h2>Remaining work (ordered; do not spend the exhausted slot)</h2>
<ol>
<li><b>Obtain complete uniqueness coverage.</b> The current public enumeration names 21 sibling rasters and the local scan adds 6 prior project downloads. This does not prove coverage of every previous artifact or the organizer registry. Expand/verify the registry from an authoritative inventory before any candidate can be called globally unique; keep the raw &gt;70% forward-overlap rule and rho &gt;0.90 rule literal.</li>
<li><b>Resolve the reported 0.2778 attribution.</b> Obtain a submission-page receipt containing the exact filename/hash and score. Until then, retain the account-level 0.2778 as observed and the H33-2-B2 file attribution as unverified.</li>
<li><b>Check official 3DEP tile coverage before H61-L is viable.</b> The USGS 3DEP 1 m collection is free/public-domain, but region-level catalog metadata does not prove target-footprint 1 m tiles exist. Query the official National Map/3DEP footprint for the exact raster extent; record tile IDs, dates, CRS, and hashes before building features. This check was not made in this run.</li>
<li><b>Only under a new authorized run card:</b> use the shared holdout/evaluator and compare H61-L (or another preregistered idea) against <code>{SHARED_EVALUATOR}</code> uniform_flank = {SHARED_BASE_DTI:.6f} HOLDOUT-DTI (95% CI {SHARED_BASE_CI[0]:.6f}–{SHARED_BASE_CI[1]:.6f}; {SHARED_NPOS:,} withheld positives) on identical folds, score and budget. Do not compare H61-G's 0.0465 across evaluator versions. The standing run card reports 3/3 experiments used.</li>
<li><b>Resolve gravity interpretation.</b> Test H61-H magnetic co-location and H61-J source-depth consistency only as falsification hypotheses. Current data do not rule out intrabasement density contrasts as the source of an apparent basement step.</li>
<li><b>Template housekeeping:</b> inspect older drivers such as <code>scripts/run_lane61.py</code> for stale corpus assumptions before reusing them; do not launch the full H61-G experiment pipeline without new authorization.</li>
</ol>
<h2>Limitations</h2>
<ul>
<li>H61-G's <span class="tag h">HOLDOUT-DTI</span> uses <code>{esc(EVALUATOR)}</code> and withholds mapped catalogue segments. It is an internal index, not the competition's hidden uncatalogued-fault score.</li>
<li>The shared <code>gems61-pooled-hide-v2</code> benchmark is a different instrument/fold set. Its {SHARED_BASE_DTI:.6f} value is an internal same-version comparator, not a live projection or score.</li>
<li>GP-1012 calibration matches a regional depth statistic (fraction deeper than 1 km), not independent pixelwise truth; its broad 1:2.5M scale cannot identify the cause of individual gravity edges.</li>
<li>Intrabasement lithologic density contrasts were not modeled or independently checked; a gravity step is not by itself evidence of a fault.</li>
<li>H33-2-B2's 0.2778 association is owner-reported and not tied to an organizer receipt. The official leaderboard observation is account-level only.</li>
<li>The current registry audit sees 27 accessible rasters, not the full organizer-side registry. H61-G fails even this partial gate, so the lack of full coverage cannot rescue it.</li>
<li>1 m USGS 3DEP product access and licensing are documented as public/free, but exact project tile availability for this footprint was not checked. It remains conditional.</li>
<li>Competition rasters were obtained from a hash-pinned public mirror because direct competition hosts are blocked in the sandbox; this is not organizer provenance.</li>
</ul>
<h2>Official sources for manual review</h2>
<ul>
<li>Competition problem page (metric, format): <a href="{COMP}page/967/">{COMP}page/967/</a></li>
<li>Official leaderboard: <a href="{COMP}leaderboard/">{COMP}leaderboard/</a></li>
<li>Submission portal/receipts: <a href="{COMP}submissions/">{COMP}submissions/</a></li>
<li>USGS GP-1012 catalog record/DOI (Saltus &amp; Jachens 1995): <a href="https://doi.org/10.3133/gp1012">https://doi.org/10.3133/gp1012</a></li>
<li>USGS 3DEP official program and elevation data: <a href="https://www.usgs.gov/3d-elevation-program">usgs.gov/3d-elevation-program</a>; 1 m DEM collection metadata: <a href="https://catalog.data.gov/dataset/1-meter-digital-elevation-models-dems-usgs-national-map-3dep-downloadable-data-collection">Data.gov / USGS 1 m DEM</a>. The collection is public-domain; exact local tile availability is still unverified.</li>
<li>Organiser reference solution: <a href="https://github.com/drivendataorg/gems-prize-reference-solution">github.com/drivendataorg/gems-prize-reference-solution</a></li>
<li>Repository evidence: <a href="{REPO}/blob/main/evidence/h61g_run_card.json">H61-G run card</a> · <a href="{REPO}/blob/main/evidence/h61g_uniqueness.json">uniqueness audit</a> · <a href="{REPO}/blob/main/evidence/prior_range_error_audit.json">prior range-error audit</a> · <a href="{REPO}/blob/main/evidence/registry_snapshot_provenance.json">registry snapshot provenance</a> · <a href="{REPO}/blob/main/evidence/source_review_20261011.json">official-source review</a> · <a href="{REPO}/blob/main/reports/forensics_current.json">current forensics</a></li>
</ul>
"""

# ----------------------------------------------------------------------------- verify
verify_body = f"""
<h1>Format verification ≠ submission clearance</h1>
<h2>Validator receipt for archived audit artifact <code>{esc(TIF)}</code></h2>
<p>All {len(fin['validator'])} checks below pass, so the TIFF is well-formed and its values are finite and in [0,1]. This does not establish registry uniqueness or submission eligibility.</p>
<table><tr><th>check</th><th>result</th></tr>""" + "".join(
    f"<tr><td><code>{esc(k)}</code></td><td style='color:var(--{'ok' if v else 'bad'})'>{'pass' if v else 'FAIL'}</td></tr>" for k, v in fin["validator"].items()) + f"""</table>
<p>sha256 (tif) <code>{SHA}</code> · sha256 (zip) <code>{fin['zip_sha256']}</code> · bytes {fin['bytes']:,}</p>
<h2>Literal uniqueness gate: <span style="color:var(--bad)">DUPLICATE — DO NOT SUBMIT</span></h2>
<p>The candidate contains {int(uni['candidate_dots']):,} dots. Its worst raw one-sided 3-px overlap is <b>{100*float(uni['worst_overlap_gate']['value']):.4f}%</b>
({int(round(int(uni['candidate_dots'])*float(uni['worst_overlap_gate']['value']))):,} dots) against <code>{esc(uni['worst_overlap_gate']['file'])}</code>;
the literal duplicate rule stops at &gt;70%. The corresponding eligible-area base rate is {100*float(uni['worst_overlap']['base_rate']):.4f}% and Jaccard is {float(uni['worst_overlap']['jaccard_diagnostic']):.6f}; these are diagnostics only and cannot replace or waive the raw-overlap test. Worst rank correlation is {uni['worst_spearman']['value']:+.4f} (threshold &gt;0.90).</p>
<p>Scope: {uni['n_registry_rasters_compared']} accessible rasters = 21 enumerated public sibling rasters + {uni['scope']['prior_project_downloads']} prior project downloads. <code>full_registry_coverage=false</code>; the enumerated list is explicitly finite and the organizer-side registry is unavailable. Accordingly this report does not claim full-registry uniqueness. Status: <b>audit-only; do not submit</b>.</p>
<table><tr><th>reference raster</th><th>Spearman</th><th>candidate dots within 3 px</th><th>base rate</th><th>Jaccard (diagnostic)</th><th>literal overlap gate</th></tr>""" + "".join(
    f"<tr><td>{esc(r['file'])}</td><td>{r['spearman_footprint']:+.4f}</td><td>{100*r['frac_my_dots_within_3px_of_theirs']:.4f}%</td><td>{100*r['base_rate_within_3px']:.3f}%</td><td>{r['jaccard']:.6f}</td><td>{'EXCEEDED' if r['overlap_gate_exceeded'] else 'not exceeded'}</td></tr>"
    for r in uni["rows"] if "spearman_footprint" in r) + f"""</table>
<p><a href="downloads/{esc(TIF)}">Download audit-only TIFF (DO NOT SUBMIT)</a> · full machine-readable report: <a href="https://github.com/buffedlizard55-lab/61GEMSDOE/blob/main/evidence/h61g_uniqueness.json"><code>evidence/h61g_uniqueness.json</code></a>.</p>
<h2>Reproduce the audit (no new experiment)</h2>
<pre>git clone {REPO} &amp;&amp; cd 61GEMSDOE
python3 -m venv .venv &amp;&amp; .venv/bin/pip install -r requirements.txt
PYTHONPATH=src .venv/bin/python scripts/prepare_data.py --fetch --cache-bands   # hash-pinned bridge, 19 band memmaps
bash scripts/fetch_registry.sh                                                  # finite 21-raster list -> /tmp/refs/registry
PYTHONPATH=src .venv/bin/python scripts/run_h61g.py unique                     # expected: DUPLICATE; audit only, no experiment
PYTHONPATH=src .venv/bin/python -m pytest -q tests
PYTHONPATH=src .venv/bin/python scripts/build_site_h61g.py</pre>
<p>The 3-experiment budget is exhausted. Do not run <code>scripts/run_h61g.py all</code> or create a new candidate unless a new authorized run card/scope is provided and the registry scope is adequate. The updated pipeline gates both before the submission writer and on the reread TIFF before copying to public downloads.</p>
<p>Run card: <code>evidence/h61g_run_card.json</code>. Artifact hash, validation receipt, and duplicate-gate report are separate evidence objects.</p>
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
<p><b>Newest artifact status: BLOCKED — DUPLICATE; DO NOT SUBMIT.</b> It is FORMAT-VALID, but {100*float(uni['worst_overlap']['value']):.4f}% of its dots overlap within 3 px of a prior raster, exceeding the literal &gt;70% stop rule. The accessible registry is incomplete, so no global uniqueness claim is made. HOLDOUT-DTI {f4(DTI)} is an internal result, not a competition score.</p>
<p><a href="docs/downloads/{esc(TIF)}">Download audit copy — NOT FOR SUBMISSION</a> · <a href="docs/verify.html">Inspect verification</a> · <a href="docs/executive-summary.html">How to submit a future cleared file</a> · <a href="docs/analysis.html">Reported 0.2778 analysis</a></p>
</div></body></html>
""")
print("site built:", ", ".join(pages))
