"""Integration tests for example flows from the Stepflow documentation.

Tests the full end-to-end path used by the ``stepflow-langflow run`` CLI:
LangflowConverter -> StepflowClient -> orchestrator -> langflow worker.

The POC flow requires ``OPENAI_API_KEY`` for execution tests.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_poc_flow() -> Path:
    """Locate the POC flow JSON from the sibling stepflow repo's docs."""
    # This file is at tests/integration/test_example_flows.py
    here = Path(__file__).resolve()
    # here.parents[4] = langflow repo root (e.g. /Users/.../langflow)
    langflow_repo = here.parents[4]
    candidate = langflow_repo.parent / "stepflow" / "docs" / "static" / "files" / "2025-09-langflow-poc-flow.json"
    if candidate.exists():
        return candidate

    # Env var fallback
    if env_path := os.environ.get("STEPFLOW_POC_FLOW"):
        p = Path(env_path)
        if p.exists():
            return p

    pytest.skip("POC flow not found. Set STEPFLOW_POC_FLOW or ensure sibling stepflow repo exists.")


def requires_openai() -> pytest.MarkDecorator:
    """Skip if OPENAI_API_KEY is not set."""
    return pytest.mark.skipif(
        not os.environ.get("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def poc_flow_data() -> dict[str, Any]:
    """Load the POC flow JSON."""
    path = _find_poc_flow()
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Translation tests (no orchestrator required)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_poc_flow_translation(converter, poc_flow_data):
    """The POC flow must translate to a valid Stepflow flow with correct
    variable schema for OPENAI_API_KEY."""
    flow = converter.convert(poc_flow_data)

    assert flow is not None, "convert() returned None"
    assert flow.steps, "translated flow has no steps"

    for step in flow.steps:
        assert step.component.startswith(("/langflow/", "/builtin/")), f"unexpected component prefix: {step.component}"

    # Verify the variable schema includes OPENAI_API_KEY with env_var annotation
    import msgspec

    flow_dict = msgspec.to_builtins(flow)
    var_props = flow_dict.get("schemas", {}).get("properties", {}).get("variables", {}).get("properties", {})
    assert "OPENAI_API_KEY" in var_props, f"Expected OPENAI_API_KEY in variable schema, got: {list(var_props.keys())}"
    assert var_props["OPENAI_API_KEY"].get("env_var") == "OPENAI_API_KEY", (
        f"Expected env_var annotation, got: {var_props['OPENAI_API_KEY']}"
    )


# ---------------------------------------------------------------------------
# Execution tests (require orchestrator + OPENAI_API_KEY)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="module")
@requires_openai()
async def test_poc_flow_execution(runner, poc_flow_data):
    """The POC flow must execute end-to-end with variables populated from env.

    Uses StepflowRunner which delegates to StepflowClient with
    ``populate_variables_from_env=True``, exercising the same code path
    as ``stepflow-langflow run --local``.
    """
    flow_data = poc_flow_data.get("data", poc_flow_data)

    run_outputs, session_id = await runner.run(
        flow_data=flow_data,
        input_value=None,
        session_id=None,
    )

    assert run_outputs, "Expected at least one RunOutputs"
    assert session_id

    result = run_outputs[0].outputs[0]
    assert result is not None, "Expected a ResultData"

    # The flow produces a blog post — verify we got non-trivial text
    has_output = bool(result.messages) or result.results is not None
    assert has_output, "Expected messages or results from POC flow"

    if result.messages:
        text = result.messages[0].message
        assert text and len(text) > 100, f"Expected substantial text output, got: {text!r:.200}"
