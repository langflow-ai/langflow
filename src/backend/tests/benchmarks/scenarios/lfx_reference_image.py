"""CNT-01 lfx_reference_image scenario: cold-start of the lfx reference Dockerfile image.

Measures `lfx run <noop_flow>` executed inside the patched src/lfx/docker/Dockerfile image
(Python 3.13-slim-bookworm, UV_COMPILE_BYTECODE=1, --no-install-project layer separation).

This is a hyperfine-wrapped scenario (self_measuring=False): each hyperfine iteration
runs `docker run --rm lfx-reference lfx run /fixtures/noop_flow.json --format text` and
exits. Verified 2026-04-18 via direct read of src/lfx/src/lfx/cli/run.py: the lfx run
command calls run_flow, echoes the result, and exits. No port is bound, so a TCP
readiness probe / self-measuring supervisor is not applicable. The driver handles
timing via hyperfine wall-clock, identical to the lfx_bare scenario shape.

Unlike `benchmarks-lean`, the lfx-reference image is a production image: it contains
no `uv` binary and no baked-in `/fixtures` symlink. The scenario therefore invokes
`lfx` directly (the runtime PATH already includes `/app/.venv/bin`) and relies on the
driver's variant-aware bind mount that exposes the benchmarks fixtures at `/fixtures`.

Sentinel threshold: {"mean_ms": 0, "stddev_ms": 0, "runs": 0}  / Phase 3 D-09.
Authoritative numbers land via run-benchmark-snapshot CI label on the Phase 5 PR.

Requirement addressed: CNT-01.
Decisions: D-01 (patched in-place Dockerfile), D-13 (new scenario name and variant),
D-15 (sentinel threshold, snapshot-via-label).
"""

from __future__ import annotations

from src.backend.tests.benchmarks.scenarios import Scenario

SCENARIO = Scenario(
    name="lfx_reference_image",
    variant="lfx_reference",
    command=["lfx", "run", "/fixtures/noop_flow.json", "--format", "text"],
    env={
        "LFX_BENCHMARK_CHECKPOINTS": "1",
        "LFX_BENCHMARK_CHECKPOINTS_FILE": "/tmp/checkpoints.json",  # noqa: S108
    },
    runs=10,
    captures_checkpoints=True,
    captures_pyinstrument=False,
    captures_importtime=False,
)
