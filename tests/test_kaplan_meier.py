"""Tests for `_kaplan_meier` against lifelines.KaplanMeierFitter."""

from __future__ import annotations

import numpy as np
import pytest
from lifelines import KaplanMeierFitter

from guanrank import _kaplan_meier


def _lifelines_sr_at_times(
    T: np.ndarray, E: np.ndarray, times: np.ndarray
) -> np.ndarray:
    kmf = KaplanMeierFitter()
    kmf.fit(durations=T, event_observed=E)
    # Step function: SR at each requested time.
    return kmf.survival_function_at_times(times).to_numpy()


def _assert_km_matches_lifelines(T: np.ndarray, E: np.ndarray) -> None:
    sr_times, sr_vals = _kaplan_meier(T, E)
    expected = _lifelines_sr_at_times(T, E, sr_times)
    np.testing.assert_allclose(sr_vals, expected, atol=1e-12, rtol=1e-12)


def test_km_random_dataset(random_dataset):
    T, E = random_dataset
    _assert_km_matches_lifelines(T, E)


def test_km_all_events():
    T = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    E = np.array([1, 1, 1, 1, 1], dtype=np.int8)
    _assert_km_matches_lifelines(T, E)


def test_km_all_censored():
    T = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    E = np.array([0, 0, 0, 0, 0], dtype=np.int8)
    _assert_km_matches_lifelines(T, E)


def test_km_ties_mixed_event_censor():
    T = np.array([1.0, 1.0, 2.0, 2.0, 3.0])
    E = np.array([1, 0, 1, 1, 0], dtype=np.int8)
    _assert_km_matches_lifelines(T, E)


def test_km_single_event():
    T = np.array([2.5])
    E = np.array([1], dtype=np.int8)
    _assert_km_matches_lifelines(T, E)


def test_km_single_censored():
    T = np.array([2.5])
    E = np.array([0], dtype=np.int8)
    _assert_km_matches_lifelines(T, E)


def test_km_sr0_at_t0_is_one():
    """Implicit SR(0) = 1.0: an SR lookup before the first observed time is 1.0."""
    from guanrank import _sr_at

    T = np.array([1.0, 2.0, 3.0])
    E = np.array([1, 1, 1], dtype=np.int8)
    sr_times, sr_vals = _kaplan_meier(T, E)
    assert _sr_at(sr_times, sr_vals, 0.5) == 1.0


def test_sr_at_step_lookup():
    from guanrank import _sr_at

    T = np.array([1.0, 2.0, 3.0])
    E = np.array([1, 1, 1], dtype=np.int8)
    sr_times, sr_vals = _kaplan_meier(T, E)

    # Before first time: 1.0
    assert _sr_at(sr_times, sr_vals, 0.0) == 1.0
    # Exactly at observed time: value at that index
    assert _sr_at(sr_times, sr_vals, 1.0) == pytest.approx(sr_vals[0])
    assert _sr_at(sr_times, sr_vals, 2.0) == pytest.approx(sr_vals[1])
    # Between observed times: previous step
    assert _sr_at(sr_times, sr_vals, 1.5) == pytest.approx(sr_vals[0])
    assert _sr_at(sr_times, sr_vals, 2.5) == pytest.approx(sr_vals[1])
    # Past last observed time: final value
    assert _sr_at(sr_times, sr_vals, 100.0) == pytest.approx(sr_vals[-1])
