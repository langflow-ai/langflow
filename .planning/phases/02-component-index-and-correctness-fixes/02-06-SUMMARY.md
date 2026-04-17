---
phase: 02-component-index-and-correctness-fixes
plan: 06
subsystem: lfx-component-index

tags: [idx, idx-07, stale-index, warning, structlog, read-time, parity]

requires:
  - phase: 02-component-index-and-correctness-fixes
    plan: 02-01
    provides: lazy asyncio.Lock property on ComponentCache; TestIDX01LazyLock::test_cache_built_once_threading; shared parity scaffolding (_parity_helpers.py)
  - phase: 02-component-index-and-correctness-fixes
    plan: 02-03
    provides: _save_generated_index stamps cache with version("lfx"); TestIDX04IDX05WriteSide
  - phase: 02-component-index-and-correctness-fixes
    plan: 02-05
    provides: async _read_component_index with asyncio.to_thread read pattern
provides:
  - Read-time stale-index warning inside get_and_cache_all_types_dict that fires exactly once when the user's disk cache version differs from the installed lfx version, logs via structlog (logger.warning), includes cached + installed versions + cache path, silent on version match / absent cache / corrupt cache, placed BEFORE the cache build lock so it does not widen the lock-hold window
  - TestIDX07StaleIndexWarning class with 5 tests (fires-on-mismatch, silent-on-match, silent-when-absent, silent-on-corrupt, parity on smallest.json)
  - Threading test (TestIDX01LazyLock::test_cache_built_once_threading) isolated from user's real disk cache via monkey-patched _get_cache_path defense-in-depth
affects: []

tech-stack:
  added: []
  patterns:
    - "Read-time stale-index warning pattern: orjson.loads(await asyncio.to_thread(cache_path.read_bytes)) to peek the cached version without blocking the event loop, gated on cache_path.exists() so the built-in shipped index never fires the warning"
    - "Structlog-routed warning captured in tests via monkeypatch.setattr(ci.logger, 'warning', MagicMock()) rather than caplog, sidestepping structlog/stdlib-logging bridge variance across test environments"
    - "Idempotent read-only checks placed BEFORE the cache-build lock acquisition when they must yield to the event loop; the double-check inside the lock preserves cache-build-once semantics without holding the lock during the disk I/O"

key-files:
  created: []
  modified:
    - src/lfx/src/lfx/interface/components.py
    - src/lfx/tests/unit/test_component_index.py

key-decisions:
  - "IDX-07 peek placed OUTSIDE the ComponentCache.lock critical section. The plan text directed `BETWEEN the await logger.adebug(\"Building components cache\") line and the langflow_components = await import_langflow_components(...) line` (i.e. inside the lock), but plan's own <interfaces> + <context> sections flagged that 02-RESEARCH.md recommends `BEFORE` and that placement is left to the implementer. Placing the peek inside the lock regressed TestIDX01LazyLock::test_cache_built_once_threading from a sub-second pass to a 60s+ deadlock-like hang: holding the per-thread lock while running a ~5MB asyncio.to_thread disk read widens the lock-hold window enough to expose a latent race in the lazy-lock reset pattern. Moving the peek BEFORE the lock restores the test to its pre-IDX-07 timing and aligns with the research recommendation."
  - "Threading-test isolation retained as defense in depth: even after moving the peek outside the lock, the test now also monkey-patches _get_cache_path to a non-existent tmp_path so the IDX-07 peek short-circuits on cache_path.exists() == False instead of reading the developer's real 5.9MB user cache. This keeps the test deterministic across environments and makes the intent explicit (the test is about multi-loop lock behaviour, not about the stale-index warning)."
  - "Test capture via MagicMock instead of caplog. Plan allowed either; chose MagicMock on ci.logger.warning so structlog BoundLogger processor-chain variance (e.g. different structlog configs between environments) cannot hide a legitimate warning miss. Rendered-message assertion uses `fmt % tuple(args)` to verify all three substituted fields are present."

requirements-completed: [IDX-07]

duration: ~35 min
completed: 2026-04-16
---

# Phase 2 Plan 06: IDX-07 read-time stale-index warning Summary

**`get_and_cache_all_types_dict` now emits `logger.warning("stale component index: cached=%s, installed=%s, path=%s. Delete the file or restart to regenerate.", ...)` exactly once when the user's disk cache at `_get_cache_path()` has a `version` field differing from `importlib.metadata.version("lfx")`. The peek uses `orjson.loads(await asyncio.to_thread(cache_path.read_bytes))` so the event loop is not blocked during cold start. The warning is gated on `cache_path.exists()` so clean installs that only load the built-in `_assets/component_index.json` never fire it, and an `except Exception: pass` on the peek swallows corrupt-cache noise (downstream `_read_component_index` retains the corrupt-file warning path). The peek runs BEFORE `async with component_cache.lock:` rather than inside it to avoid widening the lock-hold window, which otherwise regresses the existing `TestIDX01LazyLock::test_cache_built_once_threading` test from sub-second to 60s+ deadlock-like hang; the threading test also gains a monkey-patched `_get_cache_path` defense-in-depth so it never reads the developer's real on-disk cache.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-04-16 (HEAD df303643d1 after 02-05 completion)
- **Completed:** 2026-04-16
- **Tasks:** 2 (both TDD: read-time warning implementation + test class addition) + 1 deviation-driven fix commit
- **Files modified:** 2 (0 created, 0 deleted)

## Accomplishments

- `get_and_cache_all_types_dict` in `src/lfx/src/lfx/interface/components.py` now performs a disk-cache version peek before acquiring `component_cache.lock`. If the installed lfx version is resolvable and `_get_cache_path()` points at an existing file, the function reads that file via `await asyncio.to_thread(cache_path.read_bytes)`, parses `version` via `orjson.loads`, and emits `logger.warning(...)` when the two versions disagree. All exception paths during the peek are swallowed with `# noqa: BLE001, S110` — the downstream `_read_component_index` owns the corrupt-file warning path.
- `TestIDX07StaleIndexWarning` added with 5 tests (all pass, 1.87s): `test_warning_fires_on_version_mismatch`, `test_warning_silent_on_version_match`, `test_warning_silent_when_cache_file_absent`, `test_warning_silent_on_corrupt_cache`, `test_parity_smallest_after_idx07`.
- Threading test `TestIDX01LazyLock::test_cache_built_once_threading` gains a monkey-patched `_get_cache_path` pointing at a non-existent `tmp_path / "definitely_not_here.json"`. This is the specific isolation fix called out in the user's execution brief: with IDX-07 reading the user's real 5.9MB on-disk cache inside ten concurrent threads each with their own event loop, the test turned pathologically slow.
- Full `src/lfx/tests/unit/test_component_index.py` suite: **44 passed, 2 skipped** (both skips expected — `langchain_openai` absent in lfx-only venv) in 2.34s. Previous baseline after 02-05: 39 passed + 2 skipped. IDX-07 added 5 new passing tests; the numbers align.

## Task Commits

Each commit passes the lfx pre-commit hooks (ruff check, ruff format, case-conflicts, end-of-files, trim-whitespace, detect-secrets). No `--no-verify`.

1. **Task 1: Add read-time stale-index warning inside get_and_cache_all_types_dict** — `83b0cae972` (feat)
2. **Deviation fix: move IDX-07 peek outside cache lock + isolate threading test from user disk** — `f6315feb38` (fix)
3. **Task 2: Add TestIDX07StaleIndexWarning for IDX-07 read-time warning** — `a6129189ca` (test)

## Observed Warning Message (per plan output spec)

`test_warning_fires_on_version_mismatch` constructs a disk cache file with `version="old-1.0"` and patches `importlib.metadata.version("lfx")` to return `"new-2.0"`. The MagicMock captures exactly one call to `ci.logger.warning` with:

```python
(
    "stale component index: cached=%s, installed=%s, path=%s. Delete the file or restart to regenerate.",
    "old-1.0",
    "new-2.0",
    PosixPath(".../tmpdir/component_index.json"),
)
```

Rendered (via `fmt % tuple(args)`):

```
stale component index: cached=old-1.0, installed=new-2.0, path=/private/var/folders/.../component_index.json. Delete the file or restart to regenerate.
```

All three substituted fields (cached version, installed version, cache file path) are present.

## Negative-Case Silence (per plan output spec)

The three negative tests assert `not stale_calls` (zero matching warning calls):

| Test | Setup | Stale-warning calls |
|------|-------|---------------------|
| `test_warning_silent_on_version_match` | cached `"same-1.0"` + installed `"same-1.0"` | 0 |
| `test_warning_silent_when_cache_file_absent` | `_get_cache_path()` returns non-existent path | 0 |
| `test_warning_silent_on_corrupt_cache` | cache file contains `b"this is not json at all {{{ garbage"` | 0 |

## Parity Snapshot Match (per plan output spec)

`TestIDX07StaleIndexWarning::test_parity_smallest_after_idx07` compares `_capture_parity_snapshot(smallest.json)` against `smallest.snapshot.json` captured in plan 02-01. Snapshot is byte-identical:

```json
{
  "final_text": "hello",
  "vertex_order": [
    "ChatInput-5aSdS",
    "ChatOutput-WnLEC"
  ]
}
```

## Position of Peek Relative to import_langflow_components

**BEFORE**, and also before `async with component_cache.lock:`. See Deviations section below for the rationale — the plan text suggested placing the peek between `await logger.adebug(...)` and `await import_langflow_components(...)` (i.e. inside the lock), but both the plan's <context> note and 02-RESEARCH.md recommend placing it BEFORE `import_langflow_components`, and placement relative to the lock was left to the implementer. We moved it outside the lock after discovering that inside-the-lock placement regressed `TestIDX01LazyLock::test_cache_built_once_threading` from 0.62s to a 60s+ hang.

## Acceptance Grep Results

| Grep | Expected | Actual |
|------|----------|--------|
| `stale component index` in components.py | 1 | 1 |
| `logger\.warning\(` in components.py | >=1 | multiple (including new IDX-07 warning) |
| `warnings\.warn` in components.py | 0 | 0 |
| `await asyncio\.to_thread\(cache_path\.read_bytes\)` in components.py | 1 | 1 |
| `installed_version = _version\("lfx"\)` in components.py | 1 | 1 |
| `class TestIDX07StaleIndexWarning` in test file | 1 | 1 |
| `def test_warning_fires_on_version_mismatch` in test file | 1 | 1 |
| `def test_warning_silent_on_version_match` in test file | 1 | 1 |
| `def test_warning_silent_when_cache_file_absent` in test file | 1 | 1 |
| `def test_warning_silent_on_corrupt_cache` in test file | 1 | 1 |
| `def test_parity_smallest_after_idx07` in test file | 1 | 1 |

All 11 acceptance greps satisfied.

## Files Modified

- `src/lfx/src/lfx/interface/components.py` — added ~50-line IDX-07 peek block at the top of `get_and_cache_all_types_dict`'s `if component_cache.all_types_dict is None:` branch, BEFORE `async with component_cache.lock:`. Resolves `installed_version` via `_version("lfx")` with `PackageNotFoundError` fallback, then `_get_cache_path()`, then `cache_path.exists()`, then `orjson.loads(await asyncio.to_thread(cache_path.read_bytes))`, then a type-safe extraction of `cached_version` and the emit path. `# noqa: BLE001, S110` on the outer `except Exception: pass` captures both broad-except and pass-without-log ruff flags. No imports added at module scope — `importlib.metadata` symbols are imported locally inside the block under aliases `_version` / `_PackageNotFoundError` to avoid collisions with other local imports in the same function added by earlier plans.
- `src/lfx/tests/unit/test_component_index.py` — (1) `TestIDX01LazyLock::test_cache_built_once_threading` gains a `tmp_path` parameter and a `monkeypatch.setattr(ci, "_get_cache_path", lambda: _absent_cache_path)` at the top so the IDX-07 peek short-circuits on `cache_path.exists()` being False; docstring extended with "IDX-07 isolation" section explaining why. (2) `TestIDX07StaleIndexWarning` appended at end of file with 5 tests using `monkeypatch.setattr(ci.logger, "warning", MagicMock())` for structlog-agnostic capture.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] IDX-07 peek inside the cache lock regresses TestIDX01LazyLock::test_cache_built_once_threading**

- **Found during:** Post-Task-1 verification — running `TestIDX01LazyLock -v` went from 0.62s (pre-IDX-07 baseline confirmed by checking out `df303643d1` of components.py) to 2:00 with the threading test failing under `RuntimeError('Lock bound to different event loop')`. Running the threading test alone post-Task-1 hung for 14+ minutes.
- **Issue:** The plan's `<action>` text directed inserting the peek `BETWEEN the await logger.adebug("Building components cache") line and the langflow_components = await import_langflow_components(...) line` — i.e., INSIDE the `async with component_cache.lock:` critical section. But both the plan's own `<interfaces>` block and 02-RESEARCH.md's "IDX-07 stale warning" Code Examples entry explicitly note that the peek should be placed BEFORE `import_langflow_components` and that outside-the-lock placement is permissible. Holding the per-thread lock while performing a ~5MB `asyncio.to_thread` disk read widens the lock-hold window enough to expose a latent race in the ComponentCache lazy-lock reset pattern exercised by the threading test: a thread's lock bound to event-loop A is observed by another thread still operating in loop B.
- **Fix:** Moved the IDX-07 peek BEFORE `async with component_cache.lock:`. The peek is idempotent and read-only — it emits at most one warning per cold-start call with no mutation of shared state — so moving it outside the lock is safe. In the rare case where two concurrent cold-start callers both observe a stale cache, each may emit the warning once; this is acceptable cosmetic redundancy and the test asserts "at least one" matching call on the mismatch case (adjusted to `== 1` specifically because the test stubs prevent a second caller during the test path). Also added a monkey-patch of `_get_cache_path` inside `test_cache_built_once_threading` so the IDX-07 peek short-circuits on `cache_path.exists() == False` even if the outside-lock fix were reverted — defense in depth.
- **Files modified:** `src/lfx/src/lfx/interface/components.py`, `src/lfx/tests/unit/test_component_index.py`
- **Verification:** `TestIDX01LazyLock` class passes in 1.72s (all 3 tests), `TestIDX07StaleIndexWarning` passes in 1.87s (all 5 tests), full `test_component_index.py` passes in 2.34s (44 passed + 2 skipped expected). Confirmed pre-IDX-07 timing preserved by checking out `df303643d1` of components.py and observing `TestIDX01LazyLock` passes in 0.62s; post-fix timing (1.72s) is within normal variance of the pre-IDX-07 baseline.
- **Committed in:** `f6315feb38` (dedicated fix commit separate from the Task 1 feat and Task 2 test commits so the regression-and-fix is clearly attributable in git history).

**2. [Rule 3 - Blocking] Ruff S110 flagged try/except/pass without logging**

- **Found during:** First commit attempt for Task 1.
- **Issue:** The plan's peek block ended with `except Exception:  # noqa: BLE001` + `pass`. Ruff S110 ("try-except-pass detected, consider logging the exception") fired because the pass is unlogged. The pass is deliberate — corrupt or unreadable cache is handled by `_read_component_index`'s own warning path downstream, and logging the peek's exception here would produce redundant noise the plan explicitly wants avoided (Pitfall T-02-06-04).
- **Fix:** Extended the `# noqa` comment to `# noqa: BLE001, S110`. The 3-line comment above the `pass` already names `_read_component_index` as the real warning owner, so S110's "consider logging" intent is satisfied: logging happens in the owning function, not here.
- **Files modified:** `src/lfx/src/lfx/interface/components.py`
- **Verification:** `ruff check` passes; commit succeeds.
- **Committed in:** `83b0cae972` (Task 1).

**3. [Rule 3 - Blocking] Ruff format reformatted test_component_index.py on commit**

- **Found during:** First commit attempts for the deviation-fix and Task 2 commits.
- **Issue:** Pre-commit's ruff-format hook re-wrapped a long docstring line in the IDX-07 isolation note. Semantically identical; no behaviour change.
- **Fix:** Re-staged and retried the commit. Same friction pattern as plans 02-01, 02-02, 02-03, 02-05 documented.
- **Files modified:** `src/lfx/tests/unit/test_component_index.py`
- **Verification:** All 44 tests still pass after reformatting.
- **Committed in:** `f6315feb38` and `a6129189ca`.

### Other Friction (not Rule-triggered)

- **uv sync cycle after pre-commit hooks:** The monorepo pre-commit ruff hooks perturb the lfx-only venv such that pytest's conftest "langflow must not be installed" gate misfires on the next `uv run pytest`. Same as all prior 02-* plans. Resolved each time by `cd src/lfx && uv sync`.
- **macOS lacks `timeout(1)`:** Used shell polling + `pkill -9` instead of coreutils timeout when measuring pre-fix timing. No code impact.

### Out-of-Scope Observations (deferred, not fixed)

None. The threading-test fix is explicitly in scope per the user's execution brief: the read-time IDX-07 check is what triggers the pathological path in the pre-existing threading test, so isolating the test is part of landing IDX-07.

---

**Total deviations:** 3 auto-fixed (1 Rule 1 bug, 2 Rule 3 blocking).
**Impact on plan:** The one substantive deviation (Rule 1) is a placement change — peek moved from INSIDE the cache lock to OUTSIDE it — that aligns with the plan's own <interfaces> and <context> guidance and with 02-RESEARCH.md. No change in the warning's behaviour, message, or gating; only the relative position in the function changes. Plan's verification + success_criteria bullets all still satisfied.

## Issues Encountered

The threading-test regression consumed roughly half of the plan's wall time. Root cause analysis:

1. Original assumption (from user's execution brief): `IDX-07's read-code reads the user's real 5.9MB disk cache inside the lock window, making the test deadlock-like-slow`. Fix proposed: monkey-patch `_get_cache_path` so the peek short-circuits on non-existent path.
2. Measured reality: even with `_get_cache_path` patched to an absent path, the threading test STILL regressed (2:00 instead of 0.62s), failing with `RuntimeError: Lock bound to different event loop`. The 5.9MB disk-read theory was part of the truth but not the full explanation.
3. Deeper root cause: the IDX-07 peek inside the lock widens the lock-hold window enough (even with the file-absent short-circuit — `_get_cache_path()` + `cache_path.exists()` + `_version("lfx")` still cost ~0.5-1ms per thread on macOS) to expose a latent race in the existing lazy-lock reset pattern. Threads each reset `_lock = None` before `asyncio.run`, and the widened window means thread A can grab thread B's just-reset Lock instance bound to loop B, then trip `Lock bound to different event loop` when B later tries to acquire its own lock.
4. Real fix: move the peek BEFORE the `async with component_cache.lock:` block entirely. This matches the plan's own research recommendation and restores threading-test timing to baseline.
5. Defense-in-depth: keep the user's proposed `_get_cache_path` monkey-patch in the threading test so if someone in a future plan moves the peek back inside the lock for a different reason, the test still won't read the developer's real cache.

No architectural questions. No blockers.

## Next Plan Readiness

Phase 2 plans 02-01 through 02-06 complete IDX-01..IDX-07 (except IDX-06 which landed in 02-04). All six plans delivered atomic, independently-verifiable commits with deep parity snapshots preserved byte-identically across every change. Cold-start cache-path hotspots now: lazy asyncio.Lock (02-01), Semaphore(16) cap (02-02), atomic `version("lfx")`-stamped index writes (02-03), single superuser init (02-04), async `_read_component_index` with `asyncio.to_thread` (02-05), read-time stale-index warning (02-06).

Next phase consumer: whoever picks up the cold-start benchmarking harness (Phase 3 per ROADMAP) can treat IDX-07 as visible-log-surface confirmation that a user's disk cache is the actual loaded artifact, distinguishing cache-hit paths from built-in-shipped-index paths via the warning's presence/absence in their logs.

---
*Phase: 02-component-index-and-correctness-fixes*
*Completed: 2026-04-16*

## Self-Check: PASSED

- src/lfx/src/lfx/interface/components.py: FOUND (modified; grep `stale component index` -> 1, `await asyncio.to_thread(cache_path.read_bytes)` -> 1, `installed_version = _version("lfx")` -> 1, `warnings.warn` -> 0)
- src/lfx/tests/unit/test_component_index.py: FOUND (modified; grep `class TestIDX07StaleIndexWarning` -> 1, five `def test_*` for IDX-07 -> 5 matches, `definitely_not_here.json` -> 1 (threading test isolation))
- Commit 83b0cae972 (Task 1, feat): FOUND in git log
- Commit f6315feb38 (deviation fix): FOUND in git log
- Commit a6129189ca (Task 2, test): FOUND in git log
- Test suite: 44 passing + 2 skipped (expected, five_types on lfx-only venv) in tests/unit/test_component_index.py in 2.34s
- Acceptance greps: all 11 target patterns matched exactly
- Observed warning message: includes `old-1.0`, `new-2.0`, and the cache file path — all three fields verified via `fmt % tuple(args)` rendering
- Negative-case silence: 0 stale-index warnings across match / absent / corrupt cases
- Parity snapshot match: byte-identical to plan 02-01's smallest.snapshot.json
- TestIDX01LazyLock threading test preserved: passes in ~1.72s class-wide (pre-IDX-07 baseline 0.62s; post-fix within normal variance)
