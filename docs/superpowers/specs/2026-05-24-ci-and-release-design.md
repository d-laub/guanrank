# CI & Release Pipelines — Design

**Date:** 2026-05-24
**Status:** Approved (pending implementation plan)

## Goal

Add GitHub Actions automation for:

1. **CI on every PR and push to `main`**: lint (via prek, covering standard hooks + ruff + pyrefly) and test across every supported Python version (3.10–3.14) on Linux and macOS.
2. **Manually triggered release pipeline**: bump version with Commitizen, tag, generate changelog, build wheels, publish to PyPI via OIDC trusted publishing, and create a GitHub Release.

## Non-Goals

- Windows support (not in `pixi.toml` platforms).
- `cibuildwheel` / compiled-extension matrix builds — the package is pure Python (numba is a runtime dependency, not a C extension).
- Auto-release on merge — releases are explicitly manual.

## Files Added / Changed

| Path | Action |
| --- | --- |
| `.github/workflows/ci.yml` | new |
| `.github/workflows/release.yml` | new |
| `.pre-commit-config.yaml` | add pyrefly hook |
| `pixi.toml` | add combined per-Python test envs |
| `pyproject.toml` | add `[tool.commitizen]` and `[tool.pyrefly]` sections |

## CI Workflow (`.github/workflows/ci.yml`)

**Triggers:** `pull_request` (any branch), `push` to `main`.

**Permissions:** `contents: read` only.

**Concurrency:** group by ref, cancel-in-progress, so superseded PR pushes don't burn runners.

### Job: `lint`

- Runs on `ubuntu-latest`.
- Steps:
  1. `actions/checkout@v4`
  2. `j178/prek-action@v1` with `extra_args: --all-files`

This single invocation runs every hook in `.pre-commit-config.yaml`: pre-commit-hooks standard checks, `ruff-check`, `ruff-format`, and the new `pyrefly` hook. The `commitizen` hook is `stages: [commit-msg]` so it's a no-op under `--all-files`.

### Job: `test`

- Strategy: `fail-fast: false`, matrix:
  - `os: [ubuntu-latest, macos-latest]`
  - `env: [py310-test, py311-test, py312-test, py313-test, py314-test]`
- Steps:
  1. `actions/checkout@v4`
  2. `prefix-dev/setup-pixi@v0.8` with `environments: ${{ matrix.env }}` and `cache: true`
  3. `pixi run -e ${{ matrix.env }} test`

Each `pyNNN-test` env in `pixi.toml` is the composition of `feature.pyNNN` and `feature.test`, which gives one cleanly addressable env per matrix cell (see `pixi.toml` changes below).

## Release Workflow (`.github/workflows/release.yml`)

**Trigger:** `workflow_dispatch` with one input:
- `increment` (optional): one of `MAJOR`, `MINOR`, `PATCH`, or empty. Empty = let Commitizen infer from conventional commits since the last tag.

**Permissions:**
- `contents: write` (push the bump commit + tag, create the GitHub Release)
- `id-token: write` (PyPI OIDC)

**Environment:** `pypi` — a GitHub Environment configured with required reviewers, providing a manual approval gate before the publish step runs. The PyPI Trusted Publisher is bound to this environment.

### Steps (single job, `ubuntu-latest`)

1. `actions/checkout@v4` with `fetch-depth: 0` and `ref: main` (Commitizen needs full history to compute the bump).
2. `prefix-dev/setup-pixi@v0.8` with the default env (provides Python; commitizen and uv installed via `uv tool install`), or a dedicated `release` pixi env containing `commitizen` and `uv` — chosen during implementation.
3. Configure git identity: `github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>`.
4. `cz bump --yes --changelog` (with `--increment ${{ inputs.increment }}` if non-empty). This:
   - bumps `version` in `pyproject.toml`,
   - updates `CHANGELOG.md`,
   - creates a commit and an annotated tag matching `tag_format` (see `pyproject.toml` config).
5. `git push origin main --follow-tags`.
6. `uv build` — emits `dist/*.whl` and `dist/*.tar.gz` (pure-Python wheel, single artifact across the matrix).
7. **Manual approval gate** (via the `pypi` environment) before the next step.
8. `pypa/gh-action-pypi-publish@release/v1` — OIDC publish from `dist/`.
9. Extract the new version's section from `CHANGELOG.md` and `gh release create "v${NEW_VERSION}" --notes-file <section-file> dist/*`. The new version is captured from `cz version --project` after the bump.

### One-Time Manual Setup (documented in spec, not in the workflow)

- **PyPI Trusted Publisher** (https://pypi.org/manage/account/publishing/): project `guanrank`, owner `d-laub`, repo `guanrank`, workflow filename `release.yml`, environment `pypi`.
- **GitHub Environment `pypi`**: create under repo Settings → Environments, add required reviewer (the maintainer).
- **Branch protection on `main`**: if protected, allow `github-actions[bot]` to bypass, or convert the release workflow to the PR-based variant (out of scope for this spec).

## `.pre-commit-config.yaml` Changes

Append:

```yaml
- repo: https://github.com/facebook/pyrefly
  rev: <latest tagged release, pinned at implementation time>
  hooks:
  - id: pyrefly-check
```

If the upstream repo does not yet publish a pre-commit hook id, fall back to a `local` hook running `pyrefly check` against `src/`. Decision made at implementation time after checking upstream.

## `pixi.toml` Changes

Add composed test envs so each matrix cell maps to a single env name:

```toml
[environments]
default  = ["py310"]
py310    = ["py310"]
py311    = ["py311"]
py312    = ["py312"]
py313    = ["py313"]
py314    = ["py314"]
test     = ["py310", "test"]        # existing
py310-test = ["py310", "test"]
py311-test = ["py311", "test"]
py312-test = ["py312", "test"]
py313-test = ["py313", "test"]
py314-test = ["py314", "test"]
```

## `pyproject.toml` Changes

Add:

```toml
[tool.commitizen]
name = "cz_conventional_commits"
version_provider = "pep621"           # reads/writes [project].version
tag_format = "v$version"
update_changelog_on_bump = true
changelog_file = "CHANGELOG.md"
major_version_zero = true             # while 0.x, breaking changes bump minor
```

```toml
[tool.pyrefly]
project-includes = ["src"]
```

Exact pyrefly config keys reconciled against the pyrefly version pinned during implementation.

## Failure Modes & Mitigations

| Failure | Mitigation |
| --- | --- |
| Numba/llvmlite wheel unavailable for a `(os, python)` cell | `fail-fast: false` keeps other cells running; we document the gap and either drop that cell or wait for upstream wheels. |
| Branch protection blocks the bump push | Maintainer either grants bypass to `github-actions[bot]` or invokes the workflow with `increment=""` from a temporary unprotected state. |
| `cz bump` finds no conventional commits and no `increment` given | Workflow fails fast with a clear error; maintainer re-runs with explicit `increment`. |
| Publish step fails after tag is pushed | Tag remains; re-running the workflow is unsafe (would double-bump). Recovery: manually `uv build && twine upload` from the tagged commit, or delete the tag and re-run. Documented in a `RELEASING.md` follow-up (out of scope here). |

## Out of Scope (Follow-ups)

- `RELEASING.md` runbook for the manual setup steps and failure recovery.
- Dependabot / Renovate config.
- Coverage reporting.
- PR-based release variant for stricter branch protection.
