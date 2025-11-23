"""
Auth Proxy Router - Forwards authentication requests to genesis-service-auth.

This module provides proxy endpoints that forward authentication-related requests
from the frontend to the genesis-service-auth service (port 3005), maintaining
feature parity with the genesis-bff architecture while eliminating the proxy layer.
"""

import os
from typing import Any

import requests
from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel


class RefreshTokenRequest(BaseModel):
    """Request body for refresh token endpoint."""
    refreshToken: str


class IntrospectTokenRequest(BaseModel):
    """Request body for introspect token endpoint."""
    accessToken: str


class UpdateUserStatusRequest(BaseModel):
    """Request body for update user status endpoint."""
    status: str | None = None


# Create router with /auth prefix
auth_proxy_router = APIRouter(prefix="/auth", tags=["auth-proxy"])

def _get_auth_service_url() -> str:
    """Get auth service URL from environment."""
    auth_url = os.getenv("GENESIS_SERVICE_AUTH_URL")
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
    body: RefreshTokenRequest,
) -> JSONResponse:
    """
    Refresh access token using refresh token.

    Forwards refresh token request to auth service which will:
    - Validate the refresh token
    - Generate new access and refresh tokens
    - Update user cache

    Args:
        email_id: User's email ID
        body: Request body containing refreshToken

    Returns:
        JSONResponse with new tokens
    """
    # Forward to auth service
    status_code, response_data = _forward_to_auth_service(
        method="POST",
        endpoint=f"/auth/api/v1/auth/refresh-token/{email_id}",
        json_data=body.model_dump(),
    )

    return JSONResponse(status_code=status_code, content=response_data)


@auth_proxy_router.post("/introspect-token/{email_id}")
async def introspect_token_by_email(
    email_id: str,
    body: IntrospectTokenRequest,
) -> JSONResponse:
    """
    Validate token and get user information by email ID.

    Forwards introspection request to auth service which will:
    - Validate the provided token
    - Return user information if valid
    - Check token expiration

    Args:
        email_id: User's email ID
        body: Request body containing accessToken

    Returns:
        JSONResponse with user information
    """
    # Forward to auth service
    status_code, response_data = _forward_to_auth_service(
        method="POST",
        endpoint=f"/auth/api/v1/auth/introspect-token/{email_id}",
        json_data=body.model_dump(),
    )

    return JSONResponse(status_code=status_code, content=response_data)


@auth_proxy_router.post("/update-user-status/{email_id}")
async def update_user_status(
    email_id: str,
    body: UpdateUserStatusRequest,
) -> JSONResponse:
    """
    Update user status (e.g., active, inactive, banned).

    Forwards status update request to auth service which will:
    - Validate admin permissions
    - Update user status in database
    - Clear user cache

    Args:
        email_id: User's email ID
        body: Request body containing status

    Returns:
        JSONResponse with update result
    """
    # Forward to auth service
    status_code, response_data = _forward_to_auth_service(
        method="POST",
        endpoint=f"/auth/api/v1/auth/update-user-status/{email_id}",
        json_data=body.model_dump(exclude_none=True),
    )

    return JSONResponse(status_code=status_code, content=response_data)


@auth_proxy_router.get("/validate-token")
async def validate_token(
    authorization: str = Header(...),
) -> JSONResponse:
    """
    Validate token from Authorization header.

    Forwards validation request to auth service which will:
    - Validate the token from Authorization header
    - Return validation result

    Args:
        authorization: JWT token from Authorization header (required)

    Returns:
        JSONResponse with validation result
    """
    headers = {"authorization": authorization}

    status_code, response_data = _forward_to_auth_service(
        method="GET",
        endpoint="/auth/api/v1/auth/validate-token",
        headers=headers,
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


@auth_proxy_router.get("/user/email/{email_id}")
async def find_user_by_email(
    email_id: str,
    artifactId: str = Query(None, description="Artifact ID (optional)"),
    artifactType: str = Query(None, description="Artifact Type (optional)"),
    authorization: str = Header(None),
) -> JSONResponse:
    """
    Find user by email ID with optional artifact context.

    Forwards user lookup request to auth service which will:
    - Look up user by email
    - Return user information with artifact context (if provided)

    Args:
        email_id: User's email ID
        artifactId: Optional artifact ID for context
        artifactType: Optional type of artifact
        authorization: JWT token from Authorization header

    Returns:
        JSONResponse with user information
    """
    # Forward to auth service with query parameters
    headers = {}
    if authorization:
        headers["authorization"] = authorization

    # Build query string with optional parameters
    query_params = []
    if artifactId:
        query_params.append(f"artifactId={artifactId}")
    if artifactType:
        query_params.append(f"artifactType={artifactType}")
# auth/api/v1/user/email
    endpoint = f"/auth/api/v1/user/email/{email_id}"
    if query_params:
        endpoint += "?" + "&".join(query_params)

    status_code, response_data = _forward_to_auth_service(
        method="GET",
        endpoint=endpoint,
        headers=headers,
    )

    return JSONResponse(status_code=status_code, content=response_data)
