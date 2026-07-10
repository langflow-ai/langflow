"""AgentComponent retries with an error-driven model remediation.

When the selected model rejects the request with a recognized constraint
(e.g. OpenAI gpt-5.6 needs the Responses API for tools), message_response must
rebuild the model with the remediation override, retry once, and remember the
winning override for the model (discover-once).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.schema.message import Message

GPT56_RESPONSES_API_ERROR = RuntimeError(
    "Error building Component Agent: Error code: 400 - Function tools with "
    "reasoning_effort are not supported for gpt-5.6 in /v1/chat/completions. "
    "To use function tools, use /v1/responses or set reasoning_effort to 'none'."
)


@pytest.mark.asyncio
async def test_message_response_remediates_responses_api_error_and_remembers():
    from lfx.base.models import model_remediation
    from lfx.components.models_and_agents.agent import AgentComponent

    model_remediation.reset_remediation_cache()
    try:
        agent = AgentComponent()
        agent.input_value = "hi"
        agent.system_prompt = ""
        agent.tools = []

        run_agent = AsyncMock(side_effect=[GPT56_RESPONSES_API_ERROR, Message(text="ok")])

        with (
            patch.object(
                AgentComponent,
                "_resolve_selected_model",
                return_value=[{"provider": "OpenAI", "name": "gpt-5.6"}],
            ),
            patch.object(
                AgentComponent,
                "get_agent_requirements",
                new=AsyncMock(return_value=(MagicMock(), [], [])),
            ),
            patch.object(AgentComponent, "create_agent_runnable", return_value=MagicMock()),
            patch.object(AgentComponent, "_inject_dynamic_prompt_values", return_value=""),
            patch.object(AgentComponent, "set", new=MagicMock()),
            patch.object(AgentComponent, "run_agent", new=run_agent),
        ):
            result = await agent.message_response()

        assert isinstance(result, Message)
        assert result.text == "ok"
        assert run_agent.await_count == 2
        assert agent._model_overrides == {"use_responses_api": True}
        assert model_remediation.cached_overrides("OpenAI", "gpt-5.6") == {"use_responses_api": True}
    finally:
        model_remediation.reset_remediation_cache()


@pytest.mark.asyncio
async def test_message_response_does_not_retry_unrelated_errors():
    from lfx.base.models import model_remediation
    from lfx.components.models_and_agents.agent import AgentComponent

    model_remediation.reset_remediation_cache()
    try:
        agent = AgentComponent()
        agent.input_value = "hi"
        agent.system_prompt = ""
        agent.tools = []

        run_agent = AsyncMock(side_effect=RuntimeError("rate limit exceeded"))

        with (
            patch.object(
                AgentComponent,
                "_resolve_selected_model",
                return_value=[{"provider": "OpenAI", "name": "gpt-5.6"}],
            ),
            patch.object(
                AgentComponent,
                "get_agent_requirements",
                new=AsyncMock(return_value=(MagicMock(), [], [])),
            ),
            patch.object(AgentComponent, "create_agent_runnable", return_value=MagicMock()),
            patch.object(AgentComponent, "_inject_dynamic_prompt_values", return_value=""),
            patch.object(AgentComponent, "set", new=MagicMock()),
            patch.object(AgentComponent, "run_agent", new=run_agent),
            pytest.raises(RuntimeError, match="rate limit"),
        ):
            await agent.message_response()

        assert run_agent.await_count == 1
        assert model_remediation.cached_overrides("OpenAI", "gpt-5.6") == {}
    finally:
        model_remediation.reset_remediation_cache()
