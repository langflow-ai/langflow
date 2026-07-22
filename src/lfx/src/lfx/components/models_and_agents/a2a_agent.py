"""A2A client component: send a message to a remote A2A agent and return its reply.

Langflow can also be an A2A *server* (see the langflow A2A routes); this is the other
direction, letting a flow call out to any spec-compliant A2A agent via the a2a-sdk client.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import TYPE_CHECKING, Any

import httpx

from lfx.custom import Component
from lfx.io import (
    DataDisplayInput,
    DropdownInput,
    IntInput,
    MessageTextInput,
    MultilineInput,
    Output,
    SecretStrInput,
    TabInput,
)
from lfx.schema.message import Message
from lfx.utils.ssrf_protection import (
    SSRFProtectionError,
    is_host_allowed,
    is_ip_blocked,
    resolve_hostname,
    validate_and_resolve_url,
)
from lfx.utils.ssrf_transport import SSRFProtectedTransport

if TYPE_CHECKING:
    from lfx.schema.dotdict import dotdict

DEFAULT_TIMEOUT = 60.0
# Cap the aggregated reply STRING (not the buffered HTTP body: the a2a-sdk reads the whole
# non-streaming response into memory before this loop runs). Bounding the body itself needs a
# read-layer byte cap; tracked as a follow-up.
MAX_A2A_RESPONSE_CHARS = 100_000
_CARD_SUFFIX = "/.well-known/agent-card.json"
# A spec-compliant agent card is a few KB. Refuse to buffer or parse anything pathological: the
# card comes from a remote server we don't trust.
_MAX_CARD_BYTES = 256 * 1024
# Card strings land in build_config and are rendered in the editor, so clip them too.
_MAX_CARD_TEXT = 500


def _clip(value: object, limit: int = _MAX_CARD_TEXT) -> str:
    """Coerce untrusted card content to a bounded string."""
    text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _agent_base_url(url: str | None) -> str:
    """Normalize a pasted URL to the agent's base.

    The card URL (``<base>/.well-known/agent-card.json``) is exactly what the UI hands the user
    to copy, so accept it: strip the well-known suffix so every A2A call resolves the card once
    instead of double-appending it.
    """
    base = (url or "").strip().rstrip("/").removesuffix(_CARD_SUFFIX)
    return base.rstrip("/")


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


async def _reply_or_raise(responses) -> str:
    """Join the text parts of an A2A send-message response stream into the reply.

    Surfaces a non-successful remote task instead of passing its status text off as a reply: a task
    that ended failed/rejected/canceled (or was returned still non-terminal by a server that ignored
    the blocking send) is not a successful answer. A message-only reply carries no task state.
    """
    from a2a.helpers.proto_helpers import get_text_parts
    from a2a.types import a2a_pb2 as pb

    texts: list[str] = []
    total_chars = 0
    final_state: int | None = None
    async for response in responses:
        before = len(texts)
        if response.HasField("task"):
            final_state = response.task.status.state
            for artifact in response.task.artifacts:
                texts.extend(get_text_parts(artifact.parts))
            if not texts and response.task.status.HasField("message"):
                texts.extend(get_text_parts(response.task.status.message.parts))
        elif response.HasField("message"):
            texts.extend(get_text_parts(response.message.parts))
        total_chars += sum(len(text) for text in texts[before:])
        if total_chars >= MAX_A2A_RESPONSE_CHARS:
            break
    reply = "\n".join(text for text in texts if text)[:MAX_A2A_RESPONSE_CHARS]
    if final_state is not None and final_state != pb.TaskState.TASK_STATE_COMPLETED:
        msg = f"Remote A2A agent task did not complete ({pb.TaskState.Name(final_state)}): {reply or 'no detail'}"
        raise ValueError(msg)
    return reply


async def _resolve_card_bounded(httpx_client: httpx.AsyncClient, base_url: str) -> Any:
    """Fetch and parse the remote agent card with the body capped at ``_MAX_CARD_BYTES``.

    Runtime counterpart to the editor's :meth:`A2AAgentComponent._fetch_card`: same bounded read,
    but this raises on failure/oversize instead of degrading to no preview, because a runtime call
    with no card can't proceed. Returns the parsed SDK ``AgentCard`` for ``create_client`` to reuse.
    """
    async with httpx_client.stream("GET", f"{base_url}{_CARD_SUFFIX}") as response:
        response.raise_for_status()
        # Trust neither the declared length nor the actual stream.
        declared = response.headers.get("content-length")
        if declared is not None and int(declared) > _MAX_CARD_BYTES:
            msg = f"Agent card at {base_url} exceeds {_MAX_CARD_BYTES} bytes"
            raise ValueError(msg)
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > _MAX_CARD_BYTES:
                msg = f"Agent card at {base_url} exceeds {_MAX_CARD_BYTES} bytes"
                raise ValueError(msg)
    from a2a.client.card_resolver import parse_agent_card

    return parse_agent_card(json.loads(bytes(body)))


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
    from a2a.helpers.proto_helpers import new_text_part
    from a2a.types import a2a_pb2 as pb

    # Resolve the card ourselves with a bounded read, then hand it to create_client so the SDK
    # skips its own unbounded fetch. create_client(url) delegates to A2ACardResolver, which buffers
    # the whole card body with no cap; a hostile server streaming an endless card would OOM the
    # worker. Same 256KB cap as the editor preview, but here a bad card raises (fails the call).
    card = await _resolve_card_bounded(httpx_client, agent_url)
    client = await create_client(
        card,
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
    return await _reply_or_raise(client.send_message(request))


class A2AAgentComponent(Component):
    display_name = "A2A Agent"
    description = (
        "Call an A2A (Agent-to-Agent) agent and return its reply. Pick an agent flow in this "
        "project, or point at a remote agent by its URL."
    )
    documentation: str = "https://docs.langflow.org/a2a-server"
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
            info="The remote A2A agent's URL. Paste either its base URL or its "
            "/.well-known/agent-card.json card URL; both resolve the same agent.",
            required=False,
            real_time_refresh=True,
        ),
        # External: read-only view of the remote agent's card. Hidden until a URL yields a card.
        DataDisplayInput(
            name="agent_card",
            display_name="Agent card",
            info="The remote agent's advertised card. Appears when you enter a URL that returns one.",
            button_text="View agent card",
            button_icon="id-card",
            show=False,
        ),
        MultilineInput(
            name="input_value",
            display_name="Message",
            info="The message to send to the agent.",
            required=True,
            tool_mode=True,
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
                build_config["agent_card"]["show"] = False
                await self._populate_internal_agents(build_config)
            else:
                # Only surface the card display if the URL already set still resolves a card.
                await self._apply_external_card(build_config, build_config["agent_url"].get("value"))
        elif field_name == "agent_name_selected" and (build_config.get("is_refresh") or field_value is None):
            await self._populate_internal_agents(build_config)
        elif field_name == "agent_url":
            await self._apply_external_card(build_config, field_value)
        return build_config

    async def _populate_internal_agents(self, build_config: dotdict) -> None:
        """Fill the Internal dropdown with A2A agents published in the caller's folder."""
        agents = await self.alist_a2a_agents_by_flow_folder()
        build_config["agent_name_selected"]["options"] = [agent.data["name"] for agent in agents]
        build_config["agent_name_selected"]["options_metadata"] = [
            {"id": str(agent.data["id"]), "updated_at": agent.data.get("updated_at")} for agent in agents
        ]

    def _selected_agent_flow_id(self) -> str | None:
        """Resolve the dropdown pick to a flow id via options_metadata, since names are not unique."""
        field = self._inputs.get("agent_name_selected")
        options = list(getattr(field, "options", None) or [])
        metadata = list(getattr(field, "options_metadata", None) or [])
        if self.agent_name_selected in options:
            index = options.index(self.agent_name_selected)
            if index < len(metadata):
                return str(metadata[index].get("id") or "") or None
        return None

    @staticmethod
    def _agent_id_by_name(published: list[Any], agent_name: str) -> str | None:
        """Fall back for flows saved before the dropdown recorded ids: only an unambiguous name wins."""
        matches = [agent for agent in published if agent.data.get("name") == agent_name]
        return str(matches[0].data["id"]) if len(matches) == 1 else None

    async def _apply_external_card(self, build_config: dotdict, url: str | None) -> None:
        """On URL change, fetch the remote agent's card; show the display only if one comes back."""
        card = await self._fetch_card(url) if url and str(url).startswith("http") else None
        build_config["agent_card"]["value"] = self._card_payload(card) if card else {}
        build_config["agent_card"]["show"] = bool(card)

    async def _fetch_card(self, url: str) -> dict | None:
        """Fetch the remote agent card, SSRF-validated.

        Returns None on any failure so a bad URL shows no preview instead of erroring the editor
        (mirrors AstraDB's degrade-in-config style).
        """
        base = _agent_base_url(url)
        try:
            # to_thread: validate_and_resolve_url does blocking DNS; keep it off the event loop.
            _validated_url, validated_ips = await asyncio.to_thread(validate_and_resolve_url, base)
        except SSRFProtectionError:
            return None
        try:
            client = build_a2a_client(base, validated_ips, api_key=self.api_key, timeout=15)
            async with client, client.stream("GET", f"{base}{_CARD_SUFFIX}") as response:
                if response.status_code != httpx.codes.OK:
                    return None
                # Bound the read: trust neither the declared length nor the actual stream.
                declared = response.headers.get("content-length")
                if declared is not None and int(declared) > _MAX_CARD_BYTES:
                    return None
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > _MAX_CARD_BYTES:
                        return None
            data = json.loads(bytes(body))
            # A spec-compliant card is a JSON object; anything else degrades to no preview.
            return data if isinstance(data, dict) else None
        except Exception:  # noqa: BLE001 - a bad/unreachable/oversized url degrades to no preview
            return None

    @staticmethod
    def _card_payload(card: dict) -> dict:
        """Build the structured data-display payload (identity + chips + sections) from an agent card.

        The card is untrusted remote input, so every field is treated as arbitrary: a bad shape
        degrades to a thinner preview rather than raising.
        """
        card = card if isinstance(card, dict) else {}
        name = _clip(card.get("name") or "Agent")
        version = _clip(card.get("version") or "")

        # Quick-facts chips under the header. Auth leads (accent + icon) since it's decision-critical;
        # capabilities and transport/protocol follow as muted context.
        chips: list[dict] = []
        if card.get("security"):
            chips.append({"label": "Requires an API key", "icon": "key-round", "tone": "accent"})
        capabilities = card.get("capabilities")
        capabilities = capabilities if isinstance(capabilities, dict) else {}
        if capabilities.get("streaming"):
            chips.append({"label": "Streaming", "tone": "muted"})
        if capabilities.get("pushNotifications"):
            chips.append({"label": "Push notifications", "tone": "muted"})
        if transport := card.get("preferredTransport"):
            chips.append({"label": _clip(transport, 40), "tone": "muted"})
        if protocol := card.get("protocolVersion"):
            chips.append({"label": f"A2A {_clip(protocol, 20)}", "tone": "muted"})

        sections: list[dict] = []
        if description := card.get("description"):
            sections.append({"heading": "Description", "text": _clip(description)})

        # The card comes from a remote server, so tolerate malformed skill/schema shapes.
        raw_skills = card.get("skills")
        skills = [skill for skill in raw_skills if isinstance(skill, dict)] if isinstance(raw_skills, list) else []
        schema = skills[0].get("inputSchema") if skills else {}
        schema = schema if isinstance(schema, dict) else {}
        required_raw = schema.get("required")
        # Keep only string entries: a non-list or a list with unhashable items would break set()/membership.
        required = {r for r in required_raw if isinstance(r, str)} if isinstance(required_raw, list) else set()
        properties = schema.get("properties")
        properties = properties if isinstance(properties, dict) else {}
        if properties:
            fields = [
                {
                    "name": _clip(key, 80),
                    # spec is remote-controlled: a non-dict value (e.g. "notastring") would crash .get().
                    "type": _clip(spec.get("type") or "" if isinstance(spec, dict) else "", 40),
                    "required": key in required,
                }
                for key, spec in properties.items()
            ]
            sections.append({"heading": "Sends", "fields": fields})

        skill_cards = [
            {
                "title": _clip(skill.get("name") or skill.get("id") or "skill", 80),
                "description": _clip(skill.get("description") or ""),
            }
            for skill in skills
        ]
        if skill_cards:
            sections.append({"heading": "Skills", "cards": skill_cards})

        return {"title": name, "version": version, "chips": chips, "sections": sections}

    async def send_to_agent(self) -> Message:
        if self.mode == "Internal":
            return await self._run_internal_agent()
        return await self._call_external_agent()

    async def _run_target_isolated(self, graph, flow_id: str):
        """Run the target flow with the caller's LangChain run-config context reset.

        When the caller Agent is under tool-approval (HITL), it runs inside a LangGraph
        whose RunnableConfig — carrying ``configurable.thread_id`` + the durable checkpointer —
        is propagated to child runnables through ``var_child_runnable_config``. ``graph.arun``
        does ``copy_context()``, so the target flow's own Agent would inherit that thread id and
        checkpoint against the CALLER's HITL thread, corrupting its tool loop ("tool_use without
        tool_result"). Resetting the contextvar to a clean config before the nested run makes the
        target execute as a fresh, independent graph.
        """
        from lfx.helpers import run_flow

        try:
            from langchain_core.runnables.config import var_child_runnable_config
        except ImportError:
            var_child_runnable_config = None

        async def _do_run():
            return await run_flow(
                inputs={"input_value": self.input_value, "type": "chat"},
                graph=graph,
                user_id=str(self.user_id),
                session_id=self._isolated_sub_session(flow_id),
                output_type="chat",
            )

        if var_child_runnable_config is None:
            return await _do_run()
        token = var_child_runnable_config.set(None)
        try:
            return await _do_run()
        finally:
            var_child_runnable_config.reset(token)

    def _isolated_sub_session(self, flow_id: str) -> str:
        """Session for the internal sub-run, isolated from the caller's LangGraph thread.

        Running the target on the caller's raw session_id makes the target's Agent inherit the
        caller's in-flight thread — which mid-tool-execution holds this ``send_to_agent`` call as
        an orphan ``tool_use`` with no ``tool_result`` yet — so the target's LLM call is rejected
        ("tool_use without tool_result"). Namespacing by (caller session, target flow) gives the
        sub-agent its own thread while staying stable across calls within one caller session.
        """
        base = getattr(getattr(self, "graph", None), "session_id", None)
        return f"{base}:a2a:{flow_id}" if base else uuid.uuid4().hex

    async def _run_internal_agent(self) -> Message:
        # An in-project A2A agent is just a flow with chat I/O, so run it in-process (no HTTP, no
        # SSRF, no api key) and read its chat reply. Same three primitives Run Flow uses.
        from lfx.graph.graph.base import Graph
        from lfx.helpers import get_flow_by_id_or_name, run_flow

        agent_name = self.agent_name_selected or None
        if not agent_name:
            msg = "Select an A2A agent to call."
            raise ValueError(msg)

        # The pick is stored as a name, but the target can be renamed or unpublished between editing
        # and running. Re-resolve it against the agents published right now, preferring the flow id
        # the dropdown recorded, so a same-named flow can't be called by accident and an unpublished
        # one is refused instead of silently run.
        published = await self.alist_a2a_agents_by_flow_folder()
        published_ids = {str(agent.data["id"]) for agent in published}
        flow_id = self._selected_agent_flow_id() or self._agent_id_by_name(published, agent_name)
        if flow_id is None or flow_id not in published_ids:
            msg = (
                f"Agent flow '{agent_name}' is not published as an A2A agent in this project. "
                "Turn on 'Serve as an A2A agent' for it, or select another agent."
            )
            raise ValueError(msg)

        flow = await get_flow_by_id_or_name(user_id=self.user_id, flow_id=flow_id)
        if not flow or not flow.data:
            msg = f"Agent flow '{agent_name}' could not be found."
            raise ValueError(msg)

        graph = Graph.from_payload(
            flow.data.get("data", {}),
            flow_id=str(flow.data.get("id", "")),
            flow_name=flow.data.get("name"),
        )
        run_outputs = await self._run_target_isolated(graph, flow_id)
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

        # Accept either the base URL or the card URL the UI hands out; the SDK resolves the card
        # from <base>/.well-known/agent-card.json, so normalize first to avoid double-appending.
        agent_url = _agent_base_url(self.agent_url)

        # Validate + DNS-pin the agent URL before any outbound call (blocks loopback, RFC1918,
        # link-local / cloud metadata, etc.); mirrors the API Request component.
        try:
            # to_thread: validate_and_resolve_url does blocking DNS; keep it off the event loop.
            _validated_url, validated_ips = await asyncio.to_thread(validate_and_resolve_url, agent_url)
        except SSRFProtectionError as e:
            msg = f"SSRF Protection: {e}"
            raise ValueError(msg) from e

        client = build_a2a_client(agent_url, validated_ips, api_key=self.api_key, timeout=timeout)
        try:
            async with client:
                answer = await call_a2a_agent(agent_url, self.input_value, httpx_client=client)
        except SSRFProtectionError as e:
            msg = f"SSRF Protection: {e}"
            raise ValueError(msg) from e
        except Exception as e:
            msg = f"Failed to call A2A agent at {agent_url}: {e}"
            raise ValueError(msg) from e

        message = Message(text=answer or "No response received from the A2A agent.")
        self.status = message
        return message
