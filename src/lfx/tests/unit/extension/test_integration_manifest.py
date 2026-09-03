"""Integration capability-manifest validation and loader exposure."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import pytest
from lfx.extension import load_extension, validate_extension
from lfx.extension.bundle_registry import BundleRecord, BundleRegistry

if TYPE_CHECKING:
    from pathlib import Path


def _capability_manifest(*, provider_id: str = "google") -> dict:
    return {
        "schema_version": 1,
        "provider_id": provider_id,
        "display_name": "Google Workspace",
        "icon": "Google",
        "docs_url": "https://developers.google.com/workspace",
        "auth_profiles": [
            {
                "id": "user",
                "kind": "oauth2_authorization_code",
                "identity": "user_delegated",
                "supports_pkce": True,
                "supports_refresh": True,
                "default_scopes": ["drive.file"],
                "client_type_by_context": {"hosted": "confidential", "desktop": "public"},
                "owner_by_context": {"hosted": "langflow", "desktop": "langflow"},
            }
        ],
        "capabilities": [
            {
                "id": "google.drive.files.search",
                "display_name": "Drive: Search Files",
                "auth_profile_id": "user",
                "identity": "user_delegated",
                "required_scopes": ["drive.file"],
                "conditional_scopes": [],
                "policy_keys": ["integrations.google.drive.search"],
                "substrate": "sdk",
                "maturity": "ga",
                "deployment_contexts": ["hosted", "self_managed", "desktop", "headless"],
                "risk": "read",
                "component_ref": "GoogleDriveSearchComponent",
            }
        ],
    }


def _write_extension(tmp_path: Path, *, capability_manifest: dict | None = None) -> None:
    manifest = {
        "id": "lfx-google",
        "version": "1.13.0",
        "name": "Google",
        "lfx": {"compat": ["1"]},
        "bundles": [{"name": "google", "path": "google"}],
    }
    if capability_manifest is not None:
        manifest["integrations"] = [{"provider_id": "google", "bundle": "google", "path": "capabilities.v1.json"}]
    (tmp_path / "extension.json").write_text(json.dumps(manifest), encoding="utf-8")
    bundle = tmp_path / "google"
    bundle.mkdir()
    (bundle / "component.py").write_text(
        "class Component:\n    pass\n\n"
        "class GoogleDriveSearchComponent(Component):\n"
        "    display_name = 'Drive: Search Files'\n"
        "    def build(self):\n        return None\n",
        encoding="utf-8",
    )
    if capability_manifest is not None:
        (bundle / "capabilities.v1.json").write_text(json.dumps(capability_manifest), encoding="utf-8")


def test_loader_exposes_validated_integration_metadata(tmp_path: Path) -> None:
    _write_extension(tmp_path, capability_manifest=_capability_manifest())

    result = load_extension(tmp_path, distribution="lfx-google")

    assert result.ok, result.errors
    assert len(result.integrations) == 1
    loaded = result.integrations[0]
    assert loaded.provider_id == "google"
    assert loaded.bundle == "google"
    assert loaded.distribution == "lfx-google"
    assert loaded.capability_manifest.schema_version == 1
    capability = loaded.capability_manifest.capabilities[0]
    assert capability.id == "google.drive.files.search"
    assert capability.policy_keys == ("integrations.google.drive.search",)
    assert capability.substrate == "sdk"
    assert capability.maturity == "ga"
    assert capability.deployment_contexts == ("hosted", "self_managed", "desktop", "headless")


def test_bundle_registry_exposes_integration_snapshot(tmp_path: Path) -> None:
    _write_extension(tmp_path, capability_manifest=_capability_manifest())
    result = load_extension(tmp_path, distribution="lfx-google")
    assert result.ok, result.errors
    registry = BundleRegistry()
    registry.install_bundle(
        BundleRecord(
            bundle="google",
            extension_id="lfx-google",
            extension_version="1.13.0",
            slot="official",
            components=tuple(result.components),
            integrations=tuple(result.integrations),
            distribution="lfx-google",
            source_path=tmp_path,
        )
    )

    assert registry.list_integrations() == result.integrations


def test_manifest_without_integrations_loads_unchanged(tmp_path: Path) -> None:
    _write_extension(tmp_path)

    result = load_extension(tmp_path)

    assert result.ok, result.errors
    assert result.integrations == []
    assert len(result.components) == 1


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.update(schema_version=2),
        lambda payload: payload["capabilities"][0].update(substrate="webhook"),
        lambda payload: payload["capabilities"][0].update(policy_keys=[]),
        lambda payload: payload["capabilities"][0].update(deployment_contexts=["mobile"]),
        lambda payload: payload["capabilities"][0].update(component_ref=""),
        lambda payload: payload.update(unknown=True),
    ],
)
def test_validate_rejects_malformed_capability_manifest(tmp_path: Path, mutation) -> None:
    capability_manifest = _capability_manifest()
    mutation(capability_manifest)
    _write_extension(tmp_path, capability_manifest=capability_manifest)

    report = validate_extension(tmp_path)

    assert not report.ok
    assert "manifest-invalid" in [error.code for error in report.errors.errors]


def test_loader_rejects_capability_manifest_for_another_provider(tmp_path: Path) -> None:
    _write_extension(tmp_path, capability_manifest=_capability_manifest(provider_id="microsoft"))

    result = load_extension(tmp_path)

    assert not result.ok
    assert result.integrations == []
    assert [error.code for error in result.errors] == ["manifest-invalid"]
    assert "microsoft" in result.errors[0].message


def test_validate_rejects_missing_capability_manifest(tmp_path: Path) -> None:
    _write_extension(tmp_path, capability_manifest=_capability_manifest())
    (tmp_path / "google" / "capabilities.v1.json").unlink()

    report = validate_extension(tmp_path)

    assert not report.ok
    assert [error.code for error in report.errors.errors] == ["manifest-unreadable"]


def test_validate_rejects_action_outside_provider_namespace(tmp_path: Path) -> None:
    capability_manifest = _capability_manifest()
    capability_manifest["capabilities"][0]["id"] = "microsoft.drive.files.search"
    _write_extension(tmp_path, capability_manifest=capability_manifest)

    report = validate_extension(tmp_path)

    assert not report.ok
    assert "provider namespace" in report.errors.errors[0].message


@pytest.mark.skipif(os.name == "nt", reason="symlinks are unreliable on Windows CI")
def test_validate_rejects_capability_manifest_symlink_escape(tmp_path: Path) -> None:
    _write_extension(tmp_path, capability_manifest=_capability_manifest())
    outside = tmp_path.parent / f"{tmp_path.name}-outside-capabilities.json"
    outside.write_text(json.dumps(_capability_manifest()), encoding="utf-8")
    capability_path = tmp_path / "google" / "capabilities.v1.json"
    capability_path.unlink()
    try:
        capability_path.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unsupported in this environment")

    report = validate_extension(tmp_path)

    assert not report.ok
    assert "path-escape" in [error.code for error in report.errors.errors]
