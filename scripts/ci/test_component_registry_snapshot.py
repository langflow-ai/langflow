"""Incomplete discovery cannot produce a successful release registry snapshot."""
# ruff: noqa: SLF001

import os
import subprocess
import sys
import textwrap
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


@pytest.mark.parametrize(
    "event",
    [
        "socket.connect",
        "subprocess.Popen",
        "os.system",
        "os.posix_spawn",
        "socket.sendmsg",
        "socket.getnameinfo",
        "os.exec",
        "os.spawn",
        "os.fork",
        "os.forkpty",
        "os.startfile",
        "os.startfile/2",
        "pty.spawn",
    ],
)
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


@pytest.mark.component_runtime
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
    trusted_path = {"PATH": os.defpath}
    exporter._refuse_network("subprocess.Popen", ("git", ["git", "version"], None, trusted_path))
    exporter._refuse_network("subprocess.Popen", ("/usr/bin/git", ["/usr/bin/git", "version"], None, trusted_path))
    with pytest.raises(exporter.RegistrySnapshotError):
        exporter._refuse_network("subprocess.Popen", ("/bin/sh", ["git", "version"]))
    with pytest.raises(exporter.RegistrySnapshotError):
        exporter._refuse_network("subprocess.Popen", ("git", ["git", "clone", "https://example.test/repo"]))


def test_git_version_probe_rejects_path_lookalikes_without_executing_them(tmp_path, monkeypatch):
    fake = tmp_path / "git"
    fake.write_text("fixture-only")
    fake.chmod(0o755)
    trusted_path = {"PATH": os.defpath}
    forbidden = [
        ("git", ["git", "version"], None, {"PATH": str(tmp_path)}),
        ("git", ["git", "version"], None, {"PATH": f"{tmp_path}:/usr/bin:/bin"}),
        ("git", ["git", "version"], None, {"PATH": ".:/usr/bin:/bin"}),
        ("git", ["git", "version"], None, {"PATH": ""}),
        (str(fake), ["git", "version"], None, trusted_path),
        ("git", [str(fake), "version"], None, trusted_path),
        ("git", ["git", "version", "extra"], None, trusted_path),
    ]
    for arguments in forbidden:
        with pytest.raises(exporter.RegistrySnapshotError):
            exporter._refuse_network("subprocess.Popen", arguments)
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(exporter.RegistrySnapshotError):
        exporter._refuse_network("subprocess.Popen", ("git", ["git", "version"], None, None))


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
        assert os.environ["PATH"] == os.defpath
        assert os.environ["HOME"] != "/fixture/original-home"
        assert os.environ["LANGFLOW_CONFIG_DIR"].startswith(os.environ["HOME"])
        assert os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] == "True"
        return {"complete": True}

    monkeypatch.setattr(exporter, "collect_snapshot", collect)
    exporter.main()
    assert json.loads(output.read_text()) == {"complete": True}


@pytest.mark.parametrize(
    "event",
    [
        "socket.connect",
        "socket.getaddrinfo",
        "subprocess.Popen",
        "socket.sendmsg",
        "socket.getnameinfo",
        "os.exec",
        "os.spawn",
        "os.fork",
        "os.forkpty",
        "os.startfile",
        "os.startfile/2",
        "pty.spawn",
    ],
)
def test_swallowed_audit_refusal_cannot_publish_complete_snapshot(event, tmp_path):
    output = tmp_path / "snapshot.json"
    script = textwrap.dedent("""
        import importlib.util
        import sys

        output, module_path, event = sys.argv[1:]
        spec = importlib.util.spec_from_file_location("exporter", module_path)
        exporter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(exporter)

        def fallback_registry():
            try:
                sys.audit(event, "fixture-refused-target")
            except exporter.RegistrySnapshotError:
                pass
            return {
                "format_version": 1, "complete": True,
                "distributions": {"lfx": "1.14.0"},
                "all_types": {"core": {"Fallback": {"template": {"code": {"value": "fallback"}}, "outputs": []}}},
                "component_packages": {"Fallback": "lfx"},
            }

        exporter.collect_snapshot = fallback_registry
        sys.argv = ["snapshot", "--output", output]
        exporter.main()
    """)
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script, str(output), exporter.__file__, event],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 1
    assert "incomplete registry cannot be exported" in result.stderr
    assert "fixture-refused-target" not in result.stderr
    assert not output.exists()


def test_export_allows_only_trusted_file_probe_of_current_interpreter(tmp_path):
    python = os.path.realpath(sys.executable)
    trusted_path = {"PATH": os.defpath}
    exporter._refuse_network("subprocess.Popen", ("file", ["file", "-b", python], None, trusted_path))
    interpreter_alias = tmp_path / "python-alias"
    interpreter_alias.symlink_to(python)
    exporter._refuse_network("subprocess.Popen", ("file", ["file", "-b", str(interpreter_alias)], None, trusted_path))
    fake = tmp_path / "file"
    fake.write_text("fixture-only")
    fake.chmod(0o755)
    forbidden = [
        ("/bin/sh", ["file", "-b", python], None, trusted_path),
        ("file", ["file", "-b", "/fixture/other-target"], None, trusted_path),
        ("file", ["file", "-b", python, "/fixture/extra-target"], None, trusted_path),
        ("file", ["file", "-L", python], None, trusted_path),
        ("file", ["file", "-b", python], None, {"PATH": str(tmp_path)}),
        (str(fake), [str(fake), "-b", python], None, trusted_path),
        ("file", ["file", "-b", python], None, {"PATH": ".:/usr/bin:/bin"}),
    ]
    for arguments in forbidden:
        with pytest.raises(exporter.RegistrySnapshotError):
            exporter._refuse_network("subprocess.Popen", arguments)


@pytest.mark.parametrize("program", ["git", "file"])
@pytest.mark.parametrize(
    "extra",
    [
        {"LD_PRELOAD": "/synthetic/unused-library.so"},
        {"UNREVIEWED_ENVIRONMENT": "fixture-only"},
        {"HOME": "/synthetic/unreviewed-home"},
        {"HOME": None},
    ],
)
def test_metadata_probe_rejects_injected_environment(program, extra):
    argv = [program, "version"] if program == "git" else [program, "-b", os.path.realpath(sys.executable)]
    previous = len(exporter._refused_calls)
    with pytest.raises(exporter.RegistrySnapshotError):
        exporter._refuse_network("subprocess.Popen", (program, argv, None, {"PATH": os.defpath, **extra}))
    assert exporter._refused_calls[previous:] == ["subprocess.Popen"]


def test_malformed_probe_environment_keeps_refusal_evidence():
    from collections.abc import Mapping

    class BrokenEnvironment(Mapping):
        def __getitem__(self, _key):
            raise RuntimeError("synthetic environment lookup failure")

        def __iter__(self):
            return iter(("PATH",))

        def __len__(self):
            return 1

    previous = len(exporter._refused_calls)
    with pytest.raises(exporter.RegistrySnapshotError):
        exporter._refuse_network("subprocess.Popen", ("git", ["git", "version"], None, BrokenEnvironment()))
    assert exporter._refused_calls[previous:] == ["subprocess.Popen"]


@pytest.mark.parametrize("program", ["git", "file"])
def test_metadata_probe_keeps_the_known_runtime_flag_unchanged(program, monkeypatch):
    monkeypatch.setenv("OTEL_SEMCONV_STABILITY_OPT_IN", "http")
    argv = [program, "version"] if program == "git" else [program, "-b", os.path.realpath(sys.executable)]
    environment = {"PATH": os.defpath, "OTEL_SEMCONV_STABILITY_OPT_IN": "http"}
    previous = len(exporter._refused_calls)
    exporter._refuse_network("subprocess.Popen", (program, argv, None, environment))
    assert len(exporter._refused_calls) == previous
    with pytest.raises(exporter.RegistrySnapshotError):
        exporter._refuse_network(
            "subprocess.Popen", (program, argv, None, {**environment, "OTEL_SEMCONV_STABILITY_OPT_IN": "changed"})
        )
    assert exporter._refused_calls[previous:] == ["subprocess.Popen"]
