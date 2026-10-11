"""Shared test fixtures for the 61GEMSDOE lane.

The organiser's rasters are large and are restored by ``scripts/prepare_data.py``,
so every test here is written to run either against the real grid (when present)
or against a small synthetic grid pinned to the same constants.  Nothing in the
suite downloads anything.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
CACHE = ROOT / ".cache"


@pytest.fixture(scope="session")
def grid_available() -> bool:
    return (CACHE / "training_features.tif").exists() or (ROOT / "data/official").exists()


@pytest.fixture
def small_grid():
    """A 64x48 synthetic grid with the same 100 m pixel size."""
    h, w = 64, 48
    rng = np.random.default_rng(7)
    footprint = np.ones((h, w), bool)
    footprint[:4, :] = False
    catalogue = np.zeros((h, w), bool)
    catalogue[40, 10:30] = True
    truth = np.zeros((h, w), bool)
    truth[20, 8:28] = True
    return dict(shape=(h, w), footprint=footprint, catalogue=catalogue,
                truth=truth, rng=rng)


@pytest.fixture
def step_field():
    """A synthetic basement-depth field with one exact vertical step.

    Depth is 0 m left of column 32 and 500 m right of it, so the horizontal
    gradient of depth is a single clean crest along column 32 and the throw is
    exactly 500 m.  Everything the step operator claims can be checked against
    these two numbers.
    """
    h, w = 64, 64
    depth = np.zeros((h, w), np.float32)
    depth[:, 32:] = 500.0
    return dict(depth=depth, step_col=32, throw_m=500.0)
