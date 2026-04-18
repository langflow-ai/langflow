---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Phase 05 Plan 03 complete; commits 197c421107/ec4125a5c6 (cold-start guide + sidebar/cross-links).
last_updated: "2026-04-18T15:10:00.000Z"
last_activity: 2026-04-18 -- Phase 05 Plan 03 complete
progress:
  total_phases: 7
  completed_phases: 3
  total_plans: 36
  completed_plans: 21
  percent: 58
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-16)

**Core value:** Faster cold start for `lfx run` on containerized/serverless deployments without breaking flow file format, Python API surface, or runtime behavior parity.
**Current focus:** Phase 05 — container-and-deployment-optimization

## Current Position

Phase: 05 (container-and-deployment-optimization) — EXECUTING
Plan: 4 of 6
Status: Executing Phase 05
Last activity: 2026-04-18 -- Phase 05 Plan 03 complete (cold-start deployment guide CNT-03)

Phase 4 outcome: [##########] 100% (5/5 plans executed)

## Performance Metrics

**Velocity:**

- Total plans completed: 17
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 2 | 6 | - | - |
| 4 | 5 | 59m | 11.8m |

**Recent Trend:**

- Last 5 plans: 04-05 (29m, 2 tasks, 5 files), 04-04 (5m, 2 tasks, 2 files), 04-03 (9m, 2 tasks, 3 files), 04-02 (6m, 2 tasks, 2 files), 04-01 (10m, 3 tasks, 12 files)
- Trend: -

*Updated after each plan completion*
| Phase 02 P02 | 8 | 2 tasks | 4 files |
| Phase 04 P01 | 10 | 3 tasks | 13 files |
| Phase 04 P02 | 6 | 2 tasks | 2 files |
| Phase 04 P03 | 9 | 2 tasks | 3 files |
| Phase 04 P04 | 5 | 2 tasks | 2 files |
| Phase 04 P05 | 29 | 2 tasks | 5 files |
| Phase 05 P01 | 1 | 2 tasks | 1 file |
| Phase 05 P02 | 3 | 4 tasks | 4 files |
| Phase 05 P03 | 8 | 2 tasks | 4 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Phase mapping confirmed 37/37 requirements; pre-mapped categories unchanged.
- [Roadmap]: langchain_core work (IMP-07, IMP-08) is the highest-complexity item in Phase 3; sub-task by module group (agents, schema, serialization) as separate independently deployable units.
- [Roadmap]: CNT-04 (LANGFLOW_GUNICORN_PRELOAD default) is conditional on verifying `after_fork` + `engine.dispose()` in `langflow/services/database/`; stays opt-in otherwise.
- [Roadmap]: SVC-03 (MCP sleep replacement) is conditional on SVC-01 (starter-project hash gate) being stable.
- [01-06]: thresholds.json shipped as Path B sentinel (mean_ms=0) because plan 05's baseline was macOS+podman non-authoritative (D-10/Pitfall 3). First workflow_dispatch with mode=snapshot on release-1.9.0 overwrites the sentinel with authoritative Linux numbers.
- [01-06]: cold-start-benchmark.yml uses v6 action pins matching repo-wide standard (checkout, setup-python, setup-uv, upload-artifact).
- [01-06]: benchmarks:override label records to workflow summary for audit but does NOT bypass failure; branch-protection governs merge-on-red per D-16.
- [02-01]: IDX-01 concurrency tests stub _load_components_dynamically instead of wrapping the real loader. Real loader enumerates every lfx.components subpackage and transitively imports optional integrations (toolguard) not present in the lfx-only test venv. D-08 permits stubbing since the contract is counter-once-under-race.
- [02-01]: Threading test resets ComponentCache._lock per thread inside the worker body. Without this, thread 2 inherits thread 1's asyncio.Lock bound to a different event loop and RuntimeError fires. Matches research doc T-02-01-03 accept disposition (each thread creates its own Lock on first access in its own loop).
- [02-01]: Graph.async_start inputs must be InputValueRequest (not list[dict]). Graph.astep calls inputs.model_dump() and falls through to {} for non-model inputs; list[dict] produces empty-string ChatInput propagation.
- [02-01]: _install_mock_llm returns False gracefully when langchain_openai is absent. smallest.json uses no LLM, so lfx-only venv is unaffected; later LLM-bearing fixtures rely on this in environments where langchain_openai IS installed.
- [Phase 02-02]: IDX-02 test uses monkey-patched pkgutil.walk_packages + _process_single_module to exercise real semaphore/bounded helper/gather/merge loop without pulling toolguard/langchain_openai. 200 synthetic modules (> 16 semaphore cap) preserves pitfall 9 coverage.
- [Phase 02-02]: test_parity_five_types skips gracefully when langchain_openai is absent (matches 02-01 precedent). Snapshot preserved for runs in venvs that have it.
- [Phase 04-01]: Task 3 test drives run_starter_projects_hash_gate directly (approach (b)) rather than re-implementing the gate in-test; production and test share the compute/read/compare/sync/write sequence. Only FileLock wrapping is external.
- [Phase 04-01]: main.py inlines the 4 helper calls (compute/read/force/write) rather than delegating to run_starter_projects_hash_gate, because Task 2's acceptance criteria grep for each helper name in main.py. The wrapper remains exported for test + future callers.
- [Phase 04-01]: importlib.metadata.version aliased to version_metadata in main.py to avoid shadowing the get_lifespan(*, version=None) kwarg.
- [Phase 04-01]: Hash file format is two-line plaintext (64-hex-sha on line 1, '# version: <lfx>' on line 2); parser skips blank/'#'-prefixed lines.
- [Phase 04-02]: D-09 review-table column widths trimmed (in-memory -> in-mem, files -> fs, etc.) to fit within 120-char ruff E501 limit while preserving all greppable marker strings verbatim.
- [Phase 04-02]: test_svc02_dependency_review.py intentionally does NOT import ast_helpers.find_calls_to; the gather-AST cross-check is plan 04-03's scope. Keeps the two plans' tests independent.
- [Phase 04-02]: _extract_table_rows uses 'first-column ends with _' heuristic to stitch multi-line cells (load_bundles_with_error_ + handling). Blank-first-column wrap rows skipped when no pending continuation exists.
- [Phase 04-02]: SVC-04 remains Partial at requirements-tracking level; 04-02 delivers the D-09/D-10 anchor + parity-guard test, 04-03 adds the gather-vs-rows cross-check, 04-05 closes SVC-04 with the restart-parity integration test.
- [Phase 04-03]: setup_llm_caching (sync) wrapped in asyncio.to_thread inside the wave-1 gather so the worker thread runs it in parallel with copy_profile_pictures without blocking the event loop. Negligible wall-clock today (cache-assignment is ~1ms) but future-proofs against accidental I/O growth in setup_llm_caching.
- [Phase 04-03]: all_types_dict is None -> raise RuntimeError guard. _safe_step swallows exceptions and returns None; bundles_result being None is tolerable (empty temp_dirs) but all_types_dict None is not (starter-project block cannot proceed). Preserves today's "lifespan cannot continue on types-cache failure" semantics.
- [Phase 04-03]: Wave summary log lines say "Wave N (...) done" NOT "SVC-02 wave N done" because 04-02's test asserts "SVC-02 wave N" occurs exactly once in source (the comment marker). Reworded log avoids a second occurrence regressing the 04-02 test.
- [Phase 04-03]: ast_helpers.extract_gather_task_names extended to unwrap asyncio.to_thread(fn) one level deeper. Required for wave 1 where setup_llm_caching is wrapped in to_thread; without the extension the extractor returns "to_thread" instead of "setup_llm_caching" and the D-06 set-equality assertion fails.
- [Phase 04-03]: Startup gathers distinguished from shutdown/cleanup gathers by "extract_gather_task_names returns a non-empty list". Startup gathers wrap each task in _safe_step (yields 1+ names); shutdown gathers pass bare task splats (yields 0 names). Filter is simpler than scanning for the _safe_step marker explicitly.
- [Phase 04-04]: starter_projects_ready_event constructed inside lifespan (D-12) to avoid module-level event-loop binding (Pitfall 1, same root cause as IDX-01). Test 4 asserts zero module-level Assigns of the Event name and >=1 Assign inside async def lifespan.
- [Phase 04-04]: Event .set() placed on the success path of the with-lock body (single unconditional line after the if/else hash gate, inside with lock:), NOT in a finally: clause. Research Open Question 2 rationale -- setting in finally would mask genuine starter-project failures. Consumer's 60s bounded wait is the correct signal for lock-contended/failed cases.
- [Phase 04-04]: Consumer timeout kept at 60.0s (D-13 default) not adjusted. 10x headroom over observed starter-project wall-clock; degraded-mode fallback (MCP proceeds on timeout) is non-fatal. 04-05 benchmark evidence will surface if tuning is needed.
- [Phase 04-04]: delayed_init_mcp_servers kept inline inside lifespan() for closure capture of starter_projects_ready_event (Pitfall 6). Test 5 asserts exactly one AsyncFunctionDef with that name inside lifespan and zero at module level.
- [Phase 04-04]: Comment wording avoids literal "asyncio.sleep(10.0)" string (says "previously hardcoded 10-second coordination sleep") so grep-based acceptance criteria stay clean. AST absence check (find_sleep_with_value(tree, 10.0) == []) is the authoritative D-07 guarantee.
- [Phase 04-04]: Cross-test-loop guard implemented as two near-identical race tests (test_event_race_first_run + test_event_race_second_run) running in the same pytest session. Surfaces any regression to module-level asyncio.Event that would bind to the first test's loop and fail the second.
- [Phase 04-05]: thresholds.json sentinel row for langflow_run_no_change_restart (mean_ms=0) per Phase 3 D-09 rule carry-forward. Authoritative numbers land via run-benchmark-snapshot CI label, never from a developer macOS machine.
- [Phase 04-05]: Two-boot supervisor self-seeds LANGFLOW_CONFIG_DIR + LANGFLOW_DATABASE_URL under tempdir if caller has not exported them. Makes the supervisor self-contained (local smoke-test works without wiring) and CI-override-friendly (workflow still owns the env).
- [Phase 04-05]: New scenario inherits langflow_run_http_ready's flaky-scenario treatment (5-min timeout, continue-on-error=true, Post-regression-comment-step excludes both) until the structlog marker fix lands in Phase 4/5. cold-start-benchmark.yml aggregate step's tracked list extended so snapshot mode writes a row for the new scenario (sentinel if hyperfine JSON missing).
- [Phase 04-05]: SVC-04 parity Test 6 uses AST function-name list equality against a hardcoded expected list, not a byte-level sha256 snapshot. Structurally meaningful invariant (whitespace/comment changes should NOT fail the parity check); Test 7 complements with a signature-level guard on initialize_services(*, fix_migration: bool = False).
- [Phase 04-05]: Init-order error marker set spans SQLite ("no such table"), MySQL/Postgres ("table doesn't exist"), sqlalchemy ("OperationalError"), and ServiceManager ("service not initialized"). caplog at logging.ERROR captures init-order violations without noise from INFO/WARNING startup chatter.
- [Phase 05-01]: D-02 unblocked: pydantic-core 2.41.5 ships cp313 musllinux wheels (aarch64, armv7l, x86_64) confirmed in uv.lock lines 11129-11131; Python 3.13 bump applied to Dockerfile builder + runtime stages.
- [Phase 05-01]: --no-install-project on first uv sync ensures deps layer cache-hits on source-only changes (CNT-02); second sync (--no-editable) installs the lfx package itself after source COPY.
- [Phase 05-02]: lfx_reference_image uses hyperfine wrapping (self_measuring=False): lfx run exits after flow completion (no port bound); TCP readiness probe / supervisor not applicable. Resolves RESEARCH.md Open Question 2.
- [Phase 05-02]: Sentinel threshold mean_ms=0 for lfx_reference_image per D-15; authoritative numbers land via run-benchmark-snapshot CI label on Phase 5 PR.
- [Phase 05-02]: captures_pyinstrument=False and captures_importtime=False for lfx_reference_image: measures deployed image as black box; harness tooling not present in lfx reference image.
- [Phase 05-03]: Cross-platform requirements generation documented as `uv pip compile --python-platform linux --python-version 3.13` (not `uv export`); verified against uv 0.9.11 live — `uv export` lacks these flags entirely.
- [Phase 05-03]: deployment-prod-best-practices.mdx cross-link added to See also section (end of file) rather than mid-section insertion to avoid disrupting existing content.

### Pending Todos

None yet.

### Blockers/Concerns

- **Open question for Phase 1:** Is dep-install or import time the dominant cold-start cost? Phase 1 measurement answers this; no code changes should be selected before the answer is known.
- ~~**Open question for Phase 2:** Confirm minimum deployed Python version to determine whether asyncio.Lock lazy-property fix is warning-severity or crash-severity in production.~~ RESOLVED 2026-04-16 (PROJECT.md key decision): 3.13/3.14 -- crash-severity, IDX-01 landed 2026-04-16 in plan 02-01 (commits e8ebd83fb4 + 40223ac991).
- **Open question for Phase 4:** Confirm whether production `lfx run` uses `serve_app.py` or `run_flow()` — affects Phase 4 priority.
- **Open question for Phase 5:** Confirm watsonX.orchestrate base Docker image (assumed `python:3.12-slim`; may be `ubi9`).

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| FUT-01 | Installed-deps detection fast path | Conditional on Phase 1 confirming dep-install is on critical path | Roadmap |
| FUT-02 | Prebuilt image variants | v2 scope | Roadmap |
| FUT-03 | Persistent cross-container dep cache | v2 scope | Roadmap |
| FUT-04 | `lfx warm` / `lfx prebuild` CLI subcommand | v2 scope (improvements over new features) | Roadmap |

## Session Continuity

Last session: 2026-04-18T15:10:00.000Z
Stopped at: Phase 05 Plan 03 complete; cold-start deployment guide created (2 commits: 197c421107, ec4125a5c6). CNT-03 satisfied. uv export flag discrepancy found and corrected (uv pip compile used instead).
Resume file: None.
Next step: Execute Phase 05 Plan 04.

### Phase 3 close notes

- **Commits:** 288aa05814, 3490da3009, 3c279d56e1, 62bc53e642, fccce205c2, 01954dbe99, 943012d72a
- **Graph cold-import wall-clock:** 1440 ms (pre-Phase-3) → 356 ms median (−75%)
- **Deferred plans (Langflow-run scope; user deprioritized):** 03-03 (IMP-04 OTel/Prometheus), 03-04 (IMP-05 voice_mode), 03-05 (IMP-06 langflow/__init__.py compat), 03-06 (IMP-01 langflow/__main__.py)
- **Absence verified:** pandas, numpy, PIL, langchain_core, langchain_classic, langchain_text_splitters, networkx — all 0 modules on Graph path
- **Remaining eager roots on Graph path:** pydantic (68), rich (52), fastapi (38 — blocked by HTTPException base class in base_component.py). Not in Phase 3 scope.
- **thresholds.json CI snapshot:** pending — user must apply `run-benchmark-snapshot` label to the Phase 3 PR when opened
