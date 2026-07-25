"""Load committed fixture_index entries and fixture JSON payloads.

Used by ``test_subsystem_coverage`` (and re-exported from this package's
``__init__``) to resolve a flow id to its index entry and on-disk fixture.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from tests.locust.langflow_runtime.flows.defaults import FLOWS_DIR

FIXTURE_INDEX_PATH = FLOWS_DIR / "fixture_index.json"


def load_fixture_index() -> dict[str, Any]:
    return json.loads(FIXTURE_INDEX_PATH.read_text(encoding="utf-8"))


def flow_entry(flow_id: str) -> dict[str, Any]:
    for flow in load_fixture_index()["flows"]:
        if flow["id"] == flow_id:
            return flow
    pytest.fail(f"flow {flow_id} missing from fixture_index")


def load_fixture_payload(flow_id: str) -> dict[str, Any]:
    entry = flow_entry(flow_id)
    return json.loads((FLOWS_DIR / entry["fixture_path"]).read_text(encoding="utf-8"))
