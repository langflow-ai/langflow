"""Unit tests for the OrcaRouter unified model provider.

Covers:
  - Provider metadata registration (variables, mapping, live-fetch flag).
  - fetch_live_orcarouter_models -- mocks the OrcaRouter /models endpoint,
    the per-model ``tool_calling``/``reasoning`` derivation, the pinned
    ``orcarouter/auto`` router, and degradation paths for transport, status,
    and payload errors.
  - validate_model_provider_key -- success, 401, and transient-network paths.
  - get_llm -- base_url + default_headers wiring (including env-var fallback).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
import requests

# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def test_orcarouter_in_provider_registry():
    from lfx.base.models.model_metadata import LIVE_MODEL_PROVIDERS, MODEL_PROVIDER_METADATA

    assert "OrcaRouter" in MODEL_PROVIDER_METADATA
    assert "OrcaRouter" in LIVE_MODEL_PROVIDERS


def test_orcarouter_metadata_shape():
    from lfx.base.models.model_metadata import MODEL_PROVIDER_METADATA

    meta = MODEL_PROVIDER_METADATA["OrcaRouter"]
    assert meta["icon"] == "OrcaRouter"
    assert meta["base_url"] == "https://api.orcarouter.ai/v1"
    assert meta["mapping"]["model_class"] == "ChatOpenAI"
    assert meta["mapping"]["model_param"] == "model"

    var_keys = {v["variable_key"] for v in meta["variables"]}
    assert var_keys == {"ORCAROUTER_API_KEY", "ORCAROUTER_SITE_URL", "ORCAROUTER_APP_NAME"}

    by_key = {v["variable_key"]: v for v in meta["variables"]}
    assert by_key["ORCAROUTER_API_KEY"]["required"] is True
    assert by_key["ORCAROUTER_API_KEY"]["is_secret"] is True
    assert by_key["ORCAROUTER_SITE_URL"]["required"] is False
    assert by_key["ORCAROUTER_SITE_URL"]["is_header"] is True
    assert by_key["ORCAROUTER_SITE_URL"]["header_name"] == "HTTP-Referer"
    assert by_key["ORCAROUTER_APP_NAME"]["header_name"] == "X-Title"


def test_orcarouter_appears_in_get_model_providers():
    from lfx.base.models.unified_models import get_model_providers

    assert "OrcaRouter" in get_model_providers()


def test_orcarouter_param_mapping_resolves_to_chatopenai():
    from lfx.base.models.model_metadata import get_provider_param_mapping

    mapping = get_provider_param_mapping("OrcaRouter")
    assert mapping["model_class"] == "ChatOpenAI"
    assert mapping["model_param"] == "model"
    assert mapping["api_key_param"] == "api_key"  # pragma: allowlist secret


def test_orcarouter_env_vars_registered_for_auto_import():
    """ORCAROUTER_* env vars must be auto-imported as global variables."""
    from lfx.services.settings.constants import VARIABLES_TO_GET_FROM_ENVIRONMENT

    for var in ("ORCAROUTER_API_KEY", "ORCAROUTER_SITE_URL", "ORCAROUTER_APP_NAME"):
        assert var in VARIABLES_TO_GET_FROM_ENVIRONMENT


def test_orcarouter_seed_pins_auto_router():
    """The seed catalog leads with the ``orcarouter/auto`` adaptive router."""
    from lfx.base.models.orcarouter_constants import ORCAROUTER_MODELS_DETAILED

    names = [m["name"] for m in ORCAROUTER_MODELS_DETAILED]
    assert names[0] == "orcarouter/auto"
    assert all(m["provider"] == "OrcaRouter" and m["icon"] == "OrcaRouter" for m in ORCAROUTER_MODELS_DETAILED)


# ---------------------------------------------------------------------------
# Live model fetcher
# ---------------------------------------------------------------------------


def _models_payload(entries: list[dict]) -> MagicMock:
    """Build a fake httpx.Response carrying an OrcaRouter /models payload."""
    response = MagicMock()
    response.json.return_value = {"data": entries}
    response.raise_for_status.return_value = None
    return response


def test_fetch_live_orcarouter_models_returns_empty_for_embeddings():
    from lfx.base.models.model_utils import fetch_live_orcarouter_models

    assert fetch_live_orcarouter_models("user-id", "embeddings") == []


def test_fetch_live_orcarouter_models_fetches_without_key():
    """/v1/models is public, so the catalog loads even without a configured key."""
    from lfx.base.models import model_utils

    response = _models_payload([{"id": "openai/gpt-5.5", "supported_parameters": ["tools"]}])
    with (
        patch.object(model_utils, "get_provider_variable_value", return_value=None),
        patch.object(model_utils.httpx, "get", return_value=response) as mock_get,
    ):
        result = model_utils.fetch_live_orcarouter_models("user-id", "llm")

    names = [m["name"] for m in result]
    # Unauthenticated fetch still returns the live catalog...
    assert "openai/gpt-5.5" in names
    # ...and pins the adaptive router.
    assert "orcarouter/auto" in names
    # No Authorization header when no key is configured.
    assert "Authorization" not in mock_get.call_args.kwargs.get("headers", {})


def test_fetch_live_orcarouter_models_pins_auto_router_first_as_default():
    """``orcarouter/auto`` is not in /v1/models, so it is pinned first + default."""
    from lfx.base.models import model_utils

    response = _models_payload(
        [
            {"id": "openai/gpt-5.5", "supported_parameters": ["tools"]},
            {"id": "anthropic/claude-opus-4.8", "supported_parameters": ["tools"]},
        ]
    )
    with (
        patch.object(model_utils, "get_provider_variable_value", return_value="dummy-key"),  # pragma: allowlist secret
        patch.object(model_utils.httpx, "get", return_value=response),
    ):
        result = model_utils.fetch_live_orcarouter_models("user-id", "llm")

    names = [m["name"] for m in result]
    assert "orcarouter/auto" in names
    assert names[0] == "orcarouter/auto"
    auto = next(m for m in result if m["name"] == "orcarouter/auto")
    assert auto["default"] is True


def test_fetch_live_orcarouter_models_forwards_key_and_hits_models_endpoint():
    from lfx.base.models import model_utils

    response = _models_payload([{"id": "openai/gpt-5.5", "supported_parameters": ["tools"]}])
    with (
        patch.object(model_utils, "get_provider_variable_value", return_value="dummy-key"),  # pragma: allowlist secret
        patch.object(model_utils.httpx, "get", return_value=response) as mock_get,
    ):
        model_utils.fetch_live_orcarouter_models("user-id", "llm")

    call = mock_get.call_args
    assert call.args[0] == "https://api.orcarouter.ai/v1/models"
    assert call.kwargs["headers"]["Authorization"].startswith("Bearer ")


def test_fetch_live_orcarouter_models_derives_tool_calling_and_reasoning_per_model():
    """OrcaRouter assumes tool support unless supported_parameters is enumerated."""
    from lfx.base.models import model_utils

    response = _models_payload(
        [
            {"id": "vendor/tools-reasoning", "supported_parameters": ["tools", "reasoning", "temperature"]},
            {"id": "vendor/tools-only", "supported_parameters": ["tools"]},
            {"id": "vendor/reasoning-only", "supported_parameters": ["reasoning"]},
            {"id": "vendor/neither", "supported_parameters": ["temperature", "top_p"]},
            {"id": "vendor/no-params"},  # missing -> assume tool support, no reasoning
            {"id": "vendor/empty-params", "supported_parameters": []},  # empty -> assume tool support
        ]
    )
    with (
        patch.object(model_utils, "get_provider_variable_value", return_value="dummy-key"),  # pragma: allowlist secret
        patch.object(model_utils.httpx, "get", return_value=response),
    ):
        result = model_utils.fetch_live_orcarouter_models("user-id", "llm")

    by_name = {m["name"]: m for m in result}

    assert by_name["vendor/tools-reasoning"]["tool_calling"] is True
    assert by_name["vendor/tools-reasoning"]["reasoning"] is True

    assert by_name["vendor/tools-only"]["tool_calling"] is True
    assert by_name["vendor/tools-only"]["reasoning"] is False

    assert by_name["vendor/reasoning-only"]["tool_calling"] is False
    assert by_name["vendor/reasoning-only"]["reasoning"] is True

    assert by_name["vendor/neither"]["tool_calling"] is False
    assert by_name["vendor/neither"]["reasoning"] is False

    assert by_name["vendor/no-params"]["tool_calling"] is True
    assert by_name["vendor/no-params"]["reasoning"] is False

    assert by_name["vendor/empty-params"]["tool_calling"] is True
    assert by_name["vendor/empty-params"]["reasoning"] is False

    for entry in result:
        assert entry["provider"] == "OrcaRouter"
        assert entry["icon"] == "OrcaRouter"


def test_fetch_live_orcarouter_models_propagates_created_timestamp():
    from lfx.base.models import model_utils

    response = _models_payload(
        [
            {"id": "openai/gpt-5.5", "supported_parameters": ["tools"], "created": 1715558400},
            {"id": "vendor/broken-time", "supported_parameters": ["tools"], "created": "not-a-number"},
            {"id": "vendor/no-time", "supported_parameters": ["tools"]},
        ]
    )
    with (
        patch.object(model_utils, "get_provider_variable_value", return_value="dummy-key"),  # pragma: allowlist secret
        patch.object(model_utils.httpx, "get", return_value=response),
    ):
        result = model_utils.fetch_live_orcarouter_models("user-id", "llm")

    by_name = {m["name"]: m for m in result}
    assert by_name["openai/gpt-5.5"]["created"] == 1715558400
    assert by_name["vendor/broken-time"]["created"] == 0  # invalid value degrades safely
    assert by_name["vendor/no-time"]["created"] == 0


def test_fetch_live_orcarouter_models_swallows_request_error():
    from lfx.base.models import model_utils

    failing_get = MagicMock(side_effect=httpx.RequestError("network down"))
    with (
        patch.object(model_utils, "get_provider_variable_value", return_value="dummy-key"),  # pragma: allowlist secret
        patch.object(model_utils.httpx, "get", failing_get),
    ):
        assert model_utils.fetch_live_orcarouter_models("user-id", "llm") == []


def test_fetch_live_orcarouter_models_swallows_http_status_error():
    from lfx.base.models import model_utils

    bad_response = MagicMock()
    bad_response.status_code = 503
    bad_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "service unavailable", request=MagicMock(), response=bad_response
    )
    with (
        patch.object(model_utils, "get_provider_variable_value", return_value="dummy-key"),  # pragma: allowlist secret
        patch.object(model_utils.httpx, "get", return_value=bad_response),
    ):
        assert model_utils.fetch_live_orcarouter_models("user-id", "llm") == []


def test_fetch_live_orcarouter_models_swallows_malformed_payload():
    from lfx.base.models import model_utils

    weird_response = MagicMock()
    weird_response.json.return_value = {"data": "not-a-list"}
    weird_response.raise_for_status.return_value = None
    with (
        patch.object(model_utils, "get_provider_variable_value", return_value="dummy-key"),  # pragma: allowlist secret
        patch.object(model_utils.httpx, "get", return_value=weird_response),
    ):
        assert model_utils.fetch_live_orcarouter_models("user-id", "llm") == []


def test_get_live_models_dispatches_to_orcarouter():
    from lfx.base.models import model_utils

    with patch.object(model_utils, "fetch_live_orcarouter_models", return_value=[{"name": "x"}]) as mocked:
        result = model_utils.get_live_models_for_provider("user-id", "OrcaRouter", "llm")
    mocked.assert_called_once_with("user-id", "llm")
    assert result == [{"name": "x"}]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_validate_orcarouter_no_key_returns_silently():
    from lfx.base.models.unified_models import validate_model_provider_key

    validate_model_provider_key("OrcaRouter", {})


def test_validate_orcarouter_happy_path():
    """Validation passes when GET /v1/models returns 200."""
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None

    with patch.object(requests, "get", return_value=response) as mock_get:
        validate_model_provider_key(
            "OrcaRouter",
            {"ORCAROUTER_API_KEY": "dummy-orcarouter-key"},  # pragma: allowlist secret
        )

    mock_get.assert_called_once()
    call = mock_get.call_args
    assert call.args[0] == "https://api.orcarouter.ai/v1/models"
    assert call.kwargs["headers"]["Authorization"].startswith("Bearer ")


def test_validate_orcarouter_raises_on_401():
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock()
    response.status_code = 401
    response.raise_for_status.side_effect = AssertionError("should not be called when 401 path triggers")

    with (
        patch.object(requests, "get", return_value=response),
        pytest.raises(ValueError, match="Invalid OrcaRouter API key"),
    ):
        validate_model_provider_key(
            "OrcaRouter",
            {"ORCAROUTER_API_KEY": "dummy-orcarouter-bad"},  # pragma: allowlist secret
        )


def test_validate_orcarouter_network_error_raises_value_error():
    from lfx.base.models.unified_models import validate_model_provider_key

    with (
        patch.object(requests, "get", side_effect=requests.ConnectionError("DNS lookup failed")),
        pytest.raises(ValueError, match="Could not reach OrcaRouter"),
    ):
        validate_model_provider_key(
            "OrcaRouter",
            {"ORCAROUTER_API_KEY": "dummy-orcarouter-key"},  # pragma: allowlist secret
        )


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------


def _build_model_selection(name: str = "openai/gpt-5.5") -> list[dict]:
    return [
        {
            "name": name,
            "provider": "OrcaRouter",
            "metadata": {
                "model_class": "ChatOpenAI",
                "model_name_param": "model",
                "api_key_param": "api_key",  # pragma: allowlist secret
            },
        }
    ]


def test_get_llm_for_orcarouter_sets_base_url_and_headers():
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_llm

    captured_kwargs: dict = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    with (
        patch.object(
            unified_models_module, "get_api_key_for_provider", return_value="dummy-orcarouter-key"
        ),  # pragma: allowlist secret
        patch.object(unified_models_module, "get_model_class", return_value=FakeChatOpenAI),
        patch.object(
            unified_models_module,
            "get_all_variables_for_provider",
            return_value={
                "ORCAROUTER_API_KEY": "dummy-orcarouter-key",  # pragma: allowlist secret
                "ORCAROUTER_SITE_URL": "https://example.com",
                "ORCAROUTER_APP_NAME": "My App",
            },
        ),
    ):
        get_llm(_build_model_selection(), user_id=None)

    assert captured_kwargs["model"] == "openai/gpt-5.5"
    assert captured_kwargs["api_key"] == "dummy-orcarouter-key"  # pragma: allowlist secret
    assert captured_kwargs["base_url"] == "https://api.orcarouter.ai/v1"
    assert captured_kwargs["default_headers"] == {
        "HTTP-Referer": "https://example.com",
        "X-Title": "My App",
    }


def test_get_llm_for_orcarouter_omits_headers_when_not_configured():
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_llm

    captured_kwargs: dict = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    with (
        patch.object(
            unified_models_module, "get_api_key_for_provider", return_value="dummy-orcarouter-key"
        ),  # pragma: allowlist secret
        patch.object(unified_models_module, "get_model_class", return_value=FakeChatOpenAI),
        patch.object(
            unified_models_module,
            "get_all_variables_for_provider",
            return_value={"ORCAROUTER_API_KEY": "dummy-orcarouter-key"},  # pragma: allowlist secret
        ),
    ):
        get_llm(_build_model_selection(), user_id=None)

    assert captured_kwargs["base_url"] == "https://api.orcarouter.ai/v1"
    assert "default_headers" not in captured_kwargs


def test_get_llm_for_orcarouter_reads_attribution_headers_from_environment(monkeypatch):
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_llm

    monkeypatch.setenv("ORCAROUTER_SITE_URL", "https://env.example.com")
    monkeypatch.setenv("ORCAROUTER_APP_NAME", "EnvApp")

    captured_kwargs: dict = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    with (
        patch.object(
            unified_models_module, "get_api_key_for_provider", return_value="dummy-orcarouter-key"
        ),  # pragma: allowlist secret
        patch.object(unified_models_module, "get_model_class", return_value=FakeChatOpenAI),
        patch.object(
            unified_models_module,
            "get_all_variables_for_provider",
            return_value={"ORCAROUTER_API_KEY": "dummy-orcarouter-key"},  # pragma: allowlist secret
        ),
    ):
        get_llm(_build_model_selection(), user_id=None)

    assert captured_kwargs["default_headers"] == {
        "HTTP-Referer": "https://env.example.com",
        "X-Title": "EnvApp",
    }
