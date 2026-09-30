"""Plugin-discovery tests for the ingestion-source registry.

Covers what the original hand-rolled registry couldn't do:

* Third-party entry-point registration under ``lfx.ingestion_source.adapters``.
* TOML config-file registration under ``[ingestion_source.adapters]`` in
  ``lfx.toml`` (and the ``[tool.lfx.ingestion_source.adapters]`` fallback
  in ``pyproject.toml``).

Behavioral parity with the pre-AdapterRegistry registry is covered in
``src/backend/tests/unit/base/knowledge_bases/ingestion_sources/`` — this
module focuses on the new plugin surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lfx.base.knowledge_bases.ingestion_sources import registry as ingestion_registry
from lfx.base.knowledge_bases.ingestion_sources.base import (
    IngestionItem,
    IngestionItemContent,
    KBIngestionSource,
    SourceType,
)
from lfx.services.adapters import registry as adapter_registry_mod
from lfx.services.adapters.schema import AdapterType

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class _StubSource(KBIngestionSource):
    """Minimal KBIngestionSource stub for plugin-discovery tests."""

    source_type = SourceType.FILE_UPLOAD  # placeholder; not used by tests
    display_name = "Stub"
    description = "Plugin-discovery stub"

    async def list_items(self) -> AsyncIterator[IngestionItem]:  # pragma: no cover - unused
        if False:
            yield  # type: ignore[unreachable]

    async def fetch_content(self, item: IngestionItem) -> IngestionItemContent:  # pragma: no cover - unused
        raise NotImplementedError

    async def validate_config(self) -> None:  # pragma: no cover - unused
        return None


class _StubEntryPoint:
    """importlib.metadata EntryPoint stand-in for monkeypatching."""

    def __init__(self, name: str, obj: type):
        self.name = name
        self._obj = obj

    def load(self):
        return self._obj


@pytest.fixture(autouse=True)
async def _reset_registry(monkeypatch, tmp_path):
    """Reset adapter-registry state per test + force lazy discovery to re-run.

    The registry is a process-global singleton, and the ingestion-sources
    module uses a separate ``is_discovered`` flag to avoid re-running
    discovery on every lookup. ``_reset_registries`` clears both.

    The built-ins (``FileUploadSource``, ``FolderSource``, …) register
    via module-level side effects in
    ``lfx.base.knowledge_bases.ingestion_sources.__init__``. That
    ``import`` fires exactly once per process, so after a reset the
    built-ins would stay missing and leak into sibling tests that
    assume a populated registry. We reinstall them explicitly in the
    fixture's teardown so the process-wide registry is restored to
    its post-import state.
    """
    await adapter_registry_mod._reset_registries()

    # ``_ensure_discovered`` routes config lookup through the settings
    # service → config_dir path. Point that at ``tmp_path`` so TOML
    # files laid down by tests are the ones the registry reads.
    import lfx.base.knowledge_bases.ingestion_sources.registry as reg

    monkeypatch.setattr(
        reg,
        "_ensure_discovered",
        _make_ensure_discovered(tmp_path),
    )
    try:
        yield
    finally:
        await adapter_registry_mod._reset_registries()
        _reinstall_builtin_sources()


def _reinstall_builtin_sources() -> None:
    """Re-register the built-in sources.

    These normally register via module-level side effects in
    ``lfx.base.knowledge_bases.ingestion_sources.__init__`` at import
    time; after ``_reset_registries`` we reinstall them explicitly.

    In this phase only ``file_upload`` and ``folder`` are registered.
    The S3 / Google Drive / OneDrive / SharePoint stubs are NOT
    re-registered because the production import path doesn't register
    them either — see the ``__init__`` module's docstring.
    """
    from lfx.base.knowledge_bases.ingestion_sources.file_upload import FileUploadSource
    from lfx.base.knowledge_bases.ingestion_sources.folder import FolderSource

    ingestion_registry.register_source(SourceType.FILE_UPLOAD, FileUploadSource)
    ingestion_registry.register_source(SourceType.FOLDER, FolderSource)


def _make_ensure_discovered(config_dir):
    """Bind a fresh ``_ensure_discovered`` that uses ``config_dir`` directly.

    The production implementation resolves the config dir through the
    settings service; for tests we inject the tmp_path directly to
    avoid standing up a full settings service just to read a TOML file.
    """
    import threading

    from lfx.base.knowledge_bases.ingestion_sources import registry as reg

    lock = threading.Lock()

    def _impl() -> None:
        registry = reg._registry()
        if registry.is_discovered:
            return
        with lock:
            if registry.is_discovered:
                return
            registry.discover(config_dir=config_dir)

    return _impl


# --------------------------------------------------------------------- #
# Entry-point discovery                                                  #
# --------------------------------------------------------------------- #


def test_entry_point_registers_plugin_source(monkeypatch):
    """Third-party entry points should appear in the registry on first lookup.

    A package publishing an entry point under
    ``lfx.ingestion_source.adapters`` should register lazily when
    ``get_source_class`` is called for the first time.
    """

    def fake_entry_points(*, group: str):
        if group == AdapterType.INGESTION_SOURCE.entry_point_group:
            return [_StubEntryPoint("box", _StubSource)]
        return []

    monkeypatch.setattr("importlib.metadata.entry_points", fake_entry_points)

    cls = ingestion_registry.get_source_class("box")
    assert cls is _StubSource
    assert "box" in ingestion_registry.registered_source_keys()


def test_builtin_sources_are_not_shadowed_by_entry_points(monkeypatch):
    """Entry-point registration must not overwrite built-in sources.

    Entry-point discovery calls ``register_class(..., override=False)``,
    so a third-party plugin reusing a built-in key cannot silently
    replace the built-in implementation.
    """
    # Ensure the built-in is registered first (as it would be in
    # production — modules self-register at import time).
    from lfx.base.knowledge_bases.ingestion_sources.folder import FolderSource

    ingestion_registry.register_source(SourceType.FOLDER, FolderSource)

    def fake_entry_points(*, group: str):
        if group == AdapterType.INGESTION_SOURCE.entry_point_group:
            return [_StubEntryPoint("folder", _StubSource)]
        return []

    monkeypatch.setattr("importlib.metadata.entry_points", fake_entry_points)

    assert ingestion_registry.get_source_class(SourceType.FOLDER) is FolderSource


# --------------------------------------------------------------------- #
# TOML discovery                                                         #
# --------------------------------------------------------------------- #


def test_lfx_toml_registers_plugin_source(tmp_path, monkeypatch):
    """``lfx.toml`` entries register with ``override=True``.

    ``[ingestion_source.adapters]`` in ``lfx.toml`` should register the
    referenced class at higher priority than entry points (config files
    are the highest-priority discovery source).
    """
    # Make the stub importable through an import path.
    import sys
    import types

    fake_module = types.ModuleType("fake_plugin_pkg.ingestion")
    fake_module._StubSource = _StubSource
    sys.modules["fake_plugin_pkg.ingestion"] = fake_module

    (tmp_path / "lfx.toml").write_text(
        '[ingestion_source.adapters]\nnotion = "fake_plugin_pkg.ingestion:_StubSource"\n'
    )

    # No entry points — isolate the TOML path.
    monkeypatch.setattr("importlib.metadata.entry_points", lambda *, group: [])  # noqa: ARG005

    cls = ingestion_registry.get_source_class("notion")
    assert cls is _StubSource


def test_unknown_plugin_key_raises_unknown_not_unregistered(monkeypatch):
    """Typos surface as ``"Unknown ingestion source"`` not ``"not registered"``.

    API routes rely on this split to distinguish user-supplied typos
    (HTTP 400) from missing-import internal errors (HTTP 500). See
    ``get_source_class`` for the split.
    """
    monkeypatch.setattr("importlib.metadata.entry_points", lambda *, group: [])  # noqa: ARG005
    with pytest.raises(ValueError, match="Unknown ingestion source"):
        ingestion_registry.get_source_class("does-not-exist-anywhere")
