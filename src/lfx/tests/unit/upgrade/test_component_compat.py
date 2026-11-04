"""The compatibility rule against the shared case table and against nodes saved on older releases.

``cases.json`` is shared with the editor's copy of the rule
(``src/frontend/src/CustomNodes/helpers/__tests__/check-code-validity.test.ts``), so a change to
one copy that the other does not make fails a build. ``expected_statuses.json`` pins the status of
every node saved on each source release; see ``tests/data/component_compat/README.md``.
"""

from __future__ import annotations

import copy
import json
import os
import pathlib
import shutil
import subprocess
from functools import cache
from importlib.resources import files

import pytest
from lfx.graph.edge.base import TYPE_MIGRATIONS
from lfx.upgrade.checker import breaking_reasons, build_registry_lookup, check_flow_compatibility

DATA_DIR = pathlib.Path(__file__).parents[2] / "data" / "component_compat"
CASES = json.loads((DATA_DIR / "cases.json").read_text(encoding="utf-8"))
EXPECTED_PATH = DATA_DIR / "expected_statuses.json"

SOURCE_RELEASES = ("v1.12.6", "v1.13.0")
STARTER_PROJECTS = "src/backend/base/langflow/initial_setup/starter_projects"
COMPONENT_INDEX = "src/lfx/src/lfx/_assets/component_index.json"
FETCH_COMMAND = "git fetch origin --force " + " ".join(f"tag {tag}" for tag in SOURCE_RELEASES)

# ok and outdated_safe need no action, so a component change that keeps saved flows working
# does not touch the expected file. Every other status is pinned as it is.
NO_ACTION = "no_action"


def _result(status: str) -> str:
    return NO_ACTION if status in {"ok", "outdated_safe"} else status


def _all_types(index_blob: dict) -> dict:
    all_types: dict = {}
    for category, components in index_blob["entries"]:
        all_types.setdefault(category, {}).update(components)
    return all_types


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_shared_case(case):
    node = {"id": "n1", "data": {"id": "n1", "type": "TestComponent", "node": case["saved_node"]}}
    edges = [
        {"source": "other", "target": "n1", "data": {"targetHandle": {"fieldName": field_name, "id": "n1"}}}
        for field_name in case["connected_fields"]
    ]
    all_types = {"Test": {"TestComponent": case["component"]}} if case["component"] else {}

    report = check_flow_compatibility({"nodes": [node], "edges": edges}, all_types)

    assert report.nodes[0].status == case["expected"], case["description"]


UPDATE_CASES = [case for case in CASES if case["expected"] in {"outdated_safe", "outdated_breaking"}]


@pytest.mark.parametrize("case", UPDATE_CASES, ids=[case["name"] for case in UPDATE_CASES])
def test_shared_case_reasons(case):
    """``breaking_reasons`` finds a reason exactly for the shared cases that are breaking."""
    reasons = breaking_reasons(case["component"], case["saved_node"], case["connected_fields"])

    assert bool(reasons) == (case["expected"] == "outdated_breaking"), case["description"]


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(DATA_DIR), *args], capture_output=True, check=False)  # noqa: S603, S607


def _require_tags() -> None:
    missing = [
        tag
        for tag in SOURCE_RELEASES
        if shutil.which("git") is None or _git("rev-parse", "--verify", "--quiet", f"{tag}^{{commit}}").returncode
    ]
    if not missing:
        return
    message = f"Missing git tags {', '.join(missing)}. Run: {FETCH_COMMAND}"
    if os.environ.get("CI"):
        pytest.fail(message)
    pytest.skip(message)


def _show(tag: str, file_path: str) -> bytes:
    return _git("show", f"{tag}:{file_path}").stdout


def _flow_statuses(flows: dict[str, dict], all_types: dict, lookup: dict) -> dict[str, str]:
    statuses = {}
    for flow_name, flow in sorted(flows.items()):
        report = check_flow_compatibility(flow["data"], all_types, registry=lookup)
        for node in report.nodes:
            statuses[f"{flow_name}::{node.node_id}"] = _result(node.status)
    return statuses


def _release_statuses(tag: str, all_types: dict, lookup: dict) -> dict[str, dict[str, str]]:
    listing = _git("ls-tree", "--full-tree", "--name-only", tag, "--", f"{STARTER_PROJECTS}/")
    names = listing.stdout.decode().splitlines()
    starter_flows = {pathlib.Path(name).name: json.loads(_show(tag, name)) for name in names if name.endswith(".json")}

    # Each entry of the release's own component index stands in for a node saved on that release.
    component_index = {}
    for category, components in sorted(_all_types(json.loads(_show(tag, COMPONENT_INDEX))).items()):
        for component_type, entry in sorted(components.items()):
            node = {"id": component_type, "data": {"id": component_type, "type": component_type, "node": entry}}
            report = check_flow_compatibility({"nodes": [node]}, all_types, registry=lookup)
            for status in report.nodes:
                component_index[f"{category}.{component_type}"] = _result(status.status)

    hard_flows_dir = DATA_DIR / "hard_flows" / tag
    hard_flows = {f.name: json.loads(f.read_text(encoding="utf-8")) for f in sorted(hard_flows_dir.glob("*.json"))}

    return {
        "starter_flows": _flow_statuses(starter_flows, all_types, lookup),
        "component_index": component_index,
        "hard_flows": _flow_statuses(hard_flows, all_types, lookup),
    }


def _retired_bundle_templates() -> dict:
    """Templates of the retired components, keyed as lfx-bundles registers them.

    The core index leaves these out: lfx-bundles discovers them at runtime from lfx's own
    classes, and this test runs without lfx-bundles. Building the same templates here keeps
    their saved nodes from reading as blocked.
    """
    from lfx.components.altk.altk_agent import ALTKAgentComponent
    from lfx.components.chroma.chroma import ChromaVectorStoreComponent
    from lfx.components.chroma.local_db import LocalDBComponent
    from lfx.custom.utils import create_component_template

    def template(cls) -> dict:
        built = create_component_template(component_extractor=cls())[0]
        # Discovery stamps the pre-bundle name (``Chroma``) so older saved types still resolve.
        return {**built, "name": built.get("name") or cls.name}

    bundles = {"chroma": [ChromaVectorStoreComponent, LocalDBComponent], "altk": [ALTKAgentComponent]}
    return {
        bundle: {f"ext:{bundle}:{cls.__name__}@official": template(cls) for cls in classes}
        for bundle, classes in bundles.items()
    }


def test_source_release_statuses():
    """Every node saved on a supported source release keeps the result recorded for it.

    The result is ``no_action`` for ok and outdated_safe, otherwise the status itself.
    """
    _require_tags()
    all_types = _all_types(json.loads(files("lfx").joinpath("_assets/component_index.json").read_text()))
    all_types.update(_retired_bundle_templates())
    lookup = build_registry_lookup(all_types)
    actual = {tag: _release_statuses(tag, all_types, lookup) for tag in SOURCE_RELEASES}

    if os.environ.get("UPDATE_COMPAT_EXPECTED") == "1":
        EXPECTED_PATH.write_text(json.dumps(actual, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return

    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    changed = [
        f"{tag} {source} {key}: {expected.get(tag, {}).get(source, {}).get(key)} -> {status}"
        for tag, sources in actual.items()
        for source, statuses in sources.items()
        for key, status in statuses.items()
        if expected.get(tag, {}).get(source, {}).get(key) != status
    ]
    changed += [
        f"{tag} {source} {key}: {status} -> missing"
        for tag, sources in expected.items()
        for source, statuses in sources.items()
        for key, status in statuses.items()
        if key not in actual.get(tag, {}).get(source, {})
    ]
    assert not changed, "Results changed. If intended, rerun with UPDATE_COMPAT_EXPECTED=1:\n" + "\n".join(changed)


@cache
def _current_lookup() -> dict[str, dict]:
    return build_registry_lookup(
        _all_types(json.loads(files("lfx").joinpath("_assets/component_index.json").read_text()))
    )


def _empty_urls_input_types(entry: dict) -> None:
    entry["template"]["urls"]["input_types"] = []


def _drop_old_type_names(entry: dict) -> None:
    """Keep only the current type names (JSON, Table) on every input and output."""
    for field in entry["template"].values():
        if isinstance(field, dict) and field.get("input_types"):
            field["input_types"] = [t for t in field["input_types"] if t not in TYPE_MIGRATIONS]
    for output in entry["outputs"]:
        output["types"] = [t for t in output["types"] if t not in TYPE_MIGRATIONS]


def _drop_tool_mode(entry: dict) -> None:
    for field in entry["template"].values():
        if isinstance(field, dict):
            field.pop("tool_mode", None)


# Each case gives one component of the bundled index new code, plus the change named, the way a
# later release could. It pins the status of every node of that type in the hard flow. The starter
# flows and index entries never reach these parts of the rule.
COMPONENT_CHANGES = [
    pytest.param("run_flow_inputs.json", "RunFlow", None, "outdated_breaking", id="run flow inputs"),
    pytest.param("mcp_tools_arguments.json", "MCPTools", None, "outdated_breaking", id="mcp tools arguments"),
    pytest.param("prompt_variables.json", "Prompt Template", None, "outdated_safe", id="prompt variables"),
    pytest.param(
        "nested_groups.json",
        "URLComponent",
        _empty_urls_input_types,
        "outdated_breaking",
        id="input types emptied, connected through two groups",
    ),
    pytest.param(
        "type_names.json",
        "URLComponent",
        _empty_urls_input_types,
        "outdated_safe",
        id="input types emptied, not connected",
    ),
    pytest.param(
        "type_names.json", "ParserComponent", _drop_old_type_names, "outdated_safe", id="input types lose Data names"
    ),
    pytest.param("type_names.json", "Agent", _drop_old_type_names, "outdated_safe", id="output types lose Data names"),
    pytest.param("tool_mode.json", "URLComponent", None, "outdated_safe", id="tool mode"),
    pytest.param("tool_mode.json", "URLComponent", _drop_tool_mode, "outdated_breaking", id="tool mode dropped"),
]


@pytest.mark.parametrize("release", SOURCE_RELEASES)
@pytest.mark.parametrize(("flow_name", "component_type", "change", "expected"), COMPONENT_CHANGES)
def test_hard_flow_status_after_a_component_change(release, flow_name, component_type, change, expected):
    lookup = _current_lookup()
    entry = copy.deepcopy(lookup[component_type])
    entry["template"]["code"]["value"] += "\n# changed"
    if change:
        change(entry)
    flow = json.loads((DATA_DIR / "hard_flows" / release / flow_name).read_text(encoding="utf-8"))["data"]

    report = check_flow_compatibility(flow, {}, registry={**lookup, component_type: entry})

    assert {node.status for node in report.nodes if node.component_type == component_type} == {expected}
