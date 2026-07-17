"""Unit tests for the lfx-openai-compatible bundle's live discovery and credential validation.

Adapted from the lfx-vllm bundle tests, retargeted at the standalone
``lfx_openai_compatible.discovery`` module.

Covers:
  - fetch_live_openai_compatible_models: empty base URL, OpenAI-dict and
    plain-list payloads, /v1 deduplication, bearer-header forwarding, no-auth,
    and degradation paths.
  - validate_openai_compatible_credentials: success, missing URL, 401/403,
    server error, connection error, timeout, and /v1 deduplication.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from lfx_openai_compatible import discovery

# ---------------------------------------------------------------------------
# End-to-end registration through the extension loader
# ---------------------------------------------------------------------------


def test_bundle_registers_provider_end_to_end():
    """Loading the bundle registers OpenAI Compatible into the unified model system."""
    from lfx.base.models import provider_registry
    from lfx.base.models.unified_models import get_live_only_providers, get_model_providers
    from lfx.extension import load_extension

    provider_registry.clear()
    try:
        root = Path(__file__).resolve().parents[1] / "src" / "lfx_openai_compatible"
        result = load_extension(root)
        assert result.ok, (result.errors, result.warnings)
        assert result.components == []  # provider-only bundle: no components
        assert provider_registry.is_registered("OpenAI Compatible")
        assert "OpenAI Compatible" in get_model_providers()
        # No static catalog + live discovery => must surface through the
        # /api/v1/models live-only union so the unconfigured provider is
        # offered for configuration in the Model Providers dialog.
        assert "OpenAI Compatible" in get_live_only_providers()
        assert provider_registry.is_api_key_optional("OpenAI Compatible")
        assert provider_registry.live_discovery_for("OpenAI Compatible") is not None
        assert provider_registry.validator_for("OpenAI Compatible") is not None
    finally:
        provider_registry.clear()


def _ok_response(payload: dict | list) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = payload
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# fetch_live_openai_compatible_models
# ---------------------------------------------------------------------------


def test_fetch_returns_empty_when_no_base_url():
    with patch.object(discovery, "get_provider_variable_value", return_value=None):
        assert discovery.fetch_live_openai_compatible_models("user-id", "llm") == []


def test_fetch_openai_dict_format():
    response = _ok_response({"data": [{"id": "meta-llama/llama-3.1-8b"}, {"id": "mistral-7b"}]})
    with (
        patch.object(discovery, "get_provider_variable_value", side_effect=["https://openrouter.ai/api/v1", None]),
        patch.object(discovery, "validate_connector_url_for_ssrf", return_value=None),
        patch.object(discovery.requests, "get", return_value=response),
    ):
        result = discovery.fetch_live_openai_compatible_models("user-id", "llm")
    assert {m["name"] for m in result} == {"meta-llama/llama-3.1-8b", "mistral-7b"}
    assert all(m["provider"] == "OpenAI Compatible" and m["icon"] == "Plug" for m in result)
    assert all(m["tool_calling"] for m in result)  # llm context -> tool calling on


def test_fetch_plain_list_format():
    response = _ok_response(["qwen2-7b", "deepseek-r1"])
    with (
        patch.object(discovery, "get_provider_variable_value", side_effect=["http://localhost:8000", None]),
        patch.object(discovery, "validate_connector_url_for_ssrf", return_value=None),
        patch.object(discovery.requests, "get", return_value=response),
    ):
        result = discovery.fetch_live_openai_compatible_models("user-id", "llm")
    assert {m["name"] for m in result} == {"qwen2-7b", "deepseek-r1"}


def test_fetch_sorts_alphabetically():
    response = _ok_response({"data": [{"id": "zzz"}, {"id": "aaa"}, {"id": "mmm"}]})
    with (
        patch.object(discovery, "get_provider_variable_value", side_effect=["http://localhost:8000", None]),
        patch.object(discovery, "validate_connector_url_for_ssrf", return_value=None),
        patch.object(discovery.requests, "get", return_value=response),
    ):
        result = discovery.fetch_live_openai_compatible_models("user-id", "llm")
    assert [m["name"] for m in result] == ["aaa", "mmm", "zzz"]


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("http://localhost:8000", "http://localhost:8000/v1/models"),
        ("http://localhost:8000/v1", "http://localhost:8000/v1/models"),
        ("http://localhost:8000/", "http://localhost:8000/v1/models"),
        ("https://api.groq.com/openai/v1", "https://api.groq.com/openai/v1/models"),
    ],
)
def test_fetch_models_url_normalization(base_url, expected):
    response = _ok_response({"data": [{"id": "llama-3"}]})
    captured: list[str] = []

    def fake_get(url, **_kwargs):
        captured.append(url)
        return response

    with (
        patch.object(discovery, "get_provider_variable_value", side_effect=[base_url, None]),
        patch.object(discovery, "validate_connector_url_for_ssrf", return_value=None),
        patch.object(discovery.requests, "get", side_effect=fake_get),
    ):
        discovery.fetch_live_openai_compatible_models("user-id", "llm")
    assert captured[0] == expected


def test_fetch_forwards_api_key_as_bearer():
    response = _ok_response({"data": [{"id": "llama-3"}]})
    captured: list[dict] = []

    def fake_get(_url, headers=None, **_kwargs):
        captured.append(headers or {})
        return response

    with (
        patch.object(
            discovery,
            "get_provider_variable_value",
            side_effect=["http://localhost:8000", "secret-key"],  # pragma: allowlist secret
        ),
        patch.object(discovery, "validate_connector_url_for_ssrf", return_value=None),
        patch.object(discovery.requests, "get", side_effect=fake_get),
    ):
        discovery.fetch_live_openai_compatible_models("user-id", "llm")
    assert captured[0].get("Authorization") == "Bearer secret-key"  # pragma: allowlist secret


def test_fetch_no_auth_header_when_no_key():
    response = _ok_response({"data": [{"id": "llama-3"}]})
    captured: list[dict] = []

    def fake_get(_url, headers=None, **_kwargs):
        captured.append(headers or {})
        return response

    with (
        patch.object(discovery, "get_provider_variable_value", side_effect=["http://localhost:8000", None]),
        patch.object(discovery, "validate_connector_url_for_ssrf", return_value=None),
        patch.object(discovery.requests, "get", side_effect=fake_get),
    ):
        discovery.fetch_live_openai_compatible_models("user-id", "llm")
    assert "Authorization" not in captured[0]


def test_fetch_swallows_connection_error():
    with (
        patch.object(discovery, "get_provider_variable_value", side_effect=["http://localhost:8000", None]),
        patch.object(discovery, "validate_connector_url_for_ssrf", return_value=None),
        patch.object(discovery.requests, "get", side_effect=requests.ConnectionError("refused")),
    ):
        assert discovery.fetch_live_openai_compatible_models("user-id", "llm") == []


def test_fetch_swallows_bad_payload():
    response = _ok_response({"unexpected": "shape"})
    with (
        patch.object(discovery, "get_provider_variable_value", side_effect=["http://localhost:8000", None]),
        patch.object(discovery, "validate_connector_url_for_ssrf", return_value=None),
        patch.object(discovery.requests, "get", return_value=response),
    ):
        assert discovery.fetch_live_openai_compatible_models("user-id", "llm") == []


def test_fetch_swallows_api_key_lookup_error():
    """A failing API-key lookup falls back to anonymous discovery instead of blocking it."""
    response = _ok_response({"data": [{"id": "llama-3"}]})

    def fake_get_var(_user_id, key):
        if key == "OPENAI_COMPATIBLE_BASE_URL":
            return "http://localhost:8000"
        msg = "variable not found"
        raise RuntimeError(msg)

    with (
        patch.object(discovery, "get_provider_variable_value", side_effect=fake_get_var),
        patch.object(discovery, "validate_connector_url_for_ssrf", return_value=None),
        patch.object(discovery.requests, "get", return_value=response),
    ):
        result = discovery.fetch_live_openai_compatible_models("user-id", "llm")
    assert {m["name"] for m in result} == {"llama-3"}


def test_fetch_embeddings_tagged_embeddings():
    response = _ok_response({"data": [{"id": "bge-m3"}]})
    with (
        patch.object(discovery, "get_provider_variable_value", side_effect=["http://localhost:8000", None]),
        patch.object(discovery, "validate_connector_url_for_ssrf", return_value=None),
        patch.object(discovery.requests, "get", return_value=response),
    ):
        result = discovery.fetch_live_openai_compatible_models("user-id", "embeddings")
    assert result[0]["model_type"] == "embeddings"
    assert result[0]["tool_calling"] is False


# ---------------------------------------------------------------------------
# validate_openai_compatible_credentials
# ---------------------------------------------------------------------------


def test_validate_raises_when_no_base_url():
    with pytest.raises(ValueError, match="Invalid OpenAI-compatible base URL"):
        discovery.validate_openai_compatible_credentials("OpenAI Compatible", {})


def test_validate_happy_path_uses_v1_models():
    response = _ok_response({"data": []})
    captured: list[str] = []

    def fake_get(url, **_kwargs):
        captured.append(url)
        return response

    with (
        patch.object(discovery, "validate_connector_url_for_ssrf", return_value=None),
        patch.object(discovery.requests, "get", side_effect=fake_get),
    ):
        discovery.validate_openai_compatible_credentials(
            "OpenAI Compatible", {"OPENAI_COMPATIBLE_BASE_URL": "http://localhost:8000/v1"}
        )
    assert captured[0] == "http://localhost:8000/v1/models"


def test_validate_allows_literal_loopback_by_default(monkeypatch):
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK", "true")
    monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)
    response = _ok_response({"data": []})

    with patch.object(discovery.requests, "get", return_value=response) as mock_get:
        discovery.validate_openai_compatible_credentials(
            "OpenAI Compatible", {"OPENAI_COMPATIBLE_BASE_URL": "http://127.0.0.1:1234/v1"}
        )

    mock_get.assert_called_once_with(
        "http://127.0.0.1:1234/v1/models",
        headers={},
        timeout=discovery._TIMEOUT_SECONDS,
    )


def test_validate_blocks_literal_loopback_when_connector_policy_opts_out(monkeypatch):
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK", "false")
    monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)

    with (
        patch.object(discovery.requests, "get") as mock_get,
        pytest.raises(ValueError, match=r"127\.0\.0\.1.*blocked"),
    ):
        discovery.validate_openai_compatible_credentials(
            "OpenAI Compatible", {"OPENAI_COMPATIBLE_BASE_URL": "http://127.0.0.1:1234/v1"}
        )

    mock_get.assert_not_called()


def test_validate_forwards_api_key():
    response = _ok_response({"data": []})
    captured: dict = {}

    def fake_get(_url, **kwargs):
        captured.update(kwargs)
        return response

    with (
        patch.object(discovery, "validate_connector_url_for_ssrf", return_value=None),
        patch.object(discovery.requests, "get", side_effect=fake_get),
    ):
        discovery.validate_openai_compatible_credentials(
            "OpenAI Compatible",
            {
                "OPENAI_COMPATIBLE_BASE_URL": "http://localhost:8000",
                "OPENAI_COMPATIBLE_API_KEY": "k",  # pragma: allowlist secret
            },
        )
    assert captured["headers"]["Authorization"] == "Bearer k"  # pragma: allowlist secret


@pytest.mark.parametrize("status", [401, 403])
def test_validate_raises_on_auth_failure(status):
    response = MagicMock()
    response.status_code = status
    with (
        patch.object(discovery, "validate_connector_url_for_ssrf", return_value=None),
        patch.object(discovery.requests, "get", return_value=response),
        pytest.raises(ValueError, match="Authentication failed"),
    ):
        discovery.validate_openai_compatible_credentials(
            "OpenAI Compatible", {"OPENAI_COMPATIBLE_BASE_URL": "http://localhost:8000"}
        )


def test_validate_raises_value_error_on_server_error():
    """Non-auth HTTP failures (e.g. 500) surface as the same user-facing ValueError shape."""
    response = MagicMock()
    response.status_code = 500
    http_error = requests.HTTPError("server error", response=response)
    response.raise_for_status.side_effect = http_error
    with (
        patch.object(discovery, "validate_connector_url_for_ssrf", return_value=None),
        patch.object(discovery.requests, "get", return_value=response),
        pytest.raises(ValueError, match="returned HTTP 500"),
    ):
        discovery.validate_openai_compatible_credentials(
            "OpenAI Compatible", {"OPENAI_COMPATIBLE_BASE_URL": "http://localhost:8000"}
        )


def test_validate_raises_on_connection_error():
    with (
        patch.object(discovery, "validate_connector_url_for_ssrf", return_value=None),
        patch.object(discovery.requests, "get", side_effect=requests.ConnectionError("refused")),
        pytest.raises(ValueError, match="Could not connect to the OpenAI-compatible endpoint"),
    ):
        discovery.validate_openai_compatible_credentials(
            "OpenAI Compatible", {"OPENAI_COMPATIBLE_BASE_URL": "http://localhost:8000"}
        )


def test_validate_raises_on_timeout():
    with (
        patch.object(discovery, "validate_connector_url_for_ssrf", return_value=None),
        patch.object(discovery.requests, "get", side_effect=requests.Timeout("slow")),
        pytest.raises(ValueError, match="timed out"),
    ):
        discovery.validate_openai_compatible_credentials(
            "OpenAI Compatible", {"OPENAI_COMPATIBLE_BASE_URL": "http://localhost:8000"}
        )
