"""CLI tests for `lfx upgrade`."""

import json
from unittest.mock import patch

import pytest
from lfx.__main__ import app
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


def test_upgrade_reports_outdated_safe(flow_file):
    with patch("lfx.cli.upgrade.load_registry_from_index", return_value=_registry()):
        result = runner.invoke(app, ["upgrade", str(flow_file)])
    assert result.exit_code == 0
    assert "outdated_safe" in result.output or "safe" in result.output.lower()


def test_upgrade_reports_clean(clean_flow_file):
    with patch("lfx.cli.upgrade.load_registry_from_index", return_value=_registry()):
        result = runner.invoke(app, ["upgrade", str(clean_flow_file)])
    assert result.exit_code == 0
    assert "up to date" in result.output.lower() or "clean" in result.output.lower() or "ok" in result.output.lower()


def test_upgrade_write_updates_file(flow_file):
    with patch("lfx.cli.upgrade.load_registry_from_index", return_value=_registry()):
        result = runner.invoke(app, ["upgrade", "--write", str(flow_file)])
    assert result.exit_code == 0
    updated = json.loads(flow_file.read_text())
    assert updated["nodes"][0]["data"]["node"]["template"]["code"]["value"] == REGISTRY_CODE


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
    with patch("lfx.cli.upgrade.load_registry_from_index", return_value={}):
        result = runner.invoke(app, ["upgrade", str(f)])
    assert result.exit_code != 0


def test_upgrade_file_not_found():
    result = runner.invoke(app, ["upgrade", "/nonexistent/flow.json"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "does not exist" in result.output.lower()


# ---------------------------------------------------------------------------
# Outer-envelope flow handling
# ---------------------------------------------------------------------------


def test_upgrade_outer_envelope_flow_finds_nodes(tmp_path):
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

    with patch("lfx.cli.upgrade.load_registry_from_index", return_value=_registry()):
        result = runner.invoke(app, ["upgrade", str(f)])

    # Must find the outdated node — not falsely report "all up to date"
    assert result.exit_code == 0
    assert "outdated_safe" in result.output or "safe" in result.output.lower(), (
        f"Expected outdated_safe in output but got: {result.output!r}"
    )


def test_upgrade_outer_envelope_write_updates_inner_nodes(tmp_path):
    """--write on an outer-envelope flow must update nodes inside data.nodes."""
    envelope_flow = {
        "name": "My Flow",
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

    with patch("lfx.cli.upgrade.load_registry_from_index", return_value=_registry()):
        result = runner.invoke(app, ["upgrade", "--write", str(f)])

    assert result.exit_code == 0
    written = json.loads(f.read_text())
    # The written file is the unwrapped graph (the data key's content)
    nodes = written.get("nodes", [])
    assert nodes, "Expected nodes in written output"
    assert nodes[0]["data"]["node"]["template"]["code"]["value"] == REGISTRY_CODE
