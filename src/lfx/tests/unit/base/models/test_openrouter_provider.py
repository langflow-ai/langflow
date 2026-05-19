"""Unit tests for the OpenRouter unified model provider.

Covers:
  - Provider metadata registration (variables, mapping, live-fetch flag).
  - fetch_live_openrouter_models — mocks the OpenRouter /models endpoint and
    pins the per-model ``tool_calling`` flag, default-set intersection logic,
    and degradation paths for transport, status, and payload errors.
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


def test_openrouter_env_vars_registered_for_auto_import():
    """OPENROUTER_* env vars must be auto-imported as global variables.

    Without this, a user with the env vars set would not see the provider as
    configured in Settings → Model Providers (parity with OpenAI/Anthropic/etc.).
    """
    from lfx.services.settings.constants import VARIABLES_TO_GET_FROM_ENVIRONMENT

    for var in ("OPENROUTER_API_KEY", "OPENROUTER_SITE_URL", "OPENROUTER_APP_NAME"):
        assert var in VARIABLES_TO_GET_FROM_ENVIRONMENT


# ---------------------------------------------------------------------------
# Live model fetcher
# ---------------------------------------------------------------------------


def _models_payload(entries: list[dict]) -> MagicMock:
    """Build a fake httpx.Response carrying an OpenRouter /models payload.

    Each entry should look like ``{"id": "...", "supported_parameters": [...]}``.
    """
    response = MagicMock()
    response.json.return_value = {"data": entries}
    response.raise_for_status.return_value = None
    return response


def test_fetch_live_openrouter_models_returns_empty_for_embeddings():
    from lfx.base.models.model_utils import fetch_live_openrouter_models

    assert fetch_live_openrouter_models("user-id", "embeddings") == []


def test_fetch_live_openrouter_models_returns_empty_when_no_key():
    from lfx.base.models import model_utils

    with patch.object(model_utils, "get_provider_variable_value", return_value=None):
        assert model_utils.fetch_live_openrouter_models("user-id", "llm") == []


def test_fetch_live_openrouter_models_propagates_created_timestamp():
    """OpenRouter exposes ``created`` as a Unix epoch (seconds)."""
    from lfx.base.models import model_utils

    response = _models_payload(
        [
            {"id": "openai/gpt-4o", "supported_parameters": ["tools"], "created": 1715558400},
            {"id": "anthropic/claude-old", "supported_parameters": ["tools"], "created": 1700000000},
            {"id": "broken-time", "supported_parameters": ["tools"], "created": "not-a-number"},
            {"id": "no-time", "supported_parameters": ["tools"]},
        ]
    )
    with (
        patch.object(model_utils, "get_provider_variable_value", return_value="dummy-key"),  # pragma: allowlist secret
        patch.object(model_utils.httpx, "get", return_value=response),
    ):
        result = model_utils.fetch_live_openrouter_models("user-id", "llm")

    by_name = {m["name"]: m for m in result}
    assert by_name["openai/gpt-4o"]["created"] == 1715558400
    assert by_name["anthropic/claude-old"]["created"] == 1700000000
    assert by_name["broken-time"]["created"] == 0  # invalid value degrades safely
    assert by_name["no-time"]["created"] == 0


def test_fetch_live_openrouter_models_derives_tool_calling_and_reasoning_per_model():
    from lfx.base.models import model_utils

    response = _models_payload(
        [
            # tools + reasoning both present
            {"id": "anthropic/claude-opus", "supported_parameters": ["tools", "reasoning", "temperature"]},
            # tools only
            {"id": "openai/gpt-4o", "supported_parameters": ["tools"]},
            # reasoning only — e.g. older o1-style models
            {"id": "openai/o1-think", "supported_parameters": ["reasoning"]},
            # neither
            {"id": "perceptron/perceptron-mk1", "supported_parameters": ["temperature", "top_p"]},
            # missing supported_parameters → both False
            {"id": "broken-model"},
        ]
    )
    with (
        patch.object(model_utils, "get_provider_variable_value", return_value="dummy-key"),  # pragma: allowlist secret
        patch.object(model_utils.httpx, "get", return_value=response) as mock_get,
    ):
        result = model_utils.fetch_live_openrouter_models("user-id", "llm")

    mock_get.assert_called_once()
    call = mock_get.call_args
    assert call.args[0] == "https://openrouter.ai/api/v1/models"
    assert call.kwargs["headers"]["Authorization"].startswith("Bearer ")

    by_name = {m["name"]: m for m in result}

    assert by_name["anthropic/claude-opus"]["tool_calling"] is True
    assert by_name["anthropic/claude-opus"]["reasoning"] is True

    assert by_name["openai/gpt-4o"]["tool_calling"] is True
    assert by_name["openai/gpt-4o"]["reasoning"] is False

    assert by_name["openai/o1-think"]["tool_calling"] is False
    assert by_name["openai/o1-think"]["reasoning"] is True

    assert by_name["perceptron/perceptron-mk1"]["tool_calling"] is False
    assert by_name["perceptron/perceptron-mk1"]["reasoning"] is False

    assert by_name["broken-model"]["tool_calling"] is False
    assert by_name["broken-model"]["reasoning"] is False

    for entry in result:
        assert entry["provider"] == "OpenRouter"
        assert entry["icon"] == "OpenRouter"


def test_fetch_live_openrouter_models_defaults_intersect_with_seed_list():
    """Seed slugs in the live catalog drive the ``default`` flag.

    The curated seed list should win regardless of alphabetical ordering — seed
    slugs that happen to sort late (e.g. ``openai/...``) must still be marked
    default when present in the live catalog.
    """
    from lfx.base.models import model_utils
    from lfx.base.models.openrouter_constants import OPENROUTER_MODELS_DETAILED

    seed_names = [m["name"] for m in OPENROUTER_MODELS_DETAILED]
    # Two seed ids plus three non-seed ids. The seed ids may sort late
    # alphabetically (e.g. ``openai/...``), so alphabetical default-picking
    # would pick the non-seed ids first — this asserts we don't do that.
    live_entries = [
        {"id": "aaa/zzz-non-seed-1", "supported_parameters": ["tools"]},
        {"id": "aab/zzz-non-seed-2", "supported_parameters": []},
        {"id": "aac/zzz-non-seed-3", "supported_parameters": ["tools"]},
        {"id": seed_names[0], "supported_parameters": ["tools"]},
        {"id": seed_names[1], "supported_parameters": ["tools"]},
    ]
    response = _models_payload(live_entries)

    with (
        patch.object(model_utils, "get_provider_variable_value", return_value="dummy-key"),  # pragma: allowlist secret
        patch.object(model_utils.httpx, "get", return_value=response),
    ):
        result = model_utils.fetch_live_openrouter_models("user-id", "llm")

    defaults = {m["name"] for m in result if m.get("default")}
    assert defaults == {seed_names[0], seed_names[1]}


def test_fetch_live_openrouter_models_defaults_fall_back_when_no_seed_overlap():
    """No seed/live intersection falls back to the first MIN_DEFAULT_MODELS.

    Guards against the seed list going stale: if no seed slug appears in the
    live catalog, the first ``MIN_DEFAULT_MODELS`` (alphabetical) become the
    defaults so the UI is never devoid of suggestions.
    """
    from lfx.base.models import model_utils
    from lfx.base.models.model_utils import MIN_DEFAULT_MODELS

    live_ids = [f"vendor/model-{ch}" for ch in "abcdefghi"]  # 9 ids, none in seed list
    response = _models_payload([{"id": mid, "supported_parameters": ["tools"]} for mid in live_ids])

    with (
        patch.object(model_utils, "get_provider_variable_value", return_value="dummy-key"),  # pragma: allowlist secret
        patch.object(model_utils.httpx, "get", return_value=response),
    ):
        result = model_utils.fetch_live_openrouter_models("user-id", "llm")

    defaults = {m["name"] for m in result if m.get("default")}
    assert len(defaults) == MIN_DEFAULT_MODELS
    # The first MIN_DEFAULT_MODELS sorted alphabetically.
    assert defaults == set(sorted(live_ids)[:MIN_DEFAULT_MODELS])


def test_fetch_live_openrouter_models_swallows_request_error():
    from lfx.base.models import model_utils

    failing_get = MagicMock(side_effect=httpx.RequestError("network down"))
    with (
        patch.object(model_utils, "get_provider_variable_value", return_value="dummy-key"),  # pragma: allowlist secret
        patch.object(model_utils.httpx, "get", failing_get),
    ):
        assert model_utils.fetch_live_openrouter_models("user-id", "llm") == []


def test_fetch_live_openrouter_models_swallows_http_status_error():
    """A non-2xx response must degrade to ``[]``.

    For example a 503 from OpenRouter during a brownout must not crash the
    caller; the user sees an empty live catalog plus a warning log.
    """
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
        assert model_utils.fetch_live_openrouter_models("user-id", "llm") == []


def test_fetch_live_openrouter_models_swallows_malformed_payload():
    """A 200 response with a non-list ``data`` field must not raise."""
    from lfx.base.models import model_utils

    weird_response = MagicMock()
    weird_response.json.return_value = {"data": "not-a-list"}
    weird_response.raise_for_status.return_value = None
    with (
        patch.object(model_utils, "get_provider_variable_value", return_value="dummy-key"),  # pragma: allowlist secret
        patch.object(model_utils.httpx, "get", return_value=weird_response),
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


def test_validate_provider_uses_requested_model_name():
    """Dynamic catalog order must not change which model a toggle validates."""
    from types import SimpleNamespace

    from lfx.base.models.unified_models import validate_model_provider_key

    calls = []

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def invoke(self, _prompt):
            return "ok"

    catalog = [{"provider": "OpenAI", "models": [{"model_name": "gpt-5.5-pro"}]}]
    with (
        patch.dict("sys.modules", {"langchain_openai": SimpleNamespace(ChatOpenAI=FakeChatOpenAI)}),
        patch("lfx.base.models.unified_models.model_catalog.get_unified_models_detailed", return_value=catalog),
    ):
        validate_model_provider_key(
            "OpenAI",
            {"OPENAI_API_KEY": "dummy-openai-key"},  # pragma: allowlist secret
            model_name="gpt-4o-mini",
        )

    assert calls[0]["model_name"] == "gpt-4o-mini"


def test_validate_openrouter_happy_path():
    """Validation passes when ``GET /api/v1/auth/key`` returns 200.

    Patches ``requests.get`` on the actually-imported module (not via
    ``sys.modules``) so the test stays correct if the lazy import inside
    ``credentials.py`` is ever hoisted to module-level.
    """
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None

    with patch.object(requests, "get", return_value=response) as mock_get:
        validate_model_provider_key(
            "OpenRouter",
            {"OPENROUTER_API_KEY": "dummy-openrouter-key"},  # pragma: allowlist secret
        )

    mock_get.assert_called_once()
    call = mock_get.call_args
    # ``/api/v1/auth/key`` is auth-required (returns 401 on invalid bearer).
    # The previous ``/api/v1/models`` URL is a public endpoint that returns
    # 200 for any auth, so it could never detect an invalid key.
    assert call.args[0] == "https://openrouter.ai/api/v1/auth/key"
    assert call.kwargs["headers"]["Authorization"].startswith("Bearer ")


def test_validate_openrouter_raises_on_401():
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock()
    response.status_code = 401
    response.raise_for_status.side_effect = AssertionError("should not be called when 401 path triggers")

    with (
        patch.object(requests, "get", return_value=response),
        pytest.raises(ValueError, match="Invalid OpenRouter API key"),
    ):
        validate_model_provider_key(
            "OpenRouter",
            {"OPENROUTER_API_KEY": "dummy-openrouter-bad"},  # pragma: allowlist secret
        )


def test_validate_openrouter_uses_auth_endpoint_not_public_models_endpoint():
    """Regression: the validation endpoint must be auth-required.

    OpenRouter's ``/api/v1/models`` returns 200 regardless of the Authorization
    header (it is a public catalog). The previous implementation called that
    endpoint, so invalid keys were accepted silently and the credential save
    flow returned 201 instead of the documented 400. This test pins the URL to
    an auth-required endpoint so a future refactor cannot regress it.
    """
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None

    with patch.object(requests, "get", return_value=response) as mock_get:
        validate_model_provider_key(
            "OpenRouter",
            {"OPENROUTER_API_KEY": "dummy-openrouter-key"},  # pragma: allowlist secret
        )

    call_url = mock_get.call_args.args[0]
    assert call_url != "https://openrouter.ai/api/v1/models", (
        "OpenRouter /api/v1/models is public — using it for validation cannot detect invalid keys"
    )
    assert call_url.startswith("https://openrouter.ai/api/v1/")


def test_validate_openrouter_network_error_raises_value_error():
    """Transport errors must surface as ``ValueError``.

    The variable API only catches ``ValueError`` and returns a user-facing 400;
    any other exception escapes as an unhandled 500. A DNS / timeout / 5xx
    during validation must take that ValueError path.
    """
    from lfx.base.models.unified_models import validate_model_provider_key

    with (
        patch.object(requests, "get", side_effect=requests.ConnectionError("DNS lookup failed")),
        pytest.raises(ValueError, match="Could not reach OpenRouter"),
    ):
        validate_model_provider_key(
            "OpenRouter",
            {"OPENROUTER_API_KEY": "dummy-openrouter-key"},  # pragma: allowlist secret
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
        patch.object(
            unified_models_module, "get_api_key_for_provider", return_value="dummy-openrouter-key"
        ),  # pragma: allowlist secret
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
        patch.object(
            unified_models_module, "get_api_key_for_provider", return_value="dummy-openrouter-key"
        ),  # pragma: allowlist secret
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


def test_get_llm_for_openrouter_reads_attribution_headers_from_environment(monkeypatch):
    """Header vars resolve from os.environ when no global variable is stored.

    Mirrors the OpenAI / Ollama env-fallback pattern so a self-hosted operator
    can wire attribution via shell env without touching the database.
    """
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_llm

    monkeypatch.setenv("OPENROUTER_SITE_URL", "https://env.example.com")
    monkeypatch.setenv("OPENROUTER_APP_NAME", "EnvApp")

    captured_kwargs: dict = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    with (
        patch.object(
            unified_models_module, "get_api_key_for_provider", return_value="dummy-openrouter-key"
        ),  # pragma: allowlist secret
        patch.object(unified_models_module, "get_model_class", return_value=FakeChatOpenAI),
        patch.object(
            unified_models_module,
            "get_all_variables_for_provider",
            return_value={"OPENROUTER_API_KEY": "dummy-openrouter-key"},  # pragma: allowlist secret
        ),
    ):
        get_llm(_build_model_selection(), user_id=None)

    assert captured_kwargs["default_headers"] == {
        "HTTP-Referer": "https://env.example.com",
        "X-Title": "EnvApp",
    }
