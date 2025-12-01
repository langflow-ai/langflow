"""Custom authentication middleware for Langflow service - Direct Keycloak Mode."""

import logging
from typing import Any

import jwt
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from langflow.services.auth.keycloak_validator import KeycloakValidator, TokenValidationResult
from langflow.services.cache.token_cache import get_token_cache

logger = logging.getLogger(__name__)


class LangflowUser:
    """User object compatible with Langflow's requirements."""

    def __init__(
        self,
        genesis_user_id: str,
        client_id: str,
        access_token: str,
        user_data: dict[str, Any],
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

        # Extract roles from user_data for permission checks
        # Roles come from KeycloakValidator.get_user_details() as:
        # {"realm": [...], "resources": {"client_name": {"roles": [...]}}}
        roles_data = user_data.get("roles", {})
        realm_roles = roles_data.get("realm", []) if isinstance(roles_data, dict) else []
        resource_roles = []
        if isinstance(roles_data, dict):
            for resource_data in roles_data.get("resources", {}).values():
                if isinstance(resource_data, dict):
                    resource_roles.extend(resource_data.get("roles", []))
        self.roles = realm_roles + resource_roles

    def dict(self) -> dict[str, Any]:
        """Return user data as dictionary for compatibility."""
        return {
            "id": self.genesis_user_id,
            "username": self.username,
            "email": self.email,
            "is_active": self.is_active,
            "is_superuser": self.is_superuser,
        }


class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication middleware with Keycloak token validation."""

    def __init__(self, app) -> None:
        super().__init__(app)

        # Check if Genesis auth is enabled
        import os
        from langflow.custom.genesis.integration import is_genesis_auth_enabled
        self.genesis_auth_enabled = is_genesis_auth_enabled()

        # Initialize Keycloak validator and cache
        self.keycloak_validator: KeycloakValidator | None = None
        self.token_cache = get_token_cache()

        if self.genesis_auth_enabled:
            try:
                self.keycloak_validator = KeycloakValidator()
                logger.info("AuthMiddleware: Direct Keycloak validation enabled")
            except ValueError as e:
                logger.warning(f"Keycloak validator initialization failed: {e}")
                logger.warning("Falling back to JWT decode without validation")
        else:
            logger.info("AuthMiddleware: Genesis auth disabled, delegating to Langflow auth")

        # Langflow-specific public routes
        # NOTE: Do NOT include API key endpoints here. They must require authentication
        # via Bearer token (Genesis JWT) or x-api-key to avoid 401 issues when JWT is valid.
        self.public_routes = [
            "/health_check",
            "/health",
            "/api/v1/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/auto_login",
            "/api/v1/config",
            "/api/v1/spec/",  # Allow spec endpoints to use Langflow auth
            # Add other public endpoints as needed
        ]

        # Auth endpoints that should be exempt from token validation
        # (from BFF's PrivateRouteMiddleware exempt routes)
        self.exempt_auth_routes = [
            "/api/v1/auth/refresh-token",
            "/api/v1/auth/introspect-token",
            "/api/v1/auth/get-token",
            "/api/v1/auth/logout",
            "/api/v1/auth/update-user-status",
            "/api/v1/auth/invalidate-user-cache",
        ]

        self.client_id = "genesis-backend"  # Direct backend mode

    async def _validate_token_with_keycloak(self, access_token: str) -> dict[str, Any]:
        """
        Validate token with Keycloak using cache-aside pattern.

        Args:
            access_token: The Bearer token to validate

        Returns:
            User data extracted from validated token

        Raises:
            HTTPException: If token validation fails
        """
        try:
            # Check cache first
            cached_result = await self.token_cache.get_token_validation(access_token)
            if cached_result:
                logger.info("[CACHE]: Token validation cache hit")
                return cached_result["userData"]

            # Cache miss - validate with Keycloak
            logger.info("[CACHE]: Token validation cache miss, calling Keycloak")

            if not self.keycloak_validator:
                raise ValueError("Keycloak validator not initialized")

            token_result = await self.keycloak_validator.validate_token(access_token)

            # Extract user data
            user_data = self.keycloak_validator.get_user_details(token_result)

            # Cache the result
            await self.token_cache.cache_token_validation(access_token, user_data)
            logger.info("[CACHE]: Token validation cached")

            return user_data

        except ValueError as e:
            logger.error(f"Token validation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error during token validation: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token validation error"
            ) from e

    def _extract_user_from_jwt(self, access_token: str) -> dict[str, Any]:
        """
        Extract user from JWT payload without validation.

        FALLBACK ONLY - Used when Keycloak validator is not available.
        Should not be used in production.
        """
        try:
            # Remove Bearer prefix if present
            token = access_token
            if token.startswith("Bearer "):
                token = token[7:]
            elif token.startswith("bearer "):
                token = token[7:]

            # Decode JWT without signature verification
            payload = jwt.decode(token, options={"verify_signature": False})

            # Extract user information from JWT claims
            user_id = payload.get("sub")
            if not user_id:
                raise ValueError("Missing 'sub' claim in JWT")

            return {
                "id": user_id,
                "username": payload.get("preferred_username", payload.get("email", f"user_{user_id}")),
                "email": payload.get("email", ""),
                "is_active": True,
                "is_admin": payload.get("is_admin", False),
                "firstName": payload.get("given_name", ""),
                "lastName": payload.get("family_name", ""),
                "type": "user-account",
            }
        except Exception as e:
            logger.error(f"Failed to extract user from JWT: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format"
            ) from e

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Main middleware dispatch method."""
        try:
            # Allow OPTIONS requests for CORS preflight
            if request.method == "OPTIONS":
                return await call_next(request)

            # If Genesis auth is disabled, delegate all authentication to Langflow
            if not self.genesis_auth_enabled:
                logger.debug("Genesis auth disabled, delegating all authentication to Langflow")
                return await call_next(request)

            # Check if route is public
            if any(route in request.url.path for route in self.public_routes):
                return await call_next(request)

            # Check if route is exempt from token validation (auth endpoints)
            if any(route in request.url.path for route in self.exempt_auth_routes):
                logger.debug(f"Auth endpoint detected ({request.url.path}), skipping token validation")
                return await call_next(request)

            # Check for authentication headers
            access_token = request.headers.get("authorization")
            api_key = request.headers.get("x-api-key")

            # If API key is provided, skip Genesis auth and let Langflow handle it
            if api_key and not access_token:
                logger.debug("API key detected, delegating to Langflow authentication")
                return await call_next(request)

            # If no authentication headers at all, let Langflow handle the error
            if not access_token and not api_key:
                logger.debug("No auth headers found, delegating to Langflow authentication")
                return await call_next(request)

            # Handle JWT Bearer tokens with Genesis authentication
            if access_token:
                try:
                    # Validate token with Keycloak (with caching)
                    if self.keycloak_validator:
                        user_data = await self._validate_token_with_keycloak(access_token)
                    else:
                        # Fallback to JWT decode without validation
                        logger.warning("Using fallback JWT decode without validation")
                        user_data = self._extract_user_from_jwt(access_token)

                    # Add user info to request state
                    user = LangflowUser(
                        genesis_user_id=user_data["id"],
                        client_id=self.client_id,
                        access_token=access_token,
                        user_data=user_data,
                    )
                    request.state.user = user

                    # Proceed with the request
                    return await call_next(request)

                except HTTPException as auth_error:
                    # If Keycloak validation fails, also try delegating to Langflow
                    # (might be Langflow's own JWT in some edge cases)
                    logger.debug(f"Genesis JWT auth failed: {auth_error.detail}, delegating to Langflow")
                    return await call_next(request)

        except (ValueError, RuntimeError, ConnectionError) as e:
            # Handle any unexpected errors
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"message": str(e)},
            )