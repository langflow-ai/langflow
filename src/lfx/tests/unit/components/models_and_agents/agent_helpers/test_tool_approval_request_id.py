"""Per-pause request_id nonce for agent tool approvals.

One agent can pause multiple times in a run; without a per-pause nonce every
approval shares ``component_id:run_id`` and a stale resume for approval N would
be accepted while approval N+1 is pending (and applied to the wrong tool call).
"""

from types import SimpleNamespace

from lfx.components.models_and_agents.agent_helpers.tool_approval import ToolApprovalMixin
from lfx.run.hitl import request_id_targets_vertex

EMPTY_INTERRUPT = {"action_requests": [], "review_configs": []}


class _Agent(ToolApprovalMixin):
    def __init__(self, decisions: dict | None = None):
        self._id = "Agent-x"
        self.graph = SimpleNamespace(run_id="run-1", human_input_decisions=decisions or {})


def test_request_id_carries_interrupt_nonce():
    request = _Agent()._map_interrupt_to_request(EMPTY_INTERRUPT, "int-A")
    assert request["request_id"] == "Agent-x:run-1:int-A"


def test_request_id_without_interrupt_id_keeps_legacy_shape():
    request = _Agent()._map_interrupt_to_request(EMPTY_INTERRUPT)
    assert request["request_id"] == "Agent-x:run-1"


def test_stale_decision_does_not_match_a_newer_interrupt():
    agent = _Agent({"Agent-x:run-1:int-A": {"action_id": "approve"}})
    assert agent._injected_agent_decision("run-1", "int-B") is None


def test_decision_matches_its_exact_interrupt():
    decision = {"action_id": "reject"}
    agent = _Agent({"Agent-x:run-1:int-A": decision})
    assert agent._injected_agent_decision("run-1", "int-A") == decision


def test_legacy_two_part_decision_still_resumes_old_checkpoints():
    decision = {"action_id": "approve"}
    agent = _Agent({"Agent-x:run-1": decision})
    assert agent._injected_agent_decision("run-1", "int-A") == decision


def test_legacy_caller_without_interrupt_id_matches_single_nonced_decision():
    """Saved flows freeze pre-nonce agent code that calls ``_injected_agent_decision(thread)``.

    The engine keys the injected decision by nonce (``component:thread:interrupt``);
    the lone nonced decision must still resolve or the resumed agent re-invokes the
    LLM on the interrupted thread and the provider rejects the dangling tool_call.
    """
    decision = {"action_id": "approve"}
    agent = _Agent({"Agent-x:run-1:int-A": decision})
    assert agent._injected_agent_decision("run-1") == decision


def test_legacy_caller_without_interrupt_id_stays_none_when_ambiguous():
    agent = _Agent(
        {
            "Agent-x:run-1:int-A": {"action_id": "approve"},
            "Agent-x:run-1:int-B": {"action_id": "reject"},
        }
    )
    assert agent._injected_agent_decision("run-1") is None


def test_legacy_caller_without_interrupt_id_ignores_other_threads():
    agent = _Agent({"Agent-x:run-2:int-A": {"action_id": "approve"}})
    assert agent._injected_agent_decision("run-1") is None


async def test_legacy_read_pending_interrupt_value_helper_still_exists():
    """Frozen agent code still calls the value-only helper.

    The rename to ``_read_pending_interrupt`` must keep a value-only shim or
    resumed saved flows crash with AttributeError right after the decision resolves.
    """

    class _Interrupt:
        value = {"action_requests": [{"name": "tool"}]}
        id = "int-A"

    class _Snapshot:
        interrupts = [_Interrupt()]
        tasks = []

    class _StubAgent:
        async def aget_state(self, _config):
            return _Snapshot()

    value = await _Agent()._read_pending_interrupt_value(_StubAgent(), {"configurable": {}})
    assert value == {"action_requests": [{"name": "tool"}]}


def test_has_candidate_decision_matches_any_nonce_but_not_other_threads():
    agent = _Agent({"Agent-x:run-1:int-A": {"action_id": "approve"}})
    assert agent._has_candidate_decision("run-1")
    assert not agent._has_candidate_decision("run-2")
    assert not _Agent()._has_candidate_decision("run-1")


def test_request_id_targets_vertex_accepts_node_and_nonced_shapes():
    assert request_id_targets_vertex("HumanInput-a:run-1", "HumanInput-a", "run-1")
    assert request_id_targets_vertex("Agent-x:run-1:int-A", "Agent-x", "run-1")


def test_request_id_targets_vertex_rejects_other_vertices_and_runs():
    assert not request_id_targets_vertex("Agent-x:run-1", "Agent-y", "run-1")
    assert not request_id_targets_vertex("Agent-x:run-2", "Agent-x", "run-1")
    assert not request_id_targets_vertex("Agent-x:run-12", "Agent-x", "run-1")
