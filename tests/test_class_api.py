"""Tests for the sklearn-style `GuanRank` class."""

from __future__ import annotations

import numpy as np
import pytest

from guanrank import GuanRank, guanrank


def test_transform_before_fit_raises():
    gr = GuanRank()
    with pytest.raises(RuntimeError):
        gr.transform([1.0, 2.0], [1, 0])


def test_fit_returns_self():
    gr = GuanRank()
    out = gr.fit([1.0, 2.0, 3.0], [1, 0, 1])
    assert out is gr


def test_fit_transform_equals_functional_guanrank(random_dataset):
    T, E = random_dataset
    expected = guanrank(T, E)
    actual = GuanRank().fit_transform(T, E)
    np.testing.assert_array_equal(actual, expected)


def test_fit_then_transform_on_training_data_equals_fit_transform(random_dataset):
    T, E = random_dataset
    a = GuanRank().fit_transform(T, E)
    gr = GuanRank().fit(T, E)
    b = gr.transform(T, E)
    np.testing.assert_array_equal(a, b)


def test_transform_returns_correct_shape():
    gr = GuanRank().fit([1.0, 2.0, 3.0, 4.0], [1, 0, 1, 0])
    out = gr.transform([1.5, 2.5], [1, 0])
    assert out.shape == (2,)


def test_transform_uses_training_km_not_test_data():
    """Held-out transform must use the training KM, not refit on test data.

    Construct a `train` set and a `test` set whose inclusion would materially
    change the KM curve (test contains far-later events). Compare
    `fit(train).transform(test)` to `guanrank(concat(train, test))[test_slice]`,
    which would be the answer if test data were folded back into the fit.
    """
    T_train = np.array([1.0, 2.0, 3.0, 4.0])
    E_train = np.array([1, 0, 1, 0], dtype=np.int8)
    T_test = np.array([50.0, 60.0])
    E_test = np.array([1, 1], dtype=np.int8)

    held_out = GuanRank().fit(T_train, E_train).transform(T_test, E_test)

    T_all = np.concatenate([T_train, T_test])
    E_all = np.concatenate([E_train, E_test])
    pooled = guanrank(T_all, E_all)[len(T_train) :]

    # The two must differ: if they were equal, training-only fit would be
    # indistinguishable from refitting on the combined cohort.
    assert not np.allclose(held_out, pooled)


def test_refit_overwrites_state():
    gr = GuanRank()
    gr.fit([1.0, 2.0, 3.0], [1, 1, 1])
    sr_vals_first = gr._sr_vals.copy()

    gr.fit([10.0, 20.0, 30.0], [0, 0, 0])
    assert not np.array_equal(gr._sr_vals, sr_vals_first)


def test_fit_transform_does_not_require_separate_transform_call(random_dataset):
    """`fit_transform` should both fit (populating state) and return ranks."""
    T, E = random_dataset
    gr = GuanRank()
    ranks = gr.fit_transform(T, E)
    assert ranks is not None
    assert gr._sr_times is not None
    assert gr._sr_vals is not None
