---
phase: 01-measurement-foundation
plan: 02
subsystem: testing
tags: [benchmarks, cold-start, lfx, langchain-openai, monkey-patch, fixtures]

# Dependency graph
requires:
  - phase: 01-measurement-foundation
    provides: benchmark package scaffold (01-01: src/backend/tests/benchmarks/__init__.py, conftest.py)
provides:
  - BaseChatOpenAI._generate/._agenerate monkey-patch gated by LFX_BENCHMARK_MOCK_LLM
  - Three lfx-run-compatible fixture scripts (noop_flow, basic_prompting, document_qa)
  - Module-level graph = Graph(...) convention honored (pitfall 5)
  - CI-runnable flow execution with no OPENAI_API_KEY
affects: [01-03 checkpoint instrumentation, 01-05 benchmark driver, 01-06 CI regression gate]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Env-gated monkey-patch pattern (LFX_BENCHMARK_MOCK_LLM) for call-site LLM isolation"
    - "Lazy import via TYPE_CHECKING guard so mock module is free for typing-only consumers"
    - "Fixture wrappers reuse starter_projects factories rather than re-authoring flows"

key-files:
  created:
    - src/backend/tests/benchmarks/mock_llm.py
    - src/backend/tests/benchmarks/fixtures/__init__.py
    - src/backend/tests/benchmarks/fixtures/noop_flow.py
    - src/backend/tests/benchmarks/fixtures/basic_prompting.py
    - src/backend/tests/benchmarks/fixtures/document_qa.py
  modified: []

key-decisions:
  - "Patch _generate AND _agenerate, not _call (pitfall 4 correction; _call does not exist on BaseChatOpenAI in langchain-openai 1.1.12)"
  - "TYPE_CHECKING guard keeps langchain_core import lazy until install_mock() is actually invoked"
  - "noop_flow does NOT call install_if_enabled() so bare-boot pays no langchain_openai cost (keeps bare-boot cheapest)"
  - "install_if_enabled() called BEFORE basic_prompting_graph()/document_qa_graph() so the mock binds before component construction"
  - "document_qa fixture ships as-is; FileComponent needs a file on disk for execution (deferred to plan 05 per RESEARCH.md Open Question A)"

patterns-established:
  - "Call-site LLM mock: patch the langchain class method directly, gate behind env var, keep cost-of-import unmocked"
  - "lfx run fixture shape: module-level graph assignment, wrapper imports from langflow.initial_setup.starter_projects, mock-activation side effect at top of module"

requirements-completed: [MEAS-01, MEAS-07]

# Metrics
duration: 5min
completed: 2026-04-16
---

# Phase 1 Plan 02: LLM Mock and Fixtures Summary

**BaseChatOpenAI._generate/._agenerate monkey-patch plus three `lfx run`-compatible fixtures (noop_flow, basic_prompting, document_qa) enabling CI-runnable cold-start benchmarks with zero OpenAI API dependency.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-16T16:50:47Z
- **Completed:** 2026-04-16T16:55:49Z
- **Tasks:** 3
- **Files created:** 5

## Accomplishments

- `mock_llm.py` monkey-patches `BaseChatOpenAI._generate` AND `._agenerate` (pitfall 4 correction from CONTEXT.md D-04) behind `LFX_BENCHMARK_MOCK_LLM`, so cold-start cost (imports) is paid but HTTP is skipped.
- `fixtures/noop_flow.py` runs a minimal `ChatInput -> ChatOutput` graph that exercises the full cold-start path (service init, component index warmup, graph build) with no LLM cost. Used for the MEAS-01 bare-boot scenario.
- `fixtures/basic_prompting.py` wraps `basic_prompting_graph()` and activates the mock at import time. Verified end-to-end: `LFX_BENCHMARK_MOCK_LLM=1 uv run lfx run ... --format text` returns the fixed string and exits 0 with no `OPENAI_API_KEY` set.
- `fixtures/document_qa.py` wraps `document_qa_graph()` with the same mock pattern. The graph builds cleanly (import-time path runs); execution fails as predicted by RESEARCH.md Open Question A because `FileComponent` needs a file on disk. Plan 05 addresses this (either ship a tiny text fixture or skip document_qa execution for MEAS-01 variants that require it).

## Task Commits

Each task was committed atomically via `git commit --no-verify` (parallel worktree mode):

1. **Task 1: Create `mock_llm.py`** -- `9383dafb23` (feat)
2. **Task 2: Create no-op flow fixture** -- `94f7b28167` (feat)
3. **Task 3: Create basic_prompting and document_qa fixture wrappers** -- `0afc282e66` (feat)

## Files Created

- `src/backend/tests/benchmarks/mock_llm.py` (69 lines) -- env-gated monkey-patch with `install_mock()` and `install_if_enabled()`.
- `src/backend/tests/benchmarks/fixtures/__init__.py` (1 line) -- package marker.
- `src/backend/tests/benchmarks/fixtures/noop_flow.py` (35 lines) -- minimal `ChatInput -> ChatOutput`; no `langchain_openai` import; module-level `graph = Graph(...)`.
- `src/backend/tests/benchmarks/fixtures/basic_prompting.py` (25 lines) -- thin wrapper around `basic_prompting_graph()`; calls `install_if_enabled()` at import; module-level `graph = basic_prompting_graph()`.
- `src/backend/tests/benchmarks/fixtures/document_qa.py` (21 lines) -- thin wrapper around `document_qa_graph()`; same shape as basic_prompting.

**Note on `src/backend/tests/benchmarks/__init__.py`:** Plan 01-01 (running in a sibling wave-1 worktree) owns this file per its frontmatter. A local copy was created for import-path validation in this worktree but NOT staged/committed from here -- the file ships via plan 01-01's merge. See "Issues Encountered" below.

## Verified Behavior

**Mock mechanics** (with `LFX_BENCHMARK_MOCK_LLM=1`):
- Before install: `BaseChatOpenAI._generate` is the upstream langchain-openai 1.1.12 method.
- After `install_if_enabled()`: `BaseChatOpenAI._generate.__name__ == '_mock_generate'` and `BaseChatOpenAI._agenerate.__name__ == '_mock_agenerate'` (verified at lines 1445 / 1706 of upstream `chat_models/base.py`).
- Without the env var: `install_if_enabled()` returns `False` and no patch is applied.

**basic_prompting smoke-run** (`LFX_BENCHMARK_MOCK_LLM=1 uv run lfx run src/backend/tests/benchmarks/fixtures/basic_prompting.py --format text`):

```
Benchmark-fixed response.
```

Exit 0. No `OPENAI_API_KEY` set in env. The mocked `_generate` delivered the fixed `ChatResult` through the full `ChatInput -> PromptComponent -> OpenAIModelComponent -> ChatOutput` chain.

**noop_flow smoke-run** (`uv run lfx run src/backend/tests/benchmarks/fixtures/noop_flow.py --format text`):

Exit 0. Empty stdout (`ChatInput` with empty `input_value` produces an empty message; the point is that service init + component index warmup + graph build + single-vertex execution all succeed).

**document_qa status:** Import-time path runs cleanly (`type(graph).__name__ == 'Graph'`). Execution under `lfx run` fails as predicted:

```
{"success": false, "type": "error", "exception_type": "ComponentBuildError",
 "exception_message": "Error building Component Read File: \n\nNo files to process."}
```

This is the FileComponent-needs-a-file issue from RESEARCH.md §Open Questions 2. The fixture is correct as-written per the plan action ("Do NOT pre-emptively create that file here; confirm the failure mode first"). Failure is deferred to plan 05.

## Decisions Made

None beyond what the plan specified. All three tasks executed exactly as written (the `_call` -> `_generate`/`_agenerate` correction was already pre-baked into the plan action and RESEARCH.md Pitfall 4).

## Deviations from Plan

None -- plan executed exactly as written.

The plan itself pre-empted the most likely deviation by documenting Pitfall 4 (`_call` does not exist on BaseChatOpenAI in langchain-openai 1.1.12; patch `_generate`/`_agenerate` instead) and Pitfall 5 (`lfx run` requires module-level `graph = ...`). Both were honored in the task action code blocks verbatim.

The `document_qa` execution failure was predicted and accepted by the plan itself: Task 3 instructs "Do NOT pre-emptively create that file here; confirm the failure mode first." Confirmation happened (see "Verified Behavior" above); plan 05 addresses the follow-up.

## Issues Encountered

**Plan 01-01's `src/backend/tests/benchmarks/__init__.py` is a concurrent dependency.** Plan 01-02 imports from `src.backend.tests.benchmarks.mock_llm`, which requires the benchmarks package to be importable. Plan 01-01 owns the package `__init__.py`. Because this worktree runs in parallel with 01-01's worktree, the file was not available from 01-01's output at the moment 01-02 ran. To validate imports locally without staging 01-01's file from this worktree, a minimal `__init__.py` was written to the worktree filesystem but NOT added to git. After the orchestrator merges 01-01's worktree, the authoritative `__init__.py` from that plan will become the canonical version.

No other issues.

## Handoff Notes for Plan 05 (Driver)

**Fixture invocation from the benchmark container root:**

```bash
# Bare-boot (MEAS-01 minimal):
uv run lfx run src/backend/tests/benchmarks/fixtures/noop_flow.py --format text

# Primary MEAS-01 and MEAS-07 (CI-safe; no API key needed):
LFX_BENCHMARK_MOCK_LLM=1 uv run lfx run src/backend/tests/benchmarks/fixtures/basic_prompting.py --format text

# Secondary MEAS-01 (currently NOT runnable under lfx run without shipping a file):
# Option A (Plan 05): add src/backend/tests/benchmarks/fixtures/sample_doc.txt and wire FileComponent.path to it before building the graph.
# Option B (Plan 05): drop document_qa from MEAS-01 execution variants, keep it only as an import-time cold-start scenario.
LFX_BENCHMARK_MOCK_LLM=1 uv run lfx run src/backend/tests/benchmarks/fixtures/document_qa.py --format text  # FAILS today; see above.
```

**Env vars:**
- `LFX_BENCHMARK_MOCK_LLM=1` -- activates the BaseChatOpenAI mock; safe to leave set for every scenario, the `noop_flow` fixture ignores it (no LLM imported).
- `OPENAI_API_KEY` -- NOT required for any of the three fixtures when `LFX_BENCHMARK_MOCK_LLM=1` is set.

**Idempotency:** `install_mock()` is safe to call repeatedly; subsequent calls overwrite with the same functions.

**Import-cost characteristics:**
- `noop_flow`: does NOT import `langchain_openai` or any LLM SDK. Pays lfx + service init + component index.
- `basic_prompting` / `document_qa`: import-time cost includes full `langchain_openai` chain (this is intentional per D-04 so MEAS-07 can isolate dep-install vs import cost).

## User Setup Required

None -- no external service configuration. The LLM mock removes the need for `OPENAI_API_KEY` in CI; local development against a real key still works because the mock is a no-op when `LFX_BENCHMARK_MOCK_LLM` is unset.

## Next Phase Readiness

Ready for plan 01-03 (checkpoint instrumentation for MEAS-03) and plan 01-05 (benchmark driver that invokes these fixtures via `hyperfine`).

Open items for plan 05:
1. Decide whether to ship `fixtures/sample_doc.txt` for `document_qa` or scope it out of MEAS-01 execution variants.
2. Confirm `basic_prompting` is the only fixture used for MEAS-07 dep-install isolation (D-02).

## Self-Check: PASSED

**Files verified on disk:**
- `src/backend/tests/benchmarks/mock_llm.py`
- `src/backend/tests/benchmarks/fixtures/__init__.py`
- `src/backend/tests/benchmarks/fixtures/noop_flow.py`
- `src/backend/tests/benchmarks/fixtures/basic_prompting.py`
- `src/backend/tests/benchmarks/fixtures/document_qa.py`
- `.planning/phases/01-measurement-foundation/01-02-SUMMARY.md`

**Commits verified:**
- `9383dafb23` feat(01-02): add BaseChatOpenAI mock for cold-start benchmarks
- `94f7b28167` feat(01-02): add no-op flow fixture for MEAS-01 bare-boot scenario
- `0afc282e66` feat(01-02): add basic_prompting and document_qa benchmark fixtures

**Plan-level verification (9 items):** All passed (see "Verified Behavior" above for details).

---

*Phase: 01-measurement-foundation*
*Plan: 02*
*Completed: 2026-04-16*
