---
phase: 05-container-and-deployment-optimization
plan: 01
subsystem: infra
tags: [docker, dockerfile, uv, alpine, python313, layer-cache, bytecode, pydantic-core]

# Dependency graph
requires: []
provides:
  - "src/lfx/docker/Dockerfile using Python 3.13 (builder + runtime ABI-matched)"
  - "Dockerfile deps layer cache-stable across source-only changes via --no-install-project"
  - "CNT-01 UV_COMPILE_BYTECODE=1 preserved; CNT-02 two-step sync layer ordering correct"
affects:
  - 05-container-and-deployment-optimization
  - any CI plan that builds the lfx reference image

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-step uv sync: first sync (--no-install-project) installs only deps, second sync (--no-editable) installs the workspace member after source COPY — standard uv layer-cache pattern"

key-files:
  created: []
  modified:
    - src/lfx/docker/Dockerfile

key-decisions:
  - "D-02 unblocked: pydantic-core 2.41.5 ships cp313 musllinux wheels (aarch64, armv7l, x86_64 confirmed in uv.lock lines 11129-11131); Python 3.13 bump safe to apply"
  - "--no-install-project on first uv sync ensures source-only changes do not bust the deps layer (CNT-02); second sync installs lfx itself after source COPY"
  - "Builder and runtime Python versions must match ABI: both set to python3.13-alpine (Pitfall 2 guard)"

patterns-established:
  - "uv two-step sync: deps-only layer (--no-install-project) before source COPY, then package-install layer (--no-editable) after source COPY"

requirements-completed: [CNT-01, CNT-02]

# Metrics
duration: 1min
completed: 2026-04-18
---

# Phase 05 Plan 01: Dockerfile Patches Summary

**Dockerfile updated to Python 3.13 (builder + runtime ABI match) with --no-install-project deps-layer cache fix for source-only change stability**

## Performance

- **Duration:** 1 min
- **Started:** 2026-04-18T14:50:12Z
- **Completed:** 2026-04-18T14:51:48Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Verified pydantic-core 2.41.5 cp313 musllinux wheels in uv.lock (lines 11129-11131: aarch64, armv7l, x86_64) — D-02 unblocked
- Bumped builder FROM `ghcr.io/astral-sh/uv:python3.12-alpine` to `python3.13-alpine` (line 10)
- Added `--no-install-project` to first `uv sync` call (line 36) so deps layer cache-hits on source-only changes (CNT-02)
- Bumped runtime FROM `python:3.12-alpine` to `python:3.13-alpine` (line 50) to match builder ABI (Pitfall 2 prevention)

## Task Commits

Each task was committed atomically:

1. **Task 1: Verify pydantic-core 2.41.5 cp313 musllinux wheels** - no commit (read-only verification, no file writes on happy path)
2. **Task 2: Apply the three Dockerfile patches** - `a9658b5986` (feat)

## Verification Results

```
=== Check 1: Python version references (only 3.13, zero 3.12) ===
50:FROM python:3.13-alpine AS runtime

=== Check 2: uv sync invocations ===
36:    uv sync --frozen --no-dev --no-install-project --package lfx
44:    uv sync --frozen --no-dev --no-editable --package lfx

=== Check 3: CNT-01, non-root user, CMD ===
18:ENV UV_COMPILE_BYTECODE=1
77:CMD ["lfx", "--help"]
```

## Three Exact Line Changes (before/after)

**Patch 1 (line 10) — builder base image:**
```
OLD: FROM ghcr.io/astral-sh/uv:python3.12-alpine AS builder
NEW: FROM ghcr.io/astral-sh/uv:python3.13-alpine AS builder
```

**Patch 2 (line 36) — first uv sync, deps-layer cache:**
```
OLD:     uv sync --frozen --no-dev --package lfx
NEW:     uv sync --frozen --no-dev --no-install-project --package lfx
```

**Patch 3 (line 50) — runtime base image:**
```
OLD: FROM python:3.12-alpine AS runtime
NEW: FROM python:3.13-alpine AS runtime
```

## Files Created/Modified

- `src/lfx/docker/Dockerfile` - Three patches: Python 3.13 bump (builder + runtime) and --no-install-project for CNT-02 cache stability

## Decisions Made

- CNT-01 is "already satisfied for fresh builds" by the existing `UV_COMPILE_BYTECODE=1`; the Phase 5 improvement claim for CNT-01 comes from the Python version bump and cache fix, not from adding the env var anew.
- Task 1 had no commit because it is a read-only verification step (grep only, no file writes on the happy path per plan).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. Both grep verifications (pydantic-core version + cp313 musllinux wheel presence) passed on the first run.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Dockerfile now uses Python 3.13 throughout (builder + runtime), with correct two-step uv sync layer ordering.
- CNT-01 and CNT-02 requirements fulfilled.
- Ready for Plan 05-02 (CI scenario verifying the bytecode compilation improvement in container builds).
- `docker/build_and_push.Dockerfile` was NOT touched (D-03 guardrail respected).

---
*Phase: 05-container-and-deployment-optimization*
*Completed: 2026-04-18*
