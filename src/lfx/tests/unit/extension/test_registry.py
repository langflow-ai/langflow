"""Service-layer tests for the read-only Extension registry.

The acceptance criterion this file covers:

    > Service-layer immutability test: attempting to mutate an
    > installed/seed Extension entry through the registry service raises
    > installed-extension-immutable or seed-directory-immutable.

We assert the invariant directly without relying on a CLI verb that
hasn't shipped yet (uninstall lands in B4); the verbs are exposed at the
service layer expressly so this test can be written today.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from lfx.extension import format_extension_error
from lfx.extension.discovery import DiscoveredExtension
from lfx.extension.errors import ExtensionError
from lfx.extension.manifest import ExtensionManifest, ManifestSource
from lfx.extension.registry import (
    DuplicateExtensionError,
    Extension,
    ExtensionImmutableError,
    ExtensionRegistry,
    LoadStatus,
    build_registry_from_discovery,
)

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _manifest_dict(extension_id: str, bundle_name: str) -> dict[str, object]:
    return {
        "id": extension_id,
        "version": "1.0.0",
        "name": f"{extension_id} bundle",
        "lfx": {"compat": ["1"]},
        "bundles": [{"name": bundle_name, "path": bundle_name}],
    }


def _write_manifest(root: Path, manifest: dict[str, object]) -> ManifestSource:
    root.mkdir(parents=True, exist_ok=True)
    bundle_name = manifest["bundles"][0]["name"]  # type: ignore[index]
    (root / bundle_name).mkdir(exist_ok=True)
    manifest_path = root / "extension.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return ManifestSource(
        manifest=ExtensionManifest.model_validate(manifest),
        path=manifest_path,
        kind="extension.json",
    )


def _make_discovered(
    *,
    extension_id: str,
    bundle_name: str,
    source_kind: str,
    source: str,
    root: Path,
) -> DiscoveredExtension:
    manifest_source = _write_manifest(root, _manifest_dict(extension_id, bundle_name))
    return DiscoveredExtension(
        extension_id=extension_id,
        version=manifest_source.manifest.version,
        bundle_name=bundle_name,
        manifest=manifest_source,
        source_kind=source_kind,  # type: ignore[arg-type]
        source=source,
        extension_root=root,
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_register_installed_pins_extension_at_official_slot(tmp_path: Path) -> None:
    discovered = _make_discovered(
        extension_id="lfx-openai",
        bundle_name="openai",
        source_kind="installed",
        source="lfx-openai",
        root=tmp_path / "lfx_openai",
    )
    registry = ExtensionRegistry()
    registered = registry.register_installed(discovered)

    assert registered.extension_id == "lfx-openai"
    assert registered.slot == "official"
    assert registered.source_kind == "installed"
    assert registered.auto_update is False
    assert registered.load_status is LoadStatus.DISCOVERED
    assert registry.list_extensions() == [registered]


def test_register_seed_pins_extension_at_official_slot(tmp_path: Path) -> None:
    discovered = _make_discovered(
        extension_id="lfx-anthropic",
        bundle_name="anthropic",
        source_kind="seed",
        source=str(tmp_path / "seed/lfx_anthropic"),
        root=tmp_path / "seed/lfx_anthropic",
    )
    registry = ExtensionRegistry()
    registered = registry.register_seed(discovered)

    assert registered.source_kind == "seed"
    assert registered.slot == "official"


def test_registration_validates_source_kind(tmp_path: Path) -> None:
    """register_installed refuses seed-kind records and vice versa."""
    seed_record = _make_discovered(
        extension_id="lfx-xx",
        bundle_name="xx",
        source_kind="seed",
        source=str(tmp_path / "seed/lfx_xx"),
        root=tmp_path / "seed/lfx_xx",
    )
    installed_record = _make_discovered(
        extension_id="lfx-yy",
        bundle_name="yy",
        source_kind="installed",
        source="lfx-yy",
        root=tmp_path / "site-packages/lfx_yy",
    )
    registry = ExtensionRegistry()
    with pytest.raises(ValueError, match="register_installed"):
        registry.register_installed(seed_record)
    with pytest.raises(ValueError, match="register_seed"):
        registry.register_seed(installed_record)


def test_duplicate_extension_id_raises_typed_error(tmp_path: Path) -> None:
    a = _make_discovered(
        extension_id="lfx-openai",
        bundle_name="openai",
        source_kind="installed",
        source="lfx-openai",
        root=tmp_path / "site-packages/lfx_openai",
    )
    b = _make_discovered(
        extension_id="lfx-openai",
        bundle_name="openai",
        source_kind="seed",
        source=str(tmp_path / "seed/lfx_openai"),
        root=tmp_path / "seed/lfx_openai",
    )
    registry = ExtensionRegistry()
    registry.register_installed(a)
    with pytest.raises(DuplicateExtensionError) as exc_info:
        registry.register_seed(b)
    assert exc_info.value.error.code == "duplicate-extension-id"
    assert exc_info.value.error.content == "lfx-openai"


# ---------------------------------------------------------------------------
# Immutability invariant
# ---------------------------------------------------------------------------

_MUTATION_VERBS = ("uninstall", "disable", "enable", "install", "update_entry")


def _invoke_mutation_verb(registry: ExtensionRegistry, verb: str, extension_id: str) -> None:
    """Invoke ``verb`` on ``registry``; the mutation surface always raises."""
    method = getattr(registry, verb)
    if verb == "update_entry":
        method(extension_id, auto_update=True)
    else:
        method(extension_id)


@pytest.mark.parametrize("verb", _MUTATION_VERBS)
def test_installed_extension_is_immutable(tmp_path: Path, verb: str) -> None:
    """Every mutation verb on an installed Extension raises immutability.

    The invariant is observable via the service surface, even though
    uninstall doesn't ship as a CLI verb yet.
    """
    discovered = _make_discovered(
        extension_id="lfx-openai",
        bundle_name="openai",
        source_kind="installed",
        source="lfx-openai",
        root=tmp_path / "lfx_openai",
    )
    registry = ExtensionRegistry()
    registry.register_installed(discovered)

    with pytest.raises(ExtensionImmutableError) as exc_info:
        _invoke_mutation_verb(registry, verb, "lfx-openai")
    assert exc_info.value.error.code == "installed-extension-immutable"
    assert exc_info.value.error.content == "lfx-openai"


@pytest.mark.parametrize("verb", _MUTATION_VERBS)
def test_seed_extension_is_immutable(tmp_path: Path, verb: str) -> None:
    """Every mutation verb on a seed Extension raises seed-directory-immutable."""
    seed_root = tmp_path / "seed/lfx_anthropic"
    discovered = _make_discovered(
        extension_id="lfx-anthropic",
        bundle_name="anthropic",
        source_kind="seed",
        source=str(seed_root),
        root=seed_root,
    )
    registry = ExtensionRegistry()
    registry.register_seed(discovered)

    with pytest.raises(ExtensionImmutableError) as exc_info:
        _invoke_mutation_verb(registry, verb, "lfx-anthropic")
    assert exc_info.value.error.code == "seed-directory-immutable"
    assert exc_info.value.error.content == "lfx-anthropic"


def test_immutability_error_round_trips_to_format(tmp_path: Path) -> None:
    """The wrapped ExtensionError feeds into format_extension_error cleanly."""
    discovered = _make_discovered(
        extension_id="lfx-openai",
        bundle_name="openai",
        source_kind="installed",
        source="lfx-openai",
        root=tmp_path / "lfx_openai",
    )
    registry = ExtensionRegistry()
    registry.register_installed(discovered)
    with pytest.raises(ExtensionImmutableError) as exc_info:
        registry.uninstall("lfx-openai")

    rendered = format_extension_error(exc_info.value.error)
    assert rendered.startswith("error[installed-extension-immutable]")
    assert "see:" in rendered
    payload = exc_info.value.to_dict()
    assert payload["code"] == "installed-extension-immutable"


def test_mutation_on_unknown_extension_raises_keyerror() -> None:
    """Distinguish "no such extension" from "extension is immutable".

    The router-trust CI guard rejects HTTP routes for these verbs anyway,
    but if a test harness invokes the service directly with a typo we
    should fail fast and clearly rather than emit a misleading typed
    error about an extension that doesn't exist.
    """
    registry = ExtensionRegistry()
    with pytest.raises(KeyError):
        registry.uninstall("missing-extension")


# ---------------------------------------------------------------------------
# Load-status updates (loader-side; not part of the immutability surface)
# ---------------------------------------------------------------------------


def test_mark_loaded_replaces_load_status(tmp_path: Path) -> None:
    discovered = _make_discovered(
        extension_id="lfx-openai",
        bundle_name="openai",
        source_kind="installed",
        source="lfx-openai",
        root=tmp_path / "lfx_openai",
    )
    registry = ExtensionRegistry()
    registry.register_installed(discovered)

    updated = registry.mark_loaded("lfx-openai")
    assert updated.load_status is LoadStatus.LOADED
    assert registry.get("lfx-openai") == updated


def test_mark_failed_attaches_typed_error(tmp_path: Path) -> None:
    discovered = _make_discovered(
        extension_id="lfx-openai",
        bundle_name="openai",
        source_kind="installed",
        source="lfx-openai",
        root=tmp_path / "lfx_openai",
    )
    registry = ExtensionRegistry()
    registry.register_installed(discovered)

    error = ExtensionError(
        code="bundle-empty",
        message="Bundle 'openai' contains no Python source files.",
        hint="Add at least one Python file.",
        location=str(tmp_path / "lfx_openai/openai"),
        content="openai",
    )
    updated = registry.mark_failed("lfx-openai", error=error)
    assert updated.load_status is LoadStatus.FAILED
    assert updated.load_error is error


# ---------------------------------------------------------------------------
# build_registry_from_discovery
# ---------------------------------------------------------------------------


def test_build_registry_from_discovery_pins_three(tmp_path: Path) -> None:
    discovered = [
        _make_discovered(
            extension_id="lfx-openai",
            bundle_name="openai",
            source_kind="installed",
            source="lfx-openai",
            root=tmp_path / "site-packages/lfx_openai",
        ),
        _make_discovered(
            extension_id="lfx-anthropic",
            bundle_name="anthropic",
            source_kind="installed",
            source="lfx-anthropic",
            root=tmp_path / "site-packages/lfx_anthropic",
        ),
        _make_discovered(
            extension_id="lfx-qdrant",
            bundle_name="qdrant",
            source_kind="seed",
            source=str(tmp_path / "seed/lfx_qdrant"),
            root=tmp_path / "seed/lfx_qdrant",
        ),
    ]
    registry, errors = build_registry_from_discovery(discovered)
    assert errors == []
    assert {ext.extension_id for ext in registry.list_extensions()} == {
        "lfx-openai",
        "lfx-anthropic",
        "lfx-qdrant",
    }


def test_build_registry_from_discovery_collects_duplicate_errors(tmp_path: Path) -> None:
    """A duplicate id produces a typed error but does not crash the build."""
    discovered = [
        _make_discovered(
            extension_id="lfx-openai",
            bundle_name="openai",
            source_kind="installed",
            source="lfx-openai-from-pip",
            root=tmp_path / "site-packages/lfx_openai",
        ),
        _make_discovered(
            extension_id="lfx-openai",
            bundle_name="openai",
            source_kind="seed",
            source=str(tmp_path / "seed/lfx_openai"),
            root=tmp_path / "seed/lfx_openai",
        ),
    ]
    registry, errors = build_registry_from_discovery(discovered)
    assert {ext.extension_id for ext in registry.list_extensions()} == {"lfx-openai"}
    assert len(errors) == 1
    assert errors[0].code == "duplicate-extension-id"


def test_extension_namespaced_slot_uses_at_prefix(tmp_path: Path) -> None:
    discovered = _make_discovered(
        extension_id="lfx-openai",
        bundle_name="openai",
        source_kind="installed",
        source="lfx-openai",
        root=tmp_path / "lfx_openai",
    )
    registry = ExtensionRegistry()
    registered = registry.register_installed(discovered)
    assert registered.namespaced_slot == "@official"


def test_extension_dataclass_is_frozen(tmp_path: Path) -> None:
    """Frozen so callers can't mutate snapshots they receive from the registry."""
    discovered = _make_discovered(
        extension_id="lfx-openai",
        bundle_name="openai",
        source_kind="installed",
        source="lfx-openai",
        root=tmp_path / "lfx_openai",
    )
    registry = ExtensionRegistry()
    ext: Extension = registry.register_installed(discovered)

    with pytest.raises((AttributeError, TypeError)):
        ext.auto_update = True  # type: ignore[misc]
