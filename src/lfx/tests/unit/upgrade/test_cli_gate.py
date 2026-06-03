"""Unit tests for the shared --upgrade-flow gate (lfx.upgrade.cli_gate)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from lfx.upgrade.cli_gate import UpgradeFlowError, UpgradeFlowMode, _load_bundled_registry, apply_upgrade_gate
from lfx.utils.flow_envelope import split_flow_envelope

# Repo fixtures: tests/unit/upgrade/test_cli_gate.py -> parents[2] == tests/
_FIXTURES = Path(__file__).parents[2] / "fixtures" / "starter_flows" / "v1.9.0"

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


# --- Registry source: the gate must default to the bundled component index ---------------
#
# Regression for the bug where `run`/`serve --upgrade-flow` passed component_cache.all_types_dict
# (empty at gate time, populated lazily only after services start) instead of the bundled index
# that `lfx upgrade` reads. An empty registry classifies EVERY node as `blocked`, so every flow
# was rejected. These tests pin that the default (all_types_dict=None) loads the bundled index.


def test_load_bundled_registry_is_populated():
    """The bundled component index must be present and non-empty in a normal install.

    If this returns an empty dict, the gate would mark every component blocked — exactly the
    bug. This is the seam the run/serve call sites rely on by passing all_types_dict=None.
    """
    registry = _load_bundled_registry()
    assert isinstance(registry, dict)
    assert registry, "bundled component index is empty"
    # Core starter components must be present so a clean flow is not classified blocked.
    flat = {ctype for components in registry.values() for ctype in components}
    assert {"ChatInput", "ChatOutput"} <= flat


def test_check_defaults_to_bundled_registry_for_clean_flow():
    """End-to-end regression: a known-clean v1.9.0 starter flow must PASS --upgrade-flow=check.

    Before the fix, the gate read an empty registry and rejected this flow with every component
    'blocked'. Passing all_types_dict=None must load the bundled index (like `lfx upgrade`) and
    let the clean flow through.
    """
    raw = json.loads((_FIXTURES / "basic_prompting.json").read_text(encoding="utf-8"))
    _, inner = split_flow_envelope(raw)
    out, count = apply_upgrade_gate(inner, mode="check")
    assert count == 0
    assert out is inner


def test_missing_bundled_registry_raises_upgrade_flow_error():
    """A broken install (no bundled index) must fail loudly via UpgradeFlowError.

    It must not silently block every component. UpgradeFlowError (not typer.Exit) keeps the
    gate's error channel uniform so each caller maps it to its own (RunError for run;
    typer.Exit for serve).
    """
    with (
        patch("lfx.interface.components._read_component_index", return_value=None),
        pytest.raises(UpgradeFlowError, match="bundled component registry is empty or missing"),
    ):
        apply_upgrade_gate(_flow(), mode="check")
