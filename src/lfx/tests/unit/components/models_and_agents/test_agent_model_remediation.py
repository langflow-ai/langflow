"""AgentComponent retries with an error-driven model remediation.

When the selected model rejects the request with a recognized constraint
(e.g. OpenAI gpt-5.6 needs the Responses API for tools), message_response must
rebuild the model with the remediation override, retry once, and remember the
winning override for the model (discover-once).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from lfx.schema.message import Message

GPT56_RESPONSES_API_ERROR = RuntimeError(
    "Error building Component Agent: Error code: 400 - Function tools with "
    "reasoning_effort are not supported for gpt-5.6-luna in /v1/chat/completions. "
    "To use function tools, use /v1/responses or set reasoning_effort to 'none'."
)


class ChatOpenAI(FakeListChatModel):
    """Dependency-free ChatOpenAI stand-in for the isolated LFX test suite."""

    model_name: str = "gpt-5.6-luna"
    use_responses_api: bool = False


def _attach_connected_model_source(
    agent,
    display_name: str | None = None,
    *,
    provider: str | None = None,
    model: list[dict] | None = None,
) -> None:
    """Attach minimal graph provenance for a model wired into the Agent input."""
    source = SimpleNamespace(
        custom_component=SimpleNamespace(
            provider=provider,
            model=model or [],
            display_name=display_name,
        ),
    )
    graph = MagicMock()
    graph.get_vertex.return_value = source
    vertex = MagicMock()
    vertex.graph = graph
    vertex.get_incoming_edge_by_target_param.return_value = "model-source"
    agent.set_vertex(vertex)


@pytest.mark.parametrize(
    ("source_kwargs", "expected_provider"),
    [
        ({"provider": "OpenAI", "model": [{"provider": "OpenRouter"}], "display_name": "Language Model"}, "OpenAI"),
        ({"model": [{"provider": "OpenAI"}], "display_name": "Language Model"}, "OpenAI"),
        ({"display_name": "OpenAI"}, "OpenAI"),
    ],
)
def test_connected_model_provider_uses_source_component_provenance(source_kwargs, expected_provider):
    from lfx.components.models_and_agents.agent import AgentComponent

    connected_model = ChatOpenAI(responses=["unused"])
    agent = AgentComponent()
    agent.model = connected_model
    _attach_connected_model_source(agent, **source_kwargs)

    assert agent._selected_model_remediation_context() == (
        expected_provider,
        "gpt-5.6-luna",
        connected_model,
    )


def test_connected_model_provider_requires_matching_source_and_model_class():
    from lfx.components.models_and_agents.agent import AgentComponent

    connected_model = FakeListChatModel(responses=["unused"])
    agent = AgentComponent()
    agent.model = connected_model
    _attach_connected_model_source(agent, "OpenAI")

    assert agent._selected_model_remediation_context() == (None, None, connected_model)


async def test_message_response_runs_when_connected_model_source_is_missing():
    from lfx.components.models_and_agents.agent import AgentComponent

    connected_model = ChatOpenAI(responses=["unused"])
    agent = AgentComponent()
    agent.model = connected_model
    agent.input_value = "hi"
    agent.system_prompt = ""
    agent.tools = []
    agent.add_current_date_tool = False
    agent.add_calculator_tool = False
    _attach_connected_model_source(agent, "OpenAI")
    agent._vertex.graph.get_vertex.side_effect = ValueError("Vertex model-source not found")
    mocked_run_agent = AsyncMock(return_value=Message(text="ok"))

    with (
        patch.object(
            AgentComponent,
            "get_memory_data",
            new=AsyncMock(return_value=[]),
        ),
        patch.object(AgentComponent, "create_agent_runnable", return_value=MagicMock()),
        patch.object(AgentComponent, "run_agent", new=mocked_run_agent),
    ):
        result = await agent.message_response()

    assert result.text == "ok"
    assert mocked_run_agent.await_count == 1


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
                return_value=[{"provider": "OpenAI", "name": "gpt-5.6-luna"}],
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
        assert model_remediation.cached_overrides("OpenAI", "gpt-5.6-luna") == {"use_responses_api": True}
    finally:
        model_remediation.reset_remediation_cache()


async def test_message_response_remediates_a_connected_model_in_place_without_caching():
    from lfx.base.models import model_remediation
    from lfx.components.models_and_agents.agent import AgentComponent

    model_remediation.reset_remediation_cache()
    try:
        connected_model = ChatOpenAI(responses=["unused"])
        agent = AgentComponent()
        agent.model = connected_model
        agent.input_value = "hi"
        agent.system_prompt = ""
        agent.tools = []
        agent.add_current_date_tool = False
        agent.add_calculator_tool = False
        _attach_connected_model_source(agent, "OpenAI")
        seen_values: list[bool] = []

        assert agent._selected_model_remediation_context() == (
            "OpenAI",
            "gpt-5.6-luna",
            connected_model,
        )

        async def run_agent(_agent):
            assert agent.llm is connected_model
            seen_values.append(connected_model.use_responses_api)
            if not connected_model.use_responses_api:
                raise GPT56_RESPONSES_API_ERROR
            return Message(text="ok")

        mocked_run_agent = AsyncMock(side_effect=run_agent)
        with (
            patch.object(model_remediation, "remember") as remember,
            patch.object(
                AgentComponent,
                "get_memory_data",
                new=AsyncMock(return_value=[]),
            ),
            patch.object(AgentComponent, "create_agent_runnable", return_value=MagicMock()),
            patch.object(AgentComponent, "run_agent", new=mocked_run_agent),
        ):
            result = await agent.message_response()

        assert result.text == "ok"
        assert seen_values == [False, True]
        assert mocked_run_agent.await_count == 2
        assert connected_model.use_responses_api is True
        remember.assert_not_called()
        assert model_remediation.cached_overrides("OpenAI", "gpt-5.6-luna") == {}
    finally:
        model_remediation.reset_remediation_cache()


async def test_message_response_does_not_retry_for_a_non_openai_connected_model():
    from lfx.base.models import model_remediation
    from lfx.components.models_and_agents.agent import AgentComponent

    model_remediation.reset_remediation_cache()
    try:
        # OpenRouter also uses ChatOpenAI, so the class name alone must not opt
        # a connected model into an OpenAI-only remediation.
        connected_model = ChatOpenAI(responses=["unused"])
        agent = AgentComponent()
        agent.model = connected_model
        agent.input_value = "hi"
        agent.system_prompt = ""
        agent.tools = []
        agent.add_current_date_tool = False
        agent.add_calculator_tool = False
        _attach_connected_model_source(agent, "OpenRouter")
        mocked_run_agent = AsyncMock(side_effect=GPT56_RESPONSES_API_ERROR)

        assert agent._selected_model_remediation_context() == (
            "OpenRouter",
            "gpt-5.6-luna",
            connected_model,
        )

        with (
            patch.object(
                AgentComponent,
                "get_memory_data",
                new=AsyncMock(return_value=[]),
            ),
            patch.object(AgentComponent, "create_agent_runnable", return_value=MagicMock()),
            patch.object(AgentComponent, "run_agent", new=mocked_run_agent),
            pytest.raises(RuntimeError, match=r"gpt-5\.6-luna"),
        ):
            await agent.message_response()

        assert mocked_run_agent.await_count == 1
        assert model_remediation.cached_overrides("OpenAI", "gpt-5.6-luna") == {}
    finally:
        model_remediation.reset_remediation_cache()


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
                return_value=[{"provider": "OpenAI", "name": "gpt-5.6-luna"}],
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
        assert model_remediation.cached_overrides("OpenAI", "gpt-5.6-luna") == {}
    finally:
        model_remediation.reset_remediation_cache()


async def test_json_response_remediates_a_connected_model_prompt_fallback():
    from lfx.base.models import model_remediation
    from lfx.components.models_and_agents.agent import AgentComponent

    model_remediation.reset_remediation_cache()
    try:
        connected_model = ChatOpenAI(responses=["unused"])
        agent = AgentComponent()
        agent.model = connected_model
        agent.input_value = "hi"
        agent.system_prompt = ""
        agent.tools = [MagicMock(name="tool")]
        agent.add_current_date_tool = False
        agent.add_calculator_tool = False
        agent.output_schema = [{"name": "answer", "type": "str", "multiple": False}]
        agent.format_instructions = ""
        _attach_connected_model_source(agent, "OpenAI")
        seen_values: list[bool] = []
        tool_effects: list[str] = []

        async def run_agent(_agent):
            assert agent.llm is connected_model
            seen_values.append(connected_model.use_responses_api)
            if not connected_model.use_responses_api:
                raise GPT56_RESPONSES_API_ERROR
            tool_effects.append("executed")
            return Message(text='{"answer": "ok"}')

        mocked_run_agent = AsyncMock(side_effect=run_agent)
        mocked_create_agent = MagicMock()
        with (
            patch.object(model_remediation, "remember") as remember,
            patch.object(
                AgentComponent,
                "get_memory_data",
                new=AsyncMock(return_value=[]),
            ),
            patch.object(AgentComponent, "create_agent_runnable", new=mocked_create_agent),
            patch.object(AgentComponent, "run_agent", new=mocked_run_agent),
        ):
            result = await agent.json_response()

        assert result.data == {"answer": "ok"}
        assert seen_values == [False, True]
        assert tool_effects == ["executed"]
        assert mocked_run_agent.await_count == 2
        assert mocked_create_agent.call_args_list == [
            call(allow_interrupts=False),
            call(allow_interrupts=False),
        ]
        remember.assert_not_called()
        assert model_remediation.cached_overrides("OpenAI", "gpt-5.6-luna") == {}
    finally:
        model_remediation.reset_remediation_cache()
