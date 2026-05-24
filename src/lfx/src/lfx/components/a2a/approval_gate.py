"""Approval Gate component — human guardrail before a side-effecting action."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, MessageInput, MultilineInput, Output
from lfx.schema.message import Message


class ApprovalGateComponent(Component):
    """Blocks a side-effecting action unless it has been approved.

    Place this node before anything with an external side effect (e.g. an
    A2A delegation, a tool call, finalizing an artifact). It is **fail-closed**:
    unless ``Approved`` is true, the action is blocked and the run fails loudly
    rather than silently performing the unapproved action.

    A human releases the action by toggling ``Approved`` (in the UI, via an
    API tweak, or wired from an upstream decision).
    """

    display_name = "Approval Gate"
    description = "Human guardrail: blocks a side-effecting action unless it is explicitly approved."
    documentation: str = "https://a2a-protocol.org/"
    icon = "ShieldCheck"
    name = "ApprovalGate"

    inputs = [
        MessageInput(
            name="input_value",
            display_name="Action / Payload",
            required=True,
            info="The message describing the action to gate. Passed through unchanged when approved.",
        ),
        BoolInput(
            name="is_approved",
            display_name="Approved",
            value=False,
            info="Must be true to release the action. Defaults to false (fail-closed).",
        ),
        MultilineInput(
            name="rejection_reason",
            display_name="Rejection Reason",
            required=False,
            advanced=True,
            info="Optional explanation surfaced when the action is blocked.",
        ),
    ]

    outputs = [
        Output(display_name="Approved", name="approved", method="gate"),
    ]

    def gate(self) -> Message:
        """Release the action when approved; otherwise block it loudly."""
        if not self.is_approved:
            reason = self.rejection_reason or "Action was not approved."
            self.status = f"Blocked by Approval Gate: {reason}"
            # Record the decision in the trace before blocking.
            self.log({"decision": "rejected", "reason": reason}, name="approval_gate")
            msg = f"Approval Gate blocked a side-effecting action: {reason}"
            raise ValueError(msg)

        value = self.input_value
        result = value if isinstance(value, Message) else Message(text=str(value))
        self.status = "Approved — action released."
        self.log({"decision": "approved"}, name="approval_gate")
        return result
