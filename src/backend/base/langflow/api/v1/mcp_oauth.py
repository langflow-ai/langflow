"""MCP OAuth API endpoints for deployment-ready authentication.

This module provides REST API endpoints for OAuth authentication with MCP servers,
enabling OAuth flows to work in deployed environments where the user's browser
cannot directly communicate with the Langflow server's local callback handler.

The flow works as follows:
1. Frontend calls POST /initiate with server config
2. Backend discovers OAuth metadata and builds auth URL
3. Frontend opens auth URL in popup
4. User completes OAuth, provider redirects to GET /callback
5. Backend exchanges code for tokens, stores in cache
6. Frontend polls GET /status/{flow_id} until complete
7. Tokens are automatically used by MCP component on next connection
"""

from __future__ import annotations

import hashlib
import secrets
from base64 import urlsafe_b64encode
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from lfx.log.logger import logger

from langflow.api.utils import CurrentActiveUser
from lfx.base.mcp.oauth.state_manager import get_oauth_state_manager

from langflow.api.v1.schemas import (
    OAuthInitiateRequest,
    OAuthInitiateResponse,
    OAuthRevokeResponse,
    OAuthStatusResponse,
)

# HTTP status code constants
HTTP_OK = 200
HTTP_CREATED = 201

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


def generate_pkce() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge.

    Returns:
        A tuple of (code_verifier, code_challenge).
    """
    # Generate 128-character code verifier using allowed characters
    allowed_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
    code_verifier = "".join(secrets.choice(allowed_chars) for _ in range(128))

    # Generate code challenge using SHA256
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = urlsafe_b64encode(digest).decode().rstrip("=")

    return code_verifier, code_challenge


async def discover_oauth_metadata(server_url: str) -> dict | None:
    """Discover OAuth authorization server metadata.

    Follows RFC 8414 and tries multiple discovery URLs:
    1. Protected Resource Metadata at /.well-known/oauth-protected-resource
    2. Authorization Server Metadata at /.well-known/oauth-authorization-server
    3. OIDC discovery at /.well-known/openid-configuration

    Args:
        server_url: The MCP server URL.

    Returns:
        The OAuth metadata dict if found, None otherwise.
    """
    from urllib.parse import urlparse

    parsed = urlparse(server_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    # Try protected resource metadata first (RFC 9728)
    prm_urls = [
        f"{base_url}/.well-known/oauth-protected-resource{parsed.path}",
        f"{base_url}/.well-known/oauth-protected-resource",
    ]

    auth_server_url = None
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Step 1: Try to get Protected Resource Metadata
        for url in prm_urls:
            try:
                response = await client.get(url)
                if response.status_code == HTTP_OK:
                    prm = response.json()
                    # Get authorization server URL from PRM
                    auth_servers = prm.get("authorization_servers", [])
                    if auth_servers:
                        auth_server_url = auth_servers[0]
                        break
            except (httpx.RequestError, httpx.HTTPStatusError, ValueError, KeyError):
                # Network errors, HTTP errors, or JSON parsing errors - try next URL
                continue

        # If no PRM, use server URL as auth server base
        if not auth_server_url:
            auth_server_url = base_url

        # Strip trailing slash to avoid double-slash in URLs
        auth_server_url = auth_server_url.rstrip("/")

        # Step 2: Discover OAuth/OIDC metadata
        asm_urls = [
            f"{auth_server_url}/.well-known/oauth-authorization-server",
            f"{auth_server_url}/.well-known/openid-configuration",
        ]

        for url in asm_urls:
            try:
                response = await client.get(url)
                if response.status_code == HTTP_OK:
                    metadata = response.json()
                    # Validate required fields
                    if "authorization_endpoint" in metadata and "token_endpoint" in metadata:
                        return metadata
            except (httpx.RequestError, httpx.HTTPStatusError, ValueError, KeyError):
                # Network errors, HTTP errors, or JSON parsing errors - try next URL
                continue

    return None


async def register_client_dynamically(
    metadata: dict,
    redirect_uri: str,
    client_name: str = "langflow",
) -> dict | None:
    """Perform Dynamic Client Registration (RFC 7591).

    Args:
        metadata: OAuth authorization server metadata.
        redirect_uri: The redirect URI to register.
        client_name: The client name.

    Returns:
        The client registration response if successful, None otherwise.
    """
    registration_endpoint = metadata.get("registration_endpoint")
    if not registration_endpoint:
        await logger.awarning("Server does not support Dynamic Client Registration")
        return None

    registration_request = {
        "client_name": client_name,
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",  # Public client
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                registration_endpoint,
                json=registration_request,
                headers={"Content-Type": "application/json"},
            )
            if response.status_code in (HTTP_OK, HTTP_CREATED):
                return response.json()
            await logger.awarning(f"Dynamic Client Registration failed: {response.status_code} - {response.text}")
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError, KeyError) as e:
            await logger.awarning(f"Dynamic Client Registration error: {e}")

    return None


async def exchange_code_for_tokens(
    metadata: dict,
    code: str,
    code_verifier: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str | None = None,
) -> dict:
    """Exchange authorization code for tokens.

    Args:
        metadata: OAuth authorization server metadata.
        code: The authorization code.
        code_verifier: The PKCE code verifier.
        redirect_uri: The redirect URI used in the authorization request.
        client_id: The client ID.
        client_secret: The client secret (optional, for confidential clients).

    Returns:
        The token response dict.

    Raises:
        HTTPException: If token exchange fails.
    """
    token_endpoint = metadata.get("token_endpoint")
    if not token_endpoint:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token endpoint not found in OAuth metadata",
        )

    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": code_verifier,
    }

    if client_secret:
        token_data["client_secret"] = client_secret

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                token_endpoint,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if response.status_code != HTTP_OK:
                error_body = response.text
                await logger.aerror(f"Token exchange failed: {response.status_code} - {error_body}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Token exchange failed: {error_body}",
                )

            return response.json()
        except httpx.RequestError as e:
            await logger.aerror(f"Token exchange request error: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to connect to token endpoint: {e}",
            ) from e


@router.post("/initiate", response_model=OAuthInitiateResponse)
async def initiate_oauth_flow(
    oauth_request: OAuthInitiateRequest,
    http_request: Request,
    current_user: CurrentActiveUser,
) -> OAuthInitiateResponse:
    """Initiate an OAuth flow for an MCP server.

    This endpoint:
    1. Discovers OAuth metadata from the MCP server
    2. Registers the client dynamically if needed
    3. Generates PKCE parameters
    4. Creates an OAuth flow in the cache
    5. Returns the authorization URL for the frontend to open

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

    # Discover OAuth metadata
    metadata = await discover_oauth_metadata(server_url)
    if not metadata:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not discover OAuth metadata for server: {server_url}",
        )

    # Determine redirect URI for callback
    # Priority: 1. explicit redirect_uri, 2. callback_base_url from frontend, 3. backend_url setting, 4. request's base URL
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

    # Get or register client
    client_id = oauth_request.client_id
    client_secret = oauth_request.client_secret

    if not client_id:
        # Try Dynamic Client Registration
        registration = await register_client_dynamically(
            metadata,
            callback_uri,
            client_name="langflow",
        )
        if registration:
            client_id = registration.get("client_id")
            client_secret = registration.get("client_secret")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Server does not support Dynamic Client Registration. "
                "Please provide a pre-registered client_id.",
            )

    # Generate PKCE parameters
    code_verifier, code_challenge = generate_pkce()

    # Create flow in state manager
    state_manager = await get_oauth_state_manager()
    flow_config = {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": callback_uri,
        "code_verifier": code_verifier,
        "metadata": metadata,
        "scopes": oauth_request.scopes,
    }
    flow_id, state_param = await state_manager.create_flow(
        user_id=user_id,
        server_url=server_url,
        config=flow_config,
    )

    # Build authorization URL
    authorization_endpoint = metadata.get("authorization_endpoint")
    auth_params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": callback_uri,
        "state": state_param,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    # Add scopes if provided
    if oauth_request.scopes:
        auth_params["scope"] = " ".join(oauth_request.scopes)

    auth_url = f"{authorization_endpoint}?{urlencode(auth_params)}"

    await logger.ainfo(f"Initiated OAuth flow {flow_id} for user {user_id}, server {server_url}")

    return OAuthInitiateResponse(
        flow_id=flow_id,
        auth_url=auth_url,
        expires_in=600,
    )


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

    The state parameter is used to look up the flow and validate the callback.

    Args:
        code: The authorization code (if successful).
        state: The state parameter from the authorization request.
        error: OAuth error code (if failed).
        error_description: OAuth error description (if failed).

    Returns:
        HTML response that auto-closes the popup.
    """
    # Handle OAuth errors
    if error:
        error_msg = error_description or error
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

    # Look up flow by state
    state_manager = await get_oauth_state_manager()
    flow_data = await state_manager.get_flow(state)

    if not flow_data:
        error_msg = "OAuth flow expired or not found"
        await logger.awarning(f"OAuth callback for unknown state: {state[:20]}...")
        return HTMLResponse(
            content=ERROR_HTML_TEMPLATE.format(error_message=error_msg),
            status_code=400,
        )

    # Exchange code for tokens
    try:
        config = flow_data.get("config", {})
        metadata = config.get("metadata", {})
        client_id = config.get("client_id")
        client_secret = config.get("client_secret")
        code_verifier = config.get("code_verifier")
        redirect_uri = config.get("redirect_uri")

        tokens = await exchange_code_for_tokens(
            metadata=metadata,
            code=code,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
            client_id=client_id,
            client_secret=client_secret,
        )

        # Store tokens and mark flow complete
        await state_manager.complete_flow(state, tokens)

        await logger.ainfo(f"OAuth flow completed successfully for flow {flow_data.get('flow_id')}")
        return HTMLResponse(content=SUCCESS_HTML, status_code=HTTP_OK)

    except HTTPException as e:
        error_msg = str(e.detail)
        await state_manager.fail_flow(state, error_msg)
        return HTMLResponse(
            content=ERROR_HTML_TEMPLATE.format(error_message=error_msg),
            status_code=400,
        )
    except Exception as e:  # noqa: BLE001
        # Catch-all for unexpected errors to ensure user gets a proper error page
        error_msg = f"Token exchange failed: {e!s}"
        await logger.aexception(error_msg)
        await state_manager.fail_flow(state, error_msg)
        return HTMLResponse(
            content=ERROR_HTML_TEMPLATE.format(error_message=error_msg),
            status_code=500,
        )


@router.get("/status/{flow_id}", response_model=OAuthStatusResponse)
async def get_oauth_status(
    flow_id: str,
    current_user: CurrentActiveUser,
) -> OAuthStatusResponse:
    """Poll the status of an OAuth flow.

    Frontend calls this endpoint repeatedly until status is "complete" or "error".

    Args:
        flow_id: The flow ID returned from /initiate.
        current_user: The authenticated user (for validation).

    Returns:
        The current status of the OAuth flow.
    """
    state_manager = await get_oauth_state_manager()
    result = await state_manager.get_flow_status(flow_id, str(current_user.id))

    return OAuthStatusResponse(
        status=result.get("status", "expired"),
        error_message=result.get("error_message"),
        server_url=result.get("server_url"),
    )


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
