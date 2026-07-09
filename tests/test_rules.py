"""Per-rule tests: each rule branch in `_compute_ranks` exercised by a minimal fixture.

Self-comparison (i==j) always contributes 0.5 to each subject's rank.
Off-diagonal contributions s(i,j) + s(j,i) sum to 1 by the rules' construction.
"""

from __future__ import annotations

import numpy as np
import pytest

from guanrank import _compute_ranks, _kaplan_meier, _rho


def _ranks(T, E):
    """Raw (un-normalized) hazard scores, to test the pairwise rules directly."""
    T = np.asarray(T, dtype=np.float64)
    E = np.asarray(E, dtype=np.int8)
    sr_times, sr_vals = _kaplan_meier(T, E)
    return _compute_ranks(sr_times, sr_vals, T, E, T, E)


def test_rule1_both_events_distinct():
    # tA=1<tB=2, both events: A scores 1, B scores 0.
    # rank[A] = 0.5 (self) + 1.0 (vs B) = 1.5
    # rank[B] = 0.0 (vs A) + 0.5 (self) = 0.5
    np.testing.assert_allclose(_ranks([1.0, 2.0], [1, 1]), [1.5, 0.5])


def test_rule1_both_events_reversed():
    np.testing.assert_allclose(_ranks([2.0, 1.0], [1, 1]), [0.5, 1.5])


def test_rule2_both_events_tied():
    # Tie with both events: each scores 0.5 off-diagonal.
    np.testing.assert_allclose(_ranks([1.0, 1.0], [1, 1]), [1.0, 1.0])


def test_rule2_both_censored_tied():
    np.testing.assert_allclose(_ranks([1.0, 1.0], [0, 0]), [1.0, 1.0])


def test_rule3_tied_A_event_B_censored():
    # tA==tB, A event, B censored: A=1, B=0.
    # rank[A] = 0.5 + 1.0 = 1.5; rank[B] = 0.0 + 0.5 = 0.5.
    np.testing.assert_allclose(_ranks([1.0, 1.0], [1, 0]), [1.5, 0.5])


def test_rule3_tied_A_censored_B_event():
    np.testing.assert_allclose(_ranks([1.0, 1.0], [0, 1]), [0.5, 1.5])


def test_rule4_tA_lt_tB_A_event_B_censored():
    # A event at earlier time vs B censored later: A=1, B=0.
    np.testing.assert_allclose(_ranks([1.0, 2.0], [1, 0]), [1.5, 0.5])


def test_rule4_reversed_tA_gt_tB_A_censored_B_event():
    # A censored at later time, B event earlier: A=0, B=1.
    np.testing.assert_allclose(_ranks([2.0, 1.0], [0, 1]), [0.5, 1.5])


def test_rule5_A_censored_then_B_event():
    """tA<tB, A censored, B event. sA = rho(tA, tB); sB = 1 - rho(tA, tB).

    With just these two subjects, lifelines and our KM put a censoring at
    tA=1 and an event at tB=2 with n_at_risk=1, so sr(2)=0 and rho(1,2)=1.
    """
    T = np.array([1.0, 2.0])
    E = np.array([0, 1], dtype=np.int8)
    sr_times, sr_vals = _kaplan_meier(T, E)
    r = _rho(sr_times, sr_vals, 1.0, 2.0)
    assert r == pytest.approx(1.0)
    np.testing.assert_allclose(_ranks(T, E), [0.5 + r, (1.0 - r) + 0.5])


def test_rule5_reversed_A_event_later_than_B_censored():
    """tA>tB, A event, B censored: sA = 1 - rho(tB, tA); sB = rho(tB, tA)."""
    T = np.array([2.0, 1.0])
    E = np.array([1, 0], dtype=np.int8)
    sr_times, sr_vals = _kaplan_meier(T, E)
    r = _rho(sr_times, sr_vals, 1.0, 2.0)
    np.testing.assert_allclose(_ranks(T, E), [(1.0 - r) + 0.5, 0.5 + r])


def test_rule6_both_censored_distinct_times_uses_rho():
    """Both censored at different times; with a third subject (an event)
    providing KM curvature so rho is non-trivial.

    Dataset: T=[1, 3, 2], E=[0, 0, 1]. Subjects of interest: indices 0 and 1
    (both censored). Index 2 is the event that bends the KM curve.

    For subject pair (0,1): tA=1, tB=3, both censored, tA<tB.
    rule 6 forward: sA(0,1) = (1+rho(1,3))/2; sB(1,0) = (1-rho(1,3))/2.
    """
    T = np.array([1.0, 3.0, 2.0])
    E = np.array([0, 0, 1], dtype=np.int8)
    sr_times, sr_vals = _kaplan_meier(T, E)
    r = _rho(sr_times, sr_vals, 1.0, 3.0)
    # Sanity check: rho should be > 0 because there is an event between t=1 and t=3.
    assert r > 0.0

    ranks = _ranks(T, E)

    # rank[0] (t=1, censored): self 0.5 + vs idx1 (rule6 fwd) (1+r)/2
    #                        + vs idx2 (rule5 reversed: tA=1<tB=2, A censored, B event) = rho(1,2)
    r_12 = _rho(sr_times, sr_vals, 1.0, 2.0)
    expected_0 = 0.5 + (1.0 + r) / 2.0 + r_12

    # rank[1] (t=3, censored): self 0.5 + vs idx0 (rule6 reversed) (1-r)/2
    #                        + vs idx2 (tA=3 > tB=2, A censored later than B's event:
    #                          symmetric to rule 4 — B's event is definitively earlier,
    #                          so sA = 0.0)
    expected_1 = 0.5 + (1.0 - r) / 2.0 + 0.0

    np.testing.assert_allclose([ranks[0], ranks[1]], [expected_0, expected_1])
