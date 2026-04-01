from __future__ import annotations

from typing import Any

import httpx
import jwt
from jwt import PyJWKClient, PyJWKClientError


class KeycloakClient:
    """Handles OIDC token exchange and JWT verification against Keycloak."""

    def __init__(self, token_endpoint: str, jwks_uri: str, client_id: str, client_secret: str):
        self._token_endpoint = token_endpoint
        self._jwks_uri = jwks_uri
        self._client_id = client_id
        self._client_secret = client_secret
        self._jwks_client = PyJWKClient(jwks_uri)

    async def exchange_code(self, code: str, redirect_uri: str, code_verifier: str | None = None) -> dict[str, Any]:
        """Exchange authorization code for tokens. Returns the token response dict."""
        post_data: dict[str, str] = {
            "grant_type": "authorization_code",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        if code_verifier is not None:
            post_data["code_verifier"] = code_verifier
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self._token_endpoint,
                data=post_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15,
            )
        if resp.status_code != 200:
            raise ValueError(f"Keycloak token exchange failed ({resp.status_code}): {resp.text}")
        return resp.json()

    def verify_and_decode(self, token: str) -> dict[str, Any]:
        """Verify the Keycloak JWT signature using JWKS and return the payload."""
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
        except PyJWKClientError as exc:
            raise ValueError(f"Failed to fetch signing key: {exc}") from exc

        payload: dict[str, Any] = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "RS512", "ES256", "ES384", "ES512"],
            options={"verify_exp": True, "verify_aud": False},
        )
        return payload

    def extract_groups(self, payload: dict[str, Any], claim: str) -> list[str]:
        """Extract group list from a JWT payload using the configured claim name.

        Supports simple top-level claims (e.g. "groups") that contain a list of strings.
        """
        value = payload.get(claim)
        if isinstance(value, list):
            return [str(g) for g in value]
        return []
