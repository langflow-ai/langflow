---
phase: 05-container-and-deployment-optimization
plan: "06"
subsystem: gunicorn/docs
tags: [gunicorn, preload-app, default-flip, migration-note, cnt-04]
dependency_graph:
  requires: [05-03, 05-05]
  provides: [cnt-04-complete, gunicorn-preload-default-true]
  affects: [langflow.__main__, docs/deployment-cold-start.mdx]
tech_stack:
  added: []
  patterns: [conditional-default-flip, D-07-gate-pattern]
key_files:
  created: []
  modified:
    - src/backend/base/langflow/__main__.py
    - docs/docs/Deployment/deployment-cold-start.mdx
decisions:
  - "D-07 gate passed: all 6 fork hazards SAFE or FIXED per 05-05-SUMMARY audit table; test_post_fork.py green"
  - "Path A docs written: default now true, opt-out via LANGFLOW_GUNICORN_PRELOAD=false, 7-hazard audit summary, when-to-stay-opted-out guidance"
metrics:
  duration_minutes: 4
  completed_date: "2026-04-18"
  tasks_completed: 2
  files_changed: 2
---

# Phase 05 Plan 06: Gunicorn Preload Default Flip Summary

**One-liner:** LANGFLOW_GUNICORN_PRELOAD default flipped from false to true after D-07 gate passed (all 7 fork hazards safe or fixed by Plan 05-05); deployment guide finalized with audit outcome and opt-out instructions.

## What Was Built

### Task 1: D-07 gate evaluation and default flip (commit `b3d9b49118`)

**Gate evaluation — PASS:**

| Gate condition | Result |
|---|---|
| (a) All 6 non-Telemetry hazards SAFE with evidence pointers in 05-05-SUMMARY | PASS |
| (b) TelemetryService.client row shows HAZARD -> FIXED with post_fork + start/stop guards | PASS |
| (c) `uv run pytest src/backend/tests/unit/services/telemetry/test_post_fork.py -x` exits 0 | PASS (2 passed in 0.39s) |

**Default flip applied:**

```diff
-                "preload_app": os.environ.get("LANGFLOW_GUNICORN_PRELOAD", "false").lower() == "true",
+                "preload_app": os.environ.get("LANGFLOW_GUNICORN_PRELOAD", "true").lower() == "true",
```

Only the default string literal changed. Env-var name preserved; `.lower() == "true"` coercion preserved; options dict unchanged otherwise.

### Task 2: Deployment guide finalization — Path A (commit `faf667896f`)

Replaced the Plan 05-03 placeholder blockquote and `TODO(plan-05-06)` comment in `docs/docs/Deployment/deployment-cold-start.mdx` with Path A content (gate-passed text):

- **What changed:** 2 lines removed (placeholder + TODO), 36 lines added (final section body)
- **Content:** default description, 7-hazard audit summary table narrative, opt-out instructions (`LANGFLOW_GUNICORN_PRELOAD=false`), "when to stay opted out" guidance for single-worker/custom-services/conflicting-worker-class cases
- **No watsonX.orchestrate mention** (D-10 preserved)
- **H2 heading preserved** (`## LANGFLOW_GUNICORN_PRELOAD migration notes`)

## D-07 Gate Path Taken: PASS

Plan 05-05's SUMMARY.md D-07 Audit Evidence table shows:
- 6 hazards SAFE by construction (SQLAlchemy, asyncio locks, ComponentCache, Redis, background tasks, file descriptors)
- 1 hazard FIXED: TelemetryService.client via post_fork hook + None-guards (commits 2f13eca7c8, 34c47e68af)

Post-flip regression check: `test_post_fork.py` re-run after default flip — 2 passed, no regressions.

## Deviations from Plan

None — plan executed exactly as written. Gate evaluation, one-line edit, and docs section swap matched the plan specification.

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes. The default change affects gunicorn startup behavior, which was the explicit intent of CNT-04.

## Self-Check: PASSED

- `src/backend/base/langflow/__main__.py` contains `LANGFLOW_GUNICORN_PRELOAD", "true"` — confirmed
- `docs/docs/Deployment/deployment-cold-start.mdx` heading preserved, no TODO, Path A text present — confirmed
- Commit `b3d9b49118` exists in git log — confirmed
- Commit `faf667896f` exists in git log — confirmed
- `test_post_fork.py` passed post-flip (2 passed) — confirmed
- No other files modified — confirmed (git diff shows exactly 2 files)
