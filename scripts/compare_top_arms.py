#!/usr/bin/env python3
"""Pairwise comparison of the leading candidates on the same holdout.

``evidence/candidate_arms.json`` ranks every arm against its *own* matched
random-line null.  That answers "is this geometry better than random?" but not
"which geometry should be shipped?".  This script answers the second question
with a paired block bootstrap between the leading arms themselves, and writes
``evidence/arm_selection.json``.

The shipped candidate is the arm with the highest HOLDOUT-DTI among arms that
are not significantly worse than the best arm.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import evaluate_holdout as eh, grid as gd, holdout as ho  # noqa: E402


def log(m: str) -> None:
    print(f"[sel] {m}", flush=True)


def main() -> int:
    ap = __import__("argparse").ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=61011)
    ap.add_argument("--hide-fraction", type=float, default=0.20)
    ap.add_argument("--buffer-px", type=int, default=3)
    ap.add_argument("--draws", type=int, default=2000)
    ap.add_argument("--arms", nargs="*", default=[
        "demoted_k3_s6", "ribbon_k3_s6", "ribbon_k3_s9", "ribbon_k2_s6",
        "basin_k2_s6", "ribbon_k4_s3", "ribbon_k1", "demoted_k1", "basin_k3_s6",
        "basin_k2_s3", "basin_k1"])
    a = ap.parse_args()

    g = gd.load_grid()
    fp = g.footprint
    folds = ho.make_folds(g.catalogue, fp, fraction=a.hide_fraction,
                          buffer_px=a.buffer_px, seed=a.seed)
    hidden = np.zeros(fp.shape, bool)
    for f in folds:
        hidden |= f.truth
    visible = folds[0].visible
    log(f"withheld positives={int(hidden.sum())} folds=" +
        ",".join(f"{f.name}={f.n_truth}" for f in folds))

    terms = {}
    for name in a.arms:
        path = ROOT / f".cache/arm_{name}.npy"
        if not path.exists():
            log(f"    {name}: MISSING, skipped")
            continue
        dots = np.load(path)
        terms[name] = eh.terms_for(dots.astype(np.float32), hidden,
                                   valid=fp, known=visible)[0]
        log(f"    {name}: dots={int(dots.sum())} dti={eh.dti_from_terms(terms[name]):.6f}")

    best = max(terms, key=lambda k: eh.dti_from_terms(terms[k]))
    log(f"best arm by point estimate: {best}")

    rows = {}
    for name in terms:
        if name == best:
            continue
        b = eh.bootstrap_paired(terms, best, name, draws=a.draws, seed=a.seed)
        key = f"{best}_minus_{name}"
        rows[name] = dict(dti=float(eh.dti_from_terms(terms[name])),
                          diff=b[key]["mean"], ci95=b[key]["ci95"],
                          p_best_better=b[key]["p_ge_zero"],
                          significantly_worse=bool(b[key]["ci95"][0] > 0.0))
        log(f"    {best} - {name:20s} = {b[key]['mean']:+.6f} "
            f"CI=[{b[key]['ci95'][0]:+.6f},{b[key]['ci95'][1]:+.6f}] "
            f"P={b[key]['p_ge_zero']:.3f}")

    not_worse = [n for n, r in rows.items() if not r["significantly_worse"]] + [best]
    ranked = sorted(not_worse, key=lambda n: -eh.dti_from_terms(terms[n]))
    chosen = ranked[0]
    log(f"arms not significantly worse than the best: {ranked}")
    log(f"chosen={chosen}")

    out = dict(evidence_class="HOLDOUT-DTI", evaluator_version=eh.VERSION,
               generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               n_withheld_positives=int(hidden.sum()),
               folds={f.name: f.n_truth for f in folds},
               rule=("ship the highest-DTI arm that is not significantly worse "
                     "than the best arm in a paired block bootstrap"),
               best_by_point_estimate=best,
               dti={n: float(eh.dti_from_terms(t)) for n, t in terms.items()},
               paired_vs_best=rows, chosen=chosen,
               chosen_dti=float(eh.dti_from_terms(terms[chosen])),
               draws=a.draws, seed=a.seed)
    (ROOT / "evidence/arm_selection.json").write_text(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
