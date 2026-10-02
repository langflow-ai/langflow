"""Native model output/legacy selection paths preserve synchronous compatibility."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from lfx.base.models.unified_models import model_catalog
from lfx.components.models_and_agents import agent as agent_module
from lfx.components.models_and_agents import language_model as language_module
from lfx.components.models_and_agents.agent import AgentComponent
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
async def test_legacy_agent_selection_and_credentials_use_native_async_hooks(monkeypatch):
    c = AgentComponent(_user_id="runtime-owner", model=[], agent_llm="OpenAI", model_name="gpt-4o-mini")
    c.set_attributes({"tools": [], "add_current_date_tool": False, "chat_history": []})
    p = policy()
    monkeypatch.setattr("lfx.services.model_provider_policy.aresolve_model_provider_policy", AsyncMock(return_value=p))
    options = AsyncMock(return_value=SELECTION)
    factory = AsyncMock(return_value=object())
    monkeypatch.setattr(agent_module, "aget_language_model_options", options)
    monkeypatch.setattr(agent_module, "aget_llm", factory)
    monkeypatch.setattr(
        agent_module, "get_language_model_options", Mock(side_effect=AssertionError("sync legacy catalog forbidden"))
    )
    monkeypatch.setattr(agent_module, "get_llm", Mock(side_effect=AssertionError("sync model factory forbidden")))
    monkeypatch.setattr(type(c), "get_memory_data", AsyncMock(return_value=[]))
    llm, history, _tools = await c.get_agent_requirements()
    assert llm is factory.return_value
    assert history == []
    options.assert_awaited_once()
    factory.assert_awaited_once()


@pytest.mark.asyncio
async def test_legacy_direct_agent_denial_precedes_catalog_and_model(monkeypatch):
    c = AgentComponent(_user_id="runtime-owner", model=[], agent_llm="OpenAI", model_name="gpt-4o-mini")
    p = policy()
    p.require.side_effect = PermissionError("denied")
    monkeypatch.setattr("lfx.services.model_provider_policy.aresolve_model_provider_policy", AsyncMock(return_value=p))
    options = AsyncMock(side_effect=AssertionError("legacy catalog before denial"))
    factory = AsyncMock()
    monkeypatch.setattr(agent_module, "aget_language_model_options", options)
    monkeypatch.setattr(agent_module, "aget_llm", factory)
    with pytest.raises(PermissionError):
        await c.message_response()
    options.assert_not_awaited()
    factory.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_catalog_parity_retains_policy_status_and_live_filters(monkeypatch):
    rows = [
        {
            "provider": "OpenAI",
            "icon": "OpenAI",
            "models": [
                {"model_name": "gpt-4o-mini", "metadata": {"default": True, "model_type": "llm", "tool_calling": True}}
            ],
        }
    ]
    p = policy()
    monkeypatch.setattr(model_catalog, "get_unified_models_detailed", lambda **_kwargs: deepcopy(rows))
    monkeypatch.setattr(model_catalog, "_get_model_status", AsyncMock(return_value=(set(), set())))
    monkeypatch.setattr(model_catalog, "_fetch_enabled_providers_for_user", AsyncMock(return_value={"OpenAI"}))
    seen = []

    def discover(models, *_args):
        seen.append(models)
        models[0]["models"].append(
            {"model_name": "no-tools", "metadata": {"default": True, "model_type": "llm", "tool_calling": False}}
        )

    monkeypatch.setattr(model_catalog, "replace_with_live_models", discover)
    asynchronous = await model_catalog.aget_language_model_options(
        "runtime-owner", tool_calling=True, provider_policy=p
    )
    synchronous = model_catalog.get_language_model_options("runtime-owner", tool_calling=True, provider_policy=p)
    assert asynchronous == synchronous
    assert all(x["name"] != "no-tools" for x in asynchronous)
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_unavailable_catalog_policy_precedes_status_and_credentials(monkeypatch):
    monkeypatch.setattr(
        "lfx.services.model_provider_policy.aresolve_model_provider_policy",
        AsyncMock(side_effect=RuntimeError("policy unavailable")),
    )
    status = AsyncMock()
    enabled = AsyncMock()
    monkeypatch.setattr(model_catalog, "_get_model_status", status)
    monkeypatch.setattr(model_catalog, "_fetch_enabled_providers_for_user", enabled)
    with pytest.raises(RuntimeError, match="policy unavailable"):
        await model_catalog.aget_language_model_options("runtime-owner")
    status.assert_not_awaited()
    enabled.assert_not_awaited()


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
@pytest.mark.parametrize("override_kind", ["subclass", "instance"])
async def test_agent_sync_model_overrides_preserve_selection_endpoint_and_context(monkeypatch, override_kind):
    import threading
    from contextvars import ContextVar
    from types import MethodType

    context = ContextVar("agent-extension-context", default="missing")
    caller_thread = threading.get_ident()
    selected = [{"name": "owned-model", "provider": "OpenAI", "metadata": {}}]
    chosen = SimpleNamespace(model_name="owned-model", base_url="https://owned.example/v1")
    observed = []

    def custom_selection(self):
        assert self.user_id == "runtime-owner"
        assert context.get() == "owner"
        return deepcopy(selected)

    def custom_model(self):
        assert context.get() == "owner"
        observed.append((deepcopy(self.model), threading.get_ident()))
        return chosen

    class ExtendedAgent(AgentComponent):
        _resolve_selected_model = custom_selection
        _get_llm = custom_model

    cls = ExtendedAgent if override_kind == "subclass" else AgentComponent
    c = cls(_user_id="runtime-owner", model=SELECTION)
    if override_kind == "instance":
        monkeypatch.setattr(c, "_resolve_selected_model", MethodType(custom_selection, c))
        monkeypatch.setattr(c, "_get_llm", MethodType(custom_model, c))
    c.set_attributes({"tools": [], "add_current_date_tool": False, "chat_history": []})
    monkeypatch.setattr(
        "lfx.services.model_provider_policy.aresolve_model_provider_policy", AsyncMock(return_value=policy())
    )
    native = AsyncMock(side_effect=AssertionError("custom synchronous model override bypassed"))
    monkeypatch.setattr(agent_module, "aget_llm", native)
    monkeypatch.setattr(type(c), "get_memory_data", AsyncMock(return_value=[]))
    token = context.set("owner")
    try:
        llm, _history, _tools = await c.get_agent_requirements()
        provider, name, _connected = await c._aselected_model_remediation_context()
    finally:
        context.reset(token)
    assert llm is chosen
    assert llm.base_url == "https://owned.example/v1"
    assert provider == "OpenAI"
    assert name == "owned-model"
    assert observed[0][0] == selected
    assert observed[0][1] != caller_thread
    native.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("override_kind", ["subclass", "instance"])
async def test_decorated_agent_sync_overrides_are_not_skipped(monkeypatch, override_kind):
    from contextvars import ContextVar
    from functools import wraps
    from types import MethodType

    context = ContextVar("decorated-owner", default="missing")
    selected = [{"name": "decorated-model", "provider": "OpenAI", "metadata": {}}]
    chosen = SimpleNamespace(model_name="decorated-model", base_url="https://decorated.example/v1")
    calls = []

    @wraps(AgentComponent._resolve_selected_model)
    def select(self):
        assert self.user_id == "runtime-owner"
        assert context.get() == "owner"
        calls.append("select")
        return deepcopy(selected)

    @wraps(AgentComponent._get_llm)
    def build(self):
        assert self.model == selected
        assert context.get() == "owner"
        calls.append("build")
        return chosen

    class DecoratedAgent(AgentComponent):
        _resolve_selected_model = select
        _get_llm = build

    c = (DecoratedAgent if override_kind == "subclass" else AgentComponent)(_user_id="runtime-owner", model=SELECTION)
    if override_kind == "instance":
        monkeypatch.setattr(c, "_resolve_selected_model", MethodType(select, c))
        monkeypatch.setattr(c, "_get_llm", MethodType(build, c))
    c.set_attributes({"tools": [], "add_current_date_tool": False, "chat_history": []})
    monkeypatch.setattr(
        "lfx.services.model_provider_policy.aresolve_model_provider_policy", AsyncMock(return_value=policy())
    )
    native = AsyncMock(side_effect=AssertionError("decorated override skipped"))
    monkeypatch.setattr(agent_module, "aget_llm", native)
    monkeypatch.setattr(type(c), "get_memory_data", AsyncMock(return_value=[]))
    token = context.set("owner")
    try:
        llm, _history, _tools = await c.get_agent_requirements()
    finally:
        context.reset(token)
    assert llm is chosen
    assert calls == ["select", "build"]
    native.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("override_kind", ["subclass", "instance", "decorated"])
async def test_custom_remediation_context_keeps_provenance_and_connected_target(monkeypatch, override_kind):
    from contextvars import ContextVar
    from functools import wraps
    from types import MethodType

    from lfx.schema.message import Message

    context = ContextVar("remediation-owner", default="missing")
    target = SimpleNamespace(model_name="owned-connected-model")

    def provenance(self):
        assert self.user_id == "runtime-owner"
        assert context.get() == "owner"
        return "OpenAI", "owned-connected-model", target

    if override_kind == "decorated":
        provenance = wraps(AgentComponent._selected_model_remediation_context)(provenance)

    class CustomContextAgent(AgentComponent):
        _selected_model_remediation_context = provenance

    c = (AgentComponent if override_kind == "instance" else CustomContextAgent)(
        _user_id="runtime-owner", model=SELECTION
    )
    if override_kind == "instance":
        monkeypatch.setattr(c, "_selected_model_remediation_context", MethodType(provenance, c))
    monkeypatch.setattr(
        "lfx.services.model_provider_policy.aresolve_model_provider_policy", AsyncMock(return_value=policy())
    )
    remediation = SimpleNamespace(name="test-remediation", overrides={"temperature": 0})
    find = Mock(side_effect=[remediation])
    apply = Mock(return_value=True)
    monkeypatch.setattr("lfx.base.models.model_remediation.find_remediation", find)
    monkeypatch.setattr("lfx.base.models.model_remediation.apply_overrides_to_model", apply)
    answer = Message(text="answer")
    run = AsyncMock(side_effect=[RuntimeError("request validation"), answer])
    token = context.set("owner")
    try:
        assert await c._run_agent_with_model_remediation(run) is answer
    finally:
        context.reset(token)
    apply.assert_called_once_with(target, remediation.overrides)
    assert find.call_args.args[1] == "OpenAI"
    assert run.await_count == 2


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
