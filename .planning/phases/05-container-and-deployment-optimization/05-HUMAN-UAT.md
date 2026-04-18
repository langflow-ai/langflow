---
status: partial
phase: 05-container-and-deployment-optimization
source: [05-VERIFICATION.md]
started: 2026-04-18T16:50:03.693Z
updated: 2026-04-18T16:50:03.693Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. CNT-01 authoritative cold-start measurement
expected: lfx_reference_image mean cold-start < 8481ms (uncompiled lfx_bare baseline). The existing bytecode_compile_delta evidence (9.40s = 49.7%) from baseline-2026-04-17.md strongly predicts improvement will be confirmed.
result: [pending]

Trigger the cold-start-benchmark workflow with the `run-benchmark-snapshot` label on the Phase 5 PR. Observe the CI log for the `lfx_reference_image` matrix job. Capture the mean cold-start time for the lfx reference image and compare against the `lfx_bare` baseline (8481ms uncompiled, `baseline-2026-04-16.md`). Confirm `mean_ms < lfx_bare_uncompiled_baseline` to show measurable improvement. Commit the updated `thresholds.json` row.

### 2. CNT-02 repeat-build cache-hit timing
expected: Repeat build elapsed < 30s. The `--no-install-project` patch on Dockerfile line 36 ensures the deps layer (uv sync first run) is cache-stable. Only the second uv sync (`--no-editable`) re-runs after source COPY layer invalidation, which should complete in 5-15s on ubuntu-latest runners.
result: [pending]

In the same CI run, observe the `build-images` job -> "Verify deps layer cache (CNT-02 repeat-build assertion)" step. The step runs `docker build` twice (initial + repeat after no-op source change to `src/lfx/src/lfx/__init__.py`) and asserts elapsed < 30s. Confirm `Repeat build elapsed: Xs` is under 30s and there is no `::error ::CNT-02 FAILED` line.

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
