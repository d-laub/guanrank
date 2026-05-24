# CI & Release Pipelines Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add GitHub Actions CI for every PR (lint via prek; test on Python 3.10–3.14 × {ubuntu, macos}) plus a manually-triggered release workflow that bumps the version with Commitizen, tags, generates a changelog, builds a wheel, publishes to PyPI via OIDC, and creates a GitHub Release.

**Architecture:** Lint runs prek once and lets `.pre-commit-config.yaml` drive every check (standard hooks + ruff + pyrefly). Tests use Pixi composed envs (`pyNNN-test`) so each matrix cell maps to one env name. Release is `workflow_dispatch`, gated by a `pypi` GitHub Environment for manual approval before publish; PyPI auth is OIDC trusted publishing — no long-lived tokens.

**Tech Stack:** GitHub Actions, Pixi (prefix-dev/setup-pixi), prek (j178/prek-action), Ruff, Pyrefly, Commitizen, uv (`uv build`), `pypa/gh-action-pypi-publish`, `gh` CLI.

**Spec:** `docs/superpowers/specs/2026-05-24-ci-and-release-design.md`

**Validation approach:** This is infrastructure, not application code — TDD shape adapts. Each config/workflow change is validated with the closest cheap check available: `pixi info` for envs, `cz bump --dry-run` for commitizen, `prek run --all-files` for hook config, `actionlint` for workflows, and finally a real PR smoke test on the live runners.

---

## Pre-flight

### Task 0: Create a working branch

**Files:** none.

- [ ] **Step 1: Create and switch to a feature branch**

```bash
git checkout -b ci/add-pipelines
```

- [ ] **Step 2: Confirm clean tree**

Run: `git status`
Expected: `On branch ci/add-pipelines` and `nothing to commit, working tree clean`.

- [ ] **Step 3: Install actionlint locally for workflow validation**

```bash
# macOS
brew install actionlint
# Verify
actionlint -version
```
Expected: prints a version string.

If brew is unavailable, download a release binary from https://github.com/rhysd/actionlint/releases and place it on `PATH`.

---

## Phase 1 — Tooling config (no workflows yet)

### Task 1: Add composed `pyNNN-test` envs to `pixi.toml`

**Files:**
- Modify: `pixi.toml` (the `[environments]` table)

- [ ] **Step 1: Edit `pixi.toml`**

Replace the existing `[environments]` block with:

```toml
[environments]
default    = ["py310"]
test       = ["py310", "test"]
py310      = ["py310"]
py311      = ["py311"]
py312      = ["py312"]
py313      = ["py313"]
py314      = ["py314"]
py310-test = ["py310", "test"]
py311-test = ["py311", "test"]
py312-test = ["py312", "test"]
py313-test = ["py313", "test"]
py314-test = ["py314", "test"]
```

- [ ] **Step 2: Verify pixi resolves every env**

Run: `pixi info`
Expected: lists all 12 environments without errors. If any env fails to solve (e.g. numba wheel missing for a (python, platform) combo), record which one in a comment in the plan and continue — we use `fail-fast: false` in CI so it will be visible there too.

- [ ] **Step 3: Smoke-test one composed env runs the test task**

Run: `pixi run -e py310-test test`
Expected: pytest collects and the existing test suite passes.

- [ ] **Step 4: Commit**

```bash
git add pixi.toml pixi.lock
git commit -m "chore: add composed pyNNN-test pixi envs for CI matrix"
```

---

### Task 2: Add Commitizen config to `pyproject.toml`

**Files:**
- Modify: `pyproject.toml` (append a new section)

- [ ] **Step 1: Append the commitizen config**

Append to the end of `pyproject.toml`:

```toml
[tool.commitizen]
name = "cz_conventional_commits"
version_provider = "pep621"
tag_format = "v$version"
update_changelog_on_bump = true
changelog_file = "CHANGELOG.md"
major_version_zero = true
```

- [ ] **Step 2: Verify commitizen reads the config**

Run: `pixi run -e test cz version --project`
Expected: prints `0.1.0` (the current `[project].version`).

If `cz` is not in the `test` env, install it ad-hoc for the check:
```bash
pixi run -e test uv tool run --from commitizen cz version --project
```

- [ ] **Step 3: Dry-run a bump to confirm the config is wired**

Run: `pixi run -e test cz bump --dry-run --yes --increment PATCH`
Expected: prints the planned new version (`0.1.1`) and the files it would touch (`pyproject.toml`, `CHANGELOG.md`). No files actually change.

If it errors with "No commits found", that's also acceptable here — it proves the tool ran with the right config. The release workflow always passes an explicit `--increment` when the user provides one.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: configure commitizen for pep621 version bumps"
```

---

### Task 3: Add Pyrefly config and pre-commit hook

**Files:**
- Modify: `pyproject.toml` (append `[tool.pyrefly]`)
- Modify: `.pre-commit-config.yaml` (append pyrefly hook)

- [ ] **Step 1: Look up the latest pyrefly pre-commit hook version**

Run: `gh api repos/facebook/pyrefly/releases/latest --jq .tag_name`
Record the tag (e.g. `v0.X.Y`). If pyrefly does not yet publish an official pre-commit hook in that repo (check `https://github.com/facebook/pyrefly#pre-commit`), fall back to the `local` hook variant in Step 3.

- [ ] **Step 2: Append pyrefly config to `pyproject.toml`**

```toml
[tool.pyrefly]
project-includes = ["src"]
```

- [ ] **Step 3: Append the pyrefly hook to `.pre-commit-config.yaml`**

If upstream publishes a hook:

```yaml
- repo: https://github.com/facebook/pyrefly
  rev: <tag from step 1>
  hooks:
  - id: pyrefly-check
```

If upstream does not publish a hook, use the local fallback:

```yaml
- repo: local
  hooks:
  - id: pyrefly
    name: pyrefly
    language: system
    entry: pyrefly check
    pass_filenames: false
    files: ^src/.*\.py$
```

The local fallback requires `pyrefly` to be installed in the environment running prek — in CI that's handled by `j178/prek-action`'s auto-install; locally, install once via `pixi run -e test uv tool install pyrefly`.

- [ ] **Step 4: Run prek (or pre-commit) to verify the hook fires**

Run: `pixi run -e test uv tool run --from prek prek run pyrefly --all-files`
(or `pre-commit run pyrefly --all-files` if prek isn't installed)
Expected: pyrefly runs and either passes cleanly or reports actual type issues in `src/guanrank/`. If it reports issues, fix them in this task — type errors block the lint job once CI is on.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .pre-commit-config.yaml
git commit -m "chore: add pyrefly type-check to pre-commit"
```

---

## Phase 2 — Workflows

### Task 4: Create the CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Ensure the workflows directory exists**

```bash
mkdir -p .github/workflows
```

- [ ] **Step 2: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  lint:
    name: lint (prek)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: j178/prek-action@v1
        with:
          extra_args: --all-files

  test:
    name: test (${{ matrix.os }}, ${{ matrix.env }})
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest]
        env: [py310-test, py311-test, py312-test, py313-test, py314-test]
    steps:
      - uses: actions/checkout@v4
      - uses: prefix-dev/setup-pixi@v0.8.14
        with:
          environments: ${{ matrix.env }}
          cache: true
      - name: Run tests
        run: pixi run -e ${{ matrix.env }} test
```

- [ ] **Step 3: Validate with actionlint**

Run: `actionlint .github/workflows/ci.yml`
Expected: no output (success). Fix any reported issues before continuing.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add lint and test workflow for PRs and main"
```

---

### Task 5: Create the release workflow

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Create `.github/workflows/release.yml`**

```yaml
name: Release

on:
  workflow_dispatch:
    inputs:
      increment:
        description: "Version bump (leave empty to auto-detect from conventional commits)"
        required: false
        type: choice
        default: ""
        options:
          - ""
          - PATCH
          - MINOR
          - MAJOR

concurrency:
  group: release
  cancel-in-progress: false

jobs:
  release:
    name: bump, build, publish
    runs-on: ubuntu-latest
    environment:
      name: pypi
      url: https://pypi.org/project/guanrank/
    permissions:
      contents: write
      id-token: write
    steps:
      - name: Checkout main with full history
        uses: actions/checkout@v4
        with:
          ref: main
          fetch-depth: 0

      - name: Configure git identity
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

      - name: Install uv
        uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true

      - name: Install commitizen
        run: uv tool install commitizen

      - name: Run cz bump
        id: bump
        run: |
          if [ -n "${{ inputs.increment }}" ]; then
            cz bump --yes --changelog --increment "${{ inputs.increment }}"
          else
            cz bump --yes --changelog
          fi
          NEW_VERSION="$(cz version --project)"
          echo "version=${NEW_VERSION}" >> "$GITHUB_OUTPUT"
          echo "tag=v${NEW_VERSION}"   >> "$GITHUB_OUTPUT"

      - name: Push commit and tag
        run: git push origin main --follow-tags

      - name: Build sdist and wheel
        run: uv build

      - name: Extract changelog section for this version
        id: notes
        run: |
          python - <<'PY' "${{ steps.bump.outputs.version }}"
          import re, sys, pathlib
          version = sys.argv[1]
          text = pathlib.Path("CHANGELOG.md").read_text()
          # Find a heading containing this version, then capture until the next heading of the same level.
          pattern = rf"(^##\s.*{re.escape(version)}.*?$.*?)(?=^##\s|\Z)"
          m = re.search(pattern, text, flags=re.M | re.S)
          notes = m.group(1).strip() if m else f"Release {version}"
          pathlib.Path("RELEASE_NOTES.md").write_text(notes)
          PY

      - name: Publish to PyPI (OIDC)
        uses: pypa/gh-action-pypi-publish@release/v1

      - name: Create GitHub Release
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh release create "${{ steps.bump.outputs.tag }}" \
            --title "${{ steps.bump.outputs.tag }}" \
            --notes-file RELEASE_NOTES.md \
            dist/*
```

- [ ] **Step 2: Validate with actionlint**

Run: `actionlint .github/workflows/release.yml`
Expected: no output (success). Fix any reported issues before continuing.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: add manual release workflow with cz bump and OIDC PyPI publish"
```

---

## Phase 3 — Smoke test on real runners

### Task 6: Open a PR and verify CI

**Files:** none.

- [ ] **Step 1: Push the branch**

```bash
git push -u origin ci/add-pipelines
```

- [ ] **Step 2: Open a PR against `main`**

```bash
gh pr create --base main --title "ci: add CI and release pipelines" --body "$(cat <<'EOF'
## Summary
- Adds lint (prek) and test (Python 3.10–3.14 × ubuntu/macos) CI on every PR
- Adds manually-triggered release workflow: cz bump → tag → build → PyPI (OIDC) → GitHub Release
- Adds pyrefly type-checking via pre-commit
- Adds composed `pyNNN-test` pixi envs for the matrix
- Adds `[tool.commitizen]` and `[tool.pyrefly]` config

Spec: `docs/superpowers/specs/2026-05-24-ci-and-release-design.md`
Plan: `docs/superpowers/plans/2026-05-24-ci-and-release-pipelines.md`

## Test plan
- [ ] `lint` job passes on this PR
- [ ] All 10 `test` matrix cells pass (or document any genuinely-broken `(os, py)` cells)
EOF
)"
```

- [ ] **Step 3: Watch the run**

```bash
gh pr checks --watch
```
Expected: `lint` and all 10 `test (...)` checks pass.

- [ ] **Step 4: Triage failures**

For each failing cell:
- If it's a pixi solve failure for a specific `(os, python)` (e.g. no numba wheel yet for py314 on macOS), document it in the PR description, and in this plan, then remove that single matrix entry from `.github/workflows/ci.yml` with an inline comment noting why and when to re-add. Re-push.
- If lint fails because of pyrefly findings in `src/`, fix the type errors in a new commit on this branch.

- [ ] **Step 5: Merge the PR**

Once green:
```bash
gh pr merge --squash --delete-branch
```

---

### Task 7: Verify the release workflow with a dry run (optional but recommended)

**Files:** none.

- [ ] **Step 1: Confirm one-time setup is in place**

Verify (all should already be done per the user):
- PyPI trusted publisher exists for project `guanrank`, repo `d-laub/guanrank`, workflow `release.yml`, environment `pypi`.
- GitHub Environment `pypi` exists with the maintainer as a required reviewer.
- `main` allows `github-actions[bot]` to push (no protection rule blocks it, or a bypass is granted).

Run: `gh api repos/d-laub/guanrank/environments/pypi --jq '.name,.protection_rules'`
Expected: `pypi` environment exists with a `required_reviewers` rule.

- [ ] **Step 2: Trigger the release workflow with `PATCH`**

```bash
gh workflow run release.yml -f increment=PATCH
gh run watch
```

- [ ] **Step 3: Approve the `pypi` environment when prompted**

The run will pause before the publish step. Approve in the GitHub UI (Actions → the run → Review deployments).

- [ ] **Step 4: Verify outputs**

After the run finishes:
```bash
gh release view v0.1.1
# pypi page (open in browser)
open https://pypi.org/project/guanrank/
```
Expected: release `v0.1.1` exists on GitHub with sdist + wheel attached and release notes from `CHANGELOG.md`; the version is live on PyPI.

- [ ] **Step 5: If anything fails after the tag is pushed**

Do **not** re-run the workflow (it would try to double-bump). Instead:
- If publish failed: `gh workflow run release.yml` is unsafe; manually `uv build` from the tagged commit and `uv publish` (or `twine upload`).
- If the tag was wrong: `git push --delete origin v0.1.1 && git tag -d v0.1.1`, revert the bump commit on `main`, and re-run.

If you skip Task 7, the first real release will exercise this code path — that's acceptable since it's `PATCH` from `0.1.0` and easy to roll back.

---

## Self-Review

**Spec coverage:**
- CI on PR + push to main → Task 4 ✓
- Lint via prek covering standard + ruff + pyrefly → Tasks 3, 4 ✓
- Test matrix Python 3.10–3.14 × {ubuntu, macos} → Tasks 1, 4 ✓
- Manual release with cz bump + tag + changelog → Task 5 ✓
- Wheel build + OIDC PyPI publish + GitHub Release → Task 5 ✓
- `pypi` environment manual gate → Task 5 ✓
- `pixi.toml` composed envs → Task 1 ✓
- `pyproject.toml` `[tool.commitizen]` + `[tool.pyrefly]` → Tasks 2, 3 ✓
- `.pre-commit-config.yaml` pyrefly hook → Task 3 ✓
- One-time PyPI/Environment/branch-protection setup → Task 7 Step 1 (verification only; user reports done) ✓
- `RELEASING.md` runbook → explicitly out of scope in spec; not planned ✓

**Placeholder scan:** Pyrefly rev tag is fetched at execution time (Task 3 Step 1), not left as a placeholder — the step says exactly how to get it. Pixi solve gaps (Task 1 Step 2) and CI matrix failures (Task 6 Step 4) have explicit triage instructions, not "handle errors".

**Type consistency:** Workflow output names (`steps.bump.outputs.version`, `.tag`) are consistent across Task 5. Env names match between Task 1 (`pyNNN-test`) and Task 4 matrix. Tag format `v$version` in Task 2 matches `v${NEW_VERSION}` in Task 5.
