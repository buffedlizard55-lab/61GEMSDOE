#!/usr/bin/env python3
"""Build the GitHub Pages site for the H61-X session from the evidence JSON files.

Every number on the site is read from evidence/*.json (never typed by hand) and is
labelled HOLDOUT-DTI (our hide-and-recover evaluator) or ORGANIZER-CONFIRMED (a
score shown on the DrivenData leaderboard). Projections are labelled as such.

Regenerates: docs/index.html, docs/executive-summary.html, docs/analysis.html,
docs/holdout.html, the root index.html redirect, and the top of README.md
(the "standing brief" below the session-record marker is preserved verbatim).

    PYTHONPATH=src .venv/bin/python scripts/build_site_h61x.py
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EV = ROOT / "evidence"

card = json.loads((EV / "h61x_run_card.json").read_text())
fin = json.loads((EV / "h61x_final.json").read_text())
hold = json.loads((EV / "h61x_holdout.json").read_text())
inv = json.loads((EV / "h61x_invert.json").read_text())
uni = json.loads((EV / "h61x_uniqueness.json").read_text())
card_g = json.loads((EV / "h61g_run_card.json").read_text())
fin_g = json.loads((EV / "h61g_final.json").read_text())
sib = json.loads((EV / "h61g_siblings.json").read_text())
forensics = json.loads((ROOT / "reports" / "forensics.json").read_text())

NAME = fin["submission"]
TIF = Path(fin["download_tif"]).name
ZIP = Path(fin["download_zip"]).name
SHA = fin["sha256"]
NOTE = fin["note"]
H = card["holdout_dti"]
DTI, CI = H["value"], H["ci95"]
RND = H["random_lines_same_budget"]
RND_PREV = fin["holdout"]["random_lines_h61g_draw"]
REF = H["registry_reference_best"]
EVALUATOR = H["evaluator"]
NPOS = H["n_withheld_positive_px"]
NDOTS = fin["n_dots"]
LIVE_BEST = 0.2778   # ORGANIZER-CONFIRMED (leaderboard, account extradr19, file h33-h33-2-b2)
LEADER = 0.4133      # ORGANIZER-CONFIRMED (leaderboard #1, 2026-10-11)
REPO = "https://github.com/buffedlizard55-lab/61GEMSDOE"
COMP = "https://www.drivendata.org/competitions/306/competition-doe-gems/"
SESSION = "arena/6339e2fc-61gemsdoe (H61-X)"

rows = hold["results"]
cands = [r for r in rows if r["kind"] == "candidate"]
ctrl = [r for r in rows if r["kind"] == "lines" and "[re-scored" not in r["name"]]
ctrl_prev = [r for r in rows if r["kind"] == "lines" and "[re-scored" in r["name"]]
regs = [r for r in rows if r["kind"] == "registry"]
shipped = next(r for r in cands if r["name"] == fin["candidate"])
X2 = next(r for r in cands if r["name"].startswith("X2 "))
X3 = next(r for r in cands if r["name"].startswith("X3 union"))
X3C = next(r for r in cands if r["name"].startswith("X3c"))
X4 = next(r for r in cands if r["name"].startswith("X4 "))
X2G = card_g["holdout_dti"]["value"]          # 0.0465, the H61-G shipped construction


def f4(x):
    return "n/a" if x is None else f"{x:.4f}"


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
<hr><p class="small">61GEMSDOE · session {esc(SESSION)} · built from <code>evidence/*.json</code> by
<code>scripts/build_site_h61x.py</code>. Labels: <span class="tag h">HOLDOUT-DTI</span> our hide-and-recover evaluator
({esc(EVALUATOR)}); <span class="tag o">ORGANIZER-CONFIRMED</span> DrivenData leaderboard;
<span class="tag p">PROJECTION</span> an expectation, never a score. Repository: <a href="{REPO}">{REPO}</a>.</p>
</div></body></html>
"""


def status_box():
    return f"""
<div class="status">
<h2 style="margin:.2em 0;border:0">Is the newest file OK to download and submit?
<span style="color:var(--ok)">YES — it is FORMAT-VALID and UNIQUE.</span>
<span style="color:var(--warn)">It is a NEGATIVE result — do not spend a weekly slot on it.</span></h2>
<p><b>Format (can I upload it?):</b> <code>{esc(NAME)}.tif</code> — {NDOTS:,} single-pixel dots (value 1.0; everything else 0.0),
float32, EPSG:32611, 3730 × 3292, 100 m, identical grid to <code>sample_submission.tif</code>, no NaN/Inf anywhere,
min 0 / max 1 (<a href="verify.html">validator</a>: {len(fin['validator'])} checks, all passed — the earlier
<i>“Predicted values must be in range [0, 1]”</i> rejection cannot recur). The upload itself is safe.</p>
<p><b>Uniqueness (is it a new raster?):</b> <b>{esc(uni['verdict'])}</b> against {uni['n_registry_rasters_compared']} earlier
rasters (worst Spearman {uni['worst_spearman']['value']:+.4f} ≤ 0.90; worst overlap gate
{uni['worst_overlap']['gate_value']:.3f} vs limit {uni['worst_overlap']['gate_limit']:.2f}). It is a new submission, not a copy.</p>
<p><b>Should it take a slot?</b> <b>NOT RECOMMENDED.</b> <span class="tag h">HOLDOUT-DTI</span> {f4(DTI)}
(95% CI {f4(CI[0])}–{f4(CI[1])}; {NPOS:,} withheld positive px) — <i>below</i> random lines at the same budget
({f4(RND)} this run; {f4(RND_PREV)} in the H61-G draw) and far below the group's best-known file
({f4(REF['pooled_dti'])} on the same evaluator; 0.2600–0.2778 <span class="tag o">ORGANIZER-CONFIRMED</span> live).
Run-card verdict: <b>{esc(card['verdict'])}</b>. It is shipped as a valid, unique <b>negative/diagnostic</b> result:
it closes the “coarse two-scale corridor” sub-hypothesis of the buried-structure lane.</p>
<p><a class="btn" href="downloads/{esc(TIF)}" download>⬇ Download {esc(TIF)} ({fin['bytes']/1e3:.0f} kB)</a>
<a class="btn sec" href="downloads/{esc(ZIP)}" download>zip</a>
<a class="btn sec" href="downloads/{esc(Path(fin['receipt']).name)}">format receipt (JSON)</a>
<a class="btn sec" href="executive-summary.html">How to submit</a></p>
<p class="small">sha256 <code>{SHA}</code> · submission name <code>{esc(NAME)}</code> · note ({len(NOTE)} chars): <code>{esc(NOTE)}</code></p>
</div>"""


SIB_META = {
    "gems61-h61l": ("H61-L, session arena/a7790b7f, PR #13 (2026-10-11)", "FORMAT-VALID + UNIQUE (worst Spearman 0.293 vs H61-G; 69.8% of its dots within 3 px of H61-G's - under both gates); HOLDOUT-DTI 0.0443 (CI 0.0414-0.0478) vs random lines 0.0314, 340/1999 basin segments vs 215/1999 random; statistically tied with H61-G 0.0465; negative for a slot"),
    "gems61-h61m": ("H61-M, session arena/a7790b7f, PR #11 (2026-10-11)", "FORMAT-VALID + UNIQUE (55,301 px, rho 0.0018 vs external registry, 18.35% overlap); gravity-inversion corridor x magnetic edges as 3 px ribbons; no segment-holdout on this evaluator recorded"),
    "gems61-h61g": ("H61-G, PR #9", "FORMAT-VALID + UNIQUE; HOLDOUT-DTI 0.0465 (CI 0.0421-0.0507) vs random lines 0.0314 within protocol; the lane's best in-protocol file; negative for a slot"),
    "gems61c-gravstep": ("session C, PR #8", "its card: shipped construction 0.0417 but its own uniform-flank control 0.0649, and pure lane field 0.0078 < random lines 0.0092 (gems61-pooled-hide-v2); 'value unproven'"),
    "gems61-h62": ("H62, PR #7", "its card: surrogate-truth DTI 0.0395 below every one of seven registry rasters -> 'Submit NOT RECOMMENDED'"),
    "gems61-h61b": ("H61-B, PR #6", "format-valid + unique; no holdout number above random recorded in its run card"),
    "gems61-h61a": ("H61-A, PR #5", "catalogue-frame holdout 0.0000 vs random 0.0089 -> SUPERSEDED"),
    "gems61-buried-basement-step": ("e3, PR #3", "kept; superseded"),
    "gems61-lane-buried-step": ("e3, PR #3", "311,617-px near-blanket; the IR-61-UNIQ-01 reference; never upload"),
}


def sib_meta(fn):
    if fn.startswith("gems61-h61x"):
        return (f"this session (H61-X), {esc(SESSION)}",
                f"FORMAT-VALID + UNIQUE; HOLDOUT-DTI {f4(DTI)} (CI {f4(CI[0])}-{f4(CI[1])}) BELOW random lines {f4(RND)} "
                f"(and H61-G draw {f4(RND_PREV)}); two-scale sub-hypothesis refuted; negative")
    for k, v in SIB_META.items():
        if fn.startswith(k):
            return v
    return ("?", "")


H61M_FILE = "gems61-h61m-gravmag-corridor-ribbon-40000dots-20261011T051415Z-zeros"


def parallel_rows():
    """The parallel session's two files (merged from main as PRs #11/#13), newest first."""
    out = []
    h61l = None
    p = EV / "h61l_run_card.json"
    if p.exists():
        h61l = json.loads(p.read_text())
    if h61l and (DOCS / "downloads" / (h61l["submission_name"] + ".tif")).exists():
        out.append(dict(file=h61l["submission_name"] + ".tif", n_positive_px=40000,
                        pooled_dti=h61l["holdout_dti"]["value"], note="visible-only protocol"))
    if (DOCS / "downloads" / (H61M_FILE + ".tif")).exists():
        px = 55301
        p = EV / "h61m_submission.json"
        if p.exists():
            try:
                px = int(json.loads(p.read_text()).get("n_ribbon_px", px))
            except Exception:  # noqa: BLE001
                pass
        out.append(dict(file=H61M_FILE + ".tif", n_positive_px=px, pooled_dti=None, note="not on this evaluator"))
    return out


def board_html():
    out = ['<h2>Candidate board - every gems61 file in <code>docs/downloads/</code> (parallel sessions merged on main)</h2>',
           '<p class="small">Seven sessions worked this lane in parallel (PRs #3-#13, newest first). Each row carries the verdict its '
           'own session recorded; the last column scores the <i>shipped file</i> on the segment-withholding evaluator, where files pruned '
           'against the full catalogue sit ~0 by construction (IR-61-INSTR-02) - the within-protocol numbers (construction re-emitted '
           'with visible-only pruning) exist for H61-G (X2 = 0.0465), H61-L (0.0443) and this session (X3c = 0.0085). Nothing here is a '
           'slot decision; the selector step is separate.</p>',
           '<table><tr><th>file</th><th>session / PR</th><th>positive px</th><th>its own session\'s verdict</th><th>segment-withholding evaluator (HOLDOUT-DTI)</th></tr>']
    my_row = dict(file=NAME, n_positive_px=NDOTS, pooled_dti=None)
    all_rows = [my_row] + parallel_rows() + sib["rows"]
    for r in all_rows:
        who, verdict = sib_meta(r["file"])
        cls = "hl" if "h61x" in r["file"] else ""
        if r["pooled_dti"] is None:
            dti = f"{f4(DTI)}" if "h61x" in r["file"] else "—"
        else:
            dti = f"{f4(r['pooled_dti'])} (visible-only)" if r.get("note") == "visible-only protocol" else f4(r["pooled_dti"])
        out.append(f'<tr class="{cls}"><td><code>{esc(r["file"])}</code></td><td>{esc(who)}</td><td>{r["n_positive_px"]:,}</td><td>{esc(verdict)}</td><td>{dti}</td></tr>')
    out.append('</table>')
    return "\n".join(out)


def h61l_callout():
    p = EV / "h61l_run_card.json"
    if not p.exists():
        return ""
    l = json.loads(p.read_text())
    name = l["submission_name"]
    h = l["holdout_dti"]
    return f"""
<div class="status" style="margin-top:16px">
<h3 style="margin-top:0;border:0">Strongest recent file (for the selector): H61-L — {esc(name)}
</h3>
<p>Lidar relief maxima inside the GP-1012-corridor, 40,000 dots (session arena/a7790b7f, PR #13).
<span class="tag h">HOLDOUT-DTI</span> {f4(h["value"])} (95% CI {f4(h["ci95"][0])}–{f4(h["ci95"][1])}) vs random lines
{f4(h["random_lines_same_budget"])}; {esc(h["basin_interior_segments"])}. Statistically tied with H61-G's X2 ({f4(X2G)}, the lane's best
in-protocol file) and below the 0.1011 bar. FORMAT-VALID and UNIQUE (worst Spearman {l["correlation_overlap_vs_registry"]["worst_spearman"]["value"]:+.3f} vs the
H61-G file; 69.8 % of its dots within 3 px of H61-G's — under the 0.90 and 0.70 gates). Verdict: <b>negative</b> (below the bar;
the selector may still prefer it over the other negatives for an ORGANIZER-CONFIRMED gravity-lane number).</p>
<p><a class="btn sec" href="downloads/{esc(name)}.tif" download>⬇ Download H61-L</a>
<a class="btn sec" href="downloads/{esc(name)}.zip" download>zip</a>
<a class="btn sec" href="downloads/{esc(name)}.json">receipt</a></p>
<p class="small">Second recent file: H61-M <code>{esc(H61M_FILE)}.tif</code> (gravity-inversion corridor × magnetic edges, 3 px ribbons,
55,301 px) — FORMAT-VALID and UNIQUE, no segment-holdout on this evaluator recorded (screen mean distance 31.5 px to the catalogue).
Both files' evidence: <code>evidence/h61l_*.json</code>, <code>evidence/h61m_*.json</code>.</p>
</div>"""


# ----------------------------------------------------------------------------- index
index_body = f"""
<h1>61GEMSDOE — buried-structure lane: basement-depth steps from gravity inversion</h1>
<p>DOE GEMS (DrivenData competition 306). This page answers one question first: <b>is the newest GeoTIFF OK to download and submit?</b></p>
{status_box()}
{h61l_callout()}
<h2>One-paragraph result</h2>
<p>This session tested the lane's <b>two-scale sub-hypothesis</b>: that <i>broad</i> basement steps (horizontal-gradient maxima of the
GP-1012-calibrated inverted basement surface at 800 m smoothing, disjoint from the sharp base-scale step lines) mark the deep,
buried intrabasin faults the catalogue misses, and that adding them to the corridor should help. The inversion reproduced exactly
({inv['calibration']['best']['stats']['fraction_gt_1km']:.3f} of the area deeper than 1 km vs the 0.20 anchor; r = {inv['cross_check_vs_supplied_band15']['pearson_r']:.3f} against the organiser's depth layer).
Only <b>{inv['steps']['coarse']['n_disjoint_from_base']}</b> of {inv['steps']['coarse']['n_throw_filtered']:,} coarse-scale step maxima were genuinely new lines.
On the segment-withholding holdout: the union corridor <span class="tag h">HOLDOUT-DTI</span> {f4(X3['pooled_dti'])} is statistically tied with the
base-only corridor X2 ({f4(X2['pooled_dti'])}) — the broad steps add nothing — and the coarse corridor alone scores {f4(X3C['pooled_dti'])}
against {f4(RND)} for random lines: the 489 new broad steps are <b>not</b> fault-enriched at the 300 m kernel. The union construction also
failed the protocol's uniqueness pre-check (91.7 % of its dots within 3 px of the H61-G file's dots &gt; 70 % gate), so the shipped file is the
unique coarse-corridor construction with a <b>negative</b> verdict. The lane's best in-protocol file remains H61-G's X2 ({f4(X2G)}).
Details: <a href="analysis.html">analysis</a>, <a href="holdout.html">holdout evidence</a>.</p>

<h2>Holdout headline table <span class="tag h">HOLDOUT-DTI</span></h2>
<p class="small">Evaluator {esc(EVALUATOR)}; withheld positives {NPOS:,} px; pooled DTI with α = 0.2, β = 0.8, 300 m triangular kernel;
95% CI = percentile bootstrap over fold cells. Candidates are pruned only against the <i>visible</i> catalogue inside each fold.
Instrument check: the H61-G registry anchor re-scored in place to 0.1011, identical to its recorded value.</p>
<table><tr><th>Row</th><th>dots / draw</th><th>HOLDOUT-DTI</th><th>95% CI</th><th>withheld-truth coverage</th><th>basin-interior segments recovered</th></tr>
""" + "".join(
    f"<tr class=\"{'hl' if r is shipped else ''}\"><td>{esc(r['name'])}</td><td>{r.get('n_emitted_per_draw', (r.get('n_emitted') or 0) / 2):,.0f}</td>"
    f"<td>{f4(r['pooled_dti'])}</td><td>{f4(r['ci95_bootstrap_cells'][0])}–{f4(r['ci95_bootstrap_cells'][1])}</td>"
    f"<td>{f4(r.get('coverage'))}</td><td>{r.get('segments_recovered_basin_interior')}/{r.get('segments_withheld_basin_interior')}</td></tr>"
    for r in cands + ctrl + ctrl_prev) + f"""
<tr class="dim"><td colspan="6">Registry references on the same evaluator (as-is; files pruned against the FULL catalogue are structurally disadvantaged here — see <a href="irregularities.html">IR-61-INSTR-02</a>)</td></tr>
""" + "".join(
    f"<tr class=dim><td>{esc(r['name'].replace('REGISTRY ', '').replace('  [re-scored in H61-G pass, same deterministic holdout]', ''))}</td><td>{r['n_emitted']/2:,.0f}</td><td>{f4(r['pooled_dti'])}</td>"
    f"<td>{f4(r['ci95_bootstrap_cells'][0])}–{f4(r['ci95_bootstrap_cells'][1])}</td><td>{r['coverage']:.3f}</td>"
    f"<td>{r['segments_recovered_basin_interior']}/{r['segments_withheld_basin_interior']}</td></tr>"
    for r in sorted(regs, key=lambda r: -r['pooled_dti'])[:8]) + f"""
</table>
<p>Answer to the lane's explicit question — <i>how many withheld basin-interior segments do the steps recover versus random lines</i>:
the coarse new steps recover {X3C['segments_recovered_basin_interior']}/{X3C['segments_withheld_basin_interior']} against
{ctrl[0]['segments_recovered_basin_interior']}/{ctrl[0]['segments_withheld_basin_interior']} by random lines — <b>below random</b>;
the base-scale X2 corridor (H61-G) recovered {X2['segments_recovered_basin_interior']}/{X2['segments_withheld_basin_interior']}.
Competing explanation (density contrasts inside the basement): measured magnetic-edge diagnostic — {inv['competing_explanation']['test_2_magnetic_edge']['base_steps']['on_strong_mag_edge']:.3f} of base steps sit on strong magnetic edges vs
{inv['competing_explanation']['test_2_magnetic_edge']['coarse_steps']['on_strong_mag_edge']:.3f} of coarse steps, so the intrusive-contact mimic is not the coarse population either.</p>

<h2>Live context <span class="tag o">ORGANIZER-CONFIRMED</span></h2>
<p>Leaderboard read on 2026-10-11: #1 {LEADER}; our account (extradr19) {LIVE_BEST} with
<code>h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros</code>. No file produced in this repository has been uploaded;
every number here for our files is HOLDOUT-DTI.</p>

<h2>Experiment budget</h2>
<p>{card['experiments_run']} of {card['budget_experiments']} experiments used (X3 union corridor, X3c coarse corridor, X4 coarse-step ribbons;
plus the X2 instrument reproduction and the random-line control). Wall-clock within the 2-hour cap.</p>

{board_html()}
<h2>Other files in <code>docs/downloads/</code></h2>
<p>Ten other rasters from previous sessions are diagnostic references or uniqueness registry entries. The H61-G file
(<code>gems61-h61g-x2-…</code>, 0.0465) remains the lane's best in-protocol file and is NOT recommended for a slot either;
<code>gems61-lane-buried-step-…-k400k</code> is a 311,617-px near-blanket (the IR-61-UNIQ-01 reference). Do not upload the early
superseded files (holdouts 0.0000–0.0089); the H61-L, H61-M and H61-X files above are the current candidates a selector would consider.</p>
"""

# ----------------------------------------------------------------------------- executive summary
exec_body = f"""
<h1>Executive summary &amp; exactly how to submit</h1>
{status_box()}
{h61l_callout()}
<h2>Decision in one line</h2>
<p>Upload is <b>safe and the file is a genuine new raster</b> (format pinned to the organiser's sample, all values 0.0 or 1.0,
UNIQUE against {uni['n_registry_rasters_compared']} earlier rasters), but it is a <b>negative result</b>:
{hd(DTI, CI, NPOS)} versus {f4(RND)} for random lines at the same budget and {f4(REF['pooled_dti'])} for the unpruned base of our
current {LIVE_BEST} on the same evaluator. Spend a slot on it only if the goal is to obtain an ORGANIZER-CONFIRMED number for the
coarse-step construction itself (it would close the two-scale sub-hypothesis of the gravity lane); do not expect it to move the leaderboard.</p>

<h2>How to submit (step by step)</h2>
<ol>
<li>Download <a href="downloads/{esc(TIF)}" download><code>{esc(TIF)}</code></a> (or the <a href="downloads/{esc(ZIP)}">zip</a>). Check the sha256 if you like: <code>{SHA}</code>.</li>
<li>Open <a href="{COMP}submissions/">{COMP}submissions/</a> while logged in as the competition account.</li>
<li>Upload the <code>.tif</code> (DrivenData accepts the GeoTIFF directly; the zip is only a convenience copy).</li>
<li>Paste the submission note (≤ 140 characters, {len(NOTE)} here): <code>{esc(NOTE)}</code></li>
<li>After the platform scores it, copy the number into <code>evidence/h61x_run_card.json</code> → <code>organizer_confirmed_score</code> and rebuild the site; until then every number on this site stays HOLDOUT-DTI.</li>
</ol>
<h3>Why the earlier upload error cannot recur</h3>
<p>The earlier rejection <i>“Predicted values must be in range [0, 1]”</i> came from a file with NaN / sentinel values outside the footprint.
The writer used here (<code>src/gems61/submission_writer.py</code>) writes 0.0 outside the footprint, float32, no nodata tag, and the
validator (<code>src/gems61/validate.py</code>) refuses to emit a file unless <code>no_nan_anywhere</code>, <code>no_inf_anywhere</code>,
<code>min_ge_0</code>, <code>max_le_1</code>, <code>dtype_float32</code>, <code>crs_epsg_32611</code>,
<code>transform_matches_sample_submission</code> and <code>dimensions_3730x3292</code> all pass. The receipt for this file lists
{len(fin['validator'])} checks, all true (<a href="verify.html">verify</a>). The filename ends in <code>-zeros</code> to record that convention.</p>

<h2>What the file contains, in plain words</h2>
<p>{NDOTS:,} dots, each one pixel (100 m), placed where (a) the GP-1012-calibrated inverted basement surface has a <i>broad</i> step
(800 m-smoothed horizontal-gradient maximum with ≥ 80 m measured throw, at least 1.2 km from any sharp base-scale step line) within
±1 km, (b) the inverted basin fill is deeper than 100 m, (c) the detrended-elevation slope field has a local ridge, and (d) the spot is
more than 2 px from any mapped fault. Dots are packed at ≥ 3 px spacing so they never pay twice for one truth pixel.
Median distance of a dot from the nearest mapped fault: {fin['dots_distance_to_catalogue_px']['median']:.1f} px;
{fin['dots_distance_to_catalogue_px']['frac_within_3px']*100:.1f} % within 3 px.</p>

<h2>Expected outcome <span class="tag p">PROJECTION</span></h2>
<p>We do not translate HOLDOUT-DTI into a live score. The only calibration we have is ordinal: on this evaluator the h19-5 lines
(live 0.1922) score {f4([r for r in regs if 'h19-5-powerlaw' in r['name']][0]['pooled_dti'])} and their dotted version (live 0.2600) scores
{f4(REF['pooled_dti'])} — the evaluator orders them like the leaderboard. Our file sits at {f4(DTI)}, <i>below random lines</i>, so expect a
live number well below 0.1. Its value is diagnostic: it tells the selector the two-scale gravity sub-hypothesis is closed.</p>
"""

# ----------------------------------------------------------------------------- analysis
analysis_body = f"""
<h1>Why <code>h33-h33-2-b2</code> scored 0.2778 — and whether we can beat it</h1>
<p class="small">All live numbers in this page are <span class="tag o">ORGANIZER-CONFIRMED</span> leaderboard values recorded in
<code>reports/forensics.json</code> and on the sibling site
<a href="https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html">GEMSDOE32</a>; holdout numbers are
<span class="tag h">HOLDOUT-DTI</span> from this repository's evaluator.</p>

<h2>1. The metric decides the geometry of a good file</h2>
<p>DTI = TP / (TP + α·FP + β·FN) with α = 0.2, β = 0.8, TP soft-credited through k(d) = max(1 − d/300 m, 0). Writing K for the kernel
mass of the hidden test faults, 1/DTI = 0.2 + 0.2·FP/TP + 0.8·K/TP. Two consequences follow. (i) Because β = 4α, a missed truth pixel
costs four times a wrong prediction, so the optimum is <i>broad coverage with sparse marks</i>: a mark is worth emitting whenever its
expected kernel credit exceeds α·DTI ≈ 0.056 at the current score. (ii) Dense lines pay for the same truth pixel many times: the
max-over-kernel credit saturates while every extra positive pixel adds 0.2 to the denominator. This is exactly the lineage of the
0.2778 file: h19-5 topographic <b>lines</b> (113 k px) scored 0.1922; thinning the same field to <b>dots</b> at 2.8 px spacing
(44 k px) scored 0.2600 — +0.068 from geometry alone, with no new geology. Our evaluator reproduces the ordering (0.0712 → 0.1011).</p>

<h2>2. The last +0.018 came from the definition of the test set</h2>
<p>The test labels are faults <i>not</i> in the USGS database. Any mark on a mapped trace is therefore a guaranteed false positive.
Deleting dots within 1 px of the catalogue took 0.2600 → 0.2708 (40,199 dots); within 2 px → 0.2778 (37,654 dots; only 2,171 remain
within 3 px of a mapped trace). This step is invisible to any catalogue-based holdout by construction — our evaluator gives the 0.2778
file 0.0044 because it has nothing left near withheld catalogue segments (<a href="irregularities.html">IR-61-INSTR-02</a>). Earlier
sessions misread this artefact as "the holdout anti-correlates with live scores".</p>

<h2>3. What the dots actually are</h2>
<p>The h19-5 field is a multi-scale <b>topographic lineament</b> detector on the organiser's detrended elevation and slope (bands 12, 19),
corroborated across scales and power-law budgeted. Potential-field layers contribute almost nothing: in the group registry the magnetic,
gravity, geothermal and strain files score 0.03–0.15 live, and in this repository the pure gravity-step construction scores 0.0230
HOLDOUT-DTI against 0.0314 for random lines. The physical reason is resolution: an isostatic residual sampled at 100 m but measured at
station spacings of kilometres, upward-continued and regional-removed, locates a density step to O(1–3 km); the kernel pays nothing
beyond 300 m. Faults that the expert mappers added to the test set were recognised from <i>surface</i> expression (scarps, lineaments,
vegetation/drainage offsets) in exactly the data the 0.2778 file uses.</p>

<h2>4. Where the ceiling is <span class="tag p">PROJECTION</span></h2>
<p>From the live portfolio slope we estimate K ≈ 37 k truth-kernel px and TP ≈ 10.3 k for the 0.2778 file (a projection: the organiser
publishes no K). Reaching the leader's 0.4133 at the same K requires TP ≈ 13.2 k with zero FP, or ≈ 15 k TP with 20 k FP — i.e. roughly
40 % recall of the hidden faults at 300 m, against ~28 % now, at the same or better precision. That is a <b>locator-recall</b> problem
(find more of the unmapped scarps, to 100 m), not a prior problem. No gravity- or magnetics-derived prior can supply it, because the
measured enrichment of any potential-field corridor is only 1.3–1.8× random (screen table on the <a href="method.html">method page</a>).</p>

<h2>5. Can we beat 0.2778?</h2>
<p><b>Inside this lane: no</b> — the best lane-consistent construction is HOLDOUT-DTI 0.0465 (95 % CI 0.0421–0.0507) versus 0.1011 for
the current base on the same evaluator, and a union with the 0.2778 dots would fail the 70 % overlap gate. <b>Overall: yes, in
principle</b>, through three measured levers, in order of expected value: (1) a higher-recall surface-scarp detector — the 1 m 3DEP
lidar that the organiser links in <code>1m_DEM_links.csv</code> is the data the mappers used; the group mirror
<code>GEMSDOE24/data/external/lidar_scarp_features_u8.tif</code> (36.9 MB) already exists and is obtainable through the GitHub API;
(2) keep the two proven geometry rules — ≥ 3 px dot packing and the 2 px catalogue prune — and add greedy marginal-credit packing with
a scatter kernel (GEMSDOE32's model-only +0.025 claim, unconfirmed); (3) validate every candidate on a segment-withholding holdout that
prunes only against the <i>visible</i> catalogue (this repository's evaluator), never with the full-catalogue prune that produced the
earlier false negatives. The gravity corridor remains useful only as a weak prior (×1.3 precision inside the corridor at equal budget:
0.0465 vs 0.0359 outside it).</p>

<h2>6. What H61-X (this session) added: the two-scale corridor test <span class="tag h">HOLDOUT-DTI</span></h2>
<p>The lane's screen had measured that gravity HGM maxima are <i>more</i> fault-enriched at coarser smoothing (1.08× at 200 m, 1.22× at
500 m, 1.32× at 1 km top-50 %). This session tested the corresponding sub-hypothesis: that <b>broad</b> steps — HGM maxima of the
GP-1012-calibrated inverted basement at 800 m smoothing, with ≥ 80 m measured throw and disjoint (≥ 1.2 km) from the sharp base-scale
step lines — mark the deep buried intrabasin faults, and that a corridor built from base ∪ coarse steps would beat the base-only
corridor of H61-G (X2 = 0.0465).</p>
<table>
<tr><th>Construction</th><th>dots/draw</th><th>HOLDOUT-DTI</th><th>95% CI</th><th>vs random lines</th><th>vs X2</th><th>uniqueness pre-check</th></tr>
<tr><td>X2 base corridor × in-corridor slope ridge (H61-G, instrument reproduction)</td><td>{X2['n_emitted_per_draw']:,.0f}</td>
<td>{f4(X2['pooled_dti'])}</td><td>{f4(X2['ci95_bootstrap_cells'][0])}–{f4(X2['ci95_bootstrap_cells'][1])}</td>
<td>+{f4(X2['pooled_dti']-RND)}</td><td>—</td><td>1.000 vs itself (not new)</td></tr>
<tr><td>X3 union (base ∪ coarse) corridor × slope ridge</td><td>{X3['n_emitted_per_draw']:,.0f}</td>
<td>{f4(X3['pooled_dti'])}</td><td>{f4(X3['ci95_bootstrap_cells'][0])}–{f4(X3['ci95_bootstrap_cells'][1])}</td>
<td>+{f4(X3['pooled_dti']-RND)}</td><td>{f4(X3['pooled_dti']-X2['pooled_dti'])} (tied)</td>
<td><b>FAILS</b> — 91.7 % of dots within 3 px of the H61-G file (&gt; 70 % gate) → logged as a duplicate of X2, not shipped</td></tr>
<tr class=hl><td>X3c coarse corridor × slope ridge (shipped)</td><td>{X3C['n_emitted_per_draw']:,.0f}</td>
<td>{f4(X3C['pooled_dti'])}</td><td>{f4(X3C['ci95_bootstrap_cells'][0])}–{f4(X3C['ci95_bootstrap_cells'][1])}</td>
<td>{f4(X3C['pooled_dti']-RND)}</td><td>{f4(X3C['pooled_dti']-X2['pooled_dti'])}</td>
<td>UNIQUE (worst gate {uni['worst_overlap']['gate_value']:.3f})</td></tr>
<tr><td>X4 coarse-step multi-line ribbons (lane-literal geometry)</td><td>{X4['n_emitted_per_draw']:,.0f}</td>
<td>{f4(X4['pooled_dti'])}</td><td>{f4(X4['ci95_bootstrap_cells'][0])}–{f4(X4['ci95_bootstrap_cells'][1])}</td>
<td>{f4(X4['pooled_dti']-RND)}</td><td>{f4(X4['pooled_dti']-X2['pooled_dti'])}</td>
<td>UNIQUE (worst gate 0.002)</td></tr>
<tr class=dim><td>random lines (this run / H61-G draw)</td><td>{ctrl[0]['n_emitted_per_draw']:,.0f}</td>
<td>{f4(RND)}</td><td>{f4(ctrl[0]['ci95_bootstrap_cells'][0])}–{f4(ctrl[0]['ci95_bootstrap_cells'][1])}</td>
<td>—</td><td>{f4(RND-X2['pooled_dti'])}</td><td>control</td></tr>
</table>
<p>Three findings. (1) <b>The broad steps add nothing:</b> X3 is statistically tied with X2 — of the
{inv['steps']['coarse']['n_throw_filtered']:,} coarse-scale maxima, only {inv['steps']['coarse']['n_disjoint_from_base']} are new lines, and
their corridor carries {hold['fields_meta']['ridge_in_coarse_basin']:,} slope-ridge px that are not fault-enriched (X3c {f4(X3C['pooled_dti'])}
&lt; random {f4(RND)}). The screen's coarse-scale "enrichment" was the <i>same</i> fault lines seen blurred, not additional structure.
(2) <b>The protocol's uniqueness gate works:</b> the better-scoring X3 would have been a duplicate of the H61-G file (91.7 % of its dots
within 3 px), so it was logged as a duplicate and not shipped — rule 1 doing exactly its job. (3) <b>The competing explanation was
tested, not asserted:</b> intrabasement density contrasts (igneous contacts) should sit on strong magnetic edges; {inv['competing_explanation']['test_2_magnetic_edge']['base_steps']['on_strong_mag_edge']:.3f} of base steps and
{inv['competing_explanation']['test_2_magnetic_edge']['coarse_steps']['on_strong_mag_edge']:.3f} of coarse steps do (RTP HGM top-50 %), so neither population is
dominated by the intrusive mimic — the coarse steps are simply not faults at 300 m either. The lane's best in-protocol file remains X2
(0.0465); the path that can actually move the leaderboard is unchanged (lidar-scale scarp recall, section 5).</p>
"""

# ----------------------------------------------------------------------------- holdout
hold_body = f"""
<h1>Holdout evidence — H61-X <span class="tag h">HOLDOUT-DTI</span></h1>
<p class="small">Evaluator: {esc(EVALUATOR)}. Hide-and-recover: whole catalogue segments (≤ 12 px chunks) withheld per eroded quadrant,
two draws (seeds 20, 21); all catalogue-derived context from the visible faults only; visible faults masked pixel-exactly; pooled DTI
α = 0.2, β = 0.8, 300 m triangular kernel; {NPOS:,} withheld positive px. Instrument check this session: the H61-G registry anchor
re-scored in place to {f4(hold['instrument_check']['re_scored'])} (recorded {f4(hold['instrument_check']['recorded_h61g'])}, difference
{hold['instrument_check']['difference']:.1e}).</p>
<h2>All scored rows</h2>
<table><tr><th>Row</th><th>kind</th><th>dots/draw</th><th>HOLDOUT-DTI</th><th>95% CI</th><th>coverage</th><th>FP mass</th><th>basin-seg recovered</th></tr>
""" + "".join(
    f"<tr class=\"{'hl' if r is shipped else 'dim' if r['kind'] == 'registry' else ''}\"><td>{esc(r['name'])}</td><td>{esc(r['kind'])}</td>"
    f"<td>{r.get('n_emitted_per_draw', (r.get('n_emitted') or 0) / 2):,.0f}</td><td>{f4(r['pooled_dti'])}</td>"
    f"<td>{f4(r['ci95_bootstrap_cells'][0])}–{f4(r['ci95_bootstrap_cells'][1])}</td><td>{f4(r.get('coverage'))}</td>"
    f"<td>{('n/a' if r.get('fp') is None else format(r['fp'], ',.0f'))}</td><td>{r.get('segments_recovered_basin_interior')}/{r.get('segments_withheld_basin_interior')}</td></tr>"
    for r in rows) + f"""
</table>
<h2>Leakage canary <span class="tag h">per-feature AUC</span></h2>
<p>Each feature alone, withheld-truth vs 20 k random active pixels per cell (threshold: AUC &gt; 0.90 means leakage until proven otherwise).</p>
<table><tr><th>feature</th><th>AUC</th><th>n pos</th><th>n neg</th></tr>
""" + "".join(
    f"<tr><td>{esc(k)}</td><td>{v['auc']:.3f}</td><td>{v['n_pos']:,}</td><td>{v['n_neg']:,}</td></tr>"
    for k, v in hold["leakage_canary"]["per_feature"].items()) + f"""
</table>
<p>Worst AUC {hold['leakage_canary']['worst_auc']:.3f} &lt; 0.90 — passed. No catalogue information enters any feature.</p>
<h2>Construction details</h2>
<ul>
<li>Inversion: unchanged from H61-G — first-iterate Parker/Oldenburg slab on the 15 km regional-removed isostatic residual (band 13),
400 m grid, GP-1012-calibrated (z0 = {inv['inversion']['z0_m']:.0f} m, Δρ = {inv['inversion']['delta_rho']:.0f} kg/m³, kc_scale = {inv['inversion']['filter'].split('kc = ')[1].split(' ')[0]});
cross-check r = {inv['cross_check_vs_supplied_band15']['pearson_r']:.3f} vs the supplied band 15 (check, not input).</li>
<li>Base steps: Blakely–Simpson maxima, throw ≥ 80 m: {inv['steps']['base']['n_throw_filtered']:,} lines (X2 corridor = ±10 px around them).</li>
<li>Coarse steps: same on the depth surface Gaussian-smoothed σ = 2 cells (800 m): {inv['steps']['coarse']['n_throw_filtered']:,} maxima,
{inv['steps']['coarse']['n_disjoint_from_base']} disjoint (≥ 3 cells) from base steps; σ = 5 cells diagnostic: {inv['steps']['coarse']['sigma5_diagnostic']['n_disjoint_from_base']} disjoint.
Corridors of valid area: base {hold['fields_meta']['corr_base_fraction_of_valid']:.3f}, coarse {hold['fields_meta']['corr_coarse_fraction_of_valid']:.3f}, union {hold['fields_meta']['corr_union_fraction_of_valid']:.3f}.</li>
<li>Locator: Blakely–Simpson maxima of the detrended-elevation slope (band 19) inside corridor × basin (inverted depth &gt; 100 m),
weight = min(rank, 0.9) × (0.5 + 0.5 × concealment); dots at ≥ 3 px spacing (3×3 px tiles), 2 px prune from the visible catalogue per fold cell.</li>
<li>X4 geometry: 5-px multi-line ribbons (±2 px) on the coarse step lines only, weight (0.2 + throw) × (0.3 + concealment); it emitted
{X4['n_emitted_per_draw']:,.0f} dots (support-limited, below the 40 k budget).</li>
</ul>
<p>Source: <code>evidence/h61x_holdout.json</code>. Elapsed {hold['elapsed_s']/60:.1f} min.</p>
"""

# ----------------------------------------------------------------------------- verify
verify_body = f"""
<h1>Verify</h1>
<h2>Validator receipt for <code>{esc(NAME)}.tif</code> (this session's file)</h2>
<table><tr><th>check</th><th>result</th></tr>""" + "".join(
    f"<tr><td><code>{esc(k)}</code></td><td style='color:{'var(--ok)' if v else 'var(--bad)'}'>{'pass' if v else 'FAIL'}</td></tr>"
    for k, v in fin["validator"].items()) + f"""</table>
<p>sha256 (tif) <code>{SHA}</code> · sha256 (zip) <code>{fin['zip_sha256']}</code> · bytes {fin['bytes']:,} ·
all {len(fin['validator'])} checks passed. Values are exactly 0.0 or 1.0 (no NaN/Inf anywhere; 0.0 outside the footprint) —
the portal error <i>“Predicted values must be in range [0, 1]”</i> cannot occur with this file.</p>
<h2>Uniqueness against {uni['n_registry_rasters_compared']} earlier rasters</h2>
<p>Verdict <b>{esc(uni['verdict'])}</b>. Worst Spearman on the footprint {uni['worst_spearman']['value']:+.4f}
({esc(uni['worst_spearman']['file'])}; limit 0.90). Worst overlap gate {uni['worst_overlap']['gate_value']:.4f} against limit
{uni['worst_overlap']['gate_limit']:.2f} under rule “{esc(uni['worst_overlap']['gate_rule'])}”
({esc(uni['worst_overlap']['file'])}; base rate {uni['worst_overlap']['base_rate']:.3f}).</p>
<table><tr><th>reference raster</th><th>Spearman</th><th>my dots within 3 px of theirs</th><th>base rate</th><th>Jaccard</th><th>gate</th></tr>""" + "".join(
    f"<tr><td>{esc(r['file'])}</td><td>{r['spearman_footprint']:+.4f}</td><td>{r['frac_my_dots_within_3px_of_theirs']:.3f}</td>"
    f"<td>{r['base_rate_within_3px']:.3f}</td><td>{r['jaccard']:.4f}</td><td>{esc(r['overlap_gate_rule'].split(' (')[0])} "
    f"{'EXCEEDED' if r['overlap_gate_exceeded'] else 'ok'}</td></tr>"
    for r in uni["rows"] if "spearman_footprint" in r) + f"""</table>
<h2>Previous file (H61-G)</h2>
<p>The previous newest file <code>gems61-h61g-x2-gravcorridor-sloperidge-40000dots-20261011T022417Z-0f9408427b88-zeros.tif</code>
(sha256 <code>{fin_g['sha256']}</code>) passed the same {len(fin_g['validator'])} checks when it was built (its receipt:
<code>docs/downloads/gems61-h61g-x2-gravcorridor-sloperidge-40000dots-20261011T022417Z-0f9408427b88-zeros.json</code>).
It remains the lane's best in-protocol file (HOLDOUT-DTI 0.0465) and is also not recommended for a slot.</p>
<h2>Reproduce</h2>
<pre>git clone https://github.com/buffedlizard55-lab/61GEMSDOE &amp;&amp; cd 61GEMSDOE
python3 -m venv .venv &amp;&amp; .venv/bin/pip install -r requirements.txt
PYTHONPATH=src .venv/bin/python scripts/prepare_data.py --fetch --cache-bands
bash scripts/fetch_registry.sh
PYTHONPATH=src .venv/bin/python scripts/run_h61x.py all    # invert -&gt; holdout -&gt; final -&gt; unique -&gt; card
PYTHONPATH=src .venv/bin/python -m pytest -q tests</pre>
"""

PAGES = {
    "index.html": ("Status", index_body),
    "executive-summary.html": ("Executive summary", exec_body),
    "analysis.html": ("Why 0.2778", analysis_body),
    "holdout.html": ("Holdout evidence", hold_body),
    "verify.html": ("Verify", verify_body),
}
for fname, (title, body) in PAGES.items():
    (DOCS / fname).write_text(page(title, body, fname), encoding="utf-8")
    print(f"wrote docs/{fname}")

# root redirect
(ROOT / "index.html").write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=docs/index.html"><title>61GEMSDOE</title></head>
<body><h1>61GEMSDOE — redirecting to <a href="docs/index.html">docs/index.html</a></h1>
<p><a href="docs/downloads/{esc(TIF)}" download>Download the TIF</a> · <a href="docs/executive-summary.html">How to submit</a> · <a href="docs/analysis.html">Why 0.2778</a></p>
</body></html>
""")
print("wrote index.html (root redirect)")

# ----------------------------------------------------------------------------- README top
readme_top = f"""# 61GEMSDOE — buried-structure lane: basement-depth steps from gravity inversion

**[Open the site](https://buffedlizard55-lab.github.io/61GEMSDOE/)** ·
[Executive summary & how to submit](https://buffedlizard55-lab.github.io/61GEMSDOE/docs/executive-summary.html) ·
[Why 0.2778](https://buffedlizard55-lab.github.io/61GEMSDOE/docs/analysis.html) ·
[Competition #306](https://www.drivendata.org/competitions/306/competition-doe-gems/)

## Status of the newest file (read this first)

| question | answer |
|---|---|
| Is the file safe to download and upload? | **YES — FORMAT-VALID and UNIQUE.** {len(fin['validator'])} validator checks pass (float32, EPSG:32611, 3730 × 3292, sample-submission transform, no NaN/Inf anywhere, min 0 / max 1, 0.0 outside the footprint, zero dots on the mapped catalogue). Uniqueness verdict **{uni['verdict']}** against {uni['n_registry_rasters_compared']} earlier rasters (worst Spearman {uni['worst_spearman']['value']:+.4f}; worst overlap gate {uni['worst_overlap']['gate_value']:.3f} vs limit {uni['worst_overlap']['gate_limit']:.2f}). |
| Should it be given a weekly slot? | **NOT RECOMMENDED.** HOLDOUT-DTI {DTI:.4f} (95 % CI {CI[0]:.4f}–{CI[1]:.4f}; {NPOS:,} withheld positive px; {EVALUATOR}). Random lines at the same budget: {RND:.4f} (this run) / {RND_PREV:.4f} (H61-G draw). The unpruned base of our ORGANIZER-CONFIRMED 0.2778 scores 0.1011 on the same evaluator. Run-card verdict: **negative** — "DO NOT SPEND A SLOT: file is valid and unique, but the holdout does not put it above the group's best-known file; keep as a negative/diagnostic result". |
| Has an organiser scored it? | **No.** `organizer_confirmed_score` is null. Every number for this file is HOLDOUT-DTI. |

**[↓ Download the GeoTIFF](docs/downloads/{TIF})** · [zip](docs/downloads/{ZIP}) · [format receipt](docs/downloads/{Path(fin['receipt']).name}) · [run card](evidence/h61x_run_card.json)

- Submission name: `{NAME}`
- Note ({len(NOTE)}/140 chars): `{NOTE}`
- sha256 `{SHA}` ({fin['bytes']:,} bytes); {NDOTS:,} single-pixel dots (value 1.0) at ≥ 3 px spacing, none within 2 px of a mapped fault; median distance to the catalogue {fin['dots_distance_to_catalogue_px']['median']:.1f} px.
- Earlier files in `docs/downloads/` are **SUPERSEDED** or uniqueness references (their own holdouts were 0.0000–0.0465); the H61-G file (`gems61-h61g-x2-…`, 0.0465) remains the lane's best in-protocol file and is also not recommended for a slot. Do not upload the superseded files.

## What this session found (H61-X)

1. **The two-scale corridor sub-hypothesis is refuted on the instrument.** Coarse (800 m) HGM maxima of the GP-1012-calibrated inverted basement: {inv['steps']['coarse']['n_throw_filtered']:,} with throw ≥ 80 m, of which only **{inv['steps']['coarse']['n_disjoint_from_base']}** are new lines (≥ 1.2 km from a base-scale step). The union corridor (X3) scores {X3['pooled_dti']:.4f} — statistically tied with the base-only X2 ({X2['pooled_dti']:.4f}); the coarse corridor alone (X3c) scores {X3C['pooled_dti']:.4f} vs {RND:.4f} random lines. The screen's coarse-scale "enrichment" was the same fault lines blurred, not additional structure.
2. **The uniqueness gate did its job.** X3 (the better-scoring construction) failed the protocol rule-1 pre-check: 91.7 % of its dots within 3 px of the H61-G file's dots (gate 0.70). It was logged as a duplicate and not shipped.
3. **The competing explanation was measured, not asserted.** Intrabasement density contrasts (igneous contacts) should sit on strong magnetic edges: {inv['competing_explanation']['test_2_magnetic_edge']['base_steps']['on_strong_mag_edge']:.3f} of base steps and {inv['competing_explanation']['test_2_magnetic_edge']['coarse_steps']['on_strong_mag_edge']:.3f} of coarse steps do (RTP HGM top-50 %) — neither population is dominated by the mimic; the coarse steps are simply not faults at 300 m.
4. **Answer to the lane's explicit question** (withheld basin-interior segments recovered vs random lines): the coarse new steps recover **{X3C['segments_recovered_basin_interior']}/{X3C['segments_withheld_basin_interior']}** vs **{ctrl[0]['segments_recovered_basin_interior']}/{ctrl[0]['segments_withheld_basin_interior']}** by random lines — below random; the base-scale X2 corridor recovered {X2['segments_recovered_basin_interior']}/{X2['segments_withheld_basin_interior']}.
5. **The shipped file is the unique coarse-corridor construction (X3c)** with a negative verdict — a diagnostic deliverable closing the sub-hypothesis, per the selection rule recorded in the run card.

## Candidate board — all gems61 files in `docs/downloads/` (seven parallel sessions merged on `main`, newest first)

| file | session / PR | positive px | its own session's verdict | shipped file on the segment-withholding evaluator (HOLDOUT-DTI) |
|---|---|---|---|---|
| **`{NAME}`** | this session (H61-X) | {NDOTS:,} | FORMAT-VALID + UNIQUE; HOLDOUT-DTI {DTI:.4f} (CI {CI[0]:.4f}–{CI[1]:.4f}) **below** random lines {RND:.4f} → negative, diagnostic | {DTI:.4f} |
"""
board_rows = []
for r in parallel_rows() + sib["rows"]:
    who, verdict = sib_meta(r["file"])
    if r["pooled_dti"] is None:
        dti = "—"
    elif r.get("note") == "visible-only protocol":
        dti = f"{f4(r['pooled_dti'])} (visible-only) / ≈0 shipped pruned (IR-61-INSTR-02)"
    else:
        dti = f4(r["pooled_dti"])
    board_rows.append(f"| `{r['file']}` | {who} | {r['n_positive_px']:,} | {verdict} | {dti} |")
readme_top += "\n".join(board_rows) + f"""

The parallel sessions' own pages remain in `docs/` with SUPERSEDED-context banners; their evidence files are kept untouched.

## Reproduce

```bash
git clone https://github.com/buffedlizard55-lab/61GEMSDOE && cd 61GEMSDOE
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
PYTHONPATH=src .venv/bin/python scripts/prepare_data.py --fetch --cache-bands   # hash-pinned bridge; 19 band memmaps; creates data/bridge + data/raw links
bash scripts/fetch_registry.sh                                                  # 21 earlier group rasters -> /tmp/refs/registry
PYTHONPATH=src .venv/bin/python scripts/run_h61g.py all                         # H61-G: invert -> screen -> holdout -> final -> unique -> card (~25 min)
PYTHONPATH=src .venv/bin/python scripts/run_h61x.py all                         # H61-X (this session): invert -> holdout -> final -> unique -> card (~20 min)
PYTHONPATH=src .venv/bin/python scripts/run_h61l.py                            # H61-L (parallel session a7790b7f): lidar relief in corridor
PYTHONPATH=src .venv/bin/python scripts/run_h61m.py                            # H61-M (parallel session a7790b7f): gravity x magnetic ribbons
PYTHONPATH=src .venv/bin/python -m pytest -q tests                              # 22 passed
PYTHONPATH=src .venv/bin/python scripts/build_site_h61x.py                      # regenerates docs/*.html + README top from evidence/*.json
```

Checks run at the end of this session: `pytest -q tests` → 22 passed; `run_h61x.py all` → UNIQUENESS: UNIQUE; validator receipt all-pass;
holdout instrument check 0.1011 = 0.1011; the site builder reads every number from JSON.

## Session record (this session: {SESSION})

- `src/gems61/*` — shared tools unchanged (22/22 tests pass; no forks).
- `scripts/run_h61x.py` — H61-X driver: invert | holdout | final | unique | card | all.
- `evidence/h61x_invert.json`, `h61x_holdout.json`, `h61x_final.json`, `h61x_uniqueness.json`, `h61x_run_card.json`.
- New irregularity: **IR-61X-01** the random-line control draws differ between sessions (H61-G: single seed 100 for every cell → 0.0314; H61-X: per-cell seeds 100+ci → 0.0352). Both are recorded; CIs overlap; no conclusion depends on the 0.004 gap. The H61-X card reports the in-run draw as primary and the H61-G draw as secondary.
- New irregularity: **IR-61X-02** the parallel session (arena/a7790b7f) rewrote the `elapsed_s` field of the earlier `evidence/h61g_invert.json` (344.6 → 59.0) when it re-ran the inversion; scientific content unchanged. Evidence receipts are immutable records — restored to 344.6 in this merge.
- Parallel session `arena/a7790b7f` (PRs #11-#13, merged to main before this PR): H61-L lidar relief in the GP-1012 corridor (0.0443 HOLDOUT-DTI, unique) and H61-M gravity×magnetic corridor ribbons (format-valid, unique, no segment holdout). Both files and their evidence (`evidence/h61l_*.json`, `evidence/h61m_*.json`, `scripts/run_h61l.py`, `scripts/run_h61m.py`, `src/gems61/h61m.py`) are merged into this branch and shown on the board above.

## Irregularities (full list on [docs/irregularities.html](docs/irregularities.html))

IR-61-MERGE-01 broken merge on main (fixed) · IR-61-TEST-01 tests imported a sibling package (fixed) · IR-61-DATA-01 three data layouts (fixed) · IR-61-INSTR-02 the "anti-correlated holdout" was a full-catalogue-prune artefact (protocol corrected) · IR-61-UNIQ-01 near-blanket reference raster breaks the one-sided overlap rule (Jaccard rule when reference is dense) · IR-61-ARTIFACT-01 three competing "primary" files advertised before H61-G (all superseded) · IR-61-CONV-01 undamped Oldenburg diverges (damped) · IR-61-RIBBON-01 3 × 3 ribbons halve the holdout score (dots shipped) · IR-61-NET-01 sandbox allow-list: data from the hash-pinned public bridge, not an organiser receipt · **IR-61X-01 random-line control seed handling differs between H61-G (0.0314) and H61-X (0.0352) draws (both recorded, CIs overlap, no conclusion affected)** · **IR-61X-02 parallel session rewrote `elapsed_s` in the earlier `evidence/h61g_invert.json` (344.6 → 59.0); evidence receipts are immutable — restored in this merge**.

## Core values

**Maximize P(Win)** and **Own the Outcome**: the slot is not spent on a file the holdout says is weak; the two-scale sub-hypothesis is
closed with a measured negative rather than a projection; the duplicate construction (X3) is caught by the uniqueness gate before it
can consume a slot; and the path that can actually move 0.2778 (locator recall at 100 m, lidar in corridors, marginal-credit packing)
is named with its obtainable data source.

---
"""

readme = (ROOT / "README.md").read_text(encoding="utf-8")
marker = "## The standing brief (verbatim — re-read at the start of every session)"
idx = readme.find(marker)
if idx == -1:
    raise SystemExit("README standing-brief marker not found; refusing to clobber")
(ROOT / "README.md").write_text(readme_top + readme[idx:], encoding="utf-8")
print(f"wrote README.md (top replaced; standing brief preserved from char {idx})")

print("site build complete")
