"""Unit tests for the HumanInput node (LE-1449) — config, outputs, rendering, registration.

The real background suspend/resume round-trip is covered by the integration test;
these assert the pure component contract that does not need a running graph.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from lfx.components.flow_controls.human_input import HumanInput
from lfx.schema.message import Message

from tests.base import ComponentTestBaseWithoutClient


def _wired(component, *, decision=None, run_id="job-1"):
    """Give the component a minimal graph context (id + injected decision) and a stop spy.

    Mirrors the SmartRouter test convention: the framework seams ``stop`` and
    ``request_pause`` are mocked so the routing logic is asserted directly.
    """
    component._id = "human"
    decisions = {f"human:{run_id}": decision} if decision is not None else {}
    graph = SimpleNamespace(
        run_id=run_id,
        human_input_decisions=decisions,
        request_pause=MagicMock(),
        # Connected by default: the node feeds a downstream consumer, so it pauses.
        successor_map={"human": ["downstream"]},
    )
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
            "decisions": ["Approve", "Reject"],
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_default_outputs_expose_branch_handles(self, component_class):
        """A freshly created node must already carry branch outputs so handles render on drag."""
        component = component_class()
        assert [o.name for o in component.outputs] == ["branch_approve", "branch_reject"]

    def test_decisions_has_no_options_so_outputs_rebuild_on_load(self, component_class):
        """decisions must serialize with empty options so the frontend rebuilds branch outputs
        from the saved value on mount (useFetchDataOnMount fires for a real_time_refresh field
        only when its options are empty-but-defined). Re-adding options reintroduces the
        'outputs revert to defaults after page refresh' bug.
        """
        component = component_class()
        decisions = next(i for i in component.inputs if i.name == "decisions")
        assert decisions.options == []
        assert decisions.real_time_refresh is True

    async def test_update_frontend_node_resyncs_branches_from_saved_decisions(self, component_class):
        """Loading a saved flow rebuilds the branch outputs from the persisted User Actions."""
        component = component_class()
        new_frontend_node = {
            "template": {
                "decisions": {"value": ["Approve", "Reject", "Escalate"]},
                "enable_fallback": {"value": True},
            },
            "outputs": [],
        }
        node = await component.update_frontend_node(new_frontend_node, dict(new_frontend_node))
        assert [o.name for o in node["outputs"]] == [
            "branch_approve",
            "branch_reject",
            "branch_escalate",
            "branch_fallback",
        ]

    def test_two_decisions_yield_two_branches(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        node = component.update_outputs({"outputs": []}, "decisions", default_kwargs["decisions"])
        assert [o.name for o in node["outputs"]] == ["branch_approve", "branch_reject"]

    def test_adding_an_action_adds_a_branch(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        actions = ["Approve", "Reject", "Escalate"]
        node = component.update_outputs({"outputs": []}, "decisions", actions)
        assert [o.name for o in node["outputs"]] == [
            "branch_approve",
            "branch_reject",
            "branch_escalate",
        ]

    def test_multiword_action_slugifies_branch_name(self, component_class):
        component = component_class(prompt="ok?", decisions=["Request Changes"])
        node = component.update_outputs({"outputs": []}, "decisions", component.decisions)
        assert node["outputs"][0].name == "branch_request_changes"
        assert node["outputs"][0].display_name == "Request Changes"

    def test_y_n_and_menu_use_the_same_node(self, component_class):
        yn = component_class(prompt="ok?", decisions=["Yes", "No"])
        menu = component_class(prompt="pick", decisions=[f"Opt{i}" for i in range(4)])
        yn_node = yn.update_outputs({"outputs": []}, "decisions", yn.decisions)
        menu_node = menu.update_outputs({"outputs": []}, "decisions", menu.decisions)
        assert len(yn_node["outputs"]) == 2  # 2 branches
        assert len(menu_node["outputs"]) == 4  # 4 branches
        assert all(o.method == "route_branch" for o in menu_node["outputs"])

    def test_enable_fallback_adds_a_fallback_branch(self, component_class):
        component = component_class(prompt="ok?", decisions=["Approve"], enable_fallback=True)
        node = component.update_outputs({"outputs": []}, "enable_fallback", True)  # noqa: FBT003
        assert [o.name for o in node["outputs"]] == ["branch_approve", "branch_fallback"]

    def test_timeout_seconds_from_value_and_unit(self, component_class):
        days = component_class(decisions=["Approve"], timeout={"value": 3, "unit": "Days"})
        minutes = component_class(decisions=["Approve"], timeout={"value": 10, "unit": "Minutes"})
        assert days._timeout_seconds() == 259200
        assert minutes._timeout_seconds() == 600

    def test_pause_request_payload_shape(self, component_class):
        component = component_class(
            prompt="Refund this?",
            decisions=["Approve", "Reject"],
            timeout={"value": 2, "unit": "Hours"},
            enable_fallback=True,
        )
        request = component._pause_request()
        assert request["kind"] == "node_input"
        assert request["prompt"] == "Refund this?"
        assert request["allowed_decisions"] == ["approve", "reject", "fallback"]
        assert [o["action_id"] for o in request["options"]] == ["approve", "reject"]
        assert request["timeout_seconds"] == 7200
        assert request["fallback_action"] == "fallback"

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

    def test_route_branch_with_decision_returns_content_and_stops_others(self, component_class):
        component = _wired(
            component_class(prompt="payload", decisions=["Approve", "Reject"]),
            decision={"action_id": "approve", "values": {}},
        )
        result = component.route_branch()
        assert isinstance(result, Message)
        assert result.text == "payload"
        component.stop.assert_any_call("branch_reject")  # the non-chosen branch is stopped
        assert ("branch_approve",) not in [c.args for c in component.stop.call_args_list]

    def test_reject_decision_stops_approve(self, component_class):
        component = _wired(
            component_class(prompt="x", decisions=["Approve", "Reject"]),
            decision={"action_id": "reject", "values": {}},
        )
        component.route_branch()
        component.stop.assert_any_call("branch_approve")

    def test_fallback_decision_routes_to_fallback_branch(self, component_class):
        component = _wired(
            component_class(prompt="x", decisions=["Approve", "Reject"], enable_fallback=True),
            decision={"action_id": "fallback", "values": {}},
        )
        component.route_branch()
        component.stop.assert_any_call("branch_approve")
        component.stop.assert_any_call("branch_reject")
        assert ("branch_fallback",) not in [c.args for c in component.stop.call_args_list]

    def test_expired_decision_stops_every_branch(self, component_class):
        """A timed-out answer with no fallback routes to the expired sentinel, so no branch survives."""
        from lfx.run.hitl import EXPIRED_ACTION

        component = _wired(
            component_class(prompt="x", decisions=["Approve", "Reject"]),
            decision={"action_id": EXPIRED_ACTION, "values": {}},
        )
        component.route_branch()
        stopped = {c.args[0] for c in component.stop.call_args_list}
        assert stopped == {"branch_approve", "branch_reject"}

    def test_route_branch_without_decision_requests_pause(self, component_class):
        component = _wired(component_class(prompt="ok?", decisions=["Approve"]))
        result = component.route_branch()
        assert result.text == ""
        component.graph.request_pause.assert_called_once()
        _args, kwargs = component.graph.request_pause.call_args
        assert kwargs["reason"] == "human_input_required"
        assert kwargs["data"]["kind"] == "node_input"

    def test_route_branch_disconnected_node_does_not_pause(self, component_class):
        """A Human Input whose branches route nowhere must not pause the whole flow.

        A node with no outgoing edges runs as an isolated start vertex; pausing it would
        suspend the entire run for a decision that goes nowhere — and, when an Agent in the
        same run has its own tool-approval pause, leave that pause unresolved on resume.
        """
        component = _wired(component_class(prompt="ok?", decisions=["Approve"]))
        component.graph.successor_map = {}  # node feeds nothing downstream
        result = component.route_branch()
        component.graph.request_pause.assert_not_called()
        assert isinstance(result, Message)
