"""End-to-end and invariant tests for `guanrank`."""

from __future__ import annotations

import numpy as np
import pytest

from guanrank import _compute_ranks, _kaplan_meier, guanrank


def _raw(T, E):
    """Raw (un-normalized) hazard scores, to test the pairwise-rule sums."""
    T = np.asarray(T, dtype=np.float64)
    E = np.asarray(E, dtype=np.int8)
    sr_times, sr_vals = _kaplan_meier(T, E)
    return _compute_ranks(sr_times, sr_vals, T, E, T, E)


def test_sum_of_raw_ranks_invariant(random_dataset):
    T, E = random_dataset
    raw = _raw(T, E)
    n = len(T)
    # Off-diagonal pairs sum to 1; N self-comparisons each contribute 0.5.
    expected_sum = n * (n - 1) / 2.0 + n * 0.5
    assert raw.sum() == pytest.approx(expected_sum)


def test_rank_bounds(random_dataset):
    T, E = random_dataset
    ranks = guanrank(T, E)
    # Normalized output lies in (0, 1], with the highest-hazard subject at 1.0.
    assert (ranks > 0.0).all()
    assert (ranks <= 1.0).all()
    assert ranks.max() == pytest.approx(1.0)


def test_all_events_distinct_times_ranks_are_reverse_time_order():
    rng = np.random.default_rng(7)
    n = 25
    T = rng.uniform(0.0, 1.0, size=n)
    # Force distinctness.
    T = np.unique(T)
    n = len(T)
    E = np.ones(n, dtype=np.int8)
    raw = _raw(T, E)

    # Expected raw: subject with the k-th smallest time gets rank (n-1-k) + 0.5.
    order = np.argsort(T)
    expected = np.empty(n, dtype=np.float64)
    for k, idx in enumerate(order):
        expected[idx] = (n - 1 - k) + 0.5
    np.testing.assert_allclose(raw, expected)

    # Normalization preserves the reverse-time ordering and caps the max at 1.0.
    ranks = guanrank(T, E)
    np.testing.assert_allclose(ranks, expected / expected.max())


def test_all_censored_equal_times_uniform_ranks():
    n = 10
    T = np.full(n, 5.0)
    E = np.zeros(n, dtype=np.int8)
    # Raw: every subject scores 0.5 against all n (self + tied peers).
    np.testing.assert_allclose(_raw(T, E), np.full(n, n * 0.5))
    # Normalized: uniform raw ranks collapse to a uniform 1.0.
    np.testing.assert_allclose(guanrank(T, E), np.ones(n))


def test_determinism(random_dataset):
    T, E = random_dataset
    np.testing.assert_array_equal(guanrank(T, E), guanrank(T, E))
