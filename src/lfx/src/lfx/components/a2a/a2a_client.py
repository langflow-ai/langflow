"""A2A Agent component — delegate a task to a remote A2A-compatible agent."""

from __future__ import annotations

import httpx

from lfx.base.a2a.client import A2AClient, A2AClientError, extract_text_artifacts
from lfx.custom.custom_component.component import Component
from lfx.io import IntInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.message import Message


class A2AClientComponent(Component):
    """Calls a remote A2A agent over the A2A REST protocol.

    This is the client half of the A2A bridge: a Langflow flow delegates a
    task to an external A2A agent (which may be another Langflow flow exposed
    via A2A), waits for it to finish, and returns the final artifact as a
    ``Message``.
    """

    display_name = "A2A Agent"
    description = "Delegate a task to a remote A2A-compatible agent and return its final result."
    documentation: str = "https://a2a-protocol.org/"
    icon = "Bot"
    name = "A2AClient"

    inputs = [
        MessageTextInput(
            name="agent_url",
            display_name="Agent URL",
            required=True,
            info="Base URL of the remote A2A agent (the AgentCard 'url'), e.g. https://host/a2a/my-agent",
            tool_mode=True,
        ),
        MessageTextInput(
            name="input_value",
            display_name="Task",
            required=True,
            info="The message/task to send to the remote agent.",
            tool_mode=True,
        ),
        SecretStrInput(
            name="auth_token",
            display_name="Auth Token",
            required=False,
            info="Bearer token for the remote agent, if it requires authentication.",
            advanced=True,
        ),
        MessageTextInput(
            name="context_id",
            display_name="Context ID",
            required=False,
            info="Optional A2A contextId to continue a prior conversation with the remote agent.",
            advanced=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (s)",
            value=120,
            advanced=True,
            info="Seconds to wait for the remote agent to respond.",
        ),
    ]

    outputs = [
        Output(display_name="Response", name="response", method="call_remote_agent"),
    ]

    # Optional injected httpx client for testing / advanced reuse. Not a UI field.
    _http_client: httpx.AsyncClient | None = None

    def _auth_headers(self) -> dict[str, str] | None:
        token = getattr(self, "auth_token", None)
        return {"Authorization": f"Bearer {token}"} if token else None

    async def call_remote_agent(self) -> Message:
        if not self.agent_url:
            msg = "A2A Agent URL is required."
            raise ValueError(msg)

        owns_client = self._http_client is None
        client = self._http_client or httpx.AsyncClient(timeout=float(self.timeout or 120))
        try:
            remote = A2AClient(client, base_url=self.agent_url, headers=self._auth_headers())
            task = await remote.send_message(self.input_value or "", context_id=self.context_id or None)
        except A2AClientError as e:
            logger.error(f"A2A delegation to {self.agent_url} failed: {e}")
            raise
        finally:
            if owns_client:
                await client.aclose()

        state = (task.get("status") or {}).get("state")
        # Record the delegated task in the trace so the remote work is visible
        # in Langflow Traces (forwarded to the tracing service via Component.log).
        self.log(
            {
                "agent_url": self.agent_url,
                "task_id": task.get("id"),
                "context_id": task.get("contextId"),
                "state": state,
            },
            name="a2a_delegation",
        )
        if state != "completed":
            # Fail loudly rather than silently returning an empty result.
            detail = (task.get("status") or {}).get("message") or {}
            msg = f"Remote A2A agent did not complete (state={state!r}): {detail}"
            raise ValueError(msg)

        result_text = "\n".join(extract_text_artifacts(task))
        self.status = result_text or task
        return Message(text=result_text)
