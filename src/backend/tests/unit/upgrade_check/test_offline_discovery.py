"""Offline discovery refuses synthetic transports before dispatch and never reports a partial registry."""

from __future__ import annotations

import os
import sys
import threading
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest
from langflow.upgrade_check import command, engine
from langflow.upgrade_check.engine import TargetSettings
from langflow.upgrade_check.isolation import child_environment, resolve_input_paths
from langflow.upgrade_check.reader import SourceDatabase

from tests.unit.upgrade_check.test_command import _events, _upgrade_check
from tests.unit.upgrade_check.test_reader import _load, _url


def _options(tmp_path):
    return {
        "database_url": _url(_load("1.13.0", tmp_path)),
        "settings": asdict(TargetSettings()),
        "json": True,
        "output": None,
    }


@pytest.mark.parametrize("phase", ["extension_import", "constructor", "template", "custom_folder"])
def test_registry_refuses_network_before_discovery_callbacks_even_when_loader_swallows_it(monkeypatch, tmp_path, phase):
    options = _options(tmp_path)
    options["settings"]["components_path"] = [str(tmp_path)]
    calls = []

    def callback(*, swallow=True):
        try:
            sys.audit("socket.connect", None, ("synthetic.invalid", 443))
        except ConnectionRefusedError:
            calls.append("refused")
            if not swallow:
                raise
        else:
            calls.append("would_dispatch")

    async def extensions(**_kwargs):
        if phase == "extension_import":
            callback()

        class FixtureComponent:
            def __init__(self):
                if phase == "constructor":
                    callback()

            def template(self):
                if phase == "template":
                    callback()

        FixtureComponent().template()
        return {}

    async def custom(_paths):
        if phase == "custom_folder":
            from lfx.custom.directory_reader.directory_reader import DirectoryReader

            monkeypatch.setattr("lfx.custom.utils.build_component", lambda _component: callback(swallow=False))
            reader = DirectoryReader(str(tmp_path))
            reader.filter_loaded_components(
                {
                    "menu": [
                        {
                            "name": "fixture",
                            "path": str(tmp_path),
                            "components": [{"name": "Fixture", "file": "fixture.py", "error": None}],
                        }
                    ]
                },
                with_errors=False,
            )
        return {}

    monkeypatch.setattr("lfx.interface.components.import_extension_components", extensions)
    monkeypatch.setattr("lfx.custom.utils.abuild_custom_components", custom)
    events = []

    with pytest.raises(command.CheckError, match="network") as caught:
        command.run(options, events.append)

    assert caught.value.code == "registry_unavailable"
    assert calls == ["refused"]
    assert events == []


def test_registry_timeout_keeps_callbacks_offline_until_worker_finishes(monkeypatch, tmp_path):
    options = _options(tmp_path)
    entered, release, refused = threading.Event(), threading.Event(), threading.Event()

    def discover(**_kwargs):
        entered.set()
        release.wait(2)
        try:
            sys.audit("socket.getaddrinfo", "synthetic.invalid", 443, 0, 0, 0)
        except ConnectionRefusedError:
            refused.set()
        return {}

    monkeypatch.setattr(command, "load_upgrade_registry", discover)
    monkeypatch.setattr(engine, "REGISTRY_SECONDS", 0.02, raising=False)
    try:
        with pytest.raises(command.CheckError, match="did not finish") as caught:
            command.run(options)
        assert caught.value.code == "registry_unavailable"
        assert entered.is_set()
        with pytest.raises(ConnectionRefusedError):
            sys.audit("socket.getaddrinfo", "synthetic.invalid", 443, 0, 0, 0)
    finally:
        release.set()
        for worker in threading.enumerate():
            if worker.name == "upgrade-check-registry":
                worker.join(2)
    assert refused.is_set()
    sys.audit("socket.getaddrinfo", "synthetic.invalid", 443, 0, 0, 0)


def test_child_environment_excludes_provider_credentials_and_original_home(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    inherited = {
        "PATH": "/runtime/bin",
        "PYTHONPATH": os.pathsep.join(["src", "../shared", ""]),
        "HOME": "/original/home",
        "AWS_ACCESS_KEY_ID": "fixture-aws-key",
        "OPENAI_API_KEY": "fixture-openai-key",  # pragma: allowlist secret
        "GOOGLE_APPLICATION_CREDENTIALS": "/original/credentials.json",
        "FUTURE_PROVIDER_TOKEN": "fixture-provider-token",  # pragma: allowlist secret
        "LANGFLOW_DATABASE_URL": "sqlite:////original/server.db",
        "HTTP_PROXY": "http://fixture.invalid",
    }
    environment = child_environment(str(tmp_path / "isolated"), inherited)
    assert set(environment) & set(inherited) == {"PATH", "PYTHONPATH", "HOME"}
    assert environment["PATH"] == os.defpath
    assert environment["PYTHONPATH"] == os.pathsep.join(
        map(str, [tmp_path / "src", tmp_path.parent / "shared", tmp_path])
    )
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        assert environment[key] == str(tmp_path / "isolated")
    assert inherited["HOME"] == "/original/home"
    assert environment["LITELLM_LOCAL_MODEL_COST_MAP"] == "True"


def test_input_paths_resolve_against_caller_directory_without_mutating_options(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    options = {
        "database_url": "sqlite:///source.db?token=fixture-token",
        "serving_database_url": "sqlite:///~/serving.db",
        "settings": {"components_path": ["components", "~/custom"]},
        "output": "report.json",
    }
    original = deepcopy(options)
    selected = resolve_input_paths(options)
    assert selected["database_url"] == f"sqlite:///{tmp_path}/source.db?token=fixture-token"
    assert selected["serving_database_url"] == f"sqlite:///{tmp_path}/home/serving.db"
    assert selected["settings"]["components_path"] == [str(tmp_path / "components"), str(tmp_path / "home/custom")]
    assert selected["output"] == str(tmp_path / "report.json")
    assert options == original


def test_selected_source_pages_remain_outside_component_callback_guard(monkeypatch, tmp_path):
    options = _options(tmp_path)
    original = SourceDatabase.flows
    pages_read = []

    def flows(source):
        sys.audit("socket.getaddrinfo", "synthetic-source.invalid", 5432, 0, 0, 0)
        pages_read.append(True)
        yield from original(source)

    monkeypatch.setattr(SourceDatabase, "flows", flows)
    monkeypatch.setattr(command, "load_upgrade_registry", lambda **_kwargs: {})
    report, _listed = command.run(options)
    assert pages_read == [True]
    assert report["source"]["counts"] == {"flows": 1, "components": 1, "flow_versions": 1}


def test_relative_cli_source_and_output_survive_isolated_working_directory(monkeypatch, tmp_path):
    source = _load("1.13.0", tmp_path)
    before = source.read_bytes()
    monkeypatch.chdir(tmp_path)
    result = _upgrade_check("--database-url", f"sqlite:///{source.name}", "--output", "report.json", "--json")
    assert result.returncode == 0, result.stderr
    report = _events(result)[-1]["report"]
    assert report["source"]["identity"]["locator"]["path"] == str(source)
    assert Path("report.json").is_file()
    assert source.read_bytes() == before
