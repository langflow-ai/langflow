"""Unit tests for the OpenCode Go unified model provider.

OpenCode Go is an OpenAI-compatible endpoint that *requires* an
``x-opencode-session`` header (stable per conversation) and a client-specific
``User-Agent``. These tests pin the provider metadata, the live ``/models``
fetch, the header wiring in ``get_llm``, and API-key validation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def test_opencode_go_in_provider_registry():
    from lfx.base.models.model_metadata import LIVE_MODEL_PROVIDERS, MODEL_PROVIDER_METADATA

    assert "OpenCode Go" in MODEL_PROVIDER_METADATA
    assert "OpenCode Go" in LIVE_MODEL_PROVIDERS


def test_opencode_go_metadata_shape():
    from lfx.base.models.model_metadata import MODEL_PROVIDER_METADATA

    meta = MODEL_PROVIDER_METADATA["OpenCode Go"]
    assert meta["provider_id"] == "opencode-go"
    assert meta["base_url"] == "https://opencode.ai/zen/go/v1"
    assert meta["api_docs_url"] == "https://opencode.ai/docs/go/"
    assert meta["max_tokens_field_name"] == "max_tokens"
    assert meta["mapping"]["model_class"] == "ChatOpenAI"
    assert meta["mapping"]["model_param"] == "model"

    var_keys = {v["variable_key"] for v in meta["variables"]}
    assert var_keys == {"OPENCODE_GO_API_KEY"}

    api_key_var = meta["variables"][0]
    assert api_key_var["required"] is True
    assert api_key_var["is_secret"] is True
    assert api_key_var["langchain_param"] == "api_key"
    assert api_key_var["component_metadata"]["mapping_field"] == "api_key"


def test_opencode_go_declares_no_base_url_override():
    """The endpoint is fixed; a user-editable URL would need SSRF validation."""
    from lfx.base.models.model_metadata import MODEL_PROVIDER_METADATA

    meta = MODEL_PROVIDER_METADATA["OpenCode Go"]
    assert all(v.get("langchain_param") != "base_url" for v in meta["variables"])


def test_opencode_go_appears_in_get_model_providers():
    from lfx.base.models.unified_models import get_model_providers

    assert "OpenCode Go" in get_model_providers()


def test_opencode_go_param_mapping_resolves_to_chatopenai():
    from lfx.base.models.model_metadata import get_provider_param_mapping

    mapping = get_provider_param_mapping("OpenCode Go")
    assert mapping["model_class"] == "ChatOpenAI"
    assert mapping["api_key_param"] == "api_key"


def test_opencode_go_secret_variable_key():
    from lfx.base.models.unified_models import get_provider_secret_variable_key

    assert get_provider_secret_variable_key("OpenCode Go") == "OPENCODE_GO_API_KEY"


# ---------------------------------------------------------------------------
# Seed catalog
# ---------------------------------------------------------------------------


def test_opencode_go_seed_catalog_is_well_formed():
    from lfx.base.models.opencode_go_constants import OPENCODE_GO_MODELS_DETAILED

    assert OPENCODE_GO_MODELS_DETAILED, "seed list backs the pre-credential dropdown"
    for row in OPENCODE_GO_MODELS_DETAILED:
        assert row["provider"] == "OpenCode Go"
        assert isinstance(row["name"], str)
        assert row["name"]
        assert row["tool_calling"] is True


def test_opencode_go_seed_does_not_shadow_established_providers():
    """``get_provider_for_model_name`` returns the FIRST catalog hit.

    OpenCode Go model IDs are bare names (``claude-sonnet-5``, ``gpt-5.2``) that
    also exist in the Anthropic/OpenAI catalogs. Registering the seed last keeps
    those names resolving to their original providers, so flows saved before this
    provider existed keep working.
    """
    from lfx.base.models.anthropic_constants import ANTHROPIC_MODELS_DETAILED
    from lfx.base.models.openai_constants import OPENAI_MODELS_DETAILED
    from lfx.base.models.opencode_go_constants import OPENCODE_GO_MODELS_DETAILED
    from lfx.base.models.unified_models import get_provider_for_model_name

    established = {m["name"] for m in (*ANTHROPIC_MODELS_DETAILED, *OPENAI_MODELS_DETAILED)}
    for row in OPENCODE_GO_MODELS_DETAILED:
        if row["name"] in established:
            assert get_provider_for_model_name(row["name"]) != "OpenCode Go"


def test_opencode_go_resolves_to_langchain_openai():
    """Without the fallback entry a deployed flow ImportErrors on a bare lfx runner."""
    from lfx.utils.flow_requirements import _PROVIDER_PACKAGE_FALLBACKS

    assert _PROVIDER_PACKAGE_FALLBACKS["OpenCode Go"] == {"langchain-openai"}


# ---------------------------------------------------------------------------
# Live discovery
# ---------------------------------------------------------------------------


def _models_payload():
    return {
        "data": [
            {"id": "claude-sonnet-5", "created": 1730000000},
            {"id": "gpt-5.2", "created": 1731000000},
            {"id": "big-pickle"},
        ]
    }


def test_fetch_live_models_returns_catalog_rows():
    from lfx.base.models.model_utils import fetch_live_opencode_go_models

    response = MagicMock()
    response.json.return_value = _models_payload()
    response.raise_for_status.return_value = None

    with (
        patch("lfx.base.models.model_utils.get_provider_variable_value", return_value="sk-test"),
        patch("lfx.base.models.model_utils.httpx.get", return_value=response) as mock_get,
    ):
        models = fetch_live_opencode_go_models("user-1", "llm")

    url = mock_get.call_args[0][0]
    assert url == "https://opencode.ai/zen/go/v1/models"
    assert mock_get.call_args.kwargs["headers"]["Authorization"] == "Bearer sk-test"

    # Sorted by id, every row owned by OpenCode Go, tool_calling assumed True.
    assert [m["name"] for m in models] == ["big-pickle", "claude-sonnet-5", "gpt-5.2"]
    assert all(m["provider"] == "OpenCode Go" for m in models)
    assert all(m["tool_calling"] is True for m in models)
    # Missing "created" degrades to 0 rather than raising.
    assert next(m for m in models if m["name"] == "big-pickle")["created"] == 0


def test_fetch_live_models_marks_defaults():
    from lfx.base.models.model_utils import fetch_live_opencode_go_models
    from lfx.base.models.opencode_go_constants import OPENCODE_GO_MODELS_DETAILED

    response = MagicMock()
    response.json.return_value = _models_payload()
    response.raise_for_status.return_value = None

    with (
        patch("lfx.base.models.model_utils.get_provider_variable_value", return_value="sk-test"),
        patch("lfx.base.models.model_utils.httpx.get", return_value=response),
    ):
        models = fetch_live_opencode_go_models("user-1", "llm")

    # Seed IDs present in the live catalog become the default set. Derived from
    # the seed module (rather than hardcoded) so this test pins the intersection
    # *behaviour* and doesn't retroactively break when Task 5 rewrites the seed
    # list from the real endpoint.
    live_ids = {"claude-sonnet-5", "gpt-5.2", "big-pickle"}
    expected = {m["name"] for m in OPENCODE_GO_MODELS_DETAILED} & live_ids
    assert expected, "payload must overlap the seed for this test to be meaningful"

    defaults = {m["name"] for m in models if m["default"]}
    assert defaults == expected


def test_fetch_live_models_defaults_fall_back_when_seed_is_stale():
    """When the live catalog shares no ids with the seed, fall back to the first.

    ``MIN_DEFAULT_MODELS`` sorted ids instead of an empty default set.
    """
    from lfx.base.models.model_utils import MIN_DEFAULT_MODELS, fetch_live_opencode_go_models

    payload = {
        "data": [{"id": f"unseeded-model-{i}", "created": 1700000000 + i} for i in range(MIN_DEFAULT_MODELS + 2)]
    }
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None

    with (
        patch("lfx.base.models.model_utils.get_provider_variable_value", return_value="sk-test"),
        patch("lfx.base.models.model_utils.httpx.get", return_value=response),
    ):
        models = fetch_live_opencode_go_models("user-1", "llm")

    sorted_ids = sorted(m["id"] for m in payload["data"])
    expected_defaults = set(sorted_ids[:MIN_DEFAULT_MODELS])

    defaults = {m["name"] for m in models if m["default"]}
    assert defaults == expected_defaults


def test_fetch_live_models_without_api_key_returns_empty():
    from lfx.base.models.model_utils import fetch_live_opencode_go_models

    with patch("lfx.base.models.model_utils.get_provider_variable_value", return_value=None):
        assert fetch_live_opencode_go_models("user-1", "llm") == []


def test_fetch_live_models_ignores_embeddings():
    from lfx.base.models.model_utils import fetch_live_opencode_go_models

    assert fetch_live_opencode_go_models("user-1", "embeddings") == []


@pytest.mark.parametrize(
    "boom",
    [
        httpx.RequestError("boom"),
        httpx.HTTPStatusError("boom", request=MagicMock(), response=MagicMock(status_code=500)),
    ],
)
def test_fetch_live_models_degrades_on_transport_error(boom):
    from lfx.base.models.model_utils import fetch_live_opencode_go_models

    with (
        patch("lfx.base.models.model_utils.get_provider_variable_value", return_value="sk-test"),
        patch("lfx.base.models.model_utils.httpx.get", side_effect=boom),
    ):
        assert fetch_live_opencode_go_models("user-1", "llm") == []


def test_fetch_live_models_degrades_on_malformed_payload():
    from lfx.base.models.model_utils import fetch_live_opencode_go_models

    response = MagicMock()
    response.json.return_value = {"data": "not-a-list"}
    response.raise_for_status.return_value = None

    with (
        patch("lfx.base.models.model_utils.get_provider_variable_value", return_value="sk-test"),
        patch("lfx.base.models.model_utils.httpx.get", return_value=response),
    ):
        assert fetch_live_opencode_go_models("user-1", "llm") == []


def test_get_live_models_for_provider_dispatches_opencode_go():
    from lfx.base.models import model_utils

    with patch.object(model_utils, "fetch_live_opencode_go_models", return_value=[{"name": "x"}]) as mock_fetch:
        result = model_utils.get_live_models_for_provider("user-1", "OpenCode Go", "llm")

    mock_fetch.assert_called_once_with("user-1", "llm")
    assert result == [{"name": "x"}]
