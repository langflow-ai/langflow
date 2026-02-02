"""MCP OAuth API endpoints for deployment-ready authentication.

This module provides REST API endpoints for OAuth authentication with MCP servers,
using the MCP SDK's OAuthClientProvider for all OAuth operations (metadata discovery,
PKCE, token exchange, and automatic token refresh).

The flow works as follows:
1. Frontend calls POST /initiate with server config
2. Backend starts background task that runs the full OAuth flow
3. Frontend polls GET /status/{flow_id} to get the auth URL
4. Frontend opens auth URL in popup
5. User completes OAuth, provider redirects to GET /callback
6. Backend stores callback, background task completes token exchange
7. Frontend polls GET /status/{flow_id} until complete
8. Tokens are automatically used (with refresh) by MCP component on next connection
"""

from __future__ import annotations

import asyncio
from typing import Annotated

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from lfx.base.mcp.oauth.provider import (
    create_deployed_oauth_provider,
)
from lfx.base.mcp.oauth.state_manager import get_oauth_state_manager
from lfx.log.logger import logger

from langflow.api.utils import CurrentActiveUser
from langflow.api.v1.schemas import (
    OAuthInitiateRequest,
    OAuthInitiateResponse,
    OAuthRevokeResponse,
    OAuthStatusResponse,
)

router = APIRouter(prefix="/mcp/oauth", tags=["mcp-oauth"])


# HTML templates for callback responses
SUCCESS_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Authentication Successful</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .container {
            text-align: center;
            padding: 40px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        h1 { color: #22c55e; margin-bottom: 10px; }
        p { color: #666; }
    </style>
    <script>
        // Auto-close popup after a short delay
        setTimeout(function() {
            if (window.opener) {
                window.close();
            }
        }, 2000);
    </script>
</head>
<body>
    <div class="container">
        <h1>Authentication Successful</h1>
        <p>You can close this window and return to Langflow.</p>
        <p style="font-size: 12px; color: #999;">This window will close automatically.</p>
    </div>
</body>
</html>"""

ERROR_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <title>Authentication Failed</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
        .container {{
            text-align: center;
            padding: 40px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            max-width: 500px;
        }}
        h1 {{ color: #ef4444; margin-bottom: 10px; }}
        p {{ color: #666; }}
        .error {{ color: #dc2626; font-family: monospace; word-break: break-word; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Authentication Failed</h1>
        <p class="error">{error_message}</p>
        <p>Please close this window and try again.</p>
    </div>
</body>
</html>"""


@router.post("/initiate", response_model=OAuthInitiateResponse)
async def initiate_oauth_flow(
    oauth_request: OAuthInitiateRequest,
    http_request: Request,
    current_user: CurrentActiveUser,
) -> OAuthInitiateResponse:
    """Initiate an OAuth flow for an MCP server.

    This endpoint uses the MCP SDK's OAuthClientProvider which:
    1. Discovers OAuth metadata automatically (RFC 8414, RFC 9728)
    2. Handles PKCE generation
    3. Registers the client dynamically if needed
    4. Builds the authorization URL

    When the SDK triggers a redirect, we catch OAuthFlowStarted and return
    the authorization URL to the frontend.

    Args:
        oauth_request: The OAuth initiate request with server config.
        http_request: The FastAPI request object (for determining callback URL).
        current_user: The authenticated user.

    Returns:
        The flow ID and authorization URL.
    """
    from langflow.services.deps import get_settings_service

    user_id = str(current_user.id)
    server_url = oauth_request.server_url

    # Determine redirect URI for callback
    # Priority: explicit redirect_uri > callback_base_url > backend_url setting > request base URL
    settings = get_settings_service().settings

    if oauth_request.redirect_uri:
        # Use explicit redirect URI (for OAuth providers with specific callback requirements)
        callback_uri = oauth_request.redirect_uri
    elif oauth_request.callback_base_url:
        # Use the URL provided by the frontend (most reliable in deployed environments)
        base_url = oauth_request.callback_base_url.rstrip("/")
        callback_uri = f"{base_url}/api/v1/mcp/oauth/callback"
    elif getattr(settings, "backend_url", None):
        # Use explicitly configured backend URL
        base_url = settings.backend_url.rstrip("/")
        callback_uri = f"{base_url}/api/v1/mcp/oauth/callback"
    else:
        # Fallback to the request's base URL
        base_url = str(http_request.base_url).rstrip("/")
        callback_uri = f"{base_url}/api/v1/mcp/oauth/callback"

    try:
        # Clear any existing tokens first - if /initiate is called, existing tokens are invalid
        # This forces the SDK to start a fresh OAuth flow
        from lfx.base.mcp.oauth.provider import get_server_key

        state_manager = await get_oauth_state_manager()
        server_key = get_server_key(server_url)
        await state_manager.delete_tokens(user_id, server_key)

        # Create the flow first so we have a flow_id to return
        flow_config = {
            "client_id": oauth_request.client_id,
            "client_secret": oauth_request.client_secret,
        }
        flow_id, _state_param = await state_manager.create_flow(user_id, server_url, flow_config)

        # Define the background task that runs the full OAuth flow
        async def run_oauth_flow() -> None:
            try:
                # Create SDK-based provider with the pre-created flow_id
                provider, _, _cleanup = await create_deployed_oauth_provider(
                    server_url=server_url,
                    user_id=user_id,
                    redirect_uri=callback_uri,
                    client_id=oauth_request.client_id,
                    client_secret=oauth_request.client_secret,
                    scopes=oauth_request.scopes,
                    flow_id=flow_id,  # Use the pre-created flow_id
                )

                # Trigger OAuth - SDK discovers metadata, registers client if needed, and builds auth URL
                # The redirect_handler will store the auth_url, then the SDK calls callback_handler
                # which waits for the callback. Once received, SDK completes token exchange.
                async with httpx.AsyncClient(auth=provider, timeout=600.0) as client:
                    # Use POST with minimal JSON-RPC message to trigger 401
                    # MCP servers only check auth on POST requests, not HEAD
                    response = await client.post(
                        server_url,
                        json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
                    )
                    # If we get here, the OAuth flow completed successfully
                    await logger.ainfo(
                        f"OAuth flow {flow_id} completed successfully, status: {response.status_code}"
                    )

                # Mark flow as complete
                flow_data = await state_manager.get_flow_by_id(flow_id)
                if flow_data:
                    flow_data["status"] = "complete"
                    await state_manager._cache_set(  # noqa: SLF001
                        state_manager._flow_key(flow_id),  # noqa: SLF001
                        flow_data,
                    )
                    await logger.ainfo(f"OAuth flow {flow_id} marked as complete")

            except TimeoutError:
                await logger.awarning(f"OAuth flow {flow_id} timed out waiting for callback")
                flow_data = await state_manager.get_flow_by_id(flow_id)
                if flow_data:
                    flow_data["status"] = "error"
                    flow_data["error_message"] = "OAuth flow timed out"
                    await state_manager._cache_set(  # noqa: SLF001
                        state_manager._flow_key(flow_id),  # noqa: SLF001
                        flow_data,
                    )
            except Exception as e:
                await logger.aexception(f"OAuth flow {flow_id} failed: {e}")
                flow_data = await state_manager.get_flow_by_id(flow_id)
                if flow_data:
                    flow_data["status"] = "error"
                    flow_data["error_message"] = str(e)
                    await state_manager._cache_set(  # noqa: SLF001
                        state_manager._flow_key(flow_id),  # noqa: SLF001
                        flow_data,
                    )

        # Start the OAuth flow in the background
        asyncio.create_task(run_oauth_flow())

        # Wait for auth_url to be available (up to 30 seconds)
        # This allows the frontend to get the auth_url directly from /initiate
        auth_url = ""
        for _ in range(60):  # 60 * 0.5s = 30s timeout
            await asyncio.sleep(0.5)
            flow_data = await state_manager.get_flow_by_id(flow_id)
            if flow_data:
                if flow_data.get("status") == "awaiting_callback":
                    auth_url = flow_data.get("auth_url", "")
                    break
                if flow_data.get("status") == "error":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=flow_data.get("error_message", "OAuth flow failed"),
                    )
                if flow_data.get("status") == "complete":
                    # Already authenticated (shouldn't happen but handle it)
                    auth_url = ""
                    break

        await logger.ainfo(
            f"Started OAuth flow {flow_id} for user {user_id}, server {server_url}, "
            f"auth_url={'present' if auth_url else 'empty'} ({len(auth_url)} chars)"
        )
        return OAuthInitiateResponse(
            flow_id=flow_id,
            auth_url=auth_url,
            expires_in=600,
        )

    except Exception as e:
        await logger.aexception(f"Failed to initiate OAuth flow: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to initiate OAuth flow: {e}",
        ) from e


@router.get("/callback", response_class=HTMLResponse)
async def oauth_callback(
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
    error_description: Annotated[str | None, Query()] = None,
) -> HTMLResponse:
    """Handle OAuth callback from the authorization server.

    This is a PUBLIC endpoint (no auth required) because OAuth providers
    cannot send authentication headers in the redirect.

    The callback stores the authorization code for the SDK's callback_handler
    to retrieve and complete the token exchange automatically.

    Args:
        code: The authorization code (if successful).
        state: The state parameter from the authorization request.
        error: OAuth error code (if failed).
        error_description: OAuth error description (if failed).

    Returns:
        HTML response that auto-closes the popup.
    """
    import html

    # Handle OAuth errors
    if error:
        # Escape error message to prevent XSS
        error_msg = html.escape(error_description or error)
        await logger.awarning(f"OAuth callback received error: {error_msg}")

        if state:
            state_manager = await get_oauth_state_manager()
            await state_manager.fail_flow(state, error_msg)

        return HTMLResponse(
            content=ERROR_HTML_TEMPLATE.format(error_message=error_msg),
            status_code=400,
        )

    # Validate required parameters
    if not code or not state:
        error_msg = "Missing code or state parameter"
        await logger.awarning(f"OAuth callback missing parameters: code={bool(code)}, state={bool(state)}")
        return HTMLResponse(
            content=ERROR_HTML_TEMPLATE.format(error_message=error_msg),
            status_code=400,
        )

    # Store callback for SDK's callback_handler to retrieve
    # The SDK will complete the token exchange automatically
    state_manager = await get_oauth_state_manager()
    success = await state_manager.store_callback(state, code)

    if not success:
        error_msg = "OAuth flow expired or not found"
        await logger.awarning(f"OAuth callback for unknown state: {state[:20]}...")
        return HTMLResponse(
            content=ERROR_HTML_TEMPLATE.format(error_message=error_msg),
            status_code=400,
        )

    await logger.ainfo(f"OAuth callback received for state {state[:20]}...")
    return HTMLResponse(content=SUCCESS_HTML, status_code=200)


@router.get("/status/{flow_id}", response_model=OAuthStatusResponse)
async def get_oauth_status(
    flow_id: str,
    current_user: CurrentActiveUser,
) -> OAuthStatusResponse:
    """Poll the status of an OAuth flow.

    Frontend calls this endpoint repeatedly until status is "complete" or "error".
    When status is "awaiting_callback", the auth_url field contains the URL to open.

    Args:
        flow_id: The flow ID returned from /initiate.
        current_user: The authenticated user (for validation).

    Returns:
        The current status of the OAuth flow.
    """
    state_manager = await get_oauth_state_manager()
    result = await state_manager.get_flow_status(flow_id, str(current_user.id))

    response = OAuthStatusResponse(
        status=result.get("status", "expired"),
        auth_url=result.get("auth_url"),
        error_message=result.get("error_message"),
        server_url=result.get("server_url"),
    )
    await logger.adebug(f"OAuth status for {flow_id}: {response.status}, auth_url={'present' if response.auth_url else 'none'}")
    return response


@router.delete("/tokens/{server_key}", response_model=OAuthRevokeResponse)
async def revoke_oauth_tokens(
    server_key: str,
    current_user: CurrentActiveUser,
) -> OAuthRevokeResponse:
    """Revoke (delete) stored OAuth tokens for a server.

    Args:
        server_key: The server key identifying the MCP server.
        current_user: The authenticated user.

    Returns:
        Success status and message.
    """
    state_manager = await get_oauth_state_manager()
    deleted = await state_manager.delete_tokens(str(current_user.id), server_key)

    if deleted:
        return OAuthRevokeResponse(
            success=True,
            message=f"OAuth tokens revoked for server: {server_key}",
        )
    return OAuthRevokeResponse(
        success=False,
        message=f"No OAuth tokens found for server: {server_key}",
    )


@router.get("/tokens/{server_key}/check")
async def check_oauth_tokens(
    server_key: str,
    current_user: CurrentActiveUser,
) -> dict:
    """Check if OAuth tokens exist for a server.

    Args:
        server_key: The server key identifying the MCP server.
        current_user: The authenticated user.

    Returns:
        Dict with has_tokens boolean.
    """
    state_manager = await get_oauth_state_manager()
    tokens = await state_manager.get_tokens(str(current_user.id), server_key)

    return {"has_tokens": tokens is not None}
