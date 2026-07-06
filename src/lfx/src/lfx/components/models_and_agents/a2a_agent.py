"""A2A client component: send a message to a remote A2A agent and return its reply.

Langflow can also be an A2A *server* (see the langflow A2A routes); this is the other
direction, letting a flow call out to any spec-compliant A2A agent via the a2a-sdk client.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Any

import httpx

from lfx.custom import Component
from lfx.io import DropdownInput, IntInput, MessageTextInput, MultilineInput, Output, SecretStrInput, TabInput
from lfx.schema.message import Message
from lfx.utils.ssrf_protection import SSRFProtectionError, validate_and_resolve_url
from lfx.utils.ssrf_transport import create_ssrf_protected_client

if TYPE_CHECKING:
    from lfx.schema.dotdict import dotdict

DEFAULT_TIMEOUT = 60.0
# Cap aggregated reply size so a chatty/streaming agent can't make us buffer unbounded text.
MAX_A2A_RESPONSE_CHARS = 100_000


def _origin(url: httpx.URL | str) -> tuple[str | None, str | None, int | None]:
    """Return the (scheme, host, port) origin of ``url`` (default ports normalized to None)."""
    parsed = url if isinstance(url, httpx.URL) else httpx.URL(url)
    return (parsed.scheme, parsed.host, parsed.port)


def build_a2a_client(
    agent_url: str,
    validated_ips: list[str],
    *,
    api_key: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> httpx.AsyncClient:
    """Build the httpx client used for all A2A calls, anchored to the ``agent_url`` origin.

    ``create_ssrf_protected_client`` only DNS-pins the ``agent_url`` host, so same-origin
    targets (the card GET and a same-origin ``message/send`` POST) are validated up front by
    ``send_to_agent`` and pinned to ``validated_ips``. A spec-compliant agent card may
    legitimately advertise its RPC ``url`` on a *different* origin; the transport does NOT pin
    that host (it falls through to normal DNS with no SSRF check), and the configured
    ``x-api-key`` must never reach it.

    The per-request hook handles those off-origin hops: it strips the ``x-api-key`` header so
    the key only ever reaches the configured agent, and it SSRF-validates the target (resolve
    + reject internal/metadata IPs) before the connection opens, covering the unpinned host the
    transport doesn't. Same-origin requests are already validated and pinned, so they keep the
    key and skip the redundant re-resolution. Redirects stay disabled so a 3xx can't smuggle the
    key or connection to an unvalidated host.
    """
    agent_origin = _origin(agent_url)

    async def _guard_request(request: httpx.Request) -> None:
        if _origin(request.url) == agent_origin:
            return
        # Off-origin hop: never leak the configured api key to a card-declared foreign host.
        request.headers.pop("x-api-key", None)
        # The transport doesn't pin this host, so SSRF-validate it here (resolves the hostname
        # and raises SSRFProtectionError if any resolved IP is blocked) before the connection
        # opens. to_thread keeps the blocking DNS resolution off the event loop.
        await asyncio.to_thread(validate_and_resolve_url, str(request.url))

    client_kwargs = {
        "timeout": timeout,
        "headers": {"x-api-key": api_key} if api_key else None,
        "follow_redirects": False,
        "event_hooks": {"request": [_guard_request]},
    }
    hostname = httpx.URL(agent_url).host
    if validated_ips and hostname:
        return create_ssrf_protected_client(hostname=hostname, validated_ips=validated_ips, **client_kwargs)
    return httpx.AsyncClient(**client_kwargs)


async def call_a2a_agent(
    agent_url: str,
    message: str,
    *,
    httpx_client: httpx.AsyncClient,
    accepted_output_modes: list[str] | None = None,
) -> str:
    """Send ``message`` to the A2A agent at ``agent_url`` and return its reply text.

    Resolves the agent card from ``<agent_url>/.well-known/agent-card.json``, sends one
    non-streaming ``message/send``, and joins the text parts of the returned artifacts
    (falling back to the task's status message). The same ``httpx_client`` fetches the card
    and posts the message; it must be built with :func:`build_a2a_client` so the api key is
    pinned to the ``agent_url`` origin. Factored out from the component so a test can drive it.
    """
    from a2a.client.client import ClientConfig
    from a2a.client.client_factory import create_client
    from a2a.helpers.proto_helpers import get_text_parts, new_text_part
    from a2a.types import a2a_pb2 as pb

    client = await create_client(
        agent_url,
        client_config=ClientConfig(
            streaming=False,
            httpx_client=httpx_client,
            accepted_output_modes=accepted_output_modes or ["application/json"],
        ),
    )
    request = pb.SendMessageRequest(
        message=pb.Message(
            message_id=uuid.uuid4().hex,
            role=pb.Role.ROLE_USER,
            parts=[new_text_part(message)],
        )
    )
    texts: list[str] = []
    total_chars = 0
    async for response in client.send_message(request):
        before = len(texts)
        if response.HasField("task"):
            for artifact in response.task.artifacts:
                texts.extend(get_text_parts(artifact.parts))
            if not texts and response.task.status.HasField("message"):
                texts.extend(get_text_parts(response.task.status.message.parts))
        elif response.HasField("message"):
            texts.extend(get_text_parts(response.message.parts))
        total_chars += sum(len(text) for text in texts[before:])
        if total_chars >= MAX_A2A_RESPONSE_CHARS:
            break
    return "\n".join(text for text in texts if text)[:MAX_A2A_RESPONSE_CHARS]


class A2AAgentComponent(Component):
    display_name = "A2A Agent"
    description = (
        "Call an A2A (Agent-to-Agent) agent and return its reply. Pick an agent flow in this "
        "project, or point at a remote agent by its URL."
    )
    documentation: str = "https://a2a-protocol.org/"
    icon = "bot"
    name = "A2AAgent"

    inputs = [
        TabInput(
            name="mode",
            display_name="Mode",
            options=["Internal", "External"],
            value="External",
            info=("Internal calls another agent flow in this project. External calls a remote A2A agent by its URL."),
            real_time_refresh=True,
        ),
        # Internal: an agent flow in the caller's project/folder. Populated in update_build_config.
        DropdownInput(
            name="agent_name_selected",
            display_name="Agent",
            info="An agent flow in this project (one with a chat input and a chat output).",
            options=[],
            options_metadata=[],
            real_time_refresh=True,
            required=False,
            show=False,
        ),
        # External: a remote A2A agent by URL.
        MessageTextInput(
            name="agent_url",
            display_name="Agent URL",
            info="Base URL of the remote A2A agent. Its card is fetched from <url>/.well-known/agent-card.json.",
            required=False,
            real_time_refresh=True,
        ),
        MultilineInput(
            name="input_value",
            display_name="Message",
            info="The message to send to the agent.",
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Optional API key sent as x-api-key, for agents that require it.",
            advanced=True,
            required=False,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (s)",
            info="Maximum seconds to wait for the agent's reply.",
            value=60,
            advanced=True,
        ),
    ]
    outputs = [Output(display_name="Response", name="response", method="send_to_agent")]

    async def update_build_config(
        self,
        build_config: dotdict,
        field_value: Any,
        field_name: str | None = None,
    ) -> dotdict:
        # The Mode tab reveals only the fields that apply. External fields carry the api key and
        # timeout for the HTTP call; Internal reveals the in-project agent picker.
        if field_name == "mode":
            internal = field_value == "Internal"
            build_config["agent_name_selected"]["show"] = internal
            build_config["agent_url"]["show"] = not internal
            build_config["agent_url"]["required"] = not internal
            build_config["api_key"]["show"] = not internal
            build_config["timeout"]["show"] = not internal
            if internal:
                await self._populate_internal_agents(build_config)
        elif field_name == "agent_name_selected" and (build_config.get("is_refresh") or field_value is None):
            await self._populate_internal_agents(build_config)
        return build_config

    async def _populate_internal_agents(self, build_config: dotdict) -> None:
        """Fill the Internal dropdown with A2A agents published in the caller's folder."""
        agents = await self.alist_a2a_agents_by_flow_folder()
        build_config["agent_name_selected"]["options"] = [agent.data["name"] for agent in agents]
        build_config["agent_name_selected"]["options_metadata"] = [
            {"id": str(agent.data["id"]), "updated_at": agent.data.get("updated_at")} for agent in agents
        ]

    async def send_to_agent(self) -> Message:
        if self.mode == "Internal":
            return await self._run_internal_agent()
        return await self._call_external_agent()

    async def _run_internal_agent(self) -> Message:
        # An in-project A2A agent is just a flow with chat I/O, so run it in-process (no HTTP, no
        # SSRF, no api key) and read its chat reply. Same three primitives Run Flow uses.
        from lfx.graph.graph.base import Graph
        from lfx.helpers import get_flow_by_id_or_name, run_flow

        agent_name = self.agent_name_selected or None
        if not agent_name:
            msg = "Select an A2A agent to call."
            raise ValueError(msg)

        # The dropdown only offers a2a_enabled agents from the caller's folder; we resolve the
        # pick by name here. A same-named flow elsewhere is a rare ambiguity we accept for now.
        flow = await get_flow_by_id_or_name(user_id=self.user_id, flow_name=agent_name)
        if not flow or not flow.data:
            msg = f"Agent flow '{agent_name}' could not be found."
            raise ValueError(msg)

        graph = Graph.from_payload(
            flow.data.get("data", {}),
            flow_id=str(flow.data.get("id", "")),
            flow_name=flow.data.get("name"),
        )
        session_id = getattr(getattr(self, "graph", None), "session_id", None)
        run_outputs = await run_flow(
            inputs={"input_value": self.input_value, "type": "chat"},
            graph=graph,
            user_id=str(self.user_id),
            session_id=session_id,
            output_type="chat",
        )
        answer = self._reply_from_run(run_outputs)
        message = Message(text=answer or "No response received from the agent.")
        self.status = message
        return message

    @staticmethod
    def _reply_from_run(run_outputs: list) -> str:
        """Pull the chat reply text out of run_flow's outputs, tolerant of the result shape."""
        texts: list[str] = []
        for run in run_outputs or []:
            for result in getattr(run, "outputs", None) or []:
                if result is None:
                    continue
                data = getattr(result, "results", None)
                candidates = list(data.values()) if isinstance(data, dict) else ([data] if data is not None else [])
                message = getattr(result, "message", None)
                if message is not None:
                    candidates.append(message)
                for candidate in candidates:
                    text = getattr(candidate, "text", None)
                    if isinstance(text, str) and text:
                        texts.append(text)
                    elif isinstance(candidate, str) and candidate:
                        texts.append(candidate)
        return "\n".join(texts)

    async def _call_external_agent(self) -> Message:
        try:
            timeout = float(self.timeout)
        except (TypeError, ValueError):
            timeout = DEFAULT_TIMEOUT

        # Validate + DNS-pin the agent URL before any outbound call (blocks loopback, RFC1918,
        # link-local / cloud metadata, etc.); mirrors the API Request component.
        try:
            _validated_url, validated_ips = validate_and_resolve_url(self.agent_url)
        except SSRFProtectionError as e:
            msg = f"SSRF Protection: {e}"
            raise ValueError(msg) from e

        client = build_a2a_client(self.agent_url, validated_ips, api_key=self.api_key, timeout=timeout)
        try:
            async with client:
                answer = await call_a2a_agent(self.agent_url, self.input_value, httpx_client=client)
        except SSRFProtectionError as e:
            msg = f"SSRF Protection: {e}"
            raise ValueError(msg) from e
        except Exception as e:
            msg = f"Failed to call A2A agent at {self.agent_url}: {e}"
            raise ValueError(msg) from e

        message = Message(text=answer or "No response received from the A2A agent.")
        self.status = message
        return message
