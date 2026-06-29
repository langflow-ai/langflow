"""Helpers for building spec-valid A2A agent cards from Langflow flows.

The typed models come from ``a2a.compat.v0_3.types`` (pydantic). Do NOT import
from ``a2a.types`` — in a2a-sdk 1.x those are protobuf messages that serialize
to a non-spec shape (no top-level ``url``, oneof-wrapped ``securitySchemes``,
``location`` instead of ``in``).
"""

import asyncio

from a2a.compat.v0_3 import types as a2a_types
from lfx.log.logger import logger
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

# Bound free-form a2a_card_overrides so they can't bloat the public,
# unauthenticated card (a single over-long string or an unbounded examples/tags
# list). Legitimate overrides are well under these.
_MAX_OVERRIDE_STR_LEN = 1000
_MAX_OVERRIDE_LIST_ITEMS = 50


def _override_str(overrides: dict, key: str) -> str | None:
    """Return a non-empty, length-bounded string override, or None.

    a2a_card_overrides is a free-form dict, so a non-string value must not reach
    the typed card model (it would raise pydantic ValidationError). Over-long
    values are dropped so the card falls back to the flow default.
    """
    value = overrides.get(key)
    if isinstance(value, str) and value and len(value) <= _MAX_OVERRIDE_STR_LEN:
        return value
    return None


def _override_str_list(overrides: dict, key: str) -> list[str] | None:
    """Return a non-empty list-of-strings override (count- and length-bounded), or None."""
    value = overrides.get(key)
    if (
        isinstance(value, list)
        and value
        and all(isinstance(item, str) and len(item) <= _MAX_OVERRIDE_STR_LEN for item in value)
    ):
        return value[:_MAX_OVERRIDE_LIST_ITEMS]
    return None


async def resolve_card_security(
    flow: Flow,
    session: AsyncSession,
) -> tuple[dict[str, a2a_types.SecurityScheme] | None, list[dict[str, list[str]]] | None]:
    """Reflect the flow's folder auth onto the A2A card (securitySchemes, security).

    Reflect-only: enforcement is F6. No decryption needed — only ``auth_type``
    is read, which is plaintext. Returns ``(None, None)`` when there is no
    API-key requirement.
    """
    if flow.folder_id is None:
        return None, None

    # Query the folder explicitly; lazy-loading flow.folder would raise in async.
    folder = (await session.exec(select(Folder).where(Folder.id == flow.folder_id))).first()
    auth_type = (folder.auth_settings or {}).get("auth_type", "none") if folder else "none"

    if auth_type == "apikey":
        scheme = a2a_types.SecurityScheme(
            a2a_types.APIKeySecurityScheme(
                in_=a2a_types.In.header,
                name=A2A_APIKEY_HEADER,
                description="API key passed in the x-api-key header.",
            )
        )
        return {A2A_APIKEY_SCHEME_NAME: scheme}, [{A2A_APIKEY_SCHEME_NAME: []}]

    # "none" / missing / "oauth" -> advertise no security. oauth is out of F2
    # scope; F6 maps it to the right scheme.
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
        # json_schema_from_flow does a full, synchronous graph build; offload it
        # so this public endpoint never blocks the event loop.
        input_schema = await asyncio.to_thread(json_schema_from_flow, flow)
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
    # streaming matches the handler card's capability (message/stream + tasks/resubscribe);
    # push_notifications stays False until that surface lands.
    capabilities = a2a_types.AgentCapabilities(streaming=True, push_notifications=False)
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
