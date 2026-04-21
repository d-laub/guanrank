# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Python implementation of the GuanRank hazard ranking algorithm ([Huang et al. 2017](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005887)). Assigns hazard risk ranks to subjects from survival/censoring data.

## Commands

```bash
# Install (editable)
uv pip install -e .

# Lint / format
ruff check --fix
ruff format

# Pre-commit
pre-commit run --all-files
```

Environment managed via Pixi (Python 3.10–3.14 supported):
```bash
pixi install
```

No tests configured yet.

## Architecture

All code lives in `src/guanrank/__init__.py`.

**Pipeline:**
1. `_kaplan_meier(t, e)` — builds KM survival function from event times
2. `_sr_at(km_times, km_surv, t)` — JIT-compiled KM lookup at time `t`
3. `_rho(t_i, t_j, e_i, e_j, km_times, km_surv)` — pairwise conditional probability via KM
4. `_compute_ranks(t, e, km_times, km_surv)` — JIT-compiled core: applies 6 pairwise rules to assign hazard scores
5. `guanrank(t, e)` — top-level function returning rank array

**Class API:** `GuanRank` — sklearn-compatible transformer with `.fit()` / `.transform()` / `.fit_transform()`. Stores KM curve from training data for out-of-sample transforms.

**Performance:** `_compute_ranks` and `_sr_at` are Numba JIT-compiled (`@njit`). First call incurs compilation overhead.

Algorithm rules are documented in `guankrank_alg.md`.
