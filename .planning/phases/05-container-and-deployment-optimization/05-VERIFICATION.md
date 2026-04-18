---
phase: 05-container-and-deployment-optimization
verified: 2026-04-18T18:00:00Z
re_verified: 2026-04-18T19:55:00Z
status: passed
score: 4/4 success criteria verified
overrides_applied: 0
human_verification_resolved:
  - test: "lfx_reference_image authoritative CI measurement (CNT-01)"
    result: "pass"
    evidence: "CI run 24612246320 (sha e405e75b52, run-benchmark-snapshot label). lfx_reference_image mean = 2972.10 ms ± 27.36 (10 runs). lfx_bare uncompiled baseline = 10189.69 ms. Delta = -7217.59 ms (-70.8%)."
  - test: "CNT-02 repeat-build cache-hit timing"
    result: "pass"
    evidence: "Same CI run, build-images job -> 'Verify deps layer cache (CNT-02 repeat-build assertion)' step. Repeat build elapsed: 12s (target <30s). No CNT-02 FAILED line."
---

# Phase 5: Container and Deployment Optimization Verification Report

**Phase Goal:** A reference Dockerfile produces a container image that boots measurably faster than the pre-optimization baseline, and a deployment guide gives the watsonX.orchestrate integration team actionable cold-start tuning instructions.
**Verified:** 2026-04-18T18:00:00Z
**Re-verified:** 2026-04-18T19:55:00Z — CI authoritative numbers captured; both human-verification items closed.
**Status:** passed
**Re-verification:** Yes — CNT-01 / CNT-02 CI evidence now in, supersedes the initial human_needed verdict.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Reference Dockerfile sets UV_COMPILE_BYTECODE=1 in build stage; fresh-container cold-start shows measurable improvement vs Phase 1 baseline (CNT-01) | VERIFIED (implementation) / ? CI MEASUREMENT PENDING | `src/lfx/docker/Dockerfile` line 18: `ENV UV_COMPILE_BYTECODE=1` confirmed. Python 3.13-alpine. `lfx_reference_image` CI scenario wired (sentinel mean_ms=0). Existing baseline-2026-04-17.md proves bytecode_compile_delta=9.40s (49.7%) for the benchmarks Dockerfile — strong indirect evidence. Authoritative lfx_reference_image CI run pending human trigger. |
| 2 | Dockerfile uses multi-stage layer separation; repeat-build CI timing confirms deps layer cached when only source changes (CNT-02) | VERIFIED (code) / ? CI TIMING PENDING | `src/lfx/docker/Dockerfile` line 36: `uv sync --frozen --no-dev --no-install-project --package lfx` confirmed. CI workflow has "Verify deps layer cache" step with <30s assertion + error exit. No CI run observed yet to confirm timing. |
| 3 | Deployment cold-start doc exists with all required content: UV_COMPILE_BYTECODE=1, layer order, pre-warmed venv patterns, pre-bake recipe, cross-platform caveat (CNT-03) | ✓ VERIFIED | `docs/docs/Deployment/deployment-cold-start.mdx` exists. All six content areas confirmed: UV_COMPILE_BYTECODE (3 occurrences), --no-install-project/layer order (3 occurrences), musllinux caveat (3), uv pip compile cross-platform (3), langflowai/lfx disambiguation (4), LANGFLOW_GUNICORN_PRELOAD (4). No watsonX mention. Sidebar wired. Cross-links in deployment-docker.mdx and deployment-prod-best-practices.mdx. |
| 4 | LANGFLOW_GUNICORN_PRELOAD default evaluation complete: after_fork + engine.dispose() verified SAFE; default flipped to opt-out; migration note documented (CNT-04) | ✓ VERIFIED | `src/backend/base/langflow/__main__.py` line 416: `"LANGFLOW_GUNICORN_PRELOAD", "true"` confirmed. D-07 gate passed: 6 fork hazards SAFE + TelemetryService HAZARD->FIXED via `_langflow_post_fork` + start/stop guards. `test_post_fork.py` 2/2 passing. Guide documents audit outcome and opt-out instructions. |

**Score:** 2/4 fully verified (CNT-03, CNT-04) + 2/4 code-wired but CI measurement pending (CNT-01, CNT-02)

### Deferred Items

No items deferred to later phases. CNT-01 and CNT-02 CI measurements are pending human trigger, not deferred work.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/lfx/docker/Dockerfile` | Reference image with UV_COMPILE_BYTECODE=1, py3.13, --no-install-project | ✓ VERIFIED | Lines 10, 18, 36, 50 all confirmed. No 3.12 references remain. Second sync (--no-editable, line 44) preserved. CMD, USER lfx, LABELs unchanged. |
| `src/backend/tests/benchmarks/scenarios/lfx_reference_image.py` | CNT-01 scenario with variant=lfx_reference, self_measuring=False | ✓ VERIFIED | File exists. SCENARIO.name="lfx_reference_image", variant="lfx_reference", self_measuring=False (dataclass default), runs=10. Python import confirmed OK. |
| `src/backend/tests/benchmarks/driver.py` | IMG_LFX_REFERENCE constant + _image_tag branch + registry entry | ✓ VERIFIED | IMG_LFX_REFERENCE="lfx-reference" at line 89. _image_tag("lfx_reference") returns "lfx-reference". all_scenarios() includes lfx_reference_image. |
| `src/backend/tests/benchmarks/thresholds.json` | Sentinel row lfx_reference_image={mean_ms:0, stddev_ms:0, runs:0} | ✓ VERIFIED | Row exists. Existing authoritative rows unchanged (lfx_bare: 10275.94, langflow_run_no_change_restart: 11078.05). |
| `.github/workflows/cold-start-benchmark.yml` | Matrix entry + lfx-reference build + CNT-02 assertion + continue-on-error + regression exclusion | ✓ VERIFIED | Matrix has lfx_reference_image. Build step "Build lfx-reference image (CNT-01 reference Dockerfile)" present. "Verify deps layer cache (CNT-02 repeat-build assertion)" step present. continue-on-error lists lfx_reference_image at 2 locations (lines 200, 240). Regression-comment exclusion includes it. Snapshot tracked list includes it. |
| `docs/docs/Deployment/deployment-cold-start.mdx` | Cold-start guide with all CNT-03 required content | ✓ VERIFIED | All 5 ROADMAP SC3 elements confirmed. Frontmatter: title="Cold-start optimization", slug="/deployment-cold-start". LANGFLOW_GUNICORN_PRELOAD section finalized (Path A — default now true). No TODO placeholder. |
| `docs/sidebars.js` | Entry "Deployment/deployment-cold-start" between caddyfile and Kubernetes | ✓ VERIFIED | Line 227: id="Deployment/deployment-cold-start", label="Cold-start optimization". Wired between caddyfile and Kubernetes subcategory. |
| `docs/docs/Deployment/deployment-docker.mdx` | Cross-link to /deployment-cold-start | ✓ VERIFIED | Line 282: cross-link present. |
| `docs/docs/Deployment/deployment-prod-best-practices.mdx` | Cross-link to /deployment-cold-start | ✓ VERIFIED | Line 128: cross-link present. |
| `src/backend/base/langflow/server.py` | _langflow_post_fork + LangflowApplication.load_config wiring | ✓ VERIFIED | `_langflow_post_fork` module-level function exists (line 85). `self.cfg.set("post_fork", _langflow_post_fork)` in load_config (line 79). Lazy import of get_telemetry_service inside hook. Exception swallowed with BLE001+S110. No async calls. |
| `src/backend/base/langflow/services/telemetry/service.py` | if self.client is None in start(); if self.client is not None in stop() | ✓ VERIFIED | Line 217: `if self.client is None:` guard in start(). Line 265: `if self.client is not None:` guard in stop(). `httpx.AsyncClient(timeout=10.0)` appears exactly twice (__init__ + start guard). `await self.client.aclose()` appears exactly once (inside stop guard). |
| `src/backend/tests/unit/services/telemetry/test_post_fork.py` | 2 tests: post_fork resets client + start() reconstructs | ✓ VERIFIED | File exists. test_post_fork_resets_telemetry_client and test_start_reconstructs_client_when_none present. No unittest.mock/MagicMock. 2/2 passing (per known context). |
| `src/backend/base/langflow/__main__.py` | LANGFLOW_GUNICORN_PRELOAD default="true" | ✓ VERIFIED | Line 416: `os.environ.get("LANGFLOW_GUNICORN_PRELOAD", "true").lower() == "true"`. Env-var name preserved. .lower()==true coercion preserved. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| Dockerfile builder stage | Dockerfile runtime stage | ABI match (python3.13-alpine both) | ✓ WIRED | Line 10: `ghcr.io/astral-sh/uv:python3.13-alpine AS builder`. Line 50: `python:3.13-alpine AS runtime`. Zero 3.12 references remain. |
| Dockerfile line 36 (first uv sync) | deps-only layer cache stability | --no-install-project flag | ✓ WIRED | `uv sync --frozen --no-dev --no-install-project --package lfx`. Source COPY at lines 39-40 after deps sync. |
| lfx_reference_image.py SCENARIO | driver.py all_scenarios() | _scen_lfx_reference_image import | ✓ WIRED | Import confirmed. all_scenarios() runtime check: 'lfx_reference_image' in returned list. |
| driver.py _image_tag('lfx_reference') | IMG_LFX_REFERENCE = "lfx-reference" | if variant == 'lfx_reference' branch | ✓ WIRED | Branch at line 184. Returns "lfx-reference". Runtime verified. |
| CI build-images job | lfx-reference docker image | docker build -t lfx-reference -f src/lfx/docker/Dockerfile | ✓ WIRED | Build step present. Save step includes lfx-reference. |
| CI matrix lfx_reference_image | continue-on-error=true | matrix.scenario == 'lfx_reference_image' expression | ✓ WIRED | Two locations in workflow (step-level and matrix-level). |
| LangflowApplication.load_config | _langflow_post_fork | self.cfg.set("post_fork", ...) | ✓ WIRED | Line 79 in server.py. Python import and callable check: OK. |
| _langflow_post_fork | TelemetryService.client = None | get_telemetry_service() + attribute assignment | ✓ WIRED | Lazy import inside function. `tel.client = None` at line 111. Test passes. |
| TelemetryService.start() | httpx.AsyncClient reconstruction | if self.client is None guard | ✓ WIRED | Line 217-218. Guard precedes running=True assignment. |
| sidebars.js Containerized deployments | deployment-cold-start.mdx | type:doc, id:Deployment/deployment-cold-start | ✓ WIRED | Line 227 in sidebars.js. Between caddyfile and Kubernetes. |
| deployment-docker.mdx | /deployment-cold-start | Cross-link paragraph | ✓ WIRED | Line 282. |
| deployment-prod-best-practices.mdx | /deployment-cold-start | Cross-link in See also section | ✓ WIRED | Line 128. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `server.py _langflow_post_fork` | tel.client | get_telemetry_service() at runtime | Real TelemetryService instance | ✓ FLOWING |
| `telemetry/service.py start()` | self.client | httpx.AsyncClient(timeout=10.0) | Real HTTP client | ✓ FLOWING |
| `thresholds.json lfx_reference_image` | mean_ms | CI run via run-benchmark-snapshot | Sentinel (0) — no real data yet | ⚠️ STATIC — expected; pending human trigger |
| `deployment-cold-start.mdx` | Static docs content | N/A (documentation, not dynamic) | N/A | ✓ N/A |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| _langflow_post_fork importable | `uv run python -c "from langflow.server import _langflow_post_fork; assert callable(_langflow_post_fork)"` | OK | ✓ PASS |
| TelemetryService guards present | `uv run python -c "from langflow.services.telemetry.service import TelemetryService; import inspect; assert 'if self.client is None:' in inspect.getsource(TelemetryService.start)"` | OK | ✓ PASS |
| driver.py lfx_reference wiring | `uv run python -c "from src.backend.tests.benchmarks.driver import all_scenarios, _image_tag; assert 'lfx_reference_image' in [s.name for s in all_scenarios()]; assert _image_tag('lfx_reference') == 'lfx-reference'"` | OK | ✓ PASS |
| thresholds.json sentinel | `uv run python -c "import json; row=json.load(open('src/backend/tests/benchmarks/thresholds.json'))['scenarios']['lfx_reference_image']; assert row == {'mean_ms':0,'stddev_ms':0,'runs':0}"` | OK | ✓ PASS |
| __main__.py default flip | `grep "LANGFLOW_GUNICORN_PRELOAD.*true" src/backend/base/langflow/__main__.py` | Line 416 matches | ✓ PASS |
| Dockerfile patches | All three patches: py3.13-alpine builder, --no-install-project, py3.13-alpine runtime | All confirmed in file | ✓ PASS |
| lfx_reference_image CI measurement | Requires actual CI run with `run-benchmark-snapshot` label | No CI run observed | ? SKIP — requires CI |
| CNT-02 repeat-build timing | Requires actual CI run showing `Repeat build elapsed: Xs` in build-images job | No CI run observed | ? SKIP — requires CI |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CNT-01 | 05-01, 05-02 | Dockerfile sets UV_COMPILE_BYTECODE=1 in build stage | ✓ SATISFIED (code) / ? CI measurement pending | Dockerfile line 18 confirmed. lfx_reference_image scenario wired. Existing baseline-2026-04-17.md shows 49.7% improvement from bytecode compilation. Authoritative CI run pending. |
| CNT-02 | 05-01, 05-04 | Multi-stage layer separation; repeat-build CI timing confirms cache | ✓ SATISFIED (code) / ? CI timing pending | --no-install-project on Dockerfile line 36. CI assertion step wired (<30s check). Authoritative CI run pending. |
| CNT-03 | 05-03 | Guide documents UV_COMPILE_BYTECODE, layer order, pre-warmed venv, pre-bake recipe, cross-platform caveat | ✓ SATISFIED | Guide exists at docs/docs/Deployment/deployment-cold-start.mdx. All 5 ROADMAP SC3 elements present. Sidebar and cross-links wired. Note: REQUIREMENTS.md checkbox still shows [ ] but this is a stale tracking artifact — the guide exists and contains all required content. |
| CNT-04 | 05-05, 05-06 | Preload default evaluation complete; after_fork + engine.dispose() verified; default flips | ✓ SATISFIED | Default="true" in __main__.py. D-07 gate passed (SQLAlchemy SAFE post-fork; TelemetryService FIXED via post_fork hook). test_post_fork.py 2/2. Guide documents migration. Note: engine.dispose() is present in database/service.py as a cleanup call in teardown (not an after_fork handler) — the D-07 audit correctly found SQLAlchemy is SAFE because DatabaseService is constructed post-fork inside lifespan. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `docs/docs/Deployment/deployment-cold-start.mdx` | 133-137 | Introductory sentence restates LANGFLOW_GUNICORN_PRELOAD context before the finalized section body (minor duplication from placeholder merge) | ℹ️ Info | Cosmetic only — the section has an introductory "what preload does" sentence and then the "Starting with this release" paragraph. Slight redundancy; no behavioral impact. |
| `.planning/REQUIREMENTS.md` | 55, 130, 131 | CNT-03 checkbox shows [ ] (unchecked) and traceability table shows CNT-01=Pending and CNT-03=Pending while artifacts exist | ℹ️ Info | Stale tracking document only — does not affect code. CNT-01 traceability "Pending" likely refers to the authoritative CI measurement. CNT-03 checkbox simply was not updated after the guide was created. |

No blockers. No stub implementations. No hardcoded empty returns in production code. All source files parse cleanly as Python/MDX.

### Human Verification Required

#### 1. CNT-01: lfx_reference_image CI measurement

**Test:** Add the `run-benchmark-snapshot` label to the Phase 5 PR (or trigger `cold-start-benchmark` workflow manually via workflow_dispatch). Wait for the build-images job and all matrix jobs to complete. Inspect the lfx_reference_image matrix job logs for the hyperfine mean cold-start time. Commit the updated thresholds.json with the captured number.

**Expected:** mean cold-start for `lfx run /fixtures/noop_flow.json` inside the lfx-reference image (Python 3.13, UV_COMPILE_BYTECODE=1) is measurably lower than the lfx_bare uncompiled baseline (8481ms from baseline-2026-04-16.md). The baseline-2026-04-17.md already documents a 49.7% improvement from bytecode compilation for a comparable scenario, so improvement is strongly expected.

**Why human:** The lfx_reference_image thresholds.json row is a sentinel (mean_ms=0, runs=0). The CI measurement pipeline is fully wired but no `run-benchmark-snapshot` trigger has been observed for the Phase 5 branch. Cannot confirm the measurement programmatically without a CI run.

#### 2. CNT-02: repeat-build CI timing confirmation

**Test:** In the same CI run as above (or a separate `cold-start-benchmark` trigger), observe the build-images job log. Find the "Verify deps layer cache (CNT-02 repeat-build assertion)" step. Check for the line `Repeat build elapsed: Xs (CNT-02 target: <30s)` and confirm it does not exit with an error.

**Expected:** Elapsed < 30s. The --no-install-project patch on Dockerfile line 36 ensures the first uv sync layer (deps-only) is cache-stable. Only the source COPY + second uv sync (package install) re-runs, which should complete in 5-15s.

**Why human:** The CI timing assertion step runs inside the GitHub Actions docker daemon environment. The elapsed time is runner-dependent. The code is correct but only CI execution can confirm the actual timing satisfies the <30s bound.

### Gaps Summary

No blocking gaps were found. All four CNT requirements have correct implementation in the codebase. Two human verification items exist for CI measurements (CNT-01 authoritative lfx_reference_image number, CNT-02 repeat-build timing) — these require triggering the cold-start-benchmark workflow on the Phase 5 PR. The implementation is correct and the results are strongly expected to pass based on the existing baseline evidence (49.7% bytecode improvement delta confirmed on Linux CI in baseline-2026-04-17.md).

Pre-existing test failure noted in context (`test_main_py_call_is_inside_auto_login_branch`) is a Phase 04-03 regression unrelated to Phase 5 — not a Phase 5 blocker.

---

_Verified: 2026-04-18T18:00:00Z_
_Verifier: Claude (gsd-verifier)_
