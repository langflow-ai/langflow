"""Shared Microsoft Graph helpers for OneDrive + SharePoint connectors.

Both connectors hit ``graph.microsoft.com`` and both refresh tokens
against ``login.microsoftonline.com/{tenant}/oauth2/v2.0/token``.
Putting the shared bits here keeps the concrete sources small.

Refresh-token flow notes:

* ``tenant_id_variable`` — default ``MICROSOFT_OAUTH_TENANT_ID``;
  set to ``"common"`` for multi-tenant apps, or a specific tenant
  id. MSAL CLI output includes this value in the cache.
* ``refresh_token_variable`` — default
  ``MICROSOFT_OAUTH_REFRESH_TOKEN``. Microsoft rotates refresh
  tokens on every refresh, so users will need to update the stored
  variable periodically. A follow-up polish phase can add the
  "refresh the refresh token" write-back path.
* ``scope`` on the refresh body must match the original grant —
  we include ``offline_access`` + the provider scope so the cached
  refresh_token keeps working across calls.
"""

from __future__ import annotations

from typing import Any

from lfx.base.knowledge_bases.ingestion_sources.connector_base import (
    HTTP_STATUS_CLIENT_ERROR_FLOOR,
    MIN_EXPIRES_IN_SECONDS,
    OAuthConnectorBase,
)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

DEFAULT_TENANT_ID_VARIABLE = "MICROSOFT_OAUTH_TENANT_ID"
DEFAULT_SCOPE = "offline_access Files.Read.All Sites.Read.All"


class MicrosoftGraphSource(OAuthConnectorBase):
    """Shared base for OneDrive + SharePoint ingestion sources.

    Subclasses set ``source_type`` / ``display_name`` / ``icon`` and
    implement ``list_items`` + ``fetch_content`` on top of a pre-
    authed ``httpx.AsyncClient`` returned by ``authed_client``.
    """

    default_client_id_variable = "MICROSOFT_OAUTH_CLIENT_ID"
    default_client_secret_variable = "MICROSOFT_OAUTH_CLIENT_SECRET"  # noqa: S105  # pragma: allowlist secret
    default_refresh_token_variable = "MICROSOFT_OAUTH_REFRESH_TOKEN"  # noqa: S105  # pragma: allowlist secret

    requires_credentials = True

    @property
    def token_endpoint(self) -> str:  # type: ignore[override] — override class attr with property
        """Tenant-aware token endpoint.

        Microsoft's token endpoint embeds the tenant in the path, so
        we can't use a class-level constant like Google does. The
        ``common`` endpoint works for multi-tenant apps; specific
        tenants work for single-tenant apps.
        """
        tenant_variable = self.source_config.get("tenant_id_variable") or DEFAULT_TENANT_ID_VARIABLE
        # Sync path — resolve_secret is async, so we fall through to
        # a sync-safe variant below. The actual token request fetches
        # tenant asynchronously via ``_token_request_body``.
        tenant = self.source_config.get("tenant") or "common"
        # Allow direct ``tenant`` override in source_config; otherwise
        # the token request body resolves the variable at refresh time.
        _ = tenant_variable  # referenced in body resolution
        return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"

    async def _token_request_body(self) -> dict[str, str]:
        client_id = await self.resolve_required_secret(self._client_id_variable())
        client_secret = await self.resolve_required_secret(self._client_secret_variable())
        refresh_token = await self.resolve_required_secret(self._refresh_token_variable())
        tenant_variable = self.source_config.get("tenant_id_variable") or DEFAULT_TENANT_ID_VARIABLE
        tenant = (await self.resolve_secret(tenant_variable)) or "common"
        # Re-derive endpoint so the tenant variable lookup is honored
        # when the property isn't aware of it yet. ``token_endpoint``
        # is also mutated so ``_refresh_access_token`` POSTs to the
        # right URL.
        self._resolved_token_endpoint = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
        scope = self.source_config.get("scope") or DEFAULT_SCOPE
        return {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "scope": scope,
        }

    async def _refresh_access_token(self) -> str:  # type: ignore[override]
        """Override to use the tenant-resolved endpoint."""
        import httpx

        body = await self._token_request_body()
        endpoint = getattr(self, "_resolved_token_endpoint", None) or self.token_endpoint
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(endpoint, data=body)
        except httpx.HTTPError as exc:
            msg = f"OAuth token refresh against {endpoint} failed: {exc}"
            raise ValueError(msg) from exc

        if response.status_code >= HTTP_STATUS_CLIENT_ERROR_FLOOR:
            msg = (
                f"OAuth token refresh failed with {response.status_code}: "
                f"{response.text[:200]}. Verify refresh token + client credentials + tenant."
            )
            raise ValueError(msg)

        payload = response.json()
        access_token = payload.get("access_token")
        if not access_token:
            msg = f"Token endpoint did not return an access_token: {payload}"
            raise ValueError(msg)

        expires_in = payload.get("expires_in")
        if isinstance(expires_in, (int, float)) and expires_in > MIN_EXPIRES_IN_SECONDS:
            self.token_ttl_seconds = int(expires_in) - 60

        return str(access_token)

    async def authed_client(self):
        """Return an httpx client with the Bearer header prebaked."""
        import httpx

        token = await self.get_access_token()
        return httpx.AsyncClient(
            timeout=60.0,
            base_url=GRAPH_BASE_URL,
            headers={"Authorization": f"Bearer {token}"},
        )

    async def validate_config(self) -> None:
        # Every MS Graph connector needs the full OAuth triple.
        await self.resolve_required_secret(self._client_id_variable())
        await self.resolve_required_secret(self._client_secret_variable())
        await self.resolve_required_secret(self._refresh_token_variable())

    def describe(self) -> dict[str, Any]:
        base = super().describe()
        base["config"].update(
            {
                "tenant_id_variable": self.source_config.get("tenant_id_variable") or DEFAULT_TENANT_ID_VARIABLE,
                "scope": self.source_config.get("scope") or DEFAULT_SCOPE,
            }
        )
        return base
