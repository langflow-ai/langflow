"""Previously persisted source must load when the retired SDKs are unavailable."""

import ast
import importlib.abc
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from lfx.custom.eval import eval_custom_component_code
from lfx.custom.legacy_storage_compat import resolve_shipped_storage_component, source_fingerprint

SOURCES = json.loads(Path(__file__).with_name("legacy_storage_source_fixtures.json").read_text())
HISTORICAL = json.loads(Path(__file__).with_name("historical_storage_source_fixtures.json").read_text())


class NoRetiredSDKs(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):  # noqa: ARG002 -- importlib protocol
        if fullname.split(".", 1)[0] in {"chromadb", "langchain_chroma", "altk"}:
            msg = f"Retired SDK must be absent: {fullname}"
            raise AssertionError(msg)


@pytest.mark.usefixtures("no_retired_sdks")
@pytest.mark.parametrize("fingerprint", HISTORICAL)
def test_every_distinct_released_source_loads_without_retired_sdks(fingerprint):
    fixture = HISTORICAL[fingerprint]
    assert source_fingerprint(fixture["source"]) == fingerprint
    component = eval_custom_component_code(fixture["source"])
    assert component.__name__ == fixture["class_name"], (fixture["tag"], fixture["path"])


@pytest.fixture
def no_retired_sdks(monkeypatch):
    monkeypatch.setattr(sys, "meta_path", [NoRetiredSDKs(), *sys.meta_path])


@pytest.mark.usefixtures("no_retired_sdks")
@pytest.mark.parametrize("name", SOURCES)
@pytest.mark.parametrize("class_only", [False, True])
def test_shipped_old_source_resolves_current_class_before_imports(name, class_only):
    source = SOURCES[name]
    if class_only:
        node = next(node for node in ast.parse(source).body if isinstance(node, ast.ClassDef) and node.name == name)
        source = ast.get_source_segment(source, node)
    component = eval_custom_component_code(source)
    assert component.__name__ == name
    assert component.__module__.startswith("lfx.components.")
    assert component is resolve_shipped_storage_component(source)
    if name in {"ChromaVectorStoreComponent", "LocalDBComponent", "ALTKAgentComponent"}:
        assert component.legacy


@pytest.mark.parametrize("name", SOURCES)
def test_custom_edits_are_never_silently_replaced(name):
    source = SOURCES[name] + "\nCUSTOM_USER_BEHAVIOR = True\n"
    assert resolve_shipped_storage_component(source) is None


def test_fingerprint_preserves_literals_but_ignores_layout():
    assert source_fingerprint("value = 'one' # comment\n") == source_fingerprint('value="one"\n')
    assert source_fingerprint("value = 'one'\n") != source_fingerprint("value = 'two'\n")


@pytest.mark.usefixtures("no_retired_sdks")
@pytest.mark.parametrize("name", SOURCES)
def test_saved_source_dependency_export_does_not_reinstall_retired_sdks(name):
    from lfx.utils.flow_requirements import _extract_imports

    assert not _extract_imports(SOURCES[name]) & {"chromadb", "langchain_chroma", "altk"}


@pytest.mark.parametrize(
    "inventory", [FileNotFoundError, PermissionError, '{"entries":[{}]}', '{"entries":[null]}', "[]"]
)
def test_unavailable_inventory_preserves_custom_component_evaluation(monkeypatch, inventory):
    """An unreadable or malformed shipped inventory must preserve normal custom evaluation."""
    from lfx.custom import legacy_storage_compat

    def read_text(**_kwargs):
        """Return malformed package data or simulate an unavailable inventory file."""
        if isinstance(inventory, type):
            msg = "inventory unavailable"
            raise inventory(msg)
        return inventory

    monkeypatch.setattr(
        legacy_storage_compat,
        "files",
        lambda _package: SimpleNamespace(joinpath=lambda *_parts: SimpleNamespace(read_text=read_text)),
    )
    legacy_storage_compat._known_sources.cache_clear()
    source = (
        "from lfx.custom import Component\n"
        "class KnowledgeComponent(Component):\n"
        "    display_name = 'Custom knowledge'\n"
    )
    try:
        assert resolve_shipped_storage_component(source) is None
        assert eval_custom_component_code(source).__name__ == "KnowledgeComponent"
    finally:
        legacy_storage_compat._known_sources.cache_clear()
