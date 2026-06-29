"""A2A client component: send a message to a remote A2A agent and return its reply.

Langflow can also be an A2A *server* (see the langflow A2A routes); this is the other
direction, letting a flow call out to any spec-compliant A2A agent via the a2a-sdk client.
"""

from __future__ import annotations

import uuid

import httpx

from lfx.custom import Component
from lfx.io import IntInput, MessageTextInput, MultilineInput, Output, SecretStrInput
from lfx.schema.message import Message
from lfx.utils.ssrf_protection import SSRFProtectionError, validate_and_resolve_url
from lfx.utils.ssrf_transport import create_ssrf_protected_client

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
    """Build the httpx client used for all A2A calls, pinned to the ``agent_url`` origin.

    ``create_ssrf_protected_client`` only DNS-pins the ``agent_url`` host. The a2a SDK then
    POSTs ``message/send`` to whatever RPC url the fetched card declares, which could be a
    different (unpinned) origin, reopening DNS-rebind SSRF and leaking the ``x-api-key``. The
    per-request hook below forbids any off-origin hop, so both the card GET and the message
    POST stay on the configured agent origin and the api key never reaches another host.
    """
    agent_origin = _origin(agent_url)

    async def _enforce_agent_origin(request: httpx.Request) -> None:
        if _origin(request.url) != agent_origin:
            msg = (
                f"A2A agent card declared an off-origin endpoint "
                f"({request.url.scheme}://{request.url.host}); refusing to send the request or "
                f"API key to a host other than the configured agent URL ({agent_url})."
            )
            raise SSRFProtectionError(msg)

    client_kwargs = {
        "timeout": timeout,
        "headers": {"x-api-key": api_key} if api_key else None,
        "follow_redirects": False,
        "event_hooks": {"request": [_enforce_agent_origin]},
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
    description = "Send a message to a remote A2A (Agent-to-Agent) agent and return its reply."
    documentation: str = "https://a2a-protocol.org/"
    icon = "bot"
    name = "A2AAgent"

    inputs = [
        MessageTextInput(
            name="agent_url",
            display_name="Agent URL",
            info="Base URL of the remote A2A agent. Its card is fetched from <url>/.well-known/agent-card.json.",
            required=True,
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

    async def send_to_agent(self) -> Message:
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
