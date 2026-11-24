"""CLI tests for `lfx upgrade`."""

import json

import pytest
import typer
from lfx.__main__ import app
from lfx.cli.upgrade import upgrade_command
from typer.testing import CliRunner

runner = CliRunner()

REGISTRY_CODE = "class MyComp:\n    pass  # v2"
NODE_CODE = "class MyComp:\n    pass  # v1"


def _flow_json(code=NODE_CODE):
    return json.dumps(
        {
            "nodes": [
                {
                    "id": "n1",
                    "data": {
                        "id": "n1",
                        "type": "MyComp",
                        "node": {
                            "display_name": "My Component",
                            "edited": False,
                            "template": {"code": {"value": code}},
                            "outputs": [
                                {"name": "o", "display_name": "O", "types": ["M"], "method": "m", "allows_loop": False}
                            ],
                        },
                    },
                }
            ],
            "edges": [],
        }
    )


def _registry():
    return {
        "Cat": {
            "MyComp": {
                "template": {"code": {"value": REGISTRY_CODE}},
                "outputs": [{"name": "o", "display_name": "O", "types": ["M"], "method": "m", "allows_loop": False}],
                "metadata": {},
            }
        }
    }


@pytest.fixture
def flow_file(tmp_path):
    f = tmp_path / "flow.json"
    f.write_text(_flow_json(code=NODE_CODE))
    return f


@pytest.fixture
def clean_flow_file(tmp_path):
    f = tmp_path / "flow.json"
    f.write_text(_flow_json(code=REGISTRY_CODE))
    return f


def test_upgrade_reports_outdated_safe(flow_file, capsys):
    upgrade_command(flow_file, write=False, registry=_registry())
    captured = capsys.readouterr()
    assert "outdated_safe" in captured.out or "safe" in captured.out.lower()


def test_upgrade_reports_clean(clean_flow_file, capsys):
    upgrade_command(clean_flow_file, write=False, registry=_registry())
    captured = capsys.readouterr()
    assert "up to date" in captured.out.lower() or "clean" in captured.out.lower() or "ok" in captured.out.lower()


def test_upgrade_write_updates_file(flow_file):
    upgrade_command(flow_file, write=True, registry=_registry())
    updated = json.loads(flow_file.read_text())
    assert updated["nodes"][0]["data"]["node"]["template"]["code"]["value"] == REGISTRY_CODE


def test_upgrade_bare_flow_write_keeps_flat_shape(flow_file):
    """A bare (non-enveloped) flow written with --write stays flat: no spurious {"data": ...} wrapper.

    Only enveloped flows get re-wrapped on write; a flat graph must round-trip as a flat graph.
    """
    upgrade_command(flow_file, write=True, registry=_registry())
    written = json.loads(flow_file.read_text())
    assert "data" not in written  # still a bare graph, not wrapped in an envelope
    assert "nodes" in written
    assert written["nodes"][0]["data"]["node"]["template"]["code"]["value"] == REGISTRY_CODE


def test_upgrade_exits_nonzero_when_blocked(tmp_path):
    f = tmp_path / "flow.json"
    f.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "n1",
                        "data": {
                            "id": "n1",
                            "type": "GhostComponent",
                            "node": {
                                "display_name": "Ghost",
                                "edited": False,
                                "template": {"code": {"value": "some code"}},
                                "outputs": [],
                            },
                        },
                    }
                ],
                "edges": [],
            }
        )
    )
    with pytest.raises(typer.Exit) as exc_info:
        upgrade_command(f, write=False, registry={})
    assert exc_info.value.exit_code != 0


def test_upgrade_file_not_found():
    result = runner.invoke(app, ["upgrade", "/nonexistent/flow.json"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "does not exist" in result.output.lower()


# ---------------------------------------------------------------------------
# Outer-envelope flow handling
# ---------------------------------------------------------------------------


def test_upgrade_outer_envelope_flow_finds_nodes(tmp_path, capsys):
    """Lfx upgrade must detect nodes in Langflow's exported outer-envelope format.

    Langflow exports flows as {"name": "...", "data": {"nodes": [...], "edges": []}}.
    Before the fix, check_flow_compatibility received the outer dict, got nodes=[], and
    always reported 'all up to date' regardless of actual node state.
    """
    envelope_flow = {
        "name": "My Flow",
        "description": "test",
        "data": {
            "nodes": [
                {
                    "id": "n1",
                    "data": {
                        "id": "n1",
                        "type": "MyComp",
                        "node": {
                            "display_name": "My Component",
                            "edited": False,
                            "template": {"code": {"value": NODE_CODE}},
                            "outputs": [
                                {"name": "o", "display_name": "O", "types": ["M"], "method": "m", "allows_loop": False}
                            ],
                        },
                    },
                }
            ],
            "edges": [],
        },
    }
    f = tmp_path / "flow.json"
    f.write_text(json.dumps(envelope_flow))

    upgrade_command(f, write=False, registry=_registry())
    captured = capsys.readouterr()

    # Must find the outdated node — not falsely report "all up to date"
    assert "outdated_safe" in captured.out or "safe" in captured.out.lower(), (
        f"Expected outdated_safe in output but got: {captured.out!r}"
    )


def test_upgrade_outer_envelope_write_updates_inner_nodes(tmp_path):
    """--write on an outer-envelope flow must update nodes inside data.nodes AND preserve envelope metadata."""
    envelope_flow = {
        "name": "My Flow",
        "description": "envelope flow",
        "endpoint_name": "my-endpoint",
        "is_component": False,
        "tags": ["fixture"],
        "data": {
            "nodes": [
                {
                    "id": "n1",
                    "data": {
                        "id": "n1",
                        "type": "MyComp",
                        "node": {
                            "display_name": "My Component",
                            "edited": False,
                            "template": {"code": {"value": NODE_CODE}},
                            "outputs": [
                                {"name": "o", "display_name": "O", "types": ["M"], "method": "m", "allows_loop": False}
                            ],
                        },
                    },
                }
            ],
            "edges": [],
        },
    }
    f = tmp_path / "flow.json"
    f.write_text(json.dumps(envelope_flow))

    upgrade_command(f, write=True, registry=_registry())

    written = json.loads(f.read_text())
    # The envelope must be preserved on write so the flow remains re-importable into Langflow.
    assert written.get("name") == "My Flow"
    assert written.get("description") == "envelope flow"
    assert written.get("endpoint_name") == "my-endpoint"
    assert written.get("is_component") is False
    assert written.get("tags") == ["fixture"]
    nodes = written.get("data", {}).get("nodes", [])
    assert nodes, "Expected nodes inside data.nodes"
    assert nodes[0]["data"]["node"]["template"]["code"]["value"] == REGISTRY_CODE


# ---------------------------------------------------------------------------
# fail-fast when the bundled registry is empty/missing
# ---------------------------------------------------------------------------


def test_load_registry_from_index_raises_when_empty(monkeypatch):
    """A missing/empty bundled registry must fail loudly, not silently classify all-blocked."""
    from lfx.cli.upgrade import load_registry_from_index

    monkeypatch.setattr("lfx.interface.components._read_component_index", lambda _: None)
    with pytest.raises(typer.Exit) as exc_info:
        load_registry_from_index()
    assert exc_info.value.exit_code != 0


# ---------------------------------------------------------------------------
# --strict treats pending safe upgrades as drift
# ---------------------------------------------------------------------------


def test_strict_exits_nonzero_on_pending_safe(flow_file):
    with pytest.raises(typer.Exit) as exc_info:
        upgrade_command(flow_file, write=False, strict=True, registry=_registry())
    assert exc_info.value.exit_code != 0


def test_strict_with_write_exits_zero(flow_file):
    # --write applies the safe upgrade, so --strict has no remaining drift to fail on.
    upgrade_command(flow_file, write=True, strict=True, registry=_registry())
    updated = json.loads(flow_file.read_text())
    assert updated["nodes"][0]["data"]["node"]["template"]["code"]["value"] == REGISTRY_CODE


def test_strict_clean_exits_zero(clean_flow_file):
    # No pending upgrades -> --strict is a no-op and the command succeeds.
    upgrade_command(clean_flow_file, write=False, strict=True, registry=_registry())


def test_non_strict_pending_safe_exits_zero(flow_file):
    # Default (no --strict): pending safe upgrades do not fail the command.
    upgrade_command(flow_file, write=False, strict=False, registry=_registry())
