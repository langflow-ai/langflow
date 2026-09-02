"""Lazy component loading must not damage the built-in registry.

``LANGFLOW_LAZY_LOAD_COMPONENTS=true`` combined with
``LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false`` blocked every flow in the product, reporting
first-party built-ins as custom components::

    Flow build blocked: custom components are not allowed: Chat Input (ChatInput-b6UCc), ...

Two defects combined:

1. ``_determine_loading_strategy`` filtered ``BASE_COMPONENTS_PATH`` out of the full-loading
   branch but not the lazy branch, so lazy mode rescanned the *built-in* component directory
   and produced metadata-only stubs keyed by directory and file name.
2. The cache initializer merged those results per CATEGORY (``{**builtin, **custom}``), so a
   category present in both -- "tools", "embeddings", "utilities" -- had its entire built-in
   contents replaced rather than supplemented.

The built-in components then had no registered hash, so ``check_flow_and_raise`` rejected
them. It only surfaced with the gate on, because that check returns early when custom
components are allowed.
"""

from typing import Any

from lfx.interface.components import (
    BASE_COMPONENTS_PATH,
    _determine_loading_strategy,
    _merge_component_sources,
)


class _Settings:
    def __init__(self, *, lazy: bool, components_path: list[str]):
        self.lazy_load_components = lazy
        self.components_path = components_path


class _SettingsService:
    def __init__(self, settings: _Settings):
        self.settings = settings


def _flatten(result: dict[str, Any]) -> dict[str, Any]:
    return result.get("components", result) or {}


class TestLazyLoadingSkipsTheBuiltInPath:
    """Both branches load *custom* components; built-ins come from the prebuilt index."""

    async def test_lazy_branch_does_not_rescan_the_built_in_directory(self):
        service = _SettingsService(_Settings(lazy=True, components_path=[BASE_COMPONENTS_PATH]))

        result = _flatten(await _determine_loading_strategy(service))

        assert result == {}, (
            "lazy loading rescanned BASE_COMPONENTS_PATH; its metadata-only stubs overwrite the "
            f"built-ins loaded from the index (got {len(result)} categories)"
        )

    async def test_full_branch_does_not_rescan_the_built_in_directory(self):
        """The behaviour the lazy branch was missing -- pinned so the pair cannot drift apart."""
        service = _SettingsService(_Settings(lazy=False, components_path=[BASE_COMPONENTS_PATH]))

        assert _flatten(await _determine_loading_strategy(service)) == {}


class TestCategoryMergePreservesBuiltIns:
    """A custom or extension category must supplement a built-in one, never replace it."""

    def test_a_colliding_category_does_not_delete_built_in_components(self):
        builtin = {"tools": {"Calculator": {"id": "builtin"}, "SearchAPI": {"id": "builtin"}}}
        custom = {"tools": {"MyTool": {"id": "custom"}}}

        merged = _merge_component_sources(builtin, custom)

        assert set(merged["tools"]) == {"Calculator", "SearchAPI", "MyTool"}

    def test_an_empty_scanned_category_does_not_erase_a_built_in_one(self):
        """The metadata scanner emits legacy category names whether or not they hold anything."""
        builtin = {"embeddings": {"OpenAIEmbeddings": {"id": "builtin"}}}
        custom = {"embeddings": {}, "llms": {}, "prompts": {}}

        merged = _merge_component_sources(builtin, custom)

        assert set(merged["embeddings"]) == {"OpenAIEmbeddings"}
        assert "llms" not in merged, "empty scanned categories should not surface as empty palette sections"

    def test_extension_still_wins_on_a_same_named_component(self):
        builtin = {"tools": {"Calculator": {"id": "builtin"}}}
        extension = {"tools": {"Calculator": {"id": "extension"}}}

        merged = _merge_component_sources(builtin, {}, extension)

        assert merged["tools"]["Calculator"]["id"] == "extension"

    def test_the_built_in_source_is_not_mutated(self):
        """The registry is a process-wide cache; merging must not write through to it."""
        builtin = {"tools": {"Calculator": {"id": "builtin"}}}

        _merge_component_sources(builtin, {"tools": {"MyTool": {"id": "custom"}}})

        assert set(builtin["tools"]) == {"Calculator"}


class TestRegistryParityAcrossModes:
    """The end-to-end invariant: lazy mode must not shrink what the server knows."""

    async def test_lazy_and_full_registries_agree_on_built_ins(self):
        from lfx.interface.components import import_langflow_components

        builtin = (await import_langflow_components(None, None))["components"]

        async def registry(*, lazy: bool) -> dict[str, Any]:
            service = _SettingsService(_Settings(lazy=lazy, components_path=[BASE_COMPONENTS_PATH]))
            custom = _flatten(await _determine_loading_strategy(service))
            return _merge_component_sources(builtin, custom)

        lazy_registry = await registry(lazy=True)
        full_registry = await registry(lazy=False)

        def counts(reg: dict[str, Any]) -> tuple[int, int]:
            return len(reg), sum(len(c) for c in reg.values())

        assert counts(lazy_registry) == counts(full_registry)
        assert any("ChatInput" in comps for comps in lazy_registry.values()), (
            "ChatInput missing from the lazy registry; built-in components would read as custom"
        )
