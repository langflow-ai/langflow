"""CLI compatibility checks must recognize installed provider components."""

import asyncio
import copy
import json

import pytest
import typer
from lfx.cli.upgrade import load_registry_from_index, upgrade_command
from lfx.upgrade.cli_gate import UpgradeFlowError, apply_upgrade_gate

COMPONENT_ID = "ext:smoke:SmokeComponent@official"
CURRENT_CODE = "class SmokeComponent:\n    pass  # current"
OLD_CODE = "class SmokeComponent:\n    pass  # previous"


def _template(code=CURRENT_CODE):
    return {
        "template": {"code": {"value": code}},
        "outputs": [],
        "metadata": {},
    }


def _flow(code=CURRENT_CODE):
    return {
        "nodes": [
            {
                "id": "smoke-node",
                "data": {"type": COMPONENT_ID, "node": {"display_name": "Smoke", **_template(code)}},
            }
        ],
        "edges": [],
    }


@pytest.fixture
def extension_registry(monkeypatch):
    # Discovery/template construction is independently covered by the extension
    # tests. Exercise the CLI's real default registry selection and checker here.
    extensions = {"smoke": {COMPONENT_ID: _template()}}
    core = {"entries": [("smoke", {"CoreComponent": _template()})]}
    monkeypatch.setattr("lfx.interface.components._read_component_index", lambda _: copy.deepcopy(core))

    async def load_extensions(_settings):
        await asyncio.sleep(0)
        return copy.deepcopy(extensions)

    monkeypatch.setattr("lfx.interface.components.import_extension_components", load_extensions)
    return extensions


@pytest.mark.usefixtures("extension_registry")
def test_upgrade_recognizes_installed_bundle(tmp_path, capsys):
    path = tmp_path / "flow.json"
    original = json.dumps(_flow())
    path.write_text(original)

    upgrade_command(path, write=False, strict=True)

    assert "All components are up to date" in capsys.readouterr().out
    assert path.read_text() == original
    assert set(load_registry_from_index()["smoke"]) == {"CoreComponent", COMPONENT_ID}


@pytest.mark.usefixtures("extension_registry")
def test_upgrade_writes_safe_bundle_update(tmp_path):
    path = tmp_path / "flow.json"
    path.write_text(json.dumps({"name": "Saved bundle flow", "data": _flow(OLD_CODE)}))

    upgrade_command(path, write=True, strict=True)

    assert json.loads(path.read_text()) == {"name": "Saved bundle flow", "data": _flow()}


@pytest.mark.asyncio
@pytest.mark.usefixtures("extension_registry")
@pytest.mark.parametrize("mode", ["check", "safe"])
async def test_run_serve_gate_recognizes_bundle_inside_event_loop(mode):
    flow = _flow(OLD_CODE if mode == "safe" else CURRENT_CODE)

    result, count = apply_upgrade_gate(flow, mode=mode)

    assert result == _flow()
    assert count == (1 if mode == "safe" else 0)


def test_uninstalled_bundle_still_blocks(extension_registry, tmp_path):
    extension_registry.clear()
    path = tmp_path / "flow.json"
    path.write_text(json.dumps(_flow()))

    with pytest.raises(typer.Exit) as exc:
        upgrade_command(path, write=True)
    assert exc.value.exit_code == 1
    with pytest.raises(UpgradeFlowError, match=r"Smoke .*blocked"):
        apply_upgrade_gate(_flow(), mode="safe")
    assert json.loads(path.read_text()) == _flow()


@pytest.mark.parametrize("core", [None, {}, {"entries": []}])
@pytest.mark.usefixtures("extension_registry")
def test_extensions_do_not_hide_missing_core_index(monkeypatch, core):
    monkeypatch.setattr("lfx.interface.components._read_component_index", lambda _: core)

    with pytest.raises(typer.Exit):
        load_registry_from_index()
    with pytest.raises(UpgradeFlowError, match="bundled component registry is empty or missing"):
        apply_upgrade_gate(_flow(), mode="check")


@pytest.mark.usefixtures("extension_registry")
def test_discovery_failure_uses_cli_error_channel(monkeypatch, capsys):
    async def fail_discovery(_settings):
        msg = "fixture discovery failure"
        raise RuntimeError(msg)

    monkeypatch.setattr("lfx.interface.components.import_extension_components", fail_discovery)

    with pytest.raises(typer.Exit) as exc:
        load_registry_from_index()
    assert exc.value.exit_code == 1
    error = capsys.readouterr().err
    assert "could not load the extension component registry" in error
    assert "fixture discovery failure" not in error
    with pytest.raises(UpgradeFlowError, match="could not load the extension component registry"):
        apply_upgrade_gate(_flow(), mode="check")
