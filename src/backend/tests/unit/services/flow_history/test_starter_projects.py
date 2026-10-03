"""Every starter project follows the engine's rules and replays exactly.

Starter projects are the most realistic graphs in the repository, so they are
the fixtures that keep the diff honest on real node shapes: large templates,
nested outputs, notes, and handle-encoded edges. Bundle starter projects are
included, and every one must pass the engine's edge rules unchanged: building
it from an empty flow adds every edge through those rules.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import langflow.initial_setup
import pytest
from lfx.services.flow_operations import (
    apply_flow_operations,
    derive_flow_operations,
    diff_flow_data,
    find_graph_violations,
    graph_hash,
    graphs_equal,
    repair_flow_data,
)

_INITIAL_SETUP = Path(langflow.initial_setup.__file__).parent
# In a source checkout, bundles live next to the backend under src/bundles.
_BUNDLES = _INITIAL_SETUP.parents[3] / "bundles"
STARTER_PROJECTS = sorted((_INITIAL_SETUP / "starter_projects").glob("*.json")) + sorted(
    _BUNDLES.glob("**/starter_projects/*.json")
)


def _flow_data(path: Path) -> dict:
    return json.loads(path.read_text())["data"]


@pytest.fixture(params=STARTER_PROJECTS, ids=[path.stem for path in STARTER_PROJECTS])
def starter(request) -> dict:
    return _flow_data(request.param)


def test_starter_projects_exist():
    assert len(STARTER_PROJECTS) >= 20


def test_starter_project_follows_every_rule(starter):
    assert find_graph_violations(starter) == []
    assert repair_flow_data(starter).fixes == []
    # Starter tables are legacy (no row ids); a write that leaves them unchanged is accepted.
    assert find_graph_violations(starter, base=starter) == []
    assert repair_flow_data(starter, base=starter).fixes == []


def _replay_one_at_a_time(base: dict, target: dict) -> dict:
    graph = base
    for operation in diff_flow_data(base, target):
        graph = apply_flow_operations(graph, [operation]).flow_data
    return graph


def test_building_a_starter_project_from_empty_replays_exactly(starter):
    empty = {"nodes": [], "edges": [], "viewport": starter.get("viewport", {})}

    assert graphs_equal(derive_flow_operations(empty, starter).flow_data, starter)
    assert graphs_equal(_replay_one_at_a_time(empty, starter), starter)
    assert graphs_equal(derive_flow_operations(starter, empty).flow_data, empty)


def test_editing_a_starter_project_replays_exactly(starter):
    target = copy.deepcopy(starter)
    nodes = target["nodes"]
    removed = nodes.pop()
    target["edges"] = [edge for edge in target["edges"] if removed["id"] not in (edge["source"], edge["target"])]
    if nodes:
        first = nodes[0]
        first["position"] = {"x": first["position"]["x"] + 40, "y": first["position"]["y"] - 10}
        template = first["data"]["node"]["template"]
        for field in template.values():
            if isinstance(field, dict) and isinstance(field.get("value"), str):
                field["value"] += " edited"
                break
        added = copy.deepcopy(first)
        added["id"] = f"{first['id']}-copy"
        added["data"]["id"] = added["id"]
        nodes.append(added)
    target["description"] = "edited"

    derived = derive_flow_operations(starter, target)

    assert graphs_equal(derived.flow_data, target)
    assert graphs_equal(_replay_one_at_a_time(starter, target), target)
    assert graph_hash(derived.flow_data) == graph_hash(target)
    # The reverse edit replays too, so restoring an earlier state is always expressible.
    assert graphs_equal(derive_flow_operations(target, starter).flow_data, starter)
