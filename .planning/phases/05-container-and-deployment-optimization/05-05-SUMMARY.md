---
phase: 05-container-and-deployment-optimization
plan: "05"
subsystem: gunicorn/telemetry
tags: [gunicorn, post-fork, telemetry, httpx, fork-safety, cnt-04]
dependency_graph:
  requires: [05-01, 05-02, 05-03, 05-04]
  provides: [fork-safe-telemetry, post-fork-hook, cnt-04-audit]
  affects: [langflow.server, langflow.services.telemetry.service]
tech_stack:
  added: []
  patterns: [gunicorn post_fork hook, None-guard pattern for fork-unsafe resources]
key_files:
  created:
    - src/backend/tests/unit/services/telemetry/test_post_fork.py
  modified:
    - src/backend/base/langflow/server.py
    - src/backend/base/langflow/services/telemetry/service.py
decisions:
  - "post_fork hook imported get_telemetry_service lazily (inside function body) to avoid circular imports and keep module-import time clean"
  - "except Exception with S110 noqa: gunicorn hook must not crash on preload_app=False path where service not yet initialized"
  - "stop() guard uses 'if self.client is not None' rather than removing the aclose call: correct for paths where client was never reset but stop() is reached"
metrics:
  duration_minutes: 4
  completed_date: "2026-04-18"
  tasks_completed: 3
  files_changed: 3
---

# Phase 05 Plan 05: Fork Hazard Audit and Telemetry Fix Summary

**One-liner:** Gunicorn post_fork hook resets `TelemetryService.client` (httpx.AsyncClient) to None in each worker; `start()` reconstructs it inside the worker's event loop, eliminating the shared file-descriptor fork hazard (CNT-04).

## What Was Built

Three targeted changes to close the one real fork hazard found by the Phase 5 audit:

### Task 1: `_langflow_post_fork` hook in server.py (commit `2f13eca7c8`)

- `LangflowApplication.load_config` now calls `self.cfg.set("post_fork", _langflow_post_fork)` after the existing option loop.
- `_langflow_post_fork(server, worker)` is a module-level synchronous function that lazy-imports `get_telemetry_service` and sets `tel.client = None`.
- All exceptions swallowed (`BLE001`, `S110`) so the hook never crashes gunicorn when the service manager is not yet initialized (preload_app=False path).

### Task 2: None-guards in TelemetryService (commit `34c47e68af`)

- `start()`: added `if self.client is None: self.client = httpx.AsyncClient(timeout=10.0)` before the task creation block — reconstructs the client inside the worker's event loop after post_fork reset.
- `stop()`: wrapped `await self.client.aclose()` with `if self.client is not None:` — prevents AttributeError on paths where the client was reset but start() short-circuited (do_not_track, or post_fork without a subsequent start call).
- `__init__` left unchanged: client still constructed in master process; post_fork then reset; start() in worker reconstructs.

### Task 3: Unit tests (commit `fd669f1e72`)

- `test_post_fork_resets_telemetry_client`: patches `langflow.services.deps.get_telemetry_service` to return a real TelemetryService fixture, calls `_langflow_post_fork(None, None)`, asserts `client is None`.
- `test_start_reconstructs_client_when_none`: sets `tel.client = None` directly, calls `tel.start()` inside an asyncio event loop, asserts client is reconstructed, then calls `tel.stop()` for cleanup.
- Both tests use real `TelemetryService` and `SettingsService` instances — no mocking of subjects under test (AGENTS.md compliance).

## D-07 Audit Evidence

This table is the D-07 gate. Plan 05-06 proceeds with the default flip ONLY if all six non-Telemetry hazards remain SAFE and the Telemetry fix is verified by passing tests.

| Hazard | Status | Plan 05-05 Action | Evidence |
|--------|--------|-------------------|----------|
| SQLAlchemy engine | SAFE | none | RESEARCH.md section "Fork Hazard Audit -> 1. SQLAlchemy"; DatabaseService.__init__ runs in initialize_services() inside lifespan (post-fork) |
| asyncio locks (ComponentCache) | SAFE | none | RESEARCH.md section "2. asyncio locks"; IDX-01 lazy @property pattern, Phase 2 |
| ComponentCache.all_types_dict | SAFE | none | RESEARCH.md section "3. ComponentCache state"; populated in lifespan wave-2 gather, per-worker |
| TelemetryService.client (httpx) | HAZARD -> FIXED | post_fork hook + start/stop guards + test | This plan; Tasks 1-3; commits 2f13eca7c8, 34c47e68af, fd669f1e72 |
| Redis connection pool | SAFE | none | RESEARCH.md section "4. Redis/httpx"; RedisCache lazy + conditional via LANGFLOW_CACHE_TYPE |
| asyncio.create_task at import | SAFE | none | RESEARCH.md section "5. Background tasks"; all create_task calls in lifespan body or service.start() |
| File descriptors at import | SAFE | none | RESEARCH.md section "6. File descriptors"; no module-level open() calls in langflow/main.py |

**Verdict:** All six audited hazards from RESEARCH.md "Fork Hazard Audit (D-05)" are either SAFE by construction or FIXED. Plan 05-06 may proceed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added `# noqa: S110` to suppress ruff S110 on try-except-pass**
- **Found during:** Task 1 commit (pre-commit hook)
- **Issue:** Ruff S110 fires on `try`-`except`-`pass` without a noqa suppressor; the plan specified `# noqa: BLE001` only
- **Fix:** Changed to `# noqa: BLE001, S110` — the silence is intentional per PATTERNS.md (hook must not crash gunicorn)
- **Files modified:** `src/backend/base/langflow/server.py`
- **Commit:** `2f13eca7c8` (included in same commit after retry)

**2. [Rule 1 - Bug] Ruff I001 import ordering in test file**
- **Found during:** Task 3 overall verification
- **Issue:** `from __future__ import annotations` placed above stdlib imports triggered I001
- **Fix:** `uv run ruff check --fix` auto-sorted the import block
- **Files modified:** `src/backend/tests/unit/services/telemetry/test_post_fork.py`
- **Commit:** `fd669f1e72`

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

- `src/backend/base/langflow/server.py` — exists, contains `_langflow_post_fork` and `self.cfg.set("post_fork", ...)` ✓
- `src/backend/base/langflow/services/telemetry/service.py` — exists, contains both guards ✓
- `src/backend/tests/unit/services/telemetry/test_post_fork.py` — exists, both tests pass ✓
- Commits: `2f13eca7c8`, `34c47e68af`, `fd669f1e72` — all present in git log ✓
- No speculative code added for the six SAFE hazards ✓
