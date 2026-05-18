"""Unit tests for the OpenRouter unified model provider.

Covers:
  - Provider metadata registration (variables, mapping, live-fetch flag).
  - fetch_live_openrouter_models — mocks the OpenRouter /models endpoint.
  - validate_model_provider_key — success and 401 paths.
  - get_llm — base_url and default_headers wiring for ChatOpenAI.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def test_openrouter_in_provider_registry():
    from lfx.base.models.model_metadata import LIVE_MODEL_PROVIDERS, MODEL_PROVIDER_METADATA

    assert "OpenRouter" in MODEL_PROVIDER_METADATA
    assert "OpenRouter" in LIVE_MODEL_PROVIDERS


def test_openrouter_metadata_shape():
    from lfx.base.models.model_metadata import MODEL_PROVIDER_METADATA

    meta = MODEL_PROVIDER_METADATA["OpenRouter"]
    assert meta["icon"] == "OpenRouter"
    assert meta["base_url"] == "https://openrouter.ai/api/v1"
    assert meta["mapping"]["model_class"] == "ChatOpenAI"
    assert meta["mapping"]["model_param"] == "model"

    var_keys = {v["variable_key"] for v in meta["variables"]}
    assert var_keys == {"OPENROUTER_API_KEY", "OPENROUTER_SITE_URL", "OPENROUTER_APP_NAME"}

    by_key = {v["variable_key"]: v for v in meta["variables"]}
    assert by_key["OPENROUTER_API_KEY"]["required"] is True
    assert by_key["OPENROUTER_API_KEY"]["is_secret"] is True
    assert by_key["OPENROUTER_SITE_URL"]["required"] is False
    assert by_key["OPENROUTER_SITE_URL"]["is_header"] is True
    assert by_key["OPENROUTER_SITE_URL"]["header_name"] == "HTTP-Referer"
    assert by_key["OPENROUTER_APP_NAME"]["header_name"] == "X-Title"


def test_openrouter_appears_in_get_model_providers():
    from lfx.base.models.unified_models import get_model_providers

    assert "OpenRouter" in get_model_providers()


def test_openrouter_param_mapping_resolves_to_chatopenai():
    from lfx.base.models.model_metadata import get_provider_param_mapping

    mapping = get_provider_param_mapping("OpenRouter")
    assert mapping["model_class"] == "ChatOpenAI"
    assert mapping["model_param"] == "model"
    assert mapping["api_key_param"] == "api_key"  # pragma: allowlist secret


# ---------------------------------------------------------------------------
# Live model fetcher
# ---------------------------------------------------------------------------


def _mock_models_response(model_ids: list[str]) -> MagicMock:
    response = MagicMock()
    response.json.return_value = {"data": [{"id": mid, "name": mid} for mid in model_ids]}
    response.raise_for_status.return_value = None
    return response


def test_fetch_live_openrouter_models_returns_empty_for_embeddings():
    from lfx.base.models.model_utils import fetch_live_openrouter_models

    assert fetch_live_openrouter_models("user-id", "embeddings") == []


def test_fetch_live_openrouter_models_returns_empty_when_no_key():
    from lfx.base.models import model_utils

    with patch.object(model_utils, "get_provider_variable_value", return_value=None):
        assert model_utils.fetch_live_openrouter_models("user-id", "llm") == []


def test_fetch_live_openrouter_models_happy_path():
    from lfx.base.models import model_utils

    response = _mock_models_response(
        ["anthropic/claude-3.5-sonnet", "openai/gpt-4o", "meta-llama/llama-3.1-70b-instruct"]
    )
    with (
        patch.object(model_utils, "get_provider_variable_value", return_value="dummy-openrouter-key"),
        patch.object(model_utils.httpx, "get", return_value=response) as mock_get,
    ):
        result = model_utils.fetch_live_openrouter_models("user-id", "llm")

    mock_get.assert_called_once()
    call_args = mock_get.call_args
    assert call_args.args[0] == "https://openrouter.ai/api/v1/models"
    assert call_args.kwargs["headers"]["Authorization"] == "Bearer dummy-openrouter-key"

    names = {m["name"] for m in result}
    assert names == {
        "anthropic/claude-3.5-sonnet",
        "openai/gpt-4o",
        "meta-llama/llama-3.1-70b-instruct",
    }
    for entry in result:
        assert entry["provider"] == "OpenRouter"
        assert entry["icon"] == "OpenRouter"
        assert entry["tool_calling"] is True

    defaults = [m for m in result if m.get("default")]
    assert len(defaults) == 3  # All 3 sample models within the first 5 marked defaults


def test_fetch_live_openrouter_models_swallows_http_error():
    import httpx
    from lfx.base.models import model_utils

    failing_get = MagicMock(side_effect=httpx.RequestError("network down"))
    with (
        patch.object(model_utils, "get_provider_variable_value", return_value="dummy-openrouter-key"),
        patch.object(model_utils.httpx, "get", failing_get),
    ):
        assert model_utils.fetch_live_openrouter_models("user-id", "llm") == []


def test_get_live_models_dispatches_to_openrouter():
    from lfx.base.models import model_utils

    with patch.object(model_utils, "fetch_live_openrouter_models", return_value=[{"name": "x"}]) as mocked:
        result = model_utils.get_live_models_for_provider("user-id", "OpenRouter", "llm")
    mocked.assert_called_once_with("user-id", "llm")
    assert result == [{"name": "x"}]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_validate_openrouter_no_key_returns_silently():
    from lfx.base.models.unified_models import validate_model_provider_key

    # No exception expected — empty key short-circuits without raising.
    validate_model_provider_key("OpenRouter", {})


def test_validate_openrouter_happy_path():
    from lfx.base.models.unified_models import credentials, validate_model_provider_key

    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None

    fake_requests = MagicMock()
    fake_requests.get.return_value = response

    with patch.dict("sys.modules", {"requests": fake_requests}):
        validate_model_provider_key(
            "OpenRouter",
            {"OPENROUTER_API_KEY": "dummy-openrouter-key"},  # pragma: allowlist secret
        )

    fake_requests.get.assert_called_once()
    call_args = fake_requests.get.call_args
    assert call_args.args[0] == "https://openrouter.ai/api/v1/models"
    assert call_args.kwargs["headers"]["Authorization"] == "Bearer dummy-openrouter-key"
    _ = credentials  # keep import warm for coverage


def test_validate_openrouter_raises_on_401():
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock()
    response.status_code = 401
    response.raise_for_status.side_effect = AssertionError("should not be called when 401 path triggers")

    fake_requests = MagicMock()
    fake_requests.get.return_value = response

    with (
        patch.dict("sys.modules", {"requests": fake_requests}),
        pytest.raises(ValueError, match="Invalid OpenRouter API key"),
    ):
        validate_model_provider_key(
            "OpenRouter",
            {"OPENROUTER_API_KEY": "dummy-openrouter-bad"},  # pragma: allowlist secret
        )


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------


def _build_model_selection(name: str = "anthropic/claude-3.5-sonnet") -> list[dict]:
    return [
        {
            "name": name,
            "provider": "OpenRouter",
            "metadata": {
                "model_class": "ChatOpenAI",
                "model_name_param": "model",
                "api_key_param": "api_key",  # pragma: allowlist secret
            },
        }
    ]


def test_get_llm_for_openrouter_sets_base_url_and_headers():
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_llm

    captured_kwargs: dict = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    with (
        patch.object(unified_models_module, "get_api_key_for_provider", return_value="dummy-openrouter-key"),
        patch.object(unified_models_module, "get_model_class", return_value=FakeChatOpenAI),
        patch.object(
            unified_models_module,
            "get_all_variables_for_provider",
            return_value={
                "OPENROUTER_API_KEY": "dummy-openrouter-key",  # pragma: allowlist secret
                "OPENROUTER_SITE_URL": "https://example.com",
                "OPENROUTER_APP_NAME": "My App",
            },
        ),
    ):
        get_llm(_build_model_selection(), user_id=None)

    assert captured_kwargs["model"] == "anthropic/claude-3.5-sonnet"
    assert captured_kwargs["api_key"] == "dummy-openrouter-key"  # pragma: allowlist secret
    assert captured_kwargs["base_url"] == "https://openrouter.ai/api/v1"
    assert captured_kwargs["default_headers"] == {
        "HTTP-Referer": "https://example.com",
        "X-Title": "My App",
    }


def test_get_llm_for_openrouter_omits_headers_when_not_configured():
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_llm

    captured_kwargs: dict = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    with (
        patch.object(unified_models_module, "get_api_key_for_provider", return_value="dummy-openrouter-key"),
        patch.object(unified_models_module, "get_model_class", return_value=FakeChatOpenAI),
        patch.object(
            unified_models_module,
            "get_all_variables_for_provider",
            return_value={"OPENROUTER_API_KEY": "dummy-openrouter-key"},  # pragma: allowlist secret
        ),
    ):
        get_llm(_build_model_selection(), user_id=None)

    assert captured_kwargs["base_url"] == "https://openrouter.ai/api/v1"
    assert "default_headers" not in captured_kwargs
