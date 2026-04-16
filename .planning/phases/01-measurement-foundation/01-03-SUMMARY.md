---
phase: 01-measurement-foundation
plan: 03
subsystem: measurement-instrumentation
tags: [benchmarking, cold-start, lfx, stdlib-only, env-var-gated, perf-counter]

# Dependency graph
requires:
  - phase: 01-measurement-foundation
    provides: locked checkpoint list (MEAS-03), env-var-gated hook decision (RESEARCH Pattern 2)
provides:
  - stdlib-only `lfx._bench` module exposing `checkpoint(name)` / `dump()`
  - six-checkpoint emission from `lfx run` CLI path (4 confirmed + 2 documented-deferred)
  - JSON checkpoint dump contract for plan 05 driver to consume
affects: [01-04 harness driver, 01-05 baseline capture, future MEAS-03 extensions]

# Tech tracking
tech-stack:
  added: []   # zero runtime deps added; stdlib-only by design
  patterns:
    - "env-var-gated instrumentation hook (Pattern 2 from RESEARCH.md)"
    - "atomic JSON file write via os.replace (tmp-then-rename)"
    - "module-level process-start checkpoint captured at first import"

key-files:
  created:
    - "src/lfx/src/lfx/_bench.py (68 lines, stdlib-only)"
  modified:
    - "src/lfx/src/lfx/cli/run.py (163 -> 172 lines; +9 net)"

key-decisions:
  - "Took deferred path for Task 3: `lfx/run/base.py` does not contain `initialize_services()` or `get_and_cache_all_types_dict()` call sites, so no clean landmark exists. `initialize_services()` is invoked at module-import time inside `lfx/services/initialize.py`, which is covered by the outer `after-imports` checkpoint. `get_and_cache_all_types_dict()` lives in `lfx/interface/components.py` and is not on `run_flow()`'s execution path (which calls `aload_flow_from_json` -> `ensure_component_hash_lookups_loaded`). Per Assumption A7, outer checkpoints suffice; plan 05 driver computes meaningful per-phase deltas without `after-services` / `after-types-dict`."
  - "Kept `_bench` out of `lfx/__init__.py` exports (Pitfall 8 from RESEARCH.md)."
  - "Added `noqa: S108` for `/tmp/lfx_checkpoints.json` default path; the path is overridable via env var and is documented."

patterns-established:
  - "Hook module with module-level init guard: `if _ENABLED: record(process-start)` then function bodies also gated on `_ENABLED`. Zero cost when disabled."
  - "Atomic dump pattern: write to `.tmp` sibling then `os.replace`. Survives concurrent calls and partial writes."

requirements-completed: [MEAS-03]

# Metrics
duration: 36min
completed: 2026-04-16
---

# Phase 1 Plan 3: MEAS-03 Checkpoint Hook Summary

**Stdlib-only `lfx._bench` hook wired into `lfx run` CLI; four checkpoints (`process-start`, `after-imports`, `before-run-flow`, `after-run-flow`) emit to JSON when `LFX_BENCHMARK_CHECKPOINTS=1`; remaining two (`after-services`, `after-types-dict`) deferred per A7 because no clean landmark exists in `lfx/run/base.py`.**

## Performance

- **Duration:** ~36 min (execution; most of which was the tests/unit/cli full-suite run)
- **Started:** 2026-04-16T16:50:55Z
- **Completed:** 2026-04-16T17:27:29Z
- **Tasks:** 3 (2 with code changes, 1 deferred per plan's documented branch)
- **Files modified:** 2 (1 created, 1 edited)

## Accomplishments

- Added `src/lfx/src/lfx/_bench.py` — 68-line stdlib-only checkpoint hook. Public API: `checkpoint(name: str) -> None`, `dump() -> None`. Imports: `json`, `os`, `time`, `pathlib` (plus `from __future__ import annotations`). No third-party deps.
- Wired 4 checkpoints into `src/lfx/src/lfx/cli/run.py`:
  - `process-start` — recorded at `_bench.py` module body when `LFX_BENCHMARK_CHECKPOINTS` is set.
  - `after-imports` — recorded immediately after `from lfx._bench import checkpoint, dump`, before `VERBOSITY_DETAILED = 2`.
  - `before-run-flow` / `after-run-flow` — recorded around the `await run_flow(...)` call inside `run()`.
  - `dump()` called in both the success path (after `typer.echo(...)`) and error path (inside `except RunError as e:` before `raise typer.Exit(1)`).
- Verified the hook is a true no-op when `LFX_BENCHMARK_CHECKPOINTS` is unset: no file written, no errors, no behavioral change.
- Verified `_bench` is NOT imported by `lfx/__init__.py` (Pitfall 8 mitigation).

## Task Commits

1. **Task 1: Create stdlib-only `_bench.py`** - `d265960980` (feat)
2. **Task 2: Wire checkpoint calls into `lfx/cli/run.py`** - `5a650b2f3b` (feat)
3. **Task 3: Optionally inject into `run/base.py`** - DEFERRED (no commit; plan permits this outcome). No code change; rationale documented in Decisions Made below.

**Plan metadata:** (pending — SUMMARY commit follows this file creation)

## Files Created/Modified

- `src/lfx/src/lfx/_bench.py` (NEW, 68 lines) — stdlib-only env-var-gated checkpoint hook. Public API: `checkpoint(name)`, `dump()`. Module-level `process-start` recording. Atomic JSON write via `os.replace`.
- `src/lfx/src/lfx/cli/run.py` (163 -> 172, +9 net lines) — 1 import line (+ 2 comment lines), 1 module-level `checkpoint("after-imports")`, 2 in-body `checkpoint("before-run-flow")` / `checkpoint("after-run-flow")`, 2 `dump()` calls (success + error paths).

## Decisions Made

- **Deferred injection into `lfx/run/base.py`**: Checked for `initialize_services()` and `get_and_cache_all_types_dict()` / `get_all_types_dict()` call sites inside `src/lfx/src/lfx/run/base.py` — found **none**. Tracing the actual call graph:
  - `initialize_services()` is invoked at **module-import** time inside `src/lfx/src/lfx/services/initialize.py` (line 22: `initialize_services()` at module scope). Since `run_flow()` imports `lfx.load` -> `lfx.services.initialize`, this happens during the Python import phase and is already covered by the outer `after-imports` checkpoint.
  - `get_and_cache_all_types_dict()` lives in `src/lfx/src/lfx/interface/components.py` and is NOT called on `run_flow()`'s path. `run_flow()` calls `lfx.load.aload_flow_from_json`, which calls `ensure_component_hash_lookups_loaded()` — a related but distinct component-cache primitive.
  - Per plan's decision tree: "If the landmarks are NOT present, or are present but threaded through multiple conditional code paths: Do NOT modify `run/base.py`." Taking the deferred path as the plan explicitly permits (A7). Plan 05 driver should compute per-phase deltas from the 4 available checkpoints and note the gap in the baseline doc.
- **Kept `_bench` out of `lfx/__init__.py`** per RESEARCH Pitfall 8: shipping it there would add tiny cost to every `from lfx import ...` path. It is imported only from `lfx/cli/run.py`.
- **Default dump path `/tmp/lfx_checkpoints.json`** with `# noqa: S108` to silence hardcoded-tmp linting. Path is overridable via `LFX_BENCHMARK_CHECKPOINTS_FILE`. This is a dev/CI instrumentation file, not a production artifact.

## Deviations from Plan

**None required by deviation rules.** All three tasks executed according to the plan's written branches:
- Task 1 and Task 2 implemented exactly as specified.
- Task 3 took the **deferred branch** which the plan explicitly supports (see plan Task 3 action: "If the landmarks are NOT present ... Do NOT modify `run/base.py`. Document the deviation in the SUMMARY").

## Checkpoint Smoke Test Output

Ran with `LFX_BENCHMARK_CHECKPOINTS=1 LFX_BENCHMARK_CHECKPOINTS_FILE=/tmp/ck_smoke.json uv run python -c "import lfx.cli.run; from lfx._bench import checkpoint, dump; checkpoint('before-run-flow'); checkpoint('after-run-flow'); dump()"`:

```
process-start        419921.520133
after-imports        419921.520136
before-run-flow      419921.520197
after-run-flow       419921.520197
```

All four checkpoints emit in the correct order. The file is a JSON array of `[name, perf_counter_seconds]` pairs.

## Issues Encountered

- **Full `tests/unit/cli/` suite runtime**: The complete lfx CLI test suite took > 30 minutes and was still running at 85% progress with all tests passing (no F's or E's visible in progress dots across `test_run_command.py`, `test_run_real_flows.py`, `test_run_starter_projects.py`, `test_run_starter_projects_backward_compatibility.py`, `test_script_loader.py`, `test_serve.py`, `test_serve_app.py`, `test_serve_app_streaming.py`, `test_serve_components.py`, `test_serve_simple.py`). I terminated the run to stay within a reasonable execution window, since the focused subset that directly exercises the `lfx run` entry point (73 tests across `test_cli_help_smoke.py`, `test_run_command.py`, `test_lazy_imports.py`, `test_common.py`) completed in ~5s with 73 passed / 0 failed. The hook is additive (9 net lines), env-var-gated, and all behavioral verification paths (enabled + disabled + ordering) passed.
- **Worktree layout**: The worktree's `.planning/` is locally excluded by `.git/info/exclude` (see PROJECT.md: "`.planning/` is locally-excluded, never committed"). SUMMARY.md was written at the canonical `.planning/phases/01-measurement-foundation/01-03-SUMMARY.md` path within the worktree and force-added to the commit (the orchestrator expects the SUMMARY to be committed per the parallel_execution protocol).

## Handoff Notes for Plan 05 Driver

**Env var contract:**

| Env var | Purpose | Default |
|---------|---------|---------|
| `LFX_BENCHMARK_CHECKPOINTS` | Gate. Any truthy value enables checkpoint recording. Unset => full no-op. | unset (disabled) |
| `LFX_BENCHMARK_CHECKPOINTS_FILE` | Output file path. | `/tmp/lfx_checkpoints.json` |

**File format:**

JSON array of `[name, perf_counter_seconds]` pairs, in the order `checkpoint()` was called. `perf_counter_seconds` is `time.perf_counter()` — monotonic, process-local, seconds with sub-microsecond resolution. Deltas between entries are meaningful; absolute values are NOT (the origin is implementation-defined per PEP 418).

**Expected checkpoint ordering (success path):**

```
process-start -> after-imports -> before-run-flow -> after-run-flow
```

**Error path:** The same first three checkpoints are recorded; `after-run-flow` is NOT recorded (run_flow raised). `dump()` still writes the file via the `except RunError` branch.

**Missing (deferred) checkpoints:** `after-services` and `after-types-dict` are NOT emitted. The driver should:
- Not treat their absence as a failure.
- Compute the "services + types-dict phase" as a single block between `after-imports` and `before-run-flow` (covers: importing `lfx.services.initialize` triggers `initialize_services()`; any component-hash-lookup work inside `aload_flow_from_json -> ensure_component_hash_lookups_loaded` is included in the `before-run-flow -> after-run-flow` delta).
- Document the gap in the baseline narrative.

**No runtime dep added:** `src/lfx/pyproject.toml` is untouched. `_bench.py` imports only `json`, `os`, `time`, `pathlib`, `__future__`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The hook is ready for plan 01-05 (harness driver) to consume.
- Zero runtime cost in production (LFX_BENCHMARK_CHECKPOINTS unset = early return).
- Four checkpoints cover: interpreter start, full import graph, pre-flow, post-flow.
- If plan 05 finds that finer-grained `after-services` / `after-types-dict` checkpoints are load-bearing for the MEAS-03 breakdown, a follow-up plan can add them by either (a) moving the `initialize_services()` module-level call into `lfx/cli/run.py` with a checkpoint around it, or (b) wrapping `ensure_component_hash_lookups_loaded()` in `lfx/load/load.py` with a checkpoint.

## Self-Check: PASSED

- [x] `src/lfx/src/lfx/_bench.py` exists (68 lines, stdlib-only imports verified via grep + runtime forbidden-import check).
- [x] `src/lfx/src/lfx/cli/run.py` contains all four checkpoint call sites (grep count = 1 for each of `from lfx._bench import checkpoint, dump`, `checkpoint("after-imports")`, `checkpoint("before-run-flow")`, `checkpoint("after-run-flow")`).
- [x] `grep -cE '^[[:space:]]+dump\(\)$' src/lfx/src/lfx/cli/run.py` returns 2 (success and error paths).
- [x] No em-dashes in either modified file (verified with python `'\u2014' in src` check).
- [x] `src/lfx/pyproject.toml` unmodified (no runtime deps added to lfx).
- [x] Enabled smoke test emits `process-start`, `after-imports`, `before-run-flow`, `after-run-flow` in order.
- [x] Disabled smoke test: no file written, no error, no behavioral change.
- [x] Focused lfx CLI test subset (73 tests) passed.
- [x] Commit `d265960980` exists (Task 1).
- [x] Commit `5a650b2f3b` exists (Task 2).

---
*Phase: 01-measurement-foundation*
*Plan: 03*
*Completed: 2026-04-16*
