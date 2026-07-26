"""HITL lifecycle validation against human_input_flow."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from tests.locust.langflow_runtime.clients.workflows import WorkflowsClient
from tests.locust.langflow_runtime.provision.api import ProvisionHttp

HITL_FIXTURE_ID = "human_input_flow"
DEFAULT_HITL_PROMPT = "Approve this?"
APPROVE_DECISION = {"action_id": "approve"}


def validate_hitl_lifecycle(
    http: ProvisionHttp,
    state: dict[str, Any],
    *,
    deadline_s: float = 120.0,
) -> bool:
    """Background → suspended → pending → resume → complete; mark usable only on success."""
    flows = state.get("flows") or {}
    record = flows.get(HITL_FIXTURE_ID)
    api_key = state.get("api_key")
    if not record or not api_key:
        state["hitl"] = {"validated": False, "usable": False, "skipped": True, "reason": "flow_or_api_key_missing"}
        state.setdefault("flags", {})["hitl_validated"] = False
        return False

    client = WorkflowsClient(
        api=http.api_client(api_key=str(api_key)),
        workload="hitl",
        flow_class="human_input",
    )
    session_id = f"perf-hitl-{state['env_id']}-{uuid4().hex[:8]}"
    try:
        client.hitl_lifecycle(
            flow_id=str(record["flow_id"]),
            input_value=DEFAULT_HITL_PROMPT,
            session_id=session_id,
            decision=APPROVE_DECISION,
            deadline_s=deadline_s,
        )
        ok = True
        error = None
    except Exception as exc:
        ok = False
        error = str(exc)

    state["hitl"] = {
        "validated": ok,
        "usable": ok,
        "session_id": session_id,
        "error": error,
        "fixture_id": HITL_FIXTURE_ID,
        "flow_id": record["flow_id"],
    }
    state.setdefault("flags", {})["hitl_validated"] = ok
    return ok
