"""Primary MEAS-07 fixture: `lfx run basic_prompting`.

Per D-11a/D-12a, two variants differ ONLY in bytecode compilation state, not deps:
  - SCENARIO_LEAN: runs in the pyc-stripped image (uncompiled; cold container pays compile cost).
  - SCENARIO_PREBAKED: runs in the landed benchmarks-lean image (.pyc already present from
    UV_COMPILE_BYTECODE=1 during uv sync).
The delta isolates bytecode compile cost on a cold container (MEAS-07, reframed).

The driver's `_image_tag(variant)` mapping resolves these variant strings to actual image
tags. Do NOT assume variant="prebaked" means the landed `benchmarks-prebaked` image: per
D-12a, that image's differentiator is the wrong one. See driver.py.

Plan 01-05 Task 5a: switched to JSON fixture so aload_flow_from_json fires the
`after-component-index` checkpoint . LFX_BENCHMARK_BOOTSTRAP_PATH points lfx._bench
at mock_llm.py so the module-level install_if_enabled() call bridges the gap left by
dropping fixture-level Python (JSON fixtures do not execute any fixture code).
"""

from __future__ import annotations

from src.backend.tests.benchmarks.scenarios import Scenario

_COMMON_ENV = {
    "LFX_BENCHMARK_CHECKPOINTS": "1",
    "LFX_BENCHMARK_CHECKPOINTS_FILE": "/tmp/checkpoints.json",  # noqa: S108
    "LFX_BENCHMARK_MOCK_LLM": "1",
    # The driver also sets LFX_BENCHMARK_BOOTSTRAP_PATH when running in docker; see driver.py.
    # Setting it here is safe because the path resolves inside the container to the baked-in
    # benchmarks source tree.
    "LFX_BENCHMARK_BOOTSTRAP_PATH": "/app/src/backend/tests/benchmarks/mock_llm.py",
    # OpenAI client still validates the key format before falling through to the mocked
    # ._generate / ._agenerate, so provide a placeholder that satisfies the format check.
    "OPENAI_API_KEY": "sk-benchmark-mocked-not-a-real-secret",  # pragma: allowlist secret
}

SCENARIO_LEAN = Scenario(
    name="lfx_with_flow",
    variant="lean",
    command=["uv", "run", "lfx", "run", "/fixtures/basic_prompting.json", "--format", "text"],
    env=_COMMON_ENV,
    runs=10,
    captures_checkpoints=True,
    captures_pyinstrument=True,
    captures_importtime=True,
)

SCENARIO_PREBAKED = Scenario(
    name="lfx_with_flow_prebaked",
    variant="prebaked",
    command=["uv", "run", "lfx", "run", "/fixtures/basic_prompting.json", "--format", "text"],
    env=_COMMON_ENV,
    runs=10,
    captures_checkpoints=True,
    captures_pyinstrument=False,  # wall-clock is all we need for the MEAS-07 delta
    captures_importtime=False,
)

# Back-compat alias: some scripts iterate on SCENARIO. The lean variant is the primary.
SCENARIO = SCENARIO_LEAN
