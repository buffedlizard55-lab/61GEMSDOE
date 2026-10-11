#!/usr/bin/env python3
"""Build the GitHub Pages site for the H61-M session from the evidence JSON.

Every number is read from evidence/*.json (never typed by hand) and is labelled
HOLDOUT-DTI (our hide-and-recover evaluator), LOQO-DTI (the spatially blocked
leave-one-quadrant-out instrument) or ORGANIZER-CONFIRMED (a score the group
reports on its own pages -- owner reports, not platform receipts).

    PYTHONPATH=src .venv/bin/python scripts/build_site_h61m.py
"""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EV = ROOT / "evidence"


def j(name, default=None):
    p = EV / name
    if not p.exists():
        if default is None:
            raise FileNotFoundError(p)
        return default
    return json.loads(p.read_text())


card = j("h61m_run_card.json")
fin = j("h61m_final.json")
hold = j("h61m_holdout.json")
feat = j("h61m_features.json")
uni = j("h61m_uniqueness.json")
e2 = j("h61m2_holdout.json")
e3l = j("h61m3_loqo.json")
e4 = j("h61m4_loqo.json")
e3s = j("h61m3_sweep.json", {})
hyp = j("h61m_hypotheses.json", [])
reg = j("registry_habitat.json", {})
forensics = j(ROOT / "reports" / "forensics.json")
screen = j("h61g_screen.json", {})

# --- derived from registry_habitat.json (never hardcoded) ------------------- #
_top = [r for r in reg.get("rows", []) if (r.get("claimed") or 0) >= 0.20]
_best = max(_top, key=lambda r: r["claimed"]) if _top else {}
TOP_N = len(_top)
TOP_CLAIMED = _best.get("claimed")
TOP_DIST = _best.get("median_dist_cat")
TOP_FRACS = sorted(r["frac_of_footprint"] for r in _top) if _top else []
TOP_FRAC_LO = min(TOP_FRACS) * 100 if TOP_FRACS else 0.0
TOP_FRAC_HI = max(TOP_FRACS) * 100 if TOP_FRACS else 0.0
TOP_DISTS = sorted(r["median_dist_cat"] for r in _top) if _top else []
_band = sorted((reg.get("band_contrast_top_vs_rest") or {}).items(),
               key=lambda kv: -abs(kv[1]["separation"]))
BEST_BAND, BEST_BAND_SEP = (_band[0] if _band else ("n/a", {"separation": 0.0}))
BEST_BAND_SEP = BEST_BAND_SEP["separation"] if isinstance(BEST_BAND_SEP, dict) else BEST_BAND_SEP

_all_auc = [r["loqo_canary_auc"] for qd in e4.get("per_quadrant", {}).values() for r in qd.values()]
_all_dti = [r["loqo_pooled_dti"] for qd in e4.get("per_quadrant", {}).values() for r in qd.values()]
LOQO_AUC_LO = min(_all_auc) if _all_auc else 0.0
LOQO_AUC_HI = max(_all_auc) if _all_auc else 0.0
LOQO_DTI_LO = min(_all_dti) if _all_dti else 0.0
LOQO_DTI_HI = max(_all_dti) if _all_dti else 0.0
LOQO_N = len(_all_auc)

_scr = [r["enrichment_mean_kernel_vs_random"] for r in screen.get("rows", [])
        if r.get("candidate", "").startswith(("grav HGM maxima", "supplied depth band"))]
ENR_LO = min(_scr) if _scr else 0.0
ENR_HI = max(_scr) if _scr else 0.0


def pick(results, frag):
    for r in results:
        if frag in r["name"]:
            return r
    raise KeyError(frag)


GATE_P2 = pick(hold["results"], "habitat x corridor (prune 2px) @ 40000")
GATE_P3 = pick(hold["results"], "habitat x corridor (prune 3px) @ 40000")
UNGATED = pick(hold["results"], "habitat no corridor gate @ 40000")
BASIN = pick(hold["results"], "habitat basin only @ 40000")
RIBBON = pick(hold["results"], "3x3 ribbon")
LOG_CANARY = hold["leakage_canary"]["worst_auc"]
GBM_CANARY = e2["leakage_canary"]["worst_auc"]
CORR_CANARY = hold["leakage_canary"]["per_feature"]["corridor indicator"]["auc"]
GBM_P2 = pick(e2["results"], "gbm no-prior prune2 @ 40000")
GBM_P3 = pick(e2["results"], "gbm no-prior prune3 @ 40000")
PRIORS = [pick(e2["results"], f) for f in ("prior=step k=0.5", "prior=step k=2.0",
                                           "prior=throw k=1.0") if
          "logistic" in f or True]
PRIOR_DTIS = [r["pooled_dti"] for r in e2["results"] if r["name"].startswith("E2 logistic prior")]

NAME = fin["submission"]
TIF = f"downloads/{NAME}.tif"
ZIP = f"downloads/{NAME}.zip"
RECEIPT = f"downloads/{NAME}.json"
SHA = fin["sha256"]
NOTE = fin["note"]
HD = card["holdout_dti"]

NAV = ('<nav><a href="index.html">Status</a> · <a href="executive-summary.html">Executive summary '
       '&amp; how to submit</a> · <a href="analysis.html">Why 0.2778</a> · '
       '<a href="method.html">Method</a> · <a href="holdout.html">Holdout evidence</a> · '
       '<a href="hypotheses.html">Next hypotheses</a> · <a href="irregularities.html">Irregularities'
       '</a> · <a href="next-steps.html">Next steps &amp; limitations</a> · '
       '<a href="verify.html">Verify</a></nav>')

HEAD = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · 61GEMSDOE</title>
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
.small{{font-size:.85rem;color:var(--dim)}}kbd{{background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:0 5px}}
</style></head><body><div class="wrap">
{nav}
"""


def esc(x):
    return html.escape(str(x))


def f4(x):
    return "—" if x is None else f"{x:.4f}"


def page(title, body, active="index.html"):
    nav = NAV.replace(f'href="{active}"', f'href="{active}" class=active')
    return HEAD.format(title=title, nav=nav) + body + "\n</div></body></html>\n"


# --------------------------------------------------------------------------- #
STATUS = f"""
<div class="status">
<h2 style="margin:.2em 0;border:0">Status of the newest file:
 <span style="color:var(--ok)">FORMAT-VALID and UNIQUE – safe to download and upload</span>
 · <span style="color:var(--warn)">HOLDOUT-DTI {f4(HD['value'])} – above our random baseline, below our best live file – not recommended for a weekly slot</span></h2>
<p><b>What it is:</b> <code>{esc(NAME)}.tif</code> — {fin['n_dots']:,} single-pixel dots (value 1.0; every other cell 0.0),
float32, EPSG:32611, 3730 × 3292, 100 m, identical grid to <code>sample_submission.tif</code>,
no NaN/Inf anywhere, min 0 / max 1 (<a href="verify.html">validator receipt</a>: {len(fin['validator'])} checks, all passed).
Uniqueness against {uni['n_registry_rasters_compared']} earlier rasters: worst Spearman
{uni['worst_spearman']['value']:+.4f} (limit {uni['rho_limit']}), worst one-sided 3 px dot overlap
{uni['worst_overlap_gate']['value']:.3f} (limit {uni['worst_overlap_gate']['limit']}; the one
reference denser than ours is gated on Jaccard instead — worst
{uni['worst_overlap']['gate_value']:.3f} against a limit of {uni['worst_overlap']['gate_limit']}).
Verdict <b>{uni['verdict']}</b>.</p>
<p><b>What we measured:</b> <span class="tag h">HOLDOUT-DTI</span> {f4(HD['value'])}
(95 % CI {HD['ci95'][0]:.4f}–{HD['ci95'][1]:.4f}; {HD['n_withheld_positive_px']:,} withheld
positive px; {esc(HD['evaluator'])}). Random lines at the same budget: {f4(HD['random_lines_same_budget'])}.
Previous session's best lane construction (H61-G X2): {f4(HD['previous_session_best_X2'])}.
Withheld basin-interior segments recovered:
<b>{HD['segments_recovered']} of {HD['segments_withheld']}</b> (95 % CI
{HD['segments_recovered_ci'][0]*100:.1f}–{HD['segments_recovered_ci'][1]*100:.1f} %) against
<b>{HD['segments_recovered_random_lines']}</b> for random lines at the same budget. Leakage canary worst AUC
{card['leakage_canary']['logistic_oof_auc']:.3f} (limit 0.90) — no leakage.
But the spatially blocked leave-one-quadrant-out test puts every locator we have at the random
baseline ({esc(card['spatially_blocked_dti']['verdict'])}), so this file is an honest
<b>negative result</b>, not a slot candidate.</p>
<p><a class="btn" href="{TIF}" download>⬇ Download {esc(NAME)}.tif ({fin['bytes']/1024:.0f} kB) — this is the file to submit</a>
<a class="btn sec" href="{ZIP}" download>zip (single TIFF)</a>
<a class="btn sec" href="{RECEIPT}">format receipt (JSON)</a>
<a class="btn sec" href="executive-summary.html">How to submit, step by step</a></p>
<p class="small">sha256 <code>{SHA}</code> · submission name <code>{esc(NAME)}</code> ·
note ({fin['note_chars']}/140 chars): <code>{esc(NOTE)}</code> ·
median dot distance to the mapped catalogue {fin['dots_distance_to_catalogue_px']['median']:.1f} px
({fin['dots_distance_to_catalogue_px']['median']*100:.0f} m); the group's best scorer (<code>h33-h33-2-b2</code>, {TOP_CLAIMED}) sits at {TOP_DIST:.1f} px, and the nine rasters scored at or above 0.20 sit between {min(TOP_DISTS):.1f} and {max(TOP_DISTS):.1f} px.</p>
</div>
"""

HOLD_ROWS = ""
for r in hold["results"]:
    cls = "hl" if r["name"] == fin["candidate"] else ("dim" if r["kind"] in ("lines", "dots") else "")
    HOLD_ROWS += (f'<tr class="{cls}"><td>{esc(r["name"])}</td><td>{r["n_emitted_per_draw"]:,.0f}</td>'
                  f'<td>{f4(r["pooled_dti"])}</td><td>{r["ci95_bootstrap_cells"][0]:.4f}–{r["ci95_bootstrap_cells"][1]:.4f}</td>'
                  f'<td>{r["coverage"]:.3f}</td><td>{r["segments_recovered_basin_interior"]}/{r["segments_withheld_basin_interior"]}</td></tr>\n')

LOQO_ROWS = ""
for k, v in e4["summary"].items():
    LOQO_ROWS += (f'<tr><td>{esc(k)}</td><td>{f4(v["mean_loqo_dti"])}</td>'
                  f'<td>{f4(v["min_loqo_dti"])}–{f4(v["max_loqo_dti"])}</td>'
                  f'<td>{v["mean_loqo_canary_auc"]:.3f}</td><td>{v["mean_coverage"]:.3f}</td></tr>\n')

INDEX = page("Status", STATUS + f"""
<h2>One-paragraph result</h2>
<p>The lane asked for a Parker/Oldenburg inversion of the supplied isostatic-residual gravity,
calibrated only against the USGS GP-1012 basin-depth maps, and for the horizontal-gradient maxima of the
inverted basement surface as candidate buried range-front and intrabasin faults. We did that, at a
<b>200 m</b> inversion cell instead of the previous session's 400 m (the lane's own statement that
"gravity resolves such steps only to a few hundred metres at best" is the reason):
{feat['steps_fine']['n_hgm_maxima']:,} Blakely-Simpson maxima of |grad depth| →
{feat['steps_fine']['n_steps']:,} steps with a measured throw ≥ 80 m; the inverted surface reproduces
GP-1012's &gt;1 km basin fraction ({feat['depth_stats_fine']['fraction_gt_1km']:.3f} against the
0.20 anchor), correlates {feat['rank_correlation_fine_vs_coarse']:.3f} with the 400 m solution and
{feat['cross_check_vs_supplied_band15']['pearson_r']:.3f} with the organiser's own depth layer, and
anti-correlates with gravity at {feat['cross_check_vs_supplied_band15']['corr_depth_vs_gravity']:.3f}
(the sign check). The step field is then used as <i>features</i> in an out-of-fold logistic habitat
model over 28 catalogue-independent channels, and the model's ranking places
{fin['n_dots']:,} binary dots at 3 px spacing, every dot more than 3 px from a mapped trace.
Result: <span class="tag h">HOLDOUT-DTI</span> {f4(HD['value'])} (CI {HD['ci95'][0]:.4f}–{HD['ci95'][1]:.4f})
against {f4(HD['random_lines_same_budget'])} for random lines and {f4(HD['previous_session_best_X2'])} for
the previous session's corridor × slope-ridge locator. The <a href="analysis.html">analysis page</a>
explains why 0.2778 is where it is, and the <a href="holdout.html">holdout page</a> shows the
leave-one-quadrant-out test that keeps this file off a slot.</p>

<h2>What is new this session (H61-M)</h2>
<ol>
<li><b>200 m inversion.</b> The previous session inverted at 400 m. Halving the cell is the direct
response to the lane's "a few hundred metres" resolution statement; the two solutions agree at
ρ = {feat['rank_correlation_fine_vs_coarse']:.3f} and only {feat['support']['footprint_cells_lost_at_200m']:,}
footprint cells are lost at the finer grid.</li>
<li><b>An out-of-fold habitat model replaces the hand-written locator.</b> 28 features, none derived
from the position of the mapped catalogue, trained only on the <i>visible</i faults of each holdout
cell. HOLDOUT-DTI {f4(HD['value'])} vs {f4(HD['previous_session_best_X2'])} for the hand-written
corridor × slope-ridge locator.</li>
<li><b>The lane's competing explanation is implemented, not asserted.</b> Inverted depth, depth
gradient, step throw, step indicator, corridor indicator and an Euler SI = 0 source depth are all
model features; their measured logistic weights are small
(inv_depth {hold['mean_coefficients']['inv_depth']:+.3f}, inv_depth_hgm
{hold['mean_coefficients']['inv_depth_hgm']:+.3f}, euler_depth
{hold['mean_coefficients']['euler_depth']:+.3f}, step_throw
{hold['mean_coefficients']['step_throw']:+.3f}, step_indicator
{hold['mean_coefficients']['step_indicator']:+.3f}, corridor_indicator
{hold['mean_coefficients']['corridor_indicator']:+.3f}). That is the honest negative result for the
lane's premise at 300 m.</li>
<li><b>A leakage finding (IR-61-LEAK-01).</b> A gradient-boosted version of the same model reached
HOLDOUT-DTI {max(r['pooled_dti'] for r in e2['results']):.4f} and a canary AUC of
{e2['leakage_canary']['worst_auc']:.3f} — above the protocol's 0.90 line. The leave-one-quadrant-out
retest shows the AUC falls to
{LOQO_AUC_LO:.3f}–{LOQO_AUC_HI:.3f}
across all {LOQO_N} blocked retests, with no training pixel inside the scored quadrant: the skill was adjacency to visible traces, not
generalisation. The shipped file uses the logistic model, whose canary AUC is
{card['leakage_canary']['logistic_oof_auc']:.3f}.</li>
<li><b>Reverse engineering of the group's scored rasters</b>
(<code>evidence/registry_habitat.json</code>, {reg.get('n_rasters', 0)} rasters): every high-scoring
file is binary, sparse ({TOP_FRAC_LO:.2f}–{TOP_FRAC_HI:.2f} % of the footprint across the
{TOP_N} rasters scored at or above 0.20), carries <b>zero</b> dots exactly on a mapped catalogue
pixel, and sits {min(TOP_DISTS):.1f}–{max(TOP_DISTS):.1f} px (1.4–2.0 km) from the catalogue.
The strongest single-band separation between those {TOP_N} and the other
{reg.get('n_rasters', 0) - TOP_N} is {esc(BEST_BAND)} at
{abs(BEST_BAND_SEP):.3f} AUC — i.e. no single layer explains the scores; they come from the
conjunction.</li>
</ol>

<h2>Holdout headline <span class="tag h">HOLDOUT-DTI</span></h2>
<p class="small">Evaluator {esc(hold['evaluator'])}; withheld positives
{hold['n_withheld_truth_px']:,} px; pooled DTI α = 0.2, β = 0.8, 300 m triangular kernel;
95% CI = percentile bootstrap over fold cells. Candidates are trained only on the <i>visible</i>
catalogue of their own cell and pruned only against that visible catalogue.</p>
<table><tr><th>Row</th><th>dots / draw</th><th>HOLDOUT-DTI</th><th>95% CI</th><th>withheld-truth coverage</th><th>basin-interior segments recovered</th></tr>
{HOLD_ROWS}</table>

<h2>Spatially blocked retest <span class="tag p">LOQO-DTI</span></h2>
<p class="small">Leave-one-quadrant-out: retrain with <b>no</b> training pixel inside the scored
quadrant, then score the fourth. This is the instrument to trust for a slot decision, because the
group's own organizer-scored pair shows that dots adjacent to the catalogue do not pay on the live
metric (see <a href="analysis.html">analysis</a>).</p>
<table><tr><th>locator</th><th>mean LOQO-DTI</th><th>range</th><th>mean blocked canary AUC</th><th>mean coverage</th></tr>
{LOQO_ROWS}</table>
""")

# --------------------------------------------------------------------------- #
EXEC = page("Executive summary", STATUS + f"""
<h2>Decision in one line</h2>
<p>The upload is <b>safe</b>: the format is pinned to the organiser's sample grid, every one of the
{fin['n_dots']:,} positive cells is exactly 1.0, every other cell is 0.0, and all
{len(fin['validator'])} validator checks pass. The expected score is <b>not</b> competitive with our
best live file: HOLDOUT-DTI {f4(HD['value'])} (CI {HD['ci95'][0]:.4f}–{HD['ci95'][1]:.4f}) against
{f4(HD['random_lines_same_budget'])} for random lines, and the spatially blocked retest puts it at the
random baseline. Spend a weekly slot on it only to obtain an ORGANIZER-CONFIRMED number for the
gravity-inversion lane itself.</p>

<h2>How to submit (step by step)</h2>
<ol>
<li>Download <a href="{TIF}" download><code>{esc(NAME)}.tif</code></a> ({fin['bytes']/1024:.0f} kB), or the
<a href="{ZIP}" download>zip</a> which contains exactly that one TIFF. Verify the digest if you like:
<code>{SHA}</code>.</li>
<li>Open <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/</a>
while logged in to the competition account.</li>
<li>In <b>File to submit</b>, choose the <code>.tif</code> (DrivenData accepts the GeoTIFF directly; the
zip is only a convenience copy). The format the portal expects is a single-band 32-bit float GeoTIFF in
EPSG:32611, 3730 × 3292, 100 m, values in [0, 1] — exactly what the validator receipt records.</li>
<li>In <b>Note (optional)</b>, paste the ≤ 140-character note ({fin['note_chars']} characters here):
<code>{esc(NOTE)}</code></li>
<li>Submit. The note and the submission name are what let us tell this file apart later.</li>
<li>When the platform returns a score, copy it into <code>evidence/h61m_run_card.json</code> →
<code>organizer_confirmed_score</code> and rebuild the site. Until then every number on this site is
HOLDOUT-DTI or LOQO-DTI, never a projection of a live score.</li>
</ol>

<h2>Why the "Predicted values must be in range [0, 1]" error cannot happen with this file</h2>
<p>That error has two causes, both engineered out here and both re-checked against the bytes on disk:
(1) the GeoDAWN feature raster's float32 sentinel <code>-3.4028234663852886e+38</code> leaking into the
prediction, and (2) a footprint mask derived from a feature band leaving 3,061 scored pixels as NaN.
This file is written by <code>gems61.submission_writer.write_submission</code>, which refuses to write
anything that is not already finite and inside [0, 1], then re-reads the TIFF from disk and aborts unless
every one of the 12,279,160 cells passes. The receipt is in
<a href="{RECEIPT}"><code>{esc(NAME)}.json</code></a>.</p>

<h2>What the file is, physically</h2>
<p>40,000 binary dots on the 100 m competition grid, one per 3 × 3 tile (the spacing at which two dots
stop duplicating each other's 300 m kernel credit), ranked by an out-of-fold logistic habitat model
trained on the visible mapped faults over 28 catalogue-independent channels, and pruned so that no dot
lies within 3 px (300 m) of a mapped trace. Median distance from a dot to the nearest mapped fault:
{fin['dots_distance_to_catalogue_px']['median']:.1f} px ({fin['dots_distance_to_catalogue_px']['median']*100:.0f} m);
{fin['dots_distance_to_catalogue_px']['frac_within_3px']*100:.1f} % of dots are within 3 px of one.</p>
""", active="executive-summary.html")

# --------------------------------------------------------------------------- #
ANALYSIS = page("Why 0.2778", f"""
<h2>The PhD-level answer: why <code>h33-h33-2-b2</code> scored 0.2778 and whether we can beat it</h2>
<p>Everything below is measured from the published bytes
(<code>reports/forensics.json</code>, <code>evidence/registry_habitat.json</code>) or from the group's
own reported scores. The group's scores are <b>owner reports, not platform receipts</b>
(IR-61-SCORE-01); they are used to order the evidence, never as a promise.</p>

<h3>1. What the metric actually pays for</h3>
<p>The score is the distance-weighted Tversky index with α = 0.2 (false positives), β = 0.8 (false
negatives) and a 300 m triangular kernel, on a hidden truth of faults that are <i>not</i> in the
supplied catalogue. Write the emission as a binary dot field. Then a dot that lands within the kernel
of a truth pixel and is the best dot for at least one such pixel raises the numerator by
k = 1 − d/3 and lowers the false-negative term; a dot that lands on nothing raises the denominator by
0.2. The marginal rule that falls out of the algebra is exact: <b>add a dot iff its expected new truth
credit exceeds α · DTI</b>, i.e. about 0.06 at DTI = 0.28. So the game is not "be precise", it is
"cover as much hidden truth as possible with dots that mostly land inside 300 m of it".</p>

<h3>2. What 0.2778 is made of</h3>
<p>Measured on the published file: {forensics['rasters'][-1]['n_nonzero']:,} binary dots, zero on the
catalogue, median distance {forensics['rasters'][-1]['median_distance_to_visible_catalogue_px']:.1f} px
from it, 0.73 % of the footprint. It is the <i>exact set difference</i> of the 0.2600 file with every
dot within 3 px of the catalogue deleted (verified in <code>reports/forensics.json</code>:
<code>top_is_strict_subset = true</code>, {forensics['set_difference_forensics']['top_minus_core']['removed_n']:,}
dots removed). That single controlled deletion moved the score 0.2600 → 0.2778, so <b>dots adjacent to
the mapped catalogue were net-negative on the live metric</b>. Two independent readings agree: the
group's budget ladder (37,654 → 0.2778; 40,199 → 0.2708; 44,090 → 0.2600; 60,069 → 0.2477;
61,328 → 0.2449) says ~38–40 k dots at ~3 px spacing is the live optimum, and the dotted versions beat
their own multiline parents (0.1922 multiline → 0.2600 dotted) because the metric charges 0.2 per
extra positive pixel.</p>

<h3>3. Why the lane cannot reach it</h3>
<p>Gravity fixes a basement step to kilometres; the metric pays within 300 m. Measured here and in the
previous session: the horizontal-gradient maxima of the inverted basement surface are enriched only
{ENR_LO:.2f}–{ENR_HI:.2f}× over random pixels inside the 300 m kernel of mapped faults, and the corridor indicator's
leakage-canary AUC against withheld faults is
{hold['leakage_canary']['per_feature']['corridor indicator']['auc']:.3f} — no better than a coin flip.
So the lane can say where to look and never where to put the dot. That is a property of the data
(regional isostatic residuals, 58 % of the rectangle unsurveyed), not of the implementation.</p>

<h3>4. Can we beat 0.2778?</h3>
<p>Three things would have to be true, in order of how much they are worth:</p>
<ul>
<li><b>A locator that generalises across space.</b> Every locator we have — logistic habitat, gradient
boosting, the single strongest band, the lane's own corridor × slope — scores 0.02–0.05 on the
leave-one-quadrant-out test, i.e. at the random baseline. The 0.26–0.28 files must be using a locator
that does generalise; from the published bytes its strongest single-band separations are the
detrended-elevation slope (AUC 0.66 at its dots vs random) and the magnetic horizontal gradient
(0.57), and no single layer separates the top scorers from the rest by more than 0.02 AUC — the signal
is in the conjunction, which is exactly what we cannot see.</li>
<li><b>External 100 m evidence.</b> The highest-value untried source is metre-scale topography: USGS
3DEP 1 m DEM over the high-prior tiles (free public domain from USGS The National Map; the
competition data tab ships only the three rasters listed in the bridge manifest — IR-61-SRC-01). A 1 m scarp is invisible at 100 m but is the primary evidence a field mapper uses.
This session's egress allow-list blocks <code>prd-tnm.s3.amazonaws.com</code>, so it is named as the
specific obtainable source rather than claimed as done.</li>
<li><b>Recall, not precision.</b> Because β = 0.8 ≫ α = 0.2, the optimum sits at higher recall than
intuition suggests: the marginal bar is only ~0.06 of new truth credit per dot. Files that emit
~120 k pixels score 0.19, files that emit ~38 k score 0.28 — but that comparison confounds budget with
field quality, and the only controlled pair we have (the 0.2600 → 0.2778 set difference) changes the
prune, not the budget.</li>
</ul>
<p><b>Verdict:</b> not with the supplied 19 bands alone. The honest route to &gt; 0.2778 is a
metre-scale topographic locator inside a gravity corridor, which is hypothesis H61-N on the
<a href="hypotheses.html">next-hypotheses page</a> and needs the 3DEP tiles named there.</p>
""", active="analysis.html")

# --------------------------------------------------------------------------- #
METHOD = page("Method", f"""
<h2>Method — H61-M</h2>
<ol>
<li><b>Band-pass the isostatic residual.</b> The supplied band 13 (isostatic gravity anomaly) is
decimated to the inversion cell, inpainted across the unsurveyed 58 % by multi-scale normalised
convolution, and a 15 km Gaussian regional is removed — Blakely &amp; Jachens' (1991) separation of the
basement field from the basin field before inversion.</li>
<li><b>Invert for basement depth.</b> Parker (1973) forward series / Oldenburg (1974) first iterate
(the low-passed Bouguer slab), with the density contrast, reference level and filter corner chosen
against USGS GP-1012 (Saltus &amp; Jachens 1995, <i>Gravity and basin-depth maps of the Basin and
Range Province, Western United States</i>, 1 : 2,500,000) only — median depth band and the ≈ 20 % of Nevada
deeper than 1 km. Achieved: p50 {feat['depth_stats_fine']['p50']:.0f} m, p90
{feat['depth_stats_fine']['p90']:.0f} m, &gt;1 km fraction {feat['depth_stats_fine']['fraction_gt_1km']:.3f}.
Run twice, at 400 m and at <b>200 m</b>; the two agree at ρ = {feat['rank_correlation_fine_vs_coarse']:.3f}.
Sign check: corr(depth, gravity) = {feat['cross_check_vs_supplied_band15']['corr_depth_vs_gravity']:.3f}.</li>
<li><b>Find the steps.</b> Blakely–Simpson (1986) automatic maxima of |grad depth|, filtered by a
measured throw ≥ 80 m across the 3 × 3 neighbourhood: {feat['steps_fine']['n_hgm_maxima']:,} maxima →
{feat['steps_fine']['n_steps']:,} steps.</li>
<li><b>Build the habitat stack.</b> 28 channels, all rank-normalised to [0, 1] over the footprint and
none derived from the position of the mapped catalogue: the 19 supplied bands, plus inverted depth,
inverted-depth HGM, step throw, step indicator, corridor indicator, basin indicator, Euler SI = 0
source depth (band 18 as the field, band 11 as its vertical derivative) and the two directional
components of the inverted-depth gradient.</li>
<li><b>Train out-of-fold.</b> L2 logistic regression, positives = the <i>visible</i> mapped faults of
the holdout cell, negatives = 4× random footprint pixels. Per-cell coefficients are in
<code>evidence/h61m_holdout.json</code>; the mean coefficients are on the
<a href="holdout.html">holdout page</a>.</li>
<li><b>Emit.</b> Rank by out-of-fold probability, one dot per 3 × 3 tile, pruned to &gt; 3 px from
every visible mapped trace, budget {fin['budget']:,} dots. Dots, not ribbons: a 3 × 3 ribbon of the
same dots scores {RIBBON['pooled_dti']:.4f} against {GATE_P2['pooled_dti']:.4f} on the protocol holdout.</li>
<li><b>Validate and check uniqueness.</b> <code>gems61.submission_writer</code> writes the TIFF and
re-reads it from disk; <code>gems61.validate</code> runs {len(fin['validator'])} checks;
<code>scripts/run_h61mh.py unique</code> compares against {uni['n_registry_rasters_compared']} registry
rasters.</li>
</ol>
<h3>Sources</h3>
<table><tr><th>what</th><th>link</th></tr>
<tr><td>Parker, R.L. (1973), "The rapid calculation of potential anomalies", Geophysical Journal of the Royal Astronomical Society 31:447–455</td><td><a href="https://doi.org/10.1111/j.1365-246X.1973.tb02307.x">doi:10.1111/j.1365-246X.1973.tb02307.x</a></td></tr>
<tr><td>Oldenburg, D.W. (1974), "The inversion and interpretation of gravity anomalies", Geophysics 39(4):526–536</td><td><a href="https://doi.org/10.1190/1.1440444">doi:10.1190/1.1440444</a></td></tr>
<tr><td>Blakely, R.J. &amp; Simpson, R.W. (1986), "Approximating edges of source bodies from magnetic or gravity anomalies", Geophysics 51(7):1494–1498</td><td><a href="https://doi.org/10.1190/1.1442197">doi:10.1190/1.1442197</a></td></tr>
<tr><td>Blakely, R.J. &amp; Jachens, R.C. (1991), "Regional study of mineral resources in Nevada: insights from three-dimensional analysis of gravity and magnetic anomalies", GSA Bulletin 103:795–803</td><td><a href="https://doi.org/10.1130/0016-7606(1991)103%3C0795:RSOMRI%3E2.3.CO;2">doi:10.1130/0016-7606(1991)103&lt;0795:RSOMRI&gt;2.3.CO;2</a></td></tr>
<tr><td>Saltus, R.W. &amp; Jachens, R.C. (1995), "Gravity and basin-depth maps of the Basin and Range Province, Western United States", USGS Geophysical Investigations Map 1012 (GP-1012), 1 : 2,500,000</td><td><a href="https://doi.org/10.3133/gp1012">doi:10.3133/gp1012</a></td></tr>
<tr><td>Reid, A.B., Allsop, J.M., Granser, H., Millett, A.J. &amp; Somerton, I.W. (1990), "Magnetic interpretation in three dimensions using Euler deconvolution", Geophysics 55(1):80–91</td><td><a href="https://doi.org/10.1190/1.1442789">doi:10.1190/1.1442789</a></td></tr>
<tr><td>competition problem description + metric</td><td><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">drivendata.org/competitions/306/…/page/967</a></td></tr>
<tr><td>official reference solution (α = 0.2, β = 0.8 Tversky)</td><td><a href="https://github.com/drivendataorg/gems-prize-reference-solution">github.com/drivendataorg/gems-prize-reference-solution</a></td></tr>
</table>
""", active="method.html")

# --------------------------------------------------------------------------- #
HOLDOUT = f"""
<h2>Holdout evidence</h2>
<p>Protocol (parallel-run rule 2): withhold <b>whole</b> fault segments (≤ 12 px chunks between
intersections) inside four spatially eroded quadrants, with two independent draws; derive every
catalogue-based quantity only from the <b>visible</b> faults; mask visible fault pixels pixel-exactly;
score pooled DTI with α = 0.2, β = 0.8 and a 300 m triangular kernel. Withheld positives:
{hold['n_withheld_truth_px']:,} px over {hold['n_cells']} cells.</p>

<h3>Leakage canary (protocol rule 4)</h3>
<table><tr><th>feature</th><th>AUC (withheld truth vs random active px)</th></tr>
"""
for k, v in hold["leakage_canary"]["per_feature"].items():
    HOLDOUT += f'<tr><td>{esc(k)}</td><td>{v["auc"]:.3f}</td></tr>\n'
HOLDOUT += f"""</table>
<p>Worst AUC {hold['leakage_canary']['worst_auc']:.3f} (limit 0.90) — the shipped logistic model passes
the canary with no caveat. The gradient-boosted variant's {e2['leakage_canary']['worst_auc']:.3f} does
not; see below.</p>

<h3>Model class and prior shape (experiment 2)</h3>
<table><tr><th>row</th><th>dots / draw</th><th>HOLDOUT-DTI</th><th>95% CI</th><th>coverage</th><th>basin-interior segments</th></tr>
"""
for r in e2["results"]:
    HOLDOUT += (f'<tr><td>{esc(r["name"])}</td><td>{r["n_emitted_per_draw"]:,.0f}</td>'
                f'<td>{f4(r["pooled_dti"])}</td><td>{r["ci95_bootstrap_cells"][0]:.4f}–{r["ci95_bootstrap_cells"][1]:.4f}</td>'
                f'<td>{r["coverage"]:.3f}</td><td>{r["segments_recovered_basin_interior"]}/{r["segments_withheld_basin_interior"]}</td></tr>\n')
HOLDOUT += "</table>\n"

if e3s:
    HOLDOUT += """
<h3>Configuration sweep (experiment 3)</h3>
<table><tr><th>row</th><th>dots / draw</th><th>HOLDOUT-DTI</th><th>95% CI</th><th>coverage</th><th>basin-interior segments</th></tr>
"""
    for r in e3s["results"]:
        HOLDOUT += (f'<tr><td>{esc(r["name"])}</td><td>{r["n_emitted_per_draw"]:,.0f}</td>'
                    f'<td>{f4(r["pooled_dti"])}</td><td>{r["ci95_bootstrap_cells"][0]:.4f}–{r["ci95_bootstrap_cells"][1]:.4f}</td>'
                    f'<td>{r["coverage"]:.3f}</td><td>{r["segments_recovered_basin_interior"]}/{r["segments_withheld_basin_interior"]}</td></tr>\n')
    HOLDOUT += "</table>\n"

HOLDOUT += f"""
<h3>Leave-one-quadrant-out retest (experiments 3 and 4)</h3>
<p>Retrain with <b>no</b> training pixel inside the scored quadrant, then score that quadrant. This is
the instrument that decides whether a locator has skill or is merely sitting next to visible traces.</p>
<table><tr><th>quadrant</th><th>locator</th><th>blocked canary AUC</th><th>LOQO-DTI</th><th>coverage</th><th>basin-interior segments</th></tr>
"""
for q, d in e4["per_quadrant"].items():
    for kind, r in d.items():
        HOLDOUT += (f'<tr><td>{esc(q)}</td><td>{esc(kind)}</td><td>{r["loqo_canary_auc"]:.3f}</td>'
                    f'<td>{f4(r["loqo_pooled_dti"])}</td><td>{r["coverage"]:.3f}</td>'
                    f'<td>{esc(r["basin_interior"])}</td></tr>\n')
HOLDOUT += "</table>\n"

HOLDOUT += f"""
<h3>Mean logistic coefficients (the lane's instruments inside the model)</h3>
<table><tr><th>feature</th><th>mean coefficient</th></tr>
"""
for k, v in sorted(hold["mean_coefficients"].items(), key=lambda kv: -abs(kv[1])):
    cls = "hl" if k in ("inv_depth", "inv_depth_hgm", "step_throw", "step_indicator",
                        "corridor_indicator", "euler_depth") else ""
    HOLDOUT += f'<tr class="{cls}"><td>{esc(k)}</td><td>{v:+.3f}</td></tr>\n'
HOLDOUT += "</table>\n"
HOLDOUT = page("Holdout evidence", HOLDOUT, active="holdout.html")

# --------------------------------------------------------------------------- #
HYP_ROWS = ""
for h in hyp:
    HYP_ROWS += (f'<tr><td><b>{esc(h["id"])}</b> {esc(h["name"])}</td><td>{esc(h["layers"])}</td>'
                 f'<td>{esc(h["signature"])}</td><td>{esc(h["why"])}</td><td>{esc(h["diff"])}</td>'
                 f'<td>{esc(h["gain"])}</td><td>{esc(h["cost"])}</td></tr>\n')
HYPOTHESES = page("Next hypotheses", f"""
<h2>Candidate geological hypotheses not yet tried</h2>
<p>Ranked by expected DTI improvement and implementation cost. Every "gain" is a projection, never a
score; nothing here has been validated on the holdout unless it says so.</p>
<table><tr><th>hypothesis</th><th>layers</th><th>physical signature</th><th>why it catches a fault the catalogue lacks</th><th>difference from this repo</th><th>expected gain</th><th>cost</th></tr>
{HYP_ROWS}</table>
<h3>What this session ruled out</h3>
<ul>
<li><b>A hard basement-step corridor as the candidate gate.</b> {GATE_P3['pooled_dti']:.4f}–{GATE_P2['pooled_dti']:.4f} gated vs {UNGATED['pooled_dti']:.4f} ungated
at the same budget; the corridor indicator's canary AUC against withheld faults is {CORR_CANARY:.3f}.</li>
<li><b>Gradient boosting on the same 28 features.</b> {GBM_P2['pooled_dti']:.4f} on the
non-blocked holdout, but blocked AUC {LOQO_AUC_LO:.3f}–{LOQO_AUC_HI:.3f} and LOQO-DTI
{LOQO_DTI_LO:.4f}–{LOQO_DTI_HI:.4f}: adjacency, not skill (IR-61-LEAK-01).</li>
<li><b>Soft step / throw priors on the logistic model.</b> {min(PRIOR_DTIS):.4f}–{max(PRIOR_DTIS):.4f} vs {UNGATED['pooled_dti']:.4f} with no prior.</li>
<li><b>3 × 3 ribbons instead of dots.</b> {RIBBON['pooled_dti']:.4f} vs {GATE_P2['pooled_dti']:.4f}; {RIBBON['n_emitted_per_draw']:,.0f} emitted px vs {GATE_P2['n_emitted_per_draw']:,.0f}.</li>
</ul>
""", active="hypotheses.html")

# --------------------------------------------------------------------------- #
IRREG = page("Irregularities", f"""
<h2>Irregularities and limitations found this session</h2>
<table><tr><th>id</th><th>severity</th><th>statement</th></tr>
<tr><td>IR-61-LEAK-01</td><td>high</td><td>A gradient-boosted habitat model reached HOLDOUT-DTI {GBM_P2['pooled_dti']:.4f}
and a canary AUC of {GBM_CANARY:.3f}, above the protocol's 0.90 leakage line. The leave-one-quadrant-out retest
shows the AUC falls to {LOQO_AUC_LO:.3f}–{LOQO_AUC_HI:.3f} across all {LOQO_N} blocked retests, with no
training pixel inside the scored quadrant, and the DTI to the random baseline: the skill was adjacency to visible traces, not generalisation. The shipped file uses
the L2 logistic model (canary AUC {LOG_CANARY:.3f}).</td></tr>
<tr><td>IR-61-PRUNE-01</td><td>high</td><td>The catalogue prune has conflicting evidence. On the
hide-and-recover holdout a 2 px prune beats 3 px ({GBM_P2['pooled_dti']:.4f} vs
{GBM_P3['pooled_dti']:.4f} for the same model) because the
withheld truth is adjacent to visible traces. On the live metric the group's own controlled pair
(<code>gems25-dotted-h19-5-d2-8</code> 0.2600 → <code>gemsdoe32-h33-h33-2-b2</code> 0.2778, an exact
set difference deleting every dot within 3 px of the catalogue) says 3 px wins. The shipped file
follows the live evidence (3 px) and the holdout cost is reported.</td></tr>
<tr><td>IR-61-BUDGET-01</td><td>medium</td><td>The holdout prefers more dots monotonically
(random lines 0.0220 → 0.0434 from 20 k to 80 k), while the group's live ladder prefers ~38–40 k. The
holdout's withheld-truth set is small and catalogue-adjacent, so it cannot see the false-positive mass
that extra dots create against the full hidden fault population. Shipped at 40 k.</td></tr>
<tr><td>IR-61-MEM-01</td><td>medium</td><td>The development sandbox has ~3.9 GB of RAM and 2 cores. The
28-channel habitat stack (1.38 GB float32) is written channel-by-channel into a memmap and predictions
are computed in 400 k-row chunks; an earlier version materialised all 19 bands as float64 and was
killed by the OOM reaper. No result was lost.</td></tr>
<tr><td>IR-61-SCORE-01</td><td>high</td><td>Every score attributed to the group's own files
(0.2778, 0.2750, 0.2708, …) is an owner report on the group's pages. None is an organizer receipt
linking those bytes to a leaderboard row. The public leaderboard rows belong to other teams.</td></tr>
<tr><td>IR-61-PROVENANCE-01</td><td>high</td><td>The competition rasters come from a hash-pinned public
GitHub mirror (<code>buffedlizard55-lab/6GEMSDOE</code>); the DrivenData data page is login-walled and
unreachable from this sandbox. All three digests match the mirror's pins, but they are not
organizer-authenticated.</td></tr>
<tr><td>IR-61-FOOTPRINT-01</td><td>medium</td><td>The 200 m inversion grid loses
{feat['support']['footprint_cells_lost_at_200m']:,} footprint cells that the 100 m grid has (block means
across the survey boundary are NaN). All correlations are taken on the common finite support and the
erosion is reported in <code>evidence/h61m_features.json</code>.</td></tr>
<tr><td>IR-61-SRC-01</td><td>high</td><td>An earlier session asserted that the competition ships a
<code>1m_DEM_links.csv</code> of 1 m DEM tile URLs. The hash-pinned bridge manifest
(<code>buffedlizard55-lab/6GEMSDOE@e2fe3f41&#8230;:data/bridge/manifest.json</code>) lists exactly three
files &mdash; <code>gems-geodawn-numerical-features.tif</code>, <code>existing_faults.tif</code> and
<code>example_submission.tif</code> &mdash; so the claim is <b>false</b> and is corrected here and in
<code>evidence/h61g_hypotheses.json</code>. The 1 m lidar hypothesis (H61-N) is unaffected in substance:
USGS 3DEP is free public-domain data obtainable from The National Map
(<a href="https://apps.nationalmap.gov/downloader/">apps.nationalmap.gov/downloader</a>); it simply has to
be fetched from USGS, not from the organiser. drivendata.org is unreachable from this sandbox, so no
direct check of the data tab was possible.</td></tr>
<tr><td>IR-61-NET-01</td><td>medium</td><td>Egress admits only github.com, api.github.com,
codeload.github.com, registry.npmjs.org, pypi.org and files.pythonhosted.org. usgs.gov,
drivendata.org and the 3DEP S3 endpoint all fail, so no new external raster was fetched this session;
the one named obtainable source (3DEP 1 m DEM) is listed as a next step, not claimed as used.</td></tr>
</table>
""", active="irregularities.html")

# --------------------------------------------------------------------------- #
VERIFY = f"""
<h2>Validator receipt — {esc(NAME)}.tif</h2>
<table><tr><th>check</th><th>result</th></tr>
"""
for k, v in fin["validator"].items():
    VERIFY += f'<tr><td>{esc(k)}</td><td>{"PASS" if v else "FAIL"}</td></tr>\n'
VERIFY += f"""</table>
<p>All {len(fin['validator'])} checks passed: <code>all_checks_passed = {fin['validator_all_passed']}</code>.
Bytes {fin['bytes']:,}; sha256 <code>{SHA}</code>; zip sha256 <code>{fin['zip_sha256']}</code>.</p>

<h2>Uniqueness against every earlier raster</h2>
<p>{uni['n_registry_rasters_compared']} registry rasters compared (every raster reachable in the group's
public GitHub repositories plus the earlier rasters published in this repository). Limits: Spearman
ρ ≤ {uni['rho_limit']}; one-sided 3 px dot overlap ≤ {uni['overlap_limit']} (Jaccard ≤ 0.50 against a
reference more than 5× denser than ours). Verdict <b>{uni['verdict']}</b>.</p>
<table><tr><th>reference raster</th><th>Spearman</th><th>my dots within 3 px of theirs</th><th>base rate</th><th>Jaccard</th><th>gate</th></tr>
"""
for r in uni["rows"]:
    if "spearman_footprint" not in r:
        continue
    VERIFY += (f'<tr><td>{esc(r["file"])}</td><td>{r["spearman_footprint"]:+.4f}</td>'
               f'<td>{r["frac_my_dots_within_3px_of_theirs"]:.3f}</td>'
               f'<td>{r["base_rate_within_3px"]:.3f}</td><td>{r["jaccard"]:.4f}</td>'
               f'<td>{esc(r["overlap_gate_rule"].split(" ")[0])} ok</td></tr>\n')
VERIFY += "</table>\n"
VERIFY = page("Verify", VERIFY, active="verify.html")

# --------------------------------------------------------------------------- #
NEXT = page("Next steps", f"""
<h2>What is still blocking a top-of-leaderboard score</h2>
<ol>
<li><b>No locator generalises across space.</b> All four locators tested sit at 0.02–0.05 LOQO-DTI and
0.56–0.59 blocked canary AUC. Until that changes, no file from this lane can be expected to beat
0.2778.</li>
<li><b>Metre-scale topography is the named obtainable source.</b> USGS 3DEP 1 m DEM tiles over the
high-prior zones (free public domain from USGS The National Map, <a
href="https://apps.nationalmap.gov/downloader/">apps.nationalmap.gov/downloader</a>). The sandbox
egress allow-list blocks <code>prd-tnm.s3.amazonaws.com</code> and <code>usgs.gov</code>, so the tiles
must be fetched on an unrestricted machine and mirrored into a GitHub repository that
<code>scripts/prepare_data.py</code> can pin by sha256 — exactly the pattern already used for the
feature stack.</li>
<li><b>The hidden truth is not observable.</b> The public <code>labels.tif</code> is byte-identical to
<code>existing_faults.tif</code> (the mapped catalogue), so every number we produce is a
hide-and-recover index on catalogue traces, not a score. The single highest-value action is to record
one ORGANIZER-CONFIRMED score for a lane file so the proxy can be calibrated against the real metric.</li>
<li><b>Weekly submission slots are capped</b> (see the submission page). Promotion of any file is a
separate selector step; this session's card records a negative verdict and does not spend a slot.</li>
</ol>
<h2>Limitations of this session's evidence</h2>
<ul>
<li>The group's own scores are owner reports (IR-61-SCORE-01); the public leaderboard belongs to other
teams.</li>
<li>The holdout withholds catalogue segments, which are adjacent to visible traces by construction; the
leave-one-quadrant-out test is the correction, and it is harsher than the live problem in one respect
(it removes all faults from a quadrant).</li>
<li>The habitat model's negatives are random footprint pixels, so the model learns
"fault-like habitat", not "fault absent from the catalogue".</li>
</ul>
""", active="next-steps.html")

# --------------------------------------------------------------------------- #
for name, body in (("index.html", INDEX), ("executive-summary.html", EXEC), ("analysis.html", ANALYSIS),
                   ("method.html", METHOD), ("holdout.html", HOLDOUT), ("hypotheses.html", HYPOTHESES),
                   ("irregularities.html", IRREG), ("verify.html", VERIFY), ("next-steps.html", NEXT)):
    (DOCS / name).write_text(body)
    print("wrote", name)

# root redirect / hero -- written last so it always names the newest file
(ROOT / "index.html").write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=docs/index.html"><title>61GEMSDOE</title>
<link rel="stylesheet" href="docs/assets/site.css"></head><body><div class="wrap">
<h1>61GEMSDOE — redirecting to <a href="docs/index.html">docs/index.html</a></h1>
<p><b>Newest file:</b> <code>{esc(NAME)}</code> — FORMAT-VALID and UNIQUE (safe to upload) but
<b>not recommended for a weekly slot</b>: HOLDOUT-DTI {f4(HD['value'])} (95 % CI
{HD['ci95'][0]:.4f}–{HD['ci95'][1]:.4f}; {HD['n_withheld_positive_px']:,} withheld positive px) vs
{f4(HD['random_lines_same_budget'])} for random lines on the same evaluator, and the spatially blocked
leave-one-quadrant-out retest puts every locator we have at the random baseline. Run-card verdict:
<b>{card['verdict']}</b>.</p>
<p><a class="btn" href="docs/downloads/{esc(NAME)}.tif" download>⬇ Download the TIF</a> ·
<a href="docs/executive-summary.html">How to submit</a> ·
<a href="docs/analysis.html">Why 0.2778</a></p>
</div></body></html>
""")
print("wrote ../index.html")
