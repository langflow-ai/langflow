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
            value=["Approve", "Reject"],
            real_time_refresh=True,
            required=True,
        ),
        DurationInput(
            name="timeout",
            display_name="Timeout",
            info="A response received after this window is rerouted to the fallback path (when enabled) "
            "instead of the chosen action. The run stays paused until a response arrives or the "
            "server's suspended-run deadline expires it. Set to 0 to wait indefinitely.",
            options=["Minutes", "Hours", "Days"],
            value={"value": 3, "unit": "Days"},
        ),
        BoolInput(
            name="enable_fallback",
            display_name="Enable Fallback",
            info="Add a 'fallback' output taken when the answer arrives after the timeout window.",
            value=False,
            advanced=True,
            real_time_refresh=True,
        ),
    ]

    # Default branch outputs mirror the default ``decisions`` so a freshly dragged
    # node shows handles immediately (update_outputs only fires on a field change).
    outputs: list[Output] = [
        Output(display_name="Approve", name="branch_approve", method="route_branch", group_outputs=True),
        Output(display_name="Reject", name="branch_reject", method="route_branch", group_outputs=True),
    ]

    async def update_frontend_node(self, new_frontend_node: dict, current_frontend_node: dict) -> dict:
        """Rebuild branch outputs from the saved User Actions so loaded/refreshed flows keep their handles."""
        new_frontend_node = await super().update_frontend_node(new_frontend_node, current_frontend_node)
        decisions = (new_frontend_node.get("template", {}).get("decisions") or {}).get("value")
        self.update_outputs(new_frontend_node, "decisions", decisions if decisions is not None else [])
        return new_frontend_node

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

    def _has_downstream_consumer(self) -> bool:
        """True if any branch output feeds a downstream node.

        A node with no outgoing edges runs as an isolated start vertex; pausing it would
        suspend the whole run for a decision that routes nowhere (and, alongside an Agent's
        own tool-approval pause, leave that pause unresolved on resume). The successor_map is
        absent only outside a prepared graph (standalone/tests), where the old behavior holds.
        """
        graph = getattr(self, "graph", None)
        successor_map = getattr(graph, "successor_map", None)
        if not isinstance(successor_map, dict):
            return True
        return bool(successor_map.get(self._id))

    def _suspend(self) -> None:
        self.graph.request_pause(reason=HUMAN_INPUT_REQUIRED, data=self._pause_request())
        self.status = "Awaiting human input"

    def route_branch(self) -> Message:
        decision = self._injected_decision()
        if decision is None:
            if not self._has_downstream_consumer():
                self.status = "Skipped: no connected outputs"
                return Message(text=self._rendered_prompt())
            self._suspend()
            return Message(text="")
        chosen = decision.get("action_id")
        non_chosen = [action_id for action_id in self._allowed_decisions() if action_id != chosen]
        for action_id in non_chosen:
            self.stop(f"branch_{action_id}")
        return Message(text=self._rendered_prompt())
