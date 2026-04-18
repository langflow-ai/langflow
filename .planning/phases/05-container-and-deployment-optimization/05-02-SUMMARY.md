---
phase: 05-container-and-deployment-optimization
plan: 02
subsystem: infra
tags: [ci, benchmarks, hyperfine, docker, sentinel, cnt-01]

# Dependency graph
requires:
  - "05-01 delivers src/lfx/docker/Dockerfile with Python 3.13 + --no-install-project (the image being measured)"
provides:
  - "lfx_reference_image scenario (hyperfine-wrapped, variant=lfx_reference, self_measuring=False)"
  - "IMG_LFX_REFERENCE = 'lfx-reference' constant in driver.py"
  - "Sentinel threshold row for lfx_reference_image (mean_ms=0 per D-15)"
  - "CI build-images job builds lfx-reference from src/lfx/docker/Dockerfile and saves it in tarball"
  - "CI matrix includes lfx_reference_image with continue-on-error=true sentinel treatment"
affects:
  - src/backend/tests/benchmarks/scenarios/lfx_reference_image.py
  - src/backend/tests/benchmarks/driver.py
  - src/backend/tests/benchmarks/thresholds.json
  - .github/workflows/cold-start-benchmark.yml

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Hyperfine-wrapped scenario for a short-lived CLI command (lfx run exits after flow completion; no TCP readiness probe needed)"
    - "Sentinel threshold pattern (mean_ms=0, runs=0) for new scenarios awaiting CI authoritative numbers per D-15"
    - "continue-on-error=true sentinel treatment applied consistently to new scenarios until first authoritative snapshot"

key-files:
  created:
    - src/backend/tests/benchmarks/scenarios/lfx_reference_image.py
  modified:
    - src/backend/tests/benchmarks/driver.py
    - src/backend/tests/benchmarks/thresholds.json
    - .github/workflows/cold-start-benchmark.yml

key-decisions:
  - "hyperfine-wrapped (self_measuring=False): lfx run exits after flow completion (verified via direct read of src/lfx/src/lfx/cli/run.py lines 144-182). No port bound, so TCP readiness probe / self-measuring supervisor is not applicable. Resolves RESEARCH.md Open Question 2."
  - "_lfx_reference_supervisor.py NOT created: PATTERNS.md flag confirmed -- skip when lfx run does not bind a port."
  - "captures_pyinstrument=False and captures_importtime=False: scenario measures the deployed image as a black box; harness tooling not present in lfx reference image."
  - "Sentinel threshold mean_ms=0, runs=0 per D-15 / Phase 3 D-09 precedent. Authoritative numbers land via run-benchmark-snapshot CI label."
  - "lfx-reference build step inserted between uncompiled variant build and docker save step in build-images job."

# Metrics
duration: 3min
completed: 2026-04-18
---

# Phase 05 Plan 02: CI Scenario lfx_reference_image Summary

**New lfx_reference_image scenario wires the CNT-01 measurement pipeline: hyperfine-wrapped cold-start of the patched lfx reference Dockerfile image (Python 3.13-alpine, UV_COMPILE_BYTECODE=1)**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-18T14:55:09Z
- **Completed:** 2026-04-18T14:57:46Z
- **Tasks:** 4
- **Files created:** 1
- **Files modified:** 3

## Accomplishments

### Task 1: Create scenarios/lfx_reference_image.py

Created `src/backend/tests/benchmarks/scenarios/lfx_reference_image.py` with:
- `SCENARIO.name = "lfx_reference_image"`, `variant = "lfx_reference"`, `self_measuring = False`
- `command = ["uv", "run", "lfx", "run", "/fixtures/noop_flow.json", "--format", "text"]`
- `captures_checkpoints = True` (lfx._bench writes JSON to LFX_BENCHMARK_CHECKPOINTS_FILE)
- `captures_pyinstrument = False`, `captures_importtime = False` (black-box image; harness tooling not available)
- `runs = 10` (matches lfx_bare shape)

Design decision confirmed: `lfx run` calls `run_flow`, echoes result, and exits. No port is bound. Hyperfine wrapping is correct; a supervisor/TCP readiness probe pattern (self_measuring=True) is NOT applicable. This resolves RESEARCH.md Open Question 2 and PATTERNS.md Open Question 1.

### Task 2: Wire into driver.py

Four edits applied atomically:
1. Added `from src.backend.tests.benchmarks.scenarios import (lfx_reference_image as _scen_lfx_reference_image,)`
2. Added `IMG_LFX_REFERENCE = "lfx-reference"` constant after IMG_UNCOMPILED
3. Appended `_scen_lfx_reference_image.SCENARIO` to `all_scenarios()` list
4. Added `if variant == "lfx_reference": return IMG_LFX_REFERENCE` branch in `_image_tag()`

Ruff auto-fixed import ordering (alphabetical) on pre-commit hook; re-staged and committed cleanly.

### Task 3: Add sentinel row to thresholds.json

Added `"lfx_reference_image": {"mean_ms": 0, "stddev_ms": 0, "runs": 0}` per D-15 sentinel pattern. All previously-existing authoritative rows unchanged.

### Task 4: Wire into cold-start-benchmark.yml

Five edits:
1. Added `- lfx_reference_image` to scenario matrix
2. Added "Build lfx-reference image" step (`docker build -t lfx-reference -f src/lfx/docker/Dockerfile .`) between uncompiled build and save step
3. Renamed "Save both images" to "Save all images" and added `lfx-reference` to `docker save` command
4. Extended both `continue-on-error` expressions to include `lfx_reference_image` (sentinel/non-blocking treatment)
5. Extended "Post regression comment" `if:` exclusion to include `lfx_reference_image`
6. Added `"lfx_reference_image"` to snapshot `tracked` list in aggregate job's inline Python

## Task Commits

Each task was committed atomically:

1. **Task 1: Create scenarios/lfx_reference_image.py** - `b7e96bf269`
2. **Task 2: Wire into driver.py** - `fec7507534`
3. **Task 3: Add sentinel row to thresholds.json** - `44bdf971df`
4. **Task 4: Wire into cold-start-benchmark.yml** - `0353a93c08`

## Verification Results

All 5 plan verification checks passed:

1. `from src.backend.tests.benchmarks.scenarios import lfx_reference_image as s; print(s.SCENARIO)` -- prints Scenario tuple with correct fields
2. `all_scenarios()` includes `'lfx_reference_image'` in registry
3. `_image_tag('lfx_reference')` returns `'lfx-reference'`
4. `thresholds.json['scenarios']['lfx_reference_image']` == `{'mean_ms': 0, 'stddev_ms': 0, 'runs': 0}`
5. YAML parses cleanly via `yaml.safe_load()`

## CNT-01 Coverage

- Plan 05-01 delivered the patched `src/lfx/docker/Dockerfile` (Python 3.13-alpine, UV_COMPILE_BYTECODE=1, --no-install-project deps-layer cache)
- This plan (05-02) delivers the measurement pipeline: CI builds the lfx-reference image, runs `lfx run <noop_flow>` via hyperfine, captures timing
- Authoritative mean_ms will be populated by the `run-benchmark-snapshot` CI label on the Phase 5 PR (per D-15)
- The sentinel row (mean_ms=0) in thresholds.json ensures verify mode does not gate on unmeasured numbers

## Deviations from Plan

None - plan executed exactly as written. The ruff import-ordering auto-fix on Task 2's commit was handled automatically (pre-commit hook modified the file; re-staged and recommitted).

## Known Stubs

- `thresholds.json["scenarios"]["lfx_reference_image"]` sentinel row `{"mean_ms": 0, "stddev_ms": 0, "runs": 0}` -- intentional per D-15. The verify mode compare_against_thresholds() treats `baseline_ms <= 0` as "sentinel trip if current > 0"; the lfx_reference_image matrix job carries `continue-on-error: true` so this sentinel does not block the workflow. Authoritative numbers land when the Phase 5 PR gets the `run-benchmark-snapshot` label.

## Threat Flags

None - no new network endpoints, auth paths, or trust boundaries beyond what the plan's threat model covers. The new `docker build` step in CI uses the committed Dockerfile from the repo (same supply chain as the existing benchmarks-lean build).

## Self-Check: PASSED

- FOUND: src/backend/tests/benchmarks/scenarios/lfx_reference_image.py
- FOUND: src/backend/tests/benchmarks/driver.py (modified)
- FOUND: src/backend/tests/benchmarks/thresholds.json (modified)
- FOUND: .github/workflows/cold-start-benchmark.yml (modified)
- FOUND: .planning/phases/05-container-and-deployment-optimization/05-02-SUMMARY.md
- FOUND commit b7e96bf269 (Task 1)
- FOUND commit fec7507534 (Task 2)
- FOUND commit 44bdf971df (Task 3)
- FOUND commit 0353a93c08 (Task 4)
