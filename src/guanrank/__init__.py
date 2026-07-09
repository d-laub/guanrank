"""GuanRank: hazard ranking algorithm from Huang et al. 2017.

https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005887
"""

from __future__ import annotations

from typing import Sequence, TypeVar

import numpy as np
from numba import njit
from numpy.typing import NDArray
from typing_extensions import Self

_FLOATING = TypeVar("_FLOATING", bound=np.floating)


def _kaplan_meier(
    T: NDArray[_FLOATING], E: NDArray[np.integer]
) -> tuple[NDArray[_FLOATING], NDArray[np.float64]]:
    """Compute KM survival function.

    Returns (sr_times, sr_vals): parallel arrays of unique observed times and
    the survival probability SR(t) at each.  SR(0) = 1.0 is implicit.
    """
    n = len(T)
    order = np.argsort(T, kind="stable")
    T_s = T[order]
    E_s = E[order]

    unique_times, first_idx = np.unique(T_s, return_index=True)
    # last_idx[k] = one past the last occurrence of unique_times[k]
    last_idx = np.append(first_idx[1:], n)

    sr_times = unique_times
    sr_vals = np.empty(len(unique_times), dtype=np.float64)

    sr = 1.0
    n_at_risk = n
    for k in range(len(unique_times)):
        chunk = E_s[first_idx[k] : last_idx[k]]
        d = int(chunk.sum())
        total = last_idx[k] - first_idx[k]
        if n_at_risk > 0:
            sr = sr * (n_at_risk - d) / n_at_risk
        sr_vals[k] = sr
        n_at_risk -= total

    return sr_times, sr_vals


@njit(cache=True)
def _sr_at(
    sr_times: NDArray[np.floating], sr_vals: NDArray[_FLOATING], t: _FLOATING
) -> float:
    """Step-function KM lookup: last SR value at a time <= t."""
    lo, hi = 0, len(sr_times)
    while lo < hi:
        mid = (lo + hi) // 2
        if sr_times[mid] <= t:
            lo = mid + 1
        else:
            hi = mid
    return sr_vals[lo - 1] if lo > 0 else 1.0


@njit(cache=True)
def _rho(
    sr_times: NDArray[np.floating],
    sr_vals: NDArray[_FLOATING],
    t1: _FLOATING,
    t2: _FLOATING,
) -> float:
    """Conditional probability of event in (t1, t2] given no event before t1."""
    sr1 = _sr_at(sr_times, sr_vals, t1)
    if sr1 == 0.0:
        return 0.0
    sr2 = _sr_at(sr_times, sr_vals, t2)
    return 1.0 - sr2 / sr1


@njit(cache=True)
def _compute_ranks(
    sr_times: NDArray[np.floating],
    sr_vals: NDArray[np.floating],
    T_fit: NDArray[np.floating],
    E_fit: NDArray[np.integer],
    T_new: NDArray[np.floating],
    E_new: NDArray[np.integer],
) -> NDArray[np.float64]:
    """Compute hazard ranks for T_new/E_new by comparing against T_fit/E_fit."""
    n_new = len(T_new)
    n_fit = len(T_fit)
    ranks = np.zeros(n_new, dtype=np.float64)
    for i in range(n_new):
        tA = T_new[i]
        eA = E_new[i]
        score = 0.0
        for j in range(n_fit):
            tB = T_fit[j]
            eB = E_fit[j]
            if eA and eB:
                # Rule 1: both events
                if tA < tB:
                    sA = 1.0
                elif tA > tB:
                    sA = 0.0
                else:
                    sA = 0.5
            elif (not eA) and (not eB):
                if tA == tB:
                    # Rule 2
                    sA = 0.5
                elif tA < tB:
                    # Rule 6
                    r = _rho(sr_times, sr_vals, tA, tB)
                    sA = (1.0 + r) / 2.0
                else:
                    # Rule 6 (symmetric)
                    r = _rho(sr_times, sr_vals, tB, tA)
                    sA = (1.0 - r) / 2.0
            elif eA and (not eB):
                if tA == tB:
                    # Rule 3 (A is event)
                    sA = 1.0
                elif tA < tB:
                    # Rule 4
                    sA = 1.0
                else:
                    # Rule 5 reversed: B censored at tB < tA, A has later event
                    r = _rho(sr_times, sr_vals, tB, tA)
                    sA = 1.0 - r
            else:
                # not eA and eB
                if tA == tB:
                    # Rule 3 (A is censored)
                    sA = 0.0
                elif tB < tA:
                    # Rule 4 reversed
                    sA = 0.0
                else:
                    # Rule 5: A censored at tA < tB, B has event
                    r = _rho(sr_times, sr_vals, tA, tB)
                    sA = r
            score += sA
        ranks[i] = score
    return ranks


def _to_arrays(
    T: Sequence[float], E: Sequence[int]
) -> tuple[NDArray[np.float64], NDArray[np.int8]]:
    return np.asarray(T, dtype=np.float64), np.asarray(E, dtype=np.int8)


def guanrank(T: Sequence[float], E: Sequence[int]) -> NDArray[np.float64]:
    """Compute normalized GuanRank hazard ranks for a dataset.

    Builds the Kaplan-Meier survival curve, scores every ordered pair of
    subjects with the six GuanRank rules, and sums each subject's pairwise
    scores into a raw hazard rank. Following Huang et al. (2017), the raw ranks
    are normalized by dividing by the largest rank in the dataset, so the
    highest-hazard subject maps to 1.0.

    Args:
        T: Time-to-event or censoring time for each subject.
        E: Event indicators, 1 if the event occurred and 0 if censored.

    Returns:
        Hazard rank for each subject, in the same order as the inputs. Higher
        means higher risk of an earlier event. Ranks lie in ``(0, 1]``, with the
        highest-hazard subject at 1.0.
    """
    T_arr, E_arr = _to_arrays(T, E)
    sr_times, sr_vals = _kaplan_meier(T_arr, E_arr)
    raw = _compute_ranks(sr_times, sr_vals, T_arr, E_arr, T_arr, E_arr)
    return raw / raw.max()


class GuanRank:
    """Sklearn-style transformer for the GuanRank hazard ranking algorithm.

    GuanRank (Huang et al., 2017) turns right-censored survival data into a
    single continuous hazard rank per subject, suitable as a regression target.
    It builds the Kaplan-Meier survival curve, scores every ordered pair of
    subjects with six rules that account for censoring, and sums each subject's
    pairwise scores into a raw rank. Raw ranks are normalized by the largest
    rank in the training cohort, so the highest-hazard training subject maps to
    1.0.

    Fitting learns the training cohort's Kaplan-Meier curve and normalization
    constant; held-out subjects are scored against that cohort and divided by
    the same training maximum. In-sample ranks lie in ``(0, 1]``. Out-of-sample
    ranks share that scale but may exceed 1.0 when a subject is riskier than
    every training subject (an earlier event than the whole cohort).

    Example:
        >>> gr = GuanRank()
        >>> train_ranks = gr.fit_transform(T_train, E_train)
        >>> test_ranks = gr.transform(T_test, E_test)
    """

    _sr_times: NDArray[np.floating] | None = None
    _sr_vals: NDArray[np.floating] | None = None
    _T_fit: NDArray[np.floating] | None = None
    _E_fit: NDArray[np.integer] | None = None
    _rank_max: float | None = None
    _train_ranks: NDArray[np.float64] | None = None

    def __init__(self) -> None:
        self._sr_times = None
        self._sr_vals = None
        self._T_fit = None
        self._E_fit = None
        self._rank_max = None
        self._train_ranks = None

    def fit(self, T: Sequence[float], E: Sequence[int]) -> Self:
        """Fit the Kaplan-Meier curve and normalization constant on training data.

        Args:
            T: Time-to-event or censoring time for each training subject.
            E: Event indicators, 1 if the event occurred and 0 if censored.

        Returns:
            The fitted estimator (``self``).
        """
        self._T_fit, self._E_fit = _to_arrays(T, E)
        self._sr_times, self._sr_vals = _kaplan_meier(self._T_fit, self._E_fit)
        self._train_ranks = _compute_ranks(
            self._sr_times,
            self._sr_vals,
            self._T_fit,
            self._E_fit,
            self._T_fit,
            self._E_fit,
        )
        self._rank_max = float(self._train_ranks.max())
        return self

    def transform(self, T: Sequence[float], E: Sequence[int]) -> NDArray[np.float64]:
        """Score new subjects against the fitted training cohort.

        Args:
            T: Time-to-event or censoring time for each subject to score.
            E: Event indicators, 1 if the event occurred and 0 if censored.

        Returns:
            Normalized hazard rank for each subject, in input order, divided by
            the training cohort's maximum rank. Values lie in ``(0, 1]`` for
            subjects no riskier than the training cohort and may exceed 1.0 for
            subjects riskier than every training subject.

        Raises:
            RuntimeError: If called before ``fit``.
        """
        if self._sr_times is None:
            raise RuntimeError("Call fit() before transform().")
        assert self._sr_vals is not None
        assert self._T_fit is not None
        assert self._E_fit is not None
        assert self._rank_max is not None

        T_arr, E_arr = _to_arrays(T, E)
        raw = _compute_ranks(
            self._sr_times, self._sr_vals, self._T_fit, self._E_fit, T_arr, E_arr
        )
        return raw / self._rank_max

    def fit_transform(
        self, T: Sequence[float], E: Sequence[int]
    ) -> NDArray[np.float64]:
        """Fit on ``T``/``E`` and return the training subjects' normalized ranks.

        Args:
            T: Time-to-event or censoring time for each subject.
            E: Event indicators, 1 if the event occurred and 0 if censored.

        Returns:
            Normalized hazard rank for each subject, in input order. Ranks lie
            in ``(0, 1]``, with the highest-hazard subject at 1.0.
        """
        self.fit(T, E)
        assert self._train_ranks is not None
        assert self._rank_max is not None
        return self._train_ranks / self._rank_max
