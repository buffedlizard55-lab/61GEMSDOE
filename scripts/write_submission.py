#!/usr/bin/env python3
"""RETIRED legacy submission writer; CLI intentionally fails closed.

This pipeline may reuse a stale ``evidence/uniqueness.json`` cache and depends
on a retired uniqueness API. It is not an authorized candidate-generation
path. Preserve implementation for provenance only; use the current run card
and strict-gated runner for any future eligible candidate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import competing, emission, evaluate_holdout as eh, gravity as gv  # noqa: E402
from gems61 import grid as gd, holdout as ho, steps as st                      # noqa: E402
from gems61 import submission_writer as sw, uniqueness as uq                   # noqa: E402

BUDGET = 40_000
THIN_PX = 1.0
OFFSETS = (0.0, 6.0, 12.0)        # the geometry the holdout selected
SIGMA_PX = 1.0                    # the smoothing scale the holdout selected
OUT_DIR = ROOT / "docs" / "submissions"


def log(msg: str) -> None:
    print(f"[sub] {msg}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--drho", type=float, default=400.0)
    ap.add_argument("--z0", type=float, default=3000.0)
    ap.add_argument("--cutoff", type=float, default=5000.0)
    ap.add_argument("--budget", type=int, default=BUDGET)
    ap.add_argument("--seed", type=int, default=61011)
    ap.add_argument("--hide-fraction", type=float, default=0.20)
    ap.add_argument("--buffer-px", type=int, default=3)
    a = ap.parse_args()

    started = time.time()
    g = gd.load_grid()
    fp = g.footprint
    log(f"grid {g.shape} footprint={int(fp.sum())} catalogue={int(g.catalogue.sum())}")

    # ------------------------------------------------------------ 1 rebuild
    b13 = np.array(gd.load_band(13))
    b2 = np.array(gd.load_band(2))
    filled = ROOT / ".cache/b13_filled.npy"
    b13f = np.load(filled) if filled.exists() else gv.inpaint(np.nan_to_num(b13),
                                                              np.isfinite(b13))
    b2p = ROOT / ".cache/b2_filled.npy"
    b2f = np.load(b2p) if b2p.exists() else gv.inpaint(np.nan_to_num(b2), np.isfinite(b2))

    relief_path = ROOT / ".cache" / f"relief_d{int(a.drho)}_z{int(a.z0)}_l{int(a.cutoff)}.npy"
    depth = -np.load(relief_path).astype(np.float32)

    s = st.detect_steps(depth, sigma_px=SIGMA_PX, half_width_px=4.0, valid=fp)
    log(f"crest px={s.n_crest} (sigma={SIGMA_PX}, L=4)")

    mag_crest = competing.magnetic_contact_crests(b2f.astype(np.float32),
                                                  sigma_grid=(2.0,), min_quantile=0.90)
    ambiguous = competing.coincidence_map(s.crest, mag_crest, tolerance_px=2.0)
    crest = s.crest & ~ambiguous
    log(f"magnetic demotion removes {int(ambiguous.sum())} px "
        f"({ambiguous.sum()/max(s.n_crest,1):.3f} of the crest)")

    rib, _ = emission.ribbon_mask(crest, offsets_px=OFFSETS)
    rib &= fp
    score = emission.nearest_crest_value(np.where(crest, s.throw, 0.0), crest) * rib
    dots = emission.thin_to_dots(rib, score, THIN_PX)
    # The organiser removes mapped faults from every term, so the shipped
    # product prunes against the WHOLE catalogue and then tops the budget back up.
    dots = emission.prune_near(dots, g.catalogue, 2)
    dots = emission.apply_budget(dots, score, a.budget)
    log(f"candidate dots={int(dots.sum())} (budget {a.budget})")

    surface = np.where(fp, s.gradient, 0.0).astype(np.float32)   # pre-placement leg
    np.save(ROOT / ".cache/surface_step_gradient.npy", surface)
    np.save(ROOT / ".cache/final_dots.npy", dots)

    # ------------------------------------------------- 2 uniqueness gate
    log("uniqueness gate (both legs, every family raster)")
    dots_sha = hashlib.sha256(np.packbits(dots).tobytes()).hexdigest()
    cached_gate = ROOT / "evidence/uniqueness.json"
    uniq = None
    if cached_gate.exists():
        prev = json.loads(cached_gate.read_text())
        n_reg = len(json.loads((ROOT / "evidence/registry_refreshed.json").read_text())["rasters"])
        if (prev.get("candidate_dots_sha256") == dots_sha
                and prev.get("n_registry_rasters") == n_reg):
            log("    identical candidate and registry: reusing the completed scan")
            uniq = prev
    if uniq is None:
        uniq = uq.check(surface, dots, fp, root=ROOT,
                        progress=lambda i, n: log(f"    {i}/{n}") if i % 100 == 0 else None)
        uniq["candidate_dots_sha256"] = dots_sha
    (ROOT / "evidence").mkdir(exist_ok=True)
    uniq["generated_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    uniq["candidate"] = dict(arm="demoted_k3_s6", positive_pixels=int(dots.sum()))
    (ROOT / "evidence/uniqueness.json").write_text(
        json.dumps(uniq, indent=2, allow_nan=False) + "\n")
    log(f"    n={uniq['n_registry_rasters']} worst_rho={uniq['worst_spearman']:.6f} "
        f"({uniq['worst_spearman_source']}) worst_overlap={uniq['worst_dot_overlap_3px']:.6f} "
        f"({uniq['worst_dot_overlap_source']}) unique={uniq['unique']}")
    if not uniq["unique"]:
        log("REFUSING TO WRITE: the candidate trips the uniqueness drift gate")
        return 2

    # ------------------------------------------------- 3 holdout, conservative
    folds = ho.make_folds(g.catalogue, fp, fraction=a.hide_fraction,
                          buffer_px=a.buffer_px, seed=a.seed)
    hidden = np.zeros(fp.shape, bool)
    for f in folds:
        hidden |= f.truth
    visible = folds[0].visible
    terms, info = eh.terms_for(dots.astype(np.float32), hidden, valid=fp, known=visible)
    boot = eh.bootstrap_paired({"candidate": terms, "candidate": terms}, "candidate",
                               "candidate", draws=1000, seed=a.seed)
    dti = float(info["dti"])
    ci95 = boot["candidate"]["ci95"]
    log(f"shipped file, re-measured on the holdout = {dti:.6f} "
        f"CI=[{ci95[0]:.6f},{ci95[1]:.6f}] on {int(hidden.sum())} withheld positives")
    log("    (not comparable with the arm number below: the shipped file is additionally "
        "pruned against the WHOLE mapped catalogue, and the holdout truth is a withheld "
        "20 % of that same catalogue, so the prune removes exactly the cells the "
        "instrument rewards. Removing them requires the withheld labels, which is why "
        "the shipped file cannot be scored by this instrument without leaking.)")

    # ------------------------------------------------- 4 write and validate
    stem = f"61gemsdoe-basement-step-ribbon-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    name = f"{stem}-buried-structure"
    note = ("Basement-depth steps from Parker-Oldenburg inversion of isostatic residual "
            "gravity; 5-line ribbons, magnetic mimics removed.")
    assert len(name) <= 140 and len(note) <= 140, (len(name), len(note))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tif_path = OUT_DIR / f"{stem}.tif"
    pred = np.where(dots, 1.0, 0.0).astype(np.float32)
    receipt = sw.write_submission(
        tif_path, pred, ROOT / "data/bridge/sample_submission.tif", fp,
        note=note, name=name, catalogue=g.catalogue,
        metadata=dict(lane="buried structure",
                      method="Parker 1973 forward / Oldenburg 1974 inversion of band 13 "
                             "iso_grav_anom; non-maximum-suppressed horizontal-gradient "
                             "maxima of basement depth; multi-line ribbons",
                      drho_kg_m3=a.drho, z0_m=a.z0, cutoff_wavelength_m=a.cutoff,
                      offsets_px=list(OFFSETS), sigma_px=SIGMA_PX, thin_px=THIN_PX,
                      budget=a.budget,
                      uniqueness=dict(n_registry_rasters=uniq["n_registry_rasters"],
                                      worst_spearman=uniq["worst_spearman"],
                                      worst_spearman_source=uniq["worst_spearman_source"],
                                      worst_dot_overlap_3px=uniq["worst_dot_overlap_3px"],
                                      worst_dot_overlap_source=uniq[
                                          "worst_dot_overlap_source"])))
    sha8 = receipt["sha256"][:8]
    log(f"wrote {tif_path.relative_to(ROOT)} ({receipt['bytes']} B) sha256={receipt['sha256']}")

    # ------------------------------------------------- 5 run card
    arms = json.loads((ROOT / "evidence/candidate_arms.json").read_text()) \
        if (ROOT / "evidence/candidate_arms.json").exists() else {}
    best = arms.get("holdout_dti", {})
    chosen = best.get("demoted_k3_s6", {})
    beats = bool(chosen.get("beats_null", False))

    card = dict(
        lane="buried structure",
        hypothesis=("A buried range-front or intrabasin normal fault offsets the "
                    "pre-Tertiary basement surface under alluvial cover; that offset is "
                    "a step in the basement depth recovered by inverting the isostatic "
                    "residual gravity, and it is located at the maximum of the "
                    "horizontal gradient of the inverted depth."),
        mechanism=("Parker (1973) Fourier forward operator and Oldenburg (1974) "
                   "iterative inversion of band 13 iso_grav_anom at drho=400 kg/m3, "
                   "z0=3000 m, cutoff 5000 m; Canny non-maximum suppression along the "
                   "gradient; throw measured across an 800 m aperture; emission as "
                   "multi-line ribbons thinned to isolated dots."),
        competing_explanation=("A lateral density contrast WITHIN basement: a "
                               "granitic/mafic contact, a hydrothermally altered zone, "
                               "a caldera fill or a palaeo-weathered horizon. 200 kg/m3 "
                               "over a 2 km section is indistinguishable from a 1000 m "
                               "step of the basement surface at a 400 kg/m3 contrast, "
                               "and it cuts no fault at all."),
        mimic_control=("Steps within 2 px of a reduced-to-pole magnetic contact crest "
                       f"(band 2) are demoted: {int(ambiguous.sum())} of {s.n_crest} "
                       f"({ambiguous.sum()/max(s.n_crest,1):.3f}). Measured on the "
                       "holdout: demotion is not significantly harmful at the same "
                       "geometry (0.0379 vs 0.0371, see evidence/candidate_arms.json)."),
        holdout_dti=dict(
            evidence_class="HOLDOUT-DTI",
            evaluator_version=eh.VERSION,
            n_withheld_positives=int(hidden.sum()),
            selected_arm_is_the_headline_number=True,
            shipped_file_remeasured_dti=dti,
            shipped_file_remeasured_ci95=ci95,
            shipped_file_remeasured_note=(
                "The shipped file is the selected arm with one extra operation: dots "
                "within 2 px of the WHOLE mapped catalogue are removed and the budget is "
                "topped back up. The holdout truth is a withheld 20 % of that same "
                "catalogue, so this removes precisely the cells the instrument rewards "
                "and the re-measured value is not comparable with the arm value. It is "
                "reported for completeness only. Under the organiser's rule that mapped "
                "faults are removed from every metric term, the deleted cells were inert, "
                "so the shipped product's expected score is the arm's."),
            selected_arm="demoted_k3_s6",
            selected_arm_dti=chosen.get("dti"),
            selected_arm_ci95=chosen.get("ci95"),
            matched_random_line_null_dti=chosen.get("null_dti"),
            paired_difference=chosen.get("diff"),
            paired_difference_ci95=chosen.get("diff_ci95"),
            beats_matched_null_at_95pct=beats),
        correlation_vs_registry=dict(
            n_rasters=uniq["n_registry_rasters"],
            worst_spearman=uniq["worst_spearman"],
            worst_spearman_source=uniq["worst_spearman_source"],
            worst_dot_overlap_3px=uniq["worst_dot_overlap_3px"],
            worst_dot_overlap_source=uniq["worst_dot_overlap_source"],
            drift_gate="Spearman > 0.90 OR > 70 % of dots within 3 px",
            passed=bool(uniq["unique"])),
        raster=dict(file=f"docs/submissions/{tif_path.name}",
                    sha256=receipt["sha256"], bytes=receipt["bytes"],
                    zip_file=f"docs/submissions/{receipt['zip_file']}",
                    zip_sha256=receipt["zip_sha256"],
                    positive_pixels=receipt["validator"]["info"]["positive_pixels"]),
        validator=receipt["validator"],
        template_report=receipt["template_report"],
        submission_name=name,
        note=note,
        note_chars=len(note),
        verdict=("promote" if beats else "negative"),
        headline_dti=chosen.get("dti"),
        headline_ci95=chosen.get("ci95"),
        verdict_reason=("The candidate does not beat a budget- and domain-matched "
                        "random-line null at the pre-registered 95 % level "
                        f"(paired difference {chosen.get('diff')}, 95 % CI "
                        f"{chosen.get('diff_ci95')}), so the pre-registered promotion "
                        "rule is not satisfied. The point estimate is positive inside "
                        "the buried (basin-interior) domain and negative or tied over "
                        "the full footprint. The single largest term is the "
                        "irreducible one: the measured positional resolution is "
                        "900 m at the median against a 300 m scoring kernel."),
        okay_to_download=True,
        okay_to_submit=bool(beats),
        download_permission_status=dict(
            scope=("Locally validated: single-band float32 GeoTIFF, values in [0,1], "
                   "no NaN inside the footprint, CRS/shape/transform identical to the "
                   "organiser's sample submission, zero positive mass outside the "
                   "scored footprint and on the mapped catalogue, and unique against "
                   f"all {uniq['n_registry_rasters']} family rasters. This is a local "
                   "format and uniqueness clearance, NOT an organiser acceptance, NOT "
                   "a leaderboard score and NOT approval to spend a weekly submission "
                   "slot.")),
        submission_slots_used=0,
        approved_for_weekly_slot=False,
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        runtime_s=round(time.time() - started, 1),
    )
    (ROOT / "evidence/run_card.json").write_text(
        json.dumps(card, indent=2, allow_nan=False) + "\n")

    sub = dict(file=tif_path.name, path=f"docs/submissions/{tif_path.name}",
               sha256=receipt["sha256"], bytes=receipt["bytes"],
               positive_pixels=receipt["validator"]["info"]["positive_pixels"],
               submission_name=name, note=note,
               verdict=card["verdict"], okay_to_submit=card["okay_to_submit"],
               # the full validator receipt for the shipped bytes, so the site can
               # print the per-check table straight from this file
               validation=receipt["validator"],
               files=dict(tif=dict(name=f"submissions/{tif_path.name}",
                                   sha256=receipt["sha256"],
                                   bytes=receipt["bytes"],
                                   positive_pixels=receipt["validator"]["info"][
                                       "positive_pixels"]),
                          zip=dict(name=f"submissions/{receipt['zip_file']}",
                                   sha256=receipt["zip_sha256"])))
    (ROOT / "evidence/submission.json").write_text(
        json.dumps(sub, indent=2, allow_nan=False) + "\n")
    (ROOT / "docs/data/submission.json").write_text(
        json.dumps(sub, indent=2, allow_nan=False) + "\n")

    log(f"verdict={card['verdict']}  okay_to_download=True  "
        f"okay_to_submit={card['okay_to_submit']}")
    log(f"done in {time.time()-started:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(
        "Retired: this legacy writer may reuse a stale uniqueness receipt and does "
        "not use the current complete-inventory shared gate. Do not write or submit a TIFF."
    )
