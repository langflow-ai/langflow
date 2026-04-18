---
phase: 05-container-and-deployment-optimization
plan: 04
subsystem: infra
tags: [ci, docker, cache, layer-verification, cnt-02]

# Dependency graph
requires:
  - "05-02 delivers 'Build lfx-reference image' step in build-images job (anchor point for this insertion)"
  - "05-01 delivers --no-install-project two-step uv sync in src/lfx/docker/Dockerfile (what CNT-02 verifies)"
provides:
  - "CNT-02 repeat-build cache-hit assertion in CI build-images job"
  - "::error :: emission naming CNT-02 + Plan 05-01 on deps-cache miss"
affects:
  - .github/workflows/cold-start-benchmark.yml

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Repeat-build timing gate: touch source file -> docker build -> assert elapsed < Ns (CI-only, ephemeral runner)"
    - "git checkout -- <file> restore pattern after no-op modification in CI step"

key-files:
  created: []
  modified:
    - .github/workflows/cold-start-benchmark.yml

key-decisions:
  - "30s threshold per D-14: RESEARCH.md section 'D-14' estimates ~10-15s cache-hit; 30s gives 2x headroom for runner variance. Raise to 45s only if proven too tight -- not to hide a genuine cache miss."
  - "Touch target src/lfx/src/lfx/__init__.py: inside src/lfx/src/ (COPYed at Dockerfile line 39) so it invalidates source COPY layer; outside src/lfx/ root so it does NOT bust the deps layer above."
  - "git checkout -- restore placed at end of run block: CI runner is ephemeral so any failure before restore is harmless (runner discarded); restore ensures docker save and subsequent steps see unmodified tree on success."
  - "Step positioned between 'Build lfx-reference image' and 'Save all images to tarball': initial build populates BuildKit cache; repeat build probes it; save step captures the final image state."

requirements-completed: [CNT-02]

# Metrics
duration: 5min
completed: 2026-04-18
---

# Phase 05 Plan 04: Repeat-Build Cache Verification Summary

**CI build-images job now asserts CNT-02: a source-only repeat docker build of lfx-reference completes in <30s, proving the deps layer cache-hits when only src/ changes**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-18T15:09:00Z
- **Completed:** 2026-04-18T15:14:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

### Task 1: Add CNT-02 repeat-build cache-hit verification step to the build-images job

Inserted a new step "Verify deps layer cache (CNT-02 repeat-build assertion)" in `.github/workflows/cold-start-benchmark.yml`'s `build-images` job between:
- AFTER: "Build lfx-reference image (CNT-01 reference Dockerfile)" (Plan 05-02)
- BEFORE: "Save all images to tarball"

Step logic:
1. Appends `# CNT-02 cache-verification no-op touch: <timestamp>` to `src/lfx/src/lfx/__init__.py`
2. Records wall-clock start via `date +%s`
3. Re-runs `docker build -t lfx-reference -f src/lfx/docker/Dockerfile .`
4. Computes elapsed seconds; asserts `elapsed < 30`
5. On failure: emits `::error ::CNT-02 FAILED: repeat build took ${elapsed}s (>=30s). The deps layer is NOT cache-hit. Verify --no-install-project is present on the first uv sync in src/lfx/docker/Dockerfile (Plan 05-01).`
6. Restores `src/lfx/src/lfx/__init__.py` via `git checkout -- src/lfx/src/lfx/__init__.py`

## Task Commits

1. **Task 1: Add CNT-02 repeat-build cache-hit verification step** - `cf7be6e3c2`

## Verification Results

All plan verification checks passed:

1. `grep -q 'Verify deps layer cache (CNT-02 repeat-build assertion)'` -- FOUND
2. `grep -q 'CNT-02 FAILED: repeat build took'` -- FOUND
3. `grep -q 'git checkout -- src/lfx/src/lfx/__init__.py'` -- FOUND
4. `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/cold-start-benchmark.yml'))"` -- YAML OK

## 30s Threshold Rationale

RESEARCH.md section "D-14" estimates "cache-hit: ~10-15s for source-only change" on ubuntu-latest. 30s provides 2x headroom for runner variance. First real CI run will log `Repeat build elapsed: Xs (CNT-02 target: <30s)` — that number becomes the empirical baseline. If it proves consistently > 20s, raise the threshold to 45s. Do NOT raise it to hide a genuine deps-cache miss (would mean --no-install-project from Plan 05-01 is absent or broken).

## First real-CI elapsed number

To be captured once `run-benchmark-snapshot` label runs the workflow on the Phase 5 PR. Look for `Repeat build elapsed: Xs` in the "Verify deps layer cache (CNT-02 repeat-build assertion)" step log of the build-images job.

## CNT-02 Coverage Chain

- Plan 05-01: `--no-install-project` on first `uv sync` in `src/lfx/docker/Dockerfile` -- creates the stable deps layer
- Plan 05-02: CI builds `lfx-reference` from that Dockerfile (first build, populates BuildKit cache)
- Plan 05-04 (this plan): CI re-builds `lfx-reference` after a source touch -- asserts cache-hits in <30s

## Deviations from Plan

None - plan executed exactly as written. Single edit to `.github/workflows/cold-start-benchmark.yml`.

## Known Stubs

None. The step is a live CI assertion, not a stub. The `elapsed` comparison is unconditional and will fail loudly if the deps cache misses.

## Threat Flags

None - no new network endpoints, auth paths, or trust boundaries. The `echo >>` and `git checkout --` operate on the CI runner's ephemeral local checkout; no cross-run persistence.

## Self-Check: PASSED

- FOUND: .github/workflows/cold-start-benchmark.yml (modified)
- FOUND commit cf7be6e3c2 (Task 1)
- FOUND: .planning/phases/05-container-and-deployment-optimization/05-04-SUMMARY.md
- Step text matches plan spec verbatim
- YAML parses cleanly
