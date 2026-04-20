# Synthetic Regression Evidence (VAL-03 / D-11)

This directory contains the local-capture proof that the cold-start regression gate trips on a synthetic regression, per CONTEXT.md D-11 and ROADMAP Phase 6 success criterion 3.

## Regime

The evidence was produced by `make bench-verify-synthetic` (Makefile lines 75-87, landed via Phase 1 plan 01-06 and calibrated in Phase 6 plan 03). The target:

1. Backs up `src/lfx/src/lfx/_bench.py` to `_bench.py.orig.bak`.
2. Injects `import time as _bench_synth_time` and `_bench_synth_time.sleep(13.0)` into `_bench.py` immediately after the first `from __future__` line (awk-based injection; preserves the `from __future__` requirement of being first non-comment statement).
3. Builds the lean benchmarks container image (`podman build --build-arg BENCH_VARIANT=lean -t benchmarks-lean -f src/backend/tests/benchmarks/Dockerfile .`).
4. Force-removes any stale `benchmarks-lean-uncompiled` derivative image so the driver rebuilds it from the freshly-injected base.
5. Runs `uv run python -m src.backend.tests.benchmarks.driver --mode docker --verify --scenarios lfx_bare --output-dir /tmp/bench_synth`.
6. Asserts the driver exits non-zero (gate tripped). Prints `PASS:` on non-zero exit; `FAIL:` on zero exit.

On restoration, a trap registered before step 2 restores `_bench.py` from `_bench.py.orig.bak` unconditionally (EXIT / HUP / INT / TERM).

The 13.0s sleep duration is calibrated against the Linux-CI baseline stored in `src/backend/tests/benchmarks/thresholds.json` (lfx_bare mean 10549.93ms). With `allowed_regression_pct=15` the gate threshold is 12132.42ms, so any injection <= ~1.6s would not trip the gate on the CI baseline. A 13s injection is large enough to exceed the threshold comfortably on both Linux-CI and macOS-local hardware.

## Result

- Make target stdout ended with `PASS:` (driver exited non-zero).
- `regression_comment.md` (in this directory) is the driver's fail-mode report that would be posted to a real PR if this regression were introduced in production.
- `lfx_bare.json` (in this directory) is the hyperfine export JSON showing the regressed mean.

## Numbers

- Authoritative baseline for `lfx_bare` (from `src/backend/tests/benchmarks/thresholds.json`): mean_ms = `10549.93`, stddev_ms = `98.96`, runs = `10`.
- Regressed run (from `lfx_bare.json` `results[0].mean` x 1000): `18196`ms (10 runs, stddev 276ms on local hardware).
- Delta vs baseline: `+7646`ms / `+72.5%`, exceeding the `allowed_regression_pct: 15` threshold, so the driver correctly exits non-zero.

## Not pushed to CI

Per CONTEXT.md D-11 this evidence is captured LOCALLY and NOT pushed to CI. Reasons:

- Pushing a "break the gate on purpose" branch to CI consumes build minutes and creates a failed-workflow entry in the PR history.
- The regression detector lives in the harness driver, not in CI scheduling; local capture satisfies VAL-03 with equal fidelity.
- The committed artifacts in this directory are read-only exhibits referenced from `.planning/benchmarks/post-2026-04-20.md` under "CI gate evidence" and `.planning/benchmarks/parity-confirmation-2026-04-20.md` where appropriate.

## Provenance

- Captured locally on `IBM-MacBook-Pro.local` on `2026-04-20`.
- Operator: `ogabrielluiz`.
- Make target: `bench-verify-synthetic`.
- Driver: `src.backend.tests.benchmarks.driver` (Phase 1 plan 01-05 / 01-06).
- Thresholds source: `src/backend/tests/benchmarks/thresholds.json` (captured_ref `12750/merge@eb2272ccc711768ecb11a3c0982aa419852bb17a`).

The `.planning/` path is worktree-excluded (see `.git/info/exclude`); these artifacts do not ship via the OSS repo.
