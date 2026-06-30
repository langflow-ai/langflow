"""Integration tests: model providers contributed through the extension loader.

Drives a synthetic ``extension.json`` declaring ``providers[]`` through the
real ``load_extension`` path and asserts the provider becomes visible in the
unified model system -- proving a bundle can register a provider end to end with
no core edits. Also covers the manifest-schema rules for the new ``providers``
field and the provider-only (empty-bundle) extension shape.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from lfx.base.models import provider_registry
from lfx.base.models.unified_models import get_model_providers
from lfx.extension import load_extension
from lfx.extension.manifest import ExtensionManifest

if TYPE_CHECKING:
    from pathlib import Path


def fake_live_discovery(user_id, model_type):  # noqa: ARG001
    return [{"provider": "FakeCo", "name": f"fake-{model_type}", "icon": "FakeCo"}]


_LIVE_DISCOVERY_PATH = f"{__name__}:fake_live_discovery"


def _provider_entry(**overrides) -> dict:
    entry = {
        "name": "FakeCo",
        "metadata": {
            "icon": "FakeCo",
            "max_tokens_field_name": "max_tokens",
            "variables": [
                {
                    "variable_name": "FakeCo API Key",
                    "variable_key": "FAKECO_API_KEY",
                    "required": True,
                    "is_secret": True,
                    "is_list": False,
                    "options": [],
                    "langchain_param": "api_key",
                },
            ],
            "api_docs_url": "https://fakeco.example/docs",
            "mapping": {"model_class": "ChatOpenAI", "model_param": "model"},
        },
        "api_key_required": False,
        "live": True,
        "live_discovery": _LIVE_DISCOVERY_PATH,
    }
    entry.update(overrides)
    return entry


def _write_manifest(root: Path, manifest: dict) -> Path:
    (root / "extension.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


@pytest.fixture(autouse=True)
def _isolate_registry():
    provider_registry.clear()
    yield
    provider_registry.clear()


# ---------------------------------------------------------------------------
# Loader: provider-only extension end to end
# ---------------------------------------------------------------------------


def test_provider_only_extension_registers_provider(tmp_path: Path):
    manifest = {
        "id": "lfx-fakeco",
        "version": "0.1.0",
        "name": "FakeCo Provider",
        "lfx": {"compat": ["1"]},
        "providers": [_provider_entry()],
    }
    root = _write_manifest(tmp_path, manifest)

    result = load_extension(root)

    assert result.ok, (result.errors, result.warnings)
    assert result.components == []  # provider-only: no component bundle
    assert provider_registry.is_registered("FakeCo")
    assert "FakeCo" in get_model_providers()
    assert provider_registry.is_api_key_optional("FakeCo") is True


def test_loaded_provider_live_discovery_dispatches(tmp_path: Path):
    manifest = {
        "id": "lfx-fakeco",
        "version": "0.1.0",
        "name": "FakeCo Provider",
        "lfx": {"compat": ["1"]},
        "providers": [_provider_entry()],
    }
    load_extension(_write_manifest(tmp_path, manifest))

    from lfx.base.models.model_utils import get_live_models_for_provider

    models = get_live_models_for_provider("user-1", "FakeCo", "llm")
    assert [m["name"] for m in models] == ["fake-llm"]


def test_invalid_provider_is_warning_not_fatal(tmp_path: Path):
    bad_entry = _provider_entry()
    # Strip the required mapping.model_class so register_provider raises and the
    # loader records a warning rather than aborting.
    bad_entry["metadata"] = {**bad_entry["metadata"], "mapping": {"model_param": "model"}}
    manifest = {
        "id": "lfx-fakeco",
        "version": "0.1.0",
        "name": "FakeCo Provider",
        "lfx": {"compat": ["1"]},
        "providers": [bad_entry],
    }
    # A manifest-level validator rejects metadata without mapping.model_class, so
    # this manifest never parses -> load_extension surfaces manifest-invalid.
    result = load_extension(_write_manifest(tmp_path, manifest))
    assert not result.ok
    assert any(e.code == "manifest-invalid" for e in result.errors)
    assert not provider_registry.is_registered("FakeCo")


# ---------------------------------------------------------------------------
# Manifest schema rules
# ---------------------------------------------------------------------------


def test_manifest_accepts_provider_only_extension():
    manifest = ExtensionManifest.model_validate(
        {
            "id": "lfx-fakeco",
            "version": "0.1.0",
            "name": "FakeCo",
            "lfx": {"compat": ["1"]},
            "providers": [_provider_entry()],
        }
    )
    assert manifest.bundles == []
    assert manifest.providers[0].name == "FakeCo"
    assert manifest.providers[0].api_key_required is False


def test_manifest_rejects_empty_extension():
    with pytest.raises(ValueError, match="at least one bundle or one provider"):
        ExtensionManifest.model_validate(
            {
                "id": "lfx-empty",
                "version": "0.1.0",
                "name": "Empty",
                "lfx": {"compat": ["1"]},
            }
        )


def test_manifest_rejects_metadata_without_model_class():
    with pytest.raises(ValueError, match="model_class"):
        ExtensionManifest.model_validate(
            {
                "id": "lfx-fakeco",
                "version": "0.1.0",
                "name": "FakeCo",
                "lfx": {"compat": ["1"]},
                "providers": [_provider_entry(metadata={"icon": "X", "mapping": {}})],
            }
        )


def test_manifest_rejects_live_and_conditional_live():
    with pytest.raises(ValueError, match="both 'live' and 'conditional_live'"):
        ExtensionManifest.model_validate(
            {
                "id": "lfx-fakeco",
                "version": "0.1.0",
                "name": "FakeCo",
                "lfx": {"compat": ["1"]},
                "providers": [_provider_entry(live=True, conditional_live=True)],
            }
        )


def test_manifest_rejects_duplicate_provider_names():
    with pytest.raises(ValueError, match="Provider names must be unique"):
        ExtensionManifest.model_validate(
            {
                "id": "lfx-fakeco",
                "version": "0.1.0",
                "name": "FakeCo",
                "lfx": {"compat": ["1"]},
                "providers": [_provider_entry(), _provider_entry()],
            }
        )


def test_manifest_hybrid_bundle_plus_provider_parses():
    manifest = ExtensionManifest.model_validate(
        {
            "id": "lfx-fakeco",
            "version": "0.1.0",
            "name": "FakeCo",
            "lfx": {"compat": ["1"]},
            "bundles": [{"name": "fakeco", "path": "components"}],
            "providers": [_provider_entry()],
        }
    )
    assert manifest.bundles[0].name == "fakeco"
    assert manifest.providers[0].name == "FakeCo"
