# Add Tests for GuanRank

**Status:** Approved design, ready for implementation plan
**Date:** 2026-05-24

## Goal

Add a pytest test suite covering the GuanRank package: Kaplan-Meier computation, all six pairwise-comparison rules, the end-to-end `guanrank()` function, and the `GuanRank` sklearn-style class API.

## Tooling

- Test framework: `pytest`.
- Reference oracle for KM: `lifelines.KaplanMeierFitter`.
- Both deps live under a new `test` feature in `pixi.toml`, with a `test` environment composed of `["py310", "test"]`. This keeps `lifelines` out of the default install.
- Add `[tasks] test = "pytest"`.

## Layout

```
tests/
  conftest.py         # shared fixtures
  test_kaplan_meier.py
  test_rules.py
  test_guanrank.py    # end-to-end + invariants
  test_class_api.py
```

`conftest.py` provides:
- Small hand-built datasets (N=2..6) used by rule tests.
- A seeded random dataset (N≈100) used by KM and invariant tests.
- A session-scoped JIT-warmup fixture that calls `guanrank([0.0, 1.0], [1, 0])` once so numba compilation cost does not appear in individual test timings.

## `test_kaplan_meier.py`

Compare `_kaplan_meier(T, E)` against `lifelines.KaplanMeierFitter` at every unique observed time. Tolerance: `atol=1e-12, rtol=1e-12`.

Cases:
- Seeded random dataset (N≈100, mixed events/censoring).
- All events (no censoring).
- All censored.
- Ties in times with mixed event/censoring at the tied time.
- Single-subject dataset (event and censored variants).
- Tie-ordering: at a tied time with both an event and a censoring, the KM step must apply the event's hazard before removing the censored subject (matches lifelines' convention).

`_sr_at(sr_times, sr_vals, t)`:
- `t` strictly less than first observed time → `1.0`.
- `t` exactly equal to an observed time → `sr_vals` at that index.
- `t` between observed times → `sr_vals` at the largest index with `sr_times ≤ t`.
- `t` greater than the last observed time → final `sr_vals` entry.

## `test_rules.py`

For each of rules 1–6 and their symmetric variants embedded in `_compute_ranks`, construct the minimal 2-subject dataset that exercises exactly that branch, call `guanrank(T, E)`, and assert both subjects' ranks. Where ρ is involved (rules 5, 6), compute the expected ρ from the trivial 2-point KM curve in the test itself; do not hard-code numeric expectations.

Each subject's rank includes the self-comparison contribution of 0.5 (the `eA == eB` and `tA == tB` branch with i == j). Assertions must account for this.

Branches to cover (rule numbers from `guankrank_alg.md`):
1. Both events, distinct times.
2. Both events, tied times.
3. Both censored, tied times.
4. Tied times, one event one censored (both directions).
5. `tA < tB`, A event, B event (rule 4 forward).
6. `tA > tB`, A event, B event (rule 4 reversed).
7. `tA < tB`, A censored, B event (rule 5 forward).
8. `tA > tB`, A event, B censored (rule 5 reversed).
9. `tA < tB`, both censored (rule 6 forward).
10. `tA > tB`, both censored (rule 6 reversed).

Plus one composite N=4 fixture that forces multiple rules to coexist, with all expected ranks computed in-test from the rule definitions and the dataset's KM.

## `test_guanrank.py` — end-to-end and invariants

- **Bounds:** `0.0 ≤ rank[i] ≤ N` for all `i`, on the seeded random dataset.
- **Pairwise-sum invariant:** for every off-diagonal pair `(i, j)`, the contributions `s(i,j) + s(j,i) = 1`. Verified by computing the full score matrix via N applications of `guanrank` over reordered single-element comparisons is overkill; instead, assert the aggregate consequence: `sum(ranks) == N*(N-1)/2 + N*0.5`. The `+ N*0.5` accounts for the self-comparison contribution of each subject. The exact constant will be re-verified against the implementation when writing the test; if the implementation excludes self-comparisons in practice the constant collapses to `N*(N-1)/2`.
- **All events, distinct times:** ranks are a permutation of `{0.5, 1.5, …, N-0.5}`, with the earliest event receiving the highest rank.
- **All censored, equal times:** every rank equals `N * 0.5`.
- **Determinism:** two calls on the same input produce bitwise-identical arrays.

## `test_class_api.py`

- `GuanRank().transform(T, E)` before `fit` raises `RuntimeError`.
- `fit(T, E)` returns `self`.
- `fit_transform(T, E)` equals `guanrank(T, E)` elementwise.
- `fit(train).transform(train)` equals `fit_transform(train)` elementwise.
- `transform(test)` returns shape `(len(test),)`.
- Held-out semantics: after `gr.fit(train)`, `gr.transform(test)` uses the *training* KM curve. Verify by constructing `test` data whose inclusion would materially change the KM (e.g., much later times with events), fitting on `train` alone, and asserting `gr.transform(test)` differs from the corresponding entries of `guanrank(np.concatenate([train, test]), ...)`.
- Refitting: calling `fit` a second time on a different dataset overwrites `_sr_times`, `_sr_vals`, `_T_fit`, `_E_fit`.

## Out of scope

- Performance/benchmark tests.
- Property-based testing (hypothesis).
- CI configuration (separate concern).
- Documentation changes beyond this spec.
