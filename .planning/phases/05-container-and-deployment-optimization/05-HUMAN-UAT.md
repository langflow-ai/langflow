---
status: resolved
phase: 05-container-and-deployment-optimization
source: [05-VERIFICATION.md]
started: 2026-04-18T16:50:03.693Z
updated: 2026-04-18T19:55:00.000Z
---

## Current Test

[complete]

## Tests

### 1. CNT-01 authoritative cold-start measurement
expected: lfx_reference_image mean cold-start < 8481ms (uncompiled lfx_bare baseline). The existing bytecode_compile_delta evidence (9.40s = 49.7%) from baseline-2026-04-17.md strongly predicts improvement will be confirmed.
result: pass

CI run 24612246320 (PR #12750, sha e405e75b52) with run-benchmark-snapshot label.
`lfx_reference_image`: **2,972.10 ms ± 27.36 ms (10 runs)** on ubuntu-latest.
`lfx_bare` baseline on the same run: **10,189.69 ms ± 39.83 ms**.
Delta: -7,217.59 ms (-70.8%). Well beyond the "measurable improvement" threshold.
thresholds.json row landed via the Aggregate job's Snapshot mode.

### 2. CNT-02 repeat-build cache-hit timing
expected: Repeat build elapsed < 30s. The `--no-install-project` patch on Dockerfile line 36 ensures the deps layer (uv sync first run) is cache-stable. Only the second uv sync (`--no-editable`) re-runs after source COPY layer invalidation, which should complete in 5-15s on ubuntu-latest runners.
result: pass

Same CI run, `build-images` job -> "Verify deps layer cache (CNT-02 repeat-build assertion)" step.
**Repeat build elapsed: 12s** (target: <30s). No `::error ::CNT-02 FAILED` line emitted.
The deps layer (first uv sync with --no-install-project) is cache-stable across source-only changes.

## Summary

total: 2
passed: 2
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

## Notes

Phase 5 surfaced three latent bugs along the way to this measurement, all fixed in-branch:

1. **src/lfx/docker/Dockerfile** — Alpine base could not install lfx's transitive deps
   (onnxruntime has no musllinux wheels). Switched to `python:3.13-slim-bookworm` +
   `ghcr.io/astral-sh/uv:python3.13-bookworm-slim`.

2. **src/backend/tests/benchmarks/scenarios/lfx_reference_image.py + driver.py** —
   scenario called `uv run lfx run` inside a production image that has no uv binary,
   and `/fixtures` wasn't mounted. `|| true` in the hyperfine wrapper masked the
   resulting shell failure and the first CI run logged a 182ms false-positive.
   Fixed by calling `lfx` directly and bind-mounting the benchmarks fixtures dir
   when `scenario.variant == "lfx_reference"`.

3. **src/lfx/pyproject.toml** — anyio>=4.13.0 imports `sniffio` internally but
   dropped it from its wheel metadata; lfx inherits the broken transitive. Added
   `sniffio>=1.3.0,<2.0.0` as an explicit lfx dep. Also fixes `uv pip install lfx`
   into clean environments (previously broken).
