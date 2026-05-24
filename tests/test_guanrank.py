"""End-to-end and invariant tests for `guanrank`."""

from __future__ import annotations

import numpy as np
import pytest

from guanrank import guanrank


def test_sum_of_ranks_invariant(random_dataset):
    T, E = random_dataset
    ranks = guanrank(T, E)
    n = len(T)
    # Off-diagonal pairs sum to 1; N self-comparisons each contribute 0.5.
    expected_sum = n * (n - 1) / 2.0 + n * 0.5
    assert ranks.sum() == pytest.approx(expected_sum)


def test_rank_bounds(random_dataset):
    T, E = random_dataset
    ranks = guanrank(T, E)
    n = len(T)
    assert (ranks >= 0.0).all()
    assert (ranks <= float(n)).all()


def test_all_events_distinct_times_ranks_are_reverse_time_order():
    rng = np.random.default_rng(7)
    n = 25
    T = rng.uniform(0.0, 1.0, size=n)
    # Force distinctness.
    T = np.unique(T)
    n = len(T)
    E = np.ones(n, dtype=np.int8)
    ranks = guanrank(T, E)

    # Expected: subject with the k-th smallest time gets rank (n-1-k) + 0.5.
    order = np.argsort(T)
    expected = np.empty(n, dtype=np.float64)
    for k, idx in enumerate(order):
        expected[idx] = (n - 1 - k) + 0.5
    np.testing.assert_allclose(ranks, expected)


def test_all_censored_equal_times_uniform_ranks():
    n = 10
    T = np.full(n, 5.0)
    E = np.zeros(n, dtype=np.int8)
    ranks = guanrank(T, E)
    np.testing.assert_allclose(ranks, np.full(n, n * 0.5))


def test_determinism(random_dataset):
    T, E = random_dataset
    np.testing.assert_array_equal(guanrank(T, E), guanrank(T, E))
