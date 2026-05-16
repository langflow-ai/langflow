"""Focused unit tests for the cache merge + dedup logic in ``get_and_cache_all_types_dict``.

The merge combines three sources -- built-in langflow components, custom-path
components, and extension-system components -- into a single
``component_cache.all_types_dict``.  The bundle walk registers extracted-bundle
components under their bare class names; the extension loader registers the
SAME components under namespaced IDs (``ext:<bundle>:<Class>@<slot>``).  Without
the dedup pass the frontend palette renders each bundle component twice.

These tests exercise the merge+dedup path directly with mocked sources, so
regressions in the bundle-match guard or the orphan-drop heuristic surface
without going through the full backend stack.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.interface.components import component_cache, get_and_cache_all_types_dict
from lfx.services.settings.service import SettingsService


@pytest.fixture(autouse=True)
def _reset_cache():
    component_cache.all_types_dict = None
    yield
    component_cache.all_types_dict = None


@pytest.fixture
def settings_service() -> MagicMock:
    svc = MagicMock(spec=SettingsService)
    svc.settings = MagicMock()
    svc.settings.lazy_load_components = False
    svc.settings.components_path = []
    return svc


def _patches(*, langflow: dict, custom: dict, extension: dict):
    """Three-source patch context for the cache builder.

    ``custom`` is mocked via ``_determine_loading_strategy`` rather than
    ``aget_all_types_dict`` because the strategy function short-circuits
    when ``components_path`` is empty (which is the case for our test
    settings fixture).
    """
    return (
        patch("lfx.interface.components.import_langflow_components", AsyncMock(return_value=langflow)),
        patch("lfx.interface.components._determine_loading_strategy", AsyncMock(return_value=custom)),
        patch("lfx.interface.components.import_extension_components", AsyncMock(return_value=extension)),
    )


class TestDeepMerge:
    """The three sources should be UNIONed, not overwrite each other per-category."""

    @pytest.mark.asyncio
    async def test_langflow_only(self, settings_service):
        langflow = {"components": {"chat": {"ChatInput": {"display_name": "Chat Input"}}}}
        with (
            _patches(langflow=langflow, custom={}, extension={})[0],
            _patches(langflow=langflow, custom={}, extension={})[1],
            _patches(langflow=langflow, custom={}, extension={})[2],
        ):
            result = await get_and_cache_all_types_dict(settings_service)
        assert "ChatInput" in result["chat"]

    @pytest.mark.asyncio
    async def test_custom_extends_langflow_category(self, settings_service):
        """Custom + langflow sharing a category should UNION (deep merge)."""
        langflow = {"components": {"chat": {"ChatInput": {"display_name": "Chat Input"}}}}
        custom = {"chat": {"MyCustomChat": {"display_name": "My Custom"}}}
        ps = _patches(langflow=langflow, custom=custom, extension={})
        with ps[0], ps[1], ps[2]:
            result = await get_and_cache_all_types_dict(settings_service)
        assert "ChatInput" in result["chat"]
        assert "MyCustomChat" in result["chat"]

    @pytest.mark.asyncio
    async def test_extension_only_no_twin_kept_with_display_name(self, settings_service):
        """An ext: entry with a real display_name and no bare twin should be preserved."""
        extension = {
            "myext": {
                "ext:myext:WidgetComponent@official": {
                    "display_name": "Widget",
                    "bundle": "myext",
                    "namespaced_id": "ext:myext:WidgetComponent@official",
                }
            }
        }
        ps = _patches(langflow={"components": {}}, custom={}, extension=extension)
        with ps[0], ps[1], ps[2]:
            result = await get_and_cache_all_types_dict(settings_service)
        # No bare twin exists so the dedup pass should leave the ext: key
        # alone (this is the "legacy custom-path bundle" exception).
        assert "ext:myext:WidgetComponent@official" in result["myext"]


class TestDedupClassNameMatch:
    """Dedup should rekey ext: -> bare name when class name matches (with Component suffix variants)."""

    @pytest.mark.asyncio
    async def test_exact_class_name_match(self, settings_service):
        langflow = {"components": {"openai": {"OpenAIModelComponent": {"display_name": "OpenAI"}}}}
        extension = {
            "openai": {
                "ext:openai:OpenAIModelComponent@official": {
                    "display_name": "OpenAI",
                    "bundle": "openai",
                    "namespaced_id": "ext:openai:OpenAIModelComponent@official",
                }
            }
        }
        ps = _patches(langflow=langflow, custom={}, extension=extension)
        with ps[0], ps[1], ps[2]:
            result = await get_and_cache_all_types_dict(settings_service)
        # ext: key dropped, bare retained, namespaced_id transplanted onto bare
        assert "ext:openai:OpenAIModelComponent@official" not in result["openai"]
        assert "OpenAIModelComponent" in result["openai"]
        assert result["openai"]["OpenAIModelComponent"]["namespaced_id"] == ("ext:openai:OpenAIModelComponent@official")

    @pytest.mark.asyncio
    async def test_component_suffix_stripped_match(self, settings_service):
        """``OpenAIModelComponent`` (in ext:) should match bare ``OpenAIModel`` (from obj.name)."""
        langflow = {"components": {"openai": {"OpenAIModel": {"display_name": "OpenAI"}}}}
        extension = {
            "openai": {
                "ext:openai:OpenAIModelComponent@official": {
                    "display_name": "OpenAI",
                    "bundle": "openai",
                    "namespaced_id": "ext:openai:OpenAIModelComponent@official",
                    "extension": "lfx-openai",
                    "extension_version": "1.0.0",
                }
            }
        }
        ps = _patches(langflow=langflow, custom={}, extension=extension)
        with ps[0], ps[1], ps[2]:
            result = await get_and_cache_all_types_dict(settings_service)
        assert "ext:openai:OpenAIModelComponent@official" not in result["openai"]
        assert "OpenAIModel" in result["openai"]
        bare = result["openai"]["OpenAIModel"]
        assert bare["namespaced_id"] == "ext:openai:OpenAIModelComponent@official"
        assert bare["bundle"] == "openai"
        assert bare["extension_version"] == "1.0.0"


class TestDedupDisplayNameFallback:
    """Dedup falls back to ``display_name`` when class names don't line up.

    Covers cases like class ``PineconeVectorStoreComponent`` registering
    under bare ``obj.name = "Pinecone"`` -- class-name matching alone
    misses the twin so we match by display_name.
    """

    @pytest.mark.asyncio
    async def test_display_name_fallback_matches(self, settings_service):
        langflow = {"components": {"pinecone": {"Pinecone": {"display_name": "Pinecone"}}}}
        extension = {
            "pinecone": {
                "ext:pinecone:PineconeVectorStoreComponent@official": {
                    "display_name": "Pinecone",
                    "bundle": "pinecone",
                    "namespaced_id": "ext:pinecone:PineconeVectorStoreComponent@official",
                }
            }
        }
        ps = _patches(langflow=langflow, custom={}, extension=extension)
        with ps[0], ps[1], ps[2]:
            result = await get_and_cache_all_types_dict(settings_service)
        assert "ext:pinecone:PineconeVectorStoreComponent@official" not in result["pinecone"]
        assert "Pinecone" in result["pinecone"]
        assert result["pinecone"]["Pinecone"]["namespaced_id"] == ("ext:pinecone:PineconeVectorStoreComponent@official")

    @pytest.mark.asyncio
    async def test_display_name_fallback_rejected_when_bundle_mismatch(self, settings_service):
        """The bundle-match guard prevents transplanting ext fields onto the wrong twin.

        Two bundles registering components under the same category with
        the same generic display_name must NOT be merged.
        """
        # Bare entry from bundle "alpha" with display_name "Embeddings"
        langflow = {
            "components": {
                "shared_category": {
                    "AlphaEmbeddings": {
                        "display_name": "Embeddings",
                        "bundle": "alpha",
                        "namespaced_id": "ext:alpha:AlphaEmbeddings@official",
                    }
                }
            }
        }
        # Ext: entry from a DIFFERENT bundle "beta" with the same display_name
        extension = {
            "shared_category": {
                "ext:beta:BetaEmbeddings@official": {
                    "display_name": "Embeddings",
                    "bundle": "beta",
                    "namespaced_id": "ext:beta:BetaEmbeddings@official",
                }
            }
        }
        ps = _patches(langflow=langflow, custom={}, extension=extension)
        with ps[0], ps[1], ps[2]:
            result = await get_and_cache_all_types_dict(settings_service)
        # The ext: key must NOT be transplanted onto AlphaEmbeddings (would
        # silently overwrite bundle-identity fields).  It survives as an
        # orphan ext: entry in the category.
        assert result["shared_category"]["AlphaEmbeddings"]["bundle"] == "alpha"
        assert result["shared_category"]["AlphaEmbeddings"]["namespaced_id"] == ("ext:alpha:AlphaEmbeddings@official")
        assert "ext:beta:BetaEmbeddings@official" in result["shared_category"]


class TestOrphanDrop:
    """Base classes that leak through ``import_extension_components`` should be dropped."""

    @pytest.mark.asyncio
    async def test_drop_orphan_with_falsy_display_name(self, settings_service):
        extension = {
            "agentics": {
                "ext:agentics:BaseAgenticComponent@official": {
                    "display_name": "",  # base class -- no real name
                    "bundle": "agentics",
                    "namespaced_id": "ext:agentics:BaseAgenticComponent@official",
                }
            }
        }
        ps = _patches(langflow={"components": {}}, custom={}, extension=extension)
        with ps[0], ps[1], ps[2]:
            result = await get_and_cache_all_types_dict(settings_service)
        assert "ext:agentics:BaseAgenticComponent@official" not in result.get("agentics", {})

    @pytest.mark.asyncio
    async def test_drop_orphan_with_default_component_display_name(self, settings_service):
        """Orphan-drop catches the serializer fallback that yields ``"Component"``.

        ``BaseAgenticComponent`` has ``display_name = False`` upstream
        but ``FrontendNode.process_display_name`` falls back to
        ``self.name``, which bottoms out at the literal ``"Component"``.
        """
        extension = {
            "agentics": {
                "ext:agentics:BaseAgenticComponent@official": {
                    "display_name": "Component",  # serializer fallback
                    "bundle": "agentics",
                    "namespaced_id": "ext:agentics:BaseAgenticComponent@official",
                }
            }
        }
        ps = _patches(langflow={"components": {}}, custom={}, extension=extension)
        with ps[0], ps[1], ps[2]:
            result = await get_and_cache_all_types_dict(settings_service)
        assert "ext:agentics:BaseAgenticComponent@official" not in result.get("agentics", {})

    @pytest.mark.asyncio
    async def test_drop_orphan_when_display_name_equals_class_name(self, settings_service):
        """Orphan-drop catches the serializer fallback that yields the class name.

        Variant of the above: upstream class set ``display_name = False``
        and ``name = "MyBaseThing"`` so the serializer returned
        ``"MyBaseThing"`` (matching the parsed class name from the ext key).
        """
        extension = {
            "ext_bundle": {
                "ext:ext_bundle:MyBase@official": {
                    "display_name": "MyBase",  # equals parsed class_name
                    "bundle": "ext_bundle",
                    "namespaced_id": "ext:ext_bundle:MyBase@official",
                }
            }
        }
        ps = _patches(langflow={"components": {}}, custom={}, extension=extension)
        with ps[0], ps[1], ps[2]:
            result = await get_and_cache_all_types_dict(settings_service)
        assert "ext:ext_bundle:MyBase@official" not in result.get("ext_bundle", {})


class TestCachePersistence:
    """The merge runs once; the second call returns the cached dict."""

    @pytest.mark.asyncio
    async def test_cache_is_reused(self, settings_service):
        langflow = {"components": {"chat": {"ChatInput": {"display_name": "Chat"}}}}
        ps = _patches(langflow=langflow, custom={}, extension={})
        with ps[0], ps[1], ps[2]:
            first = await get_and_cache_all_types_dict(settings_service)
            second = await get_and_cache_all_types_dict(settings_service)
        assert first is second
