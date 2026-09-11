"""Integration capability-manifest validation and loader exposure."""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from lfx.base.models import provider_registry
from lfx.extension import load_extension, load_extension_bundles, validate_extension
from lfx.extension.bundle_registry import BundleRecord, BundleRegistry
from lfx.extension.integration_conflicts import IntegrationConflictError
from lfx.extension.reload import reload_bundle

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


@pytest.fixture(autouse=True)
def _isolate_registry():
    provider_registry.clear()
    yield
    provider_registry.clear()


def _write_extension(
    tmp_path: Path,
    *,
    capability_manifest: dict | None = None,
    with_provider: bool = False,
    bundle_name: str = "google",
    provider_id: str = "google",
) -> None:
    manifest = {
        "id": f"lfx-{bundle_name}",
        "version": "1.13.0",
        "name": "Google",
        "lfx": {"compat": ["1"]},
        "bundles": [{"name": bundle_name, "path": bundle_name}],
    }
    if with_provider:
        manifest["providers"] = [
            {
                "name": "IntegrationTestProvider",
                "provider_id": "integration-test",
                "metadata": {"mapping": {"model_class": "ChatOpenAI", "model_param": "model"}},
            }
        ]
    if capability_manifest is not None:
        manifest["integrations"] = [{"provider_id": provider_id, "bundle": bundle_name, "path": "capabilities.v1.json"}]
    (tmp_path / "extension.json").write_text(json.dumps(manifest), encoding="utf-8")
    bundle = tmp_path / bundle_name
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
    _write_extension(tmp_path, capability_manifest=_capability_manifest(provider_id="microsoft"), with_provider=True)
    before = provider_registry.get_registry_snapshot()

    result = load_extension(tmp_path)

    assert not result.ok
    assert result.integrations == []
    assert [error.code for error in result.errors] == ["manifest-invalid"]
    assert "microsoft" in result.errors[0].message
    assert provider_registry.get_registry_snapshot() == before


@pytest.mark.parametrize("failure", [None, "manifest-invalid", "module-import-failed"])
def test_multi_bundle_provider_registration_requires_all_bundles_to_load(tmp_path: Path, failure: str | None) -> None:
    _write_extension(tmp_path, capability_manifest=_capability_manifest(), with_provider=True)
    manifest_path = tmp_path / "extension.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["bundles"].append({"name": "microsoft", "path": "microsoft"})
    manifest["integrations"].append({"provider_id": "microsoft", "bundle": "microsoft", "path": "capabilities.v1.json"})
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    bundle = tmp_path / "microsoft"
    bundle.mkdir()
    capability_manifest = _capability_manifest(provider_id="microsoft")
    capability_manifest["capabilities"][0]["id"] = "microsoft.drive.files.search"
    if failure == "manifest-invalid":
        capability_manifest["schema_version"] = 2
    (bundle / "capabilities.v1.json").write_text(json.dumps(capability_manifest), encoding="utf-8")
    component_source = (tmp_path / "google" / "component.py").read_text(encoding="utf-8")
    if failure == "module-import-failed":
        component_source += "\nraise RuntimeError('bundle import failed')\n"
    (bundle / "component.py").write_text(component_source, encoding="utf-8")
    before = provider_registry.get_registry_snapshot()

    results = load_extension_bundles(tmp_path, distribution="lfx-google")

    assert [result.bundle for result in results] == ["google", "microsoft"]
    assert results[0].ok, results[0].errors
    assert results[0].integrations[0].provider_id == "google"
    if failure:
        assert not results[1].ok
        assert [error.code for error in results[1].errors] == [failure]
        assert provider_registry.get_registry_snapshot() == before
    else:
        assert results[1].ok, results[1].errors
        assert results[1].integrations[0].provider_id == "microsoft"
        after = provider_registry.get_registry_snapshot()
        assert after.generation == before.generation + 1
        provider = after.descriptors_by_id["integration-test"]
        assert provider.origin.distribution == "lfx-google"
    assert all(not result.warnings for result in results)


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


def _integration_record(root: Path, bundle_name: str, provider_id: str, policy_key: str) -> BundleRecord:
    root.mkdir()
    capability_manifest = _capability_manifest(provider_id=provider_id)
    capability_manifest["capabilities"][0].update(id=f"{provider_id}.drive.files.search", policy_keys=[policy_key])
    _write_extension(root, capability_manifest=capability_manifest, bundle_name=bundle_name, provider_id=provider_id)
    result = load_extension(root)
    assert result.ok, result.errors
    return BundleRecord(
        bundle=bundle_name,
        extension_id=result.extension_id,
        extension_version=result.extension_version,
        slot="official",
        components=tuple(result.components),
        integrations=tuple(result.integrations),
        source_path=root,
    )


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("collision", ["provider_id", "policy key", "capability id"])
def test_registry_rejects_cross_bundle_identity_collisions(tmp_path: Path, collision: str, *, reverse: bool) -> None:
    first = _integration_record(tmp_path / "first", "first", "google", "google.send")
    second_provider = {
        "provider_id": "google",
        "policy key": "microsoft",
        "capability id": "google.drive",
    }[collision]
    second = _integration_record(
        tmp_path / "second", "second", second_provider, "google.send" if collision == "policy key" else "other.send"
    )
    if collision == "capability id":
        integration = second.integrations[0]
        capability = integration.capability_manifest.capabilities[0].model_copy(
            update={"id": "google.drive.files.search"}
        )
        second = replace(
            second,
            integrations=(
                replace(
                    integration,
                    capability_manifest=integration.capability_manifest.model_copy(
                        update={"capabilities": (capability,)}
                    ),
                ),
            ),
        )
    if reverse:
        first, second = second, first
    index = tmp_path / "components_index.json"
    registry = BundleRegistry(index_path=index)
    registry.install_bundle(first)
    snapshot, index_bytes = registry.snapshot(), index.read_bytes()

    with pytest.raises(IntegrationConflictError, match=collision) as caught:
        registry.install_bundle(second)

    assert all(error.code == "integration-identity-conflict" for error in caught.value.errors)
    assert "lfx-first" in str(caught.value)
    assert "lfx-second" in str(caught.value)
    assert registry.snapshot() == snapshot
    assert index.read_bytes() == index_bytes
    assert registry.list_integrations() == list(first.integrations)


def test_registry_allows_own_reload_and_releases_removed_identity(tmp_path: Path) -> None:
    first = _integration_record(tmp_path / "first", "first", "google", "google.send")
    second = _integration_record(tmp_path / "second", "second", "microsoft", "microsoft.send")
    registry = BundleRegistry()
    registry.install_bundle(first)
    registry.install_bundle(second)
    assert registry.install_bundle(replace(first, extension_version="1.13.1")) == first
    assert len(registry.list_integrations()) == 2
    registry.remove_bundle("first")
    replacement = _integration_record(tmp_path / "replacement", "replacement", "google", "google.send")
    registry.install_bundle(replacement)
    assert {integration.provider_id for integration in registry.list_integrations()} == {"google", "microsoft"}


def test_registry_preserves_policy_grouping_within_one_provider(tmp_path: Path) -> None:
    record = _integration_record(tmp_path / "first", "first", "google", "google.send")
    integration = record.integrations[0]
    capability = integration.capability_manifest.capabilities[0]
    catalog = integration.capability_manifest.model_copy(
        update={"capabilities": (capability, capability.model_copy(update={"id": "google.gmail.send"}))}
    )
    record = replace(record, integrations=(replace(integration, capability_manifest=catalog),))
    registry = BundleRegistry()
    registry.install_bundle(record)
    assert len(registry.list_integrations()[0].capability_manifest.capabilities) == 2


def test_concurrent_integration_claims_cannot_both_install(tmp_path: Path) -> None:
    records = [_integration_record(tmp_path / name, name, "google", "google.send") for name in ("first", "second")]
    registry = BundleRegistry()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(registry.install_bundle, record) for record in records]
    errors = [future.exception() for future in futures]
    assert sum(isinstance(error, IntegrationConflictError) for error in errors) == 1
    assert len(registry.list_integrations()) == 1


def test_conflicting_reload_preserves_live_modules_and_metadata(tmp_path: Path) -> None:
    first = _integration_record(tmp_path / "first", "first", "google", "google.send")
    second = _integration_record(tmp_path / "second", "second", "microsoft", "microsoft.send")
    registry = BundleRegistry()
    registry.install_bundle(first)
    registry.install_bundle(second)
    before = registry.snapshot()
    modules = {name: module for name, module in sys.modules.items() if name.startswith("_lfx_ext.official.")}
    catalog_path = tmp_path / "second" / "second" / "capabilities.v1.json"
    catalog = json.loads(catalog_path.read_text())
    catalog["capabilities"][0]["policy_keys"] = ["google.send"]
    catalog_path.write_text(json.dumps(catalog))

    result = reload_bundle(registry, "second")

    assert not result.ok
    assert result.errors[0].code == "integration-identity-conflict"
    assert registry.snapshot() == before
    assert all(sys.modules[name] is module for name, module in modules.items())
    assert not any(name.startswith("__reload_staging__.") for name in sys.modules)


@pytest.mark.asyncio
async def test_startup_reports_conflict_and_omits_rejected_bundle(tmp_path: Path, monkeypatch) -> None:
    from types import SimpleNamespace

    from lfx.interface import components

    first = _integration_record(tmp_path / "first", "first", "google", "google.send")
    second = _integration_record(tmp_path / "second", "second", "microsoft", "google.send")
    results = [load_extension(record.source_path) for record in (first, second)]
    registry = BundleRegistry()
    monkeypatch.setattr(components, "get_default_registry", lambda: registry)
    monkeypatch.setattr(components, "load_installed_extensions", lambda: results)
    monkeypatch.setattr(components, "load_seed_extensions", list)
    monkeypatch.setattr(components, "load_lfx_bundles_extensions", lambda **_kwargs: [])
    monkeypatch.setattr(components, "load_dev_extensions", list)
    monkeypatch.setattr(components, "discover_inline_bundles", lambda _paths: [])
    monkeypatch.setattr(components, "create_component_template", lambda **_kwargs: ({}, None))
    diagnostics = []
    monkeypatch.setattr(components, "_emit_extension_diagnostics", diagnostics.extend)

    palette = await components.import_extension_components(
        SimpleNamespace(settings=SimpleNamespace(components_path=[]))
    )

    assert palette["first"]
    assert not palette.get("second")
    assert registry.get_bundle("second") is None
    assert len(registry.list_integrations()) == 1
    assert diagnostics[1].errors[0].code == "integration-identity-conflict"


@pytest.mark.parametrize("installed", ["1.12.9", "1.13.0.dev0", "1.13.0rc1", "1.13.0"])
def test_integration_version_diagnostic_precedes_schema_errors(tmp_path: Path, monkeypatch, installed: str) -> None:
    from lfx.extension import integration_compat

    _write_extension(tmp_path, capability_manifest=_capability_manifest())
    monkeypatch.setattr(integration_compat, "version", lambda _name: installed)
    report = validate_extension(tmp_path)
    result = load_extension(tmp_path)
    if installed == "1.12.9":
        for errors in (report.errors.errors, result.errors):
            assert errors[0].code == "lfx-version-too-old"
            assert "1.12.9" in errors[0].message
            assert "lfx>=1.13.0.dev0" in errors[0].message
        assert not result.components
    else:
        assert report.ok
        assert result.ok


def test_legacy_manifest_does_not_require_integration_runtime(tmp_path: Path, monkeypatch) -> None:
    from lfx.extension import integration_compat

    _write_extension(tmp_path)
    monkeypatch.setattr(integration_compat, "version", lambda _name: "1.12.9")
    assert validate_extension(tmp_path).ok
    assert load_extension(tmp_path).ok


@pytest.mark.parametrize("integrations", [[], [{"provider_id": "google", "unrecognized": "value"}]])
def test_old_runtime_identified_before_empty_or_malformed_field(
    tmp_path: Path, monkeypatch, integrations: list
) -> None:
    from lfx.extension import integration_compat

    _write_extension(tmp_path)
    manifest_path = tmp_path / "extension.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["integrations"] = integrations
    manifest_path.write_text(json.dumps(manifest))
    monkeypatch.setattr(integration_compat, "version", lambda _name: "1.12.9")
    assert validate_extension(tmp_path).errors.errors[0].code == "lfx-version-too-old"
    assert load_extension(tmp_path).errors[0].code == "lfx-version-too-old"
