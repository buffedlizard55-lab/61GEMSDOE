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
h61mh_holdout_source = load("evidence/h61m_holdout.json")
invert = load("evidence/h61g_invert.json")
h61l = load("evidence/h61l_surface.json")
lidar = load("evidence/h61l_lidar_source.json")
hyps = load("evidence/h61g_hypotheses.json")
registry = load("evidence/registry_accessible_index.json")
artifact_audit = load("evidence/local_artifact_strict_dot_audit.json")
# Two cards. ``evidence/run_card.json`` is the current submission-status card
# (H61-O, cleared under main's Jaccard exception, PR #22/#23); the legacy H61-L
# card is the only one that carries the ``proxy_context_scores`` rows used for
# the archived H61-MH comparison, so both stay loaded and both are linked.
current_run_card = load("evidence/run_card.json")
h61l_run_card = load("evidence/h61l_run_card.json")
h61o_final = load("evidence/h61o_final.json")
h61o_holdout = load("evidence/h61o_holdout.json")
h61o_uniqueness = load("evidence/h61o_uniqueness.json")
h61o_loqo = load("evidence/h61o_loqo.json")
H61O_TIF = h61o_final["download_tif"]
H61O_ZIP = h61o_final["download_zip"]
H61O_RECEIPT = str(Path(H61O_TIF).with_suffix(".json"))
DOWNLOAD_H61O_TIF = f"downloads/{Path(H61O_TIF).name}"
DOWNLOAD_H61O_ZIP = f"downloads/{Path(H61O_ZIP).name}"
DOWNLOAD_H61O_RECEIPT = f"downloads/{Path(H61O_RECEIPT).name}"
H61O_NAME = current_run_card["submission_name"]
H61O_NOTE = current_run_card["note"]
H61O_SHA = current_run_card["raster"]["sha256"]
H61O_BYTES = int(current_run_card["raster"]["bytes"])
H61O_DOTS = int(current_run_card["raster"]["positive_pixels"])
H61O_HOLDOUT = current_run_card["holdout_dti"]
H61O_REGISTRY = current_run_card["correlation_vs_registry"]
H61O_CHECKS = sum(bool(v) for v in h61o_final["validator"].values())
H61O_CHECKS_TOTAL = len(h61o_final["validator"])
H61O_MEDIAN_PX = float(h61o_final["dots_distance_to_catalogue_px"]["median"])
H61O_O2 = next(r for r in h61o_holdout["results"]
               if r["name"] == "O2 habitat no gate (prune 3px) @ 40000")
H61O_RANDOM_LINES = next(r for r in h61o_holdout["results"]
                         if r["name"] == "CONTROL random lines @ 40000")
H61O_RANDOM_DOTS = next(r for r in h61o_holdout["results"]
                        if r["name"] == "CONTROL random dots anywhere @ 40000")
h61mh_holdout = next(row for row in h61l_run_card["holdout"]["proxy_context_scores"]
                     if row.get("artifact", "").startswith("H61-MH"))
h61mh_audit = next(row for row in artifact_audit["candidates"]
                   if any("gems61-h61m-invfeat-habitat" in name for name in row["paths"]))
forensics = load("reports/forensics.json")
h61w_sub = load("evidence/h61w_submission.json")
h61w_holdout = load("evidence/h61w_holdout.json")
h61w_audit = next(row for row in artifact_audit["candidates"]
                  if any("h61w-p60-dip-projected" in name for name in row["paths"]))
H61W_TIF = h61w_sub["file"]
H61W_ZIP = str(Path(H61W_TIF).with_suffix(".zip"))
H61W_RECEIPT = str(Path(H61W_TIF).with_suffix(".json"))
DOWNLOAD_H61W_TIF = f"downloads/{Path(H61W_TIF).name}"
DOWNLOAD_H61W_ZIP = f"downloads/{Path(H61W_ZIP).name}"
DOWNLOAD_H61W_RECEIPT = f"downloads/{Path(H61W_RECEIPT).name}"
H61W_P60 = next(r for r in h61w_holdout["results"] if r["name"].startswith("P60 dip-projected trace 60deg"))
H61W_RANDOM = next(r for r in h61w_holdout["results"] if r["name"].startswith("CONTROL random lines @ 40000"))

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
H61MH_RIBBON = next(r for r in h61mh_holdout_source["results"]
                    if r["name"] == "M4 habitat x corridor, 3x3 ribbon @ 40000")
H61MH_DOTS = next(r for r in h61mh_holdout_source["results"]
                  if r["name"] == "M1 habitat x corridor (prune 2px) @ 40000")
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
.status.ok{border-color:#3fb950;background:#0f2312}.status.ok h2{color:#3fb950}
.status.audit{border-color:#d29922;background:#241d08}.status.audit h2{color:#f2cc60}
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
<div class="status ok">
<h2>CLEARED — FORMAT-VALID and UNIQUE — OK TO DOWNLOAD AND SUBMIT</h2>
<p><b>File to submit:</b> <code>{esc(Path(H61O_TIF).name)}</code> — {H61O_DOTS:,} single-pixel dots, {H61O_BYTES:,} bytes,
sha256 <code>{H61O_SHA[:16]}…</code>. <b>{H61O_CHECKS}/{H61O_CHECKS_TOTAL} local validator checks pass</b>
(single band, float32, EPSG:32611, 3730×3292, the sample-submission transform, no NaN/Inf anywhere, min 0 / max 1,
0.0 outside the footprint, zero dots on the mapped catalogue, median {H61O_MEDIAN_PX:.1f} px from it).</p>
<p><b>Uniqueness:</b> verdict <b>{esc(H61O_REGISTRY['verdict'])}</b> against {H61O_REGISTRY['n_compared']} registry rasters under the
<b>Jaccard-exception gate</b> (IR-61-UNIQ-01, added on main in PR #22/#23) — worst Spearman {H61O_REGISTRY['worst_spearman']['value']:+.4f} (limit 0.90) vs
<code>{esc(Path(H61O_REGISTRY['worst_spearman']['file']).name)}</code>; worst one-sided 3 px overlap
{H61O_REGISTRY['worst_gate']['value']:.4%} (limit 70%) vs <code>{esc(Path(H61O_REGISTRY['worst_gate']['file']).name)}</code>.</p>
<p><b>HOLDOUT-DTI:</b> {H61O_HOLDOUT['value']:.6f} (95% CI [{H61O_HOLDOUT['ci95'][0]:.6f}, {H61O_HOLDOUT['ci95'][1]:.6f}];
{H61O_HOLDOUT['n_withheld_truth_px']:,} withheld positives; evaluator <code>{esc(H61O_HOLDOUT['evaluator'].split(' (')[0])}</code>)
versus {H61O_HOLDOUT['random_lines_same_budget']:.6f} for equal-budget random lines and {H61O_RANDOM_DOTS['pooled_dti']:.6f} for random dots anywhere;
basin-interior recovery {H61O_HOLDOUT['basin_interior_segments']} versus {H61O_RANDOM_LINES['segments_recovered_basin_interior']}/{H61O_RANDOM_LINES['segments_withheld_basin_interior']} random lines.
The run card's verdict is <b>negative</b>: cleared to download and submit, but the selector should not spend a weekly slot on it.</p>
</div>
<div class="status audit">
<h2>STRICT LITERAL LEG IS REGISTRY-DEGENERATE (IR-61-UNIQ-01) — OLDER FILES REMAIN NOT CLEARED</h2>
<p>The strict literal rule (no more than 70% of a candidate's positives within 3 px of any single prior raster) is kept as an audit leg, not a submission rule:
H61-O itself measures {H61O_REGISTRY['worst_overlap']['value']:.4%} against <code>{esc(Path(H61O_REGISTRY['worst_overlap']['file']).name)}</code>,
whose 3 px dilation already covers {H61O_REGISTRY['worst_overlap']['base_rate']:.4%} of the valid footprint, and all
{artifact_audit['summary']['strict_overlap_stops']}/{artifact_audit['summary']['candidate_artifacts']} earlier local candidate TIFFs stop at that leg, including H61-MH at {h61mh_audit['one_sided_overlap_fraction']:.4%}.
No in-lane dotted candidate can pass it, which is why main added the Jaccard exception. The older files stay <b>NOT CLEARED</b> and must not be uploaded.</p>
<p><b>Audit-only artifact of this session (H61-W):</b> the dip-projected basement-step file <code>{esc(Path(H61W_TIF).name)}</code>
is format-valid and re-derived independently, but its honest holdout result is <b>HOLDOUT-DTI {H61W_P60['pooled_dti']:.6f}</b>
(95% CI [{H61W_P60['ci95_bootstrap_cells'][0]:.6f}, {H61W_P60['ci95_bootstrap_cells'][1]:.6f}]) against <b>{H61W_RANDOM['pooled_dti']:.6f}</b>
for equal-budget random lines — it loses to its own random control, so its run card is <b>negative</b> with <code>okay_to_submit: false</code>
and <code>download_class: AUDIT-ONLY</code>. Download it for audit/learning only; <b>DO NOT SUBMIT</b> those bytes.</p>
</div>"""


def metric_label(row: dict, evaluator: str, n: int) -> str:
    return (f"HOLDOUT-DTI {row['pooled_dti']:.6f} (95% CI "
            f"[{row['ci95_bootstrap_cells'][0]:.6f}, {row['ci95_bootstrap_cells'][1]:.6f}]; "
            f"{n:,} withheld positives; evaluator {evaluator})")


status = status_box()

index_body = f"""
<h1>61GEMSDOE — buried-structure lane</h1>
<p>Basement relief from the supplied isostatic gravity; USGS GP-1012 used only for regional depth-scale calibration.
The first question is whether an artifact is safe to submit. For the current file the answer is <b>yes</b> under the two-gate
uniqueness policy on <code>main</code>, with an honest negative on the holdout: it may be uploaded, but the selector should
not spend a weekly slot on it.</p>
{status}
<p><a class="btn" href="{esc(DOWNLOAD_H61O_TIF)}" download>↓ Download the submission GeoTIFF ({H61O_BYTES:,} bytes)</a>
<a class="btn sec" href="{esc(DOWNLOAD_H61O_ZIP)}" download>ZIP</a>
<a class="btn sec" href="{esc(DOWNLOAD_H61O_RECEIPT)}">Format receipt</a>
<a class="btn sec" href="../evidence/run_card.json">Current JSON run card</a></p>
<p class="small">Submission name <code>{esc(H61O_NAME)}</code> · note <code>{esc(H61O_NOTE)}</code> ({current_run_card['note_chars']}/140) ·
SHA-256 <code>{H61O_SHA}</code>.</p>
<h2>Current evidence</h2>
<table><tr><th>Artifact/result</th><th>What is measured</th><th>Decision</th></tr>
<tr><td>H61-O current submission file</td><td>One-band float32, EPSG:32611, 3730×3292, template transform, all finite, values in [0,1]; {H61O_DOTS:,} single-pixel dots; sha256 <code>{H61O_SHA[:16]}…</code>; variable-density Parker–Oldenburg inversion (Hildenbrand 1999) with Euler depth consistency and magnetic-edge mimic demotion. HOLDOUT-DTI {H61O_HOLDOUT['value']:.6f} (95% CI [{H61O_HOLDOUT['ci95'][0]:.6f}, {H61O_HOLDOUT['ci95'][1]:.6f}]; {H61O_HOLDOUT['n_withheld_truth_px']:,} withheld positives; evaluator <code>{esc(H61O_HOLDOUT['evaluator'].split(' (')[0])}</code>) versus {H61O_HOLDOUT['random_lines_same_budget']:.6f} random lines; basin {H61O_HOLDOUT['basin_interior_segments']} versus {H61O_RANDOM_LINES['segments_recovered_basin_interior']}/{H61O_RANDOM_LINES['segments_withheld_basin_interior']} random; LOQO mean {h61o_loqo['mean_dti']:.6f}.</td><td>FORMAT-VALID + UNIQUE under the Jaccard-exception gate; <b>OK TO DOWNLOAD AND SUBMIT</b>; holdout verdict <b>negative</b> (no weekly slot recommended).</td></tr>
<tr><td>H61-G existing TIF</td><td>One-band float32, EPSG:32611, 3730×3292, template transform, all finite, [0,1]. SHA-256 <code>{SHA}</code>.</td><td>Format-valid only; strict literal gate fails ({H61G_DENSE['my_dots_within_3px_of_theirs']:.4%} &gt; 70%); audit-only, NOT CLEARED.</td></tr>
<tr><td>H61-G old holdout</td><td>{metric_label(CANDIDATE, hold['evaluator'], hold['n_withheld_truth_px'])}. Random lines at equal budget: {metric_label(RANDOM_LINES, hold['evaluator'], hold['n_withheld_truth_px'])}.</td><td>Historical proxy evidence; not an organizer score.</td></tr>
<tr><td>H61-L current-run surface</td><td>{LIDAR_GATE['candidate_support_pixels']:,} positive surface pixels; full-footprint Spearman max {LIDAR_GATE['worst_spearman']:.4f}; worst one-sided 3 px overlap {LIDAR_GATE['worst_overlap']:.4%}.</td><td>Pre-placement uniqueness stop; that run made no holdout or TIFF.</td></tr>
<tr><td>Archived H61-MH inversion-feature variant</td><td>HOLDOUT-DTI {h61mh_holdout['value']:.6f} (95% CI [{h61mh_holdout['95_percent_ci'][0]:.6f}, {h61mh_holdout['95_percent_ci'][1]:.6f}]; {h61mh_holdout['withheld_positive_count']:,} withheld positives; {esc(h61mh_holdout['evaluator'])}); basin recovery {h61mh_holdout['basin_interior_segments_recovered']}/{h61mh_holdout['basin_interior_segments_withheld']} (rate 95% CI [{h61mh_holdout['basin_interior_recovery_ci95'][0]:.6f}, {h61mh_holdout['basin_interior_recovery_ci95'][1]:.6f}]).</td><td>Historical proxy only; strict literal overlap {h61mh_audit['one_sided_overlap_fraction']:.4%}; NOT CLEARED.</td></tr>
<tr><td>H61-W newest session artifact ({esc(h61w_sub['arm'])})</td><td>One-band float32, template grid, {h61w_sub['positive_pixels']:,} single-pixel dots, sha256 <code>{h61w_sub['sha256'][:16]}…</code>, re-derived independently (<a href="../evidence/h61w_independent_check.json">independent_check.json</a>); HOLDOUT-DTI {H61W_P60['pooled_dti']:.6f} (95% CI [{H61W_P60['ci95_bootstrap_cells'][0]:.6f}, {H61W_P60['ci95_bootstrap_cells'][1]:.6f}]; {h61w_holdout['n_withheld_truth_px']:,} withheld positives; evaluator <code>{esc(h61w_holdout['evaluator'].split(' --')[0])}</code>) vs {H61W_RANDOM['pooled_dti']:.6f} random lines.</td><td>Format-valid; result <b>negative</b> (below its random control); strict literal overlap {h61w_audit['one_sided_overlap_fraction']:.4%}; <code>okay_to_submit: false</code>, AUDIT-ONLY.</td></tr>
<tr><td>Archived local candidate TIFFs</td><td>{artifact_audit['summary']['candidate_artifacts']} unique TIFF artifacts audited against <code>{esc(Path(artifact_audit['comparator']['path']).name)}</code>; one-sided overlap range {min(r['one_sided_overlap_fraction'] for r in artifact_audit['candidates']):.4%}–{max(r['one_sided_overlap_fraction'] for r in artifact_audit['candidates']):.4%}.</td><td>{artifact_audit['summary']['strict_overlap_stops']}/{artifact_audit['summary']['candidate_artifacts']} strict literal stops; none of the older files is cleared. <a href="../evidence/local_artifact_strict_dot_audit.json">Audit receipt</a>.</td></tr>
<tr><td>Current accessible raster inventory</td><td>{registry['scope']['declared_public_source_count']} declared public paths + {registry['scope']['repository_prior_file_count']} local prior TIFFs = {registry['scope']['total_raster_records']} records.</td><td>Declared scope complete; organizer-side registry completeness is not claimed. <a href="../evidence/registry_accessible_index.json">Current inventory</a>.</td></tr>
</table>
<p><b>Download for audit only (never upload these):</b> {file_link(Path(TIF).name, DOWNLOAD_TIF, download=True)} · {file_link("ZIP", DOWNLOAD_ZIP, download=True)} ·
{file_link("format receipt", DOWNLOAD_RECEIPT)}. The older archived bytes are not cleared by the Jaccard exception, which applies only to the
H61-O file named above and only after its own receipt records a passing verdict.</p>
<p><b>Download for audit only (H61-W, newest session artifact):</b> {file_link(Path(H61W_TIF).name, DOWNLOAD_H61W_TIF, download=True)} · {file_link("ZIP", DOWNLOAD_H61W_ZIP, download=True)} ·
{file_link("format receipt", DOWNLOAD_H61W_RECEIPT)} · <a href="../evidence/h61w_run_card.json">run card</a>. <b>DO NOT SUBMIT</b> these bytes; the run card says <code>okay_to_submit: false</code>.</p>
<p><a class="btn warn" href="{esc(DOWNLOAD_H61W_TIF)}" download>Download the newest H61-W TIFF — DO NOT SUBMIT (negative result, audit-only)</a>
<a class="btn sec" href="{esc(DOWNLOAD_H61W_ZIP)}" download>ZIP</a>
<a class="btn sec" href="../evidence/h61w_run_card.json">H61-W run card</a></p>
<p><a href="executive-summary.html">Submission safety and upload steps</a> · <a href="analysis.html">Score provenance</a> ·
<a href="hypotheses.html">Ranked hypotheses</a> · <a href="verify.html">Uniqueness evidence</a> ·
<a href="../evidence/run_card.json">Current H61-O run card</a> · <a href="../evidence/h61l_run_card.json">H61-L stopped-run card</a>.</p>
"""

exec_body = f"""
<h1>Executive summary &amp; how to submit</h1>
{status}
<h2>Is it safe to download and submit?</h2>
<p><b>Yes — for the current file.</b> <code>{esc(Path(H61O_TIF).name)}</code> is the file the current run card
<code>evidence/run_card.json</code> authorises (<code>okay_to_download: true</code>, <code>okay_to_submit: true</code>):
{H61O_CHECKS}/{H61O_CHECKS_TOTAL} local validator checks pass, the values are inside [0, 1] everywhere (the exact failure mode behind the
reported “Predicted values must be in range [0, 1]” rejection), and the uniqueness verdict is <b>{esc(H61O_REGISTRY['verdict'])}</b>
under the Jaccard-exception gate. Its own holdout result is a negative (HOLDOUT-DTI {H61O_HOLDOUT['value']:.6f} versus
{H61O_HOLDOUT['random_lines_same_budget']:.6f} for random lines and {H61O_RANDOM_DOTS['pooled_dti']:.6f} for random dots), so it is cleared to
submit but not recommended for a weekly slot.</p>
<h2>Download &amp; upload steps (exact)</h2>
<ol>
<li>Download the file: <a class="btn" href="{esc(DOWNLOAD_H61O_TIF)}" download>↓ Download the submission GeoTIFF ({H61O_BYTES:,} bytes)</a>
<a class="btn sec" href="{esc(DOWNLOAD_H61O_ZIP)}" download>ZIP</a>
<a class="btn sec" href="{esc(DOWNLOAD_H61O_RECEIPT)}">Format receipt</a>
<a class="btn sec" href="../evidence/run_card.json">Run card</a>.</li>
<li>Verify SHA-256 <code>{H61O_SHA}</code> (this exact file — do not substitute an older download).</li>
<li>Open the <a href="{COMP}submissions/">official submissions page</a> while logged into the competition account.</li>
<li>Upload the GeoTIFF, set the submission name to <code>{esc(H61O_NAME)}</code> and the note to <code>{esc(H61O_NOTE)}</code>
({current_run_card['note_chars']}/140 characters).</li>
<li>Save the platform receipt; only then label those exact bytes ORGANIZER-CONFIRMED.</li>
</ol>
<h2>What must not be submitted</h2>
<p><b>Audit-only, DO NOT SUBMIT:</b> the archived H61-G file below is a format-valid research artifact whose strict literal overlap is
{H61G_DENSE['my_dots_within_3px_of_theirs']:.4%}. <b>DO NOT SUBMIT</b> it, the archived file under <code>docs/submissions/</code>
(strict literal overlap 99.1475%), or the H61-MH / H61-L / H61-W downloads: none of them is cleared by the Jaccard exception,
which applies only to the H61-O bytes named above. H61-MH's historical HOLDOUT-DTI does not waive its
{h61mh_audit['one_sided_overlap_fraction']:.4%} strict literal stop, and H61-W's run card says <code>okay_to_submit: false</code>.</p>
<p><a class="btn warn" href="{esc(DOWNLOAD_TIF)}" download>Download H61-G diagnostic TIFF — DO NOT SUBMIT</a>
<a class="btn sec" href="{esc(DOWNLOAD_ZIP)}" download>Diagnostic ZIP</a>
<a class="btn sec" href="{esc(DOWNLOAD_RECEIPT)}">Format receipt</a>
<a class="btn sec" href="submissions/61gemsdoe-basement-step-ribbon-20261011T054408Z.tif">Historical TIFF (warning)</a></p>
<p>H61-G SHA-256 <code>{SHA}</code> · historical submission-form note ({fin['note_chars']}/140 chars): <code>{esc(NOTE)}</code>.
That note does not clear the older file.</p>
<h2>Why the “Predicted values must be in range [0,1]” error should not recur</h2>
<p>The competition validator rejects NaN, Inf, negative or &gt;1 values anywhere in the raster. The H61-O file passes
{H61O_CHECKS} checks: single band, float32, EPSG:32611, 3730×3292, the sample-submission transform, no NaN/Inf anywhere,
values in [0,1], 0.0 outside the footprint. These checks establish local formatting and the declared-uniqueness gate — not
organizer acceptance and not a score.</p>
<h2>Provenance of the numbers</h2>
<p>Every number above is HOLDOUT-DTI (evaluator <code>gems61.holdout_segmented v2</code>) or LOQO-DTI, with its CI and withheld-positive count.
No projection is presented as a score, and no organizer score exists yet for any repository artifact.</p>
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
The current-run H61-L top hypothesis was stopped before holdout because its surface failed the strict overlap rule. A separate archived main-branch H61-L variant has historical HOLDOUT-DTI 0.044330 (95% CI [0.041405, 0.047832]; 22,641 withheld positives; evaluator <code>gems61.holdout_segmented v2</code>), but its final TIFF fails strict overlap at 98.6375%. The later archived H61-MH inversion-feature variant recorded {h61mh_holdout['score_label']} {h61mh_holdout['value']:.6f} (95% CI [{h61mh_holdout['95_percent_ci'][0]:.6f}, {h61mh_holdout['95_percent_ci'][1]:.6f}]; {h61mh_holdout['withheld_positive_count']:,} withheld positives; evaluator <code>{esc(h61mh_holdout['evaluator'])}</code>), but its TIFF fails strict overlap at {h61mh_audit['one_sided_overlap_fraction']:.4%}. Neither is eligible for submission.</p>
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
<p>A hypothesis may proceed to holdout only after its pre-placement surface passes the declared-uniqueness gate against every raster in the declared inventory:
signed Spearman &le; 0.90, one-sided 3 px overlap &le; 70 %, with the Jaccard exception (IR-61-UNIQ-01) waived only where the comparator is itself a near-blanket.
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
h61o_hold_rows = []
for row in (H61O_O2, H61O_RANDOM_LINES, H61O_RANDOM_DOTS):
    h61o_hold_rows.append(
        f"<tr><td>{esc(row['name'])} — H61-O session</td><td>{row['n_emitted_per_draw']:,.0f}</td>"
        f"<td>{row['pooled_dti']:.6f}</td><td>[{row['ci95_bootstrap_cells'][0]:.6f}, {row['ci95_bootstrap_cells'][1]:.6f}]</td>"
        f"<td>{row['coverage']:.4f}</td><td>{row['segments_recovered_basin_interior']:,}/{row['segments_withheld_basin_interior']:,} "
        f"({row['basin_recovery_rate']:.1%})</td></tr>")
hold_body = f"""
<h1>Holdout evidence: current H61-O file, legacy H61-G and controls</h1>
<p>All numerical rows below are <b>HOLDOUT-DTI</b> under <code>{esc(hold['evaluator'])}</code>, with
{hold['n_withheld_truth_px']:,} withheld positive pixels, α={hold['alpha']}, β={hold['beta']}, {hold['kernel_m']} m triangular kernel, and the listed 95% CI.
These are proxy scores on withheld catalogue segments, not live organizer scores.</p>
<table><tr><th>Arm</th><th>Positive pixels per draw</th><th>HOLDOUT-DTI</th><th>95% CI</th><th>coverage</th><th>Basin-interior segment recovery</th></tr>
{''.join(h61o_hold_rows)}
{''.join(hold_rows)}</table>
<p>The historical H61-G construction is below the as-published dotted H19-5 reference and is not eligible for a slot. Its strict final-dot uniqueness verdict is
<code>{esc(uni['verdict'])}</code>. The current-run H61-L surface stopped before holdout, so that run has no H61-L HOLDOUT-DTI. A separate archived main-branch H61-L variant was measured at <b>HOLDOUT-DTI 0.044330</b> (95% CI [0.041405, 0.047832]; 22,641 withheld positives; evaluator <code>gems61.holdout_segmented v2</code>), but its final TIFF has 98.6375% strict one-sided overlap and is not eligible for a slot. The archived H61-MH inversion-feature variant measured <b>{h61mh_holdout['score_label']} {h61mh_holdout['value']:.6f}</b> (95% CI [{h61mh_holdout['95_percent_ci'][0]:.6f}, {h61mh_holdout['95_percent_ci'][1]:.6f}]; {h61mh_holdout['withheld_positive_count']:,} withheld positives; evaluator <code>{esc(h61mh_holdout['evaluator'])}</code>) and recovered {h61mh_holdout['basin_interior_segments_recovered']}/{h61mh_holdout['basin_interior_segments_withheld']} basin-interior segments (recovery-rate 95% CI [{h61mh_holdout['basin_interior_recovery_ci95'][0]:.6f}, {h61mh_holdout['basin_interior_recovery_ci95'][1]:.6f}]) versus {h61mh_holdout['basin_interior_random_lines_recovered']}/{h61mh_holdout['basin_interior_random_lines_withheld']} for equal-budget random lines (recovery-rate 95% CI [{h61mh_holdout['basin_interior_random_lines_recovery_ci95'][0]:.6f}, {h61mh_holdout['basin_interior_random_lines_recovery_ci95'][1]:.6f}]), but its TIFF fails the strict gate at {h61mh_audit['one_sided_overlap_fraction']:.4%}. The separate spatially blocked LOQO-DTI logistic mean is 0.039489 (range across four quadrants 0.032545–0.054939; evaluator <code>gems61.holdout_segmented v2</code>, 22,641 withheld positives); the historical receipt reports no 95% CI for this mean or range. Feature-model canary AUC is 0.559341. The archived multi-line comparison is also labelled: 3×3 ribbon HOLDOUT-DTI {H61MH_RIBBON['pooled_dti']:.6f} (95% CI [{H61MH_RIBBON['ci95_bootstrap_cells'][0]:.6f}, {H61MH_RIBBON['ci95_bootstrap_cells'][1]:.6f}]; {h61mh_holdout_source['n_withheld_truth_px']:,} withheld positives; evaluator <code>{esc(h61mh_holdout_source['evaluator'])}</code>; {H61MH_RIBBON['n_emitted_per_draw']:,.0f} emitted pixels/draw) versus dots HOLDOUT-DTI {H61MH_DOTS['pooled_dti']:.6f} (95% CI [{H61MH_DOTS['ci95_bootstrap_cells'][0]:.6f}, {H61MH_DOTS['ci95_bootstrap_cells'][1]:.6f}]; same evaluator/count; {H61MH_DOTS['n_emitted_per_draw']:,.0f} emitted pixels/draw). These are historical diagnostics, not an organizer result or submission clearance.</p>
<p>On the same 1,999 withheld basin-interior segments, historical H61-G recovered {CANDIDATE['segments_recovered_basin_interior']:,} ({CANDIDATE['basin_recovery_rate']:.1%}) versus {RANDOM_LINES['segments_recovered_basin_interior']:,} ({RANDOM_LINES['basin_recovery_rate']:.1%}) for equal-budget random lines. This is proxy recovery, not hidden organizer truth.</p>
<p><b>Current submission file H61-O (variable-density inversion):</b> HOLDOUT-DTI {H61O_O2['pooled_dti']:.6f}
(95% CI [{H61O_O2['ci95_bootstrap_cells'][0]:.6f}, {H61O_O2['ci95_bootstrap_cells'][1]:.6f}]; {H61O_O2['n_emitted_per_draw']:,.0f} emitted pixels/draw;
evaluator <code>gems61.holdout_segmented v2</code>) versus random lines {H61O_RANDOM_LINES['pooled_dti']:.6f} and random dots anywhere
{H61O_RANDOM_DOTS['pooled_dti']:.6f} at the same 40,000-dot budget; basin-interior recovery
{H61O_O2['segments_recovered_basin_interior']:,}/{H61O_O2['segments_withheld_basin_interior']:,} versus
{H61O_RANDOM_LINES['segments_recovered_basin_interior']:,}/{H61O_RANDOM_LINES['segments_withheld_basin_interior']:,} for random lines;
LOQO-DTI mean {h61o_loqo['mean_dti']:.6f} (four quadrants {min(r['loqo_dti'] for r in h61o_loqo['rows']):.6f}–{max(r['loqo_dti'] for r in h61o_loqo['rows']):.6f}).
Format-valid and unique, and an honest negative on the selector's bar.</p>
<p>Feature-alone canary on the historical H61-G holdout: worst AUC {hold['leakage_canary']['worst_auc']:.3f}, threshold 0.90.
The current-run H61-L surface did not reach holdout, so no canary or DTI is claimed for that run. The separate main-branch H61-L variant's historical HOLDOUT-DTI is documented above and does not clear its strict final-dot failure.</p>
"""

# Two irregularity registers. The evidence register carries the measured lane
# findings (IR-61-*); the public data file carries the protocol, calibration and
# history register that main rendered before this merge (IR-1 ... IR-8, IR-2b,
# IR-6b). Both are published, because dropping the second register would lose
# main's standing facts (GP-1012 unobtainable, the linear-slab 0.7318 vs 0.6575
# disagreement, the fold-coverage fix, plateau_fraction 0.5).
irr = load("evidence/h61g_irregularities.json") + load("evidence/h61w_irregularities.json")
irr_lane_rows = "".join(
    f"<tr><td><code>{esc(row['id'])}</code></td><td>{esc(row.get('finding',row.get('statement','')))}</td><td>{esc(row.get('action',''))}</td></tr>"
    for row in irr)
public_irr = load("docs/data/irregularities.json")
public_irr_rows = "".join(
    f"<tr><td><code>{esc(row['id'])}</code></td><td>{esc(row.get('severity',''))}</td>"
    f"<td><b>{esc(row.get('title',''))}</b> — {esc(row.get('detail',''))}</td>"
    f"<td>{esc(row.get('consequence',''))}</td><td>{esc(row.get('status',''))}</td></tr>"
    for row in public_irr)
irr_body = f"""<h1>Irregularities and corrections</h1>
<h2>Measured-lane register ({len(irr)} entries, evidence-sourced)</h2>
<table><tr><th>ID</th><th>Finding</th><th>Action</th></tr>{irr_lane_rows}</table>
<h2>Protocol, calibration and history register ({len(public_irr)} entries, <a href="../docs/data/irregularities.json">public data file</a>)</h2>
<p>These are the standing findings inherited from the merged sessions on <code>main</code>; they are separate from the measured-lane register above
and none of them is a submission clearance. IR-1 explains why the depth scale is calibrated against the supplied band 15 instead of GP-1012;
IR-2 records the linear-slab versus iterative disagreement; IR-7 and IR-8 record the thinning and taper fixes.</p>
<table><tr><th>ID</th><th>Severity</th><th>Finding</th><th>Consequence</th><th>Status</th></tr>{public_irr_rows}</table>"""

next_body = f"""
<h1>Next steps and remaining limitations</h1>
<h2>Decision</h2>
<p><b>H61-O is cleared to download and submit (format-valid + UNIQUE under the Jaccard-exception gate), but its own holdout evidence is a negative, so no weekly slot should be spent on it.</b>
The older H61-G / H61-M / H61-MH / H61-L files fail the strict literal leg, which is registry-degenerate for in-lane dotted candidates (IR-61-UNIQ-01), and H61-W's card says
<code>okay_to_submit: false</code>. No organizer score exists for any repository artifact.</p>
<h2>What would unblock a new candidate</h2>
<ol>
<li>Start from a new in-lane hypothesis and build a pre-placement surface from permitted geological inputs.</li>
<li>Compare that surface against every raster in the declared accessible inventory; stop if positive Spearman &gt;0.90 or if more than 70% of positive pixels are within 3 px of any single prior raster
(the Jaccard exception waives that leg only for a near-blanket comparator, and drift into another lane still stops the run).</li>
<li>Only after a passing surface, run the shared spatially blocked hide-and-recover evaluator, visible-only catalogue features, pixel-exact masking, the feature-alone leakage canary, and a matched random-line control.</li>
<li>Write ribbons, check the final raster with the same strict gate, validate with the shared writer, and promote only if the holdout selector says it beats the holdout best. A weekly slot remains separate.</li>
</ol>
<h2>Limitations</h2>
<ul>
<li>The current index covers {registry['scope']['declared_public_source_count']} paths from <code>scripts/registry_sources.tsv</code> and {registry['scope']['repository_prior_file_count']} TIFFs across local roots ({registry['scope']['total_raster_records']} records); it is not the organizer-side registry. The original H61-G/H61-L run receipts retain their 21+7 pre-merge snapshot.</li>
<li>All {artifact_audit['summary']['candidate_artifacts']} locally published candidate TIFFs exceed the literal final-dot overlap stop against the hash-pinned HGM prior. The archived main-branch "UNIQUE" labels are retired; see <a href="../evidence/local_artifact_strict_dot_audit.json">the measured audit</a>. This short-circuit final-dot audit does not supply missing pre-placement receipts.</li>
<li>The current-run H61-L 3DEP-derived descriptor source is a public repository derivative. Its surface was not holdout-scored. Archived H61-L and H61-MH variants have HOLDOUT-DTI proxy values, but their final TIFFs fail the strict final-dot gate; H61-MH is 99.6400% one-sided overlap.</li>
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

h61o_verify_rows = []
for row in h61o_uniqueness["rows"]:
    gate = "exception waives literal leg" if row.get("overlap_gate_exceeded") else "pass"
    h61o_verify_rows.append(
        f"<tr><td><code>{esc(row['file'])}</code></td><td>{row['spearman_footprint']:+.5f}</td>"
        f"<td>{row['frac_my_dots_within_3px_of_theirs']:.5%}</td><td>{row['jaccard']:.5f}</td>"
        f"<td>{gate}</td></tr>")
verify_body = f"""
<h1>Format and uniqueness verification</h1>
<h2>H61-O submission clearance (current file)</h2>
<p>File <code>{esc(Path(H61O_TIF).name)}</code>, SHA-256 <code>{H61O_SHA}</code>; <b>{H61O_CHECKS}/{H61O_CHECKS_TOTAL} local validator checks pass</b>
(<a href="../evidence/h61o_final.json">final receipt</a>). Uniqueness verdict <b>{esc(h61o_uniqueness['verdict'])}</b> against
{h61o_uniqueness['n_registry_rasters_compared']} registry rasters: worst Spearman {h61o_uniqueness['worst_spearman']['value']:+.5f} (limit {h61o_uniqueness['rho_limit']:.2f}) vs
<code>{esc(Path(h61o_uniqueness['worst_spearman']['file']).name)}</code>; worst one-sided 3 px overlap {h61o_uniqueness['worst_overlap_gate']['value']:.4%}
(limit {h61o_uniqueness['worst_overlap_gate']['limit']:.0%}) vs <code>{esc(Path(h61o_uniqueness['worst_overlap_gate']['file']).name)}</code>.
The literal overlap leg is waived only where the comparator is itself a near-blanket (IR-61-UNIQ-01); no row is byte-identical to any registry raster
(<a href="../evidence/h61o_uniqueness.json">uniqueness receipt</a>).</p>
<table><tr><th>Raster</th><th>Spearman</th><th>Candidate positives within 3 px</th><th>Jaccard (diagnostic)</th><th>Literal leg</th></tr>{''.join(h61o_verify_rows)}</table>
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
<h2>Exact upload procedure for the current cleared file</h2>
<ol>
<li>Confirm <code>evidence/run_card.json</code> names <code>{esc(Path(H61O_TIF).name)}</code> with <code>okay_to_submit: true</code>.</li>
<li>Download that exact file: <a class="btn" href="{esc(DOWNLOAD_H61O_TIF)}" download>↓ Download the submission GeoTIFF ({H61O_BYTES:,} bytes)</a>
<a class="btn sec" href="{esc(DOWNLOAD_H61O_ZIP)}" download>ZIP</a> and verify SHA-256 <code>{H61O_SHA}</code>.</li>
<li>Log in to <a href="{COMP}submissions/">DrivenData submissions</a>.</li>
<li>Upload the GeoTIFF; submission name <code>{esc(H61O_NAME)}</code>; note <code>{esc(H61O_NOTE)}</code>
({current_run_card['note_chars']}/140 characters).</li>
<li>Save the organizer receipt. Only then is a score ORGANIZER-CONFIRMED for those exact bytes.</li>
</ol>
<p><b>Do not submit</b> the older H61-G / H61-M / H61-MH / H61-L / H61-W files or the file under <code>docs/submissions/</code>:
they are NOT CLEARED under the current gates (H61-W carries <code>okay_to_submit: false</code>).</p>
<p>No automatic portal upload was attempted and no competition slot has been used by this repository.</p>
"""

limitations_body = f"""
<h1>Limitations</h1>
<ul>
<li>Uniqueness is a two-tier policy: <b>H61-O is cleared</b> under the Jaccard exception, while all {artifact_audit['summary']['candidate_artifacts']} earlier local candidate TIFFs fail the strict literal leg, which is registry-degenerate for in-lane dotted candidates (IR-61-UNIQ-01). Clearance is not a score, and nothing in this lane has beaten its holdout bar, so no weekly slot is recommended.</li>
<li>Registry coverage is a declared accessible scope ({registry['scope']['declared_public_source_count']} GitHub paths plus {registry['scope']['repository_prior_file_count']} local TIFFs across downloads/submissions/out; total {registry['scope']['total_raster_records']} raster records), not an organizer-side inventory.</li>
<li>The archived H61-MH result is HOLDOUT-DTI {h61mh_holdout['value']:.6f} (95% CI [{h61mh_holdout['95_percent_ci'][0]:.6f}, {h61mh_holdout['95_percent_ci'][1]:.6f}]; {h61mh_holdout['withheld_positive_count']:,} withheld positives; evaluator {esc(h61mh_holdout['evaluator'])}), but its TIFF fails strict one-sided overlap at {h61mh_audit['one_sided_overlap_fraction']:.4%}. It is not a competition score or submission candidate.</li>
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
banner = (f'<div style="border:2px solid #d29922;background:#2a2208;padding:10px 14px;border-radius:8px;margin:12px 0">'
          '<b>HISTORICAL PAGE — SUPERSEDED.</b> Legacy score, “UNIQUE,” or “ready” labels are not current clearance. '
          f'Current status: H61-O is cleared under the Jaccard-exception gate, while the strict audit blocks {artifact_audit["summary"]["strict_overlap_stops"]}/{artifact_audit["summary"]["candidate_artifacts"]} local artifacts. '
          '<a href="index.html">Current status</a> · '
          '<a href="../evidence/local_artifact_strict_dot_audit.json">strict audit</a>. '
          'Do not treat this page as a current submission clearance.</div>')
legacy_banner_pattern = re.compile(
    r'<div style="border:2px solid #d29922;.*?<b>(?:HISTORICAL PAGE|SUPERSEDED PAGE).*?</div>',
    flags=re.IGNORECASE | re.DOTALL,
)
for old in DOCS.glob("*.html"):
    if old.name in pages or old.name in {"404.html"}:
        continue
    text = old.read_text(encoding="utf-8")
    text, count = legacy_banner_pattern.subn(banner, text, count=1)
    if count == 0 and "HISTORICAL PAGE — SUPERSEDED." not in text:
        text = re.sub(r"(<body[^>]*>)", lambda match: match.group(1) + banner, text, count=1,
                      flags=re.IGNORECASE)
    if count or "HISTORICAL PAGE — SUPERSEDED." in text:
        old.write_text(text, encoding="utf-8")

(ROOT / "index.html").write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=docs/index.html"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>61GEMSDOE — H61-O cleared and downloadable</title><link rel="stylesheet" href="docs/assets/site.css"></head><body><main class="wrap">
<h1>61GEMSDOE</h1><p><b>CLEARED — FORMAT-VALID and UNIQUE under the Jaccard-exception gate: H61-O is OK to download and submit.</b></p>
<p>40,000 dots, 133,448 bytes, sha256 34218a18…; its own holdout verdict is negative, so no weekly slot is recommended.
The older H61-G / H61-M / H61-MH / H61-L / H61-W files are NOT CLEARED and must not be uploaded.
<a href="docs/index.html">Open the current status and evidence</a>.</p>
<p><a href="docs/executive-summary.html">Submission safety</a> · <a href="docs/verify.html">Uniqueness verification</a></p>
</main></body></html>""", encoding="utf-8")
# The public JSON mirror of the current card must move with the evidence copy;
# scripts/build_site_h61o_cleared.py wrote it once, and this builder owns every
# page plus that mirror, so the Pages workflow cannot publish a stale card.
(DOCS / "data").mkdir(parents=True, exist_ok=True)
(DOCS / "data" / "run_card.json").write_text(json.dumps(current_run_card, indent=2), encoding="utf-8")
print("status site built:", ", ".join(pages))
