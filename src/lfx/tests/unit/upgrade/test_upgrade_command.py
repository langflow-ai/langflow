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
