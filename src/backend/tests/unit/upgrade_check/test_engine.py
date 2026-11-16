"""The upgrade check's engine, run on real databases, real flows, and real components.

The databases are the reader's fixtures (see ``test_reader.py``). The hard flows and their expected
statuses are the shared rule's (``src/lfx/tests/data/component_compat``).
"""

from __future__ import annotations

import asyncio
import copy
import dataclasses
import importlib.metadata
import json
import os
import socket
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path
from uuid import uuid4

import pytest
from langchain_core.tools import StructuredTool
from langflow.upgrade_check import engine, open_source
from langflow.upgrade_check.engine import Target, TargetSettings, check_nodes, check_source, flow_status
from lfx.custom.custom_component.component import Component
from lfx.custom.utils import build_custom_component_template
from lfx.graph.graph.base import Graph
from lfx.upgrade.checker import breaking_reasons, iter_flow_nodes
from lfx.upgrade.registry import load_upgrade_registry

from tests.unit.upgrade_check.test_reader import RELEASES, _block_components, _execute, _load, _url

REPO = Path(__file__).parents[5]
COMPAT = REPO / "src" / "lfx" / "tests" / "data" / "component_compat"
OWNER = "12194f5d-e334-4af8-a54e-2841bea9bce4"

# The four components 1.13 retired live in lfx-bundles, which this environment may not have.
LFX_BUNDLES_NODES = {
    "altk_agent.json::ext:altk:ALTKAgentComponent@official-e6331": "altk",
    "chroma_ext_type.json::ext:chroma:ChromaVectorStoreComponent@official-51b51": "chroma",
    "chroma_legacy_type.json::Chroma-9e7b2": "chroma",
    "local_db.json::ext:chroma:LocalDBComponent@official-6852a": "chroma",
}


@pytest.fixture(scope="module")
def all_types():
    return load_upgrade_registry(components_path=[])


@pytest.fixture(scope="module")
def target(all_types):
    return Target.from_registry(all_types)


def _with(target: Target, entries: dict) -> Target:
    """``target`` with other upgrade-rule entries, as a later release could ship them."""
    return dataclasses.replace(target, lookup={**target.lookup, **entries})


def _hard_flow(release: str, name: str) -> dict:
    return json.loads((COMPAT / "hard_flows" / release / name).read_text(encoding="utf-8"))["data"]


def _node(flow: dict, node_id: str) -> dict:
    return next(node for node in flow["nodes"] if node["id"] == node_id)


def _new_code(entry: dict, code: str) -> dict:
    """``entry`` as a later release ships it: other code, and the template that code builds."""
    template, _ = build_custom_component_template(Component(_code=code))
    return {**copy.deepcopy(entry), **template}


def _add_flow(database: Path, name: str, **columns) -> None:
    """Copy the fixture's saved component into a new row, changing ``columns``."""
    connection = sqlite3.connect(database)
    connection.execute("CREATE TEMP TABLE copy AS SELECT * FROM flow WHERE name = 'Fixture saved component'")
    changes = {"id": uuid4().hex, "name": name, "endpoint_name": None, **columns}
    assignments = ", ".join(f"{column} = ?" for column in changes)  # the column names are this test's own
    connection.execute(f"UPDATE copy SET {assignments}", list(changes.values()))  # noqa: S608
    connection.execute("INSERT INTO flow SELECT * FROM copy")
    connection.commit()
    connection.close()


@pytest.mark.parametrize("release", RELEASES)
def test_checks_every_flow_each_release_saved(release, target, tmp_path):
    database = _load(release, tmp_path)

    with open_source(_url(database)) as source:
        results = list(check_source(source, target))
        project = next(project for project in source.projects if project.name == "Fixture project")
        raw = {flow.name: flow.data for flow in source.flows()}

    has_triggers = RELEASES[release][1]
    # Flows come in id order, then the running versions.
    by_kind = {(result.kind, result.name): result for result in results}
    assert len(by_kind) == len(results)
    assert set(by_kind) == {
        ("flow", "Fixture nested groups"),
        ("component", "Fixture saved component"),
        *([("flow_version", "Fixture nested groups")] if has_triggers else []),
    }
    for result in results:
        assert result.owner["username"] == "langflow"
        assert result.project == {"id": project.id, "name": project.name}
        assert result.status == "ok"
        # Saved I/O nodes update without losing anything.
        assert {(node.status, node.dry_run["result"]) for node in result.nodes} <= {("outdated_safe", "keeps")}
    flow, component = by_kind["flow", "Fixture nested groups"], by_kind["component", "Fixture saved component"]
    assert len(flow.nodes) + flow.ok_nodes == 3
    assert len(component.nodes) + component.ok_nodes == 1
    if has_triggers:
        version = by_kind["flow_version", "Fixture nested groups"]
        assert (version.flow_id, version.version_number) == (flow.id, 1)
        assert len(version.used_by["triggers"]) == 1

    # A node in a group inside a group reports both groups, outermost first.
    [outer] = [node for node in raw["Fixture nested groups"]["nodes"] if node["data"]["node"].get("flow")]
    inner_nodes = outer["data"]["node"]["flow"]["data"]["nodes"]
    [inner] = [node for node in inner_nodes if node["data"]["node"].get("flow")]
    paths = {
        "ChatInput": [outer["id"]],
        "TextInput": [outer["id"], inner["id"]],
        "ChatOutput": [outer["id"], inner["id"]],
    }
    assert all(node.group_path == paths[node.type] for node in flow.nodes)
    if release == "1.10.0":
        assert "ChatOutput" in {node.type for node in flow.nodes}


@pytest.mark.parametrize("release", ["v1.12.6", "v1.13.0"])
def test_hard_flows_keep_their_expected_status(release, target):
    """The dry run agrees with every status pinned for the hard flows.

    ``expected_statuses.json`` records ok and outdated_safe as ``no_action``. Its retired nodes need
    lfx-bundles; without it they are missing types that name the bundle to install.
    """
    expected = json.loads((COMPAT / "expected_statuses.json").read_text(encoding="utf-8"))[release]["hard_flows"]
    bundles_installed = bool(importlib.metadata.entry_points(group="lfx.bundles"))
    actual, missing_bundles = {}, {}
    for path in sorted((COMPAT / "hard_flows" / release).glob("*.json")):
        nodes, ok_nodes = check_nodes(_hard_flow(release, path.name), target, user_id=OWNER)
        keys = [key for key in expected if key.startswith(f"{path.name}::")]
        assert len(nodes) + ok_nodes == len(keys)
        by_key = {f"{path.name}::{node.id}": node for node in nodes}
        for key in keys:
            node = by_key.get(key)
            actual[key] = "no_action" if node is None or node.status == "outdated_safe" else node.status
            uncertain_mcp = {
                "v1.12.6": "mcp_tools_arguments.json::MCPTools-BS8An",
                "v1.13.0": "mcp_tools_arguments.json::MCPTools-4BbE9",
            }
            if key == uncertain_mcp[release] and node is not None and node.status == "could_not_verify":
                assert node.dry_run == {"result": "could_not_verify"}
                assert all(reason["code"] == "could_not_verify" for reason in node.reasons)
                assert any(
                    "generated fields" in reason["message"] or "network call" in reason["message"]
                    for reason in node.reasons
                )
                expected = {**expected, key: "could_not_verify"}
            if node is not None and node.status == "blocked":
                missing_bundles[key] = (node.bundle, [reason["code"] for reason in node.reasons])

    if not bundles_installed:
        assert missing_bundles == {
            key: (bundle, ["bundle_not_installed"]) for key, bundle in LFX_BUNDLES_NODES.items() if key in expected
        }
        actual.update(dict.fromkeys(missing_bundles, "retired"))
    assert actual == expected


def test_retired_bundle_components_with_lfx_bundles_installed(tmp_path):
    """Discovery finds lfx-bundles through its entry point; its classes carry lfx's retired markers."""
    site = tmp_path / "site" / "lfx_bundles-0.0.0.dist-info"
    site.mkdir(parents=True)
    (site / "METADATA").write_text("Metadata-Version: 2.1\nName: lfx-bundles\nVersion: 0.0.0\n")
    (site / "entry_points.txt").write_text("[lfx.bundles]\nlfx_bundles = lfx_bundles\n")
    script = (
        "import json, sys\n"
        "from pathlib import Path\n"
        "from lfx.upgrade.registry import load_upgrade_registry\n"
        "from langflow.upgrade_check.engine import Target, check_nodes\n"
        "target = Target.from_registry(load_upgrade_registry(components_path=[]))\n"
        "found = {}\n"
        "for path in sorted(Path(sys.argv[1]).glob('*.json')):\n"
        "    for node in check_nodes(json.loads(path.read_text())['data'], target)[0]:\n"
        "        found[f'{path.name}::{node.id}'] = [node.status, node.bundle, node.replacement]\n"
        "print(json.dumps(found))\n"
    )
    pythonpath = os.pathsep.join([str(tmp_path / "site"), str(REPO / "src" / "bundles" / "lfx-bundles" / "src")])
    env = {**os.environ, "PYTHONPATH": pythonpath, "LANGFLOW_CONFIG_DIR": str(tmp_path), "DO_NOT_TRACK": "true"}
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script, str(COMPAT / "hard_flows" / "v1.12.6")],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    found = json.loads(result.stdout.strip().splitlines()[-1])
    assert {key: found[key][:2] for key in LFX_BUNDLES_NODES} == {
        key: ["retired", bundle] for key, bundle in LFX_BUNDLES_NODES.items()
    }
    assert all(found[key][2] for key in LFX_BUNDLES_NODES)


def test_dry_run_keeps_outputs_the_component_rebuilds(target):
    """The Update rebuilds Human Input's outputs from the saved choices, so a custom choice is not lost.

    Human Input makes one output per saved choice. Against the index entry alone, the rule calls a
    custom choice a removed output.
    """
    entry = target.lookup["HumanInput"]
    saved, instance = build_custom_component_template(Component(_code=entry["template"]["code"]["value"]))
    saved["template"]["decisions"]["value"] = ["Approve", "Request Changes"]
    saved = asyncio.run(instance.run_and_validate_update_outputs(saved, "decisions", ["Approve", "Request Changes"]))
    flow = {"nodes": [{"id": "HumanInput-1", "data": {"type": "HumanInput", "node": saved}}], "edges": []}
    changed = copy.deepcopy(entry)
    changed["template"]["code"]["value"] += "\n# changed"

    [node], _ = check_nodes(flow, _with(target, {"HumanInput": changed}), user_id=OWNER)

    assert node.status == "outdated_safe"
    assert node.dry_run == {"result": "keeps"}
    # Against the index entry alone, the rule calls it breaking.
    reasons = breaking_reasons(changed, saved, set())
    assert [(reason.code, reason.field) for reason in reasons] == [("output_changed", "branch_request_changes")]


SAVED_STATE_COMPONENT = """
from lfx.custom import Component
from lfx.io import DictInput, FileInput, StrInput, Output
from lfx.schema import Message

class SavedStateFixture(Component):
    display_name = "Saved state fixture"
    inputs = [FileInput(name="path", file_types=["txt"]), SAVED_INPUT]
    outputs = [Output(name="result", method="result")]

    async def update_frontend_node(self, new_frontend_node, current_frontend_node):
        updated = await super().update_frontend_node(new_frontend_node, current_frontend_node)
        MUTATION
        return updated

    def result(self) -> Message:
        return Message(text=self.text)
"""


def _saved_state_flow(mutation="pass", *, input_declaration='StrInput(name="text", value="default")'):
    code = SAVED_STATE_COMPONENT.replace("MUTATION", mutation).replace("SAVED_INPUT", input_declaration)
    entry, _ = build_custom_component_template(Component(_code=code))
    saved = copy.deepcopy(entry)
    saved["template"]["code"]["value"] += "\n# previous release\n"
    saved["template"]["text"].update(value="saved selection", load_from_db=False)
    flow = {"nodes": [{"id": "saved-state", "data": {"type": "SavedStateFixture", "node": saved}}], "edges": []}
    return flow, Target.from_registry({"fixtures": {"SavedStateFixture": entry}})


def test_dry_run_cannot_claim_preservation_when_an_uploaded_file_is_unavailable():
    flow, target = _saved_state_flow()
    saved = flow["nodes"][0]["data"]["node"]
    saved["template"]["path"].update(value="uploaded.txt", file_path=f"{OWNER}/{uuid4()}.txt")

    [result], _ = check_nodes(flow, target, user_id=OWNER)

    assert (result.status, result.dry_run) == ("could_not_verify", {"result": "could_not_verify"})
    assert [(reason["code"], reason["field"]) for reason in result.reasons] == [("could_not_verify", "path")]
    assert flow_status([result]) == "warn"
    assert saved["template"]["path"]["value"] == "uploaded.txt"


def test_unverified_file_does_not_hide_an_independent_breaking_change():
    flow, target = _saved_state_flow()
    saved = flow["nodes"][0]["data"]["node"]
    saved["template"]["path"].update(value="uploaded.txt", file_path=f"{OWNER}/{uuid4()}.txt")
    saved["template"]["text"].update(type="int", value=123)

    [result], _ = check_nodes(flow, target, user_id=OWNER)

    assert (result.status, result.dry_run) == ("outdated_breaking", {"result": "could_not_verify"})
    assert [(reason["code"], reason["field"]) for reason in result.reasons] == [
        ("value_dropped", "text"),
        ("could_not_verify", "path"),
    ]
    assert flow_status([result]) == "fail"


def test_dry_run_keeps_an_uploaded_file_available_to_its_owner(tmp_path, monkeypatch):
    from lfx.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "config_dir", str(tmp_path))
    monkeypatch.setattr(settings, "storage_type", "local")
    owner_directory = tmp_path / OWNER
    owner_directory.mkdir()
    (owner_directory / "uploaded.txt").write_text("saved contents", encoding="utf-8")
    flow, target = _saved_state_flow()
    flow["nodes"][0]["data"]["node"]["template"]["path"].update(value="uploaded.txt", file_path=f"{OWNER}/uploaded.txt")

    [result], _ = check_nodes(flow, target, user_id=OWNER)

    assert (result.status, result.dry_run, result.reasons) == ("outdated_safe", {"result": "keeps"}, [])
    assert (owner_directory / "uploaded.txt").read_text(encoding="utf-8") == "saved contents"


@pytest.mark.parametrize(
    "mutation",
    [
        'updated["template"]["text"]["value"] = "replacement"',
        'updated["template"]["text"]["load_from_db"] = True',
    ],
    ids=["saved-value-changed", "literal-became-global-reference"],
)
def test_dry_run_reports_saved_state_changed_by_a_completed_update(mutation):
    flow, target = _saved_state_flow(mutation)

    [result], _ = check_nodes(flow, target, user_id=OWNER)

    assert (result.status, result.dry_run) == ("outdated_breaking", {"result": "loses"})
    assert [(reason["code"], reason["field"]) for reason in result.reasons] == [("value_dropped", "text")]
    assert flow_status([result]) == "fail"


@pytest.mark.parametrize(
    ("input_declaration", "saved_value", "replacement"),
    [
        ('StrInput(name="text", value="default")', "", "replacement"),
        ('StrInput(name="text", list=True, value=["default"])', [], ["replacement"]),
        ('DictInput(name="text", value={"default": "value"})', {}, {"replacement": "value"}),
    ],
    ids=["empty-string", "empty-list", "empty-dictionary"],
)
@pytest.mark.parametrize("changed", [True, False], ids=["changed", "preserved"])
def test_dry_run_compares_explicit_empty_values(input_declaration, saved_value, replacement, changed):
    mutation = f'updated["template"]["text"]["value"] = {replacement!r}' if changed else "pass"
    flow, target = _saved_state_flow(mutation, input_declaration=input_declaration)
    flow["nodes"][0]["data"]["node"]["template"]["text"]["value"] = saved_value

    [result], _ = check_nodes(flow, target, user_id=OWNER)

    if changed:
        assert (result.status, result.dry_run) == ("outdated_breaking", {"result": "loses"})
        assert [(reason["code"], reason["field"]) for reason in result.reasons] == [("value_dropped", "text")]
    else:
        assert (result.status, result.dry_run, result.reasons) == ("outdated_safe", {"result": "keeps"}, [])


def test_dry_run_does_not_treat_an_absent_value_as_a_saved_selection():
    flow, target = _saved_state_flow()
    del flow["nodes"][0]["data"]["node"]["template"]["text"]["value"]

    [result], _ = check_nodes(flow, target, user_id=OWNER)

    assert (result.status, result.dry_run, result.reasons) == ("outdated_safe", {"result": "keeps"}, [])


@pytest.mark.parametrize("load_from_db", [False, True], ids=["literal", "global-reference"])
def test_dry_run_keeps_saved_values_and_their_reference_mode(load_from_db):
    flow, target = _saved_state_flow()
    flow["nodes"][0]["data"]["node"]["template"]["text"]["load_from_db"] = load_from_db

    [result], _ = check_nodes(flow, target, user_id=OWNER)

    assert (result.status, result.dry_run, result.reasons) == ("outdated_safe", {"result": "keeps"}, [])


def test_dry_run_loses_a_connection(target):
    """A later URL component stops taking connections into urls, which an edge reaches through two groups."""
    flow = _hard_flow("v1.12.6", "nested_groups.json")
    code = target.lookup["URLComponent"]["template"]["code"]["value"]
    old = '            input_types=["Message"],\n        ),\n        SliderInput('
    assert old in code
    changed = _new_code(target.lookup["URLComponent"], code.replace(old, old.replace('["Message"]', "[]")))

    nodes, _ = check_nodes(flow, _with(target, {"URLComponent": changed}), user_id=OWNER)

    [url] = [node for node in nodes if node.type == "URLComponent"]
    assert url.status == "outdated_breaking"
    assert [(reason["code"], reason["field"]) for reason in url.reasons] == [("connection_dropped", "urls")]
    assert url.dry_run == {"result": "loses"}
    assert len(url.group_path) == 2
    assert flow_status(nodes) == "fail"


def test_dry_run_build_failure(target):
    flow = _hard_flow("v1.12.6", "nested_groups.json")
    changed = copy.deepcopy(target.lookup["SplitText"])
    changed["template"]["code"]["value"] = "import module_this_release_lacks\n" + changed["template"]["code"]["value"]

    nodes, _ = check_nodes(flow, _with(target, {"SplitText": changed}), user_id=OWNER)

    [split] = [node for node in nodes if node.type == "SplitText"]
    assert split.status == "outdated_safe"
    assert [reason["code"] for reason in split.reasons] == ["build_failed"]
    assert "module_this_release_lacks" in split.reasons[0]["message"]
    assert split.dry_run["result"] == "build_failed"
    assert flow_status(nodes) == "warn"


CALLS_OUT = """
import socket

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.message import Message


class CallsOut(Component):
    display_name = "Calls Out"
    inputs = [MessageTextInput(name="text", display_name="Text")]
    outputs = [Output(display_name="Text", name="text_output", method="build_text")]

    async def update_frontend_node(self, new_frontend_node, current_frontend_node):
        socket.create_connection(("127.0.0.1", PORT), timeout=5).close()
        return await super().update_frontend_node(new_frontend_node, current_frontend_node)

    def build_text(self) -> Message:
        return Message(text=self.text)
"""


def test_dry_run_cannot_reach_the_network(target):
    """A component whose update hook calls out is refused, and the check goes on."""
    with socket.create_server(("127.0.0.1", 0)) as server:
        code = CALLS_OUT.replace("PORT", str(server.getsockname()[1]))
        saved, _ = build_custom_component_template(Component(_code=code + "\n# saved"))
        flow = {"nodes": [{"id": "CallsOut-1", "data": {"type": "CallsOut", "node": saved}}], "edges": []}
        entry, _ = build_custom_component_template(Component(_code=code))

        [node], _ = check_nodes(flow, _with(target, {"CallsOut": entry}), user_id=OWNER)

        assert node.status == "outdated_safe"
        assert [reason["code"] for reason in node.reasons] == ["could_not_verify"]
        assert "socket.getaddrinfo" in node.reasons[0]["message"]
        server.settimeout(0.5)
        with pytest.raises(TimeoutError):
            server.accept()
        # Outside a dry run the network is open again.
        socket.create_connection(server.getsockname(), timeout=5).close()


def test_dry_run_time_limit(monkeypatch, target):
    monkeypatch.setattr(engine, "DRY_RUN_SECONDS", 0.2)
    code = CALLS_OUT.replace("import socket", "import time").replace(
        'socket.create_connection(("127.0.0.1", PORT), timeout=5).close()', "time.sleep(1)"
    )
    saved, _ = build_custom_component_template(Component(_code=code + "\n# saved"))
    flow = {"nodes": [{"id": "CallsOut-1", "data": {"type": "CallsOut", "node": saved}}], "edges": []}
    entry, _ = build_custom_component_template(Component(_code=code))

    try:
        [node], _ = check_nodes(flow, _with(target, {"CallsOut": entry}), user_id=OWNER)

        assert [reason["code"] for reason in node.reasons] == ["could_not_verify"]
        assert "did not finish in 0.2 seconds" in node.reasons[0]["message"]
    finally:
        # The guard remains active until the abandoned update ends, even if an assertion fails.
        for thread in threading.enumerate():
            if thread.name == "upgrade-check-dry-run":
                thread.join()


def test_missing_custom_type(target):
    saved, _ = build_custom_component_template(Component(_code=CALLS_OUT.replace("PORT", "1")))
    flow = {"nodes": [{"id": "CallsOut-1", "data": {"type": "CallsOut", "node": saved}}], "edges": []}

    [node], _ = check_nodes(flow, target)

    assert (node.status, node.bundle) == ("blocked", None)
    assert [reason["code"] for reason in node.reasons] == ["custom_type_missing"]


def test_skips_starter_projects(target, tmp_path):
    database = _load("1.13.0", tmp_path)
    connection = sqlite3.connect(database)
    starter, users_folder = uuid4().hex, uuid4().hex
    connection.execute("INSERT INTO folder (id, name, user_id) VALUES (?, 'Starter Projects', NULL)", (starter,))
    # A user's own project may carry the same name; only Langflow's is skipped.
    connection.execute(
        "INSERT INTO folder (id, name, user_id) SELECT ?, 'Starter Projects', user_id FROM flow LIMIT 1",
        (users_folder,),
    )
    connection.commit()
    connection.close()
    _add_flow(database, "Basic Prompting", folder_id=starter, user_id=None)
    _add_flow(database, "Mine", folder_id=users_folder)

    with open_source(_url(database)) as source:
        names = [result.name for result in check_source(source, target)]

    assert "Basic Prompting" not in names
    assert "Mine" in names


def test_unreadable_row_and_unset_is_component(target, tmp_path):
    database = _load("1.10.0", tmp_path)
    _add_flow(database, "Broken", data="{not json")
    _add_flow(database, "Old component", is_component=None)

    with open_source(_url(database)) as source:
        results = {result.name: result for result in check_source(source, target)}

    broken = results["Broken"]
    assert (broken.status, broken.nodes) == ("warn", [])
    assert broken.error.startswith("flow data is not JSON")
    # The server reads a row with is_component unset as a component when it has one node.
    assert results["Old component"].kind == "component"


def _older_code(flow: dict, component_type: str) -> dict:
    """``flow`` as an older release saved it: ``component_type`` nodes carry other code."""
    flow = copy.deepcopy(flow)
    for node in flow["nodes"]:
        if node["data"]["type"] == component_type:
            node["data"]["node"]["template"]["code"]["value"] += "\n# saved by an older release"
    return flow


@pytest.mark.parametrize("release", ["v1.12.6", "v1.13.0"])
def test_mcp_tools_dry_run(target, release):
    """MCP discovery is unavailable, so generated arguments cannot be verified."""
    flow = _older_code(_hard_flow(release, "mcp_tools_arguments.json"), "MCPTools")

    nodes, _ = check_nodes(flow, target, user_id=OWNER)

    [mcp] = [node for node in nodes if node.type == "MCPTools"]
    assert (mcp.status, mcp.dry_run) == ("could_not_verify", {"result": "could_not_verify"})
    assert [reason["code"] for reason in mcp.reasons] == ["could_not_verify"]
    assert flow_status(nodes) == "warn"


@pytest.mark.parametrize("release", ["v1.12.6", "v1.13.0"])
def test_run_flow_generated_contract_is_unverified(target, release):
    """The checker has no database for regenerating the selected flow's contract."""
    flow = _older_code(_hard_flow(release, "run_flow_inputs.json"), "RunFlow")

    nodes, _ = check_nodes(flow, target, user_id=OWNER)

    [run_flow] = [node for node in nodes if node.type == "RunFlow"]
    assert (run_flow.status, run_flow.dry_run) == ("could_not_verify", {"result": "could_not_verify"})
    assert [reason["code"] for reason in run_flow.reasons] == ["could_not_verify"]
    assert flow_status(nodes) == "warn"


@pytest.mark.parametrize(
    ("fixture", "component_type"),
    [("run_flow_inputs.json", "RunFlow"), ("mcp_tools_arguments.json", "MCPTools")],
)
def test_unverified_generation_keeps_removed_static_field(target, fixture, component_type):
    flow = _older_code(_hard_flow("v1.13.0", fixture), component_type)
    saved = next(node for node in flow["nodes"] if node["data"]["type"] == component_type)["data"]["node"]
    saved["template"]["old_setting"] = {"type": "str", "value": "saved"}
    saved["field_order"].append("old_setting")

    nodes, _ = check_nodes(flow, target, user_id=OWNER)

    [result] = [node for node in nodes if node.type == component_type]
    assert result.status == "outdated_breaking"
    assert result.dry_run == {"result": "could_not_verify"}
    assert [(reason["code"], reason["field"]) for reason in result.reasons] == [
        ("field_removed", "old_setting"),
        ("could_not_verify", None),
    ]
    assert flow_status(nodes) == "fail"


def test_unverified_run_flow_keeps_incompatible_static_input(target):
    flow = _older_code(_hard_flow("v1.13.0", "run_flow_inputs.json"), "RunFlow")
    saved = next(node for node in flow["nodes"] if node["data"]["type"] == "RunFlow")["data"]["node"]
    saved["template"]["session_id"].update(type="other", value="saved session")

    nodes, _ = check_nodes(flow, target, user_id=OWNER)

    [result] = [node for node in nodes if node.type == "RunFlow"]
    assert result.status == "outdated_breaking"
    assert ("value_dropped", "session_id") in [(reason["code"], reason["field"]) for reason in result.reasons]
    assert result.reasons[-1]["code"] == "could_not_verify"


def test_unverified_mcp_keeps_changed_static_output(target):
    flow = _older_code(_hard_flow("v1.13.0", "mcp_tools_arguments.json"), "MCPTools")
    saved = next(node for node in flow["nodes"] if node["data"]["type"] == "MCPTools")["data"]["node"]
    saved["outputs"][0]["method"] = "previous_method"

    nodes, _ = check_nodes(flow, target, user_id=OWNER)

    [result] = [node for node in nodes if node.type == "MCPTools"]
    assert result.status == "outdated_breaking"
    assert ("output_changed", saved["outputs"][0]["name"]) in [
        (reason["code"], reason["field"]) for reason in result.reasons
    ]
    assert result.reasons[-1]["code"] == "could_not_verify"


def _provide_discovery(
    monkeypatch,
    target,
    saved,
    component_type,
    *,
    removed_input=False,
    network_refused=False,
    refresh_fails=False,
    outputs_fail=False,
):
    calls = []
    build = engine.build_custom_component_template

    if component_type == "RunFlow":
        children = []
        for child_type, node_id in (
            ("ChatInput", "ChatInput-NrNFA"),
            ("TextInput", "TextInput-v7wpH"),
            ("ChatOutput", "ChatOutput-evE3l"),
        ):
            if removed_input and child_type == "TextInput":
                continue
            children.append(
                {
                    "id": node_id,
                    "type": "genericNode",
                    "data": {"id": node_id, "type": child_type, "node": copy.deepcopy(target.lookup[child_type])},
                }
            )
        graph = Graph.from_payload({"nodes": children, "edges": []})

        async def discover(**kwargs):
            calls.append(kwargs)
            if network_refused:
                socket.getaddrinfo("unavailable.invalid", 443)
            if refresh_fails and len(calls) == 1:
                message = "The selected flow could not be loaded"
                raise OSError(message)
            if outputs_fail and len(calls) > 1:
                message = "The selected flow outputs could not be loaded"
                raise OSError(message)
            assert kwargs["flow_id_selected"] == saved["template"]["flow_name_selected"]["selected_metadata"]["id"]
            return graph

        method = "get_graph"
    else:

        def greet(name: str, times: int = 1) -> str:
            return " ".join([f"Hello {name}"] * times)

        def greet_without_times(name: str) -> str:
            return f"Hello {name}"

        tool = StructuredTool.from_function(
            greet_without_times if removed_input else greet, name="greet", description="Return a greeting."
        )

        async def discover(**kwargs):
            calls.append(kwargs)
            if network_refused:
                socket.getaddrinfo("unavailable.invalid", 443)
            return [tool], copy.deepcopy(saved["template"]["mcp_server"]["value"])

        method = "update_tool_list"

    def build_with_discovery(*args, **kwargs):
        frontend, instance = build(*args, **kwargs)
        if type(instance).__name__ == f"{component_type}Component":
            monkeypatch.setattr(instance, method, discover)
        return frontend, instance

    monkeypatch.setattr(engine, "build_custom_component_template", build_with_discovery)
    return calls


@pytest.mark.parametrize(
    ("fixture", "component_type"),
    [("run_flow_inputs.json", "RunFlow"), ("mcp_tools_arguments.json", "MCPTools")],
)
def test_generated_contract_with_available_discovery_keeps_values_and_connections(
    monkeypatch, target, fixture, component_type
):
    flow = _older_code(_hard_flow("v1.13.0", fixture), component_type)
    saved = next(node for node in flow["nodes"] if node["data"]["type"] == component_type)["data"]["node"]
    calls = _provide_discovery(monkeypatch, target, saved, component_type)

    nodes, _ = check_nodes(flow, target, user_id=OWNER)

    [result] = [node for node in nodes if node.type == component_type]
    assert calls
    assert (result.status, result.dry_run, result.reasons) == ("outdated_safe", {"result": "keeps"}, [])


@pytest.mark.parametrize(
    ("fixture", "component_type", "removed_field"),
    [
        ("run_flow_inputs.json", "RunFlow", "TextInput-v7wpH~input_value"),
        ("mcp_tools_arguments.json", "MCPTools", "times"),
    ],
)
def test_verified_discovery_keeps_removed_generated_field_breaking(
    monkeypatch, target, fixture, component_type, removed_field
):
    flow = _older_code(_hard_flow("v1.13.0", fixture), component_type)
    saved = next(node for node in flow["nodes"] if node["data"]["type"] == component_type)["data"]["node"]
    calls = _provide_discovery(monkeypatch, target, saved, component_type, removed_input=True)

    nodes, _ = check_nodes(flow, target, user_id=OWNER)

    [result] = [node for node in nodes if node.type == component_type]
    assert calls
    assert (result.status, result.dry_run) == ("outdated_breaking", {"result": "loses"})
    assert ("field_removed", removed_field) in [(reason["code"], reason["field"]) for reason in result.reasons]
    assert all(reason["code"] == "field_removed" for reason in result.reasons)
    assert flow_status(nodes) == "fail"


@pytest.mark.parametrize(
    ("fixture", "component_type"),
    [("run_flow_inputs.json", "RunFlow"), ("mcp_tools_arguments.json", "MCPTools")],
)
def test_network_refusal_keeps_partial_generated_contract_warning(monkeypatch, target, fixture, component_type):
    flow = _older_code(_hard_flow("v1.13.0", fixture), component_type)
    saved = next(node for node in flow["nodes"] if node["data"]["type"] == component_type)["data"]["node"]
    calls = _provide_discovery(monkeypatch, target, saved, component_type, network_refused=True)

    nodes, _ = check_nodes(flow, target, user_id=OWNER)

    [result] = [node for node in nodes if node.type == component_type]
    assert calls
    assert (result.status, result.dry_run) == ("could_not_verify", {"result": "could_not_verify"})
    assert [reason["code"] for reason in result.reasons] == ["could_not_verify"]
    assert "network call" in result.reasons[0]["message"]
    assert flow_status(nodes) == "warn"


@pytest.mark.parametrize("changed_output_attribute", ["method", "name"])
def test_unverified_run_flow_keeps_regenerated_output_changes(monkeypatch, target, changed_output_attribute):
    flow = _older_code(_hard_flow("v1.13.0", "run_flow_inputs.json"), "RunFlow")
    saved = next(node for node in flow["nodes"] if node["data"]["type"] == "RunFlow")["data"]["node"]
    saved["outputs"][0][changed_output_attribute] = "ChatOutput-removed~message"
    _provide_discovery(monkeypatch, target, saved, "RunFlow", refresh_fails=True)

    nodes, _ = check_nodes(flow, target, user_id=OWNER)

    [result] = [node for node in nodes if node.type == "RunFlow"]
    assert (result.status, result.dry_run) == ("outdated_breaking", {"result": "could_not_verify"})
    assert [(reason["code"], reason["field"]) for reason in result.reasons] == [
        ("output_changed", saved["outputs"][0]["name"]),
        ("could_not_verify", None),
    ]


def test_unverified_outputs_keep_confirmed_generated_input_removal(monkeypatch, target):
    flow = _older_code(_hard_flow("v1.13.0", "run_flow_inputs.json"), "RunFlow")
    saved = next(node for node in flow["nodes"] if node["data"]["type"] == "RunFlow")["data"]["node"]
    _provide_discovery(monkeypatch, target, saved, "RunFlow", removed_input=True, outputs_fail=True)

    nodes, _ = check_nodes(flow, target, user_id=OWNER)

    [result] = [node for node in nodes if node.type == "RunFlow"]
    assert (result.status, result.dry_run) == ("outdated_breaking", {"result": "could_not_verify"})
    assert ("field_removed", "TextInput-v7wpH~input_value") in [
        (reason["code"], reason["field"]) for reason in result.reasons
    ]
    assert result.reasons[-1]["code"] == "could_not_verify"
    assert flow_status(nodes) == "fail"


def test_unverified_contract_does_not_hide_runtime_refusal(target):
    flow = _older_code(_hard_flow("v1.13.0", "mcp_tools_arguments.json"), "MCPTools")
    restricted = dataclasses.replace(
        target, settings=TargetSettings(allow_custom_components=False, substitute_outdated_component_code=False)
    )

    nodes, _ = check_nodes(flow, restricted, user_id=OWNER)

    [result] = [node for node in nodes if node.type == "MCPTools"]
    assert (result.status, result.runs) == ("could_not_verify", "refused")
    assert "refused" in [reason["code"] for reason in result.reasons]
    assert flow_status(nodes) == "fail"


def test_check_writes_only_to_its_config_dir(tmp_path):
    """The command runs the check without any LANGFLOW_ variable and with a throwaway config dir.

    Component code may build Langflow's settings (MCP components read one when they are created),
    which save a secret key. That must land in the config dir, and no database or variable service
    may start.
    """
    database = _load("1.10.0", tmp_path)
    mcp_flow = _older_code(_hard_flow("v1.13.0", "mcp_tools_arguments.json"), "MCPTools")
    _add_flow(database, "MCP flow", data=json.dumps(mcp_flow), is_component=0)
    before = database.read_bytes()
    config, home = tmp_path / "config", tmp_path / "home"
    config.mkdir()
    home.mkdir()
    script = (
        "import json, sys\n"
        "from langflow.upgrade_check import open_source\n"
        "from langflow.upgrade_check.engine import Target, check_source\n"
        "from lfx.services.manager import get_service_manager\n"
        "from lfx.upgrade.registry import load_upgrade_registry\n"
        "target = Target.from_registry(load_upgrade_registry(components_path=[]))\n"
        "with open_source(sys.argv[1]) as source:\n"
        "    statuses = {result.name: result.status for result in check_source(source, target)}\n"
        "print(json.dumps({'statuses': statuses, 'services': sorted(get_service_manager().services)}))\n"
    )
    env = {name: value for name, value in os.environ.items() if not name.startswith("LANGFLOW_")}
    env.update(LANGFLOW_CONFIG_DIR=str(config), HOME=str(home), DO_NOT_TRACK="true")
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script, _url(database)], env=env, capture_output=True, text=True, check=True
    )

    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert report["statuses"] == {"Fixture nested groups": "ok", "Fixture saved component": "ok", "MCP flow": "warn"}
    assert set(report["services"]) <= {"settings_service", "shared_component_cache_service"}
    assert list(home.rglob("*")) == []
    assert sorted(path.name for path in tmp_path.iterdir()) == ["config", "home", database.name]
    assert database.read_bytes() == before


def _saved_node(release: str, flow_name: str, node_id: str) -> dict:
    flow = _hard_flow(release, flow_name)
    return next(
        copy.deepcopy(node) for node, _, _ in iter_flow_nodes(flow["nodes"], flow["edges"]) if node["id"] == node_id
    )


# What each node runs under each setting, for the nodes listed: a node that is ok and runs is not.
RUNS = [
    pytest.param(
        {}, False, {"outdated": "saved_code", "customized": "saved_code", "custom": "saved_code"}, id="default"
    ),
    pytest.param(
        {"allow_custom_components": False},
        False,
        # Substitution swaps the server's code into drifted built-ins, the customized one too.
        {"outdated": "server_code", "customized": "server_code", "custom": "refused", "interpreter": "refused"},
        id="custom code blocked",
    ),
    pytest.param(
        {"allow_custom_components": False, "substitute_outdated_component_code": False},
        False,
        {"outdated": "refused", "customized": "refused", "custom": "refused", "interpreter": "refused"},
        id="custom code blocked, no substitution",
    ),
    pytest.param(
        {"block_code_interpreter_components": True},
        False,
        {"outdated": "saved_code", "customized": "saved_code", "custom": "saved_code", "interpreter": "refused"},
        id="interpreters blocked",
    ),
    pytest.param(
        {"custom_component_admin_only": True},
        False,
        {"outdated": "refused", "customized": "refused", "custom": "refused", "interpreter": "refused"},
        id="admin only, regular owner",
    ),
    pytest.param(
        {"custom_component_admin_only": True},
        True,
        {"outdated": "saved_code", "customized": "saved_code", "custom": "saved_code"},
        id="admin only, admin owner",
    ),
    pytest.param(
        {"custom_component_admin_only": True, "allow_custom_components": False},
        False,
        {"outdated": "server_code", "customized": "server_code", "custom": "refused", "interpreter": "refused"},
        id="admin only and custom code blocked",
    ),
]


@pytest.mark.parametrize(("settings", "is_superuser", "expected"), RUNS)
def test_runs_under_each_setting(settings, is_superuser, expected, all_types, target):
    interpreter = target.lookup["PythonREPLTool"]
    custom, _ = build_custom_component_template(Component(_code=CALLS_OUT.replace("PORT", "1")))
    nodes = {
        "ok": _saved_node("v1.13.0", "nested_groups.json", "TextInput-wZQij"),
        "outdated": _saved_node("v1.12.6", "nested_groups.json", "URLComponent-ewSSi"),
        "customized": _saved_node("v1.12.6", "customized.json", "URLComponent-fFtci"),
        "custom": {"id": "CallsOut-1", "data": {"type": "CallsOut", "node": custom}},
        "interpreter": {
            "id": "PythonREPLTool-1",
            "data": {"type": "PythonREPLTool", "node": copy.deepcopy(interpreter)},
        },
    }
    names = {node["id"]: name for name, node in nodes.items()}
    target = Target.from_registry(all_types, TargetSettings(**settings))

    listed, _ = check_nodes(
        {"nodes": list(nodes.values()), "edges": []}, target, user_id=OWNER, is_superuser=is_superuser
    )

    assert {names[node.id]: node.runs for node in listed} == expected
    for node in listed:
        refused = [reason for reason in node.reasons if reason["code"] == "refused"]
        assert bool(refused) == (node.runs == "refused")


@pytest.mark.parametrize(
    ("statement", "data_error"),
    [
        (None, None),
        (
            "UPDATE policy_bundle_revision SET blocked_template_keys = 'not json' WHERE revision = 2",
            "blocked_template_keys could not be read",
        ),
    ],
)
def test_catalog_rule_refuses_a_component(statement, data_error, all_types, tmp_path):
    """A blocked ChatInput is refused even where it is up to date.

    Rules that cannot be read are the source's error, for the report's errors, not the nodes'. The
    nodes still get the rules that could be read.
    """
    database = _load("1.13.0", tmp_path)
    _block_components(database, "1.13.0", "ChatInput")
    if statement:
        _execute(database, statement)

    with open_source(_url(database)) as source:
        policy = source.catalog_policy()
        results = list(check_source(source, Target.from_registry(all_types, catalog_policy=policy.snapshot)))

    if data_error is None:
        assert policy.data_error is None
    else:
        assert data_error in policy.data_error
    for result in results:
        [chat_input] = [node for node in result.nodes if node.type == "ChatInput"]
        assert (chat_input.status, chat_input.runs, result.status) == ("ok", "refused", "fail")
        [reason] = chat_input.reasons
        assert reason["message"] == "Flow build blocked: catalog policy blocks components: ChatInput"
        assert all(node.type == "ChatInput" for node in result.nodes)


def test_admin_only_judges_each_flow_by_its_owner(tmp_path):
    """In admin-only mode a regular user's outdated node is refused, an admin's runs its saved code."""
    database = _load("1.10.0", tmp_path)
    connection = sqlite3.connect(database)
    [(regular,)] = connection.execute("SELECT id FROM user WHERE username = 'fixture-user'")
    connection.close()
    _add_flow(database, "Regular user's component", user_id=regular)
    settings = TargetSettings(custom_component_admin_only=True)

    with open_source(_url(database)) as source:
        all_types = load_upgrade_registry(components_path=[])
        results = {result.name: result for result in check_source(source, Target.from_registry(all_types, settings))}

    assert [node.runs for node in results["Fixture saved component"].nodes] == ["saved_code"]
    assert [node.runs for node in results["Regular user's component"].nodes] == ["refused"]


@pytest.mark.parametrize(
    ("settings", "runs", "message", "status"),
    [
        pytest.param({}, "saved_code", "the saved code was edited", "warn", id="edits run"),
        pytest.param(
            {"allow_custom_components": False},
            "server_code",
            "the saved edits will not run: this server runs its own code for this component",
            "fail",
            id="edits replaced",
        ),
    ],
)
def test_customized_nodes_fail_when_their_edits_will_not_run(settings, runs, message, status, all_types):
    """A customized node warns while its edits run, and fails its flow when the server runs its own code instead."""
    flow = _hard_flow("v1.12.6", "customized.json")
    target = Target.from_registry(all_types, TargetSettings(**settings))

    nodes, _ = check_nodes(flow, target, user_id=OWNER)

    customized = [node for node in nodes if node.status == "customized"]
    assert {node.id for node in customized} == {"URLComponent-fFtci", "Agent-dsmss"}
    assert all(node.runs == runs for node in customized)
    assert all(node.reasons == [{"code": "customized", "field": None, "message": message}] for node in customized)
    assert flow_status(nodes) == status


def test_later_dry_run_does_not_inherit_a_timed_out_nodes_refusal(monkeypatch):
    release_first, first_done, second_started = threading.Event(), threading.Event(), threading.Event()
    monkeypatch.setattr(engine, "DRY_RUN_SECONDS", 0.05)

    async def update(entry, _saved, _user):
        identity = threading.get_ident()
        engine._dry_run_threads.add(identity)
        try:
            if entry.get("slow"):
                assert release_first.wait(timeout=3)
                try:
                    engine._refuse_network("socket.getaddrinfo", ("earlier-node.invalid",))
                finally:
                    first_done.set()
            else:
                second_started.set()
                release_first.set()
                assert first_done.wait(timeout=3)
                return engine._RebuildOutcome(node={"template": {}}, warnings=[])
        finally:
            engine._dry_run_threads.discard(identity)

    monkeypatch.setattr(engine, "_update", update)
    try:
        rebuilt, failure = engine._dry_run({"slow": True}, {}, None)
        assert rebuilt is None
        assert "did not finish" in failure["message"]
        rebuilt, failure = engine._dry_run({}, {}, None)
        assert rebuilt is None
        assert failure["code"] == "could_not_verify"
        assert "earlier" in failure["message"]
        assert "earlier-node.invalid" not in failure["message"]
        assert not second_started.is_set()
    finally:
        release_first.set()
        for thread in threading.enumerate():
            if thread.name == "upgrade-check-dry-run":
                thread.join(timeout=3)
