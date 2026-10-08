"""Native model output/legacy selection paths preserve synchronous compatibility."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from lfx.components.models_and_agents import agent as agent_module
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.utils.async_helpers import async_call_method

SELECTION = [{"name": "gpt-4o-mini", "provider": "OpenAI", "metadata": {}}]


def policy():
    return SimpleNamespace(
        require=Mock(), allows=lambda name: name == "OpenAI", allows_model=lambda *_args, **_kwargs: True
    )


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
        provider, name, _connected = await async_call_method(c, "_selected_model_remediation_context")
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
async def test_legacy_agent_uses_named_lookup_and_native_async_credentials(monkeypatch):
    c = AgentComponent(_user_id="runtime-owner", model=[], agent_llm="OpenAI", model_name="gpt-4o-mini")
    c.set_attributes({"tools": [], "add_current_date_tool": False, "chat_history": []})
    p = policy()
    monkeypatch.setattr("lfx.services.model_provider_policy.aresolve_model_provider_policy", AsyncMock(return_value=p))
    options = Mock(return_value=SELECTION[0])
    factory = AsyncMock(return_value=object())
    monkeypatch.setattr(agent_module, "get_language_model_option", options)
    monkeypatch.setattr(agent_module, "aget_llm", factory)
    monkeypatch.setattr(agent_module, "get_llm", Mock(side_effect=AssertionError("sync model factory forbidden")))
    monkeypatch.setattr(type(c), "get_memory_data", AsyncMock(return_value=[]))
    llm, history, _tools = await c.get_agent_requirements()
    assert llm is factory.return_value
    assert history == []
    options.assert_called_once_with("OpenAI", "gpt-4o-mini")
    factory.assert_awaited_once()


@pytest.mark.asyncio
async def test_legacy_direct_agent_denial_precedes_catalog_and_model(monkeypatch):
    c = AgentComponent(_user_id="runtime-owner", model=[], agent_llm="OpenAI", model_name="gpt-4o-mini")
    p = policy()
    p.require.side_effect = PermissionError("denied")
    monkeypatch.setattr("lfx.services.model_provider_policy.aresolve_model_provider_policy", AsyncMock(return_value=p))
    options = Mock(side_effect=AssertionError("legacy catalog before denial"))
    factory = AsyncMock()
    monkeypatch.setattr(agent_module, "get_language_model_option", options)
    monkeypatch.setattr(agent_module, "aget_llm", factory)
    with pytest.raises(PermissionError):
        await c.message_response()
    options.assert_not_called()
    factory.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("failing_method", ["_resolve_selected_model", "_model_remediation_context"])
async def test_failed_remediation_context_is_logged_without_masking_original_error(
    monkeypatch, asynchronous, failing_method
):
    component = AgentComponent(_user_id="runtime-owner", model=SELECTION)
    monkeypatch.setattr(component, failing_method, Mock(side_effect=ValueError("invalid selection")))
    log = SimpleNamespace(debug=Mock(), adebug=AsyncMock())
    monkeypatch.setattr(agent_module, "logger", log)
    if asynchronous:
        assert await component._aselected_model_remediation_context() == (None, None, None)
        log.adebug.assert_awaited_once()
    else:
        assert component._selected_model_remediation_context() == (None, None, None)
        log.debug.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("signature", ["no_arguments", "keyword_only", "async", "decorated"])
async def test_original_agent_graph_overrides_reuse_attempt_model(monkeypatch, signature):
    from functools import wraps

    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    calls = []

    def original(self, *, allow_interrupts=True):
        calls.append(allow_interrupts)
        return super(ExtendedAgent, self).create_agent_runnable(allow_interrupts=allow_interrupts)

    def no_arguments(self):
        return original(self)

    async def asynchronous(self, *, allow_interrupts=True):
        return original(self, allow_interrupts=allow_interrupts)

    override = {
        "no_arguments": no_arguments,
        "keyword_only": original,
        "async": asynchronous,
        "decorated": wraps(AgentComponent.create_agent_runnable)(original),
    }[signature]

    class ExtendedAgent(AgentComponent):
        create_agent_runnable = override

    component = ExtendedAgent()
    component.set_attributes({"tools": [], "chat_history": [], "input_value": "hello", "system_prompt": "Be brief."})
    monkeypatch.setattr(component, "_get_llm", Mock(side_effect=AssertionError("attempt model resolved twice")))
    model = FakeListChatModel(responses=["native graph answer"])
    graph = await component._acreate_agent_runnable(model)
    response = await graph.ainvoke({"messages": [("user", "hello")]})
    assert response["messages"][-1].content == "native graph answer"
    assert calls == [True]
    if signature != "no_arguments":
        await component._acreate_agent_runnable(model, allow_interrupts=False)
        assert calls == [True, False]
    if signature == "async":
        with pytest.raises(AssertionError, match="resolved twice"):
            await component.create_agent_runnable()
    else:
        with pytest.raises(AssertionError, match="resolved twice"):
            component.create_agent_runnable()


@pytest.mark.asyncio
async def test_attempt_model_binding_is_concurrent_owner_scoped_and_reset_on_failure(monkeypatch):
    import asyncio
    from types import MethodType

    from lfx.components.models_and_agents.agent import _resolved_agent_model

    first, second = AgentComponent(), AgentComponent()
    models = [object(), object()]
    entered = asyncio.Event()
    count = 0

    async def create(component):
        nonlocal count
        count += 1
        if count == 2:
            entered.set()
        await entered.wait()
        assert _resolved_agent_model.get() == (component, models[0] if component is first else models[1])
        if component is first:
            message = "construction failed"
            raise ValueError(message)
        return models[1]

    monkeypatch.setattr(first, "create_agent_runnable", MethodType(create, first))
    monkeypatch.setattr(second, "create_agent_runnable", MethodType(create, second))
    results = await asyncio.gather(
        first._acreate_agent_runnable(models[0]), second._acreate_agent_runnable(models[1]), return_exceptions=True
    )
    assert isinstance(results[0], ValueError)
    assert results[1] is models[1]
    assert _resolved_agent_model.get() is None
