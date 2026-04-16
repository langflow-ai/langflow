"""Bare-boot scenario: `lfx run <no-op flow>` (D-03).

Exercises the full cold-start path (service init + component index warmup)
with zero LLM/flow work. Locked over `lfx --help` because --help short-circuits
before initialize_services() / get_and_cache_all_types_dict().
"""

from __future__ import annotations

from src.backend.tests.benchmarks.scenarios import Scenario

SCENARIO = Scenario(
    name="lfx_bare",
    variant="lean",
    command=["uv", "run", "lfx", "run", "/fixtures/noop_flow.py", "--format", "text"],
    env={
        "LFX_BENCHMARK_CHECKPOINTS": "1",
        "LFX_BENCHMARK_CHECKPOINTS_FILE": "/tmp/checkpoints.json",  # noqa: S108
    },
    runs=10,
    captures_checkpoints=True,
    captures_pyinstrument=True,
    captures_importtime=True,
)
