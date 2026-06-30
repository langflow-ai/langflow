"""Unit tests for the vLLM unified model provider.

Covers:
  - Provider metadata registration (variables, mapping, live-fetch flag).
  - fetch_live_vllm_models — mocks the vLLM /v1/models endpoint and pins the
    model-list parsing for both OpenAI-dict and plain-list payloads, auth header
    forwarding, /v1 deduplication, and degradation paths.
  - validate_model_provider_key — success, 401/403 auth error, connection error,
    timeout, and missing URL paths.
  - get_model_providers — vLLM appears despite having no static catalog.
  - API-key-optional contract — vLLM does not raise when no API key is set.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def test_vllm_in_live_model_providers():
    from lfx.base.models.model_metadata import LIVE_MODEL_PROVIDERS

    assert "vLLM" in LIVE_MODEL_PROVIDERS


def test_vllm_in_provider_metadata():
    from lfx.base.models.model_metadata import MODEL_PROVIDER_METADATA

    assert "vLLM" in MODEL_PROVIDER_METADATA


def test_vllm_metadata_shape():
    from lfx.base.models.model_metadata import MODEL_PROVIDER_METADATA

    meta = MODEL_PROVIDER_METADATA["vLLM"]
    assert meta["icon"] == "vLLM"
    assert meta["mapping"]["model_class"] == "ChatOpenAI"
    assert meta["mapping"]["model_param"] == "model"
    assert meta["api_docs_url"] == "https://docs.vllm.ai/"

    var_keys = {v["variable_key"] for v in meta["variables"]}
    assert var_keys == {"VLLM_API_BASE", "VLLM_API_KEY"}

    by_key = {v["variable_key"]: v for v in meta["variables"]}
    assert by_key["VLLM_API_BASE"]["required"] is True
    assert by_key["VLLM_API_BASE"]["is_secret"] is False
    assert by_key["VLLM_API_KEY"]["required"] is False
    assert by_key["VLLM_API_KEY"]["is_secret"] is True


def test_vllm_base_url_mapping_field_recognized_by_param_mapping():
    """Ensure mapping_field 'vllm_base_url' contains 'base_url'.

    get_provider_param_mapping classifies it as a URL parameter and sets
    base_url_param for downstream consumers.
    """
    from lfx.base.models.model_metadata import MODEL_PROVIDER_METADATA

    meta = MODEL_PROVIDER_METADATA["vLLM"]
    by_key = {v["variable_key"]: v for v in meta["variables"]}
    mapping_field = by_key["VLLM_API_BASE"]["component_metadata"]["mapping_field"]
    assert "base_url" in mapping_field, (
        f"mapping_field '{mapping_field}' must contain 'base_url' so the param "
        "classifier in get_provider_param_mapping sets base_url_param"
    )


def test_vllm_appears_in_get_model_providers():
    """VLLM must appear in get_model_providers() even though it has no static catalog."""
    from lfx.base.models.unified_models import get_model_providers

    assert "vLLM" in get_model_providers()


def test_vllm_in_embedding_class_registry():
    from lfx.base.models.unified_models.class_registry import EMBEDDING_PROVIDER_CLASS_MAPPING

    assert EMBEDDING_PROVIDER_CLASS_MAPPING["vLLM"] == "OpenAIEmbeddings"


# ---------------------------------------------------------------------------
# Live model fetcher — fetch_live_vllm_models
# ---------------------------------------------------------------------------


def _ok_response(payload: dict | list) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def test_fetch_live_vllm_models_returns_empty_when_no_base_url():
    from lfx.base.models import model_utils

    with patch.object(model_utils, "get_provider_variable_value", return_value=None):
        assert model_utils.fetch_live_vllm_models("user-id", "llm") == []


def test_fetch_live_vllm_models_openai_dict_format():
    """Standard OpenAI-compatible {'data': [{'id': '...'}]} response."""
    from lfx.base.models import model_utils

    response = _ok_response({"data": [{"id": "meta-llama/llama-3.1-8b"}, {"id": "mistral-7b"}]})

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=["http://localhost:8000", None]),
        patch.object(model_utils, "validate_url_for_ssrf", return_value=None),
        patch.object(model_utils.requests, "get", return_value=response),
    ):
        result = model_utils.fetch_live_vllm_models("user-id", "llm")

    assert len(result) == 2
    names = {m["name"] for m in result}
    assert names == {"meta-llama/llama-3.1-8b", "mistral-7b"}
    for m in result:
        assert m["provider"] == "vLLM"
        assert m["icon"] == "vLLM"


def test_fetch_live_vllm_models_plain_list_format():
    """Fallback simple list format ['model1', 'model2']."""
    from lfx.base.models import model_utils

    response = _ok_response(["qwen2-7b", "deepseek-r1"])

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=["http://localhost:8000", None]),
        patch.object(model_utils, "validate_url_for_ssrf", return_value=None),
        patch.object(model_utils.requests, "get", return_value=response),
    ):
        result = model_utils.fetch_live_vllm_models("user-id", "llm")

    names = {m["name"] for m in result}
    assert names == {"qwen2-7b", "deepseek-r1"}


def test_fetch_live_vllm_models_sorts_alphabetically():
    from lfx.base.models import model_utils

    response = _ok_response({"data": [{"id": "zzz-model"}, {"id": "aaa-model"}, {"id": "mmm-model"}]})

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=["http://localhost:8000", None]),
        patch.object(model_utils, "validate_url_for_ssrf", return_value=None),
        patch.object(model_utils.requests, "get", return_value=response),
    ):
        result = model_utils.fetch_live_vllm_models("user-id", "llm")

    assert [m["name"] for m in result] == ["aaa-model", "mmm-model", "zzz-model"]


def test_fetch_live_vllm_models_url_with_v1_suffix_not_duplicated():
    """A base URL already ending in /v1 must not produce /v1/v1/models."""
    from lfx.base.models import model_utils

    response = _ok_response({"data": [{"id": "llama-3"}]})
    captured_url = []

    def fake_get(url, **_kwargs):
        captured_url.append(url)
        return response

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=["http://localhost:8000/v1", None]),
        patch.object(model_utils, "validate_url_for_ssrf", return_value=None),
        patch.object(model_utils.requests, "get", side_effect=fake_get),
    ):
        model_utils.fetch_live_vllm_models("user-id", "llm")

    assert captured_url[0] == "http://localhost:8000/v1/models"


def test_fetch_live_vllm_models_url_without_v1_gets_v1_prepended():
    """A base URL without /v1 must have /v1/models appended."""
    from lfx.base.models import model_utils

    response = _ok_response({"data": [{"id": "llama-3"}]})
    captured_url = []

    def fake_get(url, **_kwargs):
        captured_url.append(url)
        return response

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=["http://localhost:8000", None]),
        patch.object(model_utils, "validate_url_for_ssrf", return_value=None),
        patch.object(model_utils.requests, "get", side_effect=fake_get),
    ):
        model_utils.fetch_live_vllm_models("user-id", "llm")

    assert captured_url[0] == "http://localhost:8000/v1/models"


def test_fetch_live_vllm_models_forwards_api_key_as_bearer():
    """When VLLM_API_KEY is set it must be forwarded as Authorization: Bearer."""
    from lfx.base.models import model_utils

    response = _ok_response({"data": [{"id": "llama-3"}]})
    captured_headers = []

    def fake_get(_url, headers=None, **_kwargs):
        captured_headers.append(headers or {})
        return response

    with (
        patch.object(
            model_utils,
            "get_provider_variable_value",
            side_effect=["http://localhost:8000", "my-secret-key"],  # pragma: allowlist secret
        ),
        patch.object(model_utils, "validate_url_for_ssrf", return_value=None),
        patch.object(model_utils.requests, "get", side_effect=fake_get),
    ):
        model_utils.fetch_live_vllm_models("user-id", "llm")

    assert captured_headers[0].get("Authorization") == "Bearer my-secret-key"  # pragma: allowlist secret


def test_fetch_live_vllm_models_no_auth_header_when_no_key():
    """When no API key is configured, no Authorization header is sent."""
    from lfx.base.models import model_utils

    response = _ok_response({"data": [{"id": "llama-3"}]})
    captured_headers = []

    def fake_get(_url, headers=None, **_kwargs):
        captured_headers.append(headers or {})
        return response

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=["http://localhost:8000", None]),
        patch.object(model_utils, "validate_url_for_ssrf", return_value=None),
        patch.object(model_utils.requests, "get", side_effect=fake_get),
    ):
        model_utils.fetch_live_vllm_models("user-id", "llm")

    assert "Authorization" not in captured_headers[0]


def test_fetch_live_vllm_models_swallows_connection_error():
    from lfx.base.models import model_utils

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=["http://localhost:8000", None]),
        patch.object(model_utils, "validate_url_for_ssrf", return_value=None),
        patch.object(model_utils.requests, "get", side_effect=requests.ConnectionError("refused")),
    ):
        assert model_utils.fetch_live_vllm_models("user-id", "llm") == []


def test_fetch_live_vllm_models_swallows_timeout():
    from lfx.base.models import model_utils

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=["http://localhost:8000", None]),
        patch.object(model_utils, "validate_url_for_ssrf", return_value=None),
        patch.object(model_utils.requests, "get", side_effect=requests.Timeout("timeout")),
    ):
        assert model_utils.fetch_live_vllm_models("user-id", "llm") == []


def test_fetch_live_vllm_models_swallows_bad_payload():
    """A 200 with an unrecognised payload shape should return []."""
    from lfx.base.models import model_utils

    response = _ok_response({"unexpected_key": "unexpected_value"})

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=["http://localhost:8000", None]),
        patch.object(model_utils, "validate_url_for_ssrf", return_value=None),
        patch.object(model_utils.requests, "get", return_value=response),
    ):
        assert model_utils.fetch_live_vllm_models("user-id", "llm") == []


def test_fetch_live_vllm_models_llm_and_embeddings_same_output():
    """VLLM returns all models regardless of model_type — both calls yield the same list."""
    from lfx.base.models import model_utils

    response = _ok_response({"data": [{"id": "llama-3"}, {"id": "embedding-model"}]})

    def get_var(_user_id, key):
        if key == "VLLM_API_BASE":
            return "http://localhost:8000"
        return None

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=get_var),
        patch.object(model_utils, "validate_url_for_ssrf", return_value=None),
        patch.object(model_utils.requests, "get", return_value=response),
    ):
        llm_result = model_utils.fetch_live_vllm_models("user-id", "llm")

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=get_var),
        patch.object(model_utils, "validate_url_for_ssrf", return_value=None),
        patch.object(model_utils.requests, "get", return_value=response),
    ):
        emb_result = model_utils.fetch_live_vllm_models("user-id", "embeddings")

    assert {m["name"] for m in llm_result} == {m["name"] for m in emb_result}


def test_get_live_models_dispatches_to_vllm():
    from lfx.base.models import model_utils

    with patch.object(model_utils, "fetch_live_vllm_models", return_value=[{"name": "llama-3"}]) as mocked:
        result = model_utils.get_live_models_for_provider("user-id", "vLLM", "llm")

    mocked.assert_called_once_with("user-id", "llm")
    assert result == [{"name": "llama-3"}]


# ---------------------------------------------------------------------------
# Validation — validate_model_provider_key
# ---------------------------------------------------------------------------


def test_validate_vllm_raises_when_no_base_url():
    from lfx.base.models.unified_models import validate_model_provider_key

    with pytest.raises(ValueError, match="Invalid vLLM API base URL"):
        validate_model_provider_key("vLLM", {})


def test_validate_vllm_raises_when_base_url_is_empty():
    from lfx.base.models.unified_models import validate_model_provider_key

    with pytest.raises(ValueError, match="Invalid vLLM API base URL"):
        validate_model_provider_key("vLLM", {"VLLM_API_BASE": ""})


def test_validate_vllm_happy_path():
    """Validation passes when GET /v1/models returns 200."""
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None

    with patch.object(requests, "get", return_value=response) as mock_get:
        validate_model_provider_key("vLLM", {"VLLM_API_BASE": "http://localhost:8000"})

    mock_get.assert_called_once()
    call_url = mock_get.call_args.args[0]
    assert call_url == "http://localhost:8000/v1/models"


def test_validate_vllm_uses_v1_models_endpoint():
    """Validation must call /v1/models, not /models."""
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None
    captured_url = []

    def fake_get(url, **_kwargs):
        captured_url.append(url)
        return response

    with patch.object(requests, "get", side_effect=fake_get):
        validate_model_provider_key("vLLM", {"VLLM_API_BASE": "http://my-vllm.local"})

    assert captured_url[0].endswith("/v1/models"), (
        f"Expected /v1/models endpoint, got: {captured_url[0]}"
    )


def test_validate_vllm_forwards_api_key():
    """VLLM_API_KEY must be sent as Authorization: Bearer."""
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None
    captured_kwargs: dict = {}

    def fake_get(_url, **kwargs):
        captured_kwargs.update(kwargs)
        return response

    with patch.object(requests, "get", side_effect=fake_get):
        validate_model_provider_key(
            "vLLM",
            {
                "VLLM_API_BASE": "http://localhost:8000",
                "VLLM_API_KEY": "secret-key",  # pragma: allowlist secret
            },
        )

    assert captured_kwargs["headers"]["Authorization"] == "Bearer secret-key"  # pragma: allowlist secret


def test_validate_vllm_no_auth_header_without_api_key():
    """No Authorization header should be sent when VLLM_API_KEY is absent."""
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None
    captured_kwargs: dict = {}

    def fake_get(_url, **kwargs):
        captured_kwargs.update(kwargs)
        return response

    with patch.object(requests, "get", side_effect=fake_get):
        validate_model_provider_key("vLLM", {"VLLM_API_BASE": "http://localhost:8000"})

    assert "Authorization" not in captured_kwargs.get("headers", {})


def test_validate_vllm_raises_on_401():
    """A 401 from the vLLM server must raise ValueError with a clear auth message."""
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock()
    response.status_code = 401
    response.raise_for_status.side_effect = AssertionError("should not reach raise_for_status on 401")

    with (
        patch.object(requests, "get", return_value=response),
        pytest.raises(ValueError, match="Authentication failed"),
    ):
        validate_model_provider_key(
            "vLLM",
            {
                "VLLM_API_BASE": "http://localhost:8000",
                "VLLM_API_KEY": "wrong-key",  # pragma: allowlist secret
            },
        )


def test_validate_vllm_raises_on_403():
    """A 403 from the vLLM server must also raise ValueError."""
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock()
    response.status_code = 403
    response.raise_for_status.side_effect = AssertionError("should not reach raise_for_status on 403")

    with (
        patch.object(requests, "get", return_value=response),
        pytest.raises(ValueError, match="Authentication failed"),
    ):
        validate_model_provider_key(
            "vLLM",
            {
                "VLLM_API_BASE": "http://localhost:8000",
                "VLLM_API_KEY": "wrong-key",  # pragma: allowlist secret
            },
        )


def test_validate_vllm_raises_on_connection_error():
    """A connection error must raise a descriptive ValueError."""
    from lfx.base.models.unified_models import validate_model_provider_key

    with (
        patch.object(requests, "get", side_effect=requests.ConnectionError("connection refused")),
        pytest.raises(ValueError, match="Could not connect to vLLM server"),
    ):
        validate_model_provider_key("vLLM", {"VLLM_API_BASE": "http://localhost:8000"})


def test_validate_vllm_raises_on_timeout():
    """A timeout must raise a descriptive ValueError."""
    from lfx.base.models.unified_models import validate_model_provider_key

    with (
        patch.object(requests, "get", side_effect=requests.Timeout("timed out")),
        pytest.raises(ValueError, match="timed out"),
    ):
        validate_model_provider_key("vLLM", {"VLLM_API_BASE": "http://localhost:8000"})


def test_validate_vllm_v1_suffix_not_duplicated():
    """If VLLM_API_BASE already ends with /v1, the endpoint must be /v1/models not /v1/v1/models."""
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None
    captured_url = []

    def fake_get(url, **_kwargs):
        captured_url.append(url)
        return response

    with patch.object(requests, "get", side_effect=fake_get):
        validate_model_provider_key("vLLM", {"VLLM_API_BASE": "http://localhost:8000/v1"})

    assert captured_url[0] == "http://localhost:8000/v1/models"
    assert "/v1/v1/" not in captured_url[0]


# ---------------------------------------------------------------------------
# API-key-optional contract
# ---------------------------------------------------------------------------


def test_get_llm_does_not_raise_when_no_api_key_for_vllm():
    """VLLM does not require an API key — get_llm must not raise on a missing key."""
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_llm

    captured_kwargs: dict = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    model_selection = [
        {
            "name": "llama-3-8b",
            "provider": "vLLM",
            "metadata": {
                "model_class": "ChatOpenAI",
                "model_name_param": "model",
                "api_key_param": "api_key",  # pragma: allowlist secret
            },
        }
    ]

    with (
        patch.object(unified_models_module, "get_api_key_for_provider", return_value=None),
        patch.object(unified_models_module, "get_model_class", return_value=FakeChatOpenAI),
        patch.object(unified_models_module, "get_all_variables_for_provider", return_value={}),
    ):
        get_llm(model_selection, user_id=None)

    assert captured_kwargs["model"] == "llama-3-8b"


def test_get_embeddings_does_not_raise_when_no_api_key_for_vllm():
    """VLLM Embeddings does not require an API key and resolves base_url from VLLM_API_BASE."""
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_embeddings

    captured_kwargs: dict = {}

    class FakeOpenAIEmbeddings:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    model_selection = [
        {
            "name": "text-embedding-ada-002",
            "provider": "vLLM Embeddings",
            "metadata": {
                "embedding_class": "OpenAIEmbeddings",
                "param_mapping": {
                    "model": "model",
                    "api_key": "api_key",  # pragma: allowlist secret
                    "api_base": "base_url",
                },
            },
        }
    ]

    with (
        patch.object(unified_models_module, "get_api_key_for_provider", return_value=None),
        patch.object(unified_models_module, "get_embedding_class", return_value=FakeOpenAIEmbeddings),
        patch.object(
            unified_models_module,
            "get_all_variables_for_provider",
            return_value={"VLLM_API_BASE": "http://localhost:8000"},
        ),
    ):
        get_embeddings(model_selection, user_id=None)

    assert captured_kwargs["model"] == "text-embedding-ada-002"
    assert captured_kwargs.get("base_url") == "http://localhost:8000"
