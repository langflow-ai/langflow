"""Integration tests for the upgrade machinery against real v1.9.0 starter flows.

These flows are frozen snapshots from the Langflow v1.9.0 release. They exercise
the checker and applier against real component code rather than hand-crafted stubs.

The tests make no assumption about which nodes are outdated vs. ok — the component
registry evolves over time and the answers will change across releases. Instead they
verify the contract:

  1. The checker runs without error on every fixture flow.
  2. Every node status is one of the four valid values.
  3. The applier produces valid JSON.
  4. After applying safe upgrades, re-checking the same nodes shows no new outdated_safe nodes
     (i.e. the apply loop converges in one pass).
  5. Blocked and breaking nodes are left unchanged by the applier.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from lfx.upgrade.applier import apply_safe_upgrades
from lfx.upgrade.checker import check_flow_compatibility

FIXTURES_DIR = pathlib.Path(__file__).parent.parent.parent / "fixtures" / "starter_flows" / "v1.9.0"

FIXTURE_FLOWS = list(FIXTURES_DIR.glob("*.json"))
assert FIXTURE_FLOWS, f"No starter flow fixtures found in {FIXTURES_DIR}"


def _load_registry() -> dict:
    """Load the bundled component index directly for test use.

    Bypasses the SHA integrity gate in _read_component_index — that check is a
    production security measure and is not appropriate for a test fixture loader
    whose only job is to get real component data into the checker.
    """
    import inspect

    import orjson

    import lfx

    pkg_dir = pathlib.Path(inspect.getfile(lfx)).parent
    idx_path = pkg_dir / "_assets" / "component_index.json"
    if not idx_path.exists():
        return {}
    blob = orjson.loads(idx_path.read_bytes())
    all_types: dict = {}
    for category, components in blob.get("entries", []):
        all_types.setdefault(category, {}).update(components)
    return all_types


@pytest.fixture(scope="module")
def registry() -> dict:
    loaded = _load_registry()
    assert loaded, "Bundled component registry is empty or missing; integration checks are not meaningful"
    return loaded


@pytest.fixture(scope="module")
def flow_data_map() -> dict[str, dict]:
    """Return a map of flow_name -> flow graph data dict (the inner ``data`` key).

    Real Langflow flow JSON files have the shape::

        {
          "name": "...",
          "data": { "nodes": [...], "edges": [...], "viewport": {...} },
          ...
        }

    The checker and applier expect the inner ``data`` dict (with top-level ``nodes``
    and ``edges`` keys), so we unwrap it here. If a fixture file is already in the
    flat format (no outer ``data`` key), we use it as-is.
    """
    result = {}
    for f in FIXTURE_FLOWS:
        raw = json.loads(f.read_text(encoding="utf-8"))
        result[f.stem] = raw["data"] if "data" in raw and "nodes" in raw.get("data", {}) else raw
    return result


# ---------------------------------------------------------------------------
# Parametrise over every fixture file
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("flow_name", [f.stem for f in FIXTURE_FLOWS])
def test_checker_runs_without_error(flow_name, flow_data_map, registry):
    """Checker must not raise on any real starter flow."""
    flow = flow_data_map[flow_name]
    report = check_flow_compatibility(flow, registry)
    assert report is not None


@pytest.mark.parametrize("flow_name", [f.stem for f in FIXTURE_FLOWS])
def test_all_node_statuses_are_valid(flow_name, flow_data_map, registry):
    """Every node must resolve to one of the four known statuses."""
    valid = {"ok", "outdated_safe", "outdated_breaking", "blocked"}
    flow = flow_data_map[flow_name]
    report = check_flow_compatibility(flow, registry)
    for node in report.nodes:
        assert node.status in valid, (
            f"Unexpected status '{node.status}' for {node.display_name} ({node.component_type})"
        )


@pytest.mark.parametrize("flow_name", [f.stem for f in FIXTURE_FLOWS])
def test_applier_produces_valid_json(flow_name, flow_data_map, registry):
    """apply_safe_upgrades must always return a JSON-serialisable dict."""
    flow = flow_data_map[flow_name]
    report = check_flow_compatibility(flow, registry)
    updated = apply_safe_upgrades(flow, registry, report)
    # Must round-trip through JSON without error
    serialised = json.dumps(updated)
    reparsed = json.loads(serialised)
    assert isinstance(reparsed, dict)


@pytest.mark.parametrize("flow_name", [f.stem for f in FIXTURE_FLOWS])
def test_apply_converges_in_one_pass(flow_name, flow_data_map, registry):
    """After applying safe upgrades, re-checking should find no new outdated_safe nodes.

    This verifies the applier actually wrote the current registry code and did not
    introduce a new delta on the next check.
    """
    flow = flow_data_map[flow_name]
    report1 = check_flow_compatibility(flow, registry)
    updated = apply_safe_upgrades(flow, registry, report1)
    report2 = check_flow_compatibility(updated, registry)

    # Any node that was safe in pass 1 must now be ok in pass 2
    safe_ids_pass1 = {n.node_id for n in report1.nodes if n.status == "outdated_safe"}
    still_safe_pass2 = {n.node_id for n in report2.nodes if n.status == "outdated_safe" and n.node_id in safe_ids_pass1}
    assert not still_safe_pass2, (
        f"Applier did not converge for {flow_name}: these nodes are still outdated_safe after apply: {still_safe_pass2}"
    )


@pytest.mark.parametrize("flow_name", [f.stem for f in FIXTURE_FLOWS])
def test_applier_does_not_change_blocking_or_breaking_nodes(flow_name, flow_data_map, registry):
    """Blocked and breaking nodes must be bit-for-bit identical before and after apply."""
    flow = flow_data_map[flow_name]
    report = check_flow_compatibility(flow, registry)
    updated = apply_safe_upgrades(flow, registry, report)

    unchanged_ids = {n.node_id for n in report.nodes if n.status in ("blocked", "outdated_breaking")}
    if not unchanged_ids:
        return  # nothing to check

    orig_nodes = {(n.get("data", {}).get("id") or n.get("id")): n for n in flow.get("nodes", [])}
    updated_nodes = {(n.get("data", {}).get("id") or n.get("id")): n for n in updated.get("nodes", [])}
    for node_id in unchanged_ids:
        orig_code = orig_nodes[node_id]["data"]["node"]["template"]["code"]["value"]
        updated_code = updated_nodes[node_id]["data"]["node"]["template"]["code"]["value"]
        assert orig_code == updated_code, f"Blocked/breaking node {node_id} in {flow_name} was unexpectedly modified"


@pytest.mark.parametrize("flow_name", [f.stem for f in FIXTURE_FLOWS])
def test_original_flow_not_mutated(flow_name, flow_data_map, registry):
    """The applier must never mutate the original flow dict."""
    flow = flow_data_map[flow_name]
    # Snapshot all code values before
    original_codes = {}
    for node in flow.get("nodes", []):
        nid = node.get("data", {}).get("id") or node.get("id")
        code_field = node.get("data", {}).get("node", {}).get("template", {}).get("code")
        if isinstance(code_field, dict):
            original_codes[nid] = code_field.get("value")

    report = check_flow_compatibility(flow, registry)
    apply_safe_upgrades(flow, registry, report)

    for node in flow.get("nodes", []):
        nid = node.get("data", {}).get("id") or node.get("id")
        if nid not in original_codes:
            continue
        code_field = node.get("data", {}).get("node", {}).get("template", {}).get("code")
        current_code = code_field.get("value") if isinstance(code_field, dict) else None
        assert current_code == original_codes[nid], f"Original flow was mutated for node {nid} in {flow_name}"


# ---------------------------------------------------------------------------
# Summary test — print a human-readable report for CI logs
# ---------------------------------------------------------------------------


def test_upgrade_summary_report(flow_data_map, registry):
    """Print a human-readable summary of upgrade status across all fixture flows."""
    import sys

    for flow_name, flow in sorted(flow_data_map.items()):
        report = check_flow_compatibility(flow, registry)
        statuses = {}
        for n in report.nodes:
            statuses[n.status] = statuses.get(n.status, 0) + 1
        sys.stderr.write(f"{flow_name}: {dict(sorted(statuses.items()))}\n")
    # Always passes — output is visible in pytest -s
