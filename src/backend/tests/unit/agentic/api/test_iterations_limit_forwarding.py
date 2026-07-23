"""The request's ``iterations_limit`` must reach every assistant endpoint.

PR #14094 review finding: ``AssistantRequest`` accepts ``iterations_limit``
but only ``/assist/stream`` forwarded it — ``/assist`` and
``/execute/{flow_name}`` silently executed with the default budget. The fix
seeds ``ITERATIONS_LIMIT`` centrally in ``_resolve_assistant_context`` so any
endpoint consuming ``ctx.global_vars`` honors the cap.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from langflow.agentic.api.router import _resolve_assistant_context
from langflow.agentic.api.schemas import AssistantRequest

_ROUTER = "langflow.agentic.api.router"


def _request(**overrides) -> AssistantRequest:
    payload = {"flow_id": str(uuid4()), "input_value": "build me a flow", **overrides}
    return AssistantRequest(**payload)


@pytest.fixture
def _provider_env():
    with (
        patch(
            f"{_ROUTER}.get_enabled_providers_for_user",
            new_callable=AsyncMock,
            return_value=(["OpenAI"], {}),
        ),
        patch(
            f"{_ROUTER}.get_model_provider_variable_mapping",
            return_value={"OpenAI": "OPENAI_API_KEY"},
        ),
        patch(f"{_ROUTER}.get_default_model", return_value="gpt-4o"),
        patch(
            f"{_ROUTER}.get_all_variables_for_provider",
            return_value={"OPENAI_API_KEY": "sk-test"},
        ),
        patch(
            f"{_ROUTER}.get_provider_required_variable_keys",
            return_value=["OPENAI_API_KEY"],
        ),
    ):
        yield


@pytest.mark.usefixtures("_provider_env")
async def test_iterations_limit_is_seeded_into_global_vars():
    """Central seeding covers /assist, /assist/stream, and /execute/{flow_name} at once."""
    session = AsyncMock()
    ctx = await _resolve_assistant_context(_request(iterations_limit=1), uuid4(), session=session)

    assert ctx.global_vars["ITERATIONS_LIMIT"] == "1"


@pytest.mark.usefixtures("_provider_env")
async def test_absent_iterations_limit_leaves_global_vars_unbudgeted():
    session = AsyncMock()
    ctx = await _resolve_assistant_context(_request(), uuid4(), session=session)

    assert "ITERATIONS_LIMIT" not in ctx.global_vars


async def test_non_streaming_execution_binds_the_iterations_context():
    """The nested generate_component subflow reads the budget from the run context.

    ``execute_flow_with_validation`` (the /assist non-streaming path) must bind
    the ContextVar while the flow runs, and clear it afterwards.
    """
    from langflow.agentic.services import assistant_service
    from langflow.agentic.services.agent_run_context import current_agent_run_iterations

    captured: dict[str, int | None] = {}

    async def fake_execute_flow_file(**_kwargs) -> dict:
        captured["limit"] = current_agent_run_iterations()
        return {"result": "ok"}

    with patch.object(assistant_service, "execute_flow_file", side_effect=fake_execute_flow_file):
        await assistant_service.execute_flow_with_validation(
            flow_filename="LangflowAssistant.json",
            input_value="hello",
            global_variables={"ITERATIONS_LIMIT": "2"},
        )

    assert captured["limit"] == 2
    assert current_agent_run_iterations() is None
