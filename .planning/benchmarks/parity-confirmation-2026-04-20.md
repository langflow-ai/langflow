# Cold-Start Parity Confirmation - 2026-04-20

Every code change in the cold-start improvements milestone that touched the services layer or the component index is listed below, with a reference to the governing parity test file + function that locks the behavior invariant. No new test runs are commissioned by this document; all evidence is drawn from tests landed during Phases 2 through 5.5. The umbrella CI run that exercised all of these tests together is cited once in the "Umbrella CI run" section below.

**Scope (per CONTEXT.md D-07):** Phase 2 IDX-01 through IDX-07, Phase 3 IMP-02 + IMP-07 (Graph hot path deferrals), Phase 4 SVC-01 through SVC-04, Phase 5.5 IDX-08 + IDX-09.

**Out of scope:** Phase 5 Dockerfile and deployment-docs changes (CNT-01 through CNT-04). These do not touch services-layer or component-index code; they are container + deployment layer and do not require parity evidence in this document.

## Phase 2 - Component Index Correctness Fixes

| Phase | Req | Area | File(s) touched | Governing test | Assertion |
|-------|-----|------|-----------------|----------------|-----------|
| 2 | IDX-01 | Lazy asyncio.Lock property on ComponentCache | `src/lfx/src/lfx/interface/components.py` | `src/lfx/tests/unit/test_component_index.py::TestIDX01LazyLock::test_cache_built_once_asyncio`, `::test_cache_built_once_threading`, `::test_parity_smallest` | 10-task async race builds cache exactly once; per-thread lock creation raises no RuntimeError; smallest.json parity snapshot byte-identical. |
| 2 | IDX-02 | `_load_components_dynamically` asyncio.Semaphore(16) cap | `src/lfx/src/lfx/interface/components.py` | `test_component_index.py::TestIDX02SemaphoreCap::test_component_count_stable_across_rebuilds`, `::test_parity_five_types` | 200 synthetic modules through Semaphore(16) produce stable component counts across 5 rebuilds; five_types.json parity snapshot preserved. |
| 2 | IDX-03 | Async `_read_component_index` + `asyncio.to_thread` read_bytes | `src/lfx/src/lfx/interface/components.py` | `test_component_index.py::TestIDX03ReadPath::test_is_coroutine_function`, `::test_read_does_not_block_event_loop`, `::test_parity_smallest_after_async_refactor`, `::test_parity_five_types_after_async_refactor` | Reader is a coroutine function; ticker loop confirms no event-loop block during read; parity snapshots preserved on both fixtures. |
| 2 | IDX-04 | `version("lfx")` cache version stamp (not `version("langflow")`) | `src/lfx/src/lfx/interface/components.py` | `test_component_index.py::TestIDX04IDX05WriteSide::test_stamp_is_lfx_version`, `::test_package_not_found_fallback` | Written cache blob stamps lfx version; PackageNotFoundError falls through cleanly without crashing the writer. |
| 2 | IDX-05 | Atomic write via same-directory tmp file + `os.replace` | `src/lfx/src/lfx/interface/components.py` | `test_component_index.py::TestIDX04IDX05WriteSide::test_round_trip_lfx_only_env`, `::test_atomic_write_uses_same_directory_tmp_and_rename` | Save-then-read round-trip in lfx-only venv produces no version-mismatch log; writer uses same-dir tmp file + os.replace. |
| 2 | IDX-04 + IDX-05 parity | Combined write-side parity guard | `src/lfx/src/lfx/interface/components.py` | `test_component_index.py::TestIDX04IDX05WriteSideParity::test_parity_smallest_after_write_change` | Flow output unchanged after write-path stamping + atomic-replace edits. |
| 2 | IDX-06 | Duplicate `initialize_auto_login_default_superuser` unconditional call removed | `src/backend/base/langflow/main.py` (lines 194-196 deleted) | `src/backend/tests/unit/test_main_superuser_init.py::test_main_py_has_exactly_one_superuser_init_call`, `::test_main_py_call_is_inside_auto_login_branch`, `::test_superuser_init_called_once_with_auto_login_true`, `::test_superuser_init_zero_calls_with_auto_login_false` | Source-level: exactly one `await initialize_auto_login_default_superuser()` remains, inside the AUTO_LOGIN branch. Behavioral: AUTO_LOGIN=True fires once; AUTO_LOGIN=False fires zero times. |
| 2 | IDX-07 | Dev-mode stale-index warning on version mismatch | `src/lfx/src/lfx/interface/components.py` | `test_component_index.py::TestIDX07StaleIndexWarning::test_warning_fires_on_version_mismatch`, `::test_warning_silent_on_version_match`, `::test_warning_silent_when_cache_file_absent`, `::test_warning_silent_on_corrupt_cache`, `::test_parity_smallest_after_idx07` | Four gating cases: fires on mismatch, silent on match / absent / corrupt. Parity snapshot preserved. |

## Phase 3 - Import-Time Optimization (Graph hot path, services-adjacent scope)

| Phase | Req | Area | File(s) touched | Governing test | Assertion |
|-------|-----|------|-----------------|----------------|-----------|
| 3 | IMP-02 | pandas / numpy deferral on Graph hot path | 7 files under `src/lfx/src/lfx/` (commits 288aa05814, 3490da3009, plus Phase 3 close notes cluster) | `src/lfx/tests/unit/test_import_absence.py::TestIMP02NoPandas` | `python -X importtime -c 'import lfx'` trace does not show pandas or numpy. Graph cold-import 1440ms to 356ms (-75%) verified by the harness. |
| 3 | IMP-07 | `lfx/field_typing/constants.py` PEP 562 `__getattr__` + `_LAZY` map for 11 langchain_core symbols | `src/lfx/src/lfx/field_typing/constants.py`, `__init__.py` | `src/lfx/tests/unit/test_import_absence.py::TestIMP07FieldTyping` + `src/lfx/tests/unit/test_import_graph.py` (subprocess + sys.modules mechanism) | `import lfx.field_typing` does not eager-import langchain_core or langchain_classic. Windows c10.dll OSError fallback preserved. |

Note: the ROADMAP-unchecked Phase 3 plans (03-02 PIL, 03-07 full PEP 562, 03-08a through 03-08e, 03-09) are reconciled in `post-2026-04-20.md` under "Phase 3 ROADMAP reconciliation" per D-17. Their absence-verified status (STATE.md "Phase 3 close notes") is cross-referenced there. This parity doc lists only the two IMP requirements with landed tests per D-07.

## Phase 4 - Service Init Restructuring

| Phase | Req | Area | File(s) touched | Governing test | Assertion |
|-------|-----|------|-----------------|----------------|-----------|
| 4 | SVC-01 | Starter-project content-hash gate | `src/backend/base/langflow/main.py`, `src/backend/base/langflow/initial_setup/starter_project_hash.py` | `src/backend/tests/phase_04_service_init_parity/test_svc01_starter_hash_cache.py::test_svc01_second_invocation_skips_sync_and_is_fast`, `::test_svc01_mutated_starter_triggers_full_resync`, `::test_svc01_force_resync_env_var_bypasses_hash_match`, `::test_svc01_corrupt_hash_file_falls_through_to_resync`, `::test_svc01_missing_hash_file_falls_through_and_writes` | Hash-match skip; content mutation triggers resync; force-resync env var bypasses match; corrupt / missing hash falls through cleanly. |
| 4 | SVC-02 | `asyncio.gather` wave-1 and wave-2 independent lifespan tasks + dependency-review comment blocks | `src/backend/base/langflow/main.py` | `src/backend/tests/phase_04_service_init_parity/test_svc02_dependency_review.py::test_wave_1_review_block_present`, `::test_wave_2_review_block_present`, `::test_table_rows_match_expected_sets`, `::test_initialize_services_parity_guardrail`; `test_svc02_gather_structure.py::test_lifespan_has_two_startup_gathers`, `::test_gather_wave_1_task_set_matches_expected`, `::test_gather_wave_2_task_set_matches_expected`, `::test_every_gather_task_has_review_row`, `::test_no_task_is_both_sequential_and_in_a_gather`, `::test_initialize_services_parity_guardrail` | Review comment blocks D-09 structure; gather task sets match expected wave-1 + wave-2 membership; no task is both sequential and gathered; `initialize_services()` AST unchanged. |
| 4 | SVC-03 | MCP startup `asyncio.Event` replacing `asyncio.sleep(10.0)` | `src/backend/base/langflow/main.py` | `src/backend/tests/phase_04_service_init_parity/test_svc03_mcp_event_readiness.py::test_no_asyncio_sleep_10_in_mcp_init_path`, `::test_asyncio_sleep_5_retry_still_present`, `::test_event_set_inside_filelock_not_in_finally`, `::test_event_constructed_inside_lifespan_not_module_level`, `::test_delayed_init_mcp_servers_remains_inline_inside_lifespan`, `::test_consumer_uses_wait_for_with_60s_timeout`, `::test_event_race_first_run`, `::test_event_race_second_run` | `asyncio.sleep(10.0)` is gone; 5s retry preserved (D-14); Event constructed inside lifespan (not module-level, Pitfall 1 cross-loop guard); consumer uses `wait_for(timeout=60.0)`; cross-test-loop race guard passes twice in same session. |
| 4 | SVC-04 | Restart parity: initialization order + signature preserved | `src/backend/base/langflow/main.py`, `src/backend/tests/benchmarks/_langflow_no_change_restart_supervisor.py` | `src/backend/tests/phase_04_service_init_parity/test_svc04_restart_integration.py::test_svc04_initialize_services_boot_1_clean`, `::test_svc04_full_lifespan_sequence_boot_1`, `::test_svc04_restart_with_matching_hash_seeds_second_boot`, `::test_svc04_restart_with_corrupt_hash_falls_through_cleanly`, `::test_svc04_force_resync_env_var_second_boot_clean`, `::test_svc04_services_utils_module_structure_unchanged`, `::test_svc04_initialize_services_signature_unchanged` | Two-boot supervisor: boot 1 clean; boot 2 with matching hash seeds cleanly; no init-order ERROR markers in caplog ("no such table", "table doesn't exist", "OperationalError", "service not initialized"); service-utils module structure AST unchanged; `initialize_services(*, fix_migration: bool = False)` signature unchanged. |

## Phase 5.5 - Component Index Build Caching

| Phase | Req | Area | File(s) touched | Governing test | Assertion |
|-------|-----|------|-----------------|----------------|-----------|
| 5.5 | IDX-08 | Cache-hit short-circuit in `_read_component_index` | `src/lfx/src/lfx/interface/components.py` (read-path only; no write-side edits) | `src/lfx/tests/unit/test_component_index.py::TestIDX08CacheHit::test_cache_hit_populates_all_types_dict`, `::test_cache_miss_falls_back_to_rebuild`, `::test_cache_hit_skips_telemetry` | Prebuilt cache file: `import_langflow_components` is not called on the hit path; cache-miss still rebuilds once; telemetry skipped on hit. |
| 5.5 | IDX-09 | Cache-hit vs cache-miss parity + <500ms perf ceiling | `src/lfx/src/lfx/interface/components.py` | `src/lfx/tests/unit/test_component_index.py::TestIDX08CacheHit::test_parity_cache_hit_vs_miss`, `::test_cache_hit_perf_under_500ms` | Cache-hit and cache-miss snapshots byte-identical against `smallest.snapshot.json`; cache-hit path completes in <500ms via `time.perf_counter()`. |

## Umbrella CI run

The `run-benchmarks` verify-mode workflow run that exercised every test cited above as a cross-check for the final Phase 6 PR:

- Run: https://github.com/langflow-ai/langflow/actions/runs/24666601910

Per CONTEXT.md D-08, individual table rows do not re-cite this run ID; it is the umbrella "all these tests passed together" evidence for the entire document.

The companion snapshot-mode run that captured the post-fix authoritative numbers is cited in `.planning/benchmarks/post-2026-04-20.md` under "CI gate evidence".

## Out-of-scope changes (Phase 5 container + deployment layer)

Per CONTEXT.md D-07, the following Phase 5 changes are NOT listed in this parity document because they do not touch services-layer or component-index code:

- CNT-01: `UV_COMPILE_BYTECODE=1` in `src/lfx/docker/Dockerfile`
- CNT-02: Multi-stage layer separation in `src/lfx/docker/Dockerfile`
- CNT-03: `docs/docs/Deployment/deployment-cold-start.mdx` authoring
- CNT-04: `LANGFLOW_GUNICORN_PRELOAD` default flip + `_langflow_post_fork` hook (test file `src/backend/tests/unit/services/telemetry/test_post_fork.py`; covers fork-safety, which is a supporting-guarantee for the preload flip, but the flip itself is a deployment-layer behavior change, not a services-layer code change).

Each of these is covered by its own Phase 5 plan SUMMARY under `.planning/phases/05-container-and-deployment-optimization/` and by the Phase 5 Dockerfile smoke builds in `.github/workflows/`.
