"""Human Input node: pause a flow for a human decision, then route on the pick (LE-1449).

The User Actions picker chooses which actions the human can take (presets like
Approve/Reject/Escalate, or custom); each becomes a branch output. On first execution
the node requests a pause carrying a ``node_input`` request; on resume the injected
decision selects exactly one branch (the others are stopped). With Enable Fallback on,
a ``fallback`` branch is added for when no user action is answered (e.g. after timeout).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lfx.custom import Component
from lfx.inputs.inputs import ActionPickerInput, BoolInput, DurationInput
from lfx.io import MultilineInput, Output
from lfx.schema.message import Message

HUMAN_INPUT_REQUIRED = "human_input_required"
_KIND_NODE_INPUT = "node_input"
_FALLBACK_ACTION = "fallback"
_UNIT_SECONDS = {"Minutes": 60, "Hours": 3600, "Days": 86400}

# Picker presets mirror langgraph's HumanInTheLoopMiddleware decisions; combobox allows custom too.
_PREDEFINED_ACTIONS = [
    "Approve",
    "Edit",
    "Reject",
    "Respond",
]


def _action_id(label: str) -> str:
    """Stable branch id for a human-facing action label (e.g. 'Request Changes' -> 'request_changes')."""
    return str(label).strip().lower().replace(" ", "_")


class HumanInput(Component):
    display_name = "Human Input"
    description = "Pause the flow to collect a human decision and route on the chosen action."
    icon = "HumanInput"
    name = "HumanInput"

    inputs = [
        MultilineInput(
            name="prompt",
            display_name="Form Content",
            info="Content shown to the human for review.",
            value="",
        ),
        ActionPickerInput(
            name="decisions",
            display_name="User Actions",
            info="Actions the human can choose; each becomes a branch output. Pick from the list or type a custom one.",
            options=_PREDEFINED_ACTIONS,
            value=["Approve", "Reject"],
            real_time_refresh=True,
            required=True,
        ),
        DurationInput(
            name="timeout",
            display_name="Timeout",
            info="How long to wait for a human response before taking the fallback path (when enabled).",
            options=["Minutes", "Hours", "Days"],
            value={"value": 3, "unit": "Days"},
        ),
        BoolInput(
            name="enable_fallback",
            display_name="Enable Fallback",
            info="Add a 'fallback' output taken when no user action is answered (e.g. after the timeout).",
            value=False,
            advanced=True,
            real_time_refresh=True,
        ),
    ]

    outputs: list[Output] = []

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """One branch output per selected action (+ optional fallback) + a stable action output."""
        if field_name not in ("decisions", "enable_fallback"):
            return frontend_node
        template = frontend_node.get("template", {})

        def _other(field: str, attr_default):
            if field in template:
                return (template.get(field) or {}).get("value")
            return getattr(self, attr_default[0], attr_default[1])

        actions = field_value if field_name == "decisions" else _other("decisions", ("decisions", []))
        fallback_on = (
            field_value if field_name == "enable_fallback" else _other("enable_fallback", ("enable_fallback", False))
        )
        outputs: list[Output] = []
        seen: set[str] = set()
        for label in actions or []:
            action_id = _action_id(label)
            if not action_id or action_id in seen:
                continue
            seen.add(action_id)
            outputs.append(
                Output(
                    display_name=str(label).strip(),
                    name=f"branch_{action_id}",
                    method="route_branch",
                    group_outputs=True,
                )
            )
        if fallback_on:
            outputs.append(
                Output(
                    display_name="Fallback",
                    name=f"branch_{_FALLBACK_ACTION}",
                    method="route_branch",
                    group_outputs=True,
                )
            )
        frontend_node["outputs"] = outputs
        return frontend_node

    def _actions(self) -> list[tuple[str, str]]:
        """Selected actions as (action_id, label) pairs, de-duplicated by id."""
        seen: set[str] = set()
        actions: list[tuple[str, str]] = []
        for label in getattr(self, "decisions", []) or []:
            action_id = _action_id(label)
            if not action_id or action_id in seen:
                continue
            seen.add(action_id)
            actions.append((action_id, str(label).strip()))
        return actions

    def _rendered_prompt(self) -> str:
        return str(getattr(self, "prompt", "") or "")

    def _timeout_seconds(self) -> int:
        timeout = getattr(self, "timeout", None) or {}
        if not isinstance(timeout, dict):
            return 0
        unit = timeout.get("unit", "Days") or "Days"
        return int(timeout.get("value", 0) or 0) * _UNIT_SECONDS.get(unit, _UNIT_SECONDS["Days"])

    def _request_id(self) -> str:
        run_id = str(getattr(self.graph, "run_id", "") or "")
        return f"{self._id}:{run_id}"

    def _injected_decision(self) -> dict | None:
        decisions = getattr(self.graph, "human_input_decisions", None) if self.graph is not None else None
        if not isinstance(decisions, dict):
            return None
        return decisions.get(self._request_id())

    def _allowed_decisions(self) -> list[str]:
        ids = [action_id for action_id, _ in self._actions()]
        if getattr(self, "enable_fallback", False):
            ids.append(_FALLBACK_ACTION)
        return ids

    def _pause_request(self) -> dict[str, Any]:
        return {
            "request_id": self._request_id(),
            "kind": _KIND_NODE_INPUT,
            "prompt": self._rendered_prompt(),
            "options": [{"action_id": action_id, "label": label} for action_id, label in self._actions()],
            "allowed_decisions": self._allowed_decisions(),
            "timeout_seconds": self._timeout_seconds(),
            "fallback_action": _FALLBACK_ACTION if getattr(self, "enable_fallback", False) else None,
            "paused_at": datetime.now(timezone.utc).isoformat(),
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
        return Message(text=self._rendered_prompt())
