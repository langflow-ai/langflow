"""``langflow upgrade-check`` run as an admin runs it: a subprocess on the reader's fixture databases."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict
from typing import TYPE_CHECKING

import pytest
from langflow.upgrade_check.engine import TargetSettings

from tests.unit.upgrade_check.test_engine import _add_flow, _hard_flow, _older_code
from tests.unit.upgrade_check.test_reader import RELEASES, _execute, _load, _url

if TYPE_CHECKING:
    from pathlib import Path

PRINTS_WHEN_LOADED = """
from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.message import Message

print("hello from a custom component")


class HelloComponent(Component):
    display_name = "Hello"
    inputs = [MessageTextInput(name="text", display_name="Text")]
    outputs = [Output(display_name="Text", name="text_output", method="build_text")]

    def build_text(self) -> Message:
        return Message(text=self.text)
"""


def _upgrade_check(*args, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "langflow", "upgrade-check", *map(str, args)],
        env=env or {**os.environ, "DO_NOT_TRACK": "true"},
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )


def _events(result: subprocess.CompletedProcess) -> list[dict]:
    """Every stdout line is one event; anything else fails here."""
    return [json.loads(line) for line in result.stdout.splitlines()]


def _components(folder: Path) -> Path:
    (folder / "mine").mkdir(parents=True)
    (folder / "mine" / "hello.py").write_text(PRINTS_WHEN_LOADED)
    return folder


def _default_settings(**changes) -> dict:
    return json.loads(json.dumps({**asdict(TargetSettings()), **changes}))


def test_clean_source_streams_every_flow_then_the_report(tmp_path):
    database = _load("1.13.0", tmp_path)
    components = _components(tmp_path / "components")
    output = tmp_path / "report.json"

    result = _upgrade_check(
        "--database-url", _url(database), "--components-path", components, "--json", "--output", output
    )

    assert result.returncode == 0, result.stderr
    events = _events(result)
    assert [event["event"] for event in events] == ["flow", "flow", "flow", "report"]
    assert {(event["flow"]["kind"], event["flow"]["status"]) for event in events[:-1]} == {
        ("flow", "ok"),
        ("component", "ok"),
        ("flow_version", "ok"),
    }
    report = events[-1]["report"]
    assert json.loads(output.read_text()) == report
    assert report["format_version"] == 1
    assert report["source"] == {
        "dialect": "sqlite",
        "alembic_revision": RELEASES["1.13.0"][0],
        "counts": {"flows": 1, "components": 1, "flow_versions": 1},
    }
    # The custom component loaded, and what it printed went to stderr, not into the events.
    assert report["target"]["custom_components"] == {"path": [str(components)], "count": 1}
    assert "hello from a custom component" in result.stderr
    assert report["settings"] == {
        **_default_settings(components_path=[str(components)]),
        "catalog_rules": {"from": "policy_bundle_active", "blocked_component_keys": [], "blocked_template_keys": []},
    }
    assert report["summary"]["flows"] == {"ok": 3, "warn": 0, "fail": 0}
    assert (report["flows"], report["errors"]) == ([], [])


def test_check_reads_nothing_of_the_server_and_writes_nowhere(tmp_path):
    """The server's LANGFLOW_ variables are ignored, and the check's own config dir is gone at the end.

    An MCP Tools node builds Langflow's settings when it is created, which saves a secret key.
    """
    database = _load("1.10.0", tmp_path)
    mcp_flow = _older_code(_hard_flow("v1.13.0", "mcp_tools_arguments.json"), "MCPTools")
    _add_flow(database, "MCP flow", data=json.dumps(mcp_flow), is_component=0)
    before = database.read_bytes()
    server, home, tmp = tmp_path / "server", tmp_path / "home", tmp_path / "tmp"
    components = _components(server / "components")
    home.mkdir()
    tmp.mkdir()
    env = {name: value for name, value in os.environ.items() if not name.startswith("LANGFLOW_")}
    env.update(
        HOME=str(home),
        TMPDIR=str(tmp),
        DO_NOT_TRACK="true",
        LANGFLOW_CONFIG_DIR=str(server / "config"),
        LANGFLOW_DATABASE_URL=f"sqlite:///{server / 'langflow.db'}",
        LANGFLOW_COMPONENTS_PATH=str(components),
        LANGFLOW_ALLOW_CUSTOM_COMPONENTS="false",
    )
    output = tmp_path / "report.json"

    result = _upgrade_check("--database-url", _url(database), "--json", "--output", output, env=env)

    assert result.returncode == 1, result.stderr
    events = _events(result)
    statuses = {event["flow"]["name"]: event["flow"]["status"] for event in events[:-1]}
    assert statuses == {"Fixture nested groups": "ok", "Fixture saved component": "ok", "MCP flow": "fail"}
    report = events[-1]["report"]
    assert json.loads(output.read_text()) == report
    # Every flow with a node to update is listed, ok ones too, and its nodes say what the update does.
    listed = {flow["name"]: flow for flow in report["flows"]}
    assert {name: flow["status"] for name, flow in listed.items()} == statuses
    for name in ("Fixture nested groups", "Fixture saved component"):
        assert {(node["status"], node["dry_run"]["result"]) for node in listed[name]["nodes"]} == {
            ("outdated_safe", "keeps")
        }
    mcp_nodes = [(node["type"], node["status"]) for node in listed["MCP flow"]["nodes"]]
    assert mcp_nodes == [("MCPTools", "outdated_breaking")]
    # Defaults, not the server's variables: custom code allowed, no components path.
    assert {key: value for key, value in report["settings"].items() if key != "catalog_rules"} == _default_settings()
    assert report["target"]["custom_components"] == {"path": [], "count": 0}
    assert "hello from a custom component" not in result.stderr
    assert sorted(path.relative_to(server).as_posix() for path in server.rglob("*")) == [
        "components",
        "components/mine",
        "components/mine/hello.py",
    ]
    assert list(home.iterdir()) == []
    assert list(tmp.iterdir()) == []
    assert database.read_bytes() == before


def test_failing_flow_exits_1_and_says_why(tmp_path):
    """Without custom code or substitution, the upgraded server refuses the outdated nodes."""
    database = _load("1.10.0", tmp_path)

    result = _upgrade_check(
        "--database-url",
        _url(database),
        "--no-allow-custom-components",
        "--no-substitute-outdated-component-code",
    )

    assert result.returncode == 1, result.stderr
    assert "0 ok, 0 warn, 2 fail" in result.stdout
    assert "fail  flow 'Fixture nested groups'" in result.stdout
    assert "Chat Output (" in result.stdout
    assert "outdated_safe, runs refused" in result.stdout
    assert "Fix what is marked fail before the upgrade." in result.stdout


def test_unreadable_catalog_rules_block_the_upgrade(tmp_path):
    database = _load("1.13.0", tmp_path)
    _execute(
        database,
        "UPDATE policy_bundle_revision SET blocked_template_keys = 'not json'"
        " WHERE revision = (SELECT revision FROM policy_bundle_active)",
    )

    result = _upgrade_check("--database-url", _url(database), "--json")

    assert result.returncode == 1, result.stderr
    report = _events(result)[-1]["report"]
    assert report["summary"]["flows"] == {"ok": 3, "warn": 0, "fail": 0}
    [error] = report["errors"]
    assert (error["kind"], error["status"]) == ("catalog_rules", "fail")
    assert "blocked_template_keys could not be read" in error["message"]


@pytest.mark.parametrize("as_json", [False, True], ids=["text", "json"])
def test_a_check_that_cannot_finish_exits_2(as_json, tmp_path):
    missing = tmp_path / "missing.db"

    result = _upgrade_check("--database-url", _url(missing), *(["--json"] if as_json else []))

    assert result.returncode == 2
    message = f"cannot read the source database: FileNotFoundError: no SQLite database at {missing}"
    if as_json:
        [event] = _events(result)
        assert (event["event"], event["code"]) == ("error", "source_unreadable")
        assert event["message"].startswith(message)
    else:
        assert result.stdout == ""
        assert f"The upgrade check could not finish: {message}" in result.stderr
