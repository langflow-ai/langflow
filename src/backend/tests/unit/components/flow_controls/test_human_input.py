"""Unit tests for the HumanInput node (LE-1449) — config, outputs, rendering, registration.

The real background suspend/resume round-trip is covered by the integration test;
these assert the pure component contract that does not need a running graph.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from lfx.components.flow_controls.human_input import HumanInput
from lfx.schema.data import Data
from lfx.schema.message import Message

from tests.base import ComponentTestBaseWithoutClient


def _wired(component, *, decision=None, run_id="job-1"):
    """Give the component a minimal graph context (id + injected decision) and a stop spy.

    Mirrors the SmartRouter test convention: the framework seams ``stop`` and
    ``request_pause`` are mocked so the routing logic is asserted directly.
    """
    component._id = "human"
    decisions = {f"human:{run_id}": decision} if decision is not None else {}
    graph = SimpleNamespace(run_id=run_id, human_input_decisions=decisions, request_pause=MagicMock())
    component._vertex = SimpleNamespace(graph=graph)  # self.graph resolves to self._vertex.graph
    component.stop = MagicMock()
    return component


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

    def test_route_branch_with_decision_returns_value_and_stops_others(self, component_class):
        component = _wired(
            component_class(input_value="payload", decisions=[{"action_id": "approve"}, {"action_id": "reject"}]),
            decision={"action_id": "approve", "values": {}},
        )
        result = component.route_branch()
        assert isinstance(result, Message)
        assert result.text == "payload"
        component.stop.assert_any_call("branch_reject")  # the non-chosen branch is stopped
        assert ("branch_approve",) not in [c.args for c in component.stop.call_args_list]

    def test_reject_decision_stops_approve(self, component_class):
        component = _wired(
            component_class(input_value="x", decisions=[{"action_id": "approve"}, {"action_id": "reject"}]),
            decision={"action_id": "reject", "values": {}},
        )
        component.route_branch()
        component.stop.assert_any_call("branch_approve")

    def test_route_branch_without_decision_requests_pause(self, component_class):
        component = _wired(component_class(prompt="ok?", decisions=[{"action_id": "approve"}]))
        result = component.route_branch()
        assert result.text == ""
        component.graph.request_pause.assert_called_once()
        _args, kwargs = component.graph.request_pause.call_args
        assert kwargs["reason"] == "human_input_required"
        assert kwargs["data"]["kind"] == "node_input"

    def test_emit_action_with_decision_surfaces_id_and_values(self, component_class):
        component = _wired(
            component_class(prompt="ok?", decisions=[{"action_id": "approve"}]),
            decision={"action_id": "approve", "values": {"reason": "fraud"}},
        )
        result = component.emit_action()
        assert isinstance(result, Data)
        assert result.data["__action_id"] == "approve"
        assert result.data["__action_value"] == {"reason": "fraud"}

    def test_emit_action_without_decision_requests_pause(self, component_class):
        component = _wired(component_class(prompt="ok?", decisions=[{"action_id": "approve"}]))
        result = component.emit_action()
        assert result.data["__action_id"] is None
        component.graph.request_pause.assert_called_once()
