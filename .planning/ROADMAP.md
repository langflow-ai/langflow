# Roadmap: Langflow / lfx Cold-Start Improvements

## Overview

This milestone reduces cold-start latency for `lfx run` and `langflow run` on containerized deployments, with IBM watsonX.orchestrate as the primary target. The work proceeds in evidence-driven order: build a measurement harness first, close known correctness bugs in the component index before touching concurrency, then apply import-time deferrals (low-complexity wins first, langchain_core last), restructure service initialization, tune the container image build, and finally re-measure and confirm improvement. Every code change that touches the services layer or component index must maintain observable behavior parity.

## Open Questions

Resolved decisions are captured below; only the measurement-dependent question remains open. See `.planning/PROJECT.md` Key Decisions for full context.

- ~~**Phase 5:** What is the watsonX.orchestrate container base image?~~ **RESOLVED 2026-04-16:** Not a concern. Phase 5 Dockerfile targets a generic modern Python base; no IBM-specific constraints.
- ~~**Phase 4:** Does production `lfx run` invoke `serve_app.py` or `run_flow()` directly?~~ **RESOLVED 2026-04-16:** `run_flow()` direct. Phase 4's FastAPI lifespan work primarily benefits `langflow run`, not the lfx path.
- ~~**Phase 2:** What is the minimum Python version in the deployed lfx container?~~ **RESOLVED 2026-04-16:** 3.13 or 3.14. `asyncio.Lock()` at module import raises `RuntimeError`, so IDX-01 lazy-property pattern is a hard requirement.
- **Phase 1 (still open):** Is dep-install time or import time the dominant cost for `lfx run <flow>` in a cold container? Phase 1 measurement answers this by running the same flow with and without pre-baked deps.
- ~~**Phase 5:** Is `LANGFLOW_GUNICORN_PRELOAD=true` safe to enable by default?~~ **RESOLVED 2026-04-16:** User green-lights the default flip if it improves performance. Phase 5 still gates on fork-safety verification (SQLAlchemy `after_fork` + `engine.dispose()`, asyncio lock reset in workers) before actually flipping.

## Phases

- [x] **Phase 1: Measurement Foundation** - Build benchmarking harness, capture baseline numbers, answer dep-install vs. import-time question, produce ranked hotspot list.
- [x] **Phase 2: Component Index and Correctness Fixes** - Close TOCTOU race, thread-exhaustion bug, atomic write race, and version-stamp bug in the component index; remove duplicate superuser init; emit stale-index warning. Must maintain behavior parity with component-loaded flows. (completed 2026-04-17)
- [x] **Phase 3: Import-Time Optimization** - Defer heavy top-level imports (pandas/PIL/OTel first, langchain_core last in sub-tasks); each PR must show both `lfx run` and `langflow run` numbers and pass mypy clean. Services layer and component index semantics must not regress. (completed 2026-04-17; Graph cold-import 1440ms -> 356ms, -75%)
- [x] **Phase 4: Service Init Restructuring** - Hash-gate starter-project updates, parallelize independent lifespan tasks, replace MCP sleep with event coordination. Services layer must preserve initialization order and behavior parity. (completed 2026-04-17; langflow_run_no_change_restart CI baseline captured 2026-04-18 at 11078ms ± 23ms)
- [x] **Phase 5: Container and Deployment Optimization** - Produce optimized Dockerfile, publish cold-start deployment guide, evaluate `LANGFLOW_GUNICORN_PRELOAD` fork safety. (completed 2026-04-18; LANGFLOW_GUNICORN_PRELOAD default flipped to true after D-07 gate passed)
- [ ] **Phase 5.5: Component Index Build Caching** - Read the persisted component index on cold start and skip rebuild when the installed `lfx` version matches; targets the 3.4s ComponentCache rebuild observed in lfx_with_flow profiling on 2026-04-18.
- [ ] **Phase 6: Validation and Publication** - Re-run harness, produce before/after table, confirm parity, lock in CI regression gate.

## Phase Details

### Phase 1: Measurement Foundation
**Goal**: A reproducible measurement harness exists, baseline cold-start numbers are captured on `release-1.9.0` before any code changes, and the dep-install vs. import-time dominance question is answered for `lfx run <flow>`.
**Depends on**: Nothing (first phase)
**Requirements**: MEAS-01, MEAS-02, MEAS-03, MEAS-04, MEAS-05, MEAS-06, MEAS-07, MEAS-08
**Success Criteria** (what must be TRUE):
  1. `src/backend/tests/benchmarks/` exists with harness scripts covering `lfx run` bare boot, `lfx run <flow>` first execution, and `langflow run` end-to-end; each scenario uses explicit cold-cache preparation (Linux drop_caches or fresh Docker container per run).
  2. `.planning/benchmarks/baseline-YYYY-MM-DD.md` exists with wall-clock times for all three scenarios, per-phase breakdowns (import / service-init / first-flow-run), and a rank-ordered hotspot list of the top-N import-time contributors.
  3. A `python -X importtime` artifact and a `pyinstrument` HTML profile exist for each of the three scenarios and are saved alongside the baseline document.
  4. MEAS-07 is answered: the same representative flow is measured with and without pre-baked deps; the baseline document records whether dep-install or import time is the dominant cost.
  5. The CI regression gate (MEAS-08) is defined and wired — the gate would fail a PR that introduces a synthetic 20%+ regression — even if it cannot yet produce a passing green run until Phase 6.
**Plans**: 6 plans

Plans:
- [x] 01-01-PLAN.md — Harness scaffolding (benchmarks/ package, pytest opt-out, `benchmarks` dep-group, Makefile targets). Requirements: MEAS-01.
- [x] 01-02-PLAN.md — Fixtures (noop_flow, basic_prompting, document_qa) + BaseChatOpenAI `_generate`/`_agenerate` monkey-patch. Requirements: MEAS-01, MEAS-07 (prep).
- [x] 01-03-PLAN.md — Checkpoint instrumentation: stdlib-only `lfx/_bench.py` + six named checkpoints wired into `lfx/cli/run.py`. Requirements: MEAS-03.
- [x] 01-04-PLAN.md — Measurement Dockerfile (`python:3.13-slim` + uv + hyperfine) with `BENCH_VARIANT=lean|prebaked` build arg. Requirements: MEAS-02, MEAS-07 (prep).
- [x] 01-05-PLAN.md — Driver, scenarios, pyinstrument + `-X importtime` capture, baseline md+json writer, MEAS-07 delta. Requirements: MEAS-01, MEAS-02, MEAS-04, MEAS-05, MEAS-06, MEAS-07.
- [x] 01-06-PLAN.md — Label-gated CI workflow, committed `thresholds.json`, synthetic-regression Makefile target. Requirements: MEAS-08.

**Wave hints for parallelization:**
- wave 1: harness scaffolding (`src/backend/tests/benchmarks/` directory, conftest, test skeletons) + test-isolation fixtures (component_cache reset, lru_cache clear per pitfalls 6 and 20)
- wave 2 (depends on wave 1): baseline capture runs (cold-container measurement) + `pyinstrument` and `-X importtime` artifact collection + MEAS-07 dep-install comparison

### Phase 2: Component Index and Correctness Fixes
**Goal**: All known correctness bugs in the component index are closed before any subsequent work increases concurrency or cache utilization. Observable behavior of component-loaded flows is unchanged.
**Depends on**: Phase 1 (baseline must exist so regressions can be detected)
**Requirements**: IDX-01, IDX-02, IDX-03, IDX-04, IDX-05, IDX-06, IDX-07
**Parity constraint**: Every change in this phase touches `lfx/interface/components.py` or `langflow/main.py`, both load-bearing. Each change must be accompanied by a test (or reference to an existing test) confirming that `ComponentCache.all_types_dict` is populated correctly and that flows loaded from the component index execute identically before and after the change.
**Success Criteria** (what must be TRUE):
  1. `ComponentCache` exposes its lock as a lazy property so `asyncio.Lock()` is only created inside a running event loop; a concurrent 10-task test confirms the cache is built exactly once (IDX-01, pitfall 4).
  2. `_load_components_dynamically` is capped with `asyncio.Semaphore(16)`; a test confirms component count is stable across repeated cold builds and matches the pre-semaphore count (IDX-02, pitfall 9).
  3. `_save_generated_index` writes atomically via `os.replace` and stamps the cache with `version("lfx")`; a round-trip test (save → read in lfx-only environment) passes without a version-mismatch log (IDX-03, IDX-04, IDX-05, pitfalls 8 and 18).
  4. `index_path.read_bytes` is wrapped in `asyncio.to_thread`; the event-loop-blocking path is confirmed gone by a test that asserts no synchronous I/O from an async context during index load (IDX-03).
  5. The duplicate `initialize_auto_login_default_superuser` call is removed; a log-level test confirms it appears exactly once with `AUTO_LOGIN=True` and zero times with `AUTO_LOGIN=False` (IDX-06).
  6. A dev-mode warning is emitted when the cached index version does not match the installed package version; a unit test confirms the warning fires on version mismatch and is absent on match (IDX-07).
**Plans**: 6 plans

Plans:
- [x] 02-01-PLAN.md — IDX-01 lazy asyncio.Lock property on ComponentCache + shared parity scaffolding (mock LLM autouse fixture, _capture_parity_snapshot helper, synthetic fixtures dir with smallest.json) + TestIDX01LazyLock concurrency tests (async 10-gather race + threading no-crash) + deep parity test. Requirements: IDX-01.
- [x] 02-02-PLAN.md — IDX-02 asyncio.Semaphore(16) cap on _load_components_dynamically via _bounded helper + five_types.json synthetic fixture + TestIDX02SemaphoreCap with 5-rebuild exact per-type count equality test + deep parity. Requirements: IDX-02.
- [x] 02-03-PLAN.md — IDX-04 version stamp fix (version("lfx") replacing version("langflow")) with PackageNotFoundError fallback + IDX-05 atomic write via same-directory tmp file + os.replace + TestIDX04IDX05WriteSide (stamp + round-trip in lfx-only env + atomic-write sequence + PackageNotFoundError fallback) + deep parity. Requirements: IDX-04, IDX-05.
- [x] 02-04-PLAN.md — IDX-06 delete duplicate unconditional initialize_auto_login_default_superuser call (lines 194-196 of langflow/main.py; keep conditional block at 186-192) + source-level + behavioral tests (AUTO_LOGIN=True fires once, =False zero times). Requirements: IDX-06.
- [x] 02-05-PLAN.md — IDX-03 _read_component_index def→async refactor + wrap index_path.read_bytes in asyncio.to_thread at both sites (line 123 custom, line 136 built-in) + update 3 callers (296, 319, test AsyncMock conversion in TestImportLangflowComponents) + TestIDX03ReadPath (coroutine function check, non-blocking-loop proof via ticker, parity on smallest and five_types). Requirements: IDX-03.
- [x] 02-06-PLAN.md — IDX-07 read-time stale-index warning via structlog logger.warning gated on cache_path.exists() AND cached_version != version("lfx"); peek via asyncio.to_thread; silent on match / absent / corrupt cache + TestIDX07StaleIndexWarning (4 gating cases + deep parity). Requirements: IDX-07.

**Wave hints for parallelization:**
- wave 1 (independent bugs, 4 plans): 02-01 (IDX-01) + 02-02 (IDX-02) + 02-03 (IDX-04 + IDX-05 combined) + 02-04 (IDX-06 duplicate superuser)
- wave 2 (depends on wave 1, 2 plans): 02-05 (IDX-03 async read path) + 02-06 (IDX-07 stale warning — depends on 02-03's version stamp)

### Phase 3: Import-Time Optimization
**Goal**: Heavy top-level imports are deferred so neither `lfx run` nor `langflow run` pays for libraries that are not used on the startup path. All changes pass mypy clean, introduce no new circular imports, and each sub-task is independently deployable with benchmark evidence.
**Depends on**: Phase 2 (correctness bugs closed before concurrency increases that might expose the TOCTOU race)
**Requirements**: IMP-01, IMP-02, IMP-03, IMP-04, IMP-05, IMP-06, IMP-07, IMP-08, IMP-09, IMP-10
**Parity constraint**: Any change touching `lfx/interface/components.py` or `langchain_core` import paths must include a `modulefinder` import-graph check confirming no new circular imports. The services layer and component index semantics must not regress (no change to `ComponentCache`, `ServiceManager`, or `deps.py`).
**Ordering within this phase** (complexity ordering, not arbitrary):
  - LOW complexity first: pandas/numpy (IMP-02, 5 files), PIL (IMP-03), OTel/Prometheus (IMP-04), voice_mode router (IMP-05), compat layer (IMP-06)
  - MEDIUM next: `langflow/__main__.py` deferred imports (IMP-01)
  - HIGH last: `langchain_core` via `__getattr__` at `field_typing` level (IMP-07), then 83-file deferred-import sub-tasks by module group (IMP-08) — agents, schema, serialization as separate independently deployable units
  Each sub-task of IMP-08 requires: (a) `modulefinder` import-graph check before PR, (b) benchmark numbers for both `lfx run` and `langflow run` paths, (c) mypy clean.
**Success Criteria** (what must be TRUE):
  1. `python -X importtime -c "import lfx"` no longer shows `pandas`, `numpy`, or `PIL` in the output; benchmark confirms measurable wall-clock improvement for `lfx run` bare boot (IMP-02, IMP-03, pitfall 7).
  2. `langflow run` no longer imports `opentelemetry.instrumentation.fastapi`, `prometheus_client`, `openai`, or `elevenlabs` when those features are disabled; benchmark confirms `langflow run` cold-start improvement (IMP-04, IMP-05).
  3. `langflow/__init__.py` compat layer defers its 40+ `find_spec` calls until first attribute access; a test confirms `import langflow` in isolation does not trigger a single `find_spec` call (IMP-06).
  4. `lfx/field_typing/__init__.py` and `constants.py` expose the 11 `langchain_core` symbols via `__getattr__`; mypy passes without new `Any` types introduced; `python -X importtime -c "import lfx.field_typing"` no longer shows `langchain_core` (IMP-07, pitfall 5).
  5. Every IMP-08 sub-task (by module group) ships with before/after benchmark numbers for both `lfx run` and `langflow run`, a `modulefinder` clean bill for circular imports, and a mypy clean run; aggregate improvement across all sub-tasks is reflected in IMP-09 comparison (IMP-08, IMP-09, IMP-10).
**Plans**: 13 plans

Plans:
- [x] 03-01-PLAN.md — IMP-02 pandas/numpy deferral across 7 files (5 CONCERNS.md + 3 additional RESEARCH.md sites) + bundled DataFrame deferrals on Graph hot path (helpers/data.py, schema/artifact.py, field_typing/constants.py partial PEP 562, base_file.py DataFrame); test_import_absence.py scaffolding + 3 TestIMP02NoPandas tests. Commits: 288aa05814, 3490da3009. Requirements: IMP-02, IMP-09, IMP-10.
- [ ] 03-02-PLAN.md — IMP-03 PIL deferral in schema/image.py + interface/utils.py; TestIMP03NoPIL. Requirements: IMP-03, IMP-09, IMP-10.
- [~] 03-03-PLAN.md — **DEFERRED** (2026-04-17 scope change): Langflow-run specific; user prioritized Graph / `lfx run` optimization. Plan remains on disk for future revisit. Requirements: IMP-04, IMP-09, IMP-10.
- [~] 03-04-PLAN.md — **DEFERRED** (2026-04-17 scope change): Langflow-run specific. Requirements: IMP-05, IMP-09, IMP-10.
- [~] 03-05-PLAN.md — **DEFERRED** (2026-04-17 scope change): Langflow-run specific. Requirements: IMP-06, IMP-09, IMP-10.
- [~] 03-06-PLAN.md — **DEFERRED** (2026-04-17 scope change): Langflow-run specific (langflow/__main__.py). Requirements: IMP-01, IMP-09, IMP-10.
- [ ] 03-07-PLAN.md — IMP-07 field_typing/constants.py PEP 562 __getattr__ + _LAZY map + preserved Windows c10.dll OSError fallback; new test_import_graph.py with subprocess+sys.modules mechanism (overrides CONTEXT.md D-07 modulefinder per RESEARCH.md Pitfall 1). Requirements: IMP-07, IMP-09, IMP-10.
- [ ] 03-08a-PLAN.md — IMP-08a schema group (5 files: schema/{data,message}.py, helpers/data.py, utils/schemas.py, interface/utils.py); TestIMP08aSchemaGroup. Requirements: IMP-08, IMP-09, IMP-10.
- [ ] 03-08b-PLAN.md — IMP-08b serialization + graph group (3 files: serialization/serialization.py extension, graph/vertex/vertex_types.py, custom/validate.py); TestIMP08bSerializationGroup. Requirements: IMP-08, IMP-09, IMP-10.
- [ ] 03-08c-PLAN.md — IMP-08c base/agents group (6 files; callback.py + token_callback.py EXCLUDED per Pitfall 5); TestIMP08cAgentsGroup. Requirements: IMP-08, IMP-09, IMP-10.
- [ ] 03-08d-PLAN.md — IMP-08d base/tools + base/models + base/prompts + 7 other base/* subsystems (13 files); TestIMP08dBaseGroup. Requirements: IMP-08, IMP-09, IMP-10.
- [ ] 03-08e-PLAN.md — IMP-08e custom/custom_component group (2 files); TestIMP08eCustomGroup. Requirements: IMP-08, IMP-09, IMP-10.
- [ ] 03-09-PLAN.md — Phase close: IMP-09 aggregate benchmark table + IMP-10 mypy rollup + authoritative thresholds.json CI snapshot via `run-benchmark-snapshot` label (checkpoint:human-verify). Requirements: IMP-09, IMP-10.

**Scope note (2026-04-17):** Post-execution user direction: Graph hot path (`lfx run <flow>`) is the priority; Langflow-run-specific plans (IMP-01, IMP-04, IMP-05, IMP-06) are deferred as lower value since lfx is the biggest runtime player. Active scope is plans targeting the Graph import chain: 03-01 (done), 03-02 (PIL), 03-07 (full constants.py PEP 562), 03-08a..e (83-file langchain_core), 03-09 (phase close).

**Wave hints for parallelization (post-scope-change):**
- wave 1 (Graph-path): 03-01 (IMP-02, done) + 03-02 (IMP-03 PIL). Serialized on test_import_absence.py appends.
- wave 2: 03-07 (IMP-07 full PEP 562 for constants.py; partial pattern already applied in 03-01 commit 3490da3009).
- wave 3 (depends on 03-07 stable): 03-08a + 03-08b + 03-08c + 03-08d + 03-08e in parallel (disjoint `files_modified` sets; shared-file serialization applies only to test_import_absence.py appends and to serialization.py which plan 03-08b re-touches after IMP-02).
- wave 4 (phase close): 03-09 (depends on all active prior plans complete; checkpoint for CI snapshot).
- Deferred (not executed in this milestone): 03-03, 03-04, 03-05, 03-06 — all Langflow-run-specific.

### Phase 4: Service Init Restructuring
**Goal**: Service initialization time is reduced by skipping redundant work on the common "nothing changed" restart path and by parallelizing tasks that have no inter-dependencies. Services layer initialization order and observable behavior are preserved exactly.
**Depends on**: Phase 3 (import-time wins shift the bottleneck; Phase 1 measurements confirm service-init is now dominant before investing here)
**Requirements**: SVC-01, SVC-02, SVC-03, SVC-04
**Parity constraint**: Any change to `langflow/main.py` lifespan ordering or `langflow/initial_setup/setup.py` must be accompanied by a documented service-dependency review (services that depend on others must still see them initialized first). SVC-04 explicitly requires the initialization order to be preserved or any changes to be documented per-service.
**Success Criteria** (what must be TRUE):
  1. `create_or_update_starter_projects` exits in under 50ms when starter project content has not changed since the last run; benchmark confirms the no-change path vs. the prior baseline (SVC-01, pitfall 11).
  2. Independent lifespan tasks (`copy_profile_pictures`, `load_bundles`, superuser init) run via `asyncio.gather`; a dependency-review comment in the code documents which tasks are order-independent and which are not; total lifespan time is measurably reduced (SVC-02, pitfall 10).
  3. MCP server startup no longer uses `asyncio.sleep(10.0)`; startup is event-driven and MCP tools become available as soon as starter projects are ready; this change is conditional on SVC-01 being stable (SVC-03).
  4. Service initialization order is either unchanged or every change is documented with a per-service compatibility note; a restart integration test confirms no "service not initialized" or "table doesn't exist" errors with the new lifespan order (SVC-04).
**Plans**: 5 plans

Plans:
- [x] 04-01-PLAN.md — SVC-01 hash gate helper module + wire into main.py FileLock block + phase_04 test tree scaffold + D-05 dual-invocation spy/mutation/force-resync tests. Requirements: SVC-01.
- [x] 04-02-PLAN.md — SVC-04 D-09 inline dependency-review comment blocks (wave-1 + wave-2) in main.py lifespan + D-10 precondition test (review block presence + well-formed rows). Requirements: SVC-04.
- [x] 04-03-PLAN.md — SVC-02 _safe_step helper + wave-1 asyncio.gather (setup_llm_caching + copy_profile_pictures) + wave-2 asyncio.gather (load_bundles_with_error_handling + get_and_cache_all_types_dict) + D-06 structural assertion + D-10 gather-vs-review cross-check. Requirements: SVC-02, SVC-04.
- [x] 04-04-PLAN.md — SVC-03 asyncio.Event inside lifespan + producer inside FileLock (both hit/miss paths) + consumer replaces asyncio.sleep(10.0) with wait_for(timeout=60) + D-07 absence + race test + Pitfall-1 cross-loop guard + 5s retry preserved (D-14). Requirements: SVC-03.
- [x] 04-05-PLAN.md — CI scenario langflow_run_no_change_restart + two-boot supervisor + thresholds.json sentinel + workflow matrix + SVC-04 restart-parity integration test (boot initialize_services + get_and_cache_all_types_dict + create_or_update_starter_projects twice; assert no init-order errors via caplog). Requirements: SVC-01, SVC-04.

**Wave hints for parallelization (planner-finalized):**
- wave 1: 04-01 (SVC-01 hash gate — starter_project_hash.py is new-file; main.py edit is inside FileLock block)
- wave 2: 04-02 (SVC-04 dependency-review comment blocks — edits main.py at different regions; serialized on main.py overlap with 04-01)
- wave 3: 04-03 (SVC-02 gather — replaces sequential calls at the locations anchored by 04-02; serialized on main.py overlap)
- wave 4: 04-04 (SVC-03 Event — producer fires inside 04-01's FileLock block; consumer replaces sleep at the location 04-03 leaves alone; serialized on main.py overlap)
- wave 5: 04-05 (CI benchmark + SVC-04 restart-parity integration test — touches disjoint files: benchmark scenarios, workflow YAML, thresholds.json, new test file; can run after 04-04 since the scenario measures the post-SVC-03 restart path)

All five plans touch main.py sequentially (plans 04-01..04-04) by design; splitting main.py edits across plans limits per-plan blast radius and preserves test independence. 04-05 is disjoint on main.py.

### Phase 5: Container and Deployment Optimization
**Goal**: A reference Dockerfile produces a container image that boots measurably faster than the pre-optimization baseline, and a deployment guide gives the watsonX.orchestrate integration team actionable cold-start tuning instructions.
**Depends on**: Phase 4 (in-code improvements land before deployment-level tuning; `LANGFLOW_GUNICORN_PRELOAD` evaluation requires Phase 4 service ordering to be stable)
**Requirements**: CNT-01, CNT-02, CNT-03, CNT-04
**Success Criteria** (what must be TRUE):
  1. The reference Dockerfile sets `UV_COMPILE_BYTECODE=1` in the build stage; a fresh-container cold-start measurement (no pycache, no layer cache) shows measurable improvement vs. the Phase 1 baseline when only the Dockerfile change is applied (CNT-01, pitfall 3).
  2. The Dockerfile uses multi-stage layer separation (`uv sync --no-install-project` as a separate layer); a repeat-build CI timing confirms the deps layer is cached correctly when only source code changes (CNT-02).
  3. `docs/deployment/cold-start.md` (or nearest existing docs location) exists and documents: `UV_COMPILE_BYTECODE=1`, layer order, pre-warmed venv patterns, the recommended way to pre-bake common flow deps, and the cross-platform requirements-generation caveat from pitfall 19 (CNT-03).
  4. `LANGFLOW_GUNICORN_PRELOAD` default evaluation is complete: if `after_fork` + `engine.dispose()` is verified in `langflow/services/database/`, the default flips to opt-out with a documented migration note; otherwise it stays opt-in with a clear caveat in the guide (CNT-04, pitfalls 12 and 4).
**Plans**: 6 plans

Plans:
- [x] 05-01-PLAN.md — Dockerfile patches in-place: builder FROM to python3.13-alpine (D-02 unblocked), first uv sync gains --no-install-project (CNT-02 cache fix), runtime FROM to python3.13-alpine (Pitfall 2 ABI match). Requirements: CNT-01, CNT-02.
- [x] 05-02-PLAN.md — lfx_reference_image CI scenario + driver registry + thresholds.json sentinel + cold-start-benchmark.yml wiring (hyperfine-wrapped; lfx run exits after flow completion). Requirements: CNT-01.
- [x] 05-03-PLAN.md — deployment-cold-start.mdx guide (D-08) + sidebars.js wiring + cross-links from deployment-docker.mdx and deployment-prod-best-practices.mdx (D-09). Requirements: CNT-03.
- [x] 05-04-PLAN.md — Repeat-build cache-hit verification step in build-images job (D-14 <30s assertion for CNT-02). Requirements: CNT-02.
- [x] 05-05-PLAN.md — D-05 fork-hazard audit + TelemetryService post_fork fix (_langflow_post_fork hook in server.py + start/stop guards in services/telemetry/service.py + test_post_fork.py). Requirements: CNT-04.
- [x] 05-06-PLAN.md — LANGFLOW_GUNICORN_PRELOAD default flip conditional on 05-05 D-07 gate + finalize LANGFLOW_GUNICORN_PRELOAD section in deployment-cold-start.mdx. Requirements: CNT-04.

**Wave hints for parallelization:**
- wave 1 (independent, 4 plans): 05-01 (Dockerfile) + 05-02 (CI scenario) + 05-03 (docs guide) + 05-04 (cache-hit CI assertion). 05-02 and 05-04 both touch .github/workflows/cold-start-benchmark.yml (serialized by file overlap).
- wave 2 (depends on wave 1 + Phase 4 stable, 2 plans): 05-05 (audit + TelemetryService fix) then 05-06 (default flip conditional on 05-05 D-07 gate).

### Phase 5.5: Component Index Build Caching
**Goal**: On cold start, the component index is loaded from the persisted cache instead of rebuilt from a full package walk, bringing the index-populated path under 500ms vs the 3.4s rebuild measured on `lfx_with_flow` (2026-04-18 snapshot). Reuses the versioned, atomic on-disk cache that Phase 2 IDX-04/05 already writes.
**Depends on**: Phase 2 (IDX-04 version stamp + IDX-05 atomic write must be in place; IDX-07 stale-index detection provides the invalidation signal). Parallel to Phase 5 (Phase 5 targets container-level bytecode; Phase 5.5 targets in-process index cost). Both are independently useful; order is orthogonal.
**Requirements**: IDX-08, IDX-09
**Parity constraint**: Cache-hit and cache-miss paths must produce identical `all_types_dict` content for flow execution (same keys, same ordering). A deep parity test (load same flow via both paths, assert byte-identical final output + vertex execution order) is mandatory, matching the Phase 2 scaffolding pattern.
**Success Criteria** (what must be TRUE):
  1. `ComponentCache.get_and_cache_all_types_dict` reads the persisted index via `_read_component_index` when the cached `version("lfx")` stamp matches the installed package and the file parses cleanly; on match, it returns the cached dict without walking `lfx.components` (IDX-08).
  2. On cold start in a fresh container with a pre-baked cache, the index-build checkpoint (Phase 1 harness `after-component-index` minus `before-run-flow`) is under 500ms, down from the ~3.4s measured on `lfx_with_flow` 2026-04-18 (IDX-08).
  3. Cache-miss (missing file, version mismatch, parse error) falls through to the full rebuild without error, emitting the IDX-07 warning so dev environments notice (IDX-08).
  4. A parity test loads the same flow through both cache-hit and cache-miss paths and asserts byte-identical final output + vertex execution order via the Phase 2 `_capture_parity_snapshot` helper (IDX-09).
**Plans**: 2/2 complete (05.5-01: IDX-08 cache-hit short-circuit; 05.5-02: IDX-09 parity + perf test)
**Status**: COMPLETE (2026-04-18)

**Wave hints for parallelization:**
- wave 1: IDX-08 (read-path short-circuit in `_read_component_index` + caller threading) + IDX-09 (parity test) — can develop in parallel; tests exercise both paths by controlling whether the cache file exists.
- No wave 2 — the phase is small and single-concern.

### Phase 6: Validation and Publication
**Goal**: The full before/after evidence is assembled, parity is confirmed for all code changes, and the CI regression gate runs green on the final branch.
**Depends on**: Phase 5 (all code and deployment changes complete)
**Requirements**: VAL-01, VAL-02, VAL-03, VAL-04
**Success Criteria** (what must be TRUE):
  1. `.planning/benchmarks/post-YYYY-MM-DD.md` exists with a before/after comparison table covering all scenarios from MEAS-01, with delta ms and delta % per scenario and per phase-of-startup (import / service-init / first-flow-run) (VAL-01).
  2. A behavior parity confirmation document lists every change touching the services layer or component index (Phase 2 IDX-*, Phase 3 IMP-07/IMP-08, Phase 4 SVC-*), with test run references or assertion evidence that observable flow behavior is unchanged (VAL-02).
  3. The CI regression gate from MEAS-08 runs green on the final branch; a synthetic regression test (artificially add a 300ms sleep to an import path) confirms the gate would fail on regression (VAL-03).
  4. Final cold-start numbers are published in the appropriate release artifact (CHANGELOG, release notes, or integration note for the watsonX.orchestrate team) in whatever format is confirmed appropriate before this phase begins (VAL-04).
**Plans**: 6 plans

Plans:
- [x] 06-06-PLAN.md — IMP-11 regression fix (discovered during Phase 6 snapshot): lazy `_LazyExecGlobals` in `validate.prepare_global_scope` defers `langchain_*` imports until first access (commit 11470f8107). Unblocks VAL-01 authoritative snapshot. Requirements: VAL-01.
- [x] 06-01-PLAN.md — VAL-01: workflow-upload mitigation + snapshot-mode CI re-run (run 24642673292) + post-2026-04-20.{md,json} authoring with MEAS-03 checkpoint breakdown and Phase 3 ROADMAP reconciliation (commits 8501709b49, 8b70a2deeb). Requirements: VAL-01.
- [x] 06-02-PLAN.md — VAL-02: author parity-confirmation-YYYY-MM-DD.md covering Phase 2 IDX-01..IDX-07, Phase 3 IMP-02 + IMP-07 + IMP-11, Phase 4 SVC-01..SVC-04, Phase 5.5 IDX-08 + IDX-09 (no new test runs per D-09). Requirements: VAL-02.
- [x] 06-03-PLAN.md — VAL-03: local make bench-verify-synthetic capture under synthetic-regression-evidence/ + verify-mode CI green run under run-benchmarks label. Records verify-run ID in 06-03-SUMMARY for 06-05 backfill. Requirements: VAL-03.
- [x] 06-04-PLAN.md — VAL-04: three-layer publication (release-notes.mdx bullet, deployment-cold-start.mdx ### Measured improvements append, .planning/deliverables/watsonx-integration-note.md). Requirements: VAL-04.
- [x] 06-05-PLAN.md — VAL-03 citation tail: backfilled verify-mode CI run ID 24666601910 into post-2026-04-20.md and parity-confirmation-2026-04-20.md, replacing the `<verify-run-id-from-06-03>` placeholders (commit 864db4bea4, 2026-04-18). Requirements: VAL-03.

**Wave hints for parallelization:**
- wave 1 (regression fix, blocks all measurement): 06-06 (IMP-11 langchain_core deferral on lfx.base.models path).
- wave 2 (parallel; depends on 06-06 landing so the lfx path is clean): 06-01 (authoritative snapshot + post-doc) + 06-03 (CI verify-mode run + local synthetic-regression evidence).
- wave 3 (parallel; disjoint files_modified; both depends_on ["06-01"]): 06-02 (parity doc; derives date from post-06-01 thresholds.json) + 06-04 (publication; consumes post-06-01 numbers).
- wave 4 (depends on 06-01 + 06-02 + 06-03): 06-05 (backfill verify-run ID into the placeholder-bearing docs created by 06-01 and 06-02, using the run ID recorded by 06-03).

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Measurement Foundation | 6/6 | Complete |  |
| 2. Component Index and Correctness Fixes | 6/6 | Complete    | 2026-04-17 |
| 3. Import-Time Optimization | 9/13 | Complete | 2026-04-17 (4 deferred to future milestone) |
| 4. Service Init Restructuring | 5/5 | Complete | 2026-04-17 (CI baseline snapshot 2026-04-18) |
| 5. Container and Deployment Optimization | 5/6 | In Progress|  |
| 5.5. Component Index Build Caching | 0/? | Not started | - |
| 6. Validation and Publication | 5/6 | In Progress | - |
