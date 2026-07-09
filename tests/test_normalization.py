"""Normalization to [0, 1] against the training cohort's maximum rank.

Huang et al. (2017) normalize each hazard rank by dividing by the highest rank
in the training set, so the highest-hazard training subject maps to 1.0.
"""

from __future__ import annotations

import numpy as np
import pytest

from guanrank import GuanRank, _compute_ranks, _kaplan_meier, guanrank


def _raw(T, E):
    T = np.asarray(T, dtype=np.float64)
    E = np.asarray(E, dtype=np.int8)
    sr_times, sr_vals = _kaplan_meier(T, E)
    return _compute_ranks(sr_times, sr_vals, T, E, T, E)


def test_functional_guanrank_max_is_one():
    T = [1.0, 2.0, 3.0, 4.0]
    E = [1, 0, 1, 0]
    ranks = guanrank(T, E)
    assert ranks.max() == pytest.approx(1.0)


def test_functional_guanrank_within_unit_interval():
    rng = np.random.default_rng(0xC0FFEE)
    T = rng.uniform(0.0, 100.0, size=100)
    E = rng.integers(0, 2, size=100).astype(np.int8)
    ranks = guanrank(T, E)
    assert (ranks > 0.0).all()
    assert (ranks <= 1.0).all()


def test_functional_guanrank_is_raw_divided_by_max():
    T = [1.0, 2.0, 3.0, 4.0]
    E = [1, 0, 1, 0]
    raw = _raw(T, E)
    np.testing.assert_allclose(guanrank(T, E), raw / raw.max())


def test_fit_transform_max_is_one():
    T = [1.0, 2.0, 3.0, 4.0]
    E = [1, 0, 1, 0]
    ranks = GuanRank().fit_transform(T, E)
    assert ranks.max() == pytest.approx(1.0)


def test_transform_normalizes_by_training_max_not_per_call():
    """A held-out subject riskier than every training subject exceeds 1.0.

    Normalizing by the training maximum (not the transform call's own maximum)
    means an out-of-sample subject with an earlier event than the whole training
    cohort gets a raw rank above the training max, hence a normalized rank > 1.0.
    """
    T_train = [1.0, 2.0, 3.0, 4.0]
    E_train = [1, 0, 1, 0]
    gr = GuanRank().fit(T_train, E_train)

    # Event earlier than any training subject -> raw score of 1.0 vs each of the
    # 4 training subjects -> raw 4.0, above the training max (3.5).
    out = gr.transform([0.5], [1])
    assert out[0] > 1.0
