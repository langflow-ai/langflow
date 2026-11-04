"""Incomplete discovery cannot produce a successful release registry snapshot."""
# ruff: noqa: SLF001

from types import SimpleNamespace

import component_registry_snapshot as exporter
import pytest


class EntryPoints:
    def __init__(self, bundles):
        self.bundles = bundles

    def select(self, *, group):
        return [object()] if self.bundles and group == "langflow.extensions" else []


def runtime(monkeypatch, *, error=False, missing_template=False, empty=False):
    template = {"template": {"code": {"value": "code"}}, "outputs": []}
    result = SimpleNamespace(
        bundle="example",
        distribution="lfx-example",
        components=[SimpleNamespace(namespaced_id="ext:example:One@official")],
        errors=[SimpleNamespace(code="module-import-failed")] if error else [],
    )
    module = SimpleNamespace()
    module._read_component_index = lambda _path: {"entries": [] if empty else [["core", {"Core": template}]]}
    module._emit_extension_diagnostics = lambda _results: None
    module._merge_component_sources = lambda core, _custom, extensions: {**core, **extensions}

    async def extensions(*, components_path):
        assert components_path == []
        module._emit_extension_diagnostics([result])
        return {"example": {} if missing_template else {"ext:example:One@official": template}}

    module.import_extension_components = extensions
    monkeypatch.setattr(exporter, "_installed", lambda: {"lfx": "1.14.0", "lfx-example": "0.3.0"})
    monkeypatch.setattr(exporter.metadata, "entry_points", lambda: EntryPoints(bundles=True))
    monkeypatch.setattr(exporter.importlib, "import_module", lambda _name: module)
    return module


def test_complete_runtime_registry_keeps_bundle_provenance(monkeypatch):
    module = runtime(monkeypatch)
    original = module._emit_extension_diagnostics
    snapshot = exporter.collect_snapshot()
    assert snapshot["complete"] is True
    assert set(snapshot["all_types"]) == {"core", "example"}
    assert snapshot["component_packages"]["ext:example:One@official"] == "lfx-example"
    assert module._emit_extension_diagnostics is original


@pytest.mark.parametrize("failure", ["error", "missing_template", "empty"])
def test_degraded_runtime_registry_fails_closed(monkeypatch, failure):
    module = runtime(monkeypatch, **{failure: True})
    original = module._emit_extension_diagnostics
    with pytest.raises(exporter.RegistrySnapshotError):
        exporter.collect_snapshot()
    assert module._emit_extension_diagnostics is original


@pytest.mark.parametrize("event", ["socket.connect", "subprocess.Popen", "os.system", "os.posix_spawn"])
def test_export_refuses_provider_network_calls(event):
    with pytest.raises(exporter.RegistrySnapshotError, match="network"):
        exporter._refuse_network(event, ())
    exporter._refuse_network("open", ())


def test_provider_only_bundle_uses_real_model_fields_and_keeps_distribution():
    template = {
        "template": {
            "_type": "LanguageModelComponent",
            "model": {"type": "model"},
            "base_url": {"type": "str", "show": False},
            "other_url": {"type": "str"},
        },
        "outputs": [{"name": "model", "types": ["LanguageModel"]}],
    }
    descriptor = SimpleNamespace(
        name="Example",
        aliases=("Legacy Example",),
        origin=SimpleNamespace(distribution="lfx-example"),
        metadata={
            "variables": [
                {"component_metadata": {"mapping_field": "base_url"}},
                {"component_metadata": {"mapping_field": "not_a_component_field"}},
            ]
        },
    )
    other = SimpleNamespace(
        name="Other",
        aliases=(),
        origin=None,
        metadata={"variables": [{"component_metadata": {"mapping_field": "other_url"}}]},
    )

    def configure(fields, name):
        if name == "Example":
            fields["base_url"]["show"] = True
        return fields

    contracts, packages = exporter.project_provider_contracts(
        {"models": {"LanguageModelComponent": template}},
        {"example": descriptor, "other": other},
        configure,
        {"lfx": "1.14.0", "lfx-example": "0.3.0"},
        "lfx",
    )
    projected = contracts["provider:Example:LanguageModelComponent"]
    assert set(projected["template"]) == {"model", "base_url"}
    assert projected["template"]["base_url"]["show"] is True
    assert packages["provider:Example:LanguageModelComponent"] == "lfx-example"
    assert contracts["provider:Legacy Example:LanguageModelComponent"] == projected
    assert projected["outputs"] == template["outputs"]
    assert template["template"]["base_url"]["show"] is False


def test_provider_projection_uses_only_production_language_model_fields():
    from lfx.base.models import provider_registry, unified_models
    from lfx.interface.components import _read_component_index

    entries = dict(_read_component_index(None)["entries"])
    model = next(
        components["LanguageModelComponent"]
        for components in entries.values()
        if "LanguageModelComponent" in components
    )
    descriptors = provider_registry.get_registry_snapshot(validate_catalogs=False).descriptors_by_id
    core = {key: descriptor for key, descriptor in descriptors.items() if descriptor.origin is None}
    contracts, _packages = exporter.project_provider_contracts(
        entries,
        core,
        unified_models.apply_provider_variable_config_to_build_config,
        {"lfx": "1.14.0"},
        "lfx",
    )
    assert contracts
    for projected in contracts.values():
        assert set(projected["template"]) <= set(model["template"])
        assert projected["outputs"] == model["outputs"]
    assert "api_key" in contracts["provider:OpenAI:LanguageModelComponent"]["template"]


def test_published_settings_argument_does_not_start_application_services(monkeypatch):
    module = runtime(monkeypatch)
    modern = module.import_extension_components

    async def legacy(settings_service):
        assert vars(settings_service.settings) == {"components_path": []}
        return await modern(components_path=settings_service.settings.components_path)

    module.import_extension_components = legacy
    assert exporter.collect_snapshot()["complete"] is True


def test_export_allows_only_the_git_library_local_version_probe():
    exporter._refuse_network("subprocess.Popen", ("git", ["git", "version"]))
    with pytest.raises(exporter.RegistrySnapshotError):
        exporter._refuse_network("subprocess.Popen", ("/bin/sh", ["git", "version"]))
    with pytest.raises(exporter.RegistrySnapshotError):
        exporter._refuse_network("subprocess.Popen", ("git", ["git", "clone", "https://example.test/repo"]))


def test_snapshot_child_clears_credentials_and_installs_denial_before_runtime(monkeypatch, tmp_path):
    import json
    import os
    import sys

    monkeypatch.setattr(
        os,
        "environ",
        {
            "OPENAI_API_KEY": "fixture-provider-value",  # pragma: allowlist secret
            "AWS_SESSION_TOKEN": "fixture-session-value",
            "HOME": "/fixture/original-home",
            "PATH": os.environ.get("PATH", ""),
        },
    )
    output = tmp_path / "snapshot.json"
    monkeypatch.setattr(sys, "argv", ["exporter", "--output", str(output)])
    installed = []
    monkeypatch.setattr(sys, "addaudithook", installed.append)

    def collect():
        assert installed == [exporter._refuse_network]
        assert "OPENAI_API_KEY" not in os.environ
        assert "AWS_SESSION_TOKEN" not in os.environ
        assert os.environ["HOME"] != "/fixture/original-home"
        assert os.environ["LANGFLOW_CONFIG_DIR"].startswith(os.environ["HOME"])
        assert os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] == "True"
        return {"complete": True}

    monkeypatch.setattr(exporter, "collect_snapshot", collect)
    exporter.main()
    assert json.loads(output.read_text()) == {"complete": True}
