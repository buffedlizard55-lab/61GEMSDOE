"""Small deterministic contracts for the frozen H61U runner."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("run_h61u_test", ROOT / "scripts" / "run_h61u.py")
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RUNNER)


def test_block_mean_uses_only_finite_known_cells_and_reports_coverage():
    a = np.arange(64, dtype=np.float32).reshape(8, 8)
    known = np.ones((8, 8), bool)
    known[0, 0] = False
    a[0, 1] = np.nan
    fp = np.ones((8, 8), bool)
    fp[7, 7] = False
    mean, valid, coarse_fp, count = RUNNER._block_mean(a, known, fp, factor=4)
    assert mean.shape == (2, 2)
    assert valid.all()
    assert coarse_fp.all()
    assert count[0, 0] == 14
    assert mean[0, 0] == pytest.approx(np.nanmean(np.where(known[:4, :4] & np.isfinite(a[:4, :4]),
                                                        a[:4, :4], np.nan)))


def test_centered_crest_ribbon_has_expected_three_pixel_cross_section():
    small = np.zeros((5, 5), bool)
    small[:, 2] = True
    centers = RUNNER._centres_to_grid(small, (20, 20), factor=4)
    ribbon = RUNNER._ribbon(centers)
    assert centers.sum() == 5
    # The regularized ridge centers are four cells apart; the 3x3 dilation is
    # a three-cell-wide multi-line ribbon at each crest cell.
    assert ribbon[2, 10]
    assert ribbon[1, 10] and ribbon[3, 10]
    assert not ribbon[0, 10]


def test_synthetic_density_sheet_is_recorded_as_nonfault_not_a_score():
    receipt = RUNNER._run_density_mimic()
    assert receipt["evidence_class"] == "SYNTHETIC-NONFAULT-MIMIC-CONTROL"
    assert "no fault displacement" in receipt["forward_operator"]
    assert receipt["dti_computed"] is False
    assert receipt["same_sign_persistence_survivors"] >= 0
    assert "no fault truth" in receipt["dti_reason"]
