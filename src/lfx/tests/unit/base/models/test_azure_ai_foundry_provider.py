"""Unit tests for the Azure AI Foundry unified model provider."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import httpx
import pytest


@pytest.fixture(autouse=True)
def _clear_foundry_deployments_cache():
    """Live-discovery memoization must not leak between tests (shared endpoint/key)."""
    from lfx.base.models import model_utils

    model_utils._azure_ai_foundry_deployments_cache.clear()
    yield
    model_utils._azure_ai_foundry_deployments_cache.clear()


def test_azure_ai_foundry_in_provider_registry():
    from lfx.base.models.model_metadata import CONDITIONAL_LIVE_MODEL_PROVIDERS, MODEL_PROVIDER_METADATA

    assert "Azure AI Foundry" in MODEL_PROVIDER_METADATA
    assert "Azure AI Foundry" in CONDITIONAL_LIVE_MODEL_PROVIDERS


def test_azure_ai_foundry_metadata_shape():
    from lfx.base.models.model_metadata import MODEL_PROVIDER_METADATA

    meta = MODEL_PROVIDER_METADATA["Azure AI Foundry"]
    assert meta["icon"] == "Azure"
    assert meta["mapping"]["model_class"] == "AzureAIOpenAIApiChatModel"
    assert meta["mapping"]["model_param"] == "model"

    var_keys = {v["variable_key"] for v in meta["variables"]}
    assert var_keys == {"AZURE_AI_FOUNDRY_API_KEY", "AZURE_AI_FOUNDRY_ENDPOINT", "AZURE_AI_FOUNDRY_API_VERSION"}

    by_key = {v["variable_key"]: v for v in meta["variables"]}
    assert by_key["AZURE_AI_FOUNDRY_API_KEY"]["required"] is True
    assert by_key["AZURE_AI_FOUNDRY_API_KEY"]["is_secret"] is True
    assert by_key["AZURE_AI_FOUNDRY_API_KEY"]["langchain_param"] == "credential"
    assert by_key["AZURE_AI_FOUNDRY_ENDPOINT"]["required"] is True
    assert by_key["AZURE_AI_FOUNDRY_API_VERSION"]["required"] is False
    assert by_key["AZURE_AI_FOUNDRY_API_VERSION"]["is_secret"] is False
    # Discovery-only knob: must never be wired into the chat/embedding constructors
    # or mapped onto a component field.
    assert "langchain_param" not in by_key["AZURE_AI_FOUNDRY_API_VERSION"]
    assert "component_metadata" not in by_key["AZURE_AI_FOUNDRY_API_VERSION"]


def test_azure_ai_foundry_appears_in_get_model_providers():
    from lfx.base.models.unified_models import get_model_providers

    assert "Azure AI Foundry" in get_model_providers()


def test_azure_ai_foundry_param_mapping_resolves_to_foundry_chat_model():
    from lfx.base.models.model_metadata import get_provider_param_mapping

    mapping = get_provider_param_mapping("Azure AI Foundry")
    assert mapping["model_class"] == "AzureAIOpenAIApiChatModel"
    assert mapping["model_param"] == "model"
    assert mapping["api_key_param"] == "credential"  # pragma: allowlist secret


def test_azure_ai_foundry_env_vars_registered_for_auto_import():
    from lfx.services.settings.constants import VARIABLES_TO_GET_FROM_ENVIRONMENT

    assert "AZURE_AI_FOUNDRY_API_KEY" in VARIABLES_TO_GET_FROM_ENVIRONMENT
    assert "AZURE_AI_FOUNDRY_ENDPOINT" in VARIABLES_TO_GET_FROM_ENVIRONMENT
    assert "AZURE_AI_FOUNDRY_API_VERSION" in VARIABLES_TO_GET_FROM_ENVIRONMENT


def test_azure_ai_foundry_resolves_to_langchain_azure_ai():
    from lfx.utils.flow_requirements import generate_requirements_from_flow

    flow = {
        "data": {
            "nodes": [
                {
                    "data": {
                        "type": "LanguageModel",
                        "node": {
                            "template": {
                                "model": {
                                    "value": [{"provider": "Azure AI Foundry", "name": "gpt-4o"}],
                                },
                                "_type": "Component",
                            },
                            "base_classes": ["LanguageModel"],
                        },
                    },
                }
            ],
            "edges": [],
        }
    }
    result = generate_requirements_from_flow(flow, pin_versions=False)
    assert "langchain-azure-ai" in result


def test_fetch_live_azure_ai_foundry_models_does_not_use_catalog_as_deployments():
    """Foundry /models is a catalog, not deployments — never treat it as live ids."""
    from lfx.base.models import model_utils

    with (
        patch.object(model_utils, "get_provider_variable_value", return_value="unused"),
        patch.object(model_utils.requests, "get") as mock_get,
    ):
        models = model_utils.fetch_live_azure_ai_foundry_models("user-1")

    mock_get.assert_not_called()
    assert models == []


_FOUNDRY_ENDPOINT = "https://example.services.ai.azure.com/openai/v1"
_FOUNDRY_DEPLOYMENTS_URL = "https://example.services.ai.azure.com/openai/deployments?api-version=2023-03-15-preview"


def _foundry_variable_lookup(_user_id, variable_key):
    return {
        "AZURE_AI_FOUNDRY_ENDPOINT": _FOUNDRY_ENDPOINT,
        "AZURE_AI_FOUNDRY_API_KEY": "test-key",  # pragma: allowlist secret
    }.get(variable_key)


def _deployments_response(deployments: list[dict] | object) -> MagicMock:
    response = MagicMock(status_code=200)
    response.json.return_value = {"data": deployments}
    return response


def test_fetch_live_azure_ai_foundry_models_lists_succeeded_deployments():
    """Live discovery lists the resource's actual deployments, not the /models catalog."""
    from lfx.base.models import model_utils

    response = _deployments_response(
        [
            {"id": "gpt-5-nano", "model": "gpt-5-nano", "status": "succeeded"},
            {"id": "text-embedding-3-small", "model": "text-embedding-3-small", "status": "succeeded"},
        ]
    )

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=_foundry_variable_lookup),
        patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response) as mock_get,
    ):
        models = model_utils.fetch_live_azure_ai_foundry_models("user-1", model_type="llm")

    mock_get.assert_called_once_with(
        _FOUNDRY_DEPLOYMENTS_URL,
        headers={"api-key": "test-key"},
        timeout=model_utils.AZURE_AI_FOUNDRY_FETCH_TIMEOUT,
    )
    assert [m["name"] for m in models] == ["gpt-5-nano"]
    entry = models[0]
    assert entry["provider"] == "Azure AI Foundry"
    assert entry["icon"] == "Azure"
    assert entry["model_type"] == "llm"
    assert entry["tool_calling"] is True
    assert entry["reasoning"] is True  # gpt-5 family
    assert entry["default"] is False  # Foundry stays explicit-enable-only


def test_fetch_live_azure_ai_foundry_models_classifies_embeddings():
    from lfx.base.models import model_utils

    response = _deployments_response(
        [
            {"id": "gpt-4o", "model": "gpt-4o", "status": "succeeded"},
            {"id": "text-embedding-3-small", "model": "text-embedding-3-small", "status": "succeeded"},
        ]
    )

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=_foundry_variable_lookup),
        patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response),
    ):
        models = model_utils.fetch_live_azure_ai_foundry_models("user-1", model_type="embeddings")

    assert [m["name"] for m in models] == ["text-embedding-3-small"]
    assert models[0]["model_type"] == "embeddings"
    assert models[0]["tool_calling"] is False


def test_fetch_live_azure_ai_foundry_models_uses_deployment_id_not_underlying_model():
    """The picker must offer deployment names (what inference accepts), not model ids."""
    from lfx.base.models import model_utils

    response = _deployments_response(
        [
            {"id": "my-chat-deployment", "model": "gpt-4o", "status": "succeeded"},
            {"id": "my-embed-deployment", "model": "text-embedding-ada-002", "status": "succeeded"},
        ]
    )

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=_foundry_variable_lookup),
        patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response) as mock_get,
    ):
        llms = model_utils.fetch_live_azure_ai_foundry_models("user-1", model_type="llm")
        embeddings = model_utils.fetch_live_azure_ai_foundry_models("user-1", model_type="embeddings")

    assert [m["name"] for m in llms] == ["my-chat-deployment"]
    assert llms[0]["reasoning"] is False  # gpt-4o is not a reasoning family
    assert [m["name"] for m in embeddings] == ["my-embed-deployment"]
    # The llm + embeddings picker pair shares one memoized upstream round-trip.
    assert mock_get.call_count == 1


def test_fetch_live_azure_ai_foundry_models_flags_o_series_reasoning():
    from lfx.base.models import model_utils

    response = _deployments_response([{"id": "o3-mini", "model": "o3-mini", "status": "succeeded"}])

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=_foundry_variable_lookup),
        patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response),
    ):
        models = model_utils.fetch_live_azure_ai_foundry_models("user-1", model_type="llm")

    assert models[0]["reasoning"] is True


def test_fetch_live_azure_ai_foundry_models_excludes_non_succeeded_deployments():
    from lfx.base.models import model_utils

    response = _deployments_response(
        [
            {"id": "gpt-4o", "model": "gpt-4o", "status": "succeeded"},
            {"id": "still-creating", "model": "gpt-4o", "status": "creating"},
            {"id": "broken", "model": "gpt-4o", "status": "failed"},
            {"id": "no-status", "model": "gpt-4o"},
        ]
    )

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=_foundry_variable_lookup),
        patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response),
    ):
        models = model_utils.fetch_live_azure_ai_foundry_models("user-1", model_type="llm")

    assert [m["name"] for m in models] == ["gpt-4o"]


def test_fetch_live_azure_ai_foundry_models_skips_malformed_deployment_entries():
    from lfx.base.models import model_utils

    response = _deployments_response(
        [
            "not-a-dict",
            {"model": "gpt-4o", "status": "succeeded"},  # missing id
            {"id": "", "model": "gpt-4o", "status": "succeeded"},  # empty id
            {"id": "gpt-4o", "model": "gpt-4o", "status": "succeeded"},
        ]
    )

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=_foundry_variable_lookup),
        patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response),
    ):
        models = model_utils.fetch_live_azure_ai_foundry_models("user-1", model_type="llm")

    assert [m["name"] for m in models] == ["gpt-4o"]


def test_fetch_live_azure_ai_foundry_models_excludes_non_chat_deployments():
    """Image/audio/legacy-completions deployments can't be driven by the unified chat class."""
    from lfx.base.models import model_utils

    response = _deployments_response(
        [
            {"id": "dall-e-3", "model": "dall-e-3", "status": "succeeded"},
            {"id": "whisper", "model": "whisper", "status": "succeeded"},
            {"id": "tts-1", "model": "tts-1", "status": "succeeded"},
            {"id": "curie", "model": "curie", "status": "succeeded"},
            {"id": "text-davinci-003", "model": "text-davinci-003", "status": "succeeded"},
            {"id": "gpt-35-turbo-instruct", "model": "gpt-35-turbo-instruct", "status": "succeeded"},
            {"id": "gpt-4o", "model": "gpt-4o", "status": "succeeded"},
            # "ada" marks legacy completions, but the embeddings check wins first.
            {"id": "text-embedding-ada-002", "model": "text-embedding-ada-002", "status": "succeeded"},
            # Foundry-hosted open chat models named *-Instruct must NOT be excluded.
            {"id": "Meta-Llama-3.1-8B-Instruct", "model": "Meta-Llama-3.1-8B-Instruct", "status": "succeeded"},
        ]
    )

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=_foundry_variable_lookup),
        patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response),
    ):
        llms = model_utils.fetch_live_azure_ai_foundry_models("user-1", model_type="llm")
        embeddings = model_utils.fetch_live_azure_ai_foundry_models("user-1", model_type="embeddings")

    assert [m["name"] for m in llms] == ["gpt-4o", "Meta-Llama-3.1-8B-Instruct"]
    assert [m["name"] for m in embeddings] == ["text-embedding-ada-002"]


def test_fetch_live_azure_ai_foundry_models_honors_configured_api_version():
    """AZURE_AI_FOUNDRY_API_VERSION overrides the default deployments api-version."""
    from lfx.base.models import model_utils

    def lookup(_user_id, variable_key):
        return {
            "AZURE_AI_FOUNDRY_ENDPOINT": _FOUNDRY_ENDPOINT,
            "AZURE_AI_FOUNDRY_API_KEY": "test-key",  # pragma: allowlist secret
            "AZURE_AI_FOUNDRY_API_VERSION": "2024-10-21",
        }.get(variable_key)

    response = _deployments_response([{"id": "gpt-4o", "model": "gpt-4o", "status": "succeeded"}])

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=lookup),
        patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response) as mock_get,
    ):
        models = model_utils.fetch_live_azure_ai_foundry_models("user-1", model_type="llm")

    assert mock_get.call_args.args[0] == (
        "https://example.services.ai.azure.com/openai/deployments?api-version=2024-10-21"
    )
    assert [m["name"] for m in models] == ["gpt-4o"]


@pytest.mark.parametrize(
    "bad_version",
    ["2023&injected=1", "2023-03-15-preview?x=1", "a b", "-leading-dash", ""],
    ids=["ampersand", "question-mark", "space", "leading-dash", "empty"],
)
def test_fetch_live_azure_ai_foundry_models_rejects_unsafe_api_version(bad_version):
    """Unsafe api-version values fall back to the default instead of reaching the URL."""
    from lfx.base.models import model_utils

    def lookup(_user_id, variable_key):
        return {
            "AZURE_AI_FOUNDRY_ENDPOINT": _FOUNDRY_ENDPOINT,
            "AZURE_AI_FOUNDRY_API_KEY": "test-key",  # pragma: allowlist secret
            "AZURE_AI_FOUNDRY_API_VERSION": bad_version,
        }.get(variable_key)

    response = _deployments_response([{"id": "gpt-4o", "model": "gpt-4o", "status": "succeeded"}])

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=lookup),
        patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response) as mock_get,
    ):
        models = model_utils.fetch_live_azure_ai_foundry_models("user-1", model_type="llm")

    assert mock_get.call_args.args[0] == _FOUNDRY_DEPLOYMENTS_URL
    assert [m["name"] for m in models] == ["gpt-4o"]


def test_azure_ai_foundry_invalid_api_version_is_not_logged():
    """Rejected configuration may contain secrets and must never be echoed to logs."""
    from lfx.base.models import model_utils

    rejected_value = "2023-03-15-preview&sig=foundry-secret-token"  # pragma: allowlist secret
    with (
        patch.object(model_utils, "get_provider_variable_value", return_value=rejected_value),
        patch.object(model_utils.logger, "warning") as mock_warning,
    ):
        api_version = model_utils._azure_ai_foundry_api_version("user-1")

    assert api_version == model_utils.AZURE_AI_FOUNDRY_DEPLOYMENTS_API_VERSION
    mock_warning.assert_called_once()
    assert rejected_value not in str(mock_warning.call_args)


def test_fetch_live_azure_ai_foundry_models_flags_no_tool_chat_models():
    """Chat families documented without tool calling stay listed but tool_calling=False."""
    from lfx.base.models import model_utils

    response = _deployments_response(
        [
            {"id": "DeepSeek-R1", "model": "DeepSeek-R1", "status": "succeeded"},
            {"id": "Phi-4-mini-instruct", "model": "Phi-4-mini-instruct", "status": "succeeded"},
            {"id": "Codestral-2501", "model": "Codestral-2501", "status": "succeeded"},
            {"id": "gpt-4o", "model": "gpt-4o", "status": "succeeded"},
        ]
    )

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=_foundry_variable_lookup),
        patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response),
    ):
        llms = model_utils.fetch_live_azure_ai_foundry_models("user-1", model_type="llm")

    by_name = {m["name"]: m for m in llms}
    assert set(by_name) == {"DeepSeek-R1", "Phi-4-mini-instruct", "Codestral-2501", "gpt-4o"}
    assert by_name["DeepSeek-R1"]["tool_calling"] is False
    assert by_name["Phi-4-mini-instruct"]["tool_calling"] is False
    assert by_name["Codestral-2501"]["tool_calling"] is False
    assert by_name["gpt-4o"]["tool_calling"] is True
    assert by_name["DeepSeek-R1"]["reasoning"] is True


def test_foundry_deployments_cache_never_stores_plaintext_api_key():
    from lfx.base.models import model_utils

    response = _deployments_response([{"id": "gpt-4o", "model": "gpt-4o", "status": "succeeded"}])

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=_foundry_variable_lookup),
        patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response),
    ):
        model_utils.fetch_live_azure_ai_foundry_models("user-1", model_type="llm")

    keys = list(model_utils._azure_ai_foundry_deployments_cache.keys())
    assert keys, "expected the successful fetch to be cached"
    assert all("test-key" not in part for key in keys for part in key)


def test_foundry_deployments_cache_is_bounded():
    from lfx.base.models import model_utils

    response = _deployments_response([])
    maxsize = model_utils._AZURE_AI_FOUNDRY_DEPLOYMENTS_CACHE_MAXSIZE

    with patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response):
        for i in range(maxsize + 10):
            model_utils._fetch_azure_ai_foundry_deployment_entries(
                f"https://r{i}.services.ai.azure.com/openai/deployments?api-version=2023-03-15-preview",
                "test-key",  # pragma: allowlist secret
            )

    assert len(model_utils._azure_ai_foundry_deployments_cache) <= maxsize


def test_language_model_options_filters_live_foundry_no_tool_models():
    """Live rows must respect tool_calling filters end-to-end (Agent picker path).

    Static-catalog filtering happens before ``replace_with_live_models``, so the
    catalog re-filters after replacement — and the free-text enable injector must
    not resurrect a deployment the filter just dropped.
    """
    from lfx.base.models import model_utils
    from lfx.base.models.unified_models import model_catalog
    from lfx.base.models.unified_models.credentials import model_status_key

    response = _deployments_response(
        [
            {"id": "gpt-4o", "model": "gpt-4o", "status": "succeeded"},
            {"id": "Phi-4-mini-instruct", "model": "Phi-4-mini-instruct", "status": "succeeded"},
        ]
    )
    enables = {
        model_status_key("Azure AI Foundry", "gpt-4o", "llm"),
        model_status_key("Azure AI Foundry", "Phi-4-mini-instruct", "llm"),
    }

    async def fake_model_status(_user_id):
        return set(), enables

    async def fake_enabled_providers(_user_id, *, provider_policy=None):
        _ = provider_policy
        return {"Azure AI Foundry"}

    with (
        patch.object(model_catalog, "_get_model_status", fake_model_status),
        patch.object(model_catalog, "_fetch_enabled_providers_for_user", fake_enabled_providers),
        patch.object(model_utils, "get_provider_variable_value", side_effect=_foundry_variable_lookup),
        patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response),
    ):
        all_options = model_catalog.get_language_model_options(user_id="user-1")
        tool_options = model_catalog.get_language_model_options(user_id="user-1", tool_calling=True)

    def foundry_names(options):
        return [o["name"] for o in options if o["provider"] == "Azure AI Foundry"]

    assert foundry_names(all_options) == ["gpt-4o", "Phi-4-mini-instruct"]
    assert foundry_names(tool_options) == ["gpt-4o"]


def test_fetch_live_azure_ai_foundry_models_memoizes_failures():
    """An outage costs one upstream timeout, not one per picker read."""
    from lfx.base.models import model_utils

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=_foundry_variable_lookup),
        patch.object(
            model_utils, "ssrf_safe_httpx_get", side_effect=httpx.ConnectTimeout("request timed out")
        ) as mock_get,
    ):
        llms = model_utils.fetch_live_azure_ai_foundry_models("user-1", model_type="llm")
        embeddings = model_utils.fetch_live_azure_ai_foundry_models("user-1", model_type="embeddings")

    assert llms == []
    assert embeddings == []
    assert mock_get.call_count == 1


def test_fetch_live_azure_ai_foundry_models_derives_resource_base_from_project_endpoint():
    """Any path on the resource host (project endpoint, trailing slash) still finds /openai/deployments."""
    from lfx.base.models import model_utils

    def lookup(_user_id, variable_key):
        return {
            "AZURE_AI_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/api/projects/my-project",
            "AZURE_AI_FOUNDRY_API_KEY": "test-key",  # pragma: allowlist secret
        }.get(variable_key)

    response = _deployments_response([{"id": "gpt-4o", "model": "gpt-4o", "status": "succeeded"}])

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=lookup),
        patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response) as mock_get,
    ):
        models = model_utils.fetch_live_azure_ai_foundry_models("user-1", model_type="llm")

    assert mock_get.call_args.args[0] == _FOUNDRY_DEPLOYMENTS_URL
    assert [m["name"] for m in models] == ["gpt-4o"]


@pytest.mark.parametrize(
    "missing_key",
    ["AZURE_AI_FOUNDRY_ENDPOINT", "AZURE_AI_FOUNDRY_API_KEY"],
    ids=["missing-endpoint", "missing-api-key"],
)
def test_fetch_live_azure_ai_foundry_models_requires_endpoint_and_key(missing_key):
    from lfx.base.models import model_utils

    def lookup(_user_id, variable_key):
        if variable_key == missing_key:
            return None
        return _foundry_variable_lookup(_user_id, variable_key)

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=lookup),
        patch.object(model_utils, "ssrf_safe_httpx_get") as mock_get,
    ):
        models = model_utils.fetch_live_azure_ai_foundry_models("user-1", model_type="llm")

    mock_get.assert_not_called()
    assert models == []


@pytest.mark.parametrize(
    "endpoint",
    [
        "not-a-url",
        "https://collector.example.com/openai/v1",
        "http://example.services.ai.azure.com/openai/v1",
        "https://user:pass@example.services.ai.azure.com/openai/v1",  # pragma: allowlist secret
        "https://example.services.ai.azure.com:8443/openai/v1",
        "https://example.services.ai.azure.com:443/openai/v1",
        "https://evil.services.ai.azure.com.attacker.net/openai/v1",
        "https://services.ai.azure.com/openai/v1",
    ],
    ids=[
        "malformed",
        "non-azure-host",
        "plain-http",
        "userinfo",
        "non-default-port",
        "explicit-default-port",
        "suffix-spoof",
        "bare-suffix-no-resource",
    ],
)
def test_fetch_live_azure_ai_foundry_models_rejects_untrusted_endpoints(endpoint):
    """The api-key header must never be sent anywhere but an HTTPS Azure Foundry host."""
    from lfx.base.models import model_utils

    def lookup(_user_id, variable_key):
        return {
            "AZURE_AI_FOUNDRY_ENDPOINT": endpoint,
            "AZURE_AI_FOUNDRY_API_KEY": "test-key",  # pragma: allowlist secret
        }.get(variable_key)

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=lookup),
        patch.object(model_utils, "ssrf_safe_httpx_get") as mock_get,
        patch.object(model_utils.logger, "debug") as mock_debug,
    ):
        models = model_utils.fetch_live_azure_ai_foundry_models("user-1", model_type="llm")

    mock_get.assert_not_called()
    assert models == []
    # Rejection logs must never echo the raw endpoint: it may embed userinfo or tokens.
    assert all(endpoint not in str(call) for call in mock_debug.call_args_list)


@pytest.mark.parametrize(
    "host",
    [
        "example.openai.azure.com",
        "example.cognitiveservices.azure.com",
        "example.services.ai.azure.us",
        "example.openai.azure.cn",
    ],
    ids=["azure-openai", "cognitive-services", "us-gov", "china"],
)
def test_fetch_live_azure_ai_foundry_models_accepts_sibling_azure_clouds(host):
    from lfx.base.models import model_utils

    def lookup(_user_id, variable_key):
        return {
            "AZURE_AI_FOUNDRY_ENDPOINT": f"https://{host}/openai/v1",
            "AZURE_AI_FOUNDRY_API_KEY": "test-key",  # pragma: allowlist secret
        }.get(variable_key)

    response = _deployments_response([{"id": "gpt-4o", "model": "gpt-4o", "status": "succeeded"}])

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=lookup),
        patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response) as mock_get,
    ):
        models = model_utils.fetch_live_azure_ai_foundry_models("user-1", model_type="llm")

    assert mock_get.call_args.args[0] == f"https://{host}/openai/deployments?api-version=2023-03-15-preview"
    assert [m["name"] for m in models] == ["gpt-4o"]


@pytest.mark.parametrize(
    "failure",
    ["connection", "timeout", "http", "malformed-data", "non-dict-payload", "invalid-json", "ssrf-blocked"],
    ids=str,
)
def test_fetch_live_azure_ai_foundry_models_degrades_to_empty_on_failure(failure):
    """Every failure mode returns [] so the static seed catalog stays the fallback."""
    from lfx.base.models import model_utils
    from lfx.utils.ssrf_protection import SSRFProtectionError

    response = MagicMock(status_code=200)
    response.json.return_value = {"data": []}
    get_side_effect = None
    if failure == "connection":
        get_side_effect = httpx.ConnectError("connection refused")
    elif failure == "timeout":
        get_side_effect = httpx.ConnectTimeout("request timed out")
    elif failure == "http":
        response.status_code = 401
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=response
        )
    elif failure == "malformed-data":
        response.json.return_value = {"data": "not-a-list"}
    elif failure == "non-dict-payload":
        response.json.return_value = ["not", "a", "dict"]
    elif failure == "invalid-json":
        response.json.side_effect = ValueError("No JSON object could be decoded")
    else:
        get_side_effect = SSRFProtectionError("blocked host")

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=_foundry_variable_lookup),
        patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response, side_effect=get_side_effect),
    ):
        models = model_utils.fetch_live_azure_ai_foundry_models("user-1", model_type="llm")

    assert models == []


def test_fetch_live_azure_ai_foundry_models_rejects_unknown_model_type():
    from lfx.base.models import model_utils

    with patch.object(model_utils, "ssrf_safe_httpx_get") as mock_get:
        models = model_utils.fetch_live_azure_ai_foundry_models("user-1", model_type="image")

    mock_get.assert_not_called()
    assert models == []


def test_foundry_live_deployments_replace_static_catalog():
    """When deployments are discovered, the picker shows them instead of the seed catalog."""
    from lfx.base.models import model_utils

    seed_models = [{"model_name": "gpt-4o", "metadata": {"default": True}}]
    provider_models = [{"provider": "Azure AI Foundry", "models": seed_models, "num_models": 1}]
    live = [
        model_utils.create_model_metadata(
            provider="Azure AI Foundry",
            name="gpt-5-nano",
            icon="Azure",
            tool_calling=True,
            reasoning=True,
        )
    ]

    with patch.object(model_utils, "fetch_live_azure_ai_foundry_models", return_value=live):
        result = model_utils.replace_with_live_models(
            provider_models,
            user_id="user-1",
            enabled_providers={"Azure AI Foundry"},
            model_type="llm",
        )

    assert [m["model_name"] for m in result[0]["models"]] == ["gpt-5-nano"]
    assert result[0]["num_models"] == 1


def test_request_azure_ai_foundry_model_entries_returns_catalog_data():
    """Credential validation still probes /models for connectivity."""
    from lfx.base.models import model_utils

    response = MagicMock(status_code=200)
    response.json.return_value = {"data": [{"id": "gpt-5-mini-2025-08-07"}]}

    with patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response) as mock_get:
        entries = model_utils.request_azure_ai_foundry_model_entries(
            "https://example.services.ai.azure.com/openai/v1/",
            "test-key",  # pragma: allowlist secret
        )

    mock_get.assert_called_once_with(
        "https://example.services.ai.azure.com/openai/v1/models",
        headers={"api-key": "test-key"},
        timeout=model_utils.AZURE_AI_FOUNDRY_FETCH_TIMEOUT,
    )
    assert entries == [{"id": "gpt-5-mini-2025-08-07"}]


@pytest.mark.parametrize(
    "project_endpoint",
    [
        "https://example.services.ai.azure.com/api/projects/my-project",
        "https://example.services.ai.azure.com/api/projects/my-project/",
        "https://example.services.ai.azure.com/API/Projects/My-Project",
        "https://example.services.ai.azure.com/api/projects",
    ],
    ids=["plain", "trailing-slash", "mixed-case", "no-project-segment"],
)
def test_normalize_azure_ai_foundry_endpoint_rewrites_project_endpoint(project_endpoint):
    """The Foundry portal's prominent *project* endpoint must map to the OpenAI-compatible form."""
    from lfx.base.models import model_utils

    normalized = model_utils.normalize_azure_ai_foundry_endpoint(project_endpoint)

    assert normalized == "https://example.services.ai.azure.com/openai/v1"


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://example.services.ai.azure.com/openai/v1",
        "https://example.services.ai.azure.com/openai/v1/",
        "https://example.services.ai.azure.com",
        "https://example.openai.azure.com/openai",
        "not-a-url/api/projects/my-project",
    ],
    ids=["openai-v1", "openai-v1-trailing-slash", "bare-resource", "azure-openai", "unparseable"],
)
def test_normalize_azure_ai_foundry_endpoint_keeps_other_endpoints(endpoint):
    from lfx.base.models import model_utils

    assert model_utils.normalize_azure_ai_foundry_endpoint(endpoint) == endpoint


def test_request_azure_ai_foundry_model_entries_normalizes_project_endpoint():
    """A pasted project endpoint must probe the OpenAI-compatible /models, not the 400ing project path."""
    from lfx.base.models import model_utils

    response = MagicMock(status_code=200)
    response.json.return_value = {"data": [{"id": "gpt-5-mini-2025-08-07"}]}

    with patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response) as mock_get:
        entries = model_utils.request_azure_ai_foundry_model_entries(
            "https://example.services.ai.azure.com/api/projects/my-project",
            "test-key",  # pragma: allowlist secret
        )

    mock_get.assert_called_once_with(
        "https://example.services.ai.azure.com/openai/v1/models",
        headers={"api-key": "test-key"},
        timeout=model_utils.AZURE_AI_FOUNDRY_FETCH_TIMEOUT,
    )
    assert entries == [{"id": "gpt-5-mini-2025-08-07"}]


@pytest.mark.parametrize(
    ("endpoint", "expected_url"),
    [
        (
            "https://example.services.ai.azure.com/openai/v1",
            "https://example.services.ai.azure.com/openai/v1/models",
        ),
        (
            # Project endpoints normalize to the OpenAI-compatible form first.
            "https://example.services.ai.azure.com/api/projects/proj-default",
            "https://example.services.ai.azure.com/openai/v1/models",
        ),
        (
            "https://example.services.ai.azure.com/models",
            "https://example.services.ai.azure.com/models?api-version=2025-04-01",
        ),
        (
            "https://example.services.ai.azure.com/models?api-version=2024-05-01-preview",
            "https://example.services.ai.azure.com/models?api-version=2024-05-01-preview",
        ),
        (
            "https://example.services.ai.azure.com/openai/v1/models?api-version=preview",
            "https://example.services.ai.azure.com/openai/v1/models?api-version=preview",
        ),
        (
            "https://example.services.ai.azure.com/openai/v1/models?api-version=2025-04-01",
            "https://example.services.ai.azure.com/openai/v1/models",
        ),
    ],
    ids=[
        "openai-compatible",
        "project-endpoint-normalized",
        "generic-models-deduped",
        "existing-api-version-preserved",
        "openai-v1-preview-preserved",
        "openai-v1-dated-version-removed",
    ],
)
def test_request_azure_ai_foundry_model_entries_builds_probe_url_for_any_endpoint_form(endpoint, expected_url):
    """Each Foundry endpoint family receives only an API version supported by that route."""
    from lfx.base.models import model_utils

    response = MagicMock(status_code=200)
    response.json.return_value = {"data": []}

    with patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response) as mock_get:
        model_utils.request_azure_ai_foundry_model_entries(endpoint, "test-key")  # pragma: allowlist secret

    assert mock_get.call_args.args[0] == expected_url


def test_request_azure_ai_foundry_model_entries_honors_api_version_argument():
    """AZURE_AI_FOUNDRY_API_VERSION flows through credential validation to generic inference probes."""
    from lfx.base.models import model_utils

    response = MagicMock(status_code=200)
    response.json.return_value = {"data": []}

    with patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response) as mock_get:
        model_utils.request_azure_ai_foundry_model_entries(
            "https://example.services.ai.azure.com/models",
            "test-key",  # pragma: allowlist secret
            "2024-10-21",
        )

    assert mock_get.call_args.args[0] == "https://example.services.ai.azure.com/models?api-version=2024-10-21"


def test_request_azure_ai_foundry_model_entries_ignores_dated_version_for_openai_v1():
    """The OpenAI v1 models route accepts only v1/preview, not dated Model Inference versions."""
    from lfx.base.models import model_utils

    response = MagicMock(status_code=200)
    response.json.return_value = {"data": []}

    with patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response) as mock_get:
        model_utils.request_azure_ai_foundry_model_entries(
            "https://example.services.ai.azure.com/openai/v1",
            "test-key",  # pragma: allowlist secret
            "2024-10-21",
        )

    assert mock_get.call_args.args[0] == "https://example.services.ai.azure.com/openai/v1/models"


@pytest.mark.parametrize(
    "endpoint",
    ["http://127.0.0.1:8080", "http://169.254.169.254/latest/meta-data"],
    ids=["loopback", "cloud-metadata"],
)
def test_request_azure_ai_foundry_model_entries_blocks_ssrf_destinations(endpoint):
    """Credential validation must reject internal targets before sending the API key."""
    from lfx.base.models import model_utils
    from lfx.utils.ssrf_protection import SSRFProtectionError

    policy = {
        "LANGFLOW_SSRF_PROTECTION_ENABLED": "true",
        "LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED": "true",
        "LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK": "false",
    }
    with (
        patch.dict(os.environ, policy),
        pytest.raises(SSRFProtectionError, match="blocked"),
    ):
        model_utils.request_azure_ai_foundry_model_entries(
            endpoint,
            "test-key",  # pragma: allowlist secret
        )


@pytest.mark.parametrize(
    "failure",
    ["bad-request", "service-unavailable", "malformed-payload", "invalid-json"],
    ids=str,
)
def test_request_azure_ai_foundry_model_entries_tolerates_non_auth_failures(failure):
    """No reliable catalog route exists across Foundry shapes: only 401/403 may block a save."""
    from lfx.base.models import model_utils

    response = MagicMock(status_code=200)
    response.json.return_value = {"data": []}
    if failure == "bad-request":
        response.status_code = 400
        response.ok = False
    elif failure == "service-unavailable":
        response.status_code = 503
        response.ok = False
    elif failure == "malformed-payload":
        response.json.return_value = {"data": "not-a-list"}
    else:
        response.json.side_effect = ValueError("No JSON object could be decoded")

    with patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response):
        entries = model_utils.request_azure_ai_foundry_model_entries(
            "https://example.services.ai.azure.com/api/projects/proj-default",
            "test-key",  # pragma: allowlist secret
        )

    assert entries == []


@pytest.mark.parametrize("status_code", [401, 403], ids=["unauthorized", "forbidden"])
def test_request_azure_ai_foundry_model_entries_raises_on_auth_failure(status_code):
    from lfx.base.models import model_utils

    response = MagicMock(status_code=status_code)
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        f"{status_code} auth error",
        request=httpx.Request("GET", "https://example.services.ai.azure.com/openai/v1/models"),
        response=httpx.Response(status_code),
    )

    with (
        patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response),
        pytest.raises(httpx.HTTPStatusError),
    ):
        model_utils.request_azure_ai_foundry_model_entries(
            "https://example.services.ai.azure.com/openai/v1",
            "test-key",  # pragma: allowlist secret
        )


def test_foundry_empty_live_discovery_keeps_static_catalog():
    from lfx.base.models import model_utils

    seed_models = [{"model_name": "gpt-4o", "metadata": {"default": True}}]
    provider_models = [{"provider": "Azure AI Foundry", "models": seed_models, "num_models": 1}]

    with patch.object(model_utils, "fetch_live_azure_ai_foundry_models", return_value=[]):
        result = model_utils.replace_with_live_models(
            provider_models,
            user_id="user-1",
            enabled_providers={"Azure AI Foundry"},
            model_type="llm",
        )

    assert result[0]["models"] == seed_models


def test_validate_model_provider_key_azure_ai_foundry_success():
    from types import SimpleNamespace

    from lfx.base.models import model_utils
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock(status_code=200)
    response.json.return_value = {"data": []}
    fake_chat_models = SimpleNamespace(AzureAIOpenAIApiChatModel=object)
    with (
        patch.dict(
            "sys.modules",
            {
                "langchain_azure_ai": SimpleNamespace(chat_models=fake_chat_models),
                "langchain_azure_ai.chat_models": fake_chat_models,
            },
        ),
        patch("lfx.base.models.unified_models.model_catalog.get_unified_models_detailed", return_value=[]),
        patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response) as mock_get,
    ):
        validate_model_provider_key(
            "Azure AI Foundry",
            {
                "AZURE_AI_FOUNDRY_API_KEY": "test-key",  # pragma: allowlist secret
                "AZURE_AI_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/openai/v1",
            },
        )

    mock_get.assert_called_once_with(
        "https://example.services.ai.azure.com/openai/v1/models",
        headers={"api-key": "test-key"},
        timeout=model_utils.AZURE_AI_FOUNDRY_FETCH_TIMEOUT,
    )


def test_validate_model_provider_key_azure_ai_foundry_accepts_project_endpoint():
    """Credential validation with a pasted project endpoint probes the OpenAI-compatible /models."""
    from types import SimpleNamespace

    from lfx.base.models import model_utils
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock(status_code=200)
    response.json.return_value = {"data": []}
    fake_chat_models = SimpleNamespace(AzureAIOpenAIApiChatModel=object)
    with (
        patch.dict(
            "sys.modules",
            {
                "langchain_azure_ai": SimpleNamespace(chat_models=fake_chat_models),
                "langchain_azure_ai.chat_models": fake_chat_models,
            },
        ),
        patch("lfx.base.models.unified_models.model_catalog.get_unified_models_detailed", return_value=[]),
        patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response) as mock_get,
    ):
        validate_model_provider_key(
            "Azure AI Foundry",
            {
                "AZURE_AI_FOUNDRY_API_KEY": "test-key",  # pragma: allowlist secret
                "AZURE_AI_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/api/projects/my-project",
            },
        )

    mock_get.assert_called_once_with(
        "https://example.services.ai.azure.com/openai/v1/models",
        headers={"api-key": "test-key"},
        timeout=model_utils.AZURE_AI_FOUNDRY_FETCH_TIMEOUT,
    )


@pytest.mark.parametrize("failure", ["connection", "timeout", "unauthorized", "forbidden"], ids=str)
def test_validate_model_provider_key_azure_ai_foundry_rejects_failed_model_listing(failure):
    from types import SimpleNamespace

    from lfx.base.models import model_utils
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock(status_code=200)
    response.json.return_value = {"data": []}
    side_effect = None
    if failure == "connection":
        side_effect = httpx.ConnectError("connection refused")
    elif failure == "timeout":
        side_effect = httpx.ConnectTimeout("request timed out")
    elif failure == "unauthorized":
        response.status_code = 401
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=httpx.Request("GET", "https://example.services.ai.azure.com/openai/v1/models"),
            response=httpx.Response(401),
        )
    else:
        response.status_code = 403
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403 Forbidden",
            request=httpx.Request("GET", "https://example.services.ai.azure.com/openai/v1/models"),
            response=httpx.Response(403),
        )

    fake_chat_models = SimpleNamespace(AzureAIOpenAIApiChatModel=object)
    with (
        patch.dict(
            "sys.modules",
            {
                "langchain_azure_ai": SimpleNamespace(chat_models=fake_chat_models),
                "langchain_azure_ai.chat_models": fake_chat_models,
            },
        ),
        patch("lfx.base.models.unified_models.model_catalog.get_unified_models_detailed", return_value=[]),
        patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response, side_effect=side_effect),
        pytest.raises(ValueError, match="Azure AI Foundry"),
    ):
        validate_model_provider_key(
            "Azure AI Foundry",
            {
                "AZURE_AI_FOUNDRY_API_KEY": "test-key",  # pragma: allowlist secret
                "AZURE_AI_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/openai/v1",
            },
        )


def test_validate_model_provider_key_azure_ai_foundry_does_not_expose_endpoint_secrets():
    """HTTP errors can carry the full endpoint, but logs and UI errors must not."""
    from types import SimpleNamespace

    from lfx.base.models import model_utils
    from lfx.base.models.unified_models import credentials as credentials_module
    from lfx.base.models.unified_models import validate_model_provider_key

    sensitive_value = "foundry-secret-token"  # pragma: allowlist secret
    endpoint = f"https://example.services.ai.azure.com/openai/v1?sig={sensitive_value}"
    side_effect = httpx.ConnectError(f"connection failed for {endpoint}")
    fake_chat_models = SimpleNamespace(AzureAIOpenAIApiChatModel=object)

    with (
        patch.dict(
            "sys.modules",
            {
                "langchain_azure_ai": SimpleNamespace(chat_models=fake_chat_models),
                "langchain_azure_ai.chat_models": fake_chat_models,
            },
        ),
        patch("lfx.base.models.unified_models.model_catalog.get_unified_models_detailed", return_value=[]),
        patch.object(model_utils, "ssrf_safe_httpx_get", side_effect=side_effect),
        patch.object(credentials_module.logger, "warning") as mock_warning,
        pytest.raises(ValueError, match="Could not validate Azure AI Foundry credentials") as exc_info,
    ):
        validate_model_provider_key(
            "Azure AI Foundry",
            {
                "AZURE_AI_FOUNDRY_API_KEY": "test-key",  # pragma: allowlist secret
                "AZURE_AI_FOUNDRY_ENDPOINT": endpoint,
            },
        )

    assert sensitive_value not in str(exc_info.value)
    assert sensitive_value not in str(mock_warning.call_args)
    assert exc_info.value.__cause__ is None


@pytest.mark.parametrize("failure", ["bad-request", "service-unavailable", "malformed-payload"], ids=str)
def test_validate_model_provider_key_azure_ai_foundry_tolerates_catalog_less_resources(failure):
    """Project-scoped resources can 400 the /models probe with valid credentials.

    Only 401/403 may block the credential save; every other listing failure means
    "no catalog available" and the save proceeds (deployment names are user-typed).
    """
    from types import SimpleNamespace

    from lfx.base.models import model_utils
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock(status_code=200)
    response.json.return_value = {"data": []}
    if failure == "bad-request":
        response.status_code = 400
        response.ok = False
    elif failure == "service-unavailable":
        response.status_code = 503
        response.ok = False
    else:
        response.json.return_value = {"data": "not-a-list"}

    fake_chat_models = SimpleNamespace(AzureAIOpenAIApiChatModel=object)
    with (
        patch.dict(
            "sys.modules",
            {
                "langchain_azure_ai": SimpleNamespace(chat_models=fake_chat_models),
                "langchain_azure_ai.chat_models": fake_chat_models,
            },
        ),
        patch("lfx.base.models.unified_models.model_catalog.get_unified_models_detailed", return_value=[]),
        patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response),
    ):
        validate_model_provider_key(
            "Azure AI Foundry",
            {
                "AZURE_AI_FOUNDRY_API_KEY": "test-key",  # pragma: allowlist secret
                "AZURE_AI_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/api/projects/proj-default",
            },
        )


def test_validate_model_provider_key_azure_ai_foundry_passes_api_version_variable():
    from types import SimpleNamespace

    from lfx.base.models import model_utils
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock(status_code=200)
    response.json.return_value = {"data": []}
    fake_chat_models = SimpleNamespace(AzureAIOpenAIApiChatModel=object)
    with (
        patch.dict(
            "sys.modules",
            {
                "langchain_azure_ai": SimpleNamespace(chat_models=fake_chat_models),
                "langchain_azure_ai.chat_models": fake_chat_models,
            },
        ),
        patch("lfx.base.models.unified_models.model_catalog.get_unified_models_detailed", return_value=[]),
        patch.object(model_utils, "ssrf_safe_httpx_get", return_value=response) as mock_get,
    ):
        validate_model_provider_key(
            "Azure AI Foundry",
            {
                "AZURE_AI_FOUNDRY_API_KEY": "test-key",  # pragma: allowlist secret
                "AZURE_AI_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/models",
                "AZURE_AI_FOUNDRY_API_VERSION": "2024-10-21",
            },
        )

    assert mock_get.call_args.args[0] == "https://example.services.ai.azure.com/models?api-version=2024-10-21"


def _build_azure_ai_foundry_model_selection() -> list[dict]:
    return [
        {
            "name": "gpt-4o",
            "provider": "Azure AI Foundry",
            "metadata": {},
        }
    ]


def test_get_llm_wires_azure_ai_foundry_endpoint_and_credential():
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models import instantiation
    from lfx.base.models.unified_models.instantiation import get_llm

    captured_kwargs: dict = {}

    class FakeFoundryChatModel:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    with (
        patch.object(
            unified_models_module,
            "get_api_key_for_provider",
            return_value="test-key",
        ),
        patch.object(unified_models_module, "get_model_class", return_value=FakeFoundryChatModel),
        patch.object(
            unified_models_module,
            "get_all_variables_for_provider",
            return_value={"AZURE_AI_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/openai/v1"},
        ),
        patch.object(instantiation, "validate_url_for_ssrf_or_raise"),
    ):
        get_llm(_build_azure_ai_foundry_model_selection(), user_id="user-1", stream=False)

    assert captured_kwargs["model"] == "gpt-4o"
    assert captured_kwargs["credential"] == "test-key"
    assert captured_kwargs["endpoint"] == "https://example.services.ai.azure.com/openai/v1"
    assert captured_kwargs["request_timeout"] == 10.0


def test_get_llm_normalizes_stored_project_endpoint():
    """A project endpoint stored as the provider variable is normalized at instantiation too."""
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models import instantiation
    from lfx.base.models.unified_models.instantiation import get_llm

    captured_kwargs: dict = {}

    class FakeFoundryChatModel:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    with (
        patch.object(
            unified_models_module,
            "get_api_key_for_provider",
            return_value="test-key",
        ),
        patch.object(unified_models_module, "get_model_class", return_value=FakeFoundryChatModel),
        patch.object(
            unified_models_module,
            "get_all_variables_for_provider",
            return_value={"AZURE_AI_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/api/projects/my-project"},
        ),
        patch.object(instantiation, "validate_url_for_ssrf_or_raise"),
    ):
        get_llm(_build_azure_ai_foundry_model_selection(), user_id="user-1", stream=False)

    assert captured_kwargs["endpoint"] == "https://example.services.ai.azure.com/openai/v1"


def test_get_llm_azure_ai_foundry_requires_endpoint():
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_llm

    class FakeFoundryChatModel:
        def __init__(self, **kwargs):
            pass

    with (
        patch.object(unified_models_module, "get_api_key_for_provider", return_value="test-key"),
        patch.object(unified_models_module, "get_model_class", return_value=FakeFoundryChatModel),
        patch.object(unified_models_module, "get_all_variables_for_provider", return_value={}),
        patch("lfx.base.models.unified_models.instantiation._env_if_allowed", return_value=None),
        pytest.raises(ValueError, match="Azure AI Foundry endpoint is required"),
    ):
        get_llm(_build_azure_ai_foundry_model_selection(), user_id="user-1", stream=False)


def test_shared_deployment_aliases_resolve_to_openai_for_backwards_compat():
    """Seed Foundry deployment names overlap OpenAI; legacy lookup must prefer OpenAI.

    ``get_provider_for_model_name`` scans the static catalog in list order. Flows
    exported from 1.8.x only stored the model id (e.g. ``gpt-4o``) without a
    provider, so ambiguous aliases must keep resolving to OpenAI.
    """
    from lfx.base.models.unified_models import get_provider_for_model_name

    assert get_provider_for_model_name("gpt-4o") == "OpenAI"
    assert get_provider_for_model_name("Mistral-Large-3") == "Azure AI Foundry"
