# Langflow / lfx Cold Start Improvements

## What This Is

A measurement-driven effort to reduce cold-start time for `lfx run` (primary) and `langflow run` (secondary), so teams integrating lfx inside watsonX.orchestrate get acceptable first-request latency when their containers scale from zero. The project builds on the existing cold-start work in release-1.9.0 (component index order-of-magnitude win, lfx CLI lazy imports) rather than starting from scratch.

## Core Value

Faster cold start for lfx run on containerized/serverless deployments, without breaking flow file format, Python API surface, or runtime behavior parity.

## Requirements

### Validated

<!-- Already in release-1.9.0, the base branch for this work. -->

- ✓ Component index load is an order of magnitude faster than pre-optimization baseline — release-1.9.0
- ✓ lfx CLI uses lazy imports (PR #10739) to avoid eager load of serve/run deps — release-1.9.0
- ✓ lfx package has no runtime dependency on langflow backend — keeps embedding lightweight — release-1.9.0
- ✓ Services layer and component index are the foundation for flow execution — load-bearing, must be preserved

<!-- Validated during this milestone. -->

- ✓ Cold-start benchmarking harness covers `lfx run` base boot, `lfx run <flow>` first-execution, and `langflow run` equivalents — Phase 1
- ✓ Baseline numbers captured for cold container / clean venv / representative flow scenarios — Phase 1
- ✓ Profiling surfaced dominant hotspots (import time, service init, component index warmup) — Phase 1
- ✓ Hotspots addressed with in-code improvements while preserving services and component-index semantics — Phases 2, 3, 4
- ✓ Cold-start-optimized deployment guidance published at `docs/docs/Deployment/deployment-cold-start.mdx`, Dockerfile patched, LANGFLOW_GUNICORN_PRELOAD default flipped after fork-safety audit — Phase 5

### Active

<!-- This milestone. Measurement first, then evidence-driven fixes. -->

- [ ] Re-measure and confirm improvement against baseline; publish numbers — Phase 6

### Out of Scope

<!-- Explicit boundaries to prevent scope creep. -->

- New CLI subcommands whose sole purpose is warm-up or prebuild (e.g. `lfx warm`, `lfx build-image`) — we want improvements, not new features; add only if in-code fix is impossible
- Changes to flow file format (JSON/YAML spec) — users have flows in the wild; migrations are not in scope
- Changes to public Python API surface (`from lfx import ...`) — library consumers depend on stability
- Changes that alter runtime behavior of flows (output, side effects, ordering) — latency changes only
- Platform-specific optimization for AWS Lambda / Cloud Run — watsonX.orchestrate is the primary target; other platforms receive documentation only
- Adding runtime dependencies to lfx — keeping it dep-free is the value proposition

## Context

- **Product.** Langflow is a framework for building LLM-powered flows (FastAPI + React monorepo). `lfx` is a sibling Python package at `src/lfx/` that exposes runtime primitives with no dependency on the langflow backend, so it can be embedded lightly.
- **Deployment target.** `lfx run` is integrated into IBM's watsonX.orchestrate product. The exact infrastructure is not confirmed but is most likely containers on k8s. Cold container scale-from-zero is the worst-case path; every cold container pays full import cost plus any first-flow dep install.
- **Runtime dependency pattern.** lfx itself ships with no deps, but executing a flow typically triggers just-in-time installation of provider packages (openai, langchain, vector stores, document loaders). Whether that install is cached across containers is one of the things the measurement work must answer.
- **Prior work already in baseline.** PR #10739 (lazy imports in lfx CLI) and the component index order-of-magnitude improvement are already on release-1.9.0 — this project picks up from that line, not from an unoptimized baseline.
- **Codebase map.** Detailed architecture, conventions, and concerns live in `.planning/codebase/` (local only, not committed). `CONCERNS.md` already captures suspected hotspots including heavy top-level imports (numpy/pandas/langchain_*), module-level side effects, and service initialization fan-out.
- **Branch.** Work lives on `cold-start-improvements-v2`, based on `release-1.9.0`.

## Constraints

- **Tech stack**: Python 3, managed via `uv`. Do not add runtime dependencies to lfx. Frontend is React/TypeScript but out of scope for this milestone unless a frontend-triggered backend warmup is discovered.
- **Compatibility**: Flow file format frozen. Public Python API surface frozen. CLI flags should stay stable; changes require explicit review.
- **Runtime parity**: Observable flow behavior (output, ordering, side effects) must match pre-change state. Only latency characteristics should change.
- **Load-bearing subsystems**: Services layer and component index are foundational for many features. Changes in those areas require extra care and behavioral parity verification.
- **Scope philosophy**: Improvements over new features. Prefer removing work on the startup path to adding warmup machinery.
- **Timeline**: Not a constraint. Quality of work matters more than speed.

## Known Test Pitfalls

- **`src/lfx/tests/unit/test_serve_simple.py` hangs indefinitely.** Do NOT run `cd src/lfx && uv run pytest tests/unit/` (broad glob) — it will hang on this file. Always scope lfx test runs to specific files (e.g., `cd src/lfx && uv run pytest tests/unit/test_component_index.py -v`). When verifying a phase, enumerate the test files touched rather than running the whole tree.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Base on `release-1.9.0`, not `main` | Avoid mixing with unrelated CVE-fix work on `cve-fixes`; keep PRs focused | Pending |
| Measurement first, fixes second | The user already tried intuition-led fixes successfully; the remaining wins need evidence | Pending |
| lfx stays dependency-free | Core value proposition for embedded integrations like watsonX.orchestrate | ✓ Good |
| `.planning/` is locally excluded, never committed | Langflow is OSS; GSD scaffolding does not belong in shared history | Pending |
| Prefer in-code improvements over new CLI surface | Scope philosophy set by user: no new features for the sake of warmup | Pending |
| watsonX.orchestrate base image is not a concern | User confirmed Phase 5 Dockerfile can target a generic modern Python base; no IBM-specific constraints to plan around | ✓ Good |
| `lfx run` in production invokes `run_flow()` directly, not `serve_app.py` | User confirmed; Phase 4 (FastAPI lifespan restructuring) primarily benefits `langflow run`, not the lfx path; applies to Phase 4 scoping | ✓ Good |
| Deployed Python version is 3.13 or 3.14 | `asyncio.Lock()` at module import time raises `RuntimeError`, so IDX-01's lazy-property pattern is a hard requirement, not a nice-to-have | ✓ Good |
| `LANGFLOW_GUNICORN_PRELOAD=true` default flip is acceptable if it improves performance | User green-lights flipping the default; still gated on fork-safety verification (SQLAlchemy `after_fork` + `engine.dispose()` + asyncio lock reset in workers) in Phase 5 | Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-18 after Phase 5 (Container and Deployment Optimization)*
