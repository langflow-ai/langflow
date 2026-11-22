"""A reviewed dynamic-field limitation cannot hide another historical regression."""

import copy
import hashlib

import pytest
from component_compatibility import CompatibilityGateError, contract, digest
from historical_compatibility_gate import check_pins
from test_component_compatibility import component


def evidence(tmp_path):
    path = tmp_path / "v1/flow.json"
    path.parent.mkdir()
    path.write_text("saved fixture")
    target = component()
    before = {"v1": {"hard_flows": {"flow.json::node": "no_action", "other": "no_action"}}}
    after = copy.deepcopy(before)
    after["v1"]["hard_flows"]["flow.json::node"] = "outdated_breaking"
    entry = {
        "release": "v1",
        "fixture": "flow.json",
        "node_id": "node",
        "component": "Example",
        "fixture_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "target_contract_sha256": digest(contract(target)),
        "expected": "no_action",
        "observed": "outdated_breaking",
        "reason": "Reviewed generated-field uncertainty",
    }
    return before, after, {"format_version": 1, "limitations": [entry]}, {"Example": target}


def test_exact_reviewed_delta_is_visible(tmp_path):
    before, after, ledger, lookup = evidence(tmp_path)
    [message] = check_pins(before, after, ledger, tmp_path, lookup)
    assert "Reviewed" in message


@pytest.mark.parametrize("change", ["target", "fixture", "other_delta", "stale", "wrong_status"])
def test_limitation_cannot_hide_unreviewed_changes(change, tmp_path):
    before, after, ledger, lookup = evidence(tmp_path)
    if change == "target":
        lookup["Example"]["outputs"] = []
    elif change == "fixture":
        (tmp_path / "v1/flow.json").write_text("different saved fixture")
    elif change == "other_delta":
        after["v1"]["hard_flows"]["other"] = "blocked"
    elif change == "stale":
        after = before
    else:
        after["v1"]["hard_flows"]["flow.json::node"] = "blocked"
    with pytest.raises(CompatibilityGateError):
        check_pins(before, after, ledger, tmp_path, lookup)
