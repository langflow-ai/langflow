"""Async runtime policy selection and early-denial ordering before component work."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from lfx.base.embeddings.model import LCEmbeddingsModel
from lfx.base.models.model import LCModelComponent
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DropdownInput, ModelInput, StrInput
from lfx.io import Output
from lfx.services.model_provider_policy import ModelProviderPolicyPurpose


class StandaloneOpenAI(LCModelComponent):
    display_name = "OpenAI"
    outputs = [Output(name="model", display_name="Model", method="build_model")]

    def build_model(self):
        return object()


class StandaloneOllamaEmbedding(LCEmbeddingsModel):
    display_name = "Ollama"
    outputs = [Output(name="embeddings", display_name="Embeddings", method="build_embeddings")]

    def build_embeddings(self):
        return object()


class Composite(Component):
    model_provider_policy_mode = "delegate"
    inputs = [
        ModelInput(name="model", display_name="Model"),
        ModelInput(name="secondary", display_name="Secondary"),
        StrInput(name="provider", display_name="Provider", load_from_db=False),
    ]
    outputs = [Output(name="value", display_name="Value", method="build_value")]

    def build_value(self):
        return "safe"


class Legacy(Component):
    model_provider_policy_mode = "delegate"
    inputs = [DropdownInput(name="agent_llm", display_name="Provider", options=["OpenAI", "Anthropic", "Custom"])]
    outputs = [Output(name="value", display_name="Value", method="build_value")]

    def build_value(self):
        return "safe"


class CustomModel(LCModelComponent):
    model_provider_policy_mode = "none"
    display_name = "Custom"
    outputs = [Output(name="model", display_name="Model", method="build_model")]

    def build_model(self):
        return object()


def configure(component, parameters=None):
    component._user_id = "policy-owner"
    if parameters is not None:
        component.set_attributes(parameters)
        component._parameters = dict(parameters)
    return component


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("component", "parameters", "old_ids", "new_ids"),
    [
        (StandaloneOpenAI, {}, ["openai"], ["openai"]),
        (StandaloneOllamaEmbedding, {}, ["ollama"], ["ollama"]),
        (Composite, {"model": [{"name": "m", "provider": "OpenAI"}]}, [], ["openai"]),
        (Composite, {"model": [{"name": "m", "provider": "OpenAI"}], "provider": "Ollama"}, [], ["ollama"]),
        (
            Composite,
            {"model": [{"name": "m", "provider": "OpenAI"}], "secondary": [{"name": "m", "provider": "Anthropic"}]},
            [],
            ["openai", "anthropic"],
        ),
        (Legacy, {"agent_llm": "Anthropic"}, [], ["anthropic"]),
        (Legacy, {"agent_llm": "Custom"}, [], []),
        (CustomModel, {}, [], []),
    ],
)
async def test_async_selection_preserves_standalone_and_matches_existing_vertex_gate(
    monkeypatch, component, parameters, old_ids, new_ids
):
    c = configure(component(), parameters)
    seen = []
    monkeypatch.setattr(
        "lfx.services.model_provider_policy.require_model_provider", lambda **kwargs: seen.append(kwargs["provider"])
    )
    c.require_model_provider_policy(ModelProviderPolicyPurpose.USE)
    assert seen == old_ids
    snapshot = SimpleNamespace(require=Mock())
    resolve = AsyncMock(return_value=snapshot)
    monkeypatch.setattr("lfx.services.model_provider_policy.aresolve_model_provider_policy", resolve)
    await c.arequire_model_provider_policy(ModelProviderPolicyPurpose.USE)
    if new_ids:
        resolve.assert_awaited_once_with(
            user_id="policy-owner", providers=new_ids, purpose=ModelProviderPolicyPurpose.USE
        )
        assert [x.args[0] for x in snapshot.require.call_args_list] == new_ids
    else:
        resolve.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("component", "parameters"),
    [
        (StandaloneOpenAI, {}),
        (StandaloneOllamaEmbedding, {}),
        (Composite, {"model": [{"name": "m", "provider": "OpenAI"}]}),
        (Legacy, {"agent_llm": "Anthropic"}),
    ],
)
async def test_denial_precedes_trace_setup_outputs_and_provider_body(monkeypatch, component, parameters):
    c = configure(component(), parameters)
    resolve = AsyncMock(return_value=SimpleNamespace(require=Mock(side_effect=PermissionError("denied"))))
    monkeypatch.setattr("lfx.services.model_provider_policy.aresolve_model_provider_policy", resolve)
    monkeypatch.setattr(
        "lfx.services.model_provider_policy.require_model_provider",
        Mock(side_effect=AssertionError("sync gate forbidden")),
    )
    outputs = Mock(side_effect=AssertionError("outputs accessed before gate"))
    traced = AsyncMock(side_effect=AssertionError("trace started before gate"))
    plain = AsyncMock(side_effect=AssertionError("provider body before gate"))
    monkeypatch.setattr(c, "_get_outputs_to_process", outputs)
    monkeypatch.setattr(c, "_build_with_tracing", traced)
    monkeypatch.setattr(c, "_build_without_tracing", plain)
    with pytest.raises(PermissionError, match="denied"):
        await c.build_results()
    outputs.assert_not_called()
    traced.assert_not_awaited()
    plain.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_policy_failure_or_cancellation_does_not_run_component(monkeypatch, cancel):
    c = configure(StandaloneOpenAI())
    started = asyncio.Event()

    async def resolve(**_kwargs):
        started.set()
        if not cancel:
            msg = "lookup failed"
            raise RuntimeError(msg)
        await asyncio.Event().wait()

    monkeypatch.setattr("lfx.services.model_provider_policy.aresolve_model_provider_policy", resolve)
    body = AsyncMock(side_effect=AssertionError("component ran after failed policy"))
    monkeypatch.setattr(c, "_build_without_tracing", body)
    task = asyncio.create_task(c.build_results())
    await asyncio.wait_for(started.wait(), 0.5)
    if cancel:
        task.cancel()
    with pytest.raises(asyncio.CancelledError if cancel else RuntimeError):
        await task
    body.assert_not_awaited()


@pytest.mark.asyncio
async def test_custom_sync_policy_extension_is_not_bypassed(monkeypatch):
    from contextvars import ContextVar

    context = ContextVar("policy-context", default=False)

    class ExtraPolicy(StandaloneOpenAI):
        def require_model_provider_policy(self, purpose):
            assert context.get() is True
            assert purpose is ModelProviderPolicyPurpose.USE
            msg = "extra restriction"
            raise PermissionError(msg)

    c = configure(ExtraPolicy())
    monkeypatch.setattr(
        "lfx.services.model_provider_policy.aresolve_model_provider_policy",
        AsyncMock(return_value=SimpleNamespace(require=Mock())),
    )
    body = AsyncMock(side_effect=AssertionError("component ran after custom denial"))
    monkeypatch.setattr(c, "_build_without_tracing", body)
    token = context.set(True)
    try:
        with pytest.raises(PermissionError, match="extra restriction"):
            await c.build_results()
    finally:
        context.reset(token)
    body.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["deny", "unavailable", "cancel"])
async def test_real_memory_provider_metadata_gate_precedes_runtime_work(monkeypatch, failure):
    from lfx.components.files_and_knowledge.memory_retrieval import MemoryBaseComponent

    c = configure(MemoryBaseComponent(), {"memory_base": "attached-memory"})
    metadata = AsyncMock(return_value=("OpenAI", "text-embedding-3-small"))
    monkeypatch.setattr(c, "_policy_embedding_selection", metadata)
    reached = asyncio.Event()

    async def resolve(**kwargs):
        assert kwargs["providers"] == ["openai"]
        assert kwargs["user_id"] == "policy-owner"
        reached.set()
        if failure == "unavailable":
            msg = "policy unavailable"
            raise RuntimeError(msg)
        if failure == "cancel":
            await asyncio.Event().wait()
        return SimpleNamespace(require=Mock(side_effect=PermissionError("denied")))

    monkeypatch.setattr("lfx.services.model_provider_policy.aresolve_model_provider_policy", resolve)
    outputs = Mock(side_effect=AssertionError("inputs or output accessed before policy"))
    traced = AsyncMock(side_effect=AssertionError("trace started before policy"))
    body = AsyncMock(side_effect=AssertionError("retrieval or secret accessed before policy"))
    monkeypatch.setattr(c, "_get_outputs_to_process", outputs)
    monkeypatch.setattr(c, "_build_with_tracing", traced)
    monkeypatch.setattr(c, "_build_without_tracing", body)
    task = asyncio.create_task(c.build_results())
    await asyncio.wait_for(reached.wait(), 0.5)
    if failure == "cancel":
        task.cancel()
    expected = {"deny": PermissionError, "unavailable": RuntimeError, "cancel": asyncio.CancelledError}[failure]
    with pytest.raises(expected):
        await task
    metadata.assert_awaited_once_with("attached-memory")
    outputs.assert_not_called()
    traced.assert_not_awaited()
    body.assert_not_awaited()
