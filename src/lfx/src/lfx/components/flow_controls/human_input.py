"""Human Input node: pause a flow for a human decision, then route on the pick (LE-1449).

One configurable node covers both Y/N confirmation (a 2-row decisions table) and
N-way disambiguation (N rows) — pure configuration, no code branching between modes.
On first execution the node requests a pause carrying a ``node_input`` request; on
resume the injected decision selects exactly one branch (the others are stopped).
"""

from __future__ import annotations

from typing import Any

from lfx.custom import Component
from lfx.io import DataInput, MultilineInput, Output, TableInput
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.schema.table import EditMode

HUMAN_INPUT_REQUIRED = "human_input_required"
_KIND_NODE_INPUT = "node_input"


class _MissingDict(dict):
    """format_map source that renders an unknown ``{var}`` as an empty string."""

    def __missing__(self, key: str) -> str:
        return ""


class HumanInput(Component):
    display_name = "Human Input"
    description = "Pause the flow to collect a human decision and route on the chosen action."
    icon = "circle-help"
    name = "HumanInput"

    inputs = [
        MultilineInput(
            name="prompt",
            display_name="Prompt",
            info="Question shown to the human. Supports {variable} interpolation from Variables.",
            value="",
        ),
        DataInput(
            name="prompt_variables",
            display_name="Variables",
            info="Optional values interpolated into the prompt; a missing {variable} renders empty.",
            required=False,
            advanced=True,
        ),
        MultilineInput(
            name="input_value",
            display_name="Input",
            info="Value carried down the selected branch on resume.",
            required=False,
        ),
        TableInput(
            name="decisions",
            display_name="Decisions",
            info="One row per choice. Two rows = Y/N confirmation; N rows = an N-way menu.",
            table_schema=[
                {
                    "name": "action_id",
                    "display_name": "Action ID",
                    "type": "str",
                    "description": "Stable id for the choice (also the branch output name).",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "label",
                    "display_name": "Label",
                    "type": "str",
                    "description": "Human-facing button text.",
                    "default": "",
                    "edit_mode": EditMode.INLINE,
                },
            ],
            value=[
                {"action_id": "approve", "label": "Approve"},
                {"action_id": "reject", "label": "Reject"},
            ],
            real_time_refresh=True,
            required=True,
        ),
        TableInput(
            name="form_fields",
            display_name="Form Fields",
            info="Optional fields the human fills in; echoed back as structured output on resume.",
            table_schema=[
                {"name": "name", "display_name": "Name", "type": "str", "edit_mode": EditMode.INLINE},
                {
                    "name": "type",
                    "display_name": "Type",
                    "type": "str",
                    "default": "str",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "required",
                    "display_name": "Required",
                    "type": "boolean",
                    "default": False,
                    "edit_mode": EditMode.INLINE,
                },
            ],
            value=[],
            advanced=True,
        ),
    ]

    outputs: list[Output] = []

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """One branch output per decision row + a stable action output (SmartRouter pattern)."""
        if field_name == "decisions":
            frontend_node["outputs"] = []
            for row in field_value or []:
                action_id = row.get("action_id")
                if not action_id:
                    continue
                frontend_node["outputs"].append(
                    Output(
                        display_name=row.get("label") or action_id,
                        name=f"branch_{action_id}",
                        method="route_branch",
                        group_outputs=True,
                    )
                )
            frontend_node["outputs"].append(
                Output(display_name="Action", name="action", method="emit_action", group_outputs=True)
            )
        return frontend_node

    def _rendered_prompt(self) -> str:
        variables = getattr(self, "prompt_variables", None)
        data = variables.data if isinstance(variables, Data) else (variables or {})
        mapping = _MissingDict(data if isinstance(data, dict) else {})
        try:
            return str(self.prompt or "").format_map(mapping)
        except (ValueError, IndexError):
            # Malformed format spec (e.g. a stray "{") must not crash a paused flow.
            return str(self.prompt or "")

    def _request_id(self) -> str:
        run_id = str(getattr(self.graph, "run_id", "") or "")
        return f"{self._id}:{run_id}"

    def _injected_decision(self) -> dict | None:
        decisions = getattr(self.graph, "human_input_decisions", None) if self.graph is not None else None
        if not isinstance(decisions, dict):
            return None
        return decisions.get(self._request_id())

    def _allowed_decisions(self) -> list[str]:
        return [row["action_id"] for row in (getattr(self, "decisions", []) or []) if row.get("action_id")]

    def _pause_request(self) -> dict[str, Any]:
        return {
            "request_id": self._request_id(),
            "kind": _KIND_NODE_INPUT,
            "prompt": self._rendered_prompt(),
            "options": [
                {"action_id": row.get("action_id"), "label": row.get("label") or row.get("action_id")}
                for row in (getattr(self, "decisions", []) or [])
                if row.get("action_id")
            ],
            "schema": [dict(row) for row in (getattr(self, "form_fields", []) or [])],
            "allowed_decisions": self._allowed_decisions(),
        }

    def _suspend(self) -> None:
        self.graph.request_pause(reason=HUMAN_INPUT_REQUIRED, data=self._pause_request())
        self.status = "Awaiting human input"

    def route_branch(self) -> Message:
        decision = self._injected_decision()
        if decision is None:
            self._suspend()
            return Message(text="")
        chosen = decision.get("action_id")
        for action_id in self._allowed_decisions():
            if action_id != chosen:
                self.stop(f"branch_{action_id}")
        return Message(text=str(getattr(self, "input_value", "") or ""))

    def emit_action(self) -> Data:
        decision = self._injected_decision()
        if decision is None:
            self._suspend()
            return Data(
                data={"__action_id": None, "__action_value": None, "__rendered_content": self._rendered_prompt()}
            )
        return Data(
            data={
                "__action_id": decision.get("action_id"),
                "__action_value": decision.get("values", {}),
                "__rendered_content": self._rendered_prompt(),
            }
        )
