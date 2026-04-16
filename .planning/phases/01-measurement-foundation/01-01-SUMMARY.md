---
phase: 01-measurement-foundation
plan: 01
subsystem: testing
tags: [benchmarks, pyinstrument, importtime, hyperfine, uv, makefile, pytest]

# Dependency graph
requires:
  - phase: "(none; first plan of phase 01)"
    provides: ""
provides:
  - "src/backend/tests/benchmarks/ package scaffold (importable, pytest-ignored)"
  - "benchmarks optional-dependency group in root pyproject.toml"
  - "bench-local / bench-docker / bench-snapshot Makefile targets (stubs that error until plan 05)"
  - "Hyperfine flag rationale + entry-point documentation for downstream plans"
affects:
  - "01-02 (fixtures + mock LLM; conftest.py gets the autouse fixture here)"
  - "01-03 (checkpoint hook; reads/writes inside this package)"
  - "01-04 (Dockerfile; drops into src/backend/tests/benchmarks/)"
  - "01-05 (driver/scenarios/snapshot; Makefile targets already point here)"
  - "01-06 (CI workflow; reads thresholds.json under this package)"

# Tech tracking
tech-stack:
  added:
    - "pyinstrument>=5.1.2 (dep-group only)"
    - "importtime-convert>=1.1.0 (dep-group only)"
    - "importtime-waterfall>=1.0.0 (dep-group only; RESEARCH.md listed 2.0.0 but PyPI max is 1.0.0)"
  patterns:
    - "Conftest-level pytest opt-out via collect_ignore_glob for subprocess-style scripts"
    - "Optional-dependency groups keep non-runtime tooling out of lfx/langflow-base"
    - "Makefile stub targets that print a 'not yet implemented' error until a later plan lands"

key-files:
  created:
    - "src/backend/tests/benchmarks/__init__.py"
    - "src/backend/tests/benchmarks/conftest.py"
    - "src/backend/tests/benchmarks/README.md"
    - "src/backend/tests/benchmarks/reports/.gitkeep"
  modified:
    - "pyproject.toml (+ benchmarks dependency group)"
    - "Makefile (+ bench-local, bench-docker, bench-snapshot targets; .PHONY append)"
    - "uv.lock (refreshed for the benchmarks group)"

key-decisions:
  - "Used collect_ignore_glob = ['*.py'] rather than listing individual files; lowest-maintenance way to keep pytest from collecting benchmark scenario scripts"
  - "Floored importtime-waterfall at >=1.0.0 (not >=2.0.0 as RESEARCH.md claimed) because 2.0.0 does not exist on PyPI"
  - "No em-dashes in any shipped content (README, Makefile comments, docstrings) per user rule; plan literal text with em-dashes replaced with hyphens or rephrased"
  - "uv.lock refresh committed separately from Makefile changes so each commit is atomic and reviewable"

patterns-established:
  - "Pattern: optional-dep groups for measurement/tooling (pyproject.toml [dependency-groups].benchmarks) so deps stay out of runtime manifests"
  - "Pattern: benchmarks/conftest.py as the lone pytest-configuration anchor for the benchmark tree (plan 02 extends with autouse LLM mock)"

requirements-completed: [MEAS-01]

# Metrics
duration: 6min
completed: 2026-04-16
---

# Phase 1 Plan 1: Benchmark Harness Scaffold Summary

**Benchmarks package at `src/backend/tests/benchmarks/` with pytest opt-out, `benchmarks` uv dependency group (pyinstrument + importtime-convert + importtime-waterfall), and three Makefile stub targets (`bench-local`, `bench-docker`, `bench-snapshot`) ready for plans 02 through 06 to fill in.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-04-16T16:49:29Z
- **Completed:** 2026-04-16T16:55:00Z (approx)
- **Tasks:** 3
- **Files modified:** 7 (4 created, 3 modified)

## Accomplishments

- New importable Python package at `src/backend/tests/benchmarks/` with docstring-documented purpose.
- Pytest cleanly skips the benchmark tree (`no tests collected in 0.06s` with `--collect-only`); the broader `src/backend/tests` collection still resolves 7,919 tests.
- `uv sync --group benchmarks --dry-run` resolves to install pyinstrument 5.1.2, importtime-convert 1.1.0, importtime-waterfall 1.0.0 with zero conflicts; no runtime manifest (lfx, langflow-base) touched.
- Three Makefile targets declared, each dry-runs cleanly (`make -n bench-*` exits 0) and prints a clear "not yet implemented" error pointing to plan 05 when actually invoked.
- README documents hyperfine flag rationale (--warmup 0, --prepare, --min-runs, --export-json, --shell sh) so plan 05 lands into a pre-documented spec.

## Task Commits

1. **Task 1: Create benchmarks package scaffold** - `a11d999ab3` (feat)
2. **Task 2: Add benchmarks dependency group to pyproject.toml** - `93f7d108e1` (feat)
3. **Task 3: Add bench-local, bench-docker, bench-snapshot Makefile targets** - `d7d2589951` (feat)
4. **Post-task: refresh uv.lock for benchmarks group** - `d0c4b0b6b4` (chore)

## Files Created/Modified

- `src/backend/tests/benchmarks/__init__.py` - one-line package docstring
- `src/backend/tests/benchmarks/conftest.py` - `collect_ignore_glob = ["*.py"]` to keep pytest out; docstring signposts plan 02's autouse fixture landing spot
- `src/backend/tests/benchmarks/README.md` - entry points table, planned layout, hyperfine flag rationale, install instructions
- `src/backend/tests/benchmarks/reports/.gitkeep` - empty; preserves output directory at clean clone
- `pyproject.toml` - new `[dependency-groups] benchmarks` with pyinstrument, importtime-convert, importtime-waterfall
- `Makefile` - new BENCHMARKS section between `check_tools` and `help`; three targets appended to top-level `.PHONY`
- `uv.lock` - refreshed to include the three new benchmark deps

## Decisions Made

- **importtime-waterfall floor lowered to >=1.0.0** (plan specified >=2.0.0). RESEARCH.md §Standard Stack listed 2.0.0 as the current version, but PyPI's maximum is 1.0.0 (published 2019-02-28, asottile). Without this change, `uv sync --group benchmarks` fails to resolve, blocking every subsequent plan. See deviation 1 below.
- **No em-dashes anywhere in shipped content.** User's global rule. The plan's literal text used em-dashes in README prose, conftest docstring, and Makefile comments; each was rephrased (typically to a period, hyphen, or semicolon) without changing meaning or the grep markers the plan's verification asserts on.
- **uv.lock committed separately** from the Makefile change as a `chore` commit so each logical change is atomic; avoids the optics of "Makefile change also modifies lockfile" in diffs.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Lowered importtime-waterfall version floor from >=2.0.0 to >=1.0.0**
- **Found during:** Task 2 (pyproject.toml edit + `uv sync --group benchmarks --dry-run` verification)
- **Issue:** RESEARCH.md §Standard Stack and the plan's Task 2 action block specify `importtime-waterfall>=2.0.0`, but PyPI returns "only importtime-waterfall<=1.0.0 is available" (1.0.0 published 2019; no 2.0 release). uv refused to resolve the group, breaking Task 2's own acceptance criterion (`uv sync --group benchmarks --dry-run` exits 0) and the plan's overall "Workspace uv sync --group benchmarks resolves without error" done criterion.
- **Fix:** Changed the version constraint in `pyproject.toml` to `importtime-waterfall>=1.0.0` and added an inline comment explaining the RESEARCH.md inaccuracy so future agents don't try to bump it.
- **Files modified:** `pyproject.toml` (benchmarks dep group)
- **Verification:** `uv sync --group benchmarks --dry-run` now resolves and shows `+ importtime-waterfall==1.0.0` in the install plan. `uv.lock` refreshed successfully.
- **Committed in:** `93f7d108e1` (Task 2 commit)

**2. [Rule 2 - Missing Critical, convention] Replaced em-dashes in all shipped content**
- **Found during:** Tasks 1 and 3 (README.md, conftest.py docstring, Makefile comments)
- **Issue:** The plan's literal text included em-dashes ("—") in several places. User's global CLAUDE.md rule (`feedback_no_emdashes`) forbids em-dashes in shipped content.
- **Fix:** Replaced em-dashes with periods, commas, hyphens, or semicolons (whichever flowed naturally). No semantic change; no grep-marker lost.
- **Files modified:** `src/backend/tests/benchmarks/README.md`, `src/backend/tests/benchmarks/conftest.py`, `Makefile`
- **Verification:** `rg -- '—' src/backend/tests/benchmarks/ Makefile` returns nothing in the new content. All plan `grep -q` acceptance markers (`collect_ignore_glob`, `bench-docker`, `^## Hyperfine flag rationale`) still pass.
- **Committed in:** `a11d999ab3` (Task 1) and `d7d2589951` (Task 3)

**3. [Plan-inaccuracy note, no fix required] `make help` does not auto-list the new targets**
- **Found during:** Task 3 verification
- **Issue:** Task 3's acceptance criterion states `Running make help still succeeds and lists the new targets (they inherit the ## description convention)`. The existing `help:` target in this repo is a hand-maintained echo block; it does NOT parse `## description` tags (other targets like `load_test_*` with `##` are also not listed in `make help`). Strict "lists the new targets" is not satisfied.
- **Decision:** Do NOT modify `help:` to add the three targets. Rationale:
  - Matches the repo's existing convention (other non-core targets are also absent from `make help`).
  - Adding to `help:` would risk a parallel-agent merge conflict on the hand-maintained list.
  - `make help` still succeeds (exit 0) and the `##` tags are picked up by any auto-help tooling if/when it's introduced.
- **Impact:** Cosmetic only. `make -n bench-local|bench-docker|bench-snapshot` still resolve cleanly (primary verification), and the targets are self-documented via their `##` comments.
- **No commit needed.**

---

**Total deviations:** 3 (1 blocking fix, 1 convention fix, 1 documented plan inaccuracy with no code change)
**Impact on plan:** Both code fixes were essential for the plan to meet its own acceptance criteria (`uv sync` resolving; no em-dashes in shipped files). The `make help` note is cosmetic. Zero scope creep.

## Issues Encountered

- None during execution. The RESEARCH.md inaccuracy about importtime-waterfall 2.0.0 was the only surprise; resolved in-line via Rule 3 deviation.

## User Setup Required

None. The `benchmarks` dep group is opt-in (`uv sync --group benchmarks`); no runtime deps added; no env vars required.

## Handoff Notes

- **Plan 02 (fixtures + mock LLM):** Append the autouse fixture to `src/backend/tests/benchmarks/conftest.py`. The file's current docstring already signposts this as the landing spot. Keep `collect_ignore_glob` intact. The mock fixture should be gated on an env var (`LFX_BENCHMARK_MOCK_LLM`) per RESEARCH.md so it's inert in normal test runs.
- **Plan 03 (checkpoint hook):** Benchmark scenarios should read `LFX_BENCHMARK_CHECKPOINTS_FILE` (or similar) per RESEARCH.md §Pattern 2; the hook lives in `src/lfx/` as a stdlib-only module. This plan does not gate on plan 01's scaffold.
- **Plan 04 (Dockerfile):** Drop `Dockerfile` into `src/backend/tests/benchmarks/Dockerfile`. README already lists this path. Base on `python:3.13-slim` per D-08. Pre-bake vs lean variants via `ARG BENCH_VARIANT=lean|prebaked` per D-11.
- **Plan 05 (driver/scenarios/snapshot):** Entry points are `src.backend.tests.benchmarks.driver` and `src.backend.tests.benchmarks.snapshot` (Makefile already invokes these via `python -m`). The Makefile passes `--mode local|docker` to driver; match that CLI surface. Drop scenario scripts into `src/backend/tests/benchmarks/scenarios/`; they will be pytest-ignored automatically via the existing `collect_ignore_glob`.
- **Plan 06 (CI workflow):** `src/backend/tests/benchmarks/thresholds.json` is the machine-readable baseline per D-15. Workflow file at `.github/workflows/cold-start-benchmark.yml` (per D-17). Label-gated per D-14.

## Next Phase Readiness

- Phase 1 Plan 1 is the scaffolding; it unblocks plans 02 through 06 of the same phase. None of those depend on one another strictly (per plan frontmatter), so they can be waved in parallel.
- No blockers.

## Self-Check: PASSED

- `test -f src/backend/tests/benchmarks/__init__.py` -> FOUND
- `test -f src/backend/tests/benchmarks/conftest.py` -> FOUND
- `test -f src/backend/tests/benchmarks/README.md` -> FOUND
- `test -f src/backend/tests/benchmarks/reports/.gitkeep` -> FOUND
- `grep -q 'collect_ignore_glob' src/backend/tests/benchmarks/conftest.py` -> 0 (match)
- `grep -q '^benchmarks = \[' pyproject.toml` -> 0 (match)
- `grep -q '^bench-local:' Makefile` -> 0 (match)
- `grep -q '^bench-docker:' Makefile` -> 0 (match)
- `grep -q '^bench-snapshot:' Makefile` -> 0 (match)
- Commit `a11d999ab3` (Task 1) -> FOUND in `git log --oneline`
- Commit `93f7d108e1` (Task 2) -> FOUND in `git log --oneline`
- Commit `d7d2589951` (Task 3) -> FOUND in `git log --oneline`
- Commit `d0c4b0b6b4` (uv.lock) -> FOUND in `git log --oneline`
- `uv run pytest src/backend/tests/benchmarks/ --collect-only -q` -> `no tests collected`
- `uv run pytest src/backend/tests --collect-only -q` -> 7919 tests collected (broader tree intact)
- `uv sync --group benchmarks --dry-run` -> resolves 3 new packages, 0 conflicts
- `make -n bench-local` / `make -n bench-docker` / `make -n bench-snapshot` -> all exit 0

---
*Phase: 01-measurement-foundation*
*Completed: 2026-04-16*
