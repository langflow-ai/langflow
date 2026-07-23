"""A real, code-wireable component that pauses then resumes on an injected decision.

HumanInput's branch outputs are dynamic and can't be wired via ``.set()`` in a
unit test, so this helper mirrors HumanInput's pause/resume CONTRACT with a single
static output: first run requests a pause; on resume it reads the decision the
build path injects into ``graph.human_input_decisions`` and carries it downstream.
This exercises the real resume_from_checkpoint + inject + un-build mechanics that
``build.py``'s resume branch relies on, with a graph that wires in code.
"""

from __future__ import annotations

from lfx.custom import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.message import Message

HUMAN_INPUT_REQUIRED = "human_input_required"


class StaticPauser(Component):
    display_name = "Static Pauser"
    name = "StaticPauser"

    inputs = [MessageTextInput(name="input_value", display_name="In")]
    outputs = [Output(display_name="Out", name="out", method="run_it")]

    def _request_id(self) -> str:
        return f"{self._id}:{self.graph.run_id}"

    def _decision(self) -> dict | None:
        decisions = getattr(self.graph, "human_input_decisions", None)
        return decisions.get(self._request_id()) if isinstance(decisions, dict) else None

    def run_it(self) -> Message:
        decision = self._decision()
        if decision is None:
            self.graph.request_pause(
                reason=HUMAN_INPUT_REQUIRED,
                data={"request_id": self._request_id(), "kind": "node_input"},
            )
            return Message(text="")
        return Message(text=str(decision.get("action_id", "")))
