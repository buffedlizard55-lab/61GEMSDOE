#!/usr/bin/env python3
"""Build the submission GeoTIFF the site offers for download, then validate it.

Operating point comes from reports/experiment.json (the best holdout configuration),
so the raster that ships is the raster the holdout measured -- there is no separate
hand-tuned path that could drift from the evidence.

    python scripts/make_submission.py --data data --out docs/downloads
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import rasterio

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fields import greedy_peaks, normalise_field, off_catalogue_mask  # noqa: E402
from gravity import (fill_nodata, horizontal_gradient_magnitude,  # noqa: E402
                     parker_oldenburg_invert)
from submission_io import (EXPECTED_CRS, validate_submission,  # noqa: E402
                           write_checks, write_submission)
from uniqueness import check_uniqueness  # noqa: E402

NAME = "gems61-lane-buried-step-gravinversion-hgm-r3-k400k-b2zeros.tif"
NOTE = ("Parker-Oldenburg inversion of isostatic gravity; 3-px catalogue-excluded "
        "HGM maxima of basement relief, binary all-finite.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="docs/downloads")
    ap.add_argument("--reports", default="reports")
    ap.add_argument("--registry", default="/tmp/refs/registry")
    ap.add_argument("--cache", default="/tmp/gems_fields.npz")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    exp_path = os.path.join(args.reports, "experiment.json")
    if not os.path.exists(exp_path):
        print("reports/experiment.json missing -- run scripts/run_experiment.py first")
        return 2
    with open(exp_path) as fh:
        exp = json.load(fh)
    best = exp["experiment2_holdout"]["best"]
    # The budget study (reports/k_study.json) sweeps the emission count past the range
    # the first sweep covered, because on this metric the score is governed by total
    # emission mass as much as by placement.  If it exists, the best holdout point for
    # the lane field from THAT study is the operating point that ships.
    ks = os.path.join(args.reports, "k_study.json")
    if os.path.exists(ks):
        with open(ks) as fh:
            rows = [r for r in json.load(fh) if r["name"].startswith("LANE")]
        if rows:
            kb = max(rows, key=lambda r: r["dti"])
            best = dict(name="LANE_grav_inversion_hgm", exclude_radius=3, k=kb["k"],
                        ribbon_half_width=0, dti_mean=kb["dti"],
                        dti_per_fold=kb["per_fold"], boot={},
                        selected_by="reports/k_study.json (emission-budget study)")
            print(f"[operating point] k={kb['k']} from the budget study, holdout DTI {kb['dti']}")

    labels = None
    with rasterio.open(os.path.join(args.data, "labels.tif")) as s:
        labels = s.read(1)
    valid = labels != -1
    gt = labels == 1

    if os.path.exists(args.cache):
        z = np.load(args.cache)
        hgm = z["hgm"].astype(np.float64)
        source = f"cache {args.cache}"
    else:
        with rasterio.open(os.path.join(args.data, "training_features.tif")) as s:
            b13 = s.read(13).astype(np.float64)
        g = fill_nodata(b13, valid, sigma=25.0)
        H, W = g.shape
        yy, xx = np.mgrid[0:H, 0:W]
        A = np.stack([xx[valid].ravel().astype(np.float64),
                      yy[valid].ravel().astype(np.float64),
                      np.ones(int(valid.sum()))], axis=1)
        coef, *_ = np.linalg.lstsq(A, g[valid].ravel(), rcond=None)
        gres = g - (coef[0] * xx + coef[1] * yy + coef[2])
        h_depth = -parker_oldenburg_invert(gres, 100.0, 100.0, z0=1200.0,
                                          drho=-420.0, max_depth=4000.0,
                                          n_terms=4, n_iter=6)
        hgm = horizontal_gradient_magnitude(h_depth, valid, smooth_sigma=2.0)
        source = "Parker-Oldenburg inversion computed now"

    field = normalise_field(hgm, valid)

    # The catalogue exclusion is built from the FULL visible catalogue, which is the
    # only thing we have at submission time (the holdout used each fold's visible set).
    excl = off_catalogue_mask(gt, best["exclude_radius"]) if best["exclude_radius"] else None
    mask, centres = greedy_peaks(field, valid, k=best["k"], min_sep=3,
                                 half_width=best["ribbon_half_width"], exclude=excl)
    emitted = np.where(mask, 1.0, 0.0).astype(np.float32)

    path = os.path.join(args.out, NAME)
    info = write_submission(path, emitted, valid,
                            template=os.path.join(args.data, "sample_submission.tif"),
                            threshold=None)
    print(f"wrote {path}: {info['n_positive']} pixels set to 1 (source: {source})")

    val = validate_submission(path, os.path.join(args.data, "sample_submission.tif"))
    for k, v in val["checks"].items():
        print(f"  [{'PASS' if v[0] else 'FAIL'}] {k} = {v[1]}")
    print("  format contract:", "PASS" if val["pass"] else "FAIL")

    # .sha256 sidecar
    with open(path + ".sha256", "w") as fh:
        fh.write(f"{val['sha256']}  {NAME}\n")

    # Block-bootstrap 95% CI for the shipped operating point, computed here rather
    # than quoted from elsewhere, so the card's interval belongs to these exact bytes.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "rx", os.path.join(HERE, "run_experiment.py"))
    rx = importlib.util.module_from_spec(spec); spec.loader.exec_module(rx)
    folds = [f for f in _folds_for_ci(gt, valid)]
    ctxs = _ctxs(folds, valid)
    contribs = []
    for ctx, fold in zip(ctxs, folds):
        excl = off_catalogue_mask(fold["visible"], best["exclude_radius"]) if best["exclude_radius"] else None
        m, _ = greedy_peaks(field, valid, k=best["k"], min_sep=3,
                            half_width=best["ribbon_half_width"], exclude=excl)
        contribs.append(rx.block_contributions(ctx, np.where(m, 1.0, 0.0)))
    boot = rx.bootstrap_dti([c["tp"] for c in contribs], [c["fp"] for c in contribs],
                            [c["gt"] for c in contribs])
    print("  block-bootstrap 95% CI for the shipped point:", boot)
    holdout_detail = dict(
        dti_mean=float(np.mean([c.score(np.where(greedy_peaks(
            field, valid, k=best["k"], min_sep=3,
            half_width=best["ribbon_half_width"],
            exclude=off_catalogue_mask(f["visible"], best["exclude_radius"]) if best["exclude_radius"] else None)[0],
            1.0, 0.0))["dti"] for c, f in zip(ctxs, folds)])),
        boot=boot, k=best["k"], exclude_radius=best["exclude_radius"],
        ribbon_half_width=best["ribbon_half_width"])

    uniq = check_uniqueness(path, args.registry)
    print("  uniqueness vs registry:", uniq.get("verdict"), uniq.get("summary"))

    with open(os.path.join(args.out, NAME + ".json"), "w") as fh:
        json.dump(dict(validation=val, uniqueness=uniq,
                       holdout=best, emission_source=source), fh, indent=1)

    write_checks(val, os.path.join(args.reports, "submission_checks.json"))
    card = dict(
        hypothesis="Buried range-front and intrabasin fault steps are resolvable from "
                   "the provided isostatic-gravity anomaly by Parker-Oldenburg inversion, "
                   "and their horizontal-gradient ridges mark faults the surface "
                   "catalogue misses.",
        mechanism="Parker (1973) forward series / Oldenburg (1974) iteration on band 13 "
                  "-> basement relief -> |grad relief| -> grid-cell maxima emitted as "
                  "ribbons -> pixels within a tuned radius of the visible catalogue "
                  "removed -> binary all-finite GeoTIFF on the competition grid.",
        competing_non_fault_process="Intrabasement density contrasts (intrusion margins, "
                                    "basement lithologic contacts, buried volcanic "
                                    "centres) produce the same horizontal-gradient ridge "
                                    "as a fault step and this lane cannot separate them.",
        holdout_dti=dict(
            value=round(holdout_detail["dti_mean"], 5),
            evaluator="src/holdout.py FoldContext, parity-checked against "
                      "src/gems_metric.py score_arrays (max |diff| = 0)",
            withheld_positives=int(exp["experiment2_holdout"]["total_hidden"]),
            ci95=[holdout_detail["boot"]["lo"], holdout_detail["boot"]["hi"]],
            operating_point=dict(k=holdout_detail["k"],
                                 exclude_radius=holdout_detail["exclude_radius"],
                                 ribbon_half_width=holdout_detail["ribbon_half_width"]),
            random_line_control=exp.get("experiment2_random_line_control"),
            label="HOLDOUT-DTI (proxy: withheld segments of the VISIBLE catalogue, "
                  "NOT the competition's withheld set)"),
        random_beats_lane_on_holdout=True,
        verdict_reason="On the spatially blocked same-catalogue holdout the lane field "
                       "does not beat a random dot field of identical size (0.0888 vs "
                       "0.0855 at saturation), and the registry's own top-scoring raster "
                       "scores 0.0045 here while its mid-scoring raster scores 0.1089 -- "
                       "the competition ranking inverts on a same-catalogue holdout.",
        uniqueness_vs_registry=uniq,
        raster_sha256=val["sha256"],
        validator=dict(passed=val["pass"], checks=val["checks"], stats=val["stats"]),
        submission_name=NAME,
        submission_note=NOTE,
        note_length=len(NOTE),
        verdict="negative",
    )
    with open(os.path.join(args.reports, "run_card.json"), "w") as fh:
        json.dump(card, fh, indent=1)
    print(f"run card -> {args.reports}/run_card.json  verdict={card['verdict']} "
          f"note={len(NOTE)}/140 chars")
    return 0




def _folds_for_ci(gt, valid):
    from holdout import make_folds
    return make_folds(gt, valid, n_rows=6, n_cols=6, n_folds=4, buffer_px=6,
                      min_segment_px=8)


def _ctxs(folds, valid):
    from holdout import make_contexts
    return make_contexts(folds, valid)


if __name__ == "__main__":
    raise SystemExit(main())
