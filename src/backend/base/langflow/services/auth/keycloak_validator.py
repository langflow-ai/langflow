"""
Keycloak Token Validator Service

This service validates JWT tokens with Keycloak's introspection endpoint.
Ported from genesis-bff KeycloakAuthService to replicate BFF functionality.
"""

import os
from typing import Any

import httpx
from loguru import logger


class TokenValidationResult:
    """Result of token validation from Keycloak."""

    def __init__(self, data: dict[str, Any]):
        self.active: bool = data.get("active", False)
        self.email: str | None = data.get("email")
        self.type: str | None = None
        self.sub: str = data.get("sub", "")
        self.username: str = data.get("username", "")
        self.given_name: str = data.get("given_name", "")
        self.family_name: str = data.get("family_name", "")
        self.realm_access: dict[str, list[str]] = data.get("realm_access", {})
        self.resource_access: dict[str, dict[str, list[str]]] = data.get("resource_access", {})
        self.raw_data: dict[str, Any] = data

        # Determine account type
        if self.username and "service-account" in self.username:
            self.type = "service-account"
        else:
            self.type = "user-account"


class KeycloakValidator:
    """
    Validates tokens with Keycloak introspection endpoint.

    Uses client credentials (client_id + client_secret) to call Keycloak's
    token introspection endpoint, which verifies if a token is active and
    returns user information.

    This replicates the functionality from genesis-bff's KeycloakAuthService.
    """

    def __init__(self):
        """Initialize the Keycloak validator with configuration from environment."""
        self.realm_base_url = os.getenv("KEYCLOAK_REALM_BASE_URL")
        self.realm_name = os.getenv("KEYCLOAK_REALM_NAME")
        self.client_id = os.getenv("KEYCLOAK_CLIENT_ID")
        self.client_secret = os.getenv("KEYCLOAK_CLIENT_SECRET")

        # Validate required configuration
        if not all([self.realm_base_url, self.realm_name, self.client_id, self.client_secret]):
            msg = (
                "Keycloak configuration incomplete. Required environment variables: "
                "KEYCLOAK_REALM_BASE_URL, KEYCLOAK_REALM_NAME, KEYCLOAK_CLIENT_ID, KEYCLOAK_CLIENT_SECRET"
            )
            raise ValueError(msg)

        # Build introspection endpoint URL
        # Use direct string formatting instead of urljoin to avoid path replacement issues
        base_url = self.realm_base_url.rstrip('/')  # Remove trailing slash if present
        self.introspection_url = f"{base_url}/realms/{self.realm_name}/protocol/openid-connect/token/introspect"

        logger.info(
            f"KeycloakValidator initialized with realm: {self.realm_name}, "
            f"client_id: {self.client_id}, "
            f"introspection_url: {self.introspection_url}"
        )

    async def validate_token(self, token: str) -> TokenValidationResult:
        """
        Validate a token with Keycloak introspection endpoint.

        Args:
            token: The access token to validate (with or without 'Bearer ' prefix)

        Returns:
            TokenValidationResult containing user information if token is valid

        Raises:
            ValueError: If token is inactive or invalid
            httpx.HTTPError: If communication with Keycloak fails
        """
        # Remove 'Bearer ' prefix if present
        clean_token = token.replace("Bearer ", "").strip() if token.startswith("Bearer ") else token

        # Prepare form data for introspection request
        # Keycloak expects application/x-www-form-urlencoded format
        form_data = {"token": clean_token, "client_id": self.client_id, "client_secret": self.client_secret}

        try:
            # Call Keycloak introspection endpoint
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.introspection_url,
                    data=form_data,  # httpx automatically encodes as application/x-www-form-urlencoded
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response.raise_for_status()

            data = response.json()

            # Check if token is active
            if not data.get("active", False):
                logger.warning(
                    f"Token validation failed: Token is inactive. "
                    f"Username: {data.get('username')}, Active: {data.get('active')}"
                )
                msg = "Token is inactive or invalid"
                raise ValueError(msg)

            # Token is valid
            result = TokenValidationResult(data)
            logger.info(
                f"Token validated successfully. "
                f"Username: {result.username}, Type: {result.type}, Email: {result.email}"
            )

            return result

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Keycloak introspection HTTP error: {e.response.status_code} - "
                f"{e.response.text if hasattr(e.response, 'text') else 'No response text'}"
            )
            msg = f"Token validation failed: HTTP {e.response.status_code}"
            raise ValueError(msg) from e
        except httpx.RequestError as e:
            logger.error(f"Keycloak introspection request error: {e}")
            msg = "Token validation failed: Unable to reach Keycloak"
            raise ValueError(msg) from e
        except Exception as e:
            logger.error(f"Unexpected error during token validation: {e}")
            raise

    def get_user_details(self, token_data: TokenValidationResult) -> dict[str, Any]:
        """
        Extract user details from validated token result.

        Args:
            token_data: The validated token result from validate_token()

        Returns:
            Dictionary containing user information
        """
        return {
            "id": token_data.sub,
            "email": token_data.email,
            "username": token_data.username,
            "firstName": token_data.given_name,
            "lastName": token_data.family_name,
            "type": token_data.type,
            "roles": {
                "realm": token_data.realm_access.get("roles", []),
                "resources": token_data.resource_access,
            },
        }
