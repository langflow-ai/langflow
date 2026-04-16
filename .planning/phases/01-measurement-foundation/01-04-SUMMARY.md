---
phase: 01-measurement-foundation
plan: 04
subsystem: measurement-infra
tags: [docker, benchmarks, cold-start, python-3.13, uv, hyperfine]
requires:
  - plan 01 adds the `benchmarks` dep-group to pyproject.toml and regenerates uv.lock
  - plan 02 creates `src/backend/tests/benchmarks/fixtures/` (noop_flow, basic_prompting)
provides:
  - src/backend/tests/benchmarks/Dockerfile (93 lines) with BENCH_VARIANT=lean|prebaked
  - src/backend/tests/benchmarks/.dockerignore (47 lines) documenting build-context exclusions
affects:
  - MEAS-02 (hyperfine install via apt on Debian 13 confirmed; A2 holds, version 1.19.0)
  - MEAS-07 (two-image dep-install-isolation strategy is build-ready, awaits plan 05 driver)
tech-stack:
  added:
    - python:3.13-slim (base image pin, no digest yet)
    - ghcr.io/astral-sh/uv (COPY-from of /uv and /uvx binaries)
    - hyperfine 1.19.0 (apt, Debian 13 trixie)
  patterns:
    - uv sync --no-default-groups --group benchmarks (avoid dev group's heavy toolchain deps)
    - uv pip install --python /app/.venv/bin/python (prebake into managed venv, not --system)
    - UV_NO_SYNC=1 env var (runtime uv run reuses synced venv, does not re-resolve)
key-files:
  created:
    - src/backend/tests/benchmarks/Dockerfile
    - src/backend/tests/benchmarks/.dockerignore
  modified: []
decisions:
  - "Pass --no-default-groups to all `uv sync` calls so dev group (crosshair-tool -> gcc) is skipped. D-09 called for `only lfx + benchmark deps`; without --no-default-groups, uv sync silently installs the default dev group."
  - "Set UV_NO_SYNC=1 and UV_NO_DEFAULT_GROUPS=1 as image-wide ENV. `uv run` otherwise triggers a fresh sync with default groups on every container start, re-pulling the dev group and failing on gcc-missing systems."
  - "Include README.md in each workspace member's COPY layer. hatchling's editable-build metadata introspection (triggered by `uv sync` when it builds `langflow-base`, `lfx`, etc.) validates `readme = 'README.md'` field; without the file present, sync fails with 'Readme file does not exist'."
metrics:
  duration_minutes: ~25
  completed_date: 2026-04-16
  tasks_completed: 3
  commits: 3
---

# Phase 1 Plan 04: Measurement Dockerfile Summary

One-liner: Two-image measurement Dockerfile (`benchmarks-lean` + `benchmarks-prebaked`) on `python:3.13-slim` with `uv` + `hyperfine` + BENCH_VARIANT build arg, validated end-to-end via podman build + smoke runs.

## Files Created

| Path | Lines | Purpose |
|------|-------|---------|
| `/Users/ogabrielluiz/Projects/langflow/.claude/worktrees/agent-afb94e78/src/backend/tests/benchmarks/Dockerfile` | 93 | Measurement Dockerfile with lean/prebaked variants (D-07, D-08, D-09, D-11, D-12). |
| `/Users/ogabrielluiz/Projects/langflow/.claude/worktrees/agent-afb94e78/src/backend/tests/benchmarks/.dockerignore` | 47 | Documentation of exclusions needed at build-context root. |

## Commits

| Hash | Message |
|------|---------|
| `e5da9a1f1a` | `feat(01-04): add measurement Dockerfile with lean/prebaked variants` |
| `6acb0c6c0a` | `docs(01-04): add companion .dockerignore for measurement image` |
| `61c3a2fc4e` | `fix(01-04): make measurement Dockerfile buildable against the workspace` |

## Task 3 Checkpoint Verification

Orchestrator is running in --auto mode, so the human-verify checkpoint was executed by the executor itself. The build requires plan 01's `benchmarks` dep-group and plan 02's fixtures directory to be present; both are wave-1 plans in parallel. I temporarily applied plan 01's dep-group definition to `pyproject.toml`, regenerated `uv.lock`, and created a stub fixtures directory solely to exercise the build pipeline, then reverted all stub changes so only plan 04's files are committed. The evidence below is from that run.

Images built: `benchmarks-lean` (exit 0), `benchmarks-prebaked` (exit 0). Full build commands and outputs:

```bash
podman build --build-arg BENCH_VARIANT=lean -t benchmarks-lean \
  -f src/backend/tests/benchmarks/Dockerfile .
# -> Successfully tagged localhost/benchmarks-lean:latest
#    ceffe055f40fb0967c19e7dfefcacab5e36be9123255e1dfa42f4e33ec0929fb

podman build --build-arg BENCH_VARIANT=prebaked -t benchmarks-prebaked \
  -f src/backend/tests/benchmarks/Dockerfile .
# -> Successfully tagged localhost/benchmarks-prebaked:latest
#    2e3ed401585b7f440d5a2bd9b9fc6137c862ecddc7ef3f85bfedbd2b5a816bb4
```

Build-time sanity checks embedded in the Dockerfile:
- Step 20 (`uv run lfx --help > /dev/null 2>&1 && hyperfine --version`) printed `hyperfine 1.19.0`. lfx loads, hyperfine is wired.
- Step 21 on prebaked (`uv run python -c "import openai, langchain_openai; print('prebake-verified')"`) printed `prebake-verified`. Confirms the prebake deps landed in `/app/.venv` (where `uv run` finds them) and NOT in `/usr/local/lib/python3.13/site-packages`. This is the critical `--python /app/.venv/bin/python` vs `--system` correctness check.

Runtime smoke tests (all from executed `podman run --rm ...` commands):

| # | Command | Result | Exit |
|---|---------|--------|------|
| 1 | `podman run --rm benchmarks-lean hyperfine --version` | `hyperfine 1.19.0` | 0 |
| 2 | `podman run --rm benchmarks-lean python --version` | `Python 3.13.13` | 0 |
| 3 | `podman run --rm benchmarks-lean uv run lfx --help` | lfx help screen ("lfx - Langflow Executor") | 0 |
| 4 | `podman run --rm benchmarks-lean which hyperfine` | `/usr/bin/hyperfine` | 0 |
| 5 | `podman run --rm benchmarks-prebaked uv run python -c "import openai, langchain_openai; print('prebaked ok')"` | `prebaked ok` | 0 |

Smoke tests 6 and 7 from the plan (`lfx run /fixtures/noop_flow.py` and `lfx run /fixtures/basic_prompting.py`) require plan 02's fixture files, which are out of scope for this plan. They ran against the stub fixtures during local verification but are deferred to plan 05's driver integration test.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Issue] Missing README.md copies for workspace members**
- **Found during:** Task 3 build checkpoint, STEP 10 (`uv sync --frozen --no-install-project --group benchmarks`).
- **Issue:** hatchling's editable-build-metadata validation required each workspace member's `readme = "README.md"` file to exist at sync time. Without it, the build failed with `OSError: Readme file does not exist: README.md`.
- **Fix:** Added `README.md` to each workspace member's COPY line in the dependency layer.
- **Files modified:** `src/backend/tests/benchmarks/Dockerfile` (lines 36-41).
- **Commit:** `61c3a2fc4e`.

**2. [Rule 3 - Blocking Issue] Default `dev` dependency group pulled gcc-dependent packages**
- **Found during:** Task 3 build checkpoint, STEP 10 after the README.md fix.
- **Issue:** `uv sync --group benchmarks` without `--no-default-groups` installs both the default `dev` group AND the `benchmarks` group. The `dev` group transitively requires `crosshair-tool` which compiles a C extension requiring gcc, which is not in `python:3.13-slim`.
- **Fix:** Added `--no-default-groups` to both `uv sync` invocations. D-09 explicitly intends "only lfx + benchmark deps"; without this flag, D-09 is silently violated.
- **Files modified:** `src/backend/tests/benchmarks/Dockerfile` (lines 46 and 55).
- **Commit:** `61c3a2fc4e`.

**3. [Rule 3 - Blocking Issue] Runtime `uv run` triggered fresh sync and re-pulled dev group**
- **Found during:** Task 3 build checkpoint, STEP 20 (`uv run lfx --help`).
- **Issue:** Even after the previous two fixes, `uv run lfx --help` at runtime failed because `uv run` defaults to re-running sync with default groups, pulling `crosshair-tool` again. This would also hit every container start in production.
- **Fix:** Set `UV_NO_SYNC=1` and `UV_NO_DEFAULT_GROUPS=1` as image-wide ENV. Runtime `uv run` now reuses the already-built `/app/.venv` without re-resolving.
- **Files modified:** `src/backend/tests/benchmarks/Dockerfile` (lines 30-31).
- **Commit:** `61c3a2fc4e`.

## Authentication Gates

None. All work was local filesystem + podman; no credentialed external services.

## Assumption A2 (hyperfine on Debian 13 apt)

**HELD.** `apt-get install hyperfine` on `python:3.13-slim` installed `hyperfine 1.19.0-1+b3` from the Debian trixie main repository. No Rust multi-stage fallback was needed. `hyperfine --version` exits 0 on both images.

## Prebake Dep-Pin Ranges

No adjustments needed. Final pins in the Dockerfile prebaked variant:
- `openai>=1.0.0,<2.0.0` -> resolved to `openai 1.109.1`
- `langchain-openai>=0.3.0,<1.0.0` -> resolved to `langchain-openai 0.3.35`
- `pandas>=2.0.0` -> latest
- `scipy>=1.10.0` -> latest
- `numpy>=1.24.0` -> latest

Note: the prebake install REPLACED `openai==2.31.0` and `langchain-core==1.2.29` (from langflow-base transitive deps) with the older-pinned `openai==1.109.1` and `langchain-core==0.3.84`. This is intentional per the plan's pinning rationale (avoids `langchain_core.memory` removal issue) and matches plan expectations.

## Workspace Path Adjustments

None. All four workspace pyproject.toml files (`pyproject.toml`, `src/lfx/pyproject.toml`, `src/backend/base/pyproject.toml`, `src/sdk/pyproject.toml`) exist at their expected locations in the repo tree.

## Handoff to Plan 06 (CI Workflow)

- **Final image names:** `benchmarks-lean` and `benchmarks-prebaked`.
- **Exact build commands** (CI workflow must use):
  ```bash
  docker build --build-arg BENCH_VARIANT=lean     -t benchmarks-lean     -f src/backend/tests/benchmarks/Dockerfile .
  docker build --build-arg BENCH_VARIANT=prebaked -t benchmarks-prebaked -f src/backend/tests/benchmarks/Dockerfile .
  ```
- **.dockerignore strategy:** RECOMMEND symlink `src/backend/tests/benchmarks/.dockerignore` -> repo root `.dockerignore` at workflow start, or adopt `--build-context` pattern. The companion `.dockerignore` at the Dockerfile's location is documentation only (docker ignores it). Final decision recorded by plan 06.
- **Prerequisite ordering in CI:** The workflow MUST ensure plan 01's `benchmarks` dep-group + uv.lock regeneration are merged before invoking `docker build`. Plan 04's Dockerfile references `--group benchmarks` directly.

## Threat Flags

None. No new trust boundaries, network endpoints, auth paths, or schema changes at trust boundaries beyond what the plan's threat model already documents.

## Known Stubs

None in the shipped files. Temporary stubs used during build verification (fixtures/noop_flow.py, minimal benchmarks dep-group in pyproject.toml) were reverted before commit.

## Flagged for Phase-Level Review

**Observation (not fixed by this plan):** D-09 assumes the lean variant has ONLY "lfx + benchmark deps" and thus pays the dep-install cost for openai/langchain-openai at first `lfx run` (to enable MEAS-07's isolation). Empirical check on `benchmarks-lean` shows `openai`, `langchain-openai`, `langchain-classic`, and dozens of langchain-* providers are ALREADY installed as transitive dependencies of `langflow-base`. The two-image dep-install-cost isolation premise of D-11/D-12/MEAS-07 may be invalidated.

Two possible resolutions for the phase planner:
1. Redefine the "lean" baseline as `pip install lfx` alone (no langflow-base). This gives a genuine cold-start scenario but changes the measurement model from "what does watsonX.orchestrate's container pay" to "what does a bare lfx install pay".
2. Keep the current two-variant Dockerfile but reinterpret MEAS-07 as "does PRE-baking force a dep version pin that changes cold-start cost" rather than "does installing the deps cost N seconds at first run". The current prebaked variant DOES downgrade openai/langchain-core compared to what langflow-base's transitive deps install; that DOES produce a measurable delta, just not the one originally framed.

Flagged for the Phase 1 verifier / planner; this is NOT something plan 04 should fix unilaterally because it reshapes D-09, D-11, and D-12.

## Self-Check: PASSED

Verification:
- `test -f src/backend/tests/benchmarks/Dockerfile` -> FOUND (93 lines)
- `test -f src/backend/tests/benchmarks/.dockerignore` -> FOUND (47 lines)
- `git log --oneline | grep e5da9a1f1a` -> FOUND
- `git log --oneline | grep 6acb0c6c0a` -> FOUND
- `git log --oneline | grep 61c3a2fc4e` -> FOUND
- All task 1 grep-based acceptance criteria: PASS
- All task 2 grep-based acceptance criteria: PASS
- Task 3 build evidence: both `podman build` invocations exit 0; all 5 runtime smoke runs exit 0
