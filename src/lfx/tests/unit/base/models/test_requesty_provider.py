"""Unit tests for the Requesty unified model provider.

Covers:
  - Provider metadata registration (variables, mapping, live-fetch flag).
  - fetch_live_requesty_models — mocks the Requesty /models endpoint and pins
    the per-model ``tool_calling``/``reasoning`` flags (derived from the flat
    ``supports_*`` booleans), default-set intersection logic, and degradation
    paths for transport, status, and payload errors.
  - validate_model_provider_key — success, 401, and transient-network paths.
  - get_llm — base_url + default_headers wiring (including env-var fallback).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
import requests

# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def test_requesty_in_provider_registry():
    from lfx.base.models.model_metadata import LIVE_MODEL_PROVIDERS, MODEL_PROVIDER_METADATA

    assert "Requesty" in MODEL_PROVIDER_METADATA
    assert "Requesty" in LIVE_MODEL_PROVIDERS


def test_requesty_metadata_shape():
    from lfx.base.models.model_metadata import MODEL_PROVIDER_METADATA

    meta = MODEL_PROVIDER_METADATA["Requesty"]
    assert meta["icon"] == "Requesty"
    assert meta["base_url"] == "https://router.requesty.ai/v1"
    assert meta["mapping"]["model_class"] == "ChatOpenAI"
    assert meta["mapping"]["model_param"] == "model"

    var_keys = {v["variable_key"] for v in meta["variables"]}
    assert var_keys == {"REQUESTY_API_KEY", "REQUESTY_SITE_URL", "REQUESTY_APP_NAME"}

    by_key = {v["variable_key"]: v for v in meta["variables"]}
    assert by_key["REQUESTY_API_KEY"]["required"] is True
    assert by_key["REQUESTY_API_KEY"]["is_secret"] is True
    assert by_key["REQUESTY_SITE_URL"]["required"] is False
    assert by_key["REQUESTY_SITE_URL"]["is_header"] is True
    assert by_key["REQUESTY_SITE_URL"]["header_name"] == "HTTP-Referer"
    assert by_key["REQUESTY_APP_NAME"]["header_name"] == "X-Title"


def test_requesty_appears_in_get_model_providers():
    from lfx.base.models.unified_models import get_model_providers

    assert "Requesty" in get_model_providers()


def test_requesty_param_mapping_resolves_to_chatopenai():
    from lfx.base.models.model_metadata import get_provider_param_mapping

    mapping = get_provider_param_mapping("Requesty")
    assert mapping["model_class"] == "ChatOpenAI"
    assert mapping["model_param"] == "model"
    assert mapping["api_key_param"] == "api_key"  # pragma: allowlist secret


def test_requesty_env_vars_registered_for_auto_import():
    """REQUESTY_* env vars must be auto-imported as global variables.

    Without this, a user with the env vars set would not see the provider as
    configured in Settings -> Model Providers (parity with OpenAI/OpenRouter/etc.).
    """
    from lfx.services.settings.constants import VARIABLES_TO_GET_FROM_ENVIRONMENT

    for var in ("REQUESTY_API_KEY", "REQUESTY_SITE_URL", "REQUESTY_APP_NAME"):
        assert var in VARIABLES_TO_GET_FROM_ENVIRONMENT


# ---------------------------------------------------------------------------
# Live model fetcher
# ---------------------------------------------------------------------------


def _models_payload(entries: list[dict]) -> MagicMock:
    """Build a fake httpx.Response carrying a Requesty /models payload.

    Requesty exposes capabilities as flat booleans (``supports_tool_calling`` /
    ``supports_reasoning``) rather than OpenRouter's ``supported_parameters``
    array, and the context size field is ``context_window``.
    """
    response = MagicMock()
    response.json.return_value = {"data": entries}
    response.raise_for_status.return_value = None
    return response


def test_fetch_live_requesty_models_returns_empty_for_embeddings():
    from lfx.base.models.model_utils import fetch_live_requesty_models

    assert fetch_live_requesty_models("user-id", "embeddings") == []


def test_fetch_live_requesty_models_returns_empty_when_no_key():
    from lfx.base.models import model_utils

    with patch.object(model_utils, "get_provider_variable_value", return_value=None):
        assert model_utils.fetch_live_requesty_models("user-id", "llm") == []


def test_fetch_live_requesty_models_derives_tool_calling_and_reasoning_per_model():
    from lfx.base.models import model_utils

    response = _models_payload(
        [
            {"id": "anthropic/claude-sonnet-4-5", "supports_tool_calling": True, "supports_reasoning": True},
            {"id": "openai/gpt-4o", "supports_tool_calling": True, "supports_reasoning": False},
            {"id": "openai/o1-think", "supports_tool_calling": False, "supports_reasoning": True},
            {"id": "vendor/plain", "supports_tool_calling": False, "supports_reasoning": False},
            {"id": "broken-model"},
        ]
    )
    with (
        patch.object(model_utils, "get_provider_variable_value", return_value="dummy-key"),  # pragma: allowlist secret
        patch.object(model_utils.httpx, "get", return_value=response) as mock_get,
    ):
        result = model_utils.fetch_live_requesty_models("user-id", "llm")

    mock_get.assert_called_once()
    call = mock_get.call_args
    assert call.args[0] == "https://router.requesty.ai/v1/models"
    assert call.kwargs["headers"]["Authorization"].startswith("Bearer ")

    by_name = {m["name"]: m for m in result}

    assert by_name["anthropic/claude-sonnet-4-5"]["tool_calling"] is True
    assert by_name["anthropic/claude-sonnet-4-5"]["reasoning"] is True

    assert by_name["openai/gpt-4o"]["tool_calling"] is True
    assert by_name["openai/gpt-4o"]["reasoning"] is False

    assert by_name["openai/o1-think"]["tool_calling"] is False
    assert by_name["openai/o1-think"]["reasoning"] is True

    assert by_name["vendor/plain"]["tool_calling"] is False
    assert by_name["vendor/plain"]["reasoning"] is False

    assert by_name["broken-model"]["tool_calling"] is False
    assert by_name["broken-model"]["reasoning"] is False

    for entry in result:
        assert entry["provider"] == "Requesty"
        assert entry["icon"] == "Requesty"


def test_fetch_live_requesty_models_defaults_intersect_with_seed_list():
    """Seed slugs present in the live catalog drive the ``default`` flag."""
    from lfx.base.models import model_utils
    from lfx.base.models.requesty_constants import REQUESTY_MODELS_DETAILED

    seed_names = [m["name"] for m in REQUESTY_MODELS_DETAILED]
    live_entries = [
        {"id": "aaa/zzz-non-seed-1", "supports_tool_calling": True},
        {"id": "aab/zzz-non-seed-2", "supports_tool_calling": False},
        {"id": "aac/zzz-non-seed-3", "supports_tool_calling": True},
        {"id": seed_names[0], "supports_tool_calling": True},
        {"id": seed_names[1], "supports_tool_calling": True},
    ]
    response = _models_payload(live_entries)

    with (
        patch.object(model_utils, "get_provider_variable_value", return_value="dummy-key"),  # pragma: allowlist secret
        patch.object(model_utils.httpx, "get", return_value=response),
    ):
        result = model_utils.fetch_live_requesty_models("user-id", "llm")

    defaults = {m["name"] for m in result if m.get("default")}
    assert defaults == {seed_names[0], seed_names[1]}


def test_fetch_live_requesty_models_defaults_fall_back_when_no_seed_overlap():
    """No seed/live intersection falls back to the first MIN_DEFAULT_MODELS."""
    from lfx.base.models import model_utils
    from lfx.base.models.model_utils import MIN_DEFAULT_MODELS

    live_ids = [f"vendor/model-{ch}" for ch in "abcdefghi"]  # 9 ids, none in seed list
    response = _models_payload([{"id": mid, "supports_tool_calling": True} for mid in live_ids])

    with (
        patch.object(model_utils, "get_provider_variable_value", return_value="dummy-key"),  # pragma: allowlist secret
        patch.object(model_utils.httpx, "get", return_value=response),
    ):
        result = model_utils.fetch_live_requesty_models("user-id", "llm")

    defaults = {m["name"] for m in result if m.get("default")}
    assert len(defaults) == MIN_DEFAULT_MODELS
    assert defaults == set(sorted(live_ids)[:MIN_DEFAULT_MODELS])


def test_fetch_live_requesty_models_swallows_request_error():
    from lfx.base.models import model_utils

    failing_get = MagicMock(side_effect=httpx.RequestError("network down"))
    with (
        patch.object(model_utils, "get_provider_variable_value", return_value="dummy-key"),  # pragma: allowlist secret
        patch.object(model_utils.httpx, "get", failing_get),
    ):
        assert model_utils.fetch_live_requesty_models("user-id", "llm") == []


def test_fetch_live_requesty_models_swallows_http_status_error():
    """A non-2xx response must degrade to ``[]`` (Requesty router 5xx brownout)."""
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
        assert model_utils.fetch_live_requesty_models("user-id", "llm") == []


def test_fetch_live_requesty_models_swallows_malformed_payload():
    """A 200 response with a non-list ``data`` field must not raise."""
    from lfx.base.models import model_utils

    weird_response = MagicMock()
    weird_response.json.return_value = {"data": "not-a-list"}
    weird_response.raise_for_status.return_value = None
    with (
        patch.object(model_utils, "get_provider_variable_value", return_value="dummy-key"),  # pragma: allowlist secret
        patch.object(model_utils.httpx, "get", return_value=weird_response),
    ):
        assert model_utils.fetch_live_requesty_models("user-id", "llm") == []


def test_get_live_models_dispatches_to_requesty():
    from lfx.base.models import model_utils

    with patch.object(model_utils, "fetch_live_requesty_models", return_value=[{"name": "x"}]) as mocked:
        result = model_utils.get_live_models_for_provider("user-id", "Requesty", "llm")
    mocked.assert_called_once_with("user-id", "llm")
    assert result == [{"name": "x"}]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_validate_requesty_no_key_returns_silently():
    from lfx.base.models.unified_models import validate_model_provider_key

    # No exception expected — empty key short-circuits without raising.
    validate_model_provider_key("Requesty", {})


def test_validate_requesty_happy_path():
    """Validation passes when the chat/completions probe returns 200."""
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None

    with patch.object(requests, "post", return_value=response) as mock_post:
        validate_model_provider_key(
            "Requesty",
            {"REQUESTY_API_KEY": "dummy-requesty-key"},  # pragma: allowlist secret
        )

    mock_post.assert_called_once()
    call = mock_post.call_args
    assert call.args[0] == "https://router.requesty.ai/v1/chat/completions"
    assert call.kwargs["headers"]["Authorization"].startswith("Bearer ")


def test_validate_requesty_raises_on_401():
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock()
    response.status_code = 401
    response.raise_for_status.side_effect = AssertionError("should not be called when 401 path triggers")

    with (
        patch.object(requests, "post", return_value=response),
        pytest.raises(ValueError, match="Invalid Requesty API key"),
    ):
        validate_model_provider_key(
            "Requesty",
            {"REQUESTY_API_KEY": "dummy-requesty-bad"},  # pragma: allowlist secret
        )


def test_validate_requesty_raises_on_403():
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock()
    response.status_code = 403
    response.raise_for_status.side_effect = AssertionError("should not be called when 403 path triggers")

    with (
        patch.object(requests, "post", return_value=response),
        pytest.raises(ValueError, match="Invalid Requesty API key"),
    ):
        validate_model_provider_key(
            "Requesty",
            {"REQUESTY_API_KEY": "dummy-requesty-bad"},  # pragma: allowlist secret
        )


def test_validate_requesty_network_error_raises_value_error():
    """Transport errors must surface as ``ValueError`` (variable API only catches that)."""
    from lfx.base.models.unified_models import validate_model_provider_key

    with (
        patch.object(requests, "post", side_effect=requests.ConnectionError("DNS lookup failed")),
        pytest.raises(ValueError, match="Could not reach Requesty"),
    ):
        validate_model_provider_key(
            "Requesty",
            {"REQUESTY_API_KEY": "dummy-requesty-key"},  # pragma: allowlist secret
        )


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------


def _build_model_selection(name: str = "openai/gpt-4o-mini") -> list[dict]:
    return [
        {
            "name": name,
            "provider": "Requesty",
            "metadata": {
                "model_class": "ChatOpenAI",
                "model_name_param": "model",
                "api_key_param": "api_key",  # pragma: allowlist secret
            },
        }
    ]


def test_get_llm_for_requesty_sets_base_url_and_headers():
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_llm

    captured_kwargs: dict = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    with (
        patch.object(
            unified_models_module, "get_api_key_for_provider", return_value="dummy-requesty-key"
        ),  # pragma: allowlist secret
        patch.object(unified_models_module, "get_model_class", return_value=FakeChatOpenAI),
        patch.object(
            unified_models_module,
            "get_all_variables_for_provider",
            return_value={
                "REQUESTY_API_KEY": "dummy-requesty-key",  # pragma: allowlist secret
                "REQUESTY_SITE_URL": "https://example.com",
                "REQUESTY_APP_NAME": "My App",
            },
        ),
    ):
        get_llm(_build_model_selection(), user_id=None)

    assert captured_kwargs["model"] == "openai/gpt-4o-mini"
    assert captured_kwargs["api_key"] == "dummy-requesty-key"  # pragma: allowlist secret
    assert captured_kwargs["base_url"] == "https://router.requesty.ai/v1"
    assert captured_kwargs["default_headers"] == {
        "HTTP-Referer": "https://example.com",
        "X-Title": "My App",
    }


def test_get_llm_for_requesty_omits_headers_when_not_configured():
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_llm

    captured_kwargs: dict = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    with (
        patch.object(
            unified_models_module, "get_api_key_for_provider", return_value="dummy-requesty-key"
        ),  # pragma: allowlist secret
        patch.object(unified_models_module, "get_model_class", return_value=FakeChatOpenAI),
        patch.object(
            unified_models_module,
            "get_all_variables_for_provider",
            return_value={"REQUESTY_API_KEY": "dummy-requesty-key"},  # pragma: allowlist secret
        ),
    ):
        get_llm(_build_model_selection(), user_id=None)

    assert captured_kwargs["base_url"] == "https://router.requesty.ai/v1"
    assert "default_headers" not in captured_kwargs
