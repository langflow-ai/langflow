"""Custom authentication middleware for Langflow service."""

import asyncio
import os
from functools import partial
from typing import Any, Dict

import requests
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


class LangflowUser:
    """User object compatible with Langflow's requirements."""

    def __init__(
        self,
        genesis_user_id: str,
        client_id: str,
        access_token: str,
        user_data: Dict[str, Any],
    ) -> None:
        self.genesis_user_id = genesis_user_id
        self.client_id = client_id
        self.access_token = access_token
        self.username = user_data.get("username", f"genesis_user_{genesis_user_id}")
        self.email = user_data.get("email", "")
        self.is_active = user_data.get("is_active", True)
        self.is_superuser = user_data.get("is_admin", False)
        # Store original data for compatibility
        self._user_data = user_data

    def dict(self) -> Dict[str, Any]:
        """Return user data as dictionary for compatibility."""
        return {
            "id": self.genesis_user_id,
            "username": self.username,
            "email": self.email,
            "is_active": self.is_active,
            "is_superuser": self.is_superuser,
        }


class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication middleware adapted for Langflow."""

    def __init__(self, app) -> None:
        super().__init__(app)
        # Langflow-specific public routes
        self.public_routes = [
            "/health_check",
            "/health",
            "/api/v1/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/auto_login",  # Langflow's auto-login if needed
            # Add other public endpoints as needed
        ]
        self.client_id = os.getenv("GENESIS_CLIENT_ID")
        auth_base_url = os.getenv("GENESIS_SERVICE_AUTH_URL")

        if not auth_base_url:
            raise ValueError("GENESIS_SERVICE_AUTH_URL environment variable is not set")
        if not self.client_id:
            raise ValueError("GENESIS_CLIENT_ID environment variable is not set")

        self.auth_service_url = f"{auth_base_url}/auth/api/v1"

    def _make_request(self, access_token: str) -> Dict[str, Any]:
        """Make synchronous request to validate token."""
        try:
            response = requests.get(
                f"{self.auth_service_url}/validate/token",
                headers={"Authorization": access_token},
                timeout=10,
            )

            # Get the response content
            response_data = response.json()

            # If the request was not successful, raise an exception with the error details
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=response_data.get("message", "Authentication failed"),
                )

            return response_data["data"]

        except requests.exceptions.RequestException as e:
            # Handle network/timeout errors - log but don't crash the whole service
            print(f"⚠️ Genesis auth service unavailable: {e}")
            # In development, you might want to allow access when auth service is down
            # In production, this should be strict
            if os.getenv("GENESIS_AUTH_FAIL_OPEN", "false").lower() == "true":
                print("ℹ️ Allowing access due to GENESIS_AUTH_FAIL_OPEN=true")
                return {"id": "dev-user", "username": "dev-user", "email": "dev@genesis.local", "is_active": True}
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="User service unavailable",
                )
        except ValueError:
            # Handle JSON decode errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid response from authentication service",
            )

    async def _validate_user(self, access_token: str) -> Dict[str, Any]:
        """Validate the access token with the user management service."""
        try:
            # Run the synchronous request in a thread pool
            loop = asyncio.get_running_loop()
            user_data = await loop.run_in_executor(
                None, partial(self._make_request, access_token)
            )
            return user_data

        except HTTPException:
            # Re-raise HTTP exceptions as they contain the correct status code
            raise
        except Exception as e:
            # Handle any unexpected errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
            )

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Main middleware dispatch method."""
        try:
            # Allow OPTIONS requests for CORS preflight
            if request.method == "OPTIONS":
                return await call_next(request)

            # Check if route is public
            if any(route in request.url.path for route in self.public_routes):
                return await call_next(request)

            # Get access token
            access_token = request.headers.get("authorization")
            if not access_token:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"message": "Authorization header missing"},
                )

            try:
                # Validate token and get user data
                user_data = await self._validate_user(access_token)

                # Add user info to request state
                user = LangflowUser(
                    genesis_user_id=user_data["id"],
                    client_id=self.client_id,
                    access_token=access_token,
                    user_data=user_data.get("user_data", user_data),
                )
                request.state.user = user

                # Proceed with the request
                return await call_next(request)

            except HTTPException as auth_error:
                # Return the exact error from the authentication service
                return JSONResponse(
                    status_code=auth_error.status_code,
                    content={"message": auth_error.detail},
                )

        except Exception as e:
            # Handle any unexpected errors
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"message": str(e)},
            )
