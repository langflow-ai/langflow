"""Native model output/legacy selection paths preserve synchronous compatibility."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from lfx.components.models_and_agents import language_model as language_module
from lfx.components.models_and_agents.language_model import LanguageModelComponent

SELECTION = [{"name": "gpt-4o-mini", "provider": "OpenAI", "metadata": {}}]


def policy():
    return SimpleNamespace(
        require=Mock(), allows=lambda name: name == "OpenAI", allows_model=lambda *_args, **_kwargs: True
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("output_index", [0, 1])
async def test_native_language_model_output_awaits_options_and_factory(monkeypatch, output_index):
    component = LanguageModelComponent(_user_id="runtime-owner")
    component.set_attributes(
        {
            "model": SELECTION,
            "model_name": "chosen-model",
            "provider": "OpenAI",
            "api_key": "test-key",  # pragma: allowlist secret
            "temperature": 0.3,
            "stream": True,
        }
    )
    option = {"name": "chosen-model", "provider": "OpenAI", "metadata": {"reasoning": True}}
    monkeypatch.setattr(
        "lfx.services.model_provider_policy.aresolve_model_provider_policy", AsyncMock(return_value=policy())
    )
    lookup = AsyncMock(return_value=[option])
    factory = AsyncMock(return_value=object())
    monkeypatch.setattr(language_module, "aget_language_model_options", lookup)
    monkeypatch.setattr(language_module, "aget_llm", factory)
    monkeypatch.setattr(language_module, "get_llm", Mock(side_effect=AssertionError("sync output path forbidden")))
    chat = AsyncMock(return_value=factory.return_value)
    monkeypatch.setattr(type(component), "get_chat_result", chat)
    result = await component._get_output_result(component.outputs[output_index])
    assert result is factory.return_value
    lookup.assert_awaited_once_with(user_id="runtime-owner")
    assert factory.await_args.kwargs["model"] == [option]
    if output_index == 0:
        assert chat.await_args.kwargs["runnable"] is factory.return_value
    else:
        chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_denied_language_model_stops_before_override_options_or_factory(monkeypatch):
    component = LanguageModelComponent(_user_id="runtime-owner")
    component.set_attributes({"model": SELECTION, "model_name": "chosen", "provider": "OpenAI"})
    p = policy()
    p.require.side_effect = PermissionError("denied")
    monkeypatch.setattr("lfx.services.model_provider_policy.aresolve_model_provider_policy", AsyncMock(return_value=p))
    options = AsyncMock(side_effect=AssertionError("catalog accessed before denial"))
    factory = AsyncMock()
    monkeypatch.setattr(language_module, "aget_language_model_options", options)
    monkeypatch.setattr(language_module, "aget_llm", factory)
    with pytest.raises(PermissionError):
        await component.abuild_model()
    options.assert_not_awaited()
    factory.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_tool_calling_response_awaits_model_and_preserves_executor(monkeypatch):
    from lfx.components.langchain_utilities import tool_calling
    from lfx.components.langchain_utilities.tool_calling import ToolCallingAgentComponent

    c = ToolCallingAgentComponent(_user_id="runtime-owner", model=SELECTION)
    c.set_attributes({"tools": [], "input_value": "test", "system_prompt": ""})
    monkeypatch.setattr(
        "lfx.services.model_provider_policy.aresolve_model_provider_policy", AsyncMock(return_value=policy())
    )
    factory = AsyncMock(return_value=object())
    monkeypatch.setattr(tool_calling, "aget_llm", factory)
    monkeypatch.setattr(tool_calling, "get_llm", Mock(side_effect=AssertionError("sync legacy factory forbidden")))
    runnable = object()
    executor = object()
    build = Mock(return_value=runnable)
    wrap = Mock(return_value=executor)
    run = AsyncMock(return_value=object())
    monkeypatch.setattr(c, "_runnable_from_model", build)
    monkeypatch.setattr(c, "_executor_from_runnable", wrap)
    monkeypatch.setattr(c, "run_agent", run)
    assert await c.message_response() is run.return_value
    factory.assert_awaited_once()
    build.assert_called_once_with(factory.return_value)
    wrap.assert_called_once_with(runnable)
    run.assert_awaited_once_with(agent=executor)


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_tool_agent_builders_disambiguate_names_without_changing_shared_tools(monkeypatch, asynchronous):
    from langchain_core.tools import StructuredTool
    from lfx.components.langchain_utilities.tool_calling import ToolCallingAgentComponent

    tools = [StructuredTool.from_function(lambda: "result", name="search", description="Search") for _ in range(2)]
    component = ToolCallingAgentComponent(_user_id="runtime-owner", model=SELECTION, tools=tools)
    executor = object()
    monkeypatch.setattr(component, "create_agent_runnable", Mock(return_value=object()))
    monkeypatch.setattr(component, "_executor_from_runnable", Mock(return_value=executor))
    result = await component.abuild_agent() if asynchronous else component.build_agent()
    assert result is executor
    assert len({tool.name for tool in component.tools}) == 2
    assert [tool.name for tool in tools] == ["search", "search"]


@pytest.mark.asyncio
@pytest.mark.parametrize("unavailable", [False, True])
async def test_legacy_tool_calling_policy_stops_before_factory_and_output(monkeypatch, unavailable):
    from lfx.components.langchain_utilities import tool_calling
    from lfx.components.langchain_utilities.tool_calling import ToolCallingAgentComponent

    c = ToolCallingAgentComponent(_user_id="runtime-owner", model=SELECTION)
    p = policy()
    failure = RuntimeError("policy unavailable") if unavailable else PermissionError("denied")
    if not unavailable:
        p.require.side_effect = failure
    resolver = AsyncMock(side_effect=failure) if unavailable else AsyncMock(return_value=p)
    monkeypatch.setattr("lfx.services.model_provider_policy.aresolve_model_provider_policy", resolver)
    factory = AsyncMock()
    output = Mock()
    monkeypatch.setattr(tool_calling, "aget_llm", factory)
    monkeypatch.setattr(c, "_runnable_from_model", output)
    with pytest.raises(type(failure)):
        await c.acreate_agent_runnable()
    factory.assert_not_awaited()
    output.assert_not_called()


@pytest.mark.asyncio
async def test_sync_model_extension_keeps_context_and_does_not_block_loop(monkeypatch):
    import threading
    from contextvars import ContextVar

    context = ContextVar("model-extension-context", default="missing")
    started = threading.Event()
    released = threading.Event()
    model = object()

    class CustomLanguageModel(LanguageModelComponent):
        def build_model(self):
            assert context.get() == "owner"
            started.set()
            assert released.wait(1)
            return model

    c = CustomLanguageModel()
    chat = AsyncMock(return_value=model)
    monkeypatch.setattr(c, "get_chat_result", chat)
    token = context.set("owner")
    try:
        task = asyncio.create_task(c.text_response())
        for _ in range(50):
            if started.is_set():
                break
            await asyncio.sleep(0.01)
        assert started.is_set()
        released.set()
        assert await asyncio.wait_for(task, 1) is model
    finally:
        released.set()
        context.reset(token)
    chat.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("output_index", [0, 1])
async def test_borrowed_marked_model_builder_keeps_receiver_endpoint_and_context(monkeypatch, output_index):
    from contextvars import ContextVar

    context = ContextVar("borrowed-model-owner", default="missing")
    first = LanguageModelComponent(
        _user_id="first-owner", model=SELECTION, api_key="first-key", temperature=0.1, stream=False
    )
    second_selection = [{"name": "second-model", "provider": "IBM WatsonX", "metadata": {}}]
    second = LanguageModelComponent(
        _user_id="second-owner", model=second_selection, api_key="second-key", temperature=0.7, stream=True
    )
    second.set_attributes({"base_url_ibm_watsonx": "https://second.example/v1"})
    first.build_model = second.build_model
    chosen = SimpleNamespace(model_name="second-model", base_url="https://second.example/v1")
    calls = []

    def factory(**kwargs):
        assert context.get() == "owner"
        calls.append(kwargs)
        return chosen

    monkeypatch.setattr(language_module, "get_llm", factory)
    monkeypatch.setattr(language_module, "aget_llm", AsyncMock(side_effect=AssertionError("borrowed receiver skipped")))
    chat = AsyncMock(return_value=chosen)
    monkeypatch.setattr(first, "get_chat_result", chat)
    token = context.set("owner")
    try:
        result = await first._get_output_result(first.outputs[output_index])
    finally:
        context.reset(token)
    assert result is chosen
    assert calls[0]["model"] == second_selection
    assert calls[0]["user_id"] == "second-owner"
    assert calls[0]["api_key"] == "second-key"  # pragma: allowlist secret
    assert calls[0]["temperature"] == 0.7
    assert calls[0]["stream"] is True
    assert calls[0]["watsonx_url"] == "https://second.example/v1"
    if output_index == 0:
        assert chat.await_args.kwargs["runnable"] is chosen
