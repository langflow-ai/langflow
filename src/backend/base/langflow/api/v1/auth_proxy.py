"""
Auth Proxy Router - Forwards authentication requests to genesis-service-auth.

This module provides proxy endpoints that forward authentication-related requests
from the frontend to the genesis-service-auth service (port 3005), maintaining
feature parity with the genesis-bff architecture while eliminating the proxy layer.
"""

from typing import Any

import requests
from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from loguru import logger

from langflow.services.deps import get_settings_service

# Create router with /auth prefix
auth_proxy_router = APIRouter(prefix="/auth", tags=["auth-proxy"])


def _get_auth_service_url() -> str:
    """Get auth service URL from settings."""
    settings_service = get_settings_service()
    auth_url = settings_service.settings.genesis_service_auth_url
    if not auth_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GENESIS_SERVICE_AUTH_URL not configured",
        )
    return auth_url.rstrip("/")


def _forward_to_auth_service(
    method: str,
    endpoint: str,
    headers: dict[str, str] | None = None,
    json_data: dict[str, Any] | None = None,
    timeout: int = 10,
) -> tuple[int, dict[str, Any]]:
    """
    Forward HTTP request to auth service.

    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint: Auth service endpoint path (e.g., "/logout")
        headers: Optional request headers
        json_data: Optional JSON body
        timeout: Request timeout in seconds

    Returns:
        Tuple of (status_code, response_data)

    Raises:
        HTTPException: If request fails or times out
    """
    auth_service_url = _get_auth_service_url()
    url = f"{auth_service_url}{endpoint}"

    try:
        logger.debug(f"Forwarding {method} request to auth service: {url}")

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=json_data,
            timeout=timeout,
        )

        # Return status code and JSON response
        try:
            response_data = response.json()
        except Exception:
            response_data = {"message": response.text}

        return response.status_code, response_data

    except requests.exceptions.Timeout:
        logger.error(f"Auth service request timeout: {url}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Auth service request timed out",
        )
    except requests.exceptions.ConnectionError:
        logger.error(f"Failed to connect to auth service: {url}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service unavailable",
        )
    except Exception as e:
        logger.error(f"Auth service request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Auth service request failed: {str(e)}",
        )


@auth_proxy_router.post("/logout")
async def logout(
    request: Request,
    authorization: str = Header(None),
) -> JSONResponse:
    """
    Logout user and invalidate tokens.

    Forwards logout request to auth service which will:
    - Invalidate the user's access and refresh tokens
    - Clear user cache
    - Optionally revoke tokens with Keycloak

    Args:
        request: FastAPI request object
        authorization: JWT token from Authorization header

    Returns:
        JSONResponse with logout result
    """
    # Get request body
    try:
        body = await request.json()
    except Exception:
        body = {}

    # Forward to auth service
    headers = {}
    if authorization:
        headers["authorization"] = authorization

    status_code, response_data = _forward_to_auth_service(
        method="POST",
        endpoint="/logout",
        headers=headers,
        json_data=body,
    )

    return JSONResponse(status_code=status_code, content=response_data)


@auth_proxy_router.post("/refresh-token/{email_id}")
async def refresh_token(
    email_id: str,
    request: Request,
) -> JSONResponse:
    """
    Refresh access token using refresh token.

    Forwards refresh token request to auth service which will:
    - Validate the refresh token
    - Generate new access and refresh tokens
    - Update user cache

    Args:
        email_id: User's email ID
        request: FastAPI request object (expects {"refreshToken": "..."})

    Returns:
        JSONResponse with new tokens
    """
    # Get request body
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body must contain refreshToken",
        )

    # Forward to auth service
    status_code, response_data = _forward_to_auth_service(
        method="POST",
        endpoint=f"/refresh-token/{email_id}",
        json_data=body,
    )

    return JSONResponse(status_code=status_code, content=response_data)


@auth_proxy_router.post("/introspect-token/{email_id}")
async def introspect_token_by_email(
    email_id: str,
    request: Request,
) -> JSONResponse:
    """
    Validate token and get user information by email ID.

    Forwards introspection request to auth service which will:
    - Validate the provided token
    - Return user information if valid
    - Check token expiration

    Args:
        email_id: User's email ID
        request: FastAPI request object (expects {"token": "..."})

    Returns:
        JSONResponse with user information
    """
    # Get request body
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body must contain token",
        )

    # Forward to auth service
    status_code, response_data = _forward_to_auth_service(
        method="POST",
        endpoint=f"/introspect-token/{email_id}",
        json_data=body,
    )

    return JSONResponse(status_code=status_code, content=response_data)


@auth_proxy_router.get("/introspect-token")
async def introspect_token_from_header(
    authorization: str = Header(None),
) -> JSONResponse:
    """
    Validate token from Authorization header and get user information.

    Forwards introspection request to auth service which will:
    - Validate the token from Authorization header
    - Return user information if valid
    - Check token expiration

    Args:
        authorization: JWT token from Authorization header

    Returns:
        JSONResponse with user information
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
        )

    # Forward to auth service
    headers = {"authorization": authorization}
    status_code, response_data = _forward_to_auth_service(
        method="GET",
        endpoint="/introspect-token",
        headers=headers,
    )

    return JSONResponse(status_code=status_code, content=response_data)


@auth_proxy_router.post("/update-user-status/{email_id}")
async def update_user_status(
    email_id: str,
    request: Request,
    authorization: str = Header(None),
) -> JSONResponse:
    """
    Update user status (e.g., active, inactive, banned).

    Forwards status update request to auth service which will:
    - Validate admin permissions
    - Update user status in database
    - Clear user cache

    Args:
        email_id: User's email ID
        request: FastAPI request object (expects {"status": "..."})
        authorization: JWT token from Authorization header

    Returns:
        JSONResponse with update result
    """
    # Get request body
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body must contain status",
        )

    # Forward to auth service
    headers = {}
    if authorization:
        headers["authorization"] = authorization

    status_code, response_data = _forward_to_auth_service(
        method="POST",
        endpoint=f"/update-user-status/{email_id}",
        headers=headers,
        json_data=body,
    )

    return JSONResponse(status_code=status_code, content=response_data)


@auth_proxy_router.post("/invalidate-user-cache")
async def invalidate_user_cache(
    request: Request,
    authorization: str = Header(None),
) -> JSONResponse:
    """
    Invalidate user cache in auth service.

    Forwards cache invalidation request to auth service which will:
    - Clear cached user data
    - Force fresh token validation on next request
    - Optionally clear specific user or all users

    Args:
        request: FastAPI request object (may contain {"userId": "..."})
        authorization: JWT token from Authorization header

    Returns:
        JSONResponse with invalidation result
    """
    # Get request body
    try:
        body = await request.json()
    except Exception:
        body = {}

    # Forward to auth service
    headers = {}
    if authorization:
        headers["authorization"] = authorization

    status_code, response_data = _forward_to_auth_service(
        method="POST",
        endpoint="/invalidate-user-cache",
        headers=headers,
        json_data=body,
    )

    return JSONResponse(status_code=status_code, content=response_data)
