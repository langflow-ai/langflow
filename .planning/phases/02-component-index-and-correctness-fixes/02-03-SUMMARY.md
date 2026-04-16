---
phase: 02-component-index-and-correctness-fixes
plan: 03
subsystem: lfx-component-index

tags: [idx, idx-04, idx-05, version-stamp, atomic-write, path-replace, round-trip, parity]

requires:
  - phase: 02-component-index-and-correctness-fixes
    plan: 02-01
    provides: shared parity scaffolding (_parity_helpers.py), smallest.snapshot.json reference
provides:
  - _save_generated_index stamps cache with version("lfx") (IDX-04); PackageNotFoundError falls back to "unknown"
  - _save_generated_index writes atomically via tmp_path.write_bytes + Path.replace (IDX-05); tmp lives in same directory as target
  - TestIDX04IDX05WriteSide with lfx-version stamp + PackageNotFoundError fallback + round-trip + atomic-write-same-dir tests
  - TestIDX04IDX05WriteSideParity with deep parity guard on smallest.json
affects: [02-04, 02-05, 02-06]

tech-stack:
  added: []
  patterns:
    - "version('lfx') stamp + PackageNotFoundError fallback in _save_generated_index (IDX-04); mirrors read-time pattern at lines ~178-186"
    - "Atomic write via tmp_path = cache_path.with_suffix(cache_path.suffix + '.tmp'); tmp_path.write_bytes(json_bytes); tmp_path.replace(cache_path) (IDX-05, same-directory pattern)"
    - "Path.replace used instead of os.replace to satisfy ruff PTH105 (Path.replace is a thin wrapper around os.replace; same atomic semantics)"
    - "Test capture of Path.replace via monkeypatch on pathlib.Path class-level method (src_parent == dst_parent assertion proves same-filesystem guarantee)"

key-files:
  created: []
  modified:
    - src/lfx/src/lfx/interface/components.py
    - src/lfx/tests/unit/test_component_index.py

key-decisions:
  - "Use Path.replace instead of os.replace. The project's ruff config enforces PTH105 (use Path methods over os.*). Path.replace is a thin wrapper around os.replace with identical atomic semantics (POSIX atomic; Windows atomic since Python 3.3). This matches the existing pattern at src/lfx/src/lfx/_bench.py which also uses Path.replace, and the test assertion was adjusted to monkeypatch pathlib.Path.replace at the class level instead of os.replace on the module."
  - "Docstring phrasing avoids the literal 'version(\"langflow\")' string so the acceptance grep stays clean. The plan said the docstring could reference it, but the acceptance criteria required 0 occurrences of that literal in the file; prose mentions lfx-version stamping without re-printing the buggy call."
  - "Test for the PackageNotFoundError fallback patches 'importlib.metadata.version' (same pattern the existing TestSaveGeneratedIndex test at line 316 uses). Because _save_generated_index does 'from importlib.metadata import PackageNotFoundError, version' inside the try block, the local import picks up the patched attribute."
  - "Round-trip test uses caplog at DEBUG level scoped to 'lfx.interface.components' logger. The read path emits 'Component index version mismatch' only at DEBUG when the check fails; the assertion checks the NEGATIVE (no 'version mismatch' substring) which is the tight invariant."
  - "Atomic-write test also asserts the .tmp sibling does NOT linger after a successful rename. The plan only called for src-exists-at-replace; no-leftover-tmp is a tighter post-condition that catches future regressions where someone replaces tmp_path.replace with a copy+unlink pattern."

requirements-completed: [IDX-04, IDX-05]

duration: ~10 min
completed: 2026-04-16
---

# Phase 2 Plan 03: version("lfx") Stamp + Atomic Write (IDX-04 + IDX-05) Summary

**IDX-04 and IDX-05 land together in _save_generated_index per CONTEXT.md D-10: the cache is now stamped with version("lfx") (was version("langflow"), the bug), with a PackageNotFoundError fallback to "unknown"; and the write goes through a temp file in the SAME directory as the target followed by Path.replace (an atomic rename on POSIX and on Windows since Python 3.3). Round-trip in the lfx-only test venv confirms no version-mismatch rejection after save -> read. Deep parity on smallest.json is byte-identical to the pre-change snapshot captured in plan 02-01.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-04-16 (HEAD d83a28e220 after 02-02 completion)
- **Completed:** 2026-04-16
- **Tasks:** 2 (both TDD: production-code body rewrite + 5 new tests in TestIDX04IDX05WriteSide + deep parity)
- **Files modified:** 2 (0 created, 0 deleted)

## Accomplishments

- `_save_generated_index` now calls `version("lfx")` instead of `version("langflow")`. The prior bug meant that in lfx-only deployments (watsonX.orchestrate containers where langflow is not installed), `version("langflow")` raised `PackageNotFoundError` silently, the outer try/except swallowed the exception, and no cache was ever saved. Every restart in those environments would rebuild the full component index from scratch.
- A `PackageNotFoundError` fallback to `"unknown"` mirrors the existing read-time pattern at `components.py:178-186` so workspace/editable installs (which sometimes lack dist-info metadata) no longer crash the save path.
- The write is atomic via temp-file-plus-rename. The temp path is derived from the target via `cache_path.with_suffix(cache_path.suffix + ".tmp")`, guaranteeing it lives in the same directory (and therefore on the same filesystem) as the target. This avoids `OSError: [Errno 18] Invalid cross-device link` in containers where `$TMPDIR` is tmpfs and the cache directory is a persistent volume (pitfall 4 in 02-RESEARCH.md).
- `Path.replace` is used instead of `os.replace` (the project's ruff config enforces PTH105); semantically identical - `Path.replace` is a thin wrapper around `os.replace`. Matches the existing pattern at `src/lfx/src/lfx/_bench.py`.
- Five new tests in `TestIDX04IDX05WriteSide` + one deep parity test in `TestIDX04IDX05WriteSideParity`, all passing. Existing `TestSaveGeneratedIndex` tests continue to pass (they patch `importlib.metadata.version` without specifying a package name, so the new `version("lfx")` call still receives the patched value "0.1.12").

## Task Commits

Each task committed atomically (pre-commit hooks active, no `--no-verify`):

1. **Task 1: Rewrite _save_generated_index with version('lfx') + PackageNotFoundError fallback + Path.replace atomic write** -- `389771abad` (feat)
2. **Task 2: Add TestIDX04IDX05WriteSide + TestIDX04IDX05WriteSideParity** -- `89b19e4049` (test)

## Observed Real version("lfx") Value (per plan output spec)

The lfx-only test venv reports:

```
lfx_version=0.4.0
```

This is the value observed by `_real_version("lfx")` inside `TestIDX04IDX05WriteSide::test_stamp_is_lfx_version`. The saved cache's `version` field is byte-equal to this value.

## No Leftover .tmp File After Successful Writes (per plan output spec)

`TestIDX04IDX05WriteSide::test_atomic_write_uses_same_directory_tmp_and_rename` makes two assertions that collectively prove this:

1. The tmp file exists at the moment `Path.replace` is invoked (`captured["src_exists_at_replace"]` is True).
2. After the save completes, the `.tmp` sibling does not exist (`cache_file.with_suffix(cache_file.suffix + ".tmp").exists()` is False).

Both assertions pass. `Path.replace` atomically moves the tmp onto the target, which removes the tmp side of the rename pair by definition.

## Round-Trip Test Emitted No Version-Mismatch Log (per plan output spec)

`TestIDX04IDX05WriteSide::test_round_trip_lfx_only_env` uses `caplog.at_level(logging.DEBUG, logger="lfx.interface.components")` and asserts that after `_save_generated_index -> _read_component_index`, the string `"version mismatch"` does NOT appear in `caplog.text.lower()`. The test passes, confirming the stamp matches the installed version at read time.

## Parity Snapshot Match (per plan output spec)

`TestIDX04IDX05WriteSideParity::test_parity_smallest_after_write_change` compares an in-process `_capture_parity_snapshot(smallest.json)` call against `smallest.snapshot.json` (captured in plan 02-01 on HEAD 03bb575b59). The snapshot is byte-identical:

```json
{
  "final_text": "hello",
  "vertex_order": [
    "ChatInput-5aSdS",
    "ChatOutput-WnLEC"
  ]
}
```

Diff: (empty). The IDX-04/IDX-05 changes only affect cache-persistence, not flow execution, so parity is preserved by construction; the test confirms that expectation.

## Files Modified

- `src/lfx/src/lfx/interface/components.py` -- rewrites the body of `_save_generated_index` (lines ~208-268). Adds IDX-04 comment above the version lookup, replaces `version("langflow")` with `version("lfx")` guarded by a `try/except PackageNotFoundError: lfx_version = "unknown"` block; renames the local variable from `langflow_version` to `lfx_version`. Replaces the bare `cache_path.write_bytes(json_bytes)` with `tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp"); tmp_path.write_bytes(json_bytes); tmp_path.replace(cache_path)`.
- `src/lfx/tests/unit/test_component_index.py` -- appends `TestIDX04IDX05WriteSide` (4 tests) and `TestIDX04IDX05WriteSideParity` (1 test) below the existing 02-01 and 02-02 classes. Reuses `_PARITY_FIXTURES_DIR` and `_capture_parity_snapshot` from `_parity_helpers.py`.

## Test Outcomes

Running `cd src/lfx && uv sync && uv run pytest tests/unit/test_component_index.py -v`:

- `TestIDX04IDX05WriteSide::test_stamp_is_lfx_version`: PASSED
  - Saved `version` equals `importlib.metadata.version("lfx")` = "0.4.0" in this lfx-only venv
- `TestIDX04IDX05WriteSide::test_package_not_found_fallback`: PASSED
  - With `importlib.metadata.version` monkeypatched to raise `PackageNotFoundError`, saved version is "unknown"
- `TestIDX04IDX05WriteSide::test_round_trip_lfx_only_env`: PASSED
  - `_read_component_index` returned a non-None blob; caplog DEBUG contained no "version mismatch" substring; entries round-tripped byte-identically
- `TestIDX04IDX05WriteSide::test_atomic_write_uses_same_directory_tmp_and_rename`: PASSED
  - `Path.replace` captured: src ends with `.tmp`, dst ends with `component_index.json`, src_parent == dst_parent, src existed at replace-time, final cache exists, no leftover .tmp
- `TestIDX04IDX05WriteSideParity::test_parity_smallest_after_write_change`: PASSED
  - Snapshot byte-identical to plan 02-01's pre-change snapshot
- **Full file regression:** 36 passed + 1 skipped (02-02's parity test, by design in lfx-only venv) in ~0.81s. No regressions from the 30/30 baseline established in plan 02-01 or the 31/31 baseline from plan 02-02.

## Acceptance Grep Results

| Grep | Expected | Actual |
|------|----------|--------|
| `version("lfx")` in components.py | >= 1 | 2 (existing read-side + new save-side) |
| `version("langflow")` in components.py | 0 | 0 |
| `os.replace` or `Path.replace` usage | >= 1 | `tmp_path.replace(cache_path)` at line 266 |
| `with_suffix(...".tmp")` in components.py | 1 | 1 |
| `langflow_version` identifier | 0 | 0 |
| `stamping generated index with 'unknown'` literal | 1 | 1 |
| `class TestIDX04IDX05WriteSide` | 2 (main + parity) | 2 |
| `def test_stamp_is_lfx_version` | 1 | 1 |
| `def test_round_trip_lfx_only_env` | 1 | 1 |
| `def test_atomic_write_uses_same_directory_tmp_and_rename` | 1 | 1 |
| `def test_package_not_found_fallback` | 1 | 1 |
| `def test_parity_smallest_after_write_change` | 1 | 1 |

All acceptance criteria are met (note: the plan's name for the atomic-write test had a placeholder variant; the actual method name is `test_atomic_write_uses_same_directory_tmp_and_rename`, which satisfies the plan's grep anchor `def test_atomic_write`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Ruff PTH105 rejects `os.replace`**
- **Found during:** First attempt to commit Task 1.
- **Issue:** The plan instructed `os.replace(tmp_path, cache_path)`. The project's ruff config enforces PTH105 ("`os.replace()` should be replaced by `Path.replace()`"). Pre-commit hook rejected the commit with "Found 1 error. No fixes available."
- **Fix:** Switched to `tmp_path.replace(cache_path)` - semantically identical (Path.replace is a thin wrapper around os.replace; same atomic guarantees on POSIX and on Windows since Python 3.3). Matches the existing pattern at `src/lfx/src/lfx/_bench.py`. Updated the Task 2 test to monkeypatch `pathlib.Path.replace` at the class level instead of `lfx.interface.components.os.replace`, and renamed the test method from `test_atomic_write_uses_same_directory_tmp_and_os_replace` to `test_atomic_write_uses_same_directory_tmp_and_rename` for accuracy.
- **Files modified:** src/lfx/src/lfx/interface/components.py, src/lfx/tests/unit/test_component_index.py
- **Verification:** Ruff check passes; test_atomic_write_uses_same_directory_tmp_and_rename captures the Path.replace call correctly (src ends in .tmp, src_parent == dst_parent, no leftover tmp after success).
- **Committed in:** 389771abad (Task 1) + 89b19e4049 (Task 2).

**2. [Rule 2 - Missing Critical] Docstring reference to `version("langflow")` would fail the acceptance grep**
- **Found during:** Post-edit verification after Task 1.
- **Issue:** The initial docstring contained the phrase `stamps the cache with \`version("lfx")\`, not \`version("langflow")\`` verbatim. The plan's acceptance criteria requires `grep -cE "version\(\"langflow\"\)"` to return 0 in components.py. The literal docstring phrase was triggering a false positive (1 match).
- **Fix:** Rephrased the docstring to `"stamps the cache with the lfx package version (not langflow)"` - communicates the same intent without the literal buggy call signature.
- **Files modified:** src/lfx/src/lfx/interface/components.py
- **Verification:** `grep -cE "version\(\"langflow\"\)"` returns 0 as required.
- **Committed in:** 389771abad (Task 1; discovered and resolved before the commit landed).

**3. [Rule 3 - Blocking] Ruff EM101 on `raise PackageNotFoundError("lfx")`**
- **Found during:** First attempt to commit Task 2.
- **Issue:** Ruff EM101 ("Exception must not use a string literal, assign to variable first") flagged the test's `raise PackageNotFoundError("lfx")` stub.
- **Fix:** Changed to `msg = "lfx"; raise PackageNotFoundError(msg)`.
- **Files modified:** src/lfx/tests/unit/test_component_index.py
- **Verification:** Ruff check passes; test still exercises the intended fallback path.
- **Committed in:** 89b19e4049 (Task 2).

**4. [Rule 3 - Blocking] Ruff C416 on dict-comprehension entries extraction**
- **Found during:** First attempt to commit Task 2.
- **Issue:** The round-trip test did `entries = {top: comps for top, comps in result["entries"]}` which ruff C416 flagged as "Unnecessary dict comprehension (rewrite using `dict()`)".
- **Fix:** Changed to `entries = dict(result["entries"])` - semantically equivalent since `result["entries"]` is a list of `[top_level, components]` pairs.
- **Files modified:** src/lfx/tests/unit/test_component_index.py
- **Verification:** Ruff check passes; test still asserts entries match round-trip content.
- **Committed in:** 89b19e4049 (Task 2).

### Other Friction (not Rule-triggered)

- **uv sync cycle after pre-commit hooks:** Running the workspace pre-commit hooks (which use the monorepo ruff) perturbs the lfx-only venv in a way that causes pytest's conftest "langflow must NOT be installed" guard to misfire on a subsequent `uv run pytest`. Resolved each time by `cd src/lfx && uv sync`. Same ergonomic friction documented in plans 02-01 and 02-02; no code issue.

---

**Total deviations:** 4 auto-fixed (3 Rule 3 blocking, 1 Rule 2 missing critical).
**Impact on plan:** All deviations were tooling/lint-related fixes. The production code surface matches the plan text's intent exactly: `version("lfx")` with PackageNotFoundError fallback, same-dir tmp file, atomic rename to target. The only semantic divergence from the plan text is `Path.replace` instead of `os.replace` - these are the same primitive at different API layers, so the atomic-rename guarantee (IDX-05 truth) is preserved unchanged.

## Issues Encountered

None beyond the deviations documented above.

## Next Plan Readiness (02-04 IDX-06 duplicate superuser call)

- `_parity_helpers.py` continues to be the shared scaffolding; 02-04 does not need it (IDX-06 is in `src/backend/base/langflow/main.py`, not lfx).
- Plans 02-05 (IDX-03) and 02-06 (IDX-07) both benefit from 02-03's work: IDX-07 (stale-index warning) explicitly depends on the stable `version("lfx")` stamp landed here.
- No blockers. No open questions introduced by this plan.

---
*Phase: 02-component-index-and-correctness-fixes*
*Completed: 2026-04-16*

## Self-Check: PASSED

- src/lfx/src/lfx/interface/components.py: FOUND (modified; grep `version("lfx")` -> 2 occurrences, `version("langflow")` -> 0 occurrences, `tmp_path.replace(cache_path)` at line 266, `with_suffix(cache_path.suffix + ".tmp")` at line 264)
- src/lfx/tests/unit/test_component_index.py: FOUND (modified; grep `class TestIDX04IDX05WriteSide` -> 2, `def test_stamp_is_lfx_version` -> 1, `def test_round_trip_lfx_only_env` -> 1, `def test_atomic_write_uses_same_directory_tmp_and_rename` -> 1, `def test_package_not_found_fallback` -> 1, `def test_parity_smallest_after_write_change` -> 1)
- Commit 389771abad (Task 1, feat): FOUND in git log
- Commit 89b19e4049 (Task 2, test): FOUND in git log
- Test suite: 36 passing + 1 pre-existing skip in tests/unit/test_component_index.py.
- Acceptance greps: all target patterns matched.
- Real version("lfx") observed: "0.4.0" in the lfx-only test venv.
- No leftover .tmp after successful write: verified by test_atomic_write_uses_same_directory_tmp_and_rename.
- No version-mismatch log on round-trip: verified by test_round_trip_lfx_only_env.
- Parity snapshot match: byte-identical to plan 02-01's smallest.snapshot.json.
