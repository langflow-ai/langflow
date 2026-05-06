"""Tests that the Langflow Model provider is registered in the three system-of-record places.

The unified models system has three places that must agree, or the provider is "half-registered"
and the UI shows confusing/broken state:

  1. provider_queries.get_models_detailed()        — drives the UI dropdown
  2. model_metadata.MODEL_PROVIDER_METADATA        — drives credentials/UI metadata
  3. class_registry._MODEL_CLASS_IMPORTS           — drives runtime instantiation

These tests guard against drift: if any one is updated without the others, a test breaks.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. provider_queries — the catalog the UI reads
# ---------------------------------------------------------------------------


class TestProviderQueriesIncludesLangflowLocal:
    def test_get_models_detailed_should_include_langflow_local_group(self):
        from lfx.base.models.langflow_local_constants import LANGFLOW_LOCAL_PROVIDER_NAME
        from lfx.base.models.unified_models.provider_queries import get_models_detailed

        groups = get_models_detailed()

        flat_providers = {model.get("provider") for group in groups for model in group}
        assert LANGFLOW_LOCAL_PROVIDER_NAME in flat_providers

    def test_default_model_should_be_marked_default_in_catalog(self):
        from lfx.base.models.langflow_local_constants import (
            LANGFLOW_LOCAL_DEFAULT_MODEL,
            LANGFLOW_LOCAL_PROVIDER_NAME,
        )
        from lfx.base.models.unified_models.provider_queries import get_models_detailed

        groups = get_models_detailed()
        all_models = [m for group in groups for m in group]
        default_entries = [
            m
            for m in all_models
            if m.get("provider") == LANGFLOW_LOCAL_PROVIDER_NAME and m.get("name") == LANGFLOW_LOCAL_DEFAULT_MODEL
        ]

        assert len(default_entries) == 1
        assert default_entries[0].get("default") is True

    def test_get_model_providers_should_list_langflow_local(self):
        from lfx.base.models.langflow_local_constants import LANGFLOW_LOCAL_PROVIDER_NAME
        from lfx.base.models.unified_models.provider_queries import get_model_providers

        providers = get_model_providers()

        assert LANGFLOW_LOCAL_PROVIDER_NAME in providers


# ---------------------------------------------------------------------------
# 2. model_metadata — credentials + provider config the UI reads
# ---------------------------------------------------------------------------


class TestModelProviderMetadataIncludesLangflowLocal:
    def test_metadata_should_have_entry_for_langflow_local(self):
        from lfx.base.models.langflow_local_constants import LANGFLOW_LOCAL_PROVIDER_NAME
        from lfx.base.models.model_metadata import MODEL_PROVIDER_METADATA

        assert LANGFLOW_LOCAL_PROVIDER_NAME in MODEL_PROVIDER_METADATA

    def test_metadata_entry_should_have_no_credentials(self):
        # Why: the WHOLE POINT of the Langflow Model provider is "no API key required".
        # If variables is non-empty, the credentials UI will appear and break the
        # zero-config promise.
        from lfx.base.models.langflow_local_constants import LANGFLOW_LOCAL_PROVIDER_NAME
        from lfx.base.models.model_metadata import MODEL_PROVIDER_METADATA

        entry = MODEL_PROVIDER_METADATA[LANGFLOW_LOCAL_PROVIDER_NAME]
        assert entry.get("variables") == []

    def test_metadata_entry_should_map_to_chat_langflow_local_class(self):
        from lfx.base.models.langflow_local_constants import LANGFLOW_LOCAL_PROVIDER_NAME
        from lfx.base.models.model_metadata import MODEL_PROVIDER_METADATA

        entry = MODEL_PROVIDER_METADATA[LANGFLOW_LOCAL_PROVIDER_NAME]
        assert entry["mapping"]["model_class"] == "ChatLangflowLocal"
        assert entry["mapping"]["model_param"] == "model"

    def test_metadata_entry_should_use_langflow_icon(self):
        from lfx.base.models.langflow_local_constants import LANGFLOW_LOCAL_PROVIDER_NAME
        from lfx.base.models.model_metadata import MODEL_PROVIDER_METADATA

        entry = MODEL_PROVIDER_METADATA[LANGFLOW_LOCAL_PROVIDER_NAME]
        assert entry["icon"] == "Langflow"


class TestLiveModelProvidersIncludesLangflowLocal:
    def test_langflow_local_should_be_in_live_providers(self):
        # Why: LIVE_MODEL_PROVIDERS marks providers that resolve their model list at
        # runtime (Ollama queries `/api/tags`). Langflow Model rides on Ollama under
        # the hood and benefits from the same dynamic discovery semantics.
        from lfx.base.models.langflow_local_constants import LANGFLOW_LOCAL_PROVIDER_NAME
        from lfx.base.models.model_metadata import LIVE_MODEL_PROVIDERS

        assert LANGFLOW_LOCAL_PROVIDER_NAME in LIVE_MODEL_PROVIDERS


# ---------------------------------------------------------------------------
# 3. class_registry — runtime instantiation lookup
# ---------------------------------------------------------------------------


class TestClassRegistryResolvesChatLangflowLocal:
    def test_get_model_class_should_resolve_chat_langflow_local(self):
        from lfx.base.models.langflow_local_model import ChatLangflowLocal
        from lfx.base.models.unified_models.class_registry import get_model_class

        resolved = get_model_class("ChatLangflowLocal")

        assert resolved is ChatLangflowLocal


# ---------------------------------------------------------------------------
# Cross-cutting: ordering — Langflow Model must appear FIRST
# ---------------------------------------------------------------------------


class TestLangflowLocalAppearsFirstInCatalog:
    def test_first_provider_in_catalog_should_be_langflow_local(self):
        # Why: provider order in the unified dropdown is the order in which groups
        # appear in get_models_detailed(). Putting Langflow Model first makes it the
        # natural default for new users.
        from lfx.base.models.langflow_local_constants import LANGFLOW_LOCAL_PROVIDER_NAME
        from lfx.base.models.unified_models.provider_queries import get_models_detailed

        groups = get_models_detailed()

        # First non-empty group should belong to Langflow Model
        first_non_empty = next(group for group in groups if group)
        assert first_non_empty[0]["provider"] == LANGFLOW_LOCAL_PROVIDER_NAME
