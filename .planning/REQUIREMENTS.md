# Requirements: Langflow / lfx Cold Start Improvements

**Defined:** 2026-04-16
**Core Value:** Faster cold start for `lfx run` on containerized/serverless deployments without breaking flow file format, Python API surface, or runtime behavior parity.

## v1 Requirements

### Measurement (MEAS)

- [ ] **MEAS-01**: Benchmark harness exists at `src/backend/tests/benchmarks/` that measures `lfx run` bare boot (no flow), `lfx run <flow>` first-execution with external deps, and `langflow run` end-to-end startup.
- [ ] **MEAS-02**: Harness uses `hyperfine` for wall-clock measurement with explicit cold-cache preparation (`sync && echo 3 > /proc/sys/vm/drop_caches` on Linux; fresh Docker container per measurement).
- [ ] **MEAS-03**: Harness captures per-phase breakdown via `time.perf_counter()` checkpoints (process-start, after-imports, after-`initialize_services()`, after-`get_and_cache_all_types_dict()`, after-first-vertex-build).
- [ ] **MEAS-04**: `python -X importtime` artifact captured per scenario, rendered with `importtime-waterfall` or equivalent, saved alongside benchmark results.
- [ ] **MEAS-05**: `pyinstrument` profile captured for each of the three scenarios in MEAS-01, saved as shareable HTML.
- [ ] **MEAS-06**: Baseline numbers document at `.planning/benchmarks/baseline-YYYY-MM-DD.md` captures measured cold-start time for all scenarios on `release-1.9.0` before any code changes, with phase breakdown and top-N hotspots.
- [ ] **MEAS-07**: Harness answers the dep-install vs. import-time dominance question for `lfx run <flow>` by measuring the same flow with and without pre-baked deps.
- [ ] **MEAS-08**: CI regression gate runs the harness in a fresh Docker container and fails PRs that regress cold-start beyond a defined threshold (10-15%).

### Component Index Correctness (IDX)

- [x] **IDX-01**: `ComponentCache.get_and_cache_all_types_dict` is protected by a lazy-property `asyncio.Lock` that is created on first access (safe under Python 3.12+ module-import-time constraint).
- [x] **IDX-02**: `_load_components_dynamically` caps concurrent scans with `asyncio.Semaphore(16)` to prevent thread pool exhaustion.
- [ ] **IDX-03**: Component index read path uses `asyncio.to_thread` for `index_path.read_bytes` so it does not block the event loop.
- [ ] **IDX-04**: `_save_generated_index` stamps the cache with `version("lfx")`, not `version("langflow")`, so lfx-only deployments do not invalidate the cache on every restart.
- [ ] **IDX-05**: `_save_generated_index` uses `os.replace` for atomic writes so concurrent workers never see a torn file.
- [ ] **IDX-06**: Duplicate superuser-initialization block in `langflow/main.py` (lines 186-196 range at time of writing) is removed.
- [ ] **IDX-07**: Stale-index detection emits a dev-mode warning when the cached index version does not match the installed package version, instead of silently re-reading.
- [ ] **IDX-08**: On cold start, `ComponentCache.get_and_cache_all_types_dict` reads the persisted component index written by IDX-04/05 and skips the full rebuild when the cached version matches the installed `lfx` version, bringing the index-populated cold-start path under 500ms (vs ~3.4s measured on `lfx_with_flow` 2026-04-18).
- [ ] **IDX-09**: Cache-hit vs cache-miss behavior is covered by a deep parity test that loads the same flow through both paths and asserts byte-identical final output + vertex execution order, matching the Phase 2 parity scaffolding pattern.

### Import-Time Optimization (IMP)

- [ ] **IMP-01**: `langflow/__main__.py` defers all `from langflow.*` imports into command function bodies, leaving only CLI parsing eager.
- [ ] **IMP-02**: pandas/numpy imports in `lfx/serialization/serialization.py`, `lfx/graph/vertex/param_handler.py`, `lfx/custom/custom_component/component.py`, `lfx/base/tools/component_tool.py`, and `lfx/schema/dataframe.py` are moved to `TYPE_CHECKING` blocks and function bodies, with benchmark confirmation of no behavior change.
- [ ] **IMP-03**: `PIL` imports in `lfx/schema/image.py` and `lfx/interface/utils.py` are deferred to call-site function bodies.
- [ ] **IMP-04**: `opentelemetry` and `prometheus_client` imports in `langflow/main.py` are gated behind their respective settings flags, so they only import when telemetry is enabled.
- [ ] **IMP-05**: `langflow/api/v1/voice_mode.py` router registration is feature-flag-gated so `openai`, `elevenlabs`, `numpy`, `requests` do not import on every `langflow run`.
- [ ] **IMP-06**: `langflow/__init__.py` compat layer defers its 40+ `find_spec` calls until first access via the existing `LangflowCompatibilityModule.__getattr__` pattern.
- [ ] **IMP-07**: `lfx/field_typing/__init__.py` and `constants.py` expose the 11 `langchain_core` symbols via `__getattr__` rather than eager import, preserving type-checker and IDE autocomplete via explicit `__all__` and `TYPE_CHECKING`.
- [ ] **IMP-08**: `langchain_core` imports in the remaining ~83 lfx files are deferred in sub-tasks grouped by module (agents, schema, serialization, etc.), with `modulefinder` import-graph verification per sub-task to avoid circular-import regressions.
- [ ] **IMP-09**: Every IMP-* change is accompanied by benchmark numbers showing both `lfx run` and `langflow run` improvement (or non-regression) versus the baseline.
- [ ] **IMP-10**: mypy / pyright runs clean after all IMP-* changes (deferred imports do not break type checking).

### Service Init Restructuring (SVC)

- [x] **SVC-01**: `langflow/initial_setup/setup.py` starter-project sync reads a stored content hash and skips the full reload when the hash matches, bringing the no-change path under 50ms.
- [x] **SVC-02**: Independent lifespan tasks in `langflow/main.py` run via `asyncio.gather` instead of sequentially, after an explicit service-dependency review confirms task independence.
- [x] **SVC-03**: MCP server startup sleep is replaced with event-driven readiness, conditional on SVC-01 being stable.
- [ ] **SVC-04**: Service initialization order is preserved (or changes are documented per-service in a compatibility note) so that existing services observe no behavior regression.

### Container and Deployment (CNT)

- [x] **CNT-01**: Reference Dockerfile sets `UV_COMPILE_BYTECODE=1` in the build stage so `.pyc` files are baked into the image.
- [x] **CNT-02**: Reference Dockerfile uses multi-stage layer separation (deps layer, source layer) so `uv sync` cache hits on repeat builds.
- [ ] **CNT-03**: "Deploying lfx run fast" guide at `docs/deployment/cold-start.md` (or nearest existing docs location) documents cold-start tuning: `UV_COMPILE_BYTECODE`, layer order, pre-warmed venv patterns, and the recommended way to pre-bake common flow deps.
- [x] **CNT-04**: `LANGFLOW_GUNICORN_PRELOAD=true` default change is evaluated. If SQLAlchemy `after_fork` + `engine.dispose()` is in place and verified, the default flips; otherwise it stays opt-in with documented caveat.

### Validation and Publication (VAL)

- [ ] **VAL-01**: Post-fix benchmark re-run produces a before/after comparison table covering all scenarios in MEAS-01, saved at `.planning/benchmarks/post-YYYY-MM-DD.md`.
- [x] **VAL-02**: Behavior parity confirmation document lists every code change touching the services layer or component index, with evidence (test runs, specific assertions) that observable behavior is unchanged.
- [x] **VAL-03**: CI regression gate from MEAS-08 runs green on the final branch and would fail on a synthetic regression test.
- [x] **VAL-04**: Final cold-start numbers are communicated in whatever release artifact is appropriate (release notes / CHANGELOG / integration note for the watsonX.orchestrate team).

## v2 Requirements

Deferred intentionally. Tracked so they resurface at the next milestone.

### Future Improvements (FUT)

- **FUT-01**: Installed-deps detection fast path that skips pip install when deps are already present in the venv. Only build if MEAS-07 confirms dep-install time is on the critical path.
- **FUT-02**: Prebuilt image variants published to a registry with common flow deps baked in.
- **FUT-03**: Persistent cross-container dep cache (shared volume or tar-snapshot approach) for warm-scaling scenarios.
- **FUT-04**: `lfx warm` / `lfx prebuild` CLI subcommand. Deferred per project philosophy (improvements over new features); reconsider only if in-code paths are exhausted.

## Out of Scope

Explicit exclusions with reasoning. Anti-features from research belong here with warnings.

| Feature | Reason |
|---------|--------|
| Silent dep auto-caching | Hides bugs and version skew; makes "works on my container" problems non-reproducible. |
| Startup shortcuts that bypass the component index | Component index is load-bearing for many features per user; skipping it risks silent correctness bugs. |
| Hardcoded dep version pins in lfx | lfx is dep-free by design; pinning deps defeats the embedding value proposition. |
| Changes to flow file format | Users have flows in the wild; migrations are out of scope for this milestone. |
| Changes to public Python API surface | `from lfx import ...` consumers depend on stability. |
| Changes that alter runtime behavior (output, ordering, side effects) | Parity is required; only latency characteristics should change. |
| AWS Lambda / Cloud Run-specific optimization work | watsonX.orchestrate is the primary target; other platforms get documentation only. |
| Nuitka / mypyc / shiv / pex-based compilation | Research confirms net-negative cold-start impact for this use case. |
| Silent default changes (env vars, flags, behavior) | Requires explicit opt-in or release-note documentation. |
| Warmup daemons or background preloaders | Philosophy: improvements over new features; adds complexity without fixing the underlying cost. |

## Traceability

Empty initially. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MEAS-01 | Phase 1 | Pending |
| MEAS-02 | Phase 1 | Pending |
| MEAS-03 | Phase 1 | Pending |
| MEAS-04 | Phase 1 | Pending |
| MEAS-05 | Phase 1 | Pending |
| MEAS-06 | Phase 1 | Pending |
| MEAS-07 | Phase 1 | Pending |
| MEAS-08 | Phase 1 | Pending |
| IDX-01 | Phase 2 / Plan 02-01 | Complete (e8ebd83fb4 + 40223ac991, 2026-04-16) |
| IDX-02 | Phase 2 | Complete |
| IDX-03 | Phase 2 | Pending |
| IDX-04 | Phase 2 | Pending |
| IDX-05 | Phase 2 | Pending |
| IDX-06 | Phase 2 | Pending |
| IDX-07 | Phase 2 | Pending |
| IDX-08 | Phase 5.5 | Pending |
| IDX-09 | Phase 5.5 | Pending |
| IMP-01 | Phase 3 | Pending |
| IMP-02 | Phase 3 | Pending |
| IMP-03 | Phase 3 | Pending |
| IMP-04 | Phase 3 | Pending |
| IMP-05 | Phase 3 | Pending |
| IMP-06 | Phase 3 | Pending |
| IMP-07 | Phase 3 | Pending |
| IMP-08 | Phase 3 | Pending |
| IMP-09 | Phase 3 | Pending |
| IMP-10 | Phase 3 | Pending |
| SVC-01 | Phase 4 | Complete (04-01) |
| SVC-02 | Phase 4 | Complete (04-02: D-09 review blocks; 04-03: _safe_step + wave-1/wave-2 asyncio.gather + D-06/D-10 gather-structure test) |
| SVC-03 | Phase 4 | Complete (04-04: asyncio.Event inside lifespan + producer in FileLock + consumer asyncio.wait_for(timeout=60.0) replacing asyncio.sleep(10.0) + D-07 absence / race / Pitfall-1 cross-loop guard tests) |
| SVC-04 | Phase 4 | Partial (04-02: D-09/D-10 anchor + parity guard test landed; 04-03: gather-structure test cross-checks SVC-04 parity (initialize_services stays sequential); 04-05 restart-parity integration pending) |
| CNT-01 | Phase 5 | Pending |
| CNT-02 | Phase 5 | Complete |
| CNT-03 | Phase 5 | Pending |
| CNT-04 | Phase 5 | Complete |
| VAL-01 | Phase 6 | Pending |
| VAL-02 | Phase 6 | Pending |
| VAL-03 | Phase 6 | Complete |
| VAL-04 | Phase 6 | Complete |

**Coverage:**
- v1 requirements: 39 total
- Mapped to phases: 39
- Unmapped: 0

---
*Requirements defined: 2026-04-16*
*Last updated: 2026-04-18 -- added IDX-08 / IDX-09 under new Phase 5.5 after profiling showed component-index build is 3.4s of lfx_with_flow cold start.*
