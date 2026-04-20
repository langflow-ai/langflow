---
phase: 06-validation-and-publication
plan: 03
subsystem: validation-ci-gate
tags: [validation, ci-gate, synthetic-regression, VAL-03]

# Dependency graph
requires:
  - phase: 01-measurement-foundation
    provides: "bench-verify-synthetic Makefile target (plan 01-06) and driver exit-non-zero behavior (plan 01-05)"
  - phase: 06-validation-and-publication
    provides: "thresholds.json fresh post-Phase-6 snapshot (06-01 VAL-01) as the baseline for gate threshold math"
provides:
  - "Local synthetic-regression evidence at .planning/phases/06-validation-and-publication/synthetic-regression-evidence/ (3 files: regression_comment.md, lfx_bare.json, README.md) proving the gate trips on a calibrated +13s injection (+72.5% delta, well over the 15% tolerance)"
  - "Verify-mode CI run 24666601910 against HEAD 391f6117b8 with all 4 authoritative matrix cells green"
  - "Makefile bench-verify-synthetic target now correctly (a) injects AFTER the first from __future__ line via awk, (b) sleeps 13.0s to exceed the Linux-CI baseline threshold on both CI and macOS-local hardware, (c) force-rebuilds the benchmarks-lean-uncompiled derivative image so fresh injections are not shadowed by stale cached derivatives"
affects:
  - 06-05 (backfills the <verify-run-id-from-06-03> placeholder in .planning/benchmarks/post-2026-04-20.md and .planning/benchmarks/parity-confirmation-2026-04-20.md with the run URL https://github.com/langflow-ai/langflow/actions/runs/24666601910)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Calibrated injection: sleep duration sized against the Linux-CI baseline stored in thresholds.json, not against local hardware; math: baseline 10549.93ms * 1.15 gate = 12132.42ms, so injection must exceed ~1.6s on CI-speed hardware. 13.0s gives 1640ms margin on top of CI-speed and 6s on top of macOS-local."
    - "Awk-based post-future injection: preserves the Python language rule that from __future__ must be the first non-docstring statement. Previous printf-based prepend created a SyntaxError at import time, silently masking gate-detection behavior."
    - "Derivative-image cache-busting: driver's lean scenario uses benchmarks-lean-uncompiled (a thin FROM benchmarks-lean + .pyc strip). --skip-build reuses the wrapper whether it is fresh or not. Dropping --skip-build AND removing the wrapper image before the run ensures the driver rebuilds from the freshly injected base."
    - "Local-only capture per D-11: the regression detector lives in the harness driver, not in CI scheduling, so local evidence is equivalent to CI evidence for gate-correctness proof. Saves GHA minutes and avoids a failed-workflow entry in PR history."

key-files:
  created:
    - .planning/phases/06-validation-and-publication/synthetic-regression-evidence/README.md
    - .planning/phases/06-validation-and-publication/synthetic-regression-evidence/lfx_bare.json
    - .planning/phases/06-validation-and-publication/synthetic-regression-evidence/regression_comment.md
    - .planning/phases/06-validation-and-publication/06-03-SUMMARY.md
  modified:
    - Makefile

key-decisions:
  - "[Phase 06-03] Sleep calibration: bumped from 0.3s to 13.0s after discovering 0.3s cannot trip the CI gate on any hardware (gate threshold 12132.42ms on baseline 10549.93ms). Result: regressed lfx_bare ran at 18196ms mean, +72.5% delta, well over 15% tolerance. Driver correctly exits non-zero."
  - "[Phase 06-03] Injection point fix: moved synthetic-sleep insertion from before line 1 to after the first from __future__ line via awk. Prior printf-based prepend placed 'import time; time.sleep(0.3)' before the module docstring and before 'from __future__ import annotations', which is a SyntaxError (future-imports must be first). The import error made hyperfine succeed with a ~1s 'cold start' that never actually executed the sleep, masking gate-detection behavior entirely."
  - "[Phase 06-03] Stale-derivative-image bug: first post-calibration run still failed because the driver was invoked with --skip-build, and benchmarks-lean-uncompiled was a stale cached image from an earlier broken experiment (old printf injection). Fix: drop --skip-build AND force-rmi benchmarks-lean-uncompiled before driver invocation. Adds ~5s to the run for the thin wrapper rebuild."
  - "[Phase 06-03] VAL-03 accepted on 4/4 authoritative-cells-green + gate-step-success outcome despite workflow-level conclusion of 'cancelled'. The cancellation came from the langflow_run_http_ready sentinel matrix cell timing out at its 5-minute budget (known-flaky since before Phase 6; thresholds.json records 0 runs for it and workflow file line 11 calls it 'known-broken'). Per D-12, sentinel cells use continue-on-error: true; per D-16 this is a pre-existing sentinel failure (not a green-to-not-green regression) and therefore not a blocker. The Aggregate job's 'Verify mode - final gate summary' step succeeded (no regression_comment files aggregated), confirming the authoritative gate evaluated clean."
  - "[Phase 06-03] Verify-run-id recorded here for 06-05 backfill rather than touching VAL-01 post-doc or VAL-02 parity doc directly. 06-05 depends on 06-01, 06-02, and 06-03, so the backfill lives there."
  - "[Phase 06-03] Makefile changes committed as two separate fixes rather than one to keep the commit log legible: f3266a74cb covers injection-point + sleep-duration calibration (two related but distinct defects in the original spec), 6866a32471 covers the stale-derivative-image issue discovered only after the first post-calibration run failed."

patterns-established:
  - "Calibrate synthetic regressions against the CI baseline, not local hardware. Linux-CI runners and macOS-local hardware differ by ~10x for these scenarios; a threshold-relative calibration works on both."
  - "When a Makefile target invokes a build step AND a --skip-build-flagged consumer of a derived image, the derived image must either be explicitly rebuilt or force-removed to prevent stale caches from shadowing fresh inputs."

requirements-completed: [VAL-03]

# Metrics
duration: ~90 min (including 3 podman-build attempts: 1 OOM, 1 cached-derivative-staleness, 1 PASS)
completed: 2026-04-20
---

# Phase 6 Plan 03: CI Regression Gate Verification (VAL-03) Summary

**Proved the cold-start regression gate trips on a calibrated +13s synthetic regression (regressed lfx_bare at 18196ms vs 10549.93ms baseline, +72.5% delta) via `make bench-verify-synthetic`, and ran the verify-mode Cold Start Benchmark workflow on PR #12750 (run `24666601910`) with all 4 authoritative matrix cells (lfx_bare, lfx_with_flow, lfx_with_flow_prebaked, langflow_run_no_change_restart) green. Makefile needed three in-scope fixes (injection point, sleep calibration, stale-derivative-image cache-bust) before the local gate exercised the fresh injection correctly.**

## Performance

- **Duration:** ~90 min
- **Started:** 2026-04-20 (HEAD a8aaf7988a after 06-04 SUMMARY committed)
- **Completed:** 2026-04-20
- **Tasks:** 3 (checkpoint:human-action, auto, checkpoint:human-verify), run autonomously after one initial user-approved checkpoint on calibration choice
- **Files created:** 4 (3 evidence files + this SUMMARY)
- **Files modified:** 1 (Makefile)

## Accomplishments

### Local synthetic-regression proof (Tasks 1 + 2)

Ran `make bench-verify-synthetic` after landing three Makefile fixes. The final successful run:

- **Image builds:** `benchmarks-lean` rebuilt fresh from a _bench.py containing an awk-injected `import time as _bench_synth_time; _bench_synth_time.sleep(13.0)` after the `from __future__` line. Derived `benchmarks-lean-uncompiled` force-rebuilt by the driver after the Makefile removed the stale cached copy.
- **Hyperfine (lfx_bare, 10 runs):** mean 18.196s, stddev 0.276s, range 17.973s - 18.876s.
- **Driver regression comment (`regression_comment.md`):** `| lfx_bare | 10549.9 | 18195.7 | +72.5% | 15% | FAIL |`. Driver exited non-zero as required.
- **Makefile final line:** `PASS: driver exited non-zero on synthetic regression. Gate is wired correctly.`
- **Restoration:** trap fired on exit; `git diff src/lfx/src/lfx/_bench.py` empty; `_bench.py.orig.bak` removed.

Evidence committed at `391f6117b8` to `.planning/phases/06-validation-and-publication/synthetic-regression-evidence/` with three files: `README.md`, `lfx_bare.json`, `regression_comment.md`. Not pushed to CI per D-11.

### Verify-mode CI run (Task 3)

**Run ID:** `24666601910`
**URL:** https://github.com/langflow-ai/langflow/actions/runs/24666601910
**Trigger:** pull_request event on HEAD `391f6117b8` (branch `cold-start-improvements-v2`, PR #12750); the `run-benchmarks` label was already on the PR from a prior cycle and re-triggered automatically on push.
**Start:** 2026-04-20T12:31:25Z
**End:** 2026-04-20T12:48:05Z (~17 min)
**Workflow top-level conclusion:** `cancelled` (see D-12 / D-16 interpretation below).
**Authoritative gate step outcome:** `success` (Aggregate job > "Verify mode - final gate summary": no regression_comment*.md files aggregated, no regression).

Per-cell outcomes:

| Cell | Authoritative? | Conclusion | D-16 compare vs prior run (24610838644 @ 9230e1e6) |
| --- | --- | --- | --- |
| Resolve mode | support | success | success (no change) |
| Build images | support | success | IMPROVED (prior: failure) |
| bench:lfx_bare | authoritative | success | IMPROVED (prior: skipped due to Build images fail) |
| bench:lfx_with_flow | authoritative | success | IMPROVED (prior: skipped) |
| bench:lfx_with_flow_prebaked | authoritative | success | IMPROVED (prior: skipped) |
| bench:langflow_run_no_change_restart | authoritative | success | IMPROVED (prior: skipped) |
| bench:langflow_run_http_ready | sentinel | cancelled | pre-existing sentinel: was SKIPPED in prior run, has 0 runs in thresholds.json, workflow line 11 documents it as "known-broken". Not a green-to-not-green regression under D-16. |
| bench:lfx_reference_image | sentinel | success | IMPROVED (prior: skipped) |
| Aggregate | support | success | IMPROVED (prior: success but on empty matrix) |

**Regression comments on PR:** 0 (checked via `gh pr view 12750 --json comments` filtered on "Cold Start Benchmark" / "regression_comment" / "allowed_regression").

**D-12 / D-16 interpretation:** The workflow top-level conclusion is `cancelled` because GitHub Actions propagates matrix-cell `cancelled` states to the workflow even when `continue-on-error: true` is set at the matrix level (continue-on-error swallows `failure` but not `cancelled`). The `cancelled` state originated from the `langflow_run_http_ready` sentinel timing out at its 5-minute budget (a known-flaky scenario before Phase 6; thresholds.json records it with 0 runs and the workflow comment at line 11 calls it "known-broken scenario"). Per D-12 the plan accepts sentinel-cell non-green results as non-blocking; per D-16 the prior run on this branch had this sentinel SKIPPED (not green), so the cancellation is not a green-to-not-green regression. The authoritative gate step succeeded with all 4 authoritative matrix cells green, which is the substantive meaning of "CI regression gate runs green" in the VAL-03 success criteria.

### Makefile fixes (committed as 2 commits)

- **`f3266a74cb fix(bench): correct synthetic-regression injection point and calibrate against Linux-CI baseline (VAL-03)`** - Switched from `printf | cat` prepend to `awk '{print} /^from __future__ / && !done { print synth }'` injection after the first future-import line. Bumped sleep from 0.3s to 13.0s so the regressed mean exceeds the threshold on both CI (10549.93ms baseline * 1.15 = 12132.42ms gate) and macOS-local (~773ms baseline unscaled) hardware. Renamed the synthetic-sleep variable to `_bench_synth_time` to avoid any collision with downstream `import time` usage in `_bench.py`.
- **`6866a32471 fix(bench): force-rebuild uncompiled derivative image so the fresh injection actually runs (VAL-03)`** - Dropped `--skip-build` on the driver call and added a `podman rmi -f benchmarks-lean-uncompiled` step between the base image build and the driver invocation. Root cause: the driver's lean scenario uses `benchmarks-lean-uncompiled` (a thin wrapper image that strips .pyc from `benchmarks-lean`); with `--skip-build` the driver just checks that the wrapper image exists and reuses it, so a stale cached copy from an earlier broken experiment was reused and the fresh base image was never exercised.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Synthetic-regression Makefile target calibrated for local hardware instead of CI baseline**

- **Found during:** Pre-Task-1 readiness check (user surfaced this one in the checkpoint).
- **Issue:** Original `printf 'import time\\ntime.sleep(0.3)\\n' && cat ...` injection placed the synthetic sleep at line 1 of `_bench.py`, BEFORE the module docstring and BEFORE `from __future__ import annotations`. Python rejects future-imports that are not the first non-docstring statement, so the injected module raised SyntaxError at import time. Hyperfine still succeeded because lfx CLI start on macOS is dominated by interpreter boot (`~1s`); the synthetic sleep never actually ran, and the driver compared the ~1s regressed mean to the 10.55s baseline and correctly decided there was no regression. Gate behavior was not what the target claimed to prove. Additionally, even if the injection had been valid Python, a 0.3s sleep cannot exceed the 15% tolerance on the 10.55s Linux-CI baseline (threshold 12.13s, baseline-plus-injection at best 10.85s).
- **Fix:** Awk injection after first `from __future__` line (preserves Python language rule); sleep bumped to 13.0s (exceeds threshold on both CI and local hardware by comfortable margins).
- **Files modified:** Makefile
- **Commit:** f3266a74cb

**2. [Rule 1 - Bug] Stale benchmarks-lean-uncompiled derivative image shadows fresh injection**

- **Found during:** First post-calibration run of `make bench-verify-synthetic`. Hyperfine reported a ~1s mean (instead of the expected ~13.8s), and the log contained a SyntaxError traceback showing `from __future__` at line 21 (which should be line 19 after awk injection with 2 lines AFTER it; line 21 for `from __future__` means 2 lines were inserted BEFORE it, which is the OLD broken behavior).
- **Issue:** The Makefile rebuilds the `benchmarks-lean` image before invoking the driver, but the driver is invoked with `--skip-build`. For the `lfx_bare` scenario (variant="lean") the driver uses `benchmarks-lean-uncompiled`, which is a thin `FROM benchmarks-lean` wrapper the driver builds on demand. With `--skip-build` the driver only verifies that `benchmarks-lean-uncompiled` exists and reuses whatever is cached; in this case a stale copy from an earlier experiment (old printf injection) was cached.
- **Fix:** Drop `--skip-build` from the driver call AND force-remove `benchmarks-lean-uncompiled` before invocation so the driver rebuilds the wrapper from the freshly-built base. Adds ~5s to the run for the FROM + find-delete.
- **Files modified:** Makefile
- **Commit:** 6866a32471

**3. [Rule 3 - Blocking] Podman machine memory exhaustion during large-context build**

- **Found during:** First retry of `make bench-verify-synthetic` after applying fix 1.
- **Issue:** `podman build` on the langflow repo context OOMed at `copier: listing extended attributes of ... Social Media Agent.json`. Podman machine was configured with 2GiB and had 138 images (35.63GB reclaimable) plus dead build-cache metadata accumulated during iterative work on the Makefile.
- **Fix:** `podman system prune -f` reclaimed 178.6GB of build cache + unused images. Next build completed cleanly. No Makefile or Dockerfile change needed; a permanent fix would be a root-level `.dockerignore` that mirrors the richer `src/backend/tests/benchmarks/.dockerignore`, but that is out-of-scope for VAL-03.
- **Files modified:** None (environmental fix; out-of-scope for commit).
- **Commit:** N/A

### Acceptance interpretation difference

**VAL-03 accepted on 4/4 authoritative-cells-green + Aggregate-gate-step-success rather than on workflow-level `conclusion == "success"`.** The plan's strict acceptance text (line 328) requires `gh run view <run-id> --json conclusion` to return `success`, but the plan's D-12 rationale (line 289, line 17 truth) explicitly states sentinel cells are not blockers. When GitHub Actions sets the workflow conclusion to `cancelled` because of a sentinel cancellation (matrix `continue-on-error: true` swallows `failure` but not `cancelled`), the strict acceptance text contradicts the D-12 rationale. Under D-12 + D-16 + the plan's "authoritative cells green = gate green" rule, VAL-03 is satisfied. Under strict D-16 "NEW failures vs prior run are blockers" evaluation, the `langflow_run_http_ready` cancellation is not NEW (it was SKIPPED in the prior run, not green) and thus not a blocker.

Per user instruction "no more checkpoints unless D-16 violation": proceeded, as this is not a D-16 violation.

## Known Stubs

None.

## Self-Check: PASSED

- Makefile commit `f3266a74cb` verified present (`git log --oneline --all | grep f3266a74cb`).
- Makefile commit `6866a32471` verified present.
- Evidence commit `391f6117b8` verified present.
- File `.planning/phases/06-validation-and-publication/synthetic-regression-evidence/README.md` verified present.
- File `.planning/phases/06-validation-and-publication/synthetic-regression-evidence/lfx_bare.json` verified present and parses as JSON.
- File `.planning/phases/06-validation-and-publication/synthetic-regression-evidence/regression_comment.md` verified present.
- Run ID `24666601910` verified reachable via `gh run view 24666601910 --json status,conclusion,url`.
