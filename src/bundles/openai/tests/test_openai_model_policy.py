"""Legacy OpenAI builders enforce model policy before constructing SDK clients."""

import pytest
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from lfx.services.model_provider_policy import BaseModelProviderPolicyService, ModelProviderPolicyError
from lfx_openai.components.openai.openai import OpenAIEmbeddingsComponent
from lfx_openai.components.openai.openai_chat_model import OpenAIModelComponent


class _BlockedModelPolicy(BaseModelProviderPolicyService):
    def get_allowed_provider_ids(self, *, context, candidate_provider_ids, purpose):
        _ = context, purpose
        return candidate_provider_ids

    def get_blocked_model_keys(self, *, context, purpose):
        _ = context, purpose
        return frozenset({"openai::llm::gpt-4o-mini", "openai::embeddings::text-embedding-3-small"})


@pytest.fixture(autouse=True)
def blocked_models(monkeypatch):
    service = _BlockedModelPolicy()
    monkeypatch.setattr("lfx.services.deps.get_model_provider_policy_service", lambda: service)


def test_openai_chat_model_denied_before_secret_access(monkeypatch):
    component = OpenAIModelComponent(_user_id="user-1", model_name="gpt-4o-mini")

    def unexpected_secret_access(*_args, **_kwargs):
        pytest.fail("blocked model read its API key")

    monkeypatch.setattr("lfx_openai.components.openai.openai_chat_model.secret_value_to_str", unexpected_secret_access)
    with pytest.raises(ModelProviderPolicyError) as error:
        component.build_model()
    assert error.value.model_name == "gpt-4o-mini"


def test_openai_embedding_model_denied_before_endpoint_clients(monkeypatch):
    component = OpenAIEmbeddingsComponent(_user_id="user-1", model="text-embedding-3-small")

    def unexpected_client_construction(*_args, **_kwargs):
        pytest.fail("blocked model constructed endpoint clients")

    monkeypatch.setattr(
        "lfx_openai.components.openai.openai.openai_compatible_client_kwargs", unexpected_client_construction
    )
    with pytest.raises(ModelProviderPolicyError) as error:
        component.build_embeddings()
    assert error.value.model_name == "text-embedding-3-small"


def test_allowed_openai_models_still_construct_real_sdk_clients():
    chat = OpenAIModelComponent(_user_id="user-1", model_name="gpt-4o", api_key="local-test-key")
    embeddings = OpenAIEmbeddingsComponent(
        _user_id="user-1", model="text-embedding-3-large", openai_api_key="local-test-key"
    )

    assert isinstance(chat.build_model(), ChatOpenAI)
    assert isinstance(embeddings.build_embeddings(), OpenAIEmbeddings)


def test_openai_request_model_override_cannot_bypass_policy():
    component = OpenAIModelComponent(
        _user_id="user-1",
        model_name="gpt-4o",
        model_kwargs={"extra_body": {"model": "gpt-4o-mini"}},
        api_key="local-test-key",  # pragma: allowlist secret
    )
    with pytest.raises(ModelProviderPolicyError) as error:
        component.build_model()
    assert error.value.model_name == "gpt-4o-mini"
