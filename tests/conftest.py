"""Shared fixtures for the GuanRank test suite."""

from __future__ import annotations

import numpy as np
import pytest

from guanrank import guanrank


@pytest.fixture(scope="session", autouse=True)
def _warm_numba_jit() -> None:
    """Compile the numba kernels once per session so per-test timings are stable."""
    guanrank([0.0, 1.0], [1, 0])


@pytest.fixture
def rng() -> np.random.Generator:
    return np.random.default_rng(0xC0FFEE)


@pytest.fixture
def random_dataset(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Mixed events/censoring, N=100, no ties (with high probability)."""
    n = 100
    T = rng.uniform(0.0, 100.0, size=n)
    E = rng.integers(0, 2, size=n).astype(np.int8)
    return T, E
