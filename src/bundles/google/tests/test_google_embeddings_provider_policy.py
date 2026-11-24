from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from lfx.custom.custom_component.component import Component
from lfx.custom.utils import build_custom_component_template
from lfx.graph.vertex.base import Vertex
from lfx.services.model_provider_policy import (
    BaseModelProviderPolicyService,
    ModelProviderPolicyError,
    ModelProviderPolicyPurpose,
)
from lfx_google.components.google import google_generative_ai_embeddings
from lfx_google.components.google.google_generative_ai_embeddings import GoogleGenerativeAIEmbeddingsComponent


class _UnhydratedSecret:
    def __bool__(self) -> bool:
        raise AssertionError


@pytest.mark.parametrize(
    "purpose",
    [ModelProviderPolicyPurpose.CONFIGURE, ModelProviderPolicyPurpose.USE],
)
async def test_google_embeddings_are_gated_as_google_before_secret_hydration(monkeypatch, purpose) -> None:
    component = GoogleGenerativeAIEmbeddingsComponent(_user_id="resource-owner")
    denial = ModelProviderPolicyError("google-generative-ai", purpose)
    snapshot = SimpleNamespace(require=Mock(side_effect=denial))
    resolve_policy = AsyncMock(return_value=snapshot)
    monkeypatch.setattr("lfx.services.model_provider_policy.aresolve_model_provider_policy", resolve_policy)

    with pytest.raises(ModelProviderPolicyError):
        await component.arequire_model_provider_policy(
            purpose,
            user_id="policy-actor",
            parameters={"api_key": _UnhydratedSecret()},
        )

    assert component.model_provider_id == "google-generative-ai"
    resolve_policy.assert_awaited_once_with(
        user_id="policy-actor",
        providers=["google-generative-ai"],
        purpose=purpose,
    )
    snapshot.require.assert_called_once_with("google-generative-ai")


class _ModelPolicy(BaseModelProviderPolicyService):
    def get_allowed_provider_ids(self, *, context, candidate_provider_ids, purpose):
        _ = context, purpose
        return candidate_provider_ids

    def get_blocked_model_keys(self, *, context, purpose):
        _ = context, purpose
        return frozenset({"google-generative-ai::embeddings::models/text-embedding-004"})


@pytest.mark.parametrize("embedded_source", [False, True])
async def test_google_embedding_model_denied_before_credentials_or_client(monkeypatch, embedded_source):
    service = _ModelPolicy()
    monkeypatch.setattr("lfx.services.deps.get_model_provider_policy_service", lambda: service)
    if embedded_source:
        source = Path(google_generative_ai_embeddings.__file__).read_text()
        _, component = build_custom_component_template(Component(_code=source, _user_id="resource-owner"))
    else:
        component = GoogleGenerativeAIEmbeddingsComponent(_user_id="resource-owner")
    component.api_key = _UnhydratedSecret()
    client = Mock(side_effect=AssertionError("constructed SDK client"))
    monkeypatch.setattr(
        "lfx_google.components.google.google_generative_ai_embeddings.GoogleGenerativeAIEmbeddings", client
    )
    with pytest.raises(ModelProviderPolicyError) as error:
        component.build_embeddings()
    assert error.value.model_name == "models/text-embedding-004"
    client.assert_not_called()

    vertex = object.__new__(Vertex)
    vertex.display_name = component.display_name
    vertex.custom_component = component
    vertex.params = {"model_name": "models/text-embedding-004"}
    vertex._build_each_vertex_in_params_dict = AsyncMock()
    vertex._build_results = AsyncMock()
    with pytest.raises(ModelProviderPolicyError):
        await vertex._build(fallback_to_env_vars=False, user_id="resource-owner")
    vertex._build_each_vertex_in_params_dict.assert_not_awaited()
    vertex._build_results.assert_not_awaited()


def test_allowed_google_embedding_model_still_builds(monkeypatch):
    service = _ModelPolicy()
    monkeypatch.setattr("lfx.services.deps.get_model_provider_policy_service", lambda: service)
    component = GoogleGenerativeAIEmbeddingsComponent(
        _user_id="resource-owner", model_name="models/gemini-embedding-001", api_key="local-test-key"
    )
    client = Mock(return_value="allowed-client")
    monkeypatch.setattr(
        "lfx_google.components.google.google_generative_ai_embeddings.GoogleGenerativeAIEmbeddings", client
    )
    assert component.build_embeddings() == "allowed-client"
    client.assert_called_once_with(
        model="models/gemini-embedding-001",
        google_api_key="local-test-key",  # pragma: allowlist secret
    )
