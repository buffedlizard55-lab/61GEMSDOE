"""The hide-and-recover instrument.

The instrument's contract is that a candidate can never see the pixels it is
scored on.  These tests pin that contract down, because a leak here would make
every number in the run card meaningless.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import evaluate_holdout as eh, holdout as ho  # noqa: E402


def _cat60():
    catalogue = np.zeros((60, 60), bool)
    catalogue[10, 5:25] = True        # component A
    catalogue[30, 5:45] = True        # component B
    catalogue[50, 0:60] = True        # component C
    return catalogue


def test_withheld_segments_are_never_split():
    """A withheld component is withheld whole, so no continuation leaks."""
    catalogue = _cat60()
    fp = np.ones((60, 60), bool)
    folds = ho.make_folds(catalogue, fp, fraction=0.34, buffer_px=2, seed=1)
    hidden = np.zeros_like(catalogue)
    for f in folds:
        hidden |= f.truth
    lab, n = ho.catalogue_components(catalogue)
    for i in range(1, n + 1):
        comp = lab == i
        assert (comp & hidden).sum() in (0, int(comp.sum()))


def test_folds_cover_the_whole_grid():
    """Regression: the four quadrants must tile the grid.

    Splitting the rows into ``n_folds`` bands and keeping only the first two
    left the southern half of the grid in no fold at all, so half the catalogue
    could never be withheld.
    """
    catalogue = _cat60()
    fp = np.ones((60, 60), bool)
    folds = ho.make_folds(catalogue, fp, fraction=1.0, buffer_px=1, seed=1)
    covered = np.zeros_like(catalogue)
    for f in folds:
        assert not (covered & f.region).any()      # disjoint
        covered |= f.region
    # every catalogue pixel lies inside some fold region (a quadrant with no
    # catalogue legitimately produces no fold, so the tiling is checked on the
    # catalogue, not on the whole grid)
    assert covered[catalogue].all()
    assert not (covered & ~fp).any()
    hidden = np.zeros_like(catalogue)
    for f in folds:
        hidden |= f.truth
    assert (hidden == catalogue).all()


def test_visible_and_hidden_are_disjoint():
    catalogue = _cat60()
    fp = np.ones((60, 60), bool)
    folds = ho.make_folds(catalogue, fp, fraction=0.34, buffer_px=3, seed=2)
    for f in folds:
        assert not (f.truth & f.visible).any()


def test_the_context_buffer_removed_the_neighbourhood_of_the_hidden_set():
    """Within buffer_px of a hidden pixel, no catalogue pixel stays visible."""
    from scipy.ndimage import distance_transform_edt
    catalogue = _cat60()
    fp = np.ones((60, 60), bool)
    folds = ho.make_folds(catalogue, fp, fraction=0.34, buffer_px=3, seed=3)
    hidden = np.zeros_like(catalogue)
    for f in folds:
        hidden |= f.truth
    d = distance_transform_edt(~hidden)
    near = (d <= 3.0) & catalogue
    assert not (near & folds[0].visible).any()


def test_mass_on_the_visible_catalogue_scores_nothing():
    pred = np.zeros((40, 40), np.float32)
    truth = np.zeros((40, 40), bool)
    truth[20, 10:30] = True
    visible = np.zeros((40, 40), bool)
    visible[5, 10:30] = True
    pred[visible] = 1.0
    _, info = eh.terms_for(pred, truth, known=visible)
    assert info["fpw"] == pytest.approx(0.0)
    assert info["tpw"] == pytest.approx(0.0)


def test_perfect_prediction_scores_one_and_empty_scores_zero():
    truth = np.zeros((40, 40), bool)
    truth[20, 10:30] = True
    perfect = truth.astype(np.float32)
    terms, info = eh.terms_for(perfect, truth)
    assert info["dti"] == pytest.approx(1.0)
    assert info["coverage"] == pytest.approx(1.0)
    empty = np.zeros((40, 40), np.float32)
    terms, info = eh.terms_for(empty, truth)
    assert info["dti"] == pytest.approx(0.0)


def test_block_terms_reproduce_the_global_score_exactly():
    rng = np.random.default_rng(4)
    pred = np.zeros((80, 80), np.float32)
    pred[rng.integers(0, 80, 200), rng.integers(0, 80, 200)] = 1.0
    truth = np.zeros((80, 80), bool)
    truth[20, 5:60] = True
    truth[60, 10:70] = True
    terms, info = eh.terms_for(pred, truth, block_side=20)
    assert eh.dti_from_terms(terms) == pytest.approx(info["dti"], abs=1e-12)
    assert terms[:, 3].sum() == pytest.approx(info["n_truth"])


def test_auc_is_chance_for_noise_and_one_for_a_perfect_ranker():
    rng = np.random.default_rng(6)
    valid = np.ones((200, 200), bool)
    truth = np.zeros((200, 200), bool)
    truth[100, :] = True
    noise = rng.normal(0, 1, (200, 200))
    assert eh.auc(noise, truth, valid) == pytest.approx(0.5, abs=0.05)
    assert eh.auc(truth.astype(float), truth, valid) == pytest.approx(1.0)
    assert eh.auc(-truth.astype(float), truth, valid) == pytest.approx(0.0)


def test_auc_handles_ties_by_averaging_ranks():
    """Every rank tied: the rank sum must average, not break arbitrarily."""
    from scipy.stats import rankdata

    valid = np.ones((10, 10), bool)
    truth = np.zeros((10, 10), bool)
    truth[0, :5] = True
    feat = np.zeros((10, 10))
    feat[0, :] = 1.0                # 100 tied at the top: 5 pos, 5 neg
    got = eh.auc(feat, truth, valid)
    # independent rank-sum computation with average ranks
    ranks = rankdata(feat.ravel())
    y = truth.ravel()
    n_pos, n_neg = int(y.sum()), int((~y).sum())
    ref = (ranks[y].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)
    assert got == pytest.approx(ref, abs=1e-12)
    # the tied score is dominated by the 95 untied negatives, so it is high but
    # strictly below 1: the five tied negatives are not counted as wins
    assert 0.97 < got < 1.0


def test_basin_interior_mask_selects_the_deep_tail():
    rng = np.random.default_rng(8)
    depth = rng.uniform(0, 1000, (50, 50)).astype(np.float32)
    valid = np.ones((50, 50), bool)
    m = ho.basin_interior_mask(depth, valid, depth_quantile=0.60)
    assert m.mean() == pytest.approx(0.40, abs=0.01)
    assert depth[m].min() >= np.quantile(depth, 0.60) - 1e-3
