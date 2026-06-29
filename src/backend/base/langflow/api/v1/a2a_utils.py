"""Helpers for building spec-valid A2A agent cards from Langflow flows.

The typed models come from ``a2a.compat.v0_3.types`` (pydantic). Do NOT import
from ``a2a.types`` — in a2a-sdk 1.x those are protobuf messages that serialize
to a non-spec shape (no top-level ``url``, oneof-wrapped ``securitySchemes``,
``location`` instead of ``in``).
"""

import asyncio
from urllib.parse import urlparse

import httpx
from a2a.compat.v0_3 import types as a2a_types
from lfx.log.logger import logger
from lfx.services.deps import get_settings_service
from lfx.utils.ssrf_protection import SSRFProtectionError, is_ip_blocked, resolve_hostname, validate_and_resolve_url
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


def webhook_pin_host(url: str) -> str:
    """Return the host httpx/httpcore actually connects to (the IDNA/punycode ``raw_host``).

    httpx connects using ``raw_host`` (e.g. ``xn--exmple-cua.com``), not the unicode
    ``urlparse().hostname`` (``exämple.com``). The DNS-pin key and the host we resolve must
    both be this exact representation, or for an internationalized webhook the pin key won't
    match the connected host and the pin is silently bypassed (TOCTOU rebind for IDN hosts).
    Single source of truth for both the resolve/validate step and the dispatch pin.
    """
    return httpx.URL(url).raw_host.decode("ascii")


async def validate_webhook_url(url: str) -> list[str]:
    """Validate a push-notification webhook URL (SSRF guard) and return IPs for DNS pinning.

    The A2A endpoint is public, so the webhook target is caller-controlled. Require
    http/https, then enforce a hard IP floor that does NOT depend on the global
    ``LANGFLOW_SSRF_PROTECTION_ENABLED`` toggle (ops disable it for the API Request
    component, which would otherwise reopen private/metadata webhooks): resolve the
    host and reject if any IP is blocked. On top of the floor, run the shared SSRF
    framework (``validate_and_resolve_url``) for the allowlist / CGNAT / ``is_global``
    extras and pinned IPs. The returned IPs let the dispatch client pin DNS (closing
    the rebind window). ``LANGFLOW_A2A_ALLOW_PRIVATE_WEBHOOKS`` skips the IP check for
    a trusted internal network (returns ``[]``: nothing to pin).

    Raises ``ValueError`` when the URL is unsafe. Returns the validated IPs (framework
    IPs, falling back to the floor-resolved IPs when the global toggle is off), or
    ``[]`` when private webhooks are allowed. Used at registration (set_info) and
    re-run at dispatch.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        msg = "webhook url must be http or https"
        raise ValueError(msg)
    if not parsed.hostname:
        msg = "webhook url has no host"
        raise ValueError(msg)
    if get_settings_service().settings.a2a_allow_private_webhooks:
        return []
    # Resolve/validate the SAME host httpx connects to (IDNA/punycode raw_host), not the
    # unicode urlparse hostname, so an IDN webhook is pinned/resolved by the exact ASCII
    # host the connection uses (else the pin silently misses: TOCTOU rebind for IDN hosts).
    host = webhook_pin_host(url)
    try:
        # Hard floor: reject private/metadata IPs even when global SSRF protection is off
        # (validate_and_resolve_url returns [] with NO enforcement in that case).
        # resolve_hostname handles IP-literal hosts too; the blocking resolve runs off-loop.
        floor_ips = await asyncio.to_thread(resolve_hostname, host)
        blocked = [ip for ip in floor_ips if is_ip_blocked(ip)]
        if blocked:
            msg = f"webhook url resolves to a blocked address: {', '.join(blocked)}"
            raise ValueError(msg)
        # Then the framework check for allowlist / CGNAT / is_global extras + pinned IPs.
        _url, validated_ips = await asyncio.to_thread(validate_and_resolve_url, url)
    except SSRFProtectionError as exc:
        msg = f"webhook url is not allowed: {exc}"
        raise ValueError(msg) from exc
    # Fall back to the floor IPs so dispatch can still DNS-pin with the global toggle off.
    return validated_ips or floor_ips


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
