"""Standalone model clients obey the same model denylist as unified selectors."""

from unittest.mock import AsyncMock

import pytest
from lfx.base.embeddings.model import LCEmbeddingsModel
from lfx.base.models.model import LCModelComponent
from lfx.graph.vertex.base import Vertex
from lfx.io import DictInput, Output, StrInput
from lfx.services.model_provider_policy import (
    BaseModelProviderPolicyService,
    ModelProviderPolicyError,
    ModelProviderPolicyPurpose,
)


class _ModelPolicy(BaseModelProviderPolicyService):
    def __init__(self, blocked, *, allowed=True):
        super().__init__()
        self.blocked = blocked
        self.allowed = allowed

    def get_allowed_provider_ids(self, *, context, candidate_provider_ids, purpose):
        _ = context, purpose
        return candidate_provider_ids if self.allowed else frozenset()

    def get_blocked_model_keys(self, *, context, purpose):
        _ = context, purpose
        return frozenset(self.blocked)


def _component(base, field="model_name", *, default="blocked-model", mode="standalone", asynchronous=False):
    method_name = "build_embeddings" if base is LCEmbeddingsModel else "build_model"
    calls = []

    def build(self):
        calls.append(getattr(self, field))
        return "allowed-client"

    async def abuild(self):
        return build(self)

    cls = type(
        "StandaloneModel",
        (base,),
        {
            "display_name": "OpenAI",
            "model_provider_policy_mode": mode,
            "inputs": [
                StrInput(name=field, value=default),
                DictInput(name="model_kwargs"),
                StrInput(name="custom_model"),
            ],
            "outputs": [Output(name="client", method=method_name)],
            method_name: abuild if asynchronous else build,
        },
    )
    return cls(_user_id="user-1"), method_name, calls


@pytest.fixture
def policy(monkeypatch):
    def install(*blocked, allowed=True):
        service = _ModelPolicy(blocked, allowed=allowed)
        monkeypatch.setattr("lfx.services.deps.get_model_provider_policy_service", lambda: service)

    return install


@pytest.mark.parametrize(("base", "model_type"), [(LCModelComponent, "llm"), (LCEmbeddingsModel, "embeddings")])
@pytest.mark.parametrize("field", ["model_name", "model", "model_id"])
@pytest.mark.parametrize("key", ["blocked-model", "openai::blocked-model", "openai::{type}::blocked-model"])
def test_direct_builder_denies_model_before_client_construction(policy, base, model_type, field, key):
    policy(key.format(type=model_type))
    component, method, calls = _component(base, field)

    with pytest.raises(ModelProviderPolicyError) as error:
        getattr(component, method)()

    assert error.value.provider_id == "openai"
    assert error.value.model_name == "blocked-model"
    assert calls == []


@pytest.mark.parametrize(("base", "model_type"), [(LCModelComponent, "llm"), (LCEmbeddingsModel, "embeddings")])
async def test_build_results_denies_model_before_tracing_or_input_setup(policy, base, model_type):
    policy(f"openai::{model_type}::blocked-model")
    component, _, calls = _component(base)
    component._build_with_tracing = AsyncMock()
    component._build_without_tracing = AsyncMock()

    with pytest.raises(ModelProviderPolicyError):
        await component.build_results()

    assert calls == []
    component._build_with_tracing.assert_not_awaited()
    component._build_without_tracing.assert_not_awaited()


@pytest.mark.parametrize(("base", "model_type"), [(LCModelComponent, "llm"), (LCEmbeddingsModel, "embeddings")])
async def test_vertex_uses_raw_model_before_upstream_or_local_credential_hydration(policy, base, model_type):
    policy(f"openai::{model_type}::blocked-model")
    component, _, calls = _component(base, default="allowed-model")
    vertex = object.__new__(Vertex)
    vertex.display_name = "Standalone model"
    vertex.custom_component = component
    vertex.params = {"model_name": "blocked-model"}
    vertex._build_each_vertex_in_params_dict = AsyncMock(side_effect=AssertionError("hydrated upstream input"))
    vertex._build_results = AsyncMock(side_effect=AssertionError("hydrated local credentials"))

    with pytest.raises(ModelProviderPolicyError):
        await vertex._build(fallback_to_env_vars=False, user_id="user-1")

    assert calls == []
    vertex._build_each_vertex_in_params_dict.assert_not_awaited()
    vertex._build_results.assert_not_awaited()


@pytest.mark.parametrize("base", [LCModelComponent, LCEmbeddingsModel])
def test_allowed_model_still_builds_and_provider_denial_still_applies(policy, base):
    policy("openai::blocked-model")
    component, method, calls = _component(base, default="allowed-model")
    assert getattr(component, method)() == "allowed-client"
    assert calls == ["allowed-model"]

    policy(allowed=False)
    with pytest.raises(ModelProviderPolicyError) as error:
        getattr(component, method)()
    assert error.value.model_name is None
    assert calls == ["allowed-model"]


@pytest.mark.parametrize(("base", "other_type"), [(LCModelComponent, "embeddings"), (LCEmbeddingsModel, "llm")])
def test_typed_model_block_preserves_other_model_type(policy, base, other_type):
    policy(f"openai::{other_type}::blocked-model")
    component, method, calls = _component(base)
    assert getattr(component, method)() == "allowed-client"
    assert calls == ["blocked-model"]


@pytest.mark.parametrize("mode", ["delegate", "none"])
def test_direct_builder_preserves_policy_modes(policy, mode):
    policy(allowed=False)
    component, method, calls = _component(LCModelComponent, mode=mode)
    assert getattr(component, method)() == "allowed-client"
    assert calls == ["blocked-model"]


async def test_async_builder_retains_coroutine_contract_and_checks_model(policy):
    import inspect

    policy("openai::blocked-model")
    component, method, calls = _component(LCModelComponent, asynchronous=True)
    assert inspect.iscoroutinefunction(getattr(component, method))
    with pytest.raises(ModelProviderPolicyError):
        await getattr(component, method)()
    assert calls == []


@pytest.mark.parametrize("model_kwargs", [{"model": "blocked-model"}, {"extra_body": {"model": "blocked-model"}}])
@pytest.mark.parametrize("base", [LCModelComponent, LCEmbeddingsModel])
async def test_sdk_model_overrides_cannot_hide_blocked_model(policy, base, model_kwargs):
    policy("openai::blocked-model")
    component, method, calls = _component(base, default="allowed-model")
    params = {"model_name": "allowed-model", "model_kwargs": model_kwargs}
    with pytest.raises(ModelProviderPolicyError):
        await component.arequire_model_provider_policy(ModelProviderPolicyPurpose.USE, parameters=params)
    component.set(**params)
    with pytest.raises(ModelProviderPolicyError):
        getattr(component, method)()
    assert calls == []


def test_historical_embedding_subclass_uses_embedding_policy_type(policy):
    class HistoricalEmbeddings(LCModelComponent):
        display_name = "OpenAI"
        inputs = [StrInput(name="model_name", value="blocked-model")]
        outputs = [Output(name="embeddings", method="build_embeddings")]

        def build_embeddings(self):
            return "allowed-client"

    component = HistoricalEmbeddings(_user_id="user-1")
    policy("openai::llm::blocked-model")
    assert component.build_embeddings() == "allowed-client"
    policy("openai::embeddings::blocked-model")
    with pytest.raises(ModelProviderPolicyError):
        component.build_embeddings()


async def test_custom_model_id_checks_resolved_selector(policy):
    policy("openai::blocked-model")
    component, method, calls = _component(LCModelComponent, field="model_id", default="custom")
    params = {"model_id": "custom", "custom_model": "blocked-model"}
    with pytest.raises(ModelProviderPolicyError):
        await component.arequire_model_provider_policy(ModelProviderPolicyPurpose.USE, parameters=params)
    component.set(**params)
    with pytest.raises(ModelProviderPolicyError):
        getattr(component, method)()
    assert calls == []


def test_builder_wrapper_preserves_future_annotation_globals():
    from lfx.schema.data import Data

    namespace = {"LCModelComponent": LCModelComponent, "ProviderAlias": Data, "__name__": __name__}
    exec(  # noqa: S102
        "from __future__ import annotations\n"
        "class AnnotatedModel(LCModelComponent):\n"
        "    def build_model(self) -> ProviderAlias:\n"
        "        return ProviderAlias()\n",
        namespace,
    )
    component = namespace["AnnotatedModel"]()
    assert component._get_method_return_type("build_model") == ["JSON"]


def test_builder_wrapper_does_not_evaluate_deferred_annotations():
    from lfx.custom.custom_component.component import check_model_provider_policy

    calls = []

    def builder(self):
        return self

    if not hasattr(builder, "__annotate__"):
        pytest.skip("deferred annotations require Python 3.14")

    def annotate(_format):
        calls.append("evaluated")
        return {"return": str}

    builder.__annotate__ = annotate
    wrapper = check_model_provider_policy(builder)
    assert wrapper.__annotate__ is annotate
    assert calls == []


async def test_raw_unresolved_model_is_checked_when_runtime_value_arrives(policy):
    policy("openai::blocked-model")
    component, method, calls = _component(LCModelComponent, default="allowed-model")
    await component.arequire_model_provider_policy(ModelProviderPolicyPurpose.USE, parameters={"model_name": object()})
    component.set(model_name="blocked-model")
    with pytest.raises(ModelProviderPolicyError):
        getattr(component, method)()
    assert calls == []


def test_get_llm_preserves_policy_denial(policy, monkeypatch):
    from types import SimpleNamespace

    policy("openai::blocked-model")
    outer, _, calls = _component(LCModelComponent)
    inner_cls = type(outer)
    fake_module = SimpleNamespace(FakeProvider=inner_cls)
    monkeypatch.setattr("lfx.base.models.model.importlib.import_module", lambda _name: fake_module)
    model_info = {"FakeProvider": {"display_name": "OpenAI", "inputs": inner_cls.inputs}}

    with pytest.raises(ModelProviderPolicyError) as error:
        outer.get_llm("OpenAI", model_info)

    assert error.value.code == "policy_blocked"
    assert error.value.model_name == "blocked-model"
    assert calls == []
    # Non-policy failures keep the legacy ValueError surface.
    with pytest.raises(ValueError, match="Error building"):
        outer.get_llm("Missing Provider", model_info)
