"""Unit tests for the shared --upgrade-flow gate (lfx.upgrade.cli_gate)."""

import pytest
from lfx.upgrade.cli_gate import UpgradeFlowError, UpgradeFlowMode, apply_upgrade_gate

REGISTRY_CODE = "class C:\n    pass  # v2"
NODE_CODE = "class C:\n    pass  # v1"


def _outputs():
    return [{"name": "o", "display_name": "O", "types": ["M"], "method": "m", "allows_loop": False}]


def _registry(code: str = REGISTRY_CODE):
    return {"Cat": {"MyComp": {"template": {"code": {"value": code}}, "outputs": _outputs(), "metadata": {}}}}


def _flow(code: str = NODE_CODE, type_: str = "MyComp"):
    return {
        "nodes": [
            {
                "id": "n1",
                "data": {
                    "id": "n1",
                    "type": type_,
                    "node": {
                        "display_name": "My Component",
                        "template": {"code": {"value": code}},
                        "outputs": _outputs(),
                    },
                },
            }
        ],
        "edges": [],
    }


def test_mode_enum_str_equality():
    """UpgradeFlowMode subclasses str so literal comparisons keep working."""
    assert UpgradeFlowMode.CHECK == "check"
    assert UpgradeFlowMode.SAFE == "safe"


def test_check_clean_returns_unchanged():
    flow = _flow(code=REGISTRY_CODE)
    out, count = apply_upgrade_gate(flow, _registry(), "check")
    assert count == 0
    assert out is flow


def test_check_incompatible_raises():
    with pytest.raises(UpgradeFlowError, match="incompatible components"):
        apply_upgrade_gate(_flow(code=NODE_CODE), _registry(), "check")


def test_safe_applies_safe_upgrade():
    out, count = apply_upgrade_gate(_flow(code=NODE_CODE), _registry(), "safe")
    assert count == 1
    assert out["nodes"][0]["data"]["node"]["template"]["code"]["value"] == REGISTRY_CODE


def test_safe_blocked_raises():
    with pytest.raises(UpgradeFlowError, match="cannot be auto-upgraded"):
        apply_upgrade_gate(_flow(code=NODE_CODE, type_="Ghost"), {}, "safe")


def test_unknown_mode_raises():
    with pytest.raises(UpgradeFlowError, match="Unknown --upgrade-flow"):
        apply_upgrade_gate(_flow(), _registry(), "typo")


def test_accepts_enum_mode():
    out, count = apply_upgrade_gate(_flow(code=NODE_CODE), _registry(), UpgradeFlowMode.SAFE)
    assert count == 1
    assert out["nodes"][0]["data"]["node"]["template"]["code"]["value"] == REGISTRY_CODE
