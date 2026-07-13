"""Agent tool-call approval HITL helpers (LE-1447).

Split out of ``agent.py`` to keep it within the file-size budget. ``ToolApprovalMixin``
carries the interrupt → pause → resume logic for AgentComponent: gating connected tools,
mapping a ``HumanInTheLoopMiddleware`` interrupt onto the shared HITL pause contract (the
same one the HumanInput node uses), reading the pending interrupt from the agent's
checkpointed state, and translating the human decision back into the middleware's resume
shape. Behavior is unchanged; methods stay instance methods so ``self`` semantics hold.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lfx.schema.message import Message

HUMAN_INPUT_REQUIRED = "human_input_required"
KIND_TOOL_APPROVAL = "tool_approval"
DECISION_LABELS = {"approve": "Approve", "edit": "Edit", "reject": "Reject", "respond": "Respond"}


class ToolApprovalMixin:
    """Tool-call approval interrupt/resume behavior for AgentComponent (LE-1447)."""

    def _agent_thread_id(self) -> str | None:
        """Per-run thread id for the agent HITL checkpoint (run_id, not session_id)."""
        run_id = getattr(getattr(self, "graph", None), "run_id", None)
        return str(run_id) if run_id else None

    def _build_agent_checkpointer(self):
        """Durable saver for a gated agent run, else None (no checkpointer overhead).

        The blob store is the INJECTED checkpoint service (DB-backed in the Langflow
        runtime, in-memory standalone) so lfx never imports langflow.
        """
        thread_id = self._agent_thread_id()
        if not thread_id or not self._gated_interrupt_on():
            return None
        from lfx.components.models_and_agents.agent_helpers.job_checkpoint_saver import JobCheckpointSaver
        from lfx.graph.checkpoint.store import default_checkpoint_store
        from lfx.services.deps import get_checkpoint_service

        try:
            store = get_checkpoint_service()
        except Exception:  # noqa: BLE001
            store = None
        store = store or default_checkpoint_store()
        return JobCheckpointSaver(thread_id, store.save_blob, store.load_blob)

    def _gated_interrupt_on(self) -> dict[str, dict[str, Any]]:
        """Gate connected tools by the decisions selected on each tool's Actions row.

        Each tool carries ``approval_actions`` (a subset of approve/edit/reject/respond)
        in its metadata; a non-empty list gates that tool and maps to the middleware's
        ``InterruptOnConfig`` so the card offers exactly those decisions. The agent has
        no tool list of its own — each tool keeps its own per-action selection.
        """
        gated: dict[str, dict[str, Any]] = {}
        for tool in self.tools or []:
            name = getattr(tool, "name", None)
            metadata = getattr(tool, "metadata", None) or {}
            actions = metadata.get("approval_actions") or []
            if name and actions:
                gated[name] = {"allowed_decisions": list(actions)}
        return gated

    def _map_interrupt_to_request(self, value: dict[str, Any], interrupt_id: str | None = None) -> dict[str, Any]:
        """Translate a HumanInTheLoopMiddleware interrupt into the HITL pause request.

        Reuses the same ``request_id``/``options``/``allowed_decisions`` contract as the
        HumanInput node so the persisted card, resume route, and frontend treat an agent
        tool-approval pause exactly like a node pause. The interrupt id is appended as a
        per-pause nonce: one agent can pause multiple times in a run, and without it a
        stale resume for approval N would be accepted while approval N+1 is pending.
        """
        action_requests = value.get("action_requests") or []
        review_configs = value.get("review_configs") or []
        allowed: list[str] = []
        for config in review_configs:
            for decision in config.get("allowed_decisions") or []:
                if decision not in allowed:
                    allowed.append(decision)
        calls = ", ".join(str(req.get("name")) for req in action_requests if req.get("name"))
        prompt = action_requests[0].get("description") if action_requests else ""
        base_request_id = f"{self._id}:{self._agent_thread_id()}"
        return {
            "request_id": f"{base_request_id}:{interrupt_id}" if interrupt_id else base_request_id,
            "kind": KIND_TOOL_APPROVAL,
            "prompt": prompt or (f"Approve tool call: {calls}" if calls else "Approve the agent's next action?"),
            "options": [{"action_id": d, "label": DECISION_LABELS.get(d, d.title())} for d in allowed],
            "allowed_decisions": allowed,
            "action_requests": action_requests,
        }

    async def _read_pending_interrupt(self, agent, config: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        """Return (raw interrupt value, interrupt id) from the snapshot, or (None, None)."""
        snapshot = await agent.aget_state(config)
        interrupts = getattr(snapshot, "interrupts", None) or []
        if not interrupts:
            for task in getattr(snapshot, "tasks", None) or []:
                interrupts = getattr(task, "interrupts", None) or []
                if interrupts:
                    break
        if not interrupts:
            return None, None
        first = interrupts[0]
        value = getattr(first, "value", None)
        interrupt_id = getattr(first, "id", None) or getattr(first, "interrupt_id", None)
        return (value if isinstance(value, dict) else None), (str(interrupt_id) if interrupt_id else None)

    def _pending_interrupt_getter(self, agent, config: dict[str, Any]):
        """Closure that reports the agent's pending tool-approval request, or None.

        Called after the event stream drains; the interrupt has by then been written to
        the checkpointer, so the state snapshot carries it.
        """

        async def _get() -> dict[str, Any] | None:
            value, interrupt_id = await self._read_pending_interrupt(agent, config)
            return self._map_interrupt_to_request(value, interrupt_id) if value else None

        return _get

    def _has_candidate_decision(self, thread_id: str) -> bool:
        """Whether any injected decision targets this agent's thread (any pause nonce)."""
        decisions = getattr(self.graph, "human_input_decisions", None)
        if not isinstance(decisions, dict):
            return False
        prefix = f"{self._id}:{thread_id}"
        return any(key == prefix or str(key).startswith(prefix + ":") for key in decisions)

    def _injected_agent_decision(self, thread_id: str, interrupt_id: str | None = None) -> dict[str, Any] | None:
        """Human decision for this agent's pending approval, injected on resume.

        Nonce-keyed decisions must match the pending interrupt exactly; the bare
        ``component:thread`` key is only honored for checkpoints written before the
        nonce existed, so an earlier approval's answer can never satisfy a later pause.
        """
        decisions = getattr(self.graph, "human_input_decisions", None)
        if not isinstance(decisions, dict):
            return None
        if interrupt_id:
            nonce_match = decisions.get(f"{self._id}:{thread_id}:{interrupt_id}")
            if nonce_match is not None:
                return nonce_match
        return decisions.get(f"{self._id}:{thread_id}")

    @staticmethod
    def _to_langgraph_decision(decision: dict[str, Any], action_request: dict[str, Any]) -> dict[str, Any]:
        """Translate one HITL action_id into the middleware's resume Decision shape."""
        action_id = decision.get("action_id")
        values = decision.get("values") or {}
        if action_id == "edit":
            return {
                "type": "edit",
                "edited_action": {"name": action_request.get("name"), "args": values.get("args", values)},
            }
        if action_id == "reject":
            return {"type": "reject", "message": values.get("message", "")}
        if action_id == "respond":
            return {"type": "respond", "message": values.get("message") or values.get("response") or ""}
        return {"type": "approve"}

    def _build_resume_decisions(
        self, decision: dict[str, Any], action_requests: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """One Decision per interrupted tool call (count must match), all from the human pick."""
        count = max(len(action_requests), 1)
        return [
            self._to_langgraph_decision(decision, action_requests[i] if i < len(action_requests) else {})
            for i in range(count)
        ]

    def _suspend_for_tool_approval(self, request: dict[str, Any], agent_message: Message) -> Message:
        """Request a graph pause carrying the tool-approval request, mirroring HumanInput.

        The actual suspend happens at the next ``check_and_handle_pause`` (start of the
        following ``build_vertices``); returning the partial message lets this vertex finish.
        """
        self.graph.request_pause(reason=HUMAN_INPUT_REQUIRED, data=request)
        self.status = "Awaiting human approval"
        return agent_message
