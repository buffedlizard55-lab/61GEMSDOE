#!/usr/bin/env python3
"""Build a status site from the current, fail-closed evidence.

This replaces the earlier generator that advertised H61-G as UNIQUE and called
owner-reported scores organizer-confirmed. A download is labelled as a
competition submission only when both strict uniqueness phases and the holdout
selector clear it; otherwise the old raster is shown as diagnostic-only.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EVID = ROOT / "evidence"
COMP = "https://www.drivendata.org/competitions/306/competition-doe-gems/"
REPO = "https://github.com/buffedlizard55-lab/61GEMSDOE"


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def esc(value) -> str:
    return html.escape(str(value))


def f4(value) -> str:
    return f"{float(value):.4f}"


def file_link(label: str, path: str, *, download=False) -> str:
    return f'<a href="{esc(path)}"{ " download" if download else ""}>{esc(label)}</a>'


fin = load("evidence/h61g_final.json")
uni = load("evidence/h61g_uniqueness.json")
hold = load("evidence/h61g_holdout.json")
invert = load("evidence/h61g_invert.json")
h61l = load("evidence/h61l_surface.json")
lidar = load("evidence/h61l_lidar_source.json")
hyps = load("evidence/h61g_hypotheses.json")
registry = load("evidence/registry_accessible_index.json")
artifact_audit = load("evidence/local_artifact_strict_dot_audit.json")
forensics = load("reports/forensics.json")

TIF = fin["download_tif"]
ZIP = fin["download_zip"]
RECEIPT = str(Path(TIF).with_suffix(".json"))
# The generated HTML lives under docs/, so links are relative to that directory.
DOWNLOAD_TIF = f"downloads/{Path(TIF).name}"
DOWNLOAD_ZIP = f"downloads/{Path(ZIP).name}"
DOWNLOAD_RECEIPT = f"downloads/{Path(RECEIPT).name}"
NOTE = fin["note"]
SHA = fin["sha256"]
CANDIDATE = next(r for r in hold["results"]
                 if r["name"] == f"{fin['candidate']} @ {fin['budget']}")
RANDOM_LINES = next(r for r in hold["results"]
                    if r["name"] == f"CONTROL random lines @ {fin['budget']}")
H19_DOTTED = next(r for r in hold["results"]
                  if r["name"].startswith("REGISTRY gems25-dotted-h19-5"))
H19_LINES = next(r for r in hold["results"]
                 if r["name"].startswith("REGISTRY gems19-h19-5"))
LIDAR_GATE = h61l["uniqueness"]
LIDAR_WORST = max(LIDAR_GATE["rows"],
                  key=lambda r: r.get("my_dots_within_3px_of_theirs", -1))
H61G_DENSE = next(r for r in uni["rows"]
                  if r["file"] == "gems61-lane-buried-step-gravinversion-hgm-r3-k400k-b2zeros.tif")
LIDAR_DENSE = next(r for r in LIDAR_GATE["rows"]
                   if r["file"] == "gems61-lane-buried-step-gravinversion-hgm-r3-k400k-b2zeros.tif")

reported_h33 = next(r for r in forensics["rasters"]
                    if "gemsdoe32-h33-h33-2-b2" in r["file"])
leaderboard_source = f"{COMP}leaderboard/"

NAV = [
    ("index.html", "Status"),
    ("executive-summary.html", "Executive summary &amp; how to submit"),
    ("analysis.html", "Score provenance"),
    ("hypotheses.html", "Next hypotheses"),
    ("method.html", "Method"),
    ("holdout.html", "Holdout evidence"),
    ("irregularities.html", "Irregularities"),
    ("next-steps.html", "Next steps"),
    ("verify.html", "Verify"),
    ("submit.html", "Submission instructions"),
    ("limitations.html", "Limitations"),
]

BASE_CSS = """
.status{border:2px solid #f85149;background:#2a0f0f;padding:16px 20px;border-radius:10px;margin:18px 0}
.status h2{margin:.15em 0 .5em;border:0;color:#ff7b72}.status p:last-child{margin-bottom:0}
.btn{display:inline-block;background:#58a6ff;color:#0d1117;font-weight:700;padding:12px 18px;border-radius:8px;text-decoration:none;margin:6px 8px 6px 0}
.btn.warn{background:#f2cc60}.btn.sec{background:#161b22;color:#e6edf3;border:1px solid #30363d}
.tag{display:inline-block;font:700 .72rem/1.4 ui-monospace,monospace;padding:1px 6px;border-radius:4px;border:1px solid #30363d;margin-right:4px}
.tag.h{color:#58a6ff}.tag.o{color:#3fb950}.tag.p{color:#f2cc60}.tag.bad{color:#ff7b72}
table{border-collapse:collapse;width:100%;font-size:.92rem;margin:10px 0}th,td{border:1px solid #30363d;padding:6px 8px;text-align:left;vertical-align:top}th{background:#161b22}
nav{font-size:.9rem;color:#8b949e;margin-bottom:8px}nav a.active{font-weight:700;text-decoration:underline}
.small{font-size:.85rem;color:#8b949e}.callout{border-left:4px solid #f2cc60;background:#161b22;padding:10px 14px;margin:12px 0}
code,pre{overflow-wrap:anywhere}
"""


def page(title: str, body: str, active: str) -> str:
    nav = " · ".join(
        f'<a href="{href}"{" class=active" if href == active else ""}>{label}</a>'
        for href, label in NAV
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · 61GEMSDOE</title><link rel="stylesheet" href="assets/site.css">
<style>{BASE_CSS}</style></head><body><div class="wrap"><nav>{nav}</nav>
{body}
<hr><p class="small">61GEMSDOE · evidence is local and hash-checked where stated. HOLDOUT-DTI is a proxy, not a leaderboard score.
ORGANIZER-CONFIRMED is reserved for an organizer receipt tied to exact artifact bytes. <a href="{REPO}">Repository</a> ·
<a href="{leaderboard_source}">Official leaderboard</a>.</p></div></body></html>"""


def status_box() -> str:
    return f"""
<div class="status">
<h2>NO TIFF IS CURRENTLY CLEARED FOR COMPETITION SUBMISSION</h2>
<p><b>Existing H61-G GeoTIFF:</b> its local format/range validator passes ({sum(bool(v) for v in fin['validator'].values())}/{len(fin['validator'])} checks),
but strict uniqueness fails: <b>{H61G_DENSE['my_dots_within_3px_of_theirs']:.4%}</b> of its positive pixels fall within 3 px of
<code>{esc(H61G_DENSE['file'])}</code>, above the literal 70% stop threshold. Jaccard is diagnostic only; it cannot waive the stop.</p>
<p><b>Top new hypothesis H61-L in the current run:</b> its pre-placement scarp-ribbon surface fails, at
<b>{LIDAR_DENSE['my_dots_within_3px_of_theirs']:.4%}</b> one-sided overlap. That run stopped before placement and produced no holdout or TIFF.
A separate archived H61-L TIFF from the merged main branch exists, but it is not cleared.</p>
<p><b>Post-merge local-artifact audit:</b> <b>{artifact_audit['summary']['strict_overlap_stops']}/{artifact_audit['summary']['candidate_artifacts']}</b> local candidate TIFFs fail the same literal final-dot threshold.
The audited main-branch H61-L/H61-M/H61-X files and the TIFF under <code>docs/submissions/</code> are historical, not approved. The accessible inventory is not organizer-complete.</p>
<p><b>Decision:</b> do not submit any file from this repository at this time. The linked H61-G TIFF is downloadable only for audit/learning, not as a competition submission.
No weekly slot has been used and no organizer receipt/score exists for a project artifact.</p>
</div>"""


def metric_label(row: dict, evaluator: str, n: int) -> str:
    return (f"HOLDOUT-DTI {row['pooled_dti']:.6f} (95% CI "
            f"[{row['ci95_bootstrap_cells'][0]:.6f}, {row['ci95_bootstrap_cells'][1]:.6f}]; "
            f"{n:,} withheld positives; evaluator {evaluator})")


status = status_box()

index_body = f"""
<h1>61GEMSDOE — buried-structure lane</h1>
<p>Basement relief from the supplied isostatic gravity; USGS GP-1012 used only for regional depth-scale calibration.
The first question is whether an artifact is safe to submit. The answer is currently <b>no</b>.</p>
{status}
<h2>Current evidence</h2>
<table><tr><th>Artifact/result</th><th>What is measured</th><th>Decision</th></tr>
<tr><td>H61-G existing TIF</td><td>One-band float32, EPSG:32611, 3730×3292, template transform, all finite, [0,1]. SHA-256 <code>{SHA}</code>.</td><td>Format-valid only; strict uniqueness fails ({H61G_DENSE['my_dots_within_3px_of_theirs']:.4%} &gt; 70%). Diagnostic only.</td></tr>
<tr><td>H61-G old holdout</td><td>{metric_label(CANDIDATE, hold['evaluator'], hold['n_withheld_truth_px'])}. Random lines at equal budget: {metric_label(RANDOM_LINES, hold['evaluator'], hold['n_withheld_truth_px'])}.</td><td>Historical proxy evidence; not an organizer score.</td></tr>
<tr><td>H61-L current-run surface</td><td>{LIDAR_GATE['candidate_support_pixels']:,} positive surface pixels; full-footprint Spearman max {LIDAR_GATE['worst_spearman']:.4f}; worst one-sided 3 px overlap {LIDAR_GATE['worst_overlap']:.4%}.</td><td>Pre-placement uniqueness stop; this run made no holdout or TIFF.</td></tr>
<tr><td>Archived local candidate TIFFs</td><td>{artifact_audit['summary']['candidate_artifacts']} unique TIFF artifacts audited against <code>{esc(Path(artifact_audit['comparator']['path']).name)}</code>; one-sided overlap range {min(r['one_sided_overlap_fraction'] for r in artifact_audit['candidates']):.4%}–{max(r['one_sided_overlap_fraction'] for r in artifact_audit['candidates']):.4%}.</td><td>{artifact_audit['summary']['strict_overlap_stops']}/{artifact_audit['summary']['candidate_artifacts']} strict final-dot stops; no file cleared. <a href="../evidence/local_artifact_strict_dot_audit.json">Audit receipt</a>.</td></tr>
</table>
<p><b>Download for audit only:</b> {file_link(Path(TIF).name, DOWNLOAD_TIF, download=True)} · {file_link("ZIP", DOWNLOAD_ZIP, download=True)} ·
{file_link("format receipt", DOWNLOAD_RECEIPT)}. Do not upload these archived bytes. A future submission needs both a passing pre-placement and final-dot gate plus an eligible holdout result.</p>
<p><a href="executive-summary.html">Submission safety and upload steps</a> · <a href="analysis.html">Score provenance</a> ·
<a href="hypotheses.html">Ranked hypotheses</a> · <a href="verify.html">Strict uniqueness evidence</a> ·
<a href="../evidence/h61l_run_card.json">Current JSON run card</a>.</p>
"""

exec_body = f"""
<h1>Executive summary &amp; how to submit</h1>
{status}
<h2>Download status</h2>
<p>The H61-G file below is a format-valid research artifact, <b>not cleared for submission</b>. It is linked so reviewers can reproduce the local format and uniqueness checks.</p>
<p><a class="btn warn" href="{esc(DOWNLOAD_TIF)}" download>Download H61-G diagnostic TIFF — DO NOT SUBMIT</a>
<a class="btn sec" href="{esc(DOWNLOAD_ZIP)}" download>Diagnostic ZIP</a>
<a class="btn sec" href="{esc(DOWNLOAD_RECEIPT)}">Format receipt</a></p>
<p><b>Archived file under <code>docs/submissions/</code> — DO NOT SUBMIT:</b> its strict final-dot overlap is 99.1475%.
<a href="submissions/61gemsdoe-basement-step-ribbon-20261011T054408Z.tif">View the historical TIFF only with this warning</a> ·
<a href="../evidence/local_artifact_strict_dot_audit.json">full strict artifact audit</a>.</p>
<p>SHA-256 <code>{SHA}</code> · submission-form note attached to the historic artifact ({fin['note_chars']}/140 chars):
<code>{esc(NOTE)}</code>. That note does not make the file cleared.</p>
<h2>How to submit a future cleared file</h2>
<ol>
<li>Use only a candidate whose run card says pre-placement surface uniqueness passed, final-dot uniqueness passed, local validation passed, and holdout evidence supports promotion.</li>
<li>Download the exact one-band GeoTIFF named by that run card and verify its SHA-256.</li>
<li>Open the <a href="{COMP}submissions/">official submissions page</a> while logged into the competition account; upload the GeoTIFF and paste the note from the run card (at most 140 characters).</li>
<li>Save the platform's submission receipt and score; only then label the value ORGANIZER-CONFIRMED for those exact bytes.</li>
</ol>
<p><b>Do not upload any repository TIFF, including the archived file under <code>docs/submissions/</code> and the main-branch H61-L/H61-M/H61-X downloads.</b> The old "UNIQUE" labels are not accepted under the literal strict gate. No automatic portal submission was attempted; no competition credential was used.</p>
<h2>Why the old range error should not recur</h2>
<p>The H61-G diagnostic file passes its local template/range validator: single-band float32, EPSG:32611, 3730×3292, sample transform, finite everywhere,
values in [0,1], zero outside the footprint. These checks establish local formatting only—not uniqueness, upload acceptance, or score.</p>
"""

# No organizer receipt was found for the owner-reported H33 score.
claim = reported_h33.get("claimed_score_by_group")
removed = forensics.get("set_difference_forensics", {}).get("top_minus_core", {})
analysis_body = f"""
<h1>Score provenance and the owner-reported 0.2778 artifact</h1>
<p><b>Provenance correction:</b> <code>reports/forensics.json</code> says every score in the group's CLAIMED table is a group/owner report;
no organizer receipt ties those exact bytes to a leaderboard row. Thus <b>0.2778 is not ORGANIZER-CONFIRMED here</b>.
The official leaderboard is separate: as fetched on 2026-10-11, #1 was 0.4133 and #8 was 0.3195 (the latter is not the leaderboard high).
<a href="{leaderboard_source}">Check the live official table</a>.</p>
<h2>What is measured about the H33 bytes</h2>
<p>The group-reported value is {claim:.4f}, attached to <code>{esc(reported_h33['file'])}</code> with SHA-256
<code>{reported_h33['sha256']}</code>. Byte-level forensics finds that raster is a strict subset of the 44,090-pixel h19-5 core:
{removed['core_n']:,} core pixels → {removed['top_n']:,}; {removed['removed_n']:,} removed pixels are all within 3 px of the mapped catalogue.
This is a measured construction relationship, not proof of the claimed leaderboard score.</p>
<p>The plausible metric mechanism, conditional on the report being accurate, is geometric: DTI uses a 300 m triangular kernel with α=.2 and β=.8;
pruning positives beside already-mapped faults removes guaranteed/near-guaranteed false positives. The measured set difference supports that explanation,
but without a submission receipt we cannot assert the artifact scored 0.2778.</p>
<h2>Our lane result is separate</h2>
<p>H61-G's old artifact has {metric_label(CANDIDATE, hold['evaluator'], hold['n_withheld_truth_px'])}, versus
{metric_label(H19_DOTTED, hold['evaluator'], hold['n_withheld_truth_px'])} for the as-published H19-5 dotted reference raster and
{metric_label(RANDOM_LINES, hold['evaluator'], hold['n_withheld_truth_px'])} for the equal-budget random-line control.
These are all HOLDOUT-DTI proxy scores, not organizer scores. H61-G does not beat the strongest reference and fails uniqueness.
The current-run H61-L top hypothesis was stopped before holdout because its surface failed the strict overlap rule. A separate archived main-branch H61-L variant has historical HOLDOUT-DTI evidence, but its final TIFF fails the current strict overlap rule and is not eligible.</p>
<h2>Leaderboard discrepancy</h2>
<p>The official page fetched 2026-10-11 listed the leader at 0.4133; 0.3195 was rank #8. A previously saved sibling-site snapshot gave a different ordering,
so we report that dated official fetch, not an undated value. No owner-reported score is substituted for a public leaderboard row.</p>
"""

hyp_rows = []
for hypothesis in sorted(hyps, key=lambda row: row.get("rank", 99)):
    status_note = ""
    if hypothesis.get("id") == "H61-L":
        status_note = (f"<p class=\"callout\"><b>Measured pre-placement outcome:</b> {hypothesis.get('preplacement_status')}; "
                       f"{hypothesis.get('one_sided_overlap_fraction', 0):.4%} one-sided overlap; "
                       "this current run stopped before holdout/placement and emitted no TIFF. A separate archived main-branch H61-L TIFF exists but fails the strict final-dot gate.</p>")
    hyp_rows.append(f"""
<section><h2>#{hypothesis['rank']} {esc(hypothesis['id'])} — {esc(hypothesis['name'])}</h2>
{status_note}<table>
<tr><th>Layers</th><td>{esc(hypothesis.get('layers',''))}</td></tr>
<tr><th>Physical signature</th><td>{esc(hypothesis.get('signature',''))}</td></tr>
<tr><th>Why it may catch catalogue-missing faults</th><td>{esc(hypothesis.get('why',''))}</td></tr>
<tr><th>Difference from implemented work</th><td>{esc(hypothesis.get('diff',''))}</td></tr>
<tr><th>Expected DTI gain (projection, not score)</th><td>{esc(hypothesis.get('gain',''))}</td></tr>
<tr><th>Cost / data</th><td>{esc(hypothesis.get('cost',''))}</td></tr></table></section>
""")
hyp_body = """
<h1>Ranked novel candidate hypotheses</h1>
<p>These are 3–5 unimplemented or materially distinct buried-structure hypotheses, ranked by expected gain relative to effort.
All gain language is a PROJECTION, never a score. The top candidate is screened against the strict registry gate before any holdout or placement.
</p>
""" + "".join(hyp_rows) + """
<h2>Selection rule</h2>
<p>A hypothesis may proceed to holdout only after its pre-placement surface clears both literal thresholds against every raster in the declared inventory.
A passing surface would then be tested by the shared spatially blocked hide-and-recover evaluator, with a feature-alone leakage canary and a matched random-line control.
Weekly promotion is a separate selector decision. The current-run H61-L candidate failed before holdout, so no score or TIFF is imputed for that run. A separate archived main-branch H61-L TIFF is retained as historical, and fails the strict final-dot gate.</p>
"""

method_body = f"""
<h1>Buried-structure method and limitations</h1>
<h2>Lane definition</h2>
<p>Use the supplied isostatic gravity to estimate basement relief; calibrate only the depth scale against USGS Saltus &amp; Jachens GP-1012;
identify horizontal-gradient maxima in the basement-depth surface as candidate buried steps; emit ribbons; compare basin-interior withheld-segment recovery against random lines;
treat intrabasement density contrasts as the named non-fault mimic.</p>
<h2>What the current H61-G implementation actually does</h2>
<p>Band 13 is regional-separated at 15 km, decimated to 400 m, and converted by a low-passed Bouguer-slab first iterate with
<code>z0={invert['inversion']['z0_m']:.0f} m</code>, <code>Δρ={invert['inversion']['delta_rho']:.0f} kg/m³</code>,
and <code>kc_scale={invert['inversion'].get('filter','')}</code>. GP-1012 scale anchors set a >1 km fraction of
{invert['calibration']['best']['stats']['fraction_gt_1km']:.3f} (target ≈0.20); band 15 is used as an independent check only
(Pearson r={invert['cross_check_vs_supplied_band15']['pearson_r']:.3f}). The current production surface is <b>the first low-passed slab iterate</b>, not a demonstrated converged nonlinear Parker–Oldenburg inversion.</p>
<p>The six-step nonlinear test in <code>evidence/measure.json</code> ends with 130.546 m maximum change at iteration 6 (1 m tolerance) and a 1.4038 mGal residual.
The residual falls over the recorded steps; this does not prove general divergence, but it also does not establish convergence. Treat basement relief and any step maps as provisional.
This method/provenance mismatch is flagged as IR-61-CONV-02.</p>
<h2>Steps and H61-G locator</h2>
<p>At 400 m the existing run found {invert['steps']['n_hgm_maxima_400m']:,} HGM maxima, {invert['steps']['n_steps_throw_filtered']:,} after a ≥{invert['steps']['min_throw_m']:.0f} m throw filter,
and {invert['steps']['n_persistent_steps']:,} persistent maxima. The historical H61-G candidate used those basement steps as a ±1 km corridor and band-19 detrended-elevation slope ridges as the 100 m locator.
Its file is dots, not the requested basement-step ribbons; this is recorded as a lane/emission mismatch.</p>
<h2>H61-L top hypothesis (stopped)</h2>
<p>H61-L uses an upstream public 12-band terrain-descriptor raster derived from USGS 3DEP 1 m DEM tiles (not raw lidar and not a fault prediction).
It combines shortwave slope excess, 10 m/50 m slope break, crest/base curvature and structure-tensor coherence, then forms 3-pixel scarp ribbons inside
basement-step corridors under fill. The descriptor covers {lidar['shape'][0]}×{lidar['shape'][1]} cells and {h61l['surface_metadata']['lidar_coverage_fraction_of_footprint']:.1%} of the valid competition footprint;
SHA-256 <code>{lidar['local_sha256']}</code>. The current-run surface failed the strict pre-placement gate, so that run did not reach holdout. A different main-branch H61-L variant has a historical HOLDOUT-DTI result but its final TIFF fails the strict post-placement gate and is not cleared.</p>
<h2>Named non-fault mimic and trusted sources</h2>
<ul>
<li>Intrabasement lithologic/density contacts can make gravity steps without a fault; terrain-only steps can instead be fan toes, terrace risers, channels, landslides, roads or mines.</li>
<li>Parker (1973), DOI <a href="https://doi.org/10.1111/j.1365-246X.1973.tb06513.x">10.1111/j.1365-246X.1973.tb06513.x</a>; Oldenburg (1974), DOI <a href="https://doi.org/10.1190/1.1440444">10.1190/1.1440444</a>.</li>
<li>Blakely &amp; Simpson (1986), DOI <a href="https://doi.org/10.1190/1.1442197">10.1190/1.1442197</a>; Blakely &amp; Jachens (1991), <a href="https://doi.org/10.1130/0016-7606(1991)103%3C0795:RSOMRI%3E2.3.CO;2">DOI 10.1130/0016-7606(1991)103&lt;0795:RSOMRI&gt;2.3.CO;2</a>.</li>
<li>Saltus &amp; Jachens (1995), USGS GP-1012, <a href="https://doi.org/10.3133/gp1012">DOI 10.3133/gp1012</a>; <a href="https://pubs.usgs.gov/publication/gp1012">map publication</a>.</li>
<li>USGS <a href="https://www.usgs.gov/3d-elevation-program">3DEP</a> source description: <a href="{lidar['source']}">feature raster</a> · <a href="{lidar['metadata_source']}">band/quantization metadata</a>.</li>
</ul>
"""

hold_rows = []
for name in (
    fin["candidate"] + " @ " + str(fin["budget"]),
    f"CONTROL random lines @ {fin['budget']}",
    next((r["name"] for r in hold["results"] if r["name"].startswith("REGISTRY gems25-dotted-h19-5")), ""),
    next((r["name"] for r in hold["results"] if r["name"].startswith("REGISTRY gems19-h19-5")), ""),
):
    row = next(r for r in hold["results"] if r["name"] == name)
    recovered = row.get("segments_recovered_basin_interior")
    withheld = row.get("segments_withheld_basin_interior")
    basin_recovery = (f"{recovered:,}/{withheld:,} ({row.get('basin_recovery_rate', 0):.1%})"
                      if recovered is not None and withheld else "not reported")
    hold_rows.append(f"<tr><td>{esc(row['name'])}</td><td>{row.get('n_emitted_per_draw',0):,.0f}</td><td>{row['pooled_dti']:.6f}</td><td>[{row['ci95_bootstrap_cells'][0]:.6f}, {row['ci95_bootstrap_cells'][1]:.6f}]</td><td>{row.get('coverage',0):.4f}</td><td>{basin_recovery}</td></tr>")
hold_body = f"""
<h1>Holdout evidence: legacy H61-G and controls</h1>
<p>All numerical rows below are <b>HOLDOUT-DTI</b> under <code>{esc(hold['evaluator'])}</code>, with
{hold['n_withheld_truth_px']:,} withheld positive pixels, α={hold['alpha']}, β={hold['beta']}, {hold['kernel_m']} m triangular kernel, and the listed 95% CI.
These are proxy scores on withheld catalogue segments, not live organizer scores.</p>
<table><tr><th>Arm</th><th>Positive pixels per draw</th><th>HOLDOUT-DTI</th><th>95% CI</th><th>coverage</th><th>Basin-interior segment recovery</th></tr>
{''.join(hold_rows)}</table>
<p>The historical H61-G construction is below the as-published dotted H19-5 reference and is not eligible for a slot. Its strict final-dot uniqueness verdict is
<code>{esc(uni['verdict'])}</code>. The current-run H61-L surface stopped before holdout, so that run has no H61-L HOLDOUT-DTI. A separate archived main-branch H61-L variant was measured at <b>HOLDOUT-DTI 0.044330</b> (95% CI [0.041405, 0.047832]; 22,641 withheld positives; evaluator <code>gems61.holdout_segmented v2</code>), but its final TIFF has 98.6375% strict one-sided overlap and is not eligible for a slot.</p>
<p>On the same 1,999 withheld basin-interior segments, historical H61-G recovered {CANDIDATE['segments_recovered_basin_interior']:,} ({CANDIDATE['basin_recovery_rate']:.1%}) versus {RANDOM_LINES['segments_recovered_basin_interior']:,} ({RANDOM_LINES['basin_recovery_rate']:.1%}) for equal-budget random lines. This is proxy recovery, not hidden organizer truth.</p>
<p>Feature-alone canary on the historical H61-G holdout: worst AUC {hold['leakage_canary']['worst_auc']:.3f}, threshold 0.90.
The current-run H61-L surface did not reach holdout, so no canary or DTI is claimed for that run. The separate main-branch H61-L variant's historical HOLDOUT-DTI is documented above and does not clear its strict final-dot failure.</p>
"""

irr = load("evidence/h61g_irregularities.json")
irr_body = "<h1>Irregularities and corrections</h1><table><tr><th>ID</th><th>Finding</th><th>Action</th></tr>" + "".join(
    f"<tr><td><code>{esc(row['id'])}</code></td><td>{esc(row.get('finding',row.get('statement','')))}</td><td>{esc(row.get('action',''))}</td></tr>"
    for row in irr) + "</table>"

next_body = f"""
<h1>Next steps and remaining limitations</h1>
<h2>Decision</h2>
<p><b>No candidate is cleared and no weekly slot should be spent.</b> The old H61-G TIFF fails the explicit strict final-dot gate;
H61-L fails before placement. No organizer score exists for a repository artifact.</p>
<h2>What would unblock a new candidate</h2>
<ol>
<li>Start from a new in-lane hypothesis and build a pre-placement surface from permitted geological inputs.</li>
<li>Compare that surface against every raster in the declared accessible inventory; stop if positive Spearman &gt;0.90 or if more than 70% of positive pixels are within 3 px of any single prior raster.</li>
<li>Only after a passing surface, run the shared spatially blocked hide-and-recover evaluator, visible-only catalogue features, pixel-exact masking, the feature-alone leakage canary, and a matched random-line control.</li>
<li>Write ribbons, check the final raster with the same strict gate, validate with the shared writer, and promote only if the holdout selector says it beats the holdout best. A weekly slot remains separate.</li>
</ol>
<h2>Limitations</h2>
<ul>
<li>The current index covers {registry['scope']['declared_public_source_count']} paths from <code>scripts/registry_sources.tsv</code> and {registry['scope']['repository_prior_file_count']} TIFFs across local roots (32 records total); it is not the organizer-side registry. The original H61-G/H61-L run receipts retain their 21+7 pre-merge snapshot.</li>
<li>The 10 locally published candidate TIFFs all exceed the literal final-dot overlap stop against the hash-pinned HGM prior. The archived main-branch "UNIQUE" labels are retired; see <a href="../evidence/local_artifact_strict_dot_audit.json">the measured audit</a>. This short-circuit final-dot audit does not supply missing pre-placement receipts.</li>
<li>The current-run H61-L 3DEP-derived descriptor source is a public repository derivative. Its scarp score is not calibrated against hidden truth; that surface was not holdout-scored. A separate archived H61-L variant was HOLDOUT-DTI-scored but failed the strict final-dot gate.</li>
<li>The production basement surface is a first low-pass slab iterate; a converged nonlinear Parker–Oldenburg inversion remains unverified.</li>
<li>HOLDOUT-DTI uses mapped catalogue segments as proxy truth, while competition truth is undisclosed/unmapped. No HOLDOUT-DTI value is a live score.</li>
<li>Score claims for H33/H19 are owner-reported in the available forensics; no receipt binding exact artifact bytes to a score was found.</li>
</ul>
<h2>Trusted manual-review links</h2>
<ul><li><a href="{COMP}page/967/">Official metric/format page</a></li><li><a href="{leaderboard_source}">Official leaderboard</a></li>
<li><a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">Official rules</a></li><li><a href="https://doi.org/10.3133/gp1012">USGS GP-1012</a></li>
<li><a href="https://www.usgs.gov/3d-elevation-program">USGS 3DEP</a></li></ul>
"""

verify_rows = []
for name, ok in fin["validator"].items():
    verify_rows.append(f"<tr><td><code>{esc(name)}</code></td><td>{'PASS' if ok else 'FAIL'}</td></tr>")
prior_rows = []
for row in uni["rows"]:
    if "spearman_full_footprint" not in row:
        continue
    prior_rows.append(f"<tr><td><code>{esc(row['file'])}</code></td><td>{row['spearman_full_footprint']:+.5f}</td>"
                      f"<td>{row['my_dots_within_3px_of_theirs']:.5%}</td><td>{row['jaccard_dot_sets']:.5f}</td>"
                      f"<td>{'STOP' if row.get('duplicate') else 'pass'}</td></tr>")
artifact_rows = []
for row in artifact_audit["candidates"]:
    artifact_rows.append(
        f"<tr><td><code>{esc(', '.join(row['paths']))}</code></td>"
        f"<td>{row['positive_pixels']:,}</td>"
        f"<td>{row['one_sided_overlap_fraction']:.5%}</td>"
        f"<td>{'STOP' if row['overlap_stop'] else 'not cleared'}</td></tr>"
    )

verify_body = f"""
<h1>Format and uniqueness verification</h1>
<h2>H61-G archived TIFF local-format validation</h2>
<p>File <code>{esc(Path(TIF).name)}</code>, SHA-256 <code>{SHA}</code>; local writer/validator checks only.
All listed format/range checks pass; this does not clear uniqueness or organizer acceptance.</p>
<table><tr><th>Check</th><th>Result</th></tr>{''.join(verify_rows)}</table>
<h2>H61-G final-dot strict uniqueness</h2>
<p>Verdict <b>{esc(uni['verdict'])}</b>; {uni['inventory']['raster_count']} raster comparisons in the declared scope; organizer registry complete: no.
Limits: signed full-footprint Spearman &gt; {uni['rho_limit']:.2f}, OR one-sided positive-support overlap &gt; {uni['overlap_limit']:.0%} within {uni['overlap_radius_px']} px.
Jaccard is diagnostic only.</p>
<table><tr><th>Raster</th><th>Spearman</th><th>Candidate positives within 3 px</th><th>Jaccard (diagnostic)</th><th>Gate</th></tr>{''.join(prior_rows)}</table>
<p><b>Archive limitation:</b> no pre-placement surface-uniqueness receipt was found for the old H61-G dots. Do not infer a surface pass; the measured final-dot failure independently bars submission.</p>
<h2>H61-L surface-before-placement gate</h2>
<p>Verdict <b>{esc(LIDAR_GATE['verdict'])}</b>; candidate support {LIDAR_GATE['candidate_support_pixels']:,}; maximum positive Spearman
{LIDAR_GATE['worst_spearman']:.5f}; worst one-sided overlap {LIDAR_GATE['worst_overlap']:.5%} vs limit {LIDAR_GATE['overlap_limit']:.0%}.
The highest-overlap raster is <code>{esc(LIDAR_WORST['file'])}</code>. This current-run H61-L surface stopped here: no placement, holdout, or TIFF from this run. The separate archived main-branch variant is listed in the post-merge final-dot audit below and is not cleared.</p>
<p>Accessible inventory record: <a href="../evidence/registry_accessible_index.json">registry_accessible_index.json</a>;
H61-G gate receipt: <a href="../evidence/h61g_uniqueness.json">h61g_uniqueness.json</a>;
H61-L surface receipt: <a href="../evidence/h61l_surface.json">h61l_surface.json</a>.</p>
<h2>Post-merge strict final-dot audit of local TIFFs</h2>
<p>{artifact_audit['summary']['strict_overlap_stops']}/{artifact_audit['summary']['candidate_artifacts']} local candidate artifacts stop at the one-sided 3 px overlap leg against
<code>{esc(Path(artifact_audit['comparator']['path']).name)}</code>; threshold is strictly &gt;70%. This proves a stop, not a clearance of any unreported comparison.
The archived main-branch pre-placement receipts are not accepted as strict-gate clearance; see the complete <a href="../evidence/local_artifact_strict_dot_audit.json">audit receipt</a>.</p>
<table><tr><th>Local TIFF artifact</th><th>Positive cells</th><th>One-sided overlap</th><th>Strict gate</th></tr>{''.join(artifact_rows)}</table>
"""

submit_body = f"""
<h1>Submission instructions</h1>
{status}
<p>These instructions describe the portal procedure for a future file that has passed the project's gates. <b>Do not submit any current or archived repository TIFF, including the file under <code>docs/submissions/</code>.</b></p>
<ol><li>Verify a current run card names an exact TIFF and reports both uniqueness phases passed.</li>
<li>Verify the same card reports format checks passed and a holdout result above the selector's bar.</li>
<li>Download that exact TIFF; use its SHA-256 and note from the run card.</li>
<li>Log in to <a href="{COMP}submissions/">DrivenData submissions</a>, upload the GeoTIFF, paste the note (≤140 characters), and save the organizer receipt.</li>
<li>Only label a score ORGANIZER-CONFIRMED when the receipt identifies those exact artifact bytes.</li></ol>
<p>No automatic portal upload was attempted; no competition slot was used.</p>
"""

limitations_body = f"""
<h1>Limitations</h1>
<ul>
<li>No unique competition TIFF is currently cleared. H61-G fails the literal overlap rule; the current-run H61-L surface stopped before holdout; all {artifact_audit['summary']['candidate_artifacts']} local candidate TIFFs fail the strict final-dot overlap audit.</li>
<li>Registry coverage is a declared accessible scope ({registry['scope']['declared_public_source_count']} GitHub paths plus {registry['scope']['repository_prior_file_count']} local TIFFs across downloads/submissions/out), not an organizer-side inventory.</li>
<li>The existing basement-depth surface is the first low-passed slab iterate. Nonlinear convergence is unverified.</li>
<li>The USGS GP-1012 depth-scale calibration is regional and coarse; it is not target truth or a spatial training label.</li>
<li>The lidar derivative is a 100 m, 12-band descriptor stack aggregated from 2 m source work cells and has incomplete tile coverage; roads, channels, terraces, landslides, and mines mimic scarps.</li>
<li>The hide-and-recover instrument uses mapped catalogue faults as proxy truth; organizer truth is unmapped faults. Its values are not live scores.</li>
<li>No artifact-bound organizer receipt was located for the owner-reported 0.2778 H33 value or other owner-claimed sibling scores.</li>
</ul>
"""

pages = {
    "index.html": ("Status", index_body),
    "executive-summary.html": ("Executive summary", exec_body),
    "analysis.html": ("Score provenance", analysis_body),
    "hypotheses.html": ("Next hypotheses", hyp_body),
    "method.html": ("Method", method_body),
    "holdout.html": ("Holdout evidence", hold_body),
    "irregularities.html": ("Irregularities", irr_body),
    "next-steps.html": ("Next steps", next_body),
    "verify.html": ("Verify", verify_body),
    "submit.html": ("Submission instructions", submit_body),
    "limitations.html": ("Limitations", limitations_body),
}
DOCS.mkdir(parents=True, exist_ok=True)
for filename, (title, body) in pages.items():
    (DOCS / filename).write_text(page(title, body, filename), encoding="utf-8")

# Older parallel-session pages remain accessible but are explicitly marked historical.
banner = ('<div style="border:2px solid #d29922;background:#2a2208;padding:10px 14px;border-radius:8px;margin:12px 0">'
          '<b>HISTORICAL PAGE — SUPERSEDED.</b> Legacy score, “UNIQUE,” or “ready” labels are not current clearance. '
          'The current status is no TIFF cleared; the strict audit blocks 10/10 local artifacts. '
          '<a href="index.html">Current status</a> · '
          '<a href="../evidence/local_artifact_strict_dot_audit.json">strict audit</a>. '
          'Do not treat this page as a current submission clearance.</div>')
legacy_banner_pattern = re.compile(
    r'<div style="border:2px solid #d29922;.*?<b>(?:HISTORICAL PAGE\.|SUPERSEDED PAGE\.).*?</div>',
    flags=re.IGNORECASE | re.DOTALL,
)
for old in DOCS.glob("*.html"):
    if old.name in pages or old.name in {"404.html"}:
        continue
    text = old.read_text(encoding="utf-8")
    if "HISTORICAL PAGE — SUPERSEDED." in text:
        continue
    text, count = legacy_banner_pattern.subn(banner, text, count=1)
    if count == 0:
        text = re.sub(r"(<body[^>]*>)", lambda match: match.group(1) + banner, text, count=1,
                      flags=re.IGNORECASE)
    old.write_text(text, encoding="utf-8")

(ROOT / "index.html").write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=docs/index.html"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>61GEMSDOE — no submission cleared</title><link rel="stylesheet" href="docs/assets/site.css"></head><body><main class="wrap">
<h1>61GEMSDOE</h1><p><b>NO TIFF IS CURRENTLY CLEARED FOR COMPETITION SUBMISSION.</b></p>
<p>The H61-G file passes local format checks but fails the strict uniqueness threshold. The H61-L surface was stopped before holdout.
<a href="docs/index.html">Open the current status and evidence</a>.</p>
<p><a href="docs/executive-summary.html">Submission safety</a> · <a href="docs/verify.html">Uniqueness verification</a></p>
</main></body></html>""", encoding="utf-8")
print("status site built:", ", ".join(pages))
