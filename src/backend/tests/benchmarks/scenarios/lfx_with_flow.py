"""Primary MEAS-07 fixture (D-01): `lfx run basic_prompting`.

Per D-11a/D-12a, two variants differ ONLY in bytecode compilation state, not deps:
  - SCENARIO_LEAN: runs in the pyc-stripped image (uncompiled; cold container pays compile cost).
  - SCENARIO_PREBAKED: runs in the landed benchmarks-lean image (.pyc already present from
    UV_COMPILE_BYTECODE=1 during uv sync).
The delta isolates bytecode compile cost on a cold container (MEAS-07, reframed).

The driver's `_image_tag(variant)` mapping resolves these variant strings to actual image
tags. Do NOT assume variant="prebaked" means the landed `benchmarks-prebaked` image: per
D-12a, that image's differentiator is the wrong one. See driver.py.
"""

from __future__ import annotations

from src.backend.tests.benchmarks.scenarios import Scenario

_COMMON_ENV = {
    "LFX_BENCHMARK_CHECKPOINTS": "1",
    "LFX_BENCHMARK_CHECKPOINTS_FILE": "/tmp/checkpoints.json",  # noqa: S108
    "LFX_BENCHMARK_MOCK_LLM": "1",
}

SCENARIO_LEAN = Scenario(
    name="lfx_with_flow",
    variant="lean",
    command=["uv", "run", "lfx", "run", "/fixtures/basic_prompting.py", "--format", "text"],
    env=_COMMON_ENV,
    runs=10,
    captures_checkpoints=True,
    captures_pyinstrument=True,
    captures_importtime=True,
)

SCENARIO_PREBAKED = Scenario(
    name="lfx_with_flow_prebaked",
    variant="prebaked",
    command=["uv", "run", "lfx", "run", "/fixtures/basic_prompting.py", "--format", "text"],
    env=_COMMON_ENV,
    runs=10,
    captures_checkpoints=True,
    captures_pyinstrument=False,  # wall-clock is all we need for the MEAS-07 delta
    captures_importtime=False,
)

# Back-compat alias: some scripts iterate on SCENARIO. The lean variant is the primary.
SCENARIO = SCENARIO_LEAN
