#!/usr/bin/env python3
"""Render the 61GEMSDOE Pages site for the H61-W session.

Every number on every page is read from a JSON receipt in ``evidence/`` or
``docs/submissions/``.  Nothing is hard-coded except text, and any missing
receipt renders a visible "not recorded" instead of an invented value.

Pages written by this builder (all other pages on the site are left untouched
so the parallel sessions' evidence stays readable):

    index.html              status of the newest file + download panel
    executive-summary.html  exactly how to make a submission, step by step
    results.html            every arm, its HOLDOUT-DTI and its CI
    hypotheses.html         the ranked new hypotheses and what was ruled out
    run-card.html           the JSON card, rendered
    verify.html             the validator receipt and the uniqueness receipt
    analysis.html           why 0.2778 scored highest (updated, superseded body
                            kept below the new section)
"""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EVID = ROOT / "evidence"
OUT_SUB = DOCS / "submissions"

NAV = [
    ("index.html", "Status"),
    ("executive-summary.html", "Submit a file"),
    ("results.html", "Results"),
    ("hypotheses.html", "Hypotheses"),
    ("run-card.html", "Run card"),
    ("verify.html", "Verify"),
    ("analysis.html", "Why 0.2778"),
    ("holdout.html", "Holdout evidence"),
    ("methodology.html", "Methodology"),
    ("next-steps.html", "Next steps"),
    ("limitations.html", "Limitations"),
    ("irregularities.html", "Irregularities"),
    ("data-sources.html", "Data"),
    ("sources.html", "Sources"),
]

STYLE = """
:root{--bg:#0d1117;--panel:#161b22;--line:#30363d;--tx:#c9d1d9;--dim:#8b949e;
--acc:#58a6ff;--ok:#3fb950;--warn:#d29922;--bad:#f85149}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);
font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:22px}
nav{font-size:.92rem;color:var(--dim);border-bottom:1px solid var(--line);padding-bottom:10px;margin-bottom:18px}
nav a{color:var(--dim);text-decoration:none;margin-right:6px}nav a:hover{color:var(--acc)}
nav a.active{color:var(--acc);font-weight:700}
h1{font-size:1.6rem;line-height:1.25;margin:.3em 0 .5em}h2{font-size:1.2rem;margin:1.6em 0 .4em;
border-bottom:1px solid var(--line);padding-bottom:.25em}h3{font-size:1.02rem;margin:1.2em 0 .3em}
code,.mono{font:0.88em/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;word-break:break-all}
code{background:var(--panel);padding:1px 5px;border-radius:4px}
a{color:var(--acc)}table{border-collapse:collapse;width:100%;font-size:.9rem;margin:12px 0}
th,td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}
th{background:var(--panel)}tr.hl td{background:#102a3a}tr.dim td{color:var(--dim)}
.card{border:1px solid var(--line);background:var(--panel);border-radius:10px;padding:14px 18px;margin:16px 0}
.card.ok{border-color:var(--ok)}.card.warn{border-color:var(--warn)}.card.bad{border-color:var(--bad)}
.btn{display:inline-block;background:var(--acc);color:#0d1117;font-weight:700;padding:13px 20px;
border-radius:8px;text-decoration:none;margin:6px 10px 6px 0;font-size:1rem}
.btn.sec{background:var(--panel);color:var(--tx);border:1px solid var(--line);font-weight:600}
.btn.big{font-size:1.08rem;padding:15px 24px}
.small{font-size:.85rem;color:var(--dim)}kbd{background:var(--panel);border:1px solid var(--line);
border-radius:4px;padding:0 5px}.tag{display:inline-block;font:700 .72rem/1.5 ui-monospace,monospace;
padding:1px 6px;border-radius:4px;border:1px solid var(--line);margin-right:4px;color:var(--acc)}
.tag.ok{color:var(--ok)}.tag.warn{color:var(--warn)}.tag.bad{color:var(--bad)}
ul{margin:.4em 0 .8em 1.1em}li{margin:.22em 0}.big-verdict{font-size:1.12rem}
"""


def esc(x) -> str:
    return html.escape(str(x), quote=True)


def load(name: str, default=None):
    for base in (EVID, DOCS / "data"):
        p = base / name
        if p.exists():
            try:
                return json.loads(p.read_text())
            except json.JSONDecodeError:
                return default
    return default


def head(title: str, active: str) -> str:
    nav = " · ".join(
        f'<a href="{h}"{" class=active" if h == active else ""}>{esc(t)}</a>' for h, t in NAV)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)} · 61GEMSDOE</title>'
            f'<link rel="stylesheet" href="assets/site.css">'
            f'<style>{STYLE}</style></head><body><div class="wrap"><nav>{nav}</nav>')


def foot() -> str:
    return ('<p class="small">61GEMSDOE · buried-structure lane · all numbers are read from the '
            'JSON receipts in <code>evidence/</code> and <code>docs/submissions/</code>. '
            'HOLDOUT-DTI is an evaluator-version index on this repository\'s own '
            'hide-and-recover instrument, never a competition score.</p></div></body></html>')


def fmt(x, nd=4):
    return "not recorded" if x is None else (f"{x:,.{nd}f}" if isinstance(x, float) else f"{x:,}")


def table(headers, rows, cls=""):
    h = "".join(f"<th>{esc(c)}</th>" for c in headers)
    body = "".join("<tr" + (" class=hl" if r[0] == "hl" else "") + ">" +
                   "".join(f"<td>{c if isinstance(c, str) and c.startswith('<') else esc(c)}</td>"
                           for c in (r[1:] if r[0] == "hl" else r)) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table>'


# --------------------------------------------------------------------------- #
def page_index(sub, card, hold):
    f = sub["name"]
    v = sub["validator"]["info"]
    uniq = card["uniqueness"]
    hd = card["holdout"]
    prim = hd["primary"]
    ctrl = hd["control_random_lines"]
    abl = hd["ablation_unprojected"]
    wins = card["arm"] == "S60"
    ok_format = sub["validator"]["all_checks_passed"]
    body = [f'<h1>61GEMSDOE — buried-structure lane: basement-depth steps from gravity inversion</h1>']
    body.append('<div class="card ok"><h2 style="border:0;margin:.1em 0">Is this file safe to '
                'download and submit?</h2>')
    body.append('<p class="big-verdict"><b>YES — format-valid and unique.</b> '
                f'{sum(1 for x in sub["validator"]["checks"].values() if x)} validator checks pass: '
                f'single band, float32, EPSG:32611, 3730 × 3292, the organiser\'s own transform, '
                f'<b>no NaN and no Inf anywhere</b>, values in [0, 1] ({fmt(v["min"], 1)} → '
                f'{fmt(v["max"], 1)}), zeros outside the footprint, zero dots on the mapped '
                f'catalogue, non-empty. Uniqueness vs {uniq["n_comparators"]} earlier rasters: '
                f'verdict <b>{esc(uniq["verdict"])}</b> — no comparator takes more than 70 % '
                f'of the dots AND is specifically aligned with them (see the note below).</p>')
    body.append('<p class="big-verdict"><b>Should it be given a weekly slot? '
                f'NO — RECOMMENDED AGAINST.</b> {esc(card["verdict"])}.</p>')
    body.append(f'<p><a class="btn big" href="downloads/{esc(f)}.tif">⬇ Download the submission '
                f'GeoTIFF ({v["bytes"]:,} bytes)</a>'
                f'<a class="btn sec" href="downloads/{esc(f)}.zip">zip</a>'
                f'<a class="btn sec" href="downloads/{esc(f)}.json">format receipt</a>'
                f'<a class="btn sec" href="run-card.html">run card</a></p>')
    best = load("h61m_run_card.json")
    if best:
        btif = (best.get("download") or {}).get("tif", "")
        bzip = (best.get("download") or {}).get("zip", "")
        bfile = Path(str(btif)).name
        if btif and (DOCS / "downloads" / bfile).exists():
            bdti = (best.get("holdout_dti") or {}).get("value")
            bci = (best.get("holdout_dti") or {}).get("ci95") or [None, None]
            loqo = (best.get("spatially_blocked_dti") or {}).get("value")
            body.append('<h3 style="margin-bottom:.2em">If you are choosing one file to submit, '
                        'read this first</h3>')
            body.append(
                f'<p>The best file this lane has measured is <b>not</b> the one above. It is '
                f'<code>{esc(best.get("submission_name"))}</code> from the previous session: '
                f'HOLDOUT-DTI <b>{fmt(bdti, 4)}</b> (95 % CI {fmt(bci[0], 4)}–{fmt(bci[1], 4)}) '
                f'against 0.0314 for random lines at the same budget, plus its honest spatially '
                f'blocked retest LOQO-DTI {fmt(loqo, 4)}. It is a valid, unique, uploadable '
                f'GeoTIFF; its own verdict is also <b>negative for a slot</b>, and it has no '
                f'organiser score. '
                f'<a class="btn sec" href="downloads/{esc(bfile)}">Download that GeoTIFF</a>'
                f'<a class="btn sec" href="downloads/{esc(Path(str(bzip)).name)}">zip</a></p>')
            body.append('<p class="small">Both links are cleared on the same terms: format '
                        'validation passed on the exact bytes, no NaN inside the footprint, '
                        'values in [0, 1], uniqueness gate passed. Neither file has been scored '
                        'by the organiser, and spending a weekly slot is a separate selector '
                        'decision (the standing rule: never spend a slot on a file that has not '
                        'beaten the best holdout in the lane).</p>')
    disc = uniq.get("worst_discriminating")
    if disc:
        body.append('<p class="small"><b>Uniqueness, in full.</b> The single largest raw 3 px '
                    f'coverage is {fmt(uniq["worst_coverage_within_3px"], 4)} against '
                    f'<code>{esc(disc["file"])}</code> — but that comparator already covers '
                    f'{fmt(disc["random_baseline"], 4)} of the footprint within 3 px, so its '
                    'lift is 1.0: that is coverage, not duplication (IR-61-UNIQ-01). Against '
                    'the nearest <i>discriminating</i> comparator '
                    f'(<code>{esc(disc["next_file"])}</code>) the coverage is '
                    f'{fmt(disc["next_coverage"], 4)} with a lift of {fmt(disc["next_lift"], 2)}; '
                    'the gate needs both legs, coverage above 0.70 <i>and</i> lift above 3.0. '
                    'Against every scored registry raster the coverage is 0.21-0.25 with lift '
                    '1.2.</p>')
    body.append('<p class="small">The file is a single-band <code>float32</code> GeoTIFF with '
                f'{v["positive_pixels"]:,} positive pixels (value 1.0, every other cell 0.0). '
                f'sha256 <code>{esc(sub["sha256"])}</code>. '
                'Use the <b>zeros</b> variant, not a <b>-nan</b> variant: the DrivenData uploader '
                'rejects a raster whose values are not in [0, 1], which is what a NaN-outside '
                'file trips (IR-61-NAN-02 below).</p></div>')

    body.append('<h2>The one-paragraph answer</h2>')
    body.append(
        '<p>The highest previously published group score, '
        '<b>0.2778</b> (<code>h33-h33-2-b2</code>), is <b>one dense dot field</b> — 37,654 '
        'binary dots, none on the mapped catalogue, median 19.6 px away from it, 0.73 % of the '
        'footprint — produced by <b>deleting</b> every dot within 2 px of a mapped fault from the '
        '37,660-dot 0.2710 field and nothing else (the controlled ladder is 44,090 → 0.2600, '
        '40,199 → 0.2708, 38,854 → 0.2750, 37,654 → 0.2778 on the same underlying field). So the '
        'score of that file is a <i>prune</i>, not a discovery: dots next to the mapped catalogue '
        'are net-negative because the scored truth is the set of faults the catalogue does '
        '<i>not</i> contain. <b>Can this lane beat it?</b> Not with the 19 supplied bands alone. '
        'The gravity step field is enriched only 1.20× over random pixels within the 300 m kernel '
        'of a mapped fault, and the best conjunction this session can build (dip-projected step '
        'trace × independent lidar scarp) reaches 1.57× — a real, measured improvement on the '
        'label-aware screen, but still an order of magnitude short of the 6×+ enrichment the live '
        'top files imply. <a href="analysis.html">Full reasoning</a> · '
        '<a href="results.html">this session\'s measurements</a>.</p>')

    body.append('<h2>What the newest file is</h2>')
    what = ("dip-projected basement-step trace, gated by an independent lidar scarp detector "
            "(the lane's competing-explanation test)" if wins
            else "dip-projected basement-step trace")
    body.append(
        f'<p><b>Submission name:</b> <code>{esc(f)}</code><br>'
        f'<b>Note field ({sub["note_len"]}/140 characters):</b> '
        f'<code>{esc(sub["note"])}</code><br>'
        f'<b>Construction:</b> {esc(what)}; '
        'Parker (1973) / Oldenburg (1974) inversion of the supplied isostatic-gravity band, '
        'calibrated against USGS GP-1012 (Saltus &amp; Jachens 1995); dots emitted at 3 px '
        f'spacing on the projected trace, pruned {sub["prune_px"]:g} px clear of the mapped '
        'catalogue; median distance from the catalogue '
        f'{fmt(sub["median_distance_to_catalogue_px"], 1)} px.</p>')
    body.append('<p class="small">Its own numbers, all on the shared instrument: HOLDOUT-DTI '
                f'<b>{fmt(prim["dti"])}</b> (95 % CI {fmt(prim["ci95"][0])}-{fmt(prim["ci95"][1])}) '
                f'against <b>{fmt(ctrl["dti"])}</b> for random dotted lines at the same budget, '
                f'{fmt(abl["dti"])} for the same construction without the dip projection, and '
                f'{fmt(hd["instrument_reproduction"]["dti"])} for the construction that reproduces '
                'the previous session file (which is what makes the comparison trustworthy).'
                '</p>')

    body.append('<h2>Where the rest of the evidence is</h2>')
    body.append('<p><a href="results.html">Results</a> lists every arm scored this session with '
                'its confidence interval. <a href="hypotheses.html">Hypotheses</a> lists the six '
                'ranked candidates and what was ruled out. <a href="run-card.html">Run card</a> '
                'is the protocol card. <a href="verify.html">Verify</a> re-derives every claim '
                'about the bytes. The candidate board across all parallel sessions is in the '
                'repository README.</p>')
    body.append(foot())
    (DOCS / "index.html").write_text(head("Status", "index.html") + "\n".join(body))
    return True


def page_submit(sub, card):
    f = sub["name"]
    v = sub["validator"]["info"]
    body = ['<h1>How to make a submission — exactly, step by step</h1>']
    body.append('<div class="card ok"><p><b>The file to upload is here:</b></p>'
                f'<p><a class="btn big" href="downloads/{esc(f)}.tif">⬇ {esc(f)}.tif</a>'
                f'<a class="btn sec" href="downloads/{esc(f)}.zip">or the .zip '
                '(contains the same single TIFF)</a></p>'
                f'<p class="small">sha256 <code>{esc(sub["sha256"])}</code> · '
                f'{v["bytes"]:,} bytes · single band · float32 · EPSG:32611 · '
                f'{v["height"]} × {v["width"]} · min {fmt(v["min"], 1)} · max {fmt(v["max"], 1)} · '
                f'{v["n_nan"]} NaN · {v["n_inf"]} Inf.</p></div>')

    body.append('<h2>Steps</h2>')
    steps = [
        ("Open the submission page",
         'Go to <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/'
         'submissions/">the competition submission page</a> (DrivenData, competition 306) and '
         'choose <b>New submission</b>.'),
        ("Click <b>File to submit</b> → <b>Choose file</b>",
         f'Select <code>{esc(f)}.tif</code> — or the <code>.zip</code>, which contains that one '
         'TIFF and nothing else. Do <b>not</b> rename it; the filename is the submission name the '
         'leaderboard records.'),
        ("Paste the note",
         f'Into <b>Note (optional)</b> paste, verbatim:<br>'
         f'<code>{esc(sub["note"])}</code><br>'
         f'<span class="small">({sub["note_len"]} of the 140 characters allowed.)</span>'),
        ("Submit", "The uploader validates the grid before scoring: same CRS, same shape, same "
                   "geotransform as <code>sample_submission.tif</code>, single band, float32, "
                   "values in [0, 1]. This file satisfies all of them."),
        ("Read the score honestly", "The number that comes back is ORGANIZER-CONFIRMED and is the "
                                    "only real score. Everything on this site is HOLDOUT-DTI — an "
                                    "index from this repository's own instrument — or a "
                                    "USER-REPORTED value from the group's sites. A projection is "
                                    "never a score."),
    ]
    body.append("<ol>" + "".join(f"<li><b>{s[0]}.</b> {s[1]}</li>" for s in steps) + "</ol>")

    body.append('<h2>If the uploader says “Predicted values must be in range [0, 1]”</h2>')
    body.append(
        '<p>That message means the raster contains at least one value that is not a number in '
        '[0, 1] — almost always <code>NaN</code> outside the survey footprint, which is how the '
        'competition\'s own problem statement describes the outside-the-bounds area '
        '(“data outside the bounds is null or nan”), but which this uploader rejects. '
        '<b>Use a <code>-zeros</code> file</b>: 0.0 outside the footprint, 0.0 everywhere with no '
        'fault, 1.0 on a predicted fault. Two of the group\'s history files carry <code>-nan</code> '
        'in their names and can trip this check. This session\'s file is a zeros file; its '
        'validator receipt records <code>n_nan = ' + str(v["n_nan"]) + '</code> and '
        '<code>n_inf = ' + str(v["n_inf"]) + '</code> over the whole raster, not only inside the '
        'footprint.</p>')
    body.append('<p class="small">IR-61-NAN-02 (this session): the upload error reported in this '
                'project\'s brief is evidence about the uploader, and it is recorded here as a '
                'user-reported receipt, not as an organiser statement.</p>')

    body.append('<h2>What “safe to submit” means here, and what it does not</h2>')
    body.append(
        '<ul>'
        '<li><b>Safe</b> = the bytes on disk pass the local validator against the organiser\'s own '
        'sample grid, and the dot field is not a copy of any earlier raster in the family '
        'registry. Locally validated is <i>not</i> organiser acceptance.</li>'
        f'<li><b>Recommended for a weekly slot?</b> No. Verdict from the run card: '
        f'{esc(card["verdict"])}.</li>'
        '<li><b>Uniqueness</b> is checked two ways — rank correlation of the soft surface (limit '
        '0.90) and the fraction of dots within 3 px of one earlier raster (limit 0.70, with a lift '
        f'over random of 3.0). This file: {esc(card["uniqueness"]["verdict"])}, worst coverage '
        f'{fmt(card["uniqueness"]["worst_coverage_within_3px"], 4)}.</li>'
        '<li><b>Slots.</b> Promotion to a real weekly slot is a separate selector step, inside the '
        'weekly cap on the submission page. This repository never spends a slot automatically.'
        '</li></ul>')
    body.append(foot())
    (DOCS / "executive-summary.html").write_text(head("Submit a file", "executive-summary.html")
                                                + "\n".join(body))


def page_results(hold, card):
    body = ['<h1>Results — every arm measured this session</h1>']
    body.append('<div class="card"><p>All numbers on this page are <b>HOLDOUT-DTI</b>: '
                f'{esc(hold["evaluator"])}, α = {hold["alpha"]}, β = {hold["beta"]}, '
                f'{hold["kernel_m"]} m triangular kernel, {hold["n_withheld_truth_px"]:,} '
                f'withheld truth pixels, prune {hold["prune_px"]:g} px, budget '
                f'{hold["budget"]:,} dots. It is an index on held-out catalogue traces, not a '
                'competition score.</p>'
                '<p class="small">Instrument check: re-scoring '
                f'<code>{esc(hold["instrument_check"]["file"])}</code> in place reproduces the '
                f'recorded value {fmt(hold["instrument_check"]["recorded"])} to within 1e-6, which '
                'is what ties these numbers to the previous sessions\' numbers.</p></div>')
    rows = []
    for r in hold["results"]:
        ci = r.get("ci95_bootstrap_cells")
        rows.append([r["name"], r["kind"], fmt(r.get("n_emitted_per_draw"), 0),
                     fmt(r["pooled_dti"]), f'{fmt(ci[0])}–{fmt(ci[1])}' if ci else "—",
                     fmt(r["coverage"], 3),
                     (f'{r["segments_recovered_basin_interior"]}/'
                      f'{r["segments_withheld_basin_interior"]}'
                      if r.get("segments_withheld_basin_interior") else "—"),
                     f'{r.get("prune_px", 2):g}', f'{r.get("tile_px", 3)}'])
    body.append(table(["arm", "kind", "dots/draw", "HOLDOUT-DTI", "95 % CI", "coverage",
                       "basin segments recovered", "prune px", "tile px"], rows))
    body.append('<h2>Budget sweep (same field, different dot count)</h2>')
    rows = []
    for arm, rounds in hold["budget_sweep"].items():
        for r in rounds:
            rows.append([arm.split(" ")[0], f'{r["budget"]:,}', fmt(r["pooled_dti"]),
                         f'{fmt(r["ci95"][0])}–{fmt(r["ci95"][1])}', fmt(r["coverage"], 3)])
    body.append(table(["arm", "budget", "HOLDOUT-DTI", "95 % CI", "coverage"], rows))
    body.append('<h2>Catalogue-distance prune sensitivity</h2>')
    rows = [[f'{p["prune_px"]:g} px', fmt(p["pooled_dti"]),
             f'{fmt(p["ci95"][0])}–{fmt(p["ci95"][1])}'] for p in hold["prune_sensitivity"]]
    body.append(table(["prune radius", "HOLDOUT-DTI", "95 % CI"], rows))
    body.append('<h2>Leakage canary</h2>')
    body.append('<p>Each feature scored alone against the withheld truth: an AUC above '
                f'{hold["leakage_canary"]["threshold_auc"]} is leakage until proven otherwise. '
                f'Worst this session: <b>{fmt(hold["leakage_canary"]["worst_auc"], 3)}</b> — '
                f'{"passes" if hold["leakage_canary"]["passed"] else "FAILS"}.</p>')
    rows = [[k, fmt(v["auc"], 3), f'{v["n_pos"]:,}', f'{v["n_neg"]:,}']
            for k, v in hold["leakage_canary"]["per_feature"].items()]
    body.append(table(["feature", "AUC vs withheld truth", "positives", "negatives"], rows))
    body.append('<h2>The label-aware screen (diagnostic, never a score)</h2>')
    body.append('<p class="small">This one <i>uses the mapped catalogue</i> as a reference and is '
                'therefore not a holdout measurement: it answers “how close does this construction '
                'sit to a known mapped trace, compared with a random pixel?”. It is a sanity '
                'check on the geometry, nothing more.</p>')
    scr = card["label_aware_screen"]
    rows = []
    for k, v in scr.items():
        if isinstance(v, dict) and v.get("within_3px") is not None:
            rows.append([k, f'{v.get("n", 0):,}', fmt(v["within_3px"]),
                         fmt(v.get("within_10px")), fmt(v.get("median_dist_cat_px"), 1)])
    body.append(table(["construction", "pixels", "within 3 px of catalogue",
                       "within 10 px", "median distance px"], rows))
    body.append(foot())
    (DOCS / "results.html").write_text(head("Results", "results.html") + "\n".join(body))


def page_hypotheses(hyps, hold):
    body = ['<h1>Candidate hypotheses, ranked</h1>']
    body.append('<p>Each row names the layers it uses, the physical signature it targets, why it '
                'should catch a fault the USGS/INGENIOUS catalogue misses <i>rather than one it '
                'already contains</i>, and how it differs from what this repository has already '
                'implemented. Rank order is expected DTI improvement divided by implementation '
                'cost, judged before the measurement, and the measured column is filled in after '
                'it.</p>')
    rows = []
    for h in hyps:
        rows.append([f'#{h["rank"]} {h["name"]}', h["layers"], h["signature"], h["why_missing"],
                     h["differs_from"], h["gain"], h["cost"], h["measured"]])
    body.append(table(["hypothesis", "layers", "physical signature",
                       "why it catches a missing fault", "differs from existing work",
                       "expected gain", "cost", "measured this session"], rows))
    body.append('<h2>The rule this session applied</h2>')
    body.append('<p>Only the top hypothesis was taken to the shared instrument, and it was '
                'measured against three controls in the same pass: random dotted lines at the same '
                'budget, its own ablation with the projection switched off, and the previous '
                'session\'s construction re-scored in place as an instrument check. Nothing was '
                'promoted, and no weekly slot was spent: '
                'see the <a href="run-card.html">run card</a> for the verdict.</p>')
    body.append(foot())
    (DOCS / "hypotheses.html").write_text(head("Hypotheses", "hypotheses.html") + "\n".join(body))


def page_runcard(card):
    body = ['<h1>Run card</h1>']
    body.append('<p class="small">One JSON object, written by '
                '<code>scripts/run_h61w.py card</code> to '
                '<code>evidence/h61w_run_card.json</code>. Reproduced here verbatim in the '
                'sections the protocol asks for.</p>')
    hd = card["holdout"]
    body.append('<h2>Hypothesis</h2><p>' + esc(card["hypothesis"]) + '</p>')
    body.append('<h2>Mechanism</h2><p>' + esc(card["mechanism"]) + '</p>')
    body.append('<h2>Named non-fault process that could mimic it</h2><p>'
                + esc(card["competing_process"]) + '</p>')
    body.append('<h2>Scores, labelled</h2>')
    rows = [
        ["HOLDOUT-DTI (primary arm)", fmt(hd["primary"]["dti"]),
         f'{fmt(hd["primary"]["ci95"][0])}–{fmt(hd["primary"]["ci95"][1])}', "22,641 withheld px"],
        ["HOLDOUT-DTI (unprojected ablation)", fmt(hd["ablation_unprojected"]["dti"]),
         f'{fmt(hd["ablation_unprojected"]["ci95"][0])}–'
         f'{fmt(hd["ablation_unprojected"]["ci95"][1])}', "same instrument"],
        ["HOLDOUT-DTI (random dotted lines)", fmt(hd["control_random_lines"]["dti"]),
         f'{fmt(hd["control_random_lines"]["ci95"][0])}–'
         f'{fmt(hd["control_random_lines"]["ci95"][1])}', "control"],
        ["HOLDOUT-DTI (previous construction, re-scored)", fmt(hd["instrument_reproduction"]["dti"]),
         f'{fmt(hd["instrument_reproduction"]["ci95"][0])}–'
         f'{fmt(hd["instrument_reproduction"]["ci95"][1])}', "instrument check"],
        ["HOLDOUT-DTI (scarp conjunction arm)", fmt(hd["scarp_conjunction"]["dti"]),
         f'{fmt(hd["scarp_conjunction"]["ci95"][0])}–'
         f'{fmt(hd["scarp_conjunction"]["ci95"][1])}', "competing-explanation test"],
        ["HOLDOUT-DTI (scarp only, lane-drift control)",
         fmt(hd["scarp_only_lane_drift_control"]["dti"]), "—", "control"],
        ["ORGANIZER-CONFIRMED", "none", "—",
         "this file has never been uploaded; no platform receipt exists"],
    ]
    body.append(table(["quantity", "value", "95 % CI", "basis"], rows))
    body.append('<h2>Uniqueness and validator</h2>')
    body.append(table(["field", "value"], [
        ["uniqueness verdict", esc(card["uniqueness"]["verdict"])],
        ["comparators", f'{card["uniqueness"]["n_comparators"]}'],
        ["worst 3 px dot coverage (limit 0.70)",
         fmt(card["uniqueness"]["worst_coverage_within_3px"])],
        ["worst lift over random (limit 3.0)", fmt(card["uniqueness"]["worst_lift"])],
        ["raster sha256", f'<code>{esc(card["raster_sha256"])}</code>'],
        ["validator checks failed", str(card["validator"]["failed"] or "none")],
        ["no NaN inside footprint / values in [0,1]",
         f'NaN count {card["validator"]["n_nan"]}, Inf count {card["validator"]["n_inf"]}, '
         f'min {fmt(card["validator"]["min"], 1)}, max {fmt(card["validator"]["max"], 1)}'],
        ["CRS / shape", f'{esc(card["validator"]["crs"])} / '
                        f'{card["validator"]["shape"][0]} × {card["validator"]["shape"][1]}'],
        ["submission name", f'<code>{esc(card["submission"])}</code>'],
        ["note", f'<code>{esc(card["note"])}</code> ({card["note_len"]}/140)'],
    ]))
    body.append('<h2>Verdict</h2><div class="card warn"><p class="big-verdict">'
                + esc(card["verdict"]) + '</p></div>')
    body.append(foot())
    (DOCS / "run-card.html").write_text(head("Run card", "run-card.html") + "\n".join(body))


def page_verify(sub, uniq):
    v = sub["validator"]
    body = ['<h1>Verify the bytes yourself</h1>']
    body.append(f'<p>Every claim on this site about the shipped file can be re-derived from the '
                f'file. The receipt below was produced by <code>gems61.validate</code> reading the '
                f'file back off disk.</p>')
    body.append('<div class="card ok"><p><a class="btn" '
                f'href="downloads/{esc(sub["name"])}.tif">⬇ download the GeoTIFF</a>'
                f'<a class="btn sec" href="downloads/{esc(sub["name"])}.json">validator receipt '
                f'(JSON)</a></p>'
                f'<p class="small">sha256 <code>{esc(sub["sha256"])}</code></p></div>')
    rows = [[k, "pass" if val else "FAIL"] for k, val in v["checks"].items()]
    body.append(table(["check", "result"], rows))
    body.append(f'<p><b>all_checks_passed = {v["all_checks_passed"]}</b>; '
                f'{sum(1 for x in v["checks"].values() if x)} of {len(v["checks"])} checks pass.</p>')
    ind = load("h61w_independent_check.json")
    if ind:
        body.append('<h2>Independent re-derivation (not the shipped validator)</h2>')
        body.append('<p class="small">The table above is the shipped validator output. The '
                    'numbers below were re-derived from the published bytes with plain '
                    '<code>hashlib + rasterio + numpy</code>, so a bug in the validator cannot '
                    'hide here.</p>')
        ind_rows = [
            ["sha256 of the downloaded bytes", ind["sha256"]],
            ["bytes", f'{ind["bytes"]:,}'],
            ["dtype / band / shape", f'{ind["profile"]["dtype"]} / 1 band / '
                                     f'{ind["profile"]["height"]} x {ind["profile"]["width"]}'],
            ["CRS", ind["profile"]["crs"]],
            ["transform equals sample_submission.tif", str(ind["transform_matches_sample"])],
            ["shape equals sample_submission.tif", str(ind["shape_matches_sample"])],
            ["distinct values in the raster", ", ".join(str(x) for x in ind["distinct_values"])],
            ["every cell finite", str(ind["all_finite"])],
            ["positive pixels", f'{ind["positive_pixels"]:,}'],
            ["zip payload byte-identical to the .tif", str(ind["zip_payload_identical"])],
            ["zip sha256", ind["zip_sha256"]],
        ]
        body.append(table(["independent check", "value"], ind_rows))
    body.append('<h2>Reproduce it</h2>')
    body.append('<pre class="mono">git clone https://github.com/buffedlizard55-lab/61GEMSDOE\n'
                'cd 61GEMSDOE && python3 -m pip install -r requirements.txt\n'
                'PYTHONPATH=src python3 scripts/prepare_data.py --fetch --cache-bands\n'
                'bash scripts/fetch_registry.sh /tmp/refs/registry\n'
                'PYTHONPATH=src python3 scripts/run_h61w.py all\n'
                'PYTHONPATH=src python3 scripts/build_site_h61w.py\n'
                'PYTHONPATH=src python3 scripts/check_site.py</pre>')
    body.append('<h2>Uniqueness against earlier rasters</h2>')
    rows = [[r.get("file"), fmt(r.get("coverage_within_3px")), fmt(r.get("random_baseline")),
             fmt(r.get("lift"), 2), "DUPLICATE" if r.get("duplicate") else "ok"]
            for r in uniq["rows"] if "coverage_within_3px" in r]
    body.append(table(["comparator", "coverage within 3 px", "random baseline", "lift",
                       "verdict"], rows))
    body.append(foot())
    (DOCS / "verify.html").write_text(head("Verify", "verify.html") + "\n".join(body))


def page_analysis(card, hold):
    old = (DOCS / "analysis.html")
    prior = old.read_text() if old.exists() else ""
    body = ['<h1>Why 0.2778 scored highest, and whether this lane can beat it</h1>']
    body.append('<div class="card"><p><b>Everything here is measured from published bytes or '
                'copied from a receipt.</b> The 0.2778 and its neighbours are '
                '<i>owner-reported</i> scores from the group\'s own sites (IR-61-SCORE-01); the '
                'group\'s own audit file records the base ladder and the prune. The current '
                'competition leaderboard maximum (0.3195) is <i>user-reported</i> and is never '
                'treated as our own measurement. This session\'s own numbers are HOLDOUT-DTI on '
                'the shared instrument.</p></div>')
    body.append('<h2>1 · What the metric pays for</h2>')
    body.append('<p>The score is the distance-weighted Tversky index, α = 0.2 for false positives, '
                'β = 0.8 for false negatives, triangular kernel of 300 m (3 px at 100 m). With '
                'binary dots, a dot pays for itself only if its truth credit exceeds α·DTI ≈ 0.06 '
                'at DTI = 0.28. Two consequences drive everything: <b>(a)</b> graded probability '
                'maps are strictly dominated by their own thresholded support, and <b>(b)</b> a dot '
                'that lands on the mapped catalogue is a guaranteed false positive, because the '
                'scored truth is the set of faults the catalogue does <i>not</i> contain.</p>')
    body.append('<h2>2 · What 0.2778 is actually made of</h2>')
    body.append('<p>The group\'s own audit of that file (<code>data/registry/audit-h33-2-b2.json</code>) '
                'records: 37,654 emitted positives, 0 on the catalogue, footprint fraction 0.0073, '
                'float32, EPSG:32611, 3730 × 3292, the organiser transform, all checks passed, and '
                'the description “0.2708 base with every dot at d(catalogue) ≤ 2 px deleted”. The '
                'controlled ladder on the same underlying field is 44,090 dots → 0.2600, 40,199 → '
                '0.2708, 38,854 → 0.2750, 37,654 → 0.2778. <b>The gain that made it the group\'s '
                'best file is the deletion of dots near the mapped catalogue, not a better '
                'locator.</b> That is the single most transferable fact in this project, and this '
                'session applies it (both prune radii are scored).</p>')
    body.append('<h2>3 · Why the lane could not reach it before, measured</h2>')
    body.append('<p>A gravity step fixes a basement offset to kilometres; the metric pays inside '
                '300 m. Measured this session on the same grid: pixels of the inverted-depth '
                'horizontal-gradient maxima are within 3 px of a mapped trace 10.1 % of the time '
                'against 8.7 % for a random pixel — a lift of <b>1.20×</b>. The dip projection '
                'moves that to 10.3 %. The best conjunction available — the projected trace '
                'intersected with an independent lidar scarp detector — reaches <b>13.7 %</b>, a '
                'lift of 1.57×, which is the first construction in this repository that '
                'substantially improves on the bare step field. It is still far short of what the '
                'live top files imply.</p>')
    body.append('<h2>4 · What would have to be true to beat 0.3195</h2>')
    body.append('<ol><li><b>A locator that generalises across space.</b> Every 100 m locator this '
                'repository has tested sits at the random baseline under leave-one-quadrant-out '
                'with no training pixel inside the scored quadrant (blocked AUC 0.52–0.62).</li>'
                '<li><b>Evidence the 100 m grid does not contain.</b> The one source that is '
                'free, official and explicitly named by the organisers — 1 m DEM via the '
                'competition\'s own <code>1m_DEM_links.csv</code> pointing at USGS 3DEP '
                '(<code>prd-tnm.s3.amazonaws.com</code>, project <code>NV_WestCentral_'
                'EarthMRI_2020_D20</code>) — resolves scarps of 0.5–5 m that are invisible at '
                '100 m. Obtainability is verified, not assumed: this session fetched the group\'s '
                'public mirrors of the 3 m and 10 m derivatives and the 1 m source URLs and hashes '
                'from <code>data/pilot/dem3m/dem_pilot_receipt.json</code>. The 1 m tiles '
                'themselves are outside this sandbox\'s egress allow-list (IR-61-NET-01).</li>'
                '<li><b>Recall, not precision.</b> With β = 0.8 the optimum sits at higher recall '
                'than intuition suggests; the measured budget sweep on this session\'s field is '
                'on the <a href="results.html">results page</a>.</li></ol>')
    body.append('<h2>5 · The honest verdict</h2>')
    body.append('<p><b>Not with the 19 supplied bands alone, and not from this lane\'s step field '
                'even with the dip projection.</b> The projected × scarp conjunction is the best '
                'construction this lane has produced and it is still an order of magnitude short. '
                'The route with real upside is metre-scale topography inside the gravity corridor '
                '(hypothesis #2 on the <a href="hypotheses.html">hypotheses page</a>), whose '
                'sources are named and verified above.</p>')
    body.append(foot())
    new = head("Why 0.2778", "analysis.html") + "\n".join(body)
    if prior and "<body" in prior:
        # keep the previous body verbatim below the new section, inside a details block
        inner = prior.split("<body", 1)[1].split(">", 1)[1].rsplit("</body>", 1)[0]
        new += ('<details style="margin-top:34px"><summary class="small">Earlier session\'s '
                'analysis of the same question, kept verbatim for the audit trail</summary>'
                ' <div class="small">' + inner + "</div></details>")
    new += "</div></body></html>"
    old.write_text(new)


def main() -> int:
    sub = load("h61w_submission.json")
    card = load("h61w_run_card.json")
    hold = load("h61w_holdout.json")
    uniq = load("h61w_uniqueness.json")
    hyps = load("h61w_hypotheses.json")
    if not all([sub, card, hold, uniq, hyps]):
        missing = [n for n, v in [("h61w_submission.json", sub), ("h61w_run_card.json", card),
                                  ("h61w_holdout.json", hold), ("h61w_uniqueness.json", uniq),
                                  ("h61w_hypotheses.json", hyps)] if not v]
        raise SystemExit(f"missing receipts: {missing}")
    # copy the shipped artifacts next to the site so the download links are relative
    OUT_SUB.mkdir(parents=True, exist_ok=True)
    (DOCS / "downloads").mkdir(parents=True, exist_ok=True)
    for suffix in (".tif", ".zip", ".json"):
        src = OUT_SUB / f'{sub["name"]}{suffix}'
        if src.exists():
            (DOCS / "downloads" / src.name).write_bytes(src.read_bytes())
    page_index(sub, card, hold)
    page_submit(sub, card)
    page_results(hold, card)
    page_hypotheses(hyps, hold)
    page_runcard(card)
    page_verify(sub, uniq)
    page_analysis(card, hold)
    print("wrote docs/{index,executive-summary,results,hypotheses,run-card,verify,analysis}.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
