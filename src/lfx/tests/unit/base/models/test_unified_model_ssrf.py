"""SSRF regression coverage for unified model and embedding instantiation."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from lfx.base.models import unified_models as unified_models_module
from lfx.base.models.unified_models import instantiation


def _capture_factory():
    captured: dict = {}

    class FakeModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    return FakeModel, captured


def _model_selection(provider: str, model_class: str, **metadata) -> list[dict]:
    return [
        {
            "name": "test-model",
            "provider": provider,
            "metadata": {
                "model_class": model_class,
                "model_name_param": "model",
                "api_key_param": "api_key",  # pragma: allowlist secret
                **metadata,
            },
        }
    ]


def _embedding_selection(provider: str, embedding_class: str, param_mapping: dict[str, str]) -> list[dict]:
    return [
        {
            "name": "test-embedding",
            "provider": provider,
            "metadata": {
                "embedding_class": embedding_class,
                "param_mapping": param_mapping,
            },
        }
    ]


def _blocked_connector_policy() -> dict[str, str]:
    return {
        "LANGFLOW_SSRF_PROTECTION_ENABLED": "true",
        "LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED": "true",
        "LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK": "false",
    }


def test_get_llm_blocks_disallowed_ollama_loopback_before_model_construction():
    fake_cls, captured = _capture_factory()

    with (
        patch.dict(os.environ, _blocked_connector_policy()),
        patch.object(unified_models_module, "get_api_key_for_provider", return_value=None),
        patch.object(unified_models_module, "get_model_class", return_value=fake_cls),
        patch.object(unified_models_module, "get_all_variables_for_provider", return_value={}),
        pytest.raises(ValueError, match=r"SSRF Protection:.*127\.0\.0\.1.*blocked"),
    ):
        instantiation.get_llm(
            _model_selection("Ollama", "ChatOllama", base_url_param="base_url"),
            user_id="user-1",
            ollama_base_url="http://127.0.0.1:17864",
        )

    assert captured == {}


def test_get_embeddings_blocks_disallowed_ollama_loopback_before_model_construction():
    fake_cls, captured = _capture_factory()

    with (
        patch.dict(os.environ, _blocked_connector_policy()),
        patch.object(unified_models_module, "get_api_key_for_provider", return_value=None),
        patch.object(unified_models_module, "get_embedding_class", return_value=fake_cls),
        patch.object(unified_models_module, "get_all_variables_for_provider", return_value={}),
        patch.object(instantiation, "_build_available_embedding_models", return_value={}),
        pytest.raises(ValueError, match=r"SSRF Protection:.*127\.0\.0\.1.*blocked"),
    ):
        instantiation.get_embeddings(
            _embedding_selection(
                "Ollama",
                "OllamaEmbeddings",
                {"model": "model", "base_url": "base_url"},
            ),
            user_id="user-1",
            ollama_base_url="http://127.0.0.1:17864",
        )

    assert captured == {}


@pytest.mark.parametrize(
    "policy",
    [
        {
            "LANGFLOW_SSRF_PROTECTION_ENABLED": "true",
            "LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED": "true",
            "LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK": "true",
        },
        {
            "LANGFLOW_SSRF_PROTECTION_ENABLED": "true",
            "LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED": "false",
            "LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK": "false",
        },
    ],
)
def test_get_llm_preserves_explicit_ollama_ssrf_opt_outs(policy):
    fake_cls, captured = _capture_factory()

    with (
        patch.dict(os.environ, policy),
        patch.object(unified_models_module, "get_api_key_for_provider", return_value=None),
        patch.object(unified_models_module, "get_model_class", return_value=fake_cls),
        patch.object(unified_models_module, "get_all_variables_for_provider", return_value={}),
    ):
        instantiation.get_llm(
            _model_selection("Ollama", "ChatOllama", base_url_param="base_url"),
            user_id="user-1",
            ollama_base_url="http://127.0.0.1:11434",
        )

    assert captured["base_url"] == "http://127.0.0.1:11434"
    assert captured["sync_client_kwargs"] == {"follow_redirects": False}
    assert captured["async_client_kwargs"] == {"follow_redirects": False}


def test_get_llm_protects_final_openai_base_url_after_overrides():
    fake_cls, captured = _capture_factory()

    with (
        patch.dict(os.environ, _blocked_connector_policy()),
        patch.object(unified_models_module, "get_api_key_for_provider", return_value="test-key"),
        patch.object(unified_models_module, "get_model_class", return_value=fake_cls),
        patch.object(unified_models_module, "get_all_variables_for_provider", return_value={}),
        pytest.raises(ValueError, match=r"SSRF Protection:.*169\.254\.169\.254.*blocked"),
    ):
        instantiation.get_llm(
            _model_selection("OpenAI", "ChatOpenAI"),
            user_id="user-1",
            overrides={"base_url": "http://169.254.169.254/latest/meta-data/"},
        )

    assert captured == {}


def test_get_llm_injects_protected_openai_clients_for_custom_base_url():
    fake_cls, captured = _capture_factory()
    protected_clients = {"http_client": object(), "http_async_client": object()}

    with (
        patch.object(unified_models_module, "get_api_key_for_provider", return_value="test-key"),
        patch.object(unified_models_module, "get_model_class", return_value=fake_cls),
        patch.object(
            unified_models_module,
            "get_all_variables_for_provider",
            return_value={"OPENAI_BASE_URL": "https://models.example/v1"},
        ),
        patch.object(
            instantiation,
            "ssrf_protected_openai_clients_for_url",
            return_value=protected_clients,
            create=True,
        ) as protect_clients,
    ):
        instantiation.get_llm(_model_selection("OpenAI", "ChatOpenAI"), user_id="user-1")

    protect_clients.assert_called_once_with("https://models.example/v1")
    assert captured["http_client"] is protected_clients["http_client"]
    assert captured["http_async_client"] is protected_clients["http_async_client"]


def test_get_embeddings_injects_protected_openai_clients_for_custom_base_url():
    fake_cls, captured = _capture_factory()
    protected_clients = {"http_client": object(), "http_async_client": object()}

    with (
        patch.object(unified_models_module, "get_api_key_for_provider", return_value="test-key"),
        patch.object(unified_models_module, "get_embedding_class", return_value=fake_cls),
        patch.object(unified_models_module, "get_all_variables_for_provider", return_value={}),
        patch.object(instantiation, "_build_available_embedding_models", return_value={}),
        patch.object(
            instantiation,
            "ssrf_protected_openai_clients_for_url",
            return_value=protected_clients,
            create=True,
        ) as protect_clients,
    ):
        instantiation.get_embeddings(
            _embedding_selection(
                "OpenAI",
                "OpenAIEmbeddings",
                {"model": "model", "api_key": "api_key", "api_base": "base_url"},  # pragma: allowlist secret
            ),
            user_id="user-1",
            api_base="https://embeddings.example/v1",
        )

    protect_clients.assert_called_once_with("https://embeddings.example/v1")
    assert captured["http_client"] is protected_clients["http_client"]
    assert captured["http_async_client"] is protected_clients["http_async_client"]


def test_get_llm_validates_watsonx_url_before_model_construction():
    fake_cls, captured = _capture_factory()

    with (
        patch.object(unified_models_module, "get_api_key_for_provider", return_value="test-key"),
        patch.object(unified_models_module, "get_model_class", return_value=fake_cls),
        patch.object(unified_models_module, "get_all_variables_for_provider", return_value={}),
        patch.object(
            instantiation,
            "validate_url_for_ssrf_or_raise",
            create=True,
        ) as validate_url,
    ):
        instantiation.get_llm(
            _model_selection("IBM WatsonX", "ChatWatsonx"),
            user_id="user-1",
            watsonx_url="https://us-south.ml.cloud.ibm.com",
            watsonx_project_id="project-1",
        )

    validate_url.assert_called_once_with("https://us-south.ml.cloud.ibm.com")
    assert captured["url"] == "https://us-south.ml.cloud.ibm.com"
