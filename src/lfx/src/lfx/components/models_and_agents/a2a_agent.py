"""A2A client component: send a message to a remote A2A agent and return its reply.

Langflow can also be an A2A *server* (see the langflow A2A routes); this is the other
direction, letting a flow call out to any spec-compliant A2A agent via the a2a-sdk client.
"""

from __future__ import annotations

import asyncio
import uuid

import httpx

from lfx.custom import Component
from lfx.io import IntInput, MessageTextInput, MultilineInput, Output, SecretStrInput
from lfx.schema.message import Message
from lfx.utils.ssrf_protection import (
    SSRFProtectionError,
    is_host_allowed,
    is_ip_blocked,
    resolve_hostname,
    validate_and_resolve_url,
)
from lfx.utils.ssrf_transport import SSRFProtectedTransport

DEFAULT_TIMEOUT = 60.0
# Cap the aggregated reply STRING (not the buffered HTTP body: the a2a-sdk reads the whole
# non-streaming response into memory before this loop runs). Bounding the body itself needs a
# read-layer byte cap; tracked as a follow-up.
MAX_A2A_RESPONSE_CHARS = 100_000


def _origin(url: httpx.URL | str) -> tuple[str | None, str | None, int | None]:
    """Return the (scheme, host, port) origin of ``url`` (default ports normalized to None)."""
    parsed = url if isinstance(url, httpx.URL) else httpx.URL(url)
    return (parsed.scheme, parsed.host, parsed.port)


def _pin_host(url: httpx.URL | str) -> str:
    """The host httpcore actually connects to: the IDNA/punycode ``raw_host``, not unicode ``.host``.

    httpx connects using ``raw_host`` (e.g. ``xn--exmple-cua.com``), not the unicode ``.host``
    (``exämple.com``). The DNS-pin key must be this exact representation, or for an IDN host the
    pin is stored under a key the transport never reads and is silently bypassed (rebind for IDN
    hosts). Mirrors ``webhook_pin_host`` in the a2a backend utils.
    """
    parsed = url if isinstance(url, httpx.URL) else httpx.URL(url)
    return parsed.raw_host.decode("ascii")


def _ssrf_floor_ips(url: httpx.URL | str) -> list[str]:
    """Toggle-independent SSRF floor for a card-declared (caller-controlled) off-origin target.

    ``validate_and_resolve_url`` returns ``[]`` with NO enforcement when the global SSRF toggle
    is off, but a remote agent card can point the off-origin RPC ``url`` at an internal/metadata
    IP (confused deputy). Resolve the host and reject any blocked IP even with the toggle off,
    unless the host/IP is explicitly allowlisted. Mirrors ``validate_webhook_url``'s hard floor
    for the equally caller-controlled webhook target. Returns the resolved IPs so the caller can
    DNS-pin them.
    """
    host = _pin_host(url)
    ips = resolve_hostname(host)
    blocked = [ip for ip in ips if is_ip_blocked(ip) and not is_host_allowed(host, ip)]
    if blocked:
        msg = f"off-origin A2A target {host} resolves to a blocked address: {', '.join(blocked)}"
        raise SSRFProtectionError(msg)
    return ips


def build_a2a_client(
    agent_url: str,
    validated_ips: list[str],
    *,
    api_key: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> httpx.AsyncClient:
    """Build the httpx client used for all A2A calls, anchored to the ``agent_url`` origin.

    The client always uses the DNS-pinning transport over a single, mutable ``pinned_ips`` map.
    The map is seeded with the ``agent_url`` host (validated up front by ``send_to_agent``), so
    same-origin targets (the card GET and a same-origin ``message/send`` POST) carry the
    ``x-api-key`` and connect to the pinned IPs. An allowlisted agent host resolves to no IPs
    (trusted by config) and is simply left unpinned, matching the SSRF util.

    A spec-compliant agent card may legitimately advertise its RPC ``url`` on a *different*
    origin. The per-request hook handles those off-origin hops: it strips the ``x-api-key`` so
    the key only ever reaches the configured agent, then SSRF-validates the target (resolve +
    reject internal/metadata IPs) AND pins the validated IPs into the shared map before the
    connection opens. Pinning is the fix for a DNS-rebind window: without it the hook validates
    a public answer but httpx then does a fresh, unpinned lookup that could rebind to an internal
    IP. Writing the validated IPs into the map the transport reads at connect time makes the
    connection use exactly what was cleared, with no second resolution. Same-origin requests are
    already validated and pinned, so they keep the key and skip the redundant re-resolution.
    Because the off-origin target is card-controlled, a toggle-independent floor
    (:func:`_ssrf_floor_ips`) still rejects non-allowlisted internal IPs even when the global SSRF
    toggle is off, matching the webhook path. Redirects stay disabled so a 3xx can't smuggle the
    key or connection to an unvalidated host.
    """
    agent_origin = _origin(agent_url)
    agent_pin_host = _pin_host(agent_url)
    # Shared, mutable host -> validated-IPs map read by the transport's network backend at
    # connect time. Keys are the punycode ``raw_host`` the transport connects with, so IDN hosts
    # match. The hook adds each off-origin host before its connection opens; the a2a client issues
    # its hops sequentially, so there is no concurrent write to this dict.
    pinned_ips: dict[str, list[str]] = {}
    if validated_ips and agent_pin_host:
        pinned_ips[agent_pin_host] = list(validated_ips)

    async def _guard_request(request: httpx.Request) -> None:
        if _origin(request.url) == agent_origin:
            return
        # Off-origin hop: never leak the configured api key to a card-declared foreign host.
        request.headers.pop("x-api-key", None)
        # SSRF-validate the target (raises SSRFProtectionError if any resolved IP is blocked),
        # then pin the validated IPs so httpx connects to exactly what we cleared instead of a
        # fresh lookup a rebind could poison. to_thread keeps the blocking DNS off the event loop.
        _validated_url, off_origin_ips = await asyncio.to_thread(validate_and_resolve_url, str(request.url))
        if not off_origin_ips:
            # Framework returned no pins: the host is allowlisted OR the global SSRF toggle is
            # off. This target came from the remote card (not the flow author), so apply a
            # toggle-independent floor that still rejects non-allowlisted internal IPs.
            off_origin_ips = await asyncio.to_thread(_ssrf_floor_ips, request.url)
        pin_host = _pin_host(request.url)
        if pin_host and off_origin_ips:
            pinned_ips[pin_host] = off_origin_ips

    return httpx.AsyncClient(
        transport=SSRFProtectedTransport(pinned_ips=pinned_ips),
        timeout=timeout,
        headers={"x-api-key": api_key} if api_key else None,
        follow_redirects=False,
        event_hooks={"request": [_guard_request]},
    )


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
