"""Helpers for building spec-valid A2A agent cards from Langflow flows.

The typed models come from ``a2a.compat.v0_3.types`` (pydantic). Do NOT import
from ``a2a.types`` — in a2a-sdk 1.x those are protobuf messages that serialize
to a non-spec shape (no top-level ``url``, oneof-wrapped ``securitySchemes``,
``location`` instead of ``in``).
"""

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

from a2a.compat.v0_3 import types as a2a_types
from lfx.log.logger import logger
from lfx.services.deps import get_settings_service
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.helpers.flow import json_schema_from_flow
from langflow.services.database.models import Folder
from langflow.services.database.models.flow.model import Flow
from langflow.utils.version import get_version_info

# Scheme key advertised on the card and the header MCP already validates
# (see mcp_projects.py). The A2A card reflects this; F6 enforces it.
A2A_APIKEY_SCHEME_NAME = "apiKey"  # pragma: allowlist secret
A2A_APIKEY_HEADER = "x-api-key"  # pragma: allowlist secret

# Served when a flow's graph can't be built; the card stays valid, the input
# contract is just empty rather than 500ing the public discovery endpoint.
_EMPTY_INPUT_SCHEMA = {"type": "object", "properties": {}, "required": []}


def _override_str(overrides: dict, key: str) -> str | None:
    """Return a non-empty string override, or None.

    a2a_card_overrides is a free-form dict, so a non-string value must not reach
    the typed card model (it would raise pydantic ValidationError).
    """
    value = overrides.get(key)
    return value if isinstance(value, str) and value else None


def _override_str_list(overrides: dict, key: str) -> list[str] | None:
    """Return a non-empty list-of-strings override, or None."""
    value = overrides.get(key)
    if isinstance(value, list) and value and all(isinstance(item, str) for item in value):
        return value
    return None


async def validate_webhook_url(url: str) -> None:
    """Raise ``ValueError`` when a push-notification webhook URL is unsafe (SSRF guard).

    The A2A endpoint is public, so the webhook target is caller-controlled. Require
    http/https and a host whose every resolved address is public; reject loopback,
    private, link-local (incl. the cloud metadata IP 169.254.169.254), reserved,
    multicast, and unspecified. ``LANGFLOW_A2A_ALLOW_PRIVATE_WEBHOOKS`` skips the IP
    check for a trusted internal network.

    Validated at registration; a host that later re-resolves to a private address
    (DNS rebinding) is a residual a dispatch-time check would close.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        msg = "webhook url must be http or https"
        raise ValueError(msg)
    host = parsed.hostname
    if not host:
        msg = "webhook url has no host"
        raise ValueError(msg)
    if get_settings_service().settings.a2a_allow_private_webhooks:
        return
    try:
        # getaddrinfo is blocking; resolve off the event loop. An IP-literal host
        # returns that IP without a DNS lookup.
        infos = await asyncio.to_thread(socket.getaddrinfo, host, parsed.port, type=socket.SOCK_STREAM)
    except OSError as exc:
        msg = f"webhook host does not resolve: {host}"
        raise ValueError(msg) from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if any((ip.is_loopback, ip.is_private, ip.is_link_local, ip.is_reserved, ip.is_multicast, ip.is_unspecified)):
            msg = f"webhook url resolves to a non-public address: {ip}"
            raise ValueError(msg)


async def folder_auth_type(flow: Flow, session: AsyncSession) -> str:
    """Read the flow's folder ``auth_type`` (``"none"`` | ``"apikey"`` | ``"oauth"``).

    The single source of truth for what the card advertises (resolve_card_security)
    and what the JSON-RPC route enforces, so the two can't drift. Plaintext read,
    no decrypt. No folder / missing folder -> ``"none"`` (public).
    """
    if flow.folder_id is None:
        return "none"
    # Query the folder explicitly; lazy-loading flow.folder would raise in async.
    folder = (await session.exec(select(Folder).where(Folder.id == flow.folder_id))).first()
    return (folder.auth_settings or {}).get("auth_type", "none") if folder else "none"


async def resolve_card_security(
    flow: Flow,
    session: AsyncSession,
) -> tuple[dict[str, a2a_types.SecurityScheme] | None, list[dict[str, list[str]]] | None]:
    """Reflect the flow's folder auth onto the A2A card (securitySchemes, security).

    Reflects what the JSON-RPC route enforces. Returns ``(None, None)`` when there
    is no API-key requirement.
    """
    if await folder_auth_type(flow, session) == "apikey":
        scheme = a2a_types.SecurityScheme(
            a2a_types.APIKeySecurityScheme(
                in_=a2a_types.In.header,
                name=A2A_APIKEY_HEADER,
                description="API key passed in the x-api-key header.",
            )
        )
        return {A2A_APIKEY_SCHEME_NAME: scheme}, [{A2A_APIKEY_SCHEME_NAME: []}]

    # "none" / missing / "oauth" -> advertise no security. oauth has no advertised
    # scheme yet, so the route leaves it public until that scheme lands.
    return None, None


async def build_agent_card(flow: Flow, *, rpc_url: str, session: AsyncSession) -> dict:
    """Build a spec-valid A2A agent card (JSON-ready dict) for an agent flow.

    The caller owns gating (flow_type == AGENT, a2a_enabled, the server flag)
    and 404s when those fail. ``rpc_url`` is the per-flow JSON-RPC endpoint
    advertised as the card's ``url``; F3 finalizes that path.
    """
    overrides = flow.a2a_card_overrides if isinstance(flow.a2a_card_overrides, dict) else {}
    name = _override_str(overrides, "name") or flow.name
    description = _override_str(overrides, "description") or flow.description or f"A2A agent for flow {flow.name}"
    # No per-flow version field exists on Flow; fall back to the langflow version.
    version = _override_str(overrides, "version") or get_version_info()["version"]

    # Builds the graph from flow.data and injects a session_id property. A flow
    # can be flagged for A2A with empty/unbuildable data, so degrade to an empty
    # input contract rather than 500ing the public discovery endpoint.
    try:
        input_schema = json_schema_from_flow(flow)
    except Exception:  # noqa: BLE001 - any graph build failure degrades, not crashes
        logger.warning("Could not build A2A input schema for flow %s; serving empty input contract", flow.id)
        input_schema = dict(_EMPTY_INPUT_SCHEMA)

    skill = a2a_types.AgentSkill(
        id=str(flow.id),
        name=name,
        description=description,
        tags=_override_str_list(overrides, "tags") or ["langflow"],
        examples=_override_str_list(overrides, "examples"),
        input_modes=["application/json"],
        output_modes=["application/json"],
    )
    # streaming / push_notifications must be explicit, or exclude_none drops them.
    # Both match the handler card's capabilities: streaming gates message/stream +
    # tasks/resubscribe; push_notifications gates the tasks/pushNotificationConfig methods.
    capabilities = a2a_types.AgentCapabilities(streaming=True, push_notifications=True)
    security_schemes, security = await resolve_card_security(flow, session)

    card = a2a_types.AgentCard(
        name=name,
        description=description,
        url=rpc_url,
        version=version,
        capabilities=capabilities,
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        skills=[skill],
        security_schemes=security_schemes,
        security=security,
    )

    card_dict = card.model_dump(mode="json", by_alias=True, exclude_none=True)
    # AgentSkill has no inputSchema field; inject the flow schema post-dump.
    card_dict["skills"][0]["inputSchema"] = input_schema
    return card_dict
