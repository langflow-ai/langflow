"""Chat history seeding for the deterministic Agent chat/DB fixture."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from tests.locust.langflow_runtime.clients.workflows import WorkflowsClient
from tests.locust.langflow_runtime.flows.defaults import DEFAULT_CHAT_INPUT
from tests.locust.langflow_runtime.provision.api import ProvisionHttp

CHAT_FIXTURE_ID = "perf_chat_db_agent"
DEFAULT_SEED_TURNS = 3


def seed_chat_history(
    http: ProvisionHttp,
    state: dict[str, Any],
    *,
    turns: int = DEFAULT_SEED_TURNS,
    input_value: str = DEFAULT_CHAT_INPUT,
) -> dict[str, Any]:
    """Run a few synchronous Agent turns with persisted chat history."""
    flows = state.get("flows") or {}
    record = flows.get(CHAT_FIXTURE_ID)
    api_key = state.get("api_key")
    if not record or not api_key:
        result = {"seeded": False, "turns": 0, "skipped": True, "reason": "flow_or_api_key_missing"}
        state["chat_seed"] = result
        return result

    client = WorkflowsClient(
        api=http.api_client(api_key=str(api_key)),
        workload="chat_seed",
        flow_class="memory",
    )
    session_id = f"perf-seed-{state['env_id']}-{uuid4().hex[:8]}"
    for index in range(turns):
        client.run_sync(
            flow_id=str(record["flow_id"]),
            input_value=f"{input_value}-{index}",
            session_id=session_id,
        )
    result = {"seeded": True, "turns": turns, "session_id": session_id}
    state["chat_seed"] = result
    state.setdefault("flags", {})["chat_seeded"] = True
    return result
