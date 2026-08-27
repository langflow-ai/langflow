"""Unit tests for the lfx-vllm bundle's live discovery and credential validation.

Adapted from the original vLLM provider tests in
https://github.com/langflow-ai/langflow/pull/13910 by Yash Pareek, retargeted at
the bundle's standalone ``lfx_vllm.discovery`` module.

Covers:
  - fetch_live_vllm_models: empty base URL, OpenAI-dict and plain-list payloads,
    /v1 deduplication, bearer-header forwarding, no-auth, and degradation paths.
  - validate_vllm_credentials: success, missing URL, 401/403, connection error,
    timeout, and /v1 deduplication.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx_vllm import discovery

# ---------------------------------------------------------------------------
# End-to-end registration through the extension loader
# ---------------------------------------------------------------------------


def test_bundle_registers_vllm_provider_end_to_end():
    """Loading the bundle registers vLLM into the unified model system."""
    from lfx.base.models import provider_registry
    from lfx.base.models.unified_models import get_model_providers
    from lfx.extension import load_extension

    provider_registry.clear()
    try:
        root = Path(__file__).resolve().parents[1] / "src" / "lfx_vllm"
        result = load_extension(root)
        assert result.ok, (result.errors, result.warnings)
        assert result.components == []  # provider-only bundle: no components
        assert provider_registry.is_registered("vLLM")
        assert "vLLM" in get_model_providers()
        assert provider_registry.is_api_key_optional("vLLM")
        assert provider_registry.live_discovery_for("vLLM") is not None
        assert provider_registry.validator_for("vLLM") is not None
    finally:
        provider_registry.clear()


def _ok_response(payload: dict | list) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = payload
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    return resp


def _set_loopback_policy(monkeypatch, *, allowed: bool) -> None:
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK", str(allowed).lower())
    monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)


# ---------------------------------------------------------------------------
# fetch_live_vllm_models
# ---------------------------------------------------------------------------


def test_fetch_returns_empty_when_no_base_url():
    with patch.object(discovery, "get_provider_variable_value", return_value=None):
        assert discovery.fetch_live_vllm_models("user-id", "llm") == []


def test_fetch_allows_literal_loopback_by_default(monkeypatch):
    _set_loopback_policy(monkeypatch, allowed=True)
    response = _ok_response({"data": [{"id": "local-model"}]})

    with (
        patch.object(discovery, "get_provider_variable_value", side_effect=["http://127.0.0.1:8000/v1", None]),
        patch("httpx.Client.get", return_value=response) as mock_get,
    ):
        result = discovery.fetch_live_vllm_models("user-id", "llm")

    assert [model["name"] for model in result] == ["local-model"]
    mock_get.assert_called_once()
    assert mock_get.call_args.kwargs["follow_redirects"] is False


def test_fetch_blocks_literal_loopback_when_connector_policy_opts_out(monkeypatch):
    _set_loopback_policy(monkeypatch, allowed=False)

    with (
        patch.object(discovery, "get_provider_variable_value", side_effect=["http://127.0.0.1:8000/v1", None]),
        patch("httpx.Client.get") as mock_get,
    ):
        result = discovery.fetch_live_vllm_models("user-id", "llm")

    assert result == []
    mock_get.assert_not_called()


def test_fetch_openai_dict_format():
    response = _ok_response({"data": [{"id": "meta-llama/llama-3.1-8b"}, {"id": "mistral-7b"}]})
    with (
        patch.object(discovery, "get_provider_variable_value", side_effect=["http://localhost:8000", None]),
        patch.object(discovery, "ssrf_safe_httpx_get", return_value=response),
    ):
        result = discovery.fetch_live_vllm_models("user-id", "llm")
    assert {m["name"] for m in result} == {"meta-llama/llama-3.1-8b", "mistral-7b"}
    assert all(m["provider"] == "vLLM" and m["icon"] == "vLLM" for m in result)
    assert all(m["tool_calling"] for m in result)  # llm context -> tool calling on


def test_fetch_plain_list_format():
    response = _ok_response(["qwen2-7b", "deepseek-r1"])
    with (
        patch.object(discovery, "get_provider_variable_value", side_effect=["http://localhost:8000", None]),
        patch.object(discovery, "ssrf_safe_httpx_get", return_value=response),
    ):
        result = discovery.fetch_live_vllm_models("user-id", "llm")
    assert {m["name"] for m in result} == {"qwen2-7b", "deepseek-r1"}


def test_fetch_sorts_alphabetically():
    response = _ok_response({"data": [{"id": "zzz"}, {"id": "aaa"}, {"id": "mmm"}]})
    with (
        patch.object(discovery, "get_provider_variable_value", side_effect=["http://localhost:8000", None]),
        patch.object(discovery, "ssrf_safe_httpx_get", return_value=response),
    ):
        result = discovery.fetch_live_vllm_models("user-id", "llm")
    assert [m["name"] for m in result] == ["aaa", "mmm", "zzz"]


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("http://localhost:8000", "http://localhost:8000/v1/models"),
        ("http://localhost:8000/v1", "http://localhost:8000/v1/models"),
        ("http://localhost:8000/", "http://localhost:8000/v1/models"),
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
        patch.object(discovery, "ssrf_safe_httpx_get", side_effect=fake_get),
    ):
        discovery.fetch_live_vllm_models("user-id", "llm")
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
        patch.object(discovery, "ssrf_safe_httpx_get", side_effect=fake_get),
    ):
        discovery.fetch_live_vllm_models("user-id", "llm")
    assert captured[0].get("Authorization") == "Bearer secret-key"  # pragma: allowlist secret


def test_fetch_no_auth_header_when_no_key():
    response = _ok_response({"data": [{"id": "llama-3"}]})
    captured: list[dict] = []

    def fake_get(_url, headers=None, **_kwargs):
        captured.append(headers or {})
        return response

    with (
        patch.object(discovery, "get_provider_variable_value", side_effect=["http://localhost:8000", None]),
        patch.object(discovery, "ssrf_safe_httpx_get", side_effect=fake_get),
    ):
        discovery.fetch_live_vllm_models("user-id", "llm")
    assert "Authorization" not in captured[0]


def test_fetch_swallows_connection_error():
    with (
        patch.object(discovery, "get_provider_variable_value", side_effect=["http://localhost:8000", None]),
        patch.object(discovery, "ssrf_safe_httpx_get", side_effect=httpx.ConnectError("refused")),
    ):
        assert discovery.fetch_live_vllm_models("user-id", "llm") == []


def test_fetch_swallows_bad_payload():
    response = _ok_response({"unexpected": "shape"})
    with (
        patch.object(discovery, "get_provider_variable_value", side_effect=["http://localhost:8000", None]),
        patch.object(discovery, "ssrf_safe_httpx_get", return_value=response),
    ):
        assert discovery.fetch_live_vllm_models("user-id", "llm") == []


def test_fetch_embeddings_tagged_embeddings():
    response = _ok_response({"data": [{"id": "bge-m3"}]})
    with (
        patch.object(discovery, "get_provider_variable_value", side_effect=["http://localhost:8000", None]),
        patch.object(discovery, "ssrf_safe_httpx_get", return_value=response),
    ):
        result = discovery.fetch_live_vllm_models("user-id", "embeddings")
    assert result[0]["model_type"] == "embeddings"
    assert result[0]["tool_calling"] is False


# ---------------------------------------------------------------------------
# validate_vllm_credentials
# ---------------------------------------------------------------------------


def test_validate_raises_when_no_base_url():
    with pytest.raises(ValueError, match="Invalid vLLM API base URL"):
        discovery.validate_vllm_credentials("vLLM", {})


def test_validate_happy_path_uses_v1_models():
    response = _ok_response({"data": []})
    captured: list[str] = []

    def fake_get(url, **_kwargs):
        captured.append(url)
        return response

    with (
        patch.object(discovery, "ssrf_safe_httpx_get", side_effect=fake_get),
    ):
        discovery.validate_vllm_credentials("vLLM", {"VLLM_API_BASE": "http://localhost:8000/v1"})
    assert captured[0] == "http://localhost:8000/v1/models"


def test_validate_allows_literal_loopback_by_default(monkeypatch):
    _set_loopback_policy(monkeypatch, allowed=True)
    response = _ok_response({"data": []})

    with patch("httpx.Client.get", return_value=response) as mock_get:
        discovery.validate_vllm_credentials("vLLM", {"VLLM_API_BASE": "http://127.0.0.1:8000/v1"})

    mock_get.assert_called_once()
    assert mock_get.call_args.kwargs["url"] == "http://127.0.0.1:8000/v1/models"
    assert mock_get.call_args.kwargs["follow_redirects"] is False


def test_validate_blocks_literal_loopback_when_connector_policy_opts_out(monkeypatch):
    _set_loopback_policy(monkeypatch, allowed=False)

    with (
        patch("httpx.Client.get") as mock_get,
        pytest.raises(ValueError, match=r"127\.0\.0\.1.*blocked"),
    ):
        discovery.validate_vllm_credentials("vLLM", {"VLLM_API_BASE": "http://127.0.0.1:8000/v1"})

    mock_get.assert_not_called()


def test_validate_forwards_api_key():
    response = _ok_response({"data": []})
    captured: dict = {}

    def fake_get(_url, **kwargs):
        captured.update(kwargs)
        return response

    with (
        patch.object(discovery, "ssrf_safe_httpx_get", side_effect=fake_get),
    ):
        discovery.validate_vllm_credentials(
            "vLLM",
            {"VLLM_API_BASE": "http://localhost:8000", "VLLM_API_KEY": "k"},  # pragma: allowlist secret
        )
    assert captured["headers"]["Authorization"] == "Bearer k"  # pragma: allowlist secret


@pytest.mark.parametrize("status", [401, 403])
def test_validate_raises_on_auth_failure(status):
    response = MagicMock()
    response.status_code = status
    with (
        patch.object(discovery, "ssrf_safe_httpx_get", return_value=response),
        pytest.raises(ValueError, match="Authentication failed"),
    ):
        discovery.validate_vllm_credentials("vLLM", {"VLLM_API_BASE": "http://localhost:8000"})


def test_validate_raises_on_connection_error():
    with (
        patch.object(discovery, "ssrf_safe_httpx_get", side_effect=httpx.ConnectError("refused")),
        pytest.raises(ValueError, match="Could not connect to vLLM server"),
    ):
        discovery.validate_vllm_credentials("vLLM", {"VLLM_API_BASE": "http://localhost:8000"})


def test_validate_raises_on_timeout():
    with (
        patch.object(discovery, "ssrf_safe_httpx_get", side_effect=httpx.ReadTimeout("slow")),
        pytest.raises(ValueError, match="timed out"),
    ):
        discovery.validate_vllm_credentials("vLLM", {"VLLM_API_BASE": "http://localhost:8000"})


def test_validate_raises_value_error_on_server_error():
    request = httpx.Request("GET", "http://localhost:8000/v1/models")
    response = httpx.Response(500, request=request)
    error = httpx.HTTPStatusError("server error", request=request, response=response)

    with (
        patch.object(discovery, "ssrf_safe_httpx_get", side_effect=error),
        pytest.raises(ValueError, match="returned HTTP 500"),
    ):
        discovery.validate_vllm_credentials("vLLM", {"VLLM_API_BASE": "http://localhost:8000"})
