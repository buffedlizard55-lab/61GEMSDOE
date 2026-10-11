"""The DTI contract, re-derived from the published formula.

Every identity here is checked against the definition in the official problem
description, not against another implementation.  If a number in this file
disagrees with the evaluator, the evaluator is wrong.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import metric  # noqa: E402


def brute_force_components(pred, truth, radius=3.0):
    """Literal transcription of the published sums, O(n*m)."""
    py, px = np.nonzero(pred > 0)
    gy, gx = np.nonzero(truth)
    tp = 0.0
    for j, i in zip(gy, gx):
        d = np.hypot(py - j, px - i)
        k = np.maximum(1.0 - d / radius, 0.0)
        tp += float((pred[py, px] * k).max()) if py.size else 0.0
    fp = 0.0
    for j, i in zip(py, px):
        if gy.size:
            d = np.hypot(gy - j, gx - i)
            q = float(np.maximum(1.0 - d / radius, 0.0).max())
        else:
            q = 0.0
        fp += float(pred[j, i]) * (1.0 - q)
    fn = float(gy.size) - tp
    return tp, fp, fn


def test_kernel_is_triangular_with_radius_300m():
    assert metric.R_M == pytest.approx(300.0)
    assert metric.kernel(0.0) == pytest.approx(1.0)
    assert metric.kernel(1.5) == pytest.approx(0.5)
    assert metric.kernel(3.0) == pytest.approx(0.0)
    assert metric.kernel(4.0) == pytest.approx(0.0)


def test_offsets_cover_exactly_the_nonzero_kernel_lattice():
    dy, dx, kw = metric.offsets()
    assert len(dy) == len(dx) == len(kw)
    for j, i, k in zip(dy, dx, kw):
        assert k == pytest.approx(metric.kernel(np.hypot(j, i)))
        assert k > 0.0
    # every lattice point inside R is present exactly once
    pts = {(int(j), int(i)) for j, i in zip(dy, dx)}
    expected = {(j, i) for j in range(-3, 4) for i in range(-3, 4)
                if metric.kernel(np.hypot(j, i)) > 0}
    assert pts == expected


def test_components_match_a_brute_force_transcription():
    rng = np.random.default_rng(11)
    pred = np.zeros((40, 40), np.float32)
    pred[rng.integers(0, 40, 12), rng.integers(0, 40, 12)] = 1.0
    truth = np.zeros((40, 40), bool)
    truth[10, 5:25] = True
    tp, fp, fn = metric.max_cover(pred, truth)[:1] + (0, 0) if False else (None, None, None)
    credit, q, _ = metric.max_cover(pred, truth)
    tp_fast, fp_fast, fn_fast = credit.sum(), float((pred[pred > 0] * (1 - q[pred > 0])).sum()), \
        float(truth.sum() - credit.sum())
    tp_ref, fp_ref, fn_ref = brute_force_components(pred, truth)
    assert tp_fast == pytest.approx(tp_ref, abs=1e-6)
    assert fp_fast == pytest.approx(fp_ref, abs=1e-6)
    assert fn_fast == pytest.approx(fn_ref, abs=1e-6)


def test_dti_is_alpha02_beta08():
    assert (metric.ALPHA, metric.BETA) == (0.2, 0.8)
    assert metric.dti_from_components(10.0, 0.0, 0.0) == pytest.approx(1.0)
    assert metric.dti_from_components(10.0, 0.0, 10.0) == pytest.approx(
        10.0 / (10.0 + 0.8 * 10.0))


def test_false_positives_are_discounted_by_alpha():
    base = metric.dti_from_components(100.0, 0.0, 100.0)
    with_fp = metric.dti_from_components(100.0, 1000.0, 100.0)
    assert with_fp < base
    # the denominator grows by exactly alpha * FP
    assert (100.0 / with_fp - 100.0 / base) == pytest.approx(0.2 * 1000.0, rel=1e-9)


def test_known_pixels_cannot_radiate_credit():
    """Mass on a mapped fault is worthless: it is masked out of every term.

    The withheld truth is a *different* line, so the scored domain is non-empty
    and the mapped line can be shown to contribute neither TP nor FP.
    """
    from gems61 import evaluate_holdout as eh
    truth = np.zeros((40, 40), bool)
    truth[20, 10:30] = True
    mapped = np.zeros((40, 40), bool)
    mapped[5, 10:30] = True            # 4 px away, far enough to earn no credit
    on_fault = np.zeros((40, 40), np.float32)
    on_fault[mapped] = 1.0
    terms, info = eh.terms_for(on_fault, truth, known=mapped)
    assert info["tpw"] == pytest.approx(0.0)
    assert info["fpw"] == pytest.approx(0.0)
    assert eh.dti_from_terms(terms) == pytest.approx(0.0)


def test_marginal_inclusion_threshold_at_the_stated_leader_level():
    """At s = 0.3195 a non-redundant dot pays only inside ~280 m."""
    k = metric.marginal_inclusion_threshold(0.3195)
    assert k == pytest.approx(0.2 * 0.3195 / (1 - 0.2 * 0.3195), rel=1e-9)
    # k = 1 - d/3  =>  d = 3 (1 - k)
    assert 3.0 * (1.0 - k) == pytest.approx(2.795, abs=1e-2)


def test_binary_dominates_a_scaled_support():
    """dDTI/dlambda > 0, so a graded map is dominated by its own threshold."""
    lam = np.linspace(0.05, 1.0, 40)
    dtis = [metric.dti_from_components(l * 500.0, l * 4000.0, 5000.0 - l * 500.0)
            for l in lam]
    assert all(b >= a - 1e-12 for a, b in zip(dtis, dtis[1:]))
    assert dtis[-1] == max(dtis)
