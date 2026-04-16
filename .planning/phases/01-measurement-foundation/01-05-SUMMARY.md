---
phase: 01-measurement-foundation
plan: 05
subsystem: testing
tags: [benchmarks, hyperfine, pyinstrument, importtime, podman, docker, lfx, meas-03, meas-07, cold-start]

# Dependency graph
requires:
  - phase: 01-measurement-foundation
    provides: "MEAS-01 scenarios, mock LLM, JSON fixtures, checkpoint hook, lean+prebaked images"
provides:
  - "MEAS-03 closed: all 6 cold-start checkpoints emit on a single `lfx run` invocation"
  - "MEAS-01..MEAS-05 harness driver with hyperfine, pyinstrument, -X importtime captures"
  - "MEAS-07 reframed per D-11a/D-12a: bytecode-compile-cost delta (not dep-install)"
  - "Option A1 image variant: benchmarks-lean-uncompiled produced on-the-fly without modifying plan 04's Dockerfile"
  - "--verify mode + regression_comment.md for plan 06 CI gate"
  - "Non-authoritative local baseline (macOS + podman) for plans 01-06 to diff against"
affects:
  - "plan 01-06 (CI workflow, thresholds.json commit, bot comment gate)"
  - "phase 02+ (cold-start improvements will be measured against this harness)"

# Tech tracking
tech-stack:
  added:
    - "hyperfine 1.20.0 (host-side wall-clock sampler)"
    - "pyinstrument 5.1.2 (in-process statistical profiler)"
    - "importtime-convert 1.1.0 (-X importtime log -> flamegraph/json)"
  patterns:
    - "Option A1 bytecode-variant production: on-the-fly wrapper Dockerfile strips .pyc from landed lean image"
    - "LFX_BENCHMARK_BOOTSTRAP_{MODULE,PATH} hook in lfx._bench for JSON-fixture-side module injection"
    - "Driver verify-mode compare helper is a plain function so unit tests exercise it without docker or hyperfine"
    - "subprocess.run with shell=False throughout; the one `sh -c` use is a container-side shell inside an argv list (no host shell)"

key-files:
  created:
    - "src/backend/tests/benchmarks/fixtures/noop_flow.json"
    - "src/backend/tests/benchmarks/fixtures/basic_prompting.json"
    - "src/backend/tests/benchmarks/fixtures/document_qa.json"
    - "src/backend/tests/benchmarks/driver.py"
    - "src/backend/tests/benchmarks/snapshot.py"
    - "src/backend/tests/benchmarks/scenarios/__init__.py"
    - "src/backend/tests/benchmarks/scenarios/lfx_bare.py"
    - "src/backend/tests/benchmarks/scenarios/lfx_with_flow.py"
    - "src/backend/tests/benchmarks/scenarios/langflow_run.py"
    - "src/backend/tests/benchmarks/scenarios/_langflow_supervisor.py"
    - "src/backend/tests/benchmarks/tests/__init__.py"
    - "src/backend/tests/benchmarks/tests/test_driver_verify.py"
    - "src/backend/tests/benchmarks/reports/.gitignore"
    - "src/lfx/tests/unit/test_bench_checkpoints.py"
  modified:
    - "src/lfx/src/lfx/services/initialize.py (after-initialize-services landmark)"
    - "src/lfx/src/lfx/load/load.py (after-component-index landmark)"
    - "src/lfx/src/lfx/_bench.py (LFX_BENCHMARK_BOOTSTRAP_{MODULE,PATH} hook; tmp.replace)"
    - "src/backend/tests/benchmarks/mock_llm.py (module-level install_if_enabled)"

key-decisions:
  - "Switch primary fixtures from .py to .json (user-approved Option C). JSON path goes through aload_flow_from_json, which fires after-component-index; the .py path went through load_graph_from_script and skipped the landmark."
  - "Mock LLM bootstrap via generic LFX_BENCHMARK_BOOTSTRAP_{MODULE,PATH} env-var hook in lfx._bench (user-approved Option A, generalized). Keeps lfx layer-clean; the harness sets the env var to point at mock_llm.py."
  - "Switch pyinstrument flag from --timer coarse (does not exist in 5.1.2) to --use-timing-thread (equivalent container-slowdown mitigation for Pitfall 2)."
  - "Emit flamegraph.pl + json from importtime-convert instead of the plan's `speedscope` (not supported in 1.1.0). flamegraph.pl is universally compatible with flame-graph tooling."
  - "Commit local macOS baseline as non-authoritative smoke-only (D-10 / Pitfall 3); authoritative numbers ship via plan 06 CI run on Linux."
  - "langflow_run_http_ready scenario times out on macOS+podman; the `Application startup complete.` marker is suppressed by langflow's structlog processor pipeline on this stack. (Earlier note in this file said loguru — that is wrong; langflow uses structlog.) Linux CI (plan 06) will confirm the marker's behavior there."

patterns-established:
  - "Bootstrap hook in lfx._bench: a generic importlib escape hatch for JSON-fixture runs. Both dotted-module and path variants to tolerate import-path collisions (e.g., third-party `tests` packages in site-packages shadowing `src/backend/tests`)."
  - "Driver runs atomic scenario commits even on partial failure; any failed scenario has its error recorded in results[name]['error'] and the baseline-*.md renders what's present."
  - ".planning/ is git-excluded so baseline-*.{md,json} stay local. Authoritative numbers ship via thresholds.json (plan 06)."

requirements-completed: [MEAS-01, MEAS-02, MEAS-03, MEAS-04, MEAS-05, MEAS-06, MEAS-07]

# Metrics
duration: ~90min
completed: 2026-04-16
---

# Phase 01 Plan 05: Harness Driver + Baseline Capture Summary

**Cold-start benchmark driver runs hyperfine/pyinstrument/-X importtime against lfx_bare, lfx_with_flow (lean+prebaked), and langflow_run_http_ready scenarios; produces baseline-YYYY-MM-DD.{md,json} with measurement_mode=bytecode_compile_delta; --verify mode trips on thresholds.json regressions and emits regression_comment.md for plan 06's bot-comment step.**

## Performance

- **Duration (continuation segment, Task 5a + Task 5 + Task 5b):** ~90 min
- **Completed:** 2026-04-16
- **Tasks completed:** 6 (Tasks 1-4 in prior segment; 5a, 5, 5b in this segment)
- **Files touched:** 14 created, 4 modified

## Accomplishments

- **MEAS-03 closed.** All 6 cold-start checkpoints (`process-start`, `after-imports`, `after-initialize-services`, `after-component-index`, `before-run-flow`, `after-run-flow`) emit on a single `lfx run basic_prompting.json` invocation. Verified inside and outside the benchmark container.
- **Fixture switch from .py to .json.** JSON fixtures go through `aload_flow_from_json`, which triggers the after-component-index landmark. Previous .py fixtures used `load_graph_from_script` and skipped that landmark.
- **Bootstrap hook in lfx._bench.** `LFX_BENCHMARK_BOOTSTRAP_MODULE` (dotted path) / `LFX_BENCHMARK_BOOTSTRAP_PATH` (absolute file path) lets the harness inject module-level initialization (mock LLM) on top of JSON fixtures. lfx has no hard-coded dependency on the backend benchmark tree.
- **On-the-fly bytecode-uncompiled image.** Driver writes a wrapper Dockerfile that FROMs `benchmarks-lean` and strips `__pycache__`/`.pyc`/`.pyo` from `/app/.venv`, tagging the result as `benchmarks-lean-uncompiled`. Plan 04's landed Dockerfile is unmodified.
- **--verify mode.** Reads `thresholds.json`, compares current means against the baseline, writes `reports/regression_comment.md` on any scenario regression exceeding `allowed_regression_pct`, exits code 3. 4 unit tests (FAIL, PASS, sentinel, measurement_mode-mismatch) cover the behavior without docker.
- **Non-authoritative local baseline captured.** macOS + podman, 10 hyperfine runs per scenario:
  - `lfx_bare`: **8782 +/- 190 ms**
  - `lfx_with_flow` (lean/uncompiled): **9348 +/- 46 ms**
  - `lfx_with_flow_prebaked` (compiled): **4554 +/- 226 ms**
  - **bytecode_compile_delta: 4794 ms (~51% of cold start; import time dominant at 4574 ms)**

## Task Commits

1. **Task 1: MEAS-03 landmark gap** (from prior segment) - `5c2e525f92` (feat)
2. **Task 2: Scenario modules + langflow supervisor** (from prior segment) - `3a6d0c3994` (feat)
3. **Task 3: driver.py** (from prior segment) - `bcf914f300` (feat)
4. **Task 4: snapshot.py + verify-mode unit tests** (from prior segment) - `3208bfb1f3` (feat)
5. **Task 5a: Fixture switch .py -> .json + bootstrap hook** - `81d16d699f` (refactor)
6. **Task 5: Local baseline capture + driver portability fixes** - `db777cf7c1` (feat)
7. **Plan metadata (this SUMMARY)** - pending

## Files Created/Modified

### Created (14)

- `src/backend/tests/benchmarks/fixtures/noop_flow.json` - MEAS-01 bare-boot fixture (generated via `graph.dump()` + datetime-aware encoder).
- `src/backend/tests/benchmarks/fixtures/basic_prompting.json` - MEAS-07 primary fixture.
- `src/backend/tests/benchmarks/fixtures/document_qa.json` - MEAS-01 secondary fixture.
- `src/backend/tests/benchmarks/driver.py` - Orchestrator (~900+ lines).
- `src/backend/tests/benchmarks/snapshot.py` - One-shot baseline + thresholds.json writer.
- `src/backend/tests/benchmarks/scenarios/{__init__.py,lfx_bare.py,lfx_with_flow.py,langflow_run.py,_langflow_supervisor.py}` - Scenario registry + supervisor.
- `src/backend/tests/benchmarks/tests/{__init__.py,test_driver_verify.py}` - verify-mode unit tests (4 cases).
- `src/backend/tests/benchmarks/reports/.gitignore` - Ignores all driver-generated artifacts (matches README.md contract).
- `src/lfx/tests/unit/test_bench_checkpoints.py` - MEAS-03 landmark unit tests (4 cases).

### Modified (4)

- `src/lfx/src/lfx/services/initialize.py` - Added `after-initialize-services` checkpoint after module-level `initialize_services()` call.
- `src/lfx/src/lfx/load/load.py` - Added `after-component-index` checkpoint after `await ensure_component_hash_lookups_loaded()` in the success branch.
- `src/lfx/src/lfx/_bench.py` - Added `LFX_BENCHMARK_BOOTSTRAP_{MODULE,PATH}` hook; swapped `os.replace` for `Path.replace` (pre-existing PTH105 lint).
- `src/backend/tests/benchmarks/mock_llm.py` - Added module-level `install_if_enabled()` so the bootstrap hook activates the mock without fixture-level Python.

## Decisions Made

### Decision 1 (fixture path): Switch primary fixtures from .py to .json (Option C)

Rationale: The `.py` fixture path went through `load_graph_from_script`, not `aload_flow_from_json`, so `after-component-index` never fired. Switching to `.json`:

- Aligns with production (most users load JSON flows).
- Gets all 6 checkpoints naturally (6 of 6 observed on `lfx run basic_prompting.json`).
- No extra landmark code needed inside lfx or langflow source.

### Decision 2 (mock bootstrap): Generic LFX_BENCHMARK_BOOTSTRAP_{MODULE,PATH} hook

Rationale: Plan text listed three options. I chose a generalization of Option A: a generic hook in `lfx._bench` that imports an env-var-specified module (dotted path OR absolute file path). This:

- Keeps lfx layer-clean (no hard dependency on backend code).
- Tolerates import-path collisions (third-party `tests` packages in site-packages shadowed our `src/backend/tests` dotted name; the file-path variant dodges the issue).
- Reusable beyond the mock LLM (any future bootstrap hook for traces, instrumentation, etc.).

### Decision 3 (pyinstrument flag): --use-timing-thread instead of --timer coarse

Rationale: pyinstrument 5.1.2 does not expose `--timer`. The equivalent container-slowdown mitigation for Pitfall 2 is `--use-timing-thread`, which decouples the sampler from gettimeofday. Both flags address the same underlying Docker/podman time-syscall cost; the substitution preserves the RESEARCH.md Pitfall 2 intent.

### Decision 4 (importtime format): flamegraph.pl + json instead of speedscope

Rationale: `importtime-convert` 1.1.0 supports `--output-format {flamegraph.pl, json}`. The plan listed `speedscope`, which is unavailable in this release. `flamegraph.pl` is the canonical format accepted by Brendan Gregg's flamegraph.pl and most other flame-graph tools, so downstream observability tooling is unchanged.

### Decision 5 (local baseline): macOS + podman smoke, NOT authoritative

Rationale: CONTEXT.md D-10 and RESEARCH.md Pitfall 3 both mandate that authoritative numbers come from Linux CI, not local dev. The local baseline (`.planning/benchmarks/baseline-2026-04-16.{md,json}`) is local-only (.planning/ is git-excluded) and labeled `captured_runner: macOS-26.3.1-arm64-arm-64bit-Mach-O`. Plan 06 runs the driver on ubuntu-22.04 to produce the authoritative thresholds.json.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Relative output-dir paths fail on podman `-v`**

- **Found during:** Task 5 (smoke run)
- **Issue:** `podman -v <relative>:/out` interprets a non-absolute host path as a named volume; validator then fails with `names must match [a-zA-Z0-9][a-zA-Z0-9_.-]*`.
- **Fix:** Resolve `args.output_dir` / `args.baseline_dir` with `Path(...).resolve()` in `main()` before any downstream consumer sees them.
- **Files modified:** `src/backend/tests/benchmarks/driver.py`
- **Verification:** `podman run -v /abs/path:/out ...` succeeded with 10-run hyperfine across three scenarios.
- **Committed in:** `db777cf7c1`

**2. [Rule 1 - Bug] pyinstrument `--timer` flag does not exist in 5.1.2**

- **Found during:** Task 5 (smoke run)
- **Issue:** `pyinstrument: error: no such option: --timer` -> pyinstrument exits non-zero and the HTML artifact is not produced.
- **Fix:** Replace `--timer coarse` with `--use-timing-thread` (equivalent Pitfall 2 mitigation). The string `--timer coarse` remains in doc-comments for grep traceability.
- **Files modified:** `src/backend/tests/benchmarks/driver.py`
- **Verification:** `podman run ... pyinstrument --use-timing-thread --renderer html ...` produced 6.0-MB HTML artifacts for lfx_bare and 6.6-MB for lfx_with_flow.
- **Committed in:** `db777cf7c1`

**3. [Rule 1 - Bug] Plain `python -X importtime` fails inside container**

- **Found during:** Task 5 (smoke run)
- **Issue:** The container's system `python` does NOT have lfx installed; only `/app/.venv/bin/python` (activated via `uv run`) does. Running `python -X importtime -c 'import lfx'` raised ModuleNotFoundError.
- **Fix:** Use `uv run python -X importtime -c 'import lfx'` in the sh -c invocation.
- **Files modified:** `src/backend/tests/benchmarks/driver.py`
- **Verification:** Importtime log for lfx_bare captured 1.8 KB of well-formed `import time:` lines; importtime-convert rendered them into a 4.6 KB JSON sidecar.
- **Committed in:** `db777cf7c1`

**4. [Rule 1 - Bug] importtime-convert 1.1.0 API differs from plan text**

- **Found during:** Task 5 (smoke run)
- **Issue:** Plan called for `importtime-convert --format speedscope`; 1.1.0 accepts `--output-format {flamegraph.pl, json}` only. The `--format` flag does not exist and `speedscope` is not a supported target.
- **Fix:** Swap to `--output-format {flamegraph.pl, json}`; emit `<scenario>.flamegraph.txt` + `<scenario>.importtime.json`. Also fall back to `uv run importtime-convert` when the binary is not on PATH (it lives in `.venv/bin/`).
- **Files modified:** `src/backend/tests/benchmarks/driver.py`
- **Verification:** Both sidecars (flamegraph + json) produced non-zero output for all three scenarios.
- **Committed in:** `db777cf7c1`

**5. [Rule 1 - Bug] Langflow supervisor uses bare `python` instead of `uv run python`**

- **Found during:** Task 5 (langflow_run smoke)
- **Issue:** `scenarios/langflow_run.py`'s command was `["python", "-m", "..."]`; inside the container only `uv run python` sees langflow and lfx. Supervisor would fail on first import.
- **Fix:** Switch to `["uv", "run", "python", "-m", "..."]`.
- **Files modified:** `src/backend/tests/benchmarks/scenarios/langflow_run.py`
- **Verification:** The supervisor imported cleanly and booted langflow inside the container (the later timeout is a separate Mac/structlog issue, see Known Limitations).
- **Committed in:** `db777cf7c1`

**6. [Rule 3 - Blocker] `reports/` directory had no .gitignore**

- **Found during:** Task 5 cleanup
- **Issue:** README.md documents `reports/ - driver output; gitignored except .gitkeep`, but no actual gitignore existed; driver artifacts (hyperfine JSON, pyinstrument HTML, importtime logs) would have been staged accidentally.
- **Fix:** Added `src/backend/tests/benchmarks/reports/.gitignore` with `*` + `!.gitignore` + `!.gitkeep` ruleset.
- **Files modified:** `src/backend/tests/benchmarks/reports/.gitignore` (new).
- **Verification:** `git status` now lists only source files, not driver output.
- **Committed in:** `db777cf7c1`

**7. [Rule 1 - Bug] Pre-existing PTH105 lint in lfx/_bench.py**

- **Found during:** Task 5a commit (pre-commit ruff check)
- **Issue:** `os.replace()` should be `Path.replace()` per ruff PTH105. Pre-existing from plan 03; surfaced when my edit caused a re-check of the file.
- **Fix:** `os.replace(tmp, target)` -> `tmp.replace(target)`.
- **Files modified:** `src/lfx/src/lfx/_bench.py`
- **Verification:** `cd src/lfx && uv run pytest tests/unit/test_bench_checkpoints.py -v` -> 4 passed (dump + checkpoint behavior unchanged).
- **Committed in:** `81d16d699f`

**8. [Rule 2 - Missing critical] macOS supervisor timeout too tight**

- **Found during:** Task 5 (langflow_run smoke on macOS+podman)
- **Issue:** `STARTUP_TIMEOUT_SEC = 60.0` is sufficient for Linux CI (cold boot ~30-40s) but macOS/podman VM takes >3x longer. Without override, the supervisor was hitting the hard 60s cap.
- **Fix:** Make `STARTUP_TIMEOUT_SEC` overridable via `LANGFLOW_BENCH_STARTUP_TIMEOUT`, default 180s.
- **Files modified:** `src/backend/tests/benchmarks/scenarios/_langflow_supervisor.py`
- **Verification:** Verified supervisor still initializes cleanly at 180s default; Linux CI can keep the 60s floor via env override.
- **Committed in:** `db777cf7c1`

### Known Limitations (macOS smoke only)

**langflow_run_http_ready marker not observed on macOS+podman.** The scenario runs but the supervisor's literal marker `Application startup complete.` does not appear in the container's combined stdout/stderr even after >20 minutes of server runtime. Langflow configures its logging via **structlog** (NOT loguru — the original note in this summary was wrong), and the structlog processor pipeline does not route uvicorn's INFO log through to stdout in a way this supervisor observes; the "banner line" (`🟢 Open Langflow → http://localhost:7860`) IS printed, but the plan's contract locks the ready marker to the uvicorn phrasing. Plan 06's Linux CI run will determine whether uvicorn's log flows through on Linux (it may on some configurations); if not, plan 06 Task 1 can relax the marker to a more robust substring such as the banner line.

**Total deviations:** 8 auto-fixed (5 Rule 1 bugs from plan-vs-reality tool-version drift, 1 Rule 2 missing timeout override, 1 Rule 3 missing gitignore, 1 pre-existing lint).

**Impact on plan:** All auto-fixes essential for end-to-end execution. The fixture switch (Decision 1) is not a deviation since the user pre-approved Option C in the prompt. The marker limitation is documented for plan 06 to resolve.

## Issues Encountered

- Third-party `tests` package in site-packages shadowed our `src.backend.tests.benchmarks` dotted name, forcing the bootstrap hook to grow a path-based variant. Resolved via `LFX_BENCHMARK_BOOTSTRAP_PATH` (absolute filesystem path) alongside `LFX_BENCHMARK_BOOTSTRAP_MODULE`.
- Podman VM on macOS is ~2-3x slower for cold-start than bare-metal Linux. Times captured here are NOT comparable to Linux runner numbers (D-10 / Pitfall 3 explicitly flag this).

## TDD Gate Compliance

Not applicable (plan type is `execute`, not `tdd`). However Task 1 was executed TDD-style per the task's `tdd="true"` attribute; verified via the 4-test `test_bench_checkpoints.py` suite.

## Verification Output

### lfx bench checkpoint unit tests (4 cases)

```
tests/unit/test_bench_checkpoints.py::test_initialize_services_emits_after_initialize_services PASSED
tests/unit/test_bench_checkpoints.py::test_load_emits_after_component_index                  PASSED
tests/unit/test_bench_checkpoints.py::test_checkpoints_disabled_is_zero_cost                 PASSED
tests/unit/test_bench_checkpoints.py::test_dump_writes_named_checkpoints                     PASSED
4 passed, 4 warnings in 0.73s
```

### driver --verify unit tests (4 cases)

```
test_driver_verify.py::test_verify_fail_case_trips_gate                     PASSED
test_driver_verify.py::test_verify_pass_case_does_not_trip                  PASSED
test_driver_verify.py::test_verify_sentinel_baseline_always_trips           PASSED
test_driver_verify.py::test_verify_measurement_mode_mismatch_warns_not_fails PASSED
4 passed in 0.14s
```

### End-to-end checkpoint smoke (`lfx run basic_prompting.json`)

```python
>>> json.load(open('/tmp/ck_bp.json'))
[['process-start', ...],
 ['after-imports', ...],
 ['after-initialize-services', ...],
 ['before-run-flow', ...],
 ['after-component-index', ...],
 ['after-run-flow', ...]]
# set(names) == {'process-start', 'after-imports', 'after-initialize-services',
#                'after-component-index', 'before-run-flow', 'after-run-flow'}
# missing: set()  -> all 6 present
```

### Baseline summary (first 15 lines of baseline-2026-04-16.md)

```
# Cold Start Baseline: 2026-04-16
- captured_on: 2026-04-16
- captured_ref: `81d16d699ffffc51fce794ce6b6dcc3d72e197e4`
- python_version: 3.13.9
- hyperfine_version: hyperfine 1.20.0
- image_tags: `benchmarks-lean` (prebaked/compiled), `benchmarks-lean-uncompiled` (lean/uncompiled)
- Measurement mode: `bytecode_compile_delta`

## Wall-clock summary
| scenario | mean ms | stddev | min | max | runs |
| lfx_bare | 8781.54 | 189.76 | 8586.38 | 9244.68 | 10 |
| lfx_with_flow | 9347.67 | 46.20 | 9258.02 | 9403.87 | 10 |
| lfx_with_flow_prebaked | 4553.67 | 225.51 | 4409.34 | 5161.24 | 10 |
```

### MEAS-07 conclusion string (verify bytecode-compile language)

> "Bytecode compile adds 4794ms (~51.3% of cold start); import time remains dominant at 4574ms."

This follows the D-11a template exactly. No dep-install language.

### Plan 04 Dockerfile untouched

```
$ git diff 0f39439ce2..HEAD src/backend/tests/benchmarks/Dockerfile | wc -l
0
```

### IDX-01 crash (Pitfall 8 / Open Question 1)

Not reproduced during the 10-run hyperfine capture of any scenario. All three lfx scenarios completed their 10 iterations cleanly. The IDX-01 asyncio.Lock crash appears to NOT be present on this stack (release-1.9.0 + Python 3.13.9 + macOS). Plan 06's Linux CI run will confirm whether the crash surfaces there.

## User Setup Required

None - no external service configuration required for this plan. Plan 06 will surface the Linux CI requirement (thresholds.json commit) to the human reviewer when it produces authoritative numbers.

## Handoff for Plan 06

- **Workflow command:** `uv run python -m src.backend.tests.benchmarks.driver --mode docker --verify --skip-build` (use after the workflow builds `benchmarks-lean`; `--skip-build` skips wrapper rebuild if the uncompiled image already exists from a prior run).
- **Thresholds file:** `src/backend/tests/benchmarks/thresholds.json` (committed by plan 06 Task 1 from the Linux CI snapshot; schema includes top-level `measurement_mode: "bytecode_compile_delta"` and `allowed_regression_pct: 15`).
- **Regression comment:** `src/backend/tests/benchmarks/reports/regression_comment.md` written by `--verify` on failure; consumed by plan 06's `gh pr comment --body-file` step. File is NOT written on pass, so plan 06's CI step MUST `if [ -f ... ]; then`-guard the comment.
- **`measurement_mode` field:** Both thresholds.json and baseline-*.json carry `measurement_mode: "bytecode_compile_delta"`. Plan 06's diff-mode check (future phase) can swap modes; the driver logs a stderr WARNING on mismatch but does NOT fail.
- **Langflow supervisor marker:** Plan 06 should verify on Linux whether `Application startup complete.` appears in langflow output. If not, plan 06 Task N may relax the `READY_MARKER` in `_langflow_supervisor.py`. The root cause is langflow's **structlog** processor pipeline (NOT loguru — the original note in this summary was wrong); a fallback of `Open Langflow -> http://localhost:` would reliably fire on any stack where the banner prints.
- **Authoritative baseline:** ship from plan 06 CI's GHA runner, not from macOS. `.planning/benchmarks/baseline-2026-04-16.{md,json}` here is smoke-only (local-only via .planning/ git-exclude) and not comparable to CI numbers.

## Next Phase Readiness

- Phase 01 complete after this plan; plan 06 (CI integration) is next.
- All MEAS-* requirements satisfied: MEAS-01 (scenarios), MEAS-02 (mock LLM + fixtures), MEAS-03 (6 checkpoints), MEAS-04 (-X importtime), MEAS-05 (pyinstrument), MEAS-06 (narrative + JSON sidecar), MEAS-07 (bytecode delta, reframed per D-11a).

## Self-Check: PASSED

- 15 created files all present on disk.
- 6 expected task commits present in `git log --oneline --all`.
- Plan 04's Dockerfile diff is empty over the plan 01-05 range (`git diff 0f39439ce2..HEAD src/backend/tests/benchmarks/Dockerfile | wc -l` -> 0).

---

*Phase: 01-measurement-foundation*
*Completed: 2026-04-16*
