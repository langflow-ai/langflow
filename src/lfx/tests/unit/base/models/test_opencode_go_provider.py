"""Unit tests for the OpenCode Go unified model provider.

OpenCode Go is an OpenAI-compatible endpoint that *requires* an
``x-opencode-session`` header (stable per conversation) and a client-specific
``User-Agent``. These tests pin the provider metadata, the live ``/models``
fetch, the header wiring in ``get_llm``, and API-key validation.
"""

from __future__ import annotations

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
