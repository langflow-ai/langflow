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

Fixing (2) by merging per component then exposed a third defect: the de-dup that retires the
legacy copy of a component inline extension discovery also found matched only the component
``name``. Lazy metadata loading never imports the file, so it keys the entry by the file's
stem instead -- the pop missed and every custom component appeared twice, the second copy a
stub with no code and no outputs.
"""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import lfx.interface.components as components_module
from lfx.interface.components import (
    BASE_COMPONENTS_PATH,
    _determine_loading_strategy,
    _merge_component_sources,
    import_extension_components,
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

    async def test_lazy_branch_skips_an_equivalent_built_in_path(self, monkeypatch):
        """Path spelling must not turn the built-in directory into a custom source."""
        metadata_loader = AsyncMock(return_value={})
        monkeypatch.setattr(components_module, "aget_component_metadata", metadata_loader)
        service = _SettingsService(_Settings(lazy=True, components_path=[f"{BASE_COMPONENTS_PATH}/./"]))

        assert _flatten(await _determine_loading_strategy(service)) == {}
        metadata_loader.assert_not_awaited()

    async def test_lazy_branch_skips_a_symlink_to_the_built_in_path(self, monkeypatch, tmp_path: Path):
        """A symlink alias of the built-in directory must be filtered as the same source."""
        alias = tmp_path / "components-link"
        alias.symlink_to(Path(BASE_COMPONENTS_PATH), target_is_directory=True)
        metadata_loader = AsyncMock(return_value={})
        monkeypatch.setattr(components_module, "aget_component_metadata", metadata_loader)
        service = _SettingsService(_Settings(lazy=True, components_path=[str(alias)]))

        assert _flatten(await _determine_loading_strategy(service)) == {}
        metadata_loader.assert_not_awaited()


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

    def test_namespaced_extension_replaces_its_legacy_custom_copy(self):
        builtin = {"tools": {"Calculator": {"id": "builtin"}, "SearchAPI": {"id": "builtin"}}}
        custom = {"tools": {"MyTool": {"id": "custom"}}}
        extension_id = "ext:tools:MyTool@extra"
        extension = {"tools": {extension_id: {"id": "extension", "name": "MyTool"}}}

        merged = _merge_component_sources(builtin, custom, extension)

        assert set(merged["tools"]) == {"Calculator", "SearchAPI", extension_id}

    def test_namespaced_extension_replaces_its_lazy_stub_keyed_by_file_name(self):
        """Lazy metadata loading keys the legacy copy by file stem, not component name."""
        builtin = {"tools": {"Calculator": {"id": "builtin"}}}
        custom = {"tools": {"qa_custom_tool": {"id": "custom", "name": "qa_custom_tool", "lazy_loaded": True}}}
        extension_id = "ext:tools:QACustomTool@extra"
        extension = {
            "tools": {extension_id: {"id": "extension", "name": "QACustomTool", "legacy_module": "qa_custom_tool"}}
        }

        merged = _merge_component_sources(builtin, custom, extension)

        assert set(merged["tools"]) == {"Calculator", extension_id}, (
            "the lazy stub survived beside its extension copy; it carries no code and no outputs, "
            "so dragging it yields a node with no output handle"
        )

    def test_the_file_name_alias_does_not_evict_an_unrelated_builtin(self):
        """Only a key the custom scanner actually produced may be retired."""
        builtin = {"tools": {"qa_custom_tool": {"id": "builtin"}}}
        extension_id = "ext:tools:QACustomTool@extra"
        extension = {
            "tools": {extension_id: {"id": "extension", "name": "QACustomTool", "legacy_module": "qa_custom_tool"}}
        }

        merged = _merge_component_sources(builtin, {}, extension)

        assert set(merged["tools"]) == {"qa_custom_tool", extension_id}

    def test_namespaced_custom_override_hides_the_same_named_builtin(self):
        builtin = {"tools": {"Calculator": {"id": "builtin"}, "SearchAPI": {"id": "builtin"}}}
        custom = {"tools": {"Calculator": {"id": "custom"}}}
        extension_id = "ext:tools:CalculatorComponent@extra"
        extension = {"tools": {extension_id: {"id": "extension", "name": "Calculator"}}}

        merged = _merge_component_sources(builtin, custom, extension)

        assert set(merged["tools"]) == {"SearchAPI", extension_id}
        assert merged["tools"][extension_id]["id"] == "extension"

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


class TestLazyModeDoesNotDuplicateCustomComponents:
    """The reported symptom: one custom component, two palette entries.

    Inline extension discovery and the legacy custom scanner walk the *same*
    ``LANGFLOW_COMPONENTS_PATH`` directories, so every custom component is found twice.
    Only the extension copy is usable -- the lazy stub is metadata-only.
    """

    @staticmethod
    def _components_root(tmp_path: Path) -> Path:
        root = tmp_path / "components_root"
        tools = root / "tools"
        tools.mkdir(parents=True)
        (tools / "qa_custom_tool.py").write_text(
            "class Component:\n    pass\n"
            "class QACustomTool(Component):\n"
            "    display_name = 'QA Custom Tool'\n"
            "    def build(self):\n        return None\n",
            encoding="utf-8",
        )
        return root

    async def test_a_lazily_scanned_custom_component_appears_once(self, tmp_path: Path):
        from unittest.mock import patch

        root = self._components_root(tmp_path)
        service = _SettingsService(_Settings(lazy=True, components_path=[str(root)]))

        custom = _flatten(await _determine_loading_strategy(service))
        assert "qa_custom_tool" in custom["tools"], "precondition: lazy mode keys the stub by file name"

        def stub_template(*_args, **_kwargs):
            return ({"display_name": "QA Custom Tool", "type": "tools", "template": {}}, object())

        with patch("lfx.interface.components.create_component_template", side_effect=stub_template):
            extension = await import_extension_components(service)

        merged = _merge_component_sources({}, custom, extension)

        assert set(merged["tools"]) == {"ext:tools:QACustomTool@extra"}, (
            f"custom component duplicated in the palette: {sorted(merged['tools'])}"
        )
