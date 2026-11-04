"""Malformed node contents cannot prevent later flows and versions from being reported."""

import json

import pytest
from langflow.upgrade_check import open_source
from langflow.upgrade_check.engine import Target, check_source

from tests.unit.upgrade_check.test_engine import _add_flow
from tests.unit.upgrade_check.test_reader import _execute, _load, _url


@pytest.mark.parametrize(
    "node",
    [
        {"id": "Invalid-1", "data": {"type": "TextInput", "node": None}},
        {
            "id": "Invalid-1",
            "data": {"type": "TextInput", "node": {"template": {"code": {"type": "code", "value": ["line", 7]}}}},
        },
    ],
    ids=["null_component", "non_string_code_line"],
)
def test_malformed_row_warns_and_later_flows_and_versions_are_reported(node, tmp_path):
    database = _load("1.13.0", tmp_path)
    _add_flow(database, "Malformed first flow", data=json.dumps({"nodes": [node], "edges": []}), is_component=0)
    _execute(database, "UPDATE flow SET id = ? WHERE name = ?", ("0" * 32, "Malformed first flow"))
    before = database.read_bytes()

    with open_source(_url(database)) as source:
        results = list(check_source(source, Target.from_registry({})))

    first, *later = results
    assert (first.name, first.kind, first.status, first.nodes) == ("Malformed first flow", "flow", "warn", [])
    assert first.error.startswith("flow data could not be checked")
    assert {(result.name, result.kind) for result in later} == {
        ("Fixture nested groups", "flow"),
        ("Fixture saved component", "component"),
        ("Fixture nested groups", "flow_version"),
    }
    assert database.read_bytes() == before
