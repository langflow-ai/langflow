"""Unit tests for the HumanInput node (LE-1449) — config, outputs, rendering, registration.

The real background suspend/resume round-trip is covered by the integration test;
these assert the pure component contract that does not need a running graph.
"""

from __future__ import annotations

import pytest
from lfx.components.flow_controls.human_input import HumanInput
from lfx.schema.data import Data

from tests.base import ComponentTestBaseWithoutClient


class TestHumanInputComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return HumanInput

    @pytest.fixture
    def default_kwargs(self):
        return {
            "prompt": "Approve this?",
            "decisions": [
                {"action_id": "approve", "label": "Approve"},
                {"action_id": "reject", "label": "Reject"},
            ],
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_two_decisions_yield_two_branches_plus_action(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        node = component.update_outputs({"outputs": []}, "decisions", default_kwargs["decisions"])
        assert [o.name for o in node["outputs"]] == ["branch_approve", "branch_reject", "action"]

    def test_adding_a_row_adds_a_branch(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        rows = [{"action_id": "a"}, {"action_id": "b"}, {"action_id": "c"}]
        node = component.update_outputs({"outputs": []}, "decisions", rows)
        assert [o.name for o in node["outputs"]] == ["branch_a", "branch_b", "branch_c", "action"]

    def test_y_n_and_menu_use_the_same_node(self, component_class):
        yn = component_class(prompt="ok?", decisions=[{"action_id": "yes"}, {"action_id": "no"}])
        menu = component_class(prompt="pick", decisions=[{"action_id": f"opt{i}"} for i in range(4)])
        yn_node = yn.update_outputs({"outputs": []}, "decisions", yn.decisions)
        menu_node = menu.update_outputs({"outputs": []}, "decisions", menu.decisions)
        assert len(yn_node["outputs"]) == 3  # 2 branches + action
        assert len(menu_node["outputs"]) == 5  # 4 branches + action
        assert all(o.method in {"route_branch", "emit_action"} for o in menu_node["outputs"])

    def test_prompt_interpolates_variables(self, component_class):
        component = component_class(prompt="Refund {customer}?", prompt_variables=Data(data={"customer": "Ada"}))
        assert component._rendered_prompt() == "Refund Ada?"

    def test_missing_variable_renders_empty_no_raise(self, component_class):
        component = component_class(
            prompt="Refund {customer} for {amount}?", prompt_variables=Data(data={"customer": "Ada"})
        )
        assert component._rendered_prompt() == "Refund Ada for ?"

    def test_pause_request_payload_shape(self, component_class):
        component = component_class(
            prompt="Refund {customer}?",
            prompt_variables=Data(data={"customer": "Ada"}),
            decisions=[{"action_id": "approve", "label": "Approve"}, {"action_id": "reject", "label": "Reject"}],
            form_fields=[{"name": "reason", "type": "str", "required": True}],
        )
        request = component._pause_request()
        assert request["kind"] == "node_input"
        assert request["prompt"] == "Refund Ada?"
        assert request["allowed_decisions"] == ["approve", "reject"]
        assert [o["action_id"] for o in request["options"]] == ["approve", "reject"]
        assert request["schema"] == [{"name": "reason", "type": "str", "required": True}]

    def test_registered_in_both_import_paths_same_class(self):
        from lfx.components.flow_controls import HumanInput as FlowControlsHumanInput
        from lfx.components.logic import HumanInput as LogicHumanInput

        assert FlowControlsHumanInput is LogicHumanInput
        assert FlowControlsHumanInput.__name__ == "HumanInput"

    def test_listed_in_component_index(self):
        import json
        from pathlib import Path

        import lfx

        index_path = Path(lfx.__file__).parent / "_assets" / "component_index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        assert "HumanInput" in json.dumps(index)
