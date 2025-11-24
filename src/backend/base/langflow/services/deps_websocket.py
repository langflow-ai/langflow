"""Helper dependencies for WebSocket handlers.

WebSocket connections do not pass through the HTTP middleware stack, so
FastAPI dependencies that rely on middleware-populated context (like the
organisation-aware DB selector) fail unless the context is populated
manually. The helpers in this module ensure the Clerk organisation
context is available before downstream dependencies run.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator  # noqa:TC003
from contextvars import Token
from typing import Annotated

from fastapi import Depends, WebSocket, WebSocketException, status

from langflow.logging import logger
from langflow.services.auth.api_key_codec import decode_api_key
from langflow.services.auth.clerk_utils import auth_header_ctx, verify_clerk_token
from langflow.services.deps import get_settings_service


async def _populate_org_context(websocket: WebSocket) -> Token | None:
    """Populate ``auth_header_ctx`` with organisation data for WebSockets."""
    settings = get_settings_service()
    if not settings.auth_settings.CLERK_AUTH_ENABLED:
        return None

    payload: dict | None = None

    token = websocket.cookies.get("access_token_lf") or websocket.query_params.get("token")
    if token:
        logger.info("Verifying Clerk token for websocket connection.")
        try:
            payload = await verify_clerk_token(token)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to verify Clerk token for websocket: %s", exc)

    if payload is None:
        api_key = (
            websocket.query_params.get("x-api-key")
            or websocket.query_params.get("api_key")
            or websocket.headers.get("x-api-key")
            or websocket.headers.get("api_key")
        )
        if api_key:
            logger.info("Decoding API key for websocket connection.")
            decoded = decode_api_key(api_key)
            if decoded.organization_id:
                payload = {"org_id": decoded.organization_id}
                if decoded.user_id:
                    payload["uuid"] = decoded.user_id

    if payload:
        return auth_header_ctx.set(payload)

    raise WebSocketException(
        code=status.WS_1008_POLICY_VIOLATION,
        reason="Missing organisation id. Provide a Clerk token or organisation-scoped API key.",
    )


async def websocket_org_context(websocket: WebSocket) -> AsyncGenerator[Token | None, None]:
    """FastAPI dependency that seeds Clerk context for WebSockets."""
    ctx_token: Token | None = None
    try:
        ctx_token = await _populate_org_context(websocket)
        yield ctx_token
    finally:
        if ctx_token is not None:
            auth_header_ctx.reset(ctx_token)
        elif get_settings_service().auth_settings.CLERK_AUTH_ENABLED:
            auth_header_ctx.set(None)


WebsocketOrgContext = Annotated[Token | None, Depends(websocket_org_context)]

WEBSOCKET_ORG_DEPENDENCIES = [Depends(websocket_org_context)]
