"""A2A client transport — the "caller" half of the A2A bridge.

Speaks the same REST dialect that Langflow's A2A server implements:

    GET  {base_url}/.well-known/agent-card.json
    POST {base_url}/v1/message:send
    POST {base_url}/v1/message:stream   (SSE)
    GET  {base_url}/v1/tasks/{task_id}
    POST {base_url}/v1/tasks/{task_id}:cancel

It is deliberately thin and transport-injectable: an ``httpx.AsyncClient``
is passed in, so the same client works against a remote agent over the
network *and* against an in-process app via ASGITransport (used by the
agent-to-agent integration tests). It is used both by the langflow backend
(re-exported from ``langflow.api.a2a.client``) and by the "A2A Agent"
canvas component.

This is not the official ``a2a-sdk`` client. The SDK's ``RestTransport``
speaks protobuf-JSON; this client speaks the plain-JSON dialect the server
emits. Exchanged structures are still validated against the ``a2a-sdk``
pydantic types where they are spec-shaped (see the tests).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class A2AClientError(RuntimeError):
    """Raised when a remote A2A agent returns an error or is unreachable."""


def build_message(
    text: str,
    *,
    context_id: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an A2A message payload from text and optional structured data."""
    parts: list[dict[str, Any]] = []
    if text:
        parts.append({"kind": "text", "text": text})
    if data:
        parts.append({"kind": "data", "data": data})
    message: dict[str, Any] = {"role": "user", "parts": parts}
    if context_id is not None:
        message["contextId"] = context_id
    return message


class A2AClient:
    """A minimal client for invoking a remote A2A agent.

    Args:
        http_client: An ``httpx.AsyncClient`` used for all requests. The
            caller owns its lifecycle (this class never closes it).
        base_url: The agent's base URL (the AgentCard ``url``), e.g.
            ``https://host/a2a/my-agent`` or, in-process, ``/a2a/my-agent``.
        headers: Default headers applied to authenticated calls (e.g.
            ``{"Authorization": "Bearer ..."}``). The public AgentCard
            endpoint is fetched without them.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        base_url: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._http = http_client
        self.base_url = base_url.rstrip("/")
        self._headers = headers or {}

    # -- discovery ---------------------------------------------------------

    async def get_agent_card(self) -> dict[str, Any]:
        """Fetch the agent's public AgentCard (no auth)."""
        url = f"{self.base_url}/.well-known/agent-card.json"
        resp = await self._http.get(url)
        if resp.status_code != httpx.codes.OK:
            msg = f"Agent card discovery failed ({resp.status_code}) at {url}"
            raise A2AClientError(msg)
        return resp.json()

    # -- task delegation ---------------------------------------------------

    async def send_message(
        self,
        text: str,
        *,
        context_id: str | None = None,
        data: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """Send a message and block until the agent returns a Task.

        Returns the A2A Task dict (terminal: completed/failed/input-required).
        """
        body: dict[str, Any] = {"message": build_message(text, context_id=context_id, data=data)}
        if task_id is not None:
            body["taskId"] = task_id

        resp = await self._http.post(
            f"{self.base_url}/v1/message:send",
            json=body,
            headers=self._headers,
        )
        if resp.status_code != httpx.codes.OK:
            msg = f"message:send failed ({resp.status_code}): {resp.text}"
            raise A2AClientError(msg)
        return resp.json()

    async def stream_message(
        self,
        text: str,
        *,
        context_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Send a message and yield A2A SSE events as they arrive."""
        body = {"message": build_message(text, context_id=context_id, data=data)}
        async with self._http.stream(
            "POST",
            f"{self.base_url}/v1/message:stream",
            json=body,
            headers=self._headers,
        ) as resp:
            if resp.status_code != httpx.codes.OK:
                text_body = await resp.aread()
                msg = f"message:stream failed ({resp.status_code}): {text_body!r}"
                raise A2AClientError(msg)
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    yield json.loads(line[len("data: ") :])

    # -- task inspection ---------------------------------------------------

    async def get_task(self, task_id: str) -> dict[str, Any]:
        """Poll a task's current state."""
        resp = await self._http.get(
            f"{self.base_url}/v1/tasks/{task_id}",
            headers=self._headers,
        )
        if resp.status_code != httpx.codes.OK:
            msg = f"get_task failed ({resp.status_code}): {resp.text}"
            raise A2AClientError(msg)
        return resp.json()

    async def cancel_task(self, task_id: str) -> dict[str, Any]:
        """Request best-effort cancellation of a task."""
        resp = await self._http.post(
            f"{self.base_url}/v1/tasks/{task_id}:cancel",
            headers=self._headers,
        )
        if resp.status_code != httpx.codes.OK:
            msg = f"cancel_task failed ({resp.status_code}): {resp.text}"
            raise A2AClientError(msg)
        return resp.json()


def extract_text_artifacts(task: dict[str, Any]) -> list[str]:
    """Pull all text parts out of a completed Task's artifacts.

    Convenience for callers (and the canvas component) that just want the
    text the remote agent produced.
    """
    texts: list[str] = []
    for artifact in task.get("artifacts") or []:
        texts.extend(
            part["text"] for part in artifact.get("parts") or [] if part.get("kind") == "text" and part.get("text")
        )
    return texts
