from unittest.mock import Mock, patch

import pytest
from lfx.components.langchain_utilities import ToolCallingAgentComponent
from lfx.components.openai.openai_chat_model import OpenAIModelComponent
from lfx.components.tools.calculator import CalculatorToolComponent


class TestToolCallingAgentUpdateBuildConfig:
    """Unit tests for ToolCallingAgentComponent.update_build_config field visibility."""

    def _make_component(self):
        component = ToolCallingAgentComponent()
        component._user_id = None
        component.cache = {}
        return component

    def _get_build_config(self, component):
        return component.to_frontend_node()["data"]["node"]["template"]

    @patch("lfx.components.langchain_utilities.tool_calling.get_language_model_options")
    def test_shows_watsonx_fields_when_watsonx_selected(self, mock_opts):
        """Selecting IBM WatsonX should show base_url_ibm_watsonx and project_id."""
        watsonx_model = [{"name": "ibm/granite-13b-chat-v2", "provider": "IBM WatsonX", "metadata": {}}]
        mock_opts.return_value = watsonx_model
        component = self._make_component()
        build_config = self._get_build_config(component)

        updated = component.update_build_config(build_config, watsonx_model, field_name="model")

        assert updated["base_url_ibm_watsonx"]["show"] is True
        assert updated["base_url_ibm_watsonx"]["required"] is False
        assert updated["project_id"]["show"] is True
        assert "ollama_base_url" not in updated

    @patch("lfx.components.langchain_utilities.tool_calling.get_language_model_options")
    def test_hides_watsonx_fields_when_openai_selected(self, mock_opts):
        """Selecting OpenAI should hide all provider-specific fields."""
        openai_model = [{"name": "gpt-4o", "provider": "OpenAI", "metadata": {}}]
        mock_opts.return_value = openai_model
        component = self._make_component()
        build_config = self._get_build_config(component)

        updated = component.update_build_config(build_config, openai_model, field_name="model")

        assert updated["base_url_ibm_watsonx"]["show"] is False
        assert updated["project_id"]["show"] is False
        assert "ollama_base_url" not in updated

    @patch("lfx.components.langchain_utilities.tool_calling.get_language_model_options")
    def test_hides_all_provider_fields_with_no_model_selected(self, mock_opts):
        """With no model selected, all provider-specific fields should be hidden."""
        mock_opts.return_value = []
        component = self._make_component()
        build_config = self._get_build_config(component)

        updated = component.update_build_config(build_config, "", field_name=None)

        assert updated["base_url_ibm_watsonx"]["show"] is False
        assert updated["project_id"]["show"] is False
        assert "ollama_base_url" not in updated


class TestToolCallingAgentBackwardCompatStreaming:
    """Force streaming=True on the LLM resolved by ToolCallingAgentComponent._get_llm.

    Bug repro for ``openrag_agent.json`` (code_hash ``154c71cf7441``): the saved
    flow embeds the pre-PR-13358 ``AgentComponent`` class body whose ``_get_llm()``
    calls ``get_llm(...)`` WITHOUT ``stream=True``. When the flow loads, Python
    exec's the old class — it still inherits from the LIVE
    ``ToolCallingAgentComponent`` (parents are resolved at exec time), but its
    own ``_get_llm`` produces a chat model with ``streaming=False``. PR #13358's
    fix in ``agent.py`` cannot reach serialized class bodies. Without forcing
    streaming at the live parent chokepoint, ``runnable.astream_events(v2)``
    never emits ``on_chat_model_stream`` and the Playground silently shows the
    response in a single batch.
    """

    def _build_component(self):
        component = ToolCallingAgentComponent()
        component._user_id = None
        component.cache = {}
        component.tools = []
        component.system_prompt = "Test prompt"
        return component

    def test_should_force_streaming_true_when_legacy_serialized_agent_returns_non_streaming_llm(self):
        component = self._build_component()

        # Simulate the legacy serialized ``_get_llm()`` that built the LLM via
        # ``get_llm()`` without the ``stream=True`` kwarg — resulting chat model
        # has ``streaming=False``.
        legacy_llm = Mock()
        legacy_llm.__class__.__name__ = "ChatOpenAI"
        legacy_llm.__class__.__module__ = "langchain_openai"
        legacy_llm.model_id = "gpt-4o"
        legacy_llm.model_name = "gpt-4o"
        legacy_llm.streaming = False
        legacy_llm.bind_tools = Mock(return_value=legacy_llm)

        captured: dict[str, object] = {}

        def _capture(llm, _tools, _prompt):
            captured["llm"] = llm
            return Mock()

        with (
            patch.object(component, "_get_llm", return_value=legacy_llm),
            patch(
                "lfx.components.langchain_utilities.tool_calling.create_tool_calling_agent",
                side_effect=_capture,
            ),
        ):
            component.create_agent_runnable()

        assert captured["llm"] is legacy_llm, "create_tool_calling_agent must receive the resolved LLM"
        assert legacy_llm.streaming is True, (
            "ToolCallingAgentComponent.create_agent_runnable() must force streaming=True "
            "on the resolved LLM so serialized flows whose embedded AgentComponent code "
            "predates PR #13358 (e.g. openrag_agent.json with code_hash 154c71cf7441) "
            "still emit on_chat_model_stream chunks through astream_events(v2). "
            "PR #13358's _get_llm fix in agent.py cannot reach serialized class bodies."
        )

    def test_should_preserve_streaming_true_when_modern_agent_returns_streaming_llm(self):
        """No-op for already-streaming LLMs: don't downgrade or trigger setattr surprises."""
        component = self._build_component()

        modern_llm = Mock()
        modern_llm.__class__.__name__ = "ChatOpenAI"
        modern_llm.__class__.__module__ = "langchain_openai"
        modern_llm.model_id = "gpt-4o"
        modern_llm.model_name = "gpt-4o"
        modern_llm.streaming = True
        modern_llm.bind_tools = Mock(return_value=modern_llm)

        with (
            patch.object(component, "_get_llm", return_value=modern_llm),
            patch(
                "lfx.components.langchain_utilities.tool_calling.create_tool_calling_agent",
                return_value=Mock(),
            ),
        ):
            component.create_agent_runnable()

        assert modern_llm.streaming is True

    def test_should_not_crash_when_llm_has_no_streaming_attribute(self):
        """Future providers may lack the legacy ``streaming`` attribute.

        Guards against a provider that implements streaming through a different
        knob (e.g. ``model_kwargs={"stream": True}``). The shim must use
        ``getattr(llm, "streaming", True)`` so a missing attr defaults to True
        (no mutation) and ``create_agent_runnable`` proceeds normally.
        """
        component = self._build_component()

        # Stand-in for a chat model that doesn't expose ``streaming``.
        def _no_streaming_bind_tools(self, _tools):
            return self

        chat_exotic_cls = type(
            "ChatExoticProvider",
            (),
            {
                "__module__": "langchain_exotic",
                "model_id": "exotic-1",
                "model_name": "exotic-1",
                "bind_tools": _no_streaming_bind_tools,
            },
        )
        llm_obj = chat_exotic_cls()
        assert not hasattr(llm_obj, "streaming"), "fixture invariant: no streaming attr"

        with (
            patch.object(component, "_get_llm", return_value=llm_obj),
            patch(
                "lfx.components.langchain_utilities.tool_calling.create_tool_calling_agent",
                return_value=Mock(),
            ),
        ):
            component.create_agent_runnable()  # must NOT raise AttributeError

        assert not hasattr(llm_obj, "streaming"), (
            "Shim must NOT setattr when the LLM has no ``streaming`` attribute: "
            "getattr default of True short-circuits the ``is False`` branch."
        )

    def test_should_not_crash_when_llm_streaming_attribute_is_read_only(self):
        """``contextlib.suppress`` must swallow setattr failures.

        A future Pydantic-v2-strict chat model may freeze ``streaming``. The
        shim's job is to TRY forcing streaming; if the provider refuses, the
        agent must still run — better to surface a streaming bug downstream
        than to crash the whole flow at agent-build time.
        """
        component = self._build_component()

        def _readonly_bind_tools(self, _tools):
            return self

        def _readonly_streaming_getter(_obj):
            return False

        chat_strict_cls = type(
            "ChatStrict",
            (),
            {
                "__module__": "langchain_strict",
                "model_id": "strict-1",
                "model_name": "strict-1",
                # property with no setter — setattr raises AttributeError, exercised by contextlib.suppress
                "streaming": property(_readonly_streaming_getter),
                "bind_tools": _readonly_bind_tools,
            },
        )
        llm_obj = chat_strict_cls()

        with (
            patch.object(component, "_get_llm", return_value=llm_obj),
            patch(
                "lfx.components.langchain_utilities.tool_calling.create_tool_calling_agent",
                return_value=Mock(),
            ),
        ):
            component.create_agent_runnable()  # must NOT raise AttributeError

        # streaming still False because the property has no setter, but
        # the agent build did not crash — which is the contract.
        assert llm_obj.streaming is False

    def test_should_be_idempotent_when_create_agent_runnable_called_twice(self):
        """Repeated calls must not interact in surprising ways.

        Some workflows resolve the LLM lazily and rebuild the runnable on
        retries; the shim must be a stable transformation (``streaming=True``
        is a fixed point) so the second invocation is a no-op.
        """
        component = self._build_component()

        llm = Mock()
        llm.__class__.__name__ = "ChatOpenAI"
        llm.__class__.__module__ = "langchain_openai"
        llm.model_id = "gpt-4o"
        llm.model_name = "gpt-4o"
        llm.streaming = False
        llm.bind_tools = Mock(return_value=llm)

        with (
            patch.object(component, "_get_llm", return_value=llm),
            patch(
                "lfx.components.langchain_utilities.tool_calling.create_tool_calling_agent",
                return_value=Mock(),
            ),
        ):
            component.create_agent_runnable()
            assert llm.streaming is True, "first call must enable streaming"
            component.create_agent_runnable()
            assert llm.streaming is True, "second call must leave streaming=True intact"

    def test_should_force_streaming_true_on_granite_path(self):
        """The Granite branch also passes through the live shim chokepoint.

        ``create_granite_agent`` is selected when ``is_granite_model(llm)`` and
        the agent has tools; the shim runs BEFORE that branch (line ordering),
        so the resolved LLM must already have ``streaming=True`` even on the
        WatsonX path.
        """
        component = self._build_component()
        component.tools = [Mock(name="t1")]
        component.tools[0].name = "tool_1"

        granite_llm = Mock()
        granite_llm.__class__.__name__ = "ChatWatsonx"
        granite_llm.__class__.__module__ = "langchain_ibm"
        granite_llm.model_id = "ibm/granite-13b-chat-v2"
        granite_llm.model_name = "ibm/granite-13b-chat-v2"
        granite_llm.streaming = False
        granite_llm.bind_tools = Mock(return_value=granite_llm)

        captured: dict[str, object] = {}

        def _capture_granite(llm, _tools, _prompt):
            captured["llm"] = llm
            return Mock()

        with (
            patch.object(component, "_get_llm", return_value=granite_llm),
            patch(
                "lfx.components.langchain_utilities.tool_calling.create_granite_agent",
                side_effect=_capture_granite,
            ),
            patch(
                "lfx.components.langchain_utilities.tool_calling.is_granite_model",
                return_value=True,
            ),
        ):
            component.create_agent_runnable()

        assert captured["llm"] is granite_llm
        assert granite_llm.streaming is True, (
            "Granite/WatsonX flows must also receive streaming=True so token-by-token "
            "delivery works on IBM Granite serialized flows."
        )


@pytest.mark.api_key_required
@pytest.mark.usefixtures("client")
async def test_tool_calling_agent_component():
    tools = [CalculatorToolComponent().build_tool()]  # Use the Calculator component as a tool
    input_value = "What is 2 + 2?"
    chat_history = []
    from tests.api_keys import get_openai_api_key

    api_key = get_openai_api_key()
    temperature = 0.1

    # Default OpenAI Model Component
    llm_component = OpenAIModelComponent().set(
        api_key=api_key,
        temperature=temperature,
    )
    llm = llm_component.build_model()

    agent = ToolCallingAgentComponent(_session_id="test")
    agent.set(model=llm, tools=[tools], chat_history=chat_history, input_value=input_value)

    # Chat output
    response = await agent.message_response()
    assert "4" in response.data.get("text")
