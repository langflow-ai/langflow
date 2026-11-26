"""Unified providers must authorize credentials before using a configured endpoint."""

import sys
from functools import partial
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from lfx.base.models import model_utils, unified_models
from lfx.base.models.unified_models import instantiation

OPERATOR_KEY = "fixture-operator-key"  # pragma: allowlist secret
USER_KEY = "fixture-user-key"  # pragma: allowlist secret
ENDPOINT = "https://models.example.invalid"


@pytest.fixture(autouse=True)
def provider_environment(monkeypatch):
    monkeypatch.setenv("AZURE_AI_FOUNDRY_API_KEY", OPERATOR_KEY)
    monkeypatch.setenv("WATSONX_APIKEY", OPERATOR_KEY)
    monkeypatch.delenv("AZURE_AI_FOUNDRY_ENDPOINT", raising=False)
    monkeypatch.delenv("LANGFLOW_AZURE_AI_FOUNDRY_ENDPOINT", raising=False)
    monkeypatch.delenv("WATSONX_URL", raising=False)
    monkeypatch.delenv("LANGFLOW_WATSONX_URL", raising=False)
    monkeypatch.setattr("lfx.base.models.provider_ssrf.get_provider_credential_allowed_hosts", list)


@pytest.mark.parametrize("provider", ["Azure AI Foundry", "IBM WatsonX"])
@pytest.mark.parametrize("kind", ["chat", "embeddings", "validation"])
def test_custom_destination_rejected_before_provider_io(monkeypatch, provider, kind):
    settings = {
        "AZURE_AI_FOUNDRY_API_KEY": OPERATOR_KEY,
        "AZURE_AI_FOUNDRY_ENDPOINT": ENDPOINT,
        "WATSONX_APIKEY": OPERATOR_KEY,
        "WATSONX_URL": ENDPOINT,
        "WATSONX_PROJECT_ID": "fixture-project",
    }
    io = Mock()
    monkeypatch.setattr(unified_models, "get_all_variables_for_provider", lambda *_args: settings)
    monkeypatch.setattr(unified_models, "get_api_key_for_provider", lambda *_args: OPERATOR_KEY)
    monkeypatch.setattr(unified_models, "get_model_class", lambda _name: io)
    monkeypatch.setattr(unified_models, "get_embedding_class", lambda _name: io)
    monkeypatch.setattr(model_utils, "ssrf_safe_httpx_get", io)
    monkeypatch.setattr("lfx.base.models.unified_models.credentials.validate_connector_url_for_ssrf", io)
    monkeypatch.setattr("lfx.base.models.unified_models.model_catalog.get_unified_models_detailed", lambda **_kw: [])
    monkeypatch.setitem(sys.modules, "langchain_azure_ai.chat_models", SimpleNamespace(AzureAIOpenAIApiChatModel=io))
    model = [{"name": "fixture-model", "provider": provider, "metadata": {}}]
    build = {
        "chat": partial(instantiation.get_llm, model, user_id=None),
        "embeddings": partial(instantiation.get_embeddings, model, user_id=None),
        "validation": partial(
            unified_models.validate_model_provider_key, provider, settings, model_name="fixture-model"
        ),
    }
    with pytest.raises(ValueError, match=r"server-provisioned|Could not validate Azure AI Foundry credentials"):
        build[kind]()
    io.assert_not_called()


def test_operator_and_user_configurations_remain_available(monkeypatch):
    project = f"{ENDPOINT}/api/projects/fixture"
    monkeypatch.setenv("AZURE_AI_FOUNDRY_ENDPOINT", project)
    model_utils.ensure_foundry_credential_endpoint_allowed(OPERATOR_KEY, f"{ENDPOINT}/openai/v1")
    model_utils.ensure_foundry_credential_endpoint_allowed(USER_KEY, "https://other.example.invalid")
    model_utils.ensure_watsonx_credential_endpoint_allowed(OPERATOR_KEY, "https://eu-de.ml.cloud.ibm.com/")
    model_utils.ensure_watsonx_credential_endpoint_allowed(USER_KEY, ENDPOINT)
    monkeypatch.setenv("WATSONX_TOKEN", "fixture-token")
    with pytest.raises(ValueError, match="server-provisioned"):
        model_utils.ensure_watsonx_credential_endpoint_allowed(USER_KEY, ENDPOINT)


@pytest.mark.parametrize("variable", ["AZURE_AI_FOUNDRY_API_KEY", "LANGFLOW_AZURE_AI_FOUNDRY_API_KEY"])
def test_foundry_checks_the_resolved_key_regardless_of_variable_name(monkeypatch, variable):
    key = "fixture-resolved-key"  # pragma: allowlist secret
    monkeypatch.setenv(variable, key)
    with pytest.raises(ValueError, match="server-provisioned"):
        model_utils.ensure_foundry_credential_endpoint_allowed(key, ENDPOINT)


@pytest.mark.parametrize(
    ("endpoint_name", "key_name", "check_endpoint"),
    [
        (
            "AZURE_AI_FOUNDRY_ENDPOINT",
            "AZURE_AI_FOUNDRY_API_KEY",
            model_utils.ensure_foundry_credential_endpoint_allowed,
        ),
        ("WATSONX_URL", "WATSONX_APIKEY", model_utils.ensure_watsonx_credential_endpoint_allowed),
    ],
)
@pytest.mark.parametrize("bare_endpoint", [None, "  ", "https://primary.example.invalid"])
def test_operator_destination_matches_env_resolution(
    monkeypatch, endpoint_name, key_name, check_endpoint, bare_endpoint
):
    key = "fixture-prefixed-key"  # pragma: allowlist secret
    monkeypatch.delenv(key_name, raising=False)
    monkeypatch.setenv(f"LANGFLOW_{key_name}", key)
    monkeypatch.setenv(f"LANGFLOW_{endpoint_name}", ENDPOINT)
    if bare_endpoint is not None:
        monkeypatch.setenv(endpoint_name, bare_endpoint)

    expected = bare_endpoint if bare_endpoint and bare_endpoint.strip() else ENDPOINT
    check_endpoint(key, expected)
    unapproved = ENDPOINT if expected != ENDPOINT else "https://other.example.invalid"
    with pytest.raises(ValueError, match="server-provisioned"):
        check_endpoint(key, unapproved)


@pytest.mark.parametrize("alias", ["project_endpoint", "base_url", "openai_api_base"])
def test_foundry_requires_one_effective_chat_endpoint(monkeypatch, alias):
    monkeypatch.setattr(unified_models, "get_api_key_for_provider", lambda *_args: USER_KEY)
    monkeypatch.setattr(
        unified_models, "get_all_variables_for_provider", lambda *_args: {"AZURE_AI_FOUNDRY_ENDPOINT": ENDPOINT}
    )
    factory = Mock()
    monkeypatch.setattr(unified_models, "get_model_class", lambda _name: factory)
    model = [{"name": "fixture-model", "provider": "Azure AI Foundry", "metadata": {}}]
    with pytest.raises(ValueError, match="Azure AI Foundry"):
        instantiation.get_llm(model, user_id=None, overrides={alias: "https://other.example.invalid"})
    factory.assert_not_called()


def test_foundry_discovery_skips_unapproved_resource(monkeypatch):
    settings = {
        "AZURE_AI_FOUNDRY_ENDPOINT": "https://resource.services.ai.azure.com",
        "AZURE_AI_FOUNDRY_API_KEY": OPERATOR_KEY,
    }
    monkeypatch.setattr(model_utils, "get_provider_variable_value", lambda _user, name: settings.get(name))
    fetch = Mock()
    monkeypatch.setattr(model_utils, "_fetch_azure_ai_foundry_deployment_entries", fetch)

    assert model_utils.fetch_live_azure_ai_foundry_models(None) == []
    fetch.assert_not_called()


@pytest.mark.parametrize("auxiliary", ["Azure AI Foundry", "IBM WatsonX"])
def test_rejected_auxiliary_embeddings_preserve_selected_model(monkeypatch, auxiliary):
    settings = {"AZURE_AI_FOUNDRY_ENDPOINT": ENDPOINT, "WATSONX_URL": ENDPOINT, "WATSONX_PROJECT_ID": "fixture-project"}
    primary = Mock()
    secondary = Mock()
    monkeypatch.setattr(
        unified_models, "get_embedding_class", lambda name: primary if name == "OllamaEmbeddings" else secondary
    )
    monkeypatch.setattr(
        unified_models,
        "get_api_key_for_provider",
        lambda _user, provider, _key: OPERATOR_KEY if provider == auxiliary else None,
    )
    monkeypatch.setattr(unified_models, "get_all_variables_for_provider", lambda *_args: settings)
    monkeypatch.setattr(instantiation, "_get_configured_embedding_providers", lambda *_args: [auxiliary])
    monkeypatch.setattr(instantiation, "_get_provider_embedding_model_names", lambda *_args: ["auxiliary-model"])
    model = [{"name": "selected-model", "provider": "Ollama", "metadata": {}}]

    result = instantiation.get_embeddings(model, user_id=None)

    assert result.available_models == {"selected-model": primary.return_value}
    secondary.assert_not_called()
