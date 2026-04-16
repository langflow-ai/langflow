---
phase: 02-component-index-and-correctness-fixes
plan: 05
subsystem: lfx-component-index

tags: [idx, idx-03, asyncio, to-thread, event-loop, read-path, parity]

requires:
  - phase: 02-component-index-and-correctness-fixes
    plan: 02-01
    provides: shared parity scaffolding (_parity_helpers.py), smallest.snapshot.json
  - phase: 02-component-index-and-correctness-fixes
    plan: 02-03
    provides: TestIDX04IDX05WriteSide::test_round_trip_lfx_only_env (converted here to async)
provides:
  - async _read_component_index with asyncio.to_thread-wrapped index_path.read_bytes at both sites (IDX-03)
  - Both callers of _read_component_index in _load_from_index_or_cache use await
  - TestIDX03ReadPath class with coroutine-function check, non-blocking-event-loop proof, and parity guards on smallest.json + five_types.json
  - TestImportLangflowComponents patches migrated to AsyncMock; TestReadComponentIndex methods converted to async; TestIDX04IDX05WriteSide::test_round_trip_lfx_only_env converted to async
affects: [02-06]

tech-stack:
  added: []
  patterns:
    - "await asyncio.to_thread(index_path.read_bytes) to off-load the 5.7MB built-in index read to the default thread pool so the event loop advances during cold start"
    - "new=AsyncMock(return_value=...) on patch() blocks for async callees; bind via `with patch(..., new=AsyncMock(...)) as mock_x:` when assert_called_with is also needed"
    - "@pytest.mark.asyncio on a single method of a sync class (opt-in) instead of class-level, when most sibling tests remain sync (option (a) in the plan)"
    - "# noqa: ASYNC210 with explanatory comment to suppress ruff on an intentionally-out-of-scope sync httpx call inside an async function"

key-files:
  created: []
  modified:
    - src/lfx/src/lfx/interface/components.py
    - src/lfx/tests/unit/test_component_index.py

key-decisions:
  - "Option (a) from plan 02-05 STEP 1b: add @pytest.mark.asyncio to the individual method test_round_trip_lfx_only_env and change it to async def, leaving TestIDX04IDX05WriteSide as a sync class for the three sibling sync tests. Smaller diff than moving the test into a new async-marked class."
  - "TestReadComponentIndex (7 pre-existing tests that call _read_component_index directly) also converted to async with await. Not called out in the plan text but strictly impacted by Task 1's sync-to-async refactor; auto-fixed under Rule 1 (broken callers after an in-scope change). The test bodies are otherwise unchanged."
  - "Third AsyncMock site in TestImportLangflowComponents::test_import_with_custom_path_from_settings uses `with patch(..., new=AsyncMock(return_value=index)) as mock_read` to satisfy both the AsyncMock awaitable-return and `mock_read.assert_called_with(str(custom_file))`. This form keeps the grep acceptance of exactly 3 literal `new=AsyncMock(return_value=` occurrences satisfied."
  - "`# noqa: ASYNC210` added to the sync `httpx.get(custom_path, timeout=10.0)` call at line 131. The plan text explicitly leaves the httpx path unchanged (out of scope for IDX-03 per research Pitfall 3 and CONCERNS.md §1.7); converting `_read_component_index` to async triggered ASYNC210 on that previously-sync call. The suppression is accompanied by a 3-line comment naming CONCERNS.md §1.7 as the follow-up owner."
  - "test_read_does_not_block_event_loop asserts ticker_count > 0 (loose threshold) rather than an absolute count. Research note is explicit: tmpfs-backed test filesystems can complete the read in microseconds where ticker only gets 1-3 interleaved ticks; a tighter bound would be flaky on fast disks. One tick is the minimum provable `not fully blocked` signal."

requirements-completed: [IDX-03]

duration: ~25 min
completed: 2026-04-16
---

# Phase 2 Plan 05: async _read_component_index with asyncio.to_thread (IDX-03) Summary

**`_read_component_index` is now an `async def`; both `index_path.read_bytes()` call sites are wrapped in `await asyncio.to_thread(index_path.read_bytes)` so the 5.7MB built-in index read (and arbitrary user cache files) no longer block the event loop during cold start. Both callers in `_load_from_index_or_cache` gained `await`; `TestImportLangflowComponents` patches migrated to `AsyncMock`; `TestReadComponentIndex` methods converted to async; `TestIDX04IDX05WriteSide::test_round_trip_lfx_only_env` (added by 02-03) converted to async per STEP 1b. A new `TestIDX03ReadPath` class proves the function is a coroutine, proves the event loop is not blocked during the read (ticker_count=3 observed), and re-verifies deep parity on smallest.json byte-identically to plan 02-01's snapshot.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-04-16 (HEAD 9db4acccf2 after 02-04 completion)
- **Completed:** 2026-04-16
- **Tasks:** 2 (both TDD: async refactor + test mock migration + TestIDX03ReadPath addition)
- **Files modified:** 2 (0 created, 0 deleted)

## Accomplishments

- `_read_component_index` signature flipped from `def` to `async def`. Both `index_path.read_bytes()` call sites (the custom user-cache branch at ~line 144 and the built-in `_assets/component_index.json` branch at ~line 157) are now `await asyncio.to_thread(index_path.read_bytes)`. The event loop advances during the off-loaded read, proven by the ticker test (ticker_count=3 observed on a synthetic valid index; value >0 is the contract, absolute number varies by disk speed).
- Both callers inside `_load_from_index_or_cache` (the prebuilt-index branch at line 338 and the cache branch at line 361) now use `await _read_component_index(...)`. The enclosing function was already `async def`, so no further call-site propagation required.
- `httpx.get` call at line 131 is deliberately left sync (out of scope for IDX-03 per research Pitfall 3; tracked under CONCERNS.md §1.7). Ruff ASYNC210 was suppressed with an explanatory comment rather than an ad-hoc async httpx rewrite.
- Test mocks updated: three `TestImportLangflowComponents` tests that patched `_read_component_index` migrated to `new=AsyncMock(return_value=...)` so awaiting returns the dict; `TestReadComponentIndex`'s seven pre-existing direct-caller tests converted to `async def ... await _read_component_index(...)` (auto-fixed under Rule 1 since they were directly broken by Task 1). `TestIDX04IDX05WriteSide::test_round_trip_lfx_only_env` (added by plan 02-03) converted to async per STEP 1b (option (a): add `@pytest.mark.asyncio` to the single method, keep the parent sync class).
- `TestIDX03ReadPath` added with 4 tests: coroutine-function check, non-blocking event loop proof, parity on smallest.json, parity on five_types.json (latter skips cleanly in lfx-only venv where langchain_openai is absent, matching `TestIDX02SemaphoreCap::test_parity_five_types`).

## Task Commits

Each task committed atomically (pre-commit hooks active, no `--no-verify`):

1. **Task 1: Convert _read_component_index to async with asyncio.to_thread (IDX-03)** — `0d41e2636b` (feat)
2. **Task 2: Adapt tests to async _read_component_index + add TestIDX03ReadPath** — `37c4f98627` (test)

## Observed Non-Blocking Ticker Count (per plan output spec)

`test_read_does_not_block_event_loop` runs a concurrent ticker coroutine that yields to the loop via `await asyncio.sleep(0)` on every iteration while `_read_component_index` runs on a synthetic 20x20 (400-component) index. The contract is `ticker_count > 0` (event loop is not fully blocked).

**Observed value on the test machine (macOS darwin, Python 3.13, local filesystem):** `ticker_count=3`, `result_is_valid=True`. The exact value varies by disk speed; 3 is typical for a ~4KB in-tmp-dir read on an APFS SSD. On a 5.7MB shipped-index read in a production cold-start scenario, the ticker would advance many more times — the test intentionally uses a small synthetic index to keep the test itself fast, so the lower-bound threshold (>0) is the only robust assertion.

## TestImportLangflowComponents AsyncMock Conversion (per plan output spec)

All three affected tests pass after migration:

| Test | Patch form | Assertion form |
|------|------------|----------------|
| `test_import_with_builtin_index` | `new=AsyncMock(return_value=index)` | no mock-call assertion |
| `test_import_with_missing_index_creates_cache` | `new=AsyncMock(return_value=None)` | no mock-call assertion |
| `test_import_with_custom_path_from_settings` | `new=AsyncMock(return_value=index)` bound via `as mock_read` | `mock_read.assert_called_with(str(custom_file))` |

`test_import_with_dev_mode` and `test_import_handles_import_errors` do NOT patch `_read_component_index` — they patch `_process_single_module` / `pkgutil.walk_packages` — so they were unaffected by the refactor and are unchanged.

## Parity Snapshot Match (per plan output spec)

`TestIDX03ReadPath::test_parity_smallest_after_async_refactor` compares an in-process `_capture_parity_snapshot(smallest.json)` call against `smallest.snapshot.json` captured in plan 02-01. Snapshot is byte-identical:

```json
{
  "final_text": "hello",
  "vertex_order": [
    "ChatInput-5aSdS",
    "ChatOutput-WnLEC"
  ]
}
```

`test_parity_five_types_after_async_refactor` skips cleanly in the lfx-only test venv (same environment reason as `TestIDX02SemaphoreCap::test_parity_five_types` — `five_types.json` instantiates OpenAIModel which requires langchain_openai).

## Test Outcomes

Running `cd src/lfx && uv sync && uv run pytest tests/unit/test_component_index.py -v`:

- `TestIDX03ReadPath::test_is_coroutine_function`: PASSED
- `TestIDX03ReadPath::test_read_does_not_block_event_loop`: PASSED (ticker_count=3, result valid)
- `TestIDX03ReadPath::test_parity_smallest_after_async_refactor`: PASSED (byte-identical snapshot)
- `TestIDX03ReadPath::test_parity_five_types_after_async_refactor`: SKIPPED (langchain_openai absent, lfx-only venv, expected)
- `TestImportLangflowComponents` all 5 tests: PASSED
- `TestReadComponentIndex` all 7 tests (converted to async): PASSED
- `TestIDX04IDX05WriteSide::test_round_trip_lfx_only_env`: PASSED (now awaits `_read_component_index`)
- **Full file regression:** `39 passed + 2 skipped` in ~0.76s. Previous baseline was 36 passed + 1 skipped (end of plan 02-03); IDX-03 added 3 new passing TestIDX03ReadPath tests and 1 expected skip, so the counts align: 36+3 passed = 39 and 1+1 skipped = 2.

## Acceptance Grep Results

| Grep | Expected | Actual |
|------|----------|--------|
| `^async def _read_component_index` in components.py | 1 | 1 |
| `^def _read_component_index` in components.py | 0 | 0 |
| `await asyncio\.to_thread\(index_path\.read_bytes\)` in components.py | 2 | 2 |
| `index_path\.read_bytes\(\)` direct call in components.py | 0 | 0 |
| `await _read_component_index\(` in components.py | 2 | 2 |
| `class TestIDX03ReadPath` in test file | 1 | 1 |
| `def test_is_coroutine_function` in test file | 1 | 1 |
| `def test_read_does_not_block_event_loop` in test file | 1 | 1 |
| `def test_parity_smallest_after_async_refactor` in test file | 1 | 1 |
| `new=AsyncMock\(return_value=` in test file | 3 | 3 |
| `await _read_component_index\(str\(cache_file\)\)` in test file (STEP 1b) | 1 | 1 |

All 11 acceptance greps satisfied.

## Files Modified

- `src/lfx/src/lfx/interface/components.py` — `_read_component_index` signature changed to `async def`; two `orjson.loads(index_path.read_bytes())` calls wrapped with `orjson.loads(await asyncio.to_thread(index_path.read_bytes))`; two caller sites in `_load_from_index_or_cache` gained `await`; `httpx.get` line carries a `# noqa: ASYNC210` with an explanatory comment naming CONCERNS.md §1.7 as the future fix owner. No import changes — `asyncio` was already imported at line 1.
- `src/lfx/tests/unit/test_component_index.py` — 7 `TestReadComponentIndex` methods converted to `async def` + `await`; 3 `TestImportLangflowComponents` tests migrated to `new=AsyncMock(return_value=...)`; `TestIDX04IDX05WriteSide::test_round_trip_lfx_only_env` promoted to `@pytest.mark.asyncio` + `async def` + `await`; new `TestIDX03ReadPath` class appended at end of file with 4 tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Ruff ASYNC210 flagged sync httpx.get inside the now-async function**
- **Found during:** First commit attempt for Task 1.
- **Issue:** After promoting `_read_component_index` to `async def`, ruff ASYNC210 ("Async functions should not call blocking HTTP methods") fired on the pre-existing `response = httpx.get(custom_path, timeout=10.0)` at line 128. The plan EXPLICITLY leaves this call unchanged (Pitfall 3 in 02-RESEARCH.md: "The `httpx.get` sync call at line 107 is ALSO a blocking concern but is out of scope for IDX-03").
- **Fix:** Added `# noqa: ASYNC210` with a 3-line comment naming CONCERNS.md §1.7 as the follow-up owner. Preserves the plan's scope boundary while satisfying the linter.
- **Files modified:** `src/lfx/src/lfx/interface/components.py`
- **Verification:** `ruff check` passes; the sync HTTP call remains (only reachable when the user explicitly points `components_index_path` at an http(s) URL, which is a rare edge case compared to the common 5.7MB built-in file read).
- **Committed in:** `0d41e2636b` (Task 1)

**2. [Rule 1 - Bug] TestReadComponentIndex (7 pre-existing tests) broken by async refactor**
- **Found during:** Post-Task-1 full-file test run (before Task 2).
- **Issue:** The plan's text only named the `TestImportLangflowComponents` (3 tests) and `TestIDX04IDX05WriteSide::test_round_trip_lfx_only_env` (1 test) as needing updates. But `TestReadComponentIndex` has 7 pre-existing tests that call `_read_component_index()` directly as a sync function. After Task 1, all 7 broke with `TypeError: 'coroutine' object is not subscriptable` or `assert <coroutine object _read_component_index> is None` (depending on whether they dereferenced the return value).
- **Fix:** Converted all 7 `TestReadComponentIndex` methods to `async def ... await _read_component_index(...)`. No body changes beyond signature + `await`; `asyncio_mode = "auto"` in `src/lfx/pyproject.toml:70` makes pytest-asyncio collect them automatically without `@pytest.mark.asyncio`.
- **Files modified:** `src/lfx/tests/unit/test_component_index.py`
- **Verification:** All 7 pass after conversion (full file 39/39 + 2 expected skips).
- **Committed in:** `37c4f98627` (Task 2)

**3. [Rule 3 - Blocking] Ruff ARG002 on unused `monkeypatch` parameter**
- **Found during:** First commit attempt for Task 2.
- **Issue:** The plan's TestIDX03ReadPath example test `test_read_does_not_block_event_loop` had a `monkeypatch` parameter in the signature, but the final body only uses `tmp_path` and `patch(...)` context manager; `monkeypatch` is never called. Ruff ARG002 rejected the commit.
- **Fix:** Removed the unused `monkeypatch` parameter from the method signature.
- **Files modified:** `src/lfx/tests/unit/test_component_index.py`
- **Verification:** `ruff check` passes; test still passes (ticker_count=3).
- **Committed in:** `37c4f98627` (Task 2)

### Other Friction (not Rule-triggered)

- **uv sync cycle after pre-commit hooks:** Running the monorepo pre-commit ruff hooks perturbs the lfx-only venv such that pytest's conftest "langflow must not be installed" gate misfires on the next `uv run pytest`. Same friction as plans 02-01, 02-02, 02-03 noted. Resolved each time by `cd src/lfx && uv sync`. No code issue.
- **Ruff format reformatted `test_component_index.py` on commit:** Pre-commit's ruff-format hook wrapped one long line that spanned the new `with patch(...) as mock_read` context. Semantically identical; no test behavior change. Re-staged and retried the commit.

---

**Total deviations:** 3 auto-fixed (1 Rule 1 bug, 2 Rule 3 blocking).
**Impact on plan:** All deviations were tooling/lint/test-wiring fixes downstream of the in-scope sync-to-async refactor. The production code surface matches the plan text exactly: `async def _read_component_index`, two `asyncio.to_thread` wraps, two caller-site `await` updates, httpx.get sync call preserved (out of scope). The only addition beyond the plan's explicit test updates is the TestReadComponentIndex conversion, which the plan did not enumerate but strictly follows from the sync-to-async refactor.

## Issues Encountered

None beyond the deviations documented above. No blockers. No architectural questions.

## Next Plan Readiness (02-06 IDX-07 stale-index warning)

- The `await asyncio.to_thread(cache_path.read_bytes)` pattern used in IDX-03 is directly reusable by the 02-06 stale-index warning's fast "version peek" (see 02-RESEARCH.md's IDX-07 code example, which already uses `await asyncio.to_thread(cache_path.read_bytes)`).
- `get_and_cache_all_types_dict`'s async surface is unchanged; 02-06 inserts its version-mismatch check inside that function's lock-critical section.
- `_parity_helpers.py` scaffolding continues to be shared; 02-06 can import `_PARITY_FIXTURES_DIR` and `_capture_parity_snapshot` the same way 02-05 did.
- No blockers. No open questions introduced by this plan.

---
*Phase: 02-component-index-and-correctness-fixes*
*Completed: 2026-04-16*

## Self-Check: PASSED

- src/lfx/src/lfx/interface/components.py: FOUND (modified; grep `async def _read_component_index` -> 1, `def _read_component_index` -> 0, `await asyncio.to_thread(index_path.read_bytes)` -> 2, `index_path.read_bytes()` -> 0, `await _read_component_index(` -> 2)
- src/lfx/tests/unit/test_component_index.py: FOUND (modified; grep `class TestIDX03ReadPath` -> 1, `def test_is_coroutine_function` -> 1, `def test_read_does_not_block_event_loop` -> 1, `def test_parity_smallest_after_async_refactor` -> 1, `new=AsyncMock(return_value=` -> 3, `await _read_component_index(str(cache_file))` -> 1)
- Commit 0d41e2636b (Task 1, feat): FOUND in git log
- Commit 37c4f98627 (Task 2, test): FOUND in git log
- Test suite: 39 passing + 2 skipped (expected, five_types on lfx-only venv) in tests/unit/test_component_index.py
- Acceptance greps: all 11 target patterns matched exactly
- ticker_count observed: 3 (> 0 contract satisfied)
- Parity snapshot match: byte-identical to plan 02-01's smallest.snapshot.json
- Module imports cleanly: `from lfx.interface.components import _read_component_index, _load_from_index_or_cache, get_and_cache_all_types_dict` succeeds
- `_read_component_index` is coroutine function: `inspect.iscoroutinefunction(_read_component_index)` returns True
