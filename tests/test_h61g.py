"""Tests for shared basement-lane helpers used by H61-L holdout controls."""
import numpy as np

from gems61.h61g import random_lines


def test_random_lines_respects_allowed_domain_and_exact_budget():
    allowed = np.zeros((80, 100), bool)
    allowed[5:75, 5:95] = True
    a = random_lines(allowed.shape, allowed, 333, seed=17)
    b = random_lines(allowed.shape, allowed, 333, seed=17)
    assert int(a.sum()) == 333
    assert np.all(~a | allowed)
    assert np.array_equal(a, b)


def test_random_lines_empty_or_oversized_budget_is_safe():
    empty = np.zeros((20, 30), bool)
    assert not random_lines(empty.shape, empty, 100).any()

    tiny = np.zeros((20, 30), bool)
    tiny[3, 4:8] = True
    out = random_lines(tiny.shape, tiny, 100)
    assert int(out.sum()) == 4
    assert np.array_equal(out, tiny)
