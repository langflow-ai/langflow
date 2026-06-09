"""Shared base for cloud-connector ingestion sources.

Cloud connectors (S3, Google Drive, OneDrive, SharePoint, IBM COS)
differ from ``FileUploadSource`` / ``FolderSource`` in two ways:

1. They need **credentials** — resolved from Langflow's
   ``variable_service`` by variable-name reference, not embedded in
   the request payload. Storing variable *names* in ``source_config``
   (instead of the secrets themselves) means the ``ingestion_run``
   row can safely echo the config back to the UI without leaking
   material.

2. They perform **network I/O** to list + fetch items, so per-item
   failures are more common. The generic per-item fetch error-handling
   in ``perform_ingestion`` already records those as FAILED and moves
   on — connectors don't need to reinvent that.

This base class gives connectors a single ``resolve_secret`` helper so
every provider talks to the variable service the same way. No shared
OAuth plumbing here: Phase 3B+ adds a dedicated ``OAuthConnectorBase``
subclass with token-refresh logic once the first OAuth provider lands.
"""

from __future__ import annotations

import os
from typing import Any
from uuid import UUID

from lfx.base.knowledge_bases.ingestion_sources.base import KBIngestionSource
from lfx.log.logger import logger

# HTTP-status threshold cloud-connector helpers treat as "request failed".
# Shared so every connector checks the same boundary.
HTTP_STATUS_CLIENT_ERROR_FLOOR = 400

# Below this, we treat a ``expires_in`` reply as bogus and fall back to
# our hard-coded default TTL rather than thrashing token refreshes.
MIN_EXPIRES_IN_SECONDS = 60


class KBConnectorSource(KBIngestionSource):
    """Base class for third-party / cloud ingestion sources."""

    requires_credentials = True

    async def resolve_secret(self, variable_name: str) -> str | None:
        """Return the value of a Langflow variable, or ``None`` if absent.

        Order of resolution:

        1. Langflow's ``variable_service`` scoped to ``self.user_id``.
        2. Process env var of the same name (fallback so desktop /
           single-user deployments can skip the UI step).

        Returns ``None`` when neither source has the value; callers
        decide whether that's fatal. Never raises — config validation
        is the place for hard credential-required errors.
        """
        if not variable_name:
            return None

        user_uuid = self._coerce_user_uuid()
        if user_uuid is not None:
            value = await self._lookup_variable(user_uuid, variable_name)
            if value:
                return value

        env_value = os.environ.get(variable_name)
        return env_value or None

    async def resolve_required_secret(self, variable_name: str) -> str:
        """Like ``resolve_secret`` but raises if missing.

        Use from ``validate_config`` to surface credential errors
        before a background job is spawned.
        """
        value = await self.resolve_secret(variable_name)
        if not value:
            msg = (
                f"Required credential variable {variable_name!r} is not "
                "configured. Set it via Langflow's variable settings or as "
                "an environment variable on the server."
            )
            raise ValueError(msg)
        return value

    def _coerce_user_uuid(self) -> UUID | None:
        """Turn ``self.user_id`` into a ``UUID`` when possible."""
        if self.user_id is None:
            return None
        if isinstance(self.user_id, UUID):
            return self.user_id
        try:
            return UUID(str(self.user_id))
        except (ValueError, TypeError, AttributeError):
            return None

    async def _lookup_variable(self, user_uuid: UUID, variable_name: str) -> str | None:
        """Look up ``variable_name`` through Langflow's variable service.

        Isolated so tests can patch a single seam. Wrapped in a broad
        try/except because the variable service can raise a handful of
        domain errors (missing variable, decryption failure, DB
        unavailable) and the caller treats all of them the same way —
        fall through to the env-var lookup.
        """
        try:
            from lfx.services.deps import get_variable_service, session_scope

            variable_service = get_variable_service()
            if variable_service is None:
                return None
            async with session_scope() as session:
                value = await variable_service.get_variable(
                    user_id=user_uuid,
                    name=variable_name,
                    field="",
                    session=session,
                )
                return str(value) if value else None
        except Exception as exc:  # noqa: BLE001 — any failure → fall back to env
            logger.debug("variable_service lookup for %s failed: %s", variable_name, exc)
            return None

    def describe(self) -> dict[str, Any]:
        """UI snapshot, redacting credential *values* from the config.

        Since connectors store credential *references* in
        ``source_config`` (e.g. ``{"access_key_variable":
        "AWS_ACCESS_KEY_ID"}``), the default describe already leaks
        only variable names. Subclasses can override if they carry
        additional secret-adjacent fields.
        """
        return super().describe()


class OAuthConnectorBase(KBConnectorSource):
    """Shared OAuth 2.0 refresh-token flow for cloud connectors.

    **Approach: bring-your-own-refresh-token.** Rather than build a
    full OAuth callback system (redirect URLs, CSRF-protected state,
    per-user token storage schema), we trade the setup burden:

    * User goes through the OAuth consent flow *once* externally
      (via ``gcloud auth`` / Azure CLI / Google OAuth Playground /
      Microsoft MSAL sample) to obtain a long-lived refresh token.
    * User stores the refresh token plus OAuth client id/secret as
      Langflow variables.
    * The connector mints a short-lived access token on every list /
      fetch call by POSTing the refresh token back to the provider.

    This keeps the Phase 3B/C surface identical to S3: all three
    connectors share the ``KBConnectorSource`` variable-resolution
    pattern. A dedicated "Connect with Google / Microsoft" UX can
    land in a follow-up phase without changing the connector
    implementations — it just populates the same variables that
    power this flow today.

    Subclasses set ``token_endpoint`` and optionally override
    ``_token_request_body`` to tune provider-specific quirks.
    Access tokens are cached in memory for ``token_ttl_seconds`` to
    avoid refreshing on every API call within a single ingestion
    run.
    """

    # Subclass must override.
    token_endpoint: str = ""
    # Default cache: most providers issue 1-hour tokens; refresh 5
    # minutes before expiry to give clock skew a margin. This is the
    # *class-level default* only — each instance stores its own
    # ``token_ttl_seconds`` on ``self`` so a provider-reported
    # ``expires_in`` tune-up never mutates shared state.
    default_token_ttl_seconds: int = 55 * 60

    def __init__(self, user_id: UUID | str | None, source_config: dict[str, Any]) -> None:
        super().__init__(user_id=user_id, source_config=source_config)
        self._cached_access_token: str | None = None
        self._cached_token_expires_at: float = 0.0
        self.token_ttl_seconds: int = self.default_token_ttl_seconds

    async def get_access_token(self) -> str:
        """Return a currently-valid access token, refreshing if needed.

        Shared entry point for subclasses — don't hit the refresh
        endpoint yourself. Caches the token until it's within a 5-
        minute window of expiry so a run that performs N list+fetch
        calls makes only one refresh round-trip.
        """
        import time

        now = time.monotonic()
        if self._cached_access_token and now < self._cached_token_expires_at:
            return self._cached_access_token

        token = await self._refresh_access_token()
        self._cached_access_token = token
        self._cached_token_expires_at = now + self.token_ttl_seconds
        return token

    async def _refresh_access_token(self) -> str:
        """Exchange the refresh token for an access token via HTTP.

        Kept small and httpx-based on purpose — we don't need the full
        google-auth / msal SDKs just for a single POST, and avoiding
        those deps keeps Langflow's install footprint tight.
        """
        import httpx

        body = await self._token_request_body()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.token_endpoint, data=body)
        except httpx.HTTPError as exc:
            msg = f"OAuth token refresh against {self.token_endpoint} failed: {exc}"
            raise ValueError(msg) from exc

        if response.status_code >= HTTP_STATUS_CLIENT_ERROR_FLOOR:
            msg = (
                f"OAuth token refresh failed with {response.status_code}: "
                f"{response.text[:200]}. Verify your refresh token + client credentials."
            )
            raise ValueError(msg)

        payload = response.json()
        access_token = payload.get("access_token")
        if not access_token:
            msg = f"Token endpoint did not return an access_token: {payload}"
            raise ValueError(msg)

        # Use provider-reported expiry when available so the cache
        # matches reality rather than our 55-minute guess.
        expires_in = payload.get("expires_in")
        if isinstance(expires_in, (int, float)) and expires_in > MIN_EXPIRES_IN_SECONDS:
            # Subtract a 60-second safety margin.
            self.token_ttl_seconds = int(expires_in) - 60

        return str(access_token)

    async def _token_request_body(self) -> dict[str, str]:
        """Build the form body for the refresh POST.

        Default matches the OAuth 2.0 spec; subclasses override when
        their provider wants extra fields (scope, tenant, etc.).
        """
        client_id = await self.resolve_required_secret(self._client_id_variable())
        client_secret = await self.resolve_required_secret(self._client_secret_variable())
        refresh_token = await self.resolve_required_secret(self._refresh_token_variable())
        return {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }

    # --- variable-name conventions (subclass-overridable) ---------

    def _client_id_variable(self) -> str:
        return self.source_config.get("client_id_variable") or self.default_client_id_variable

    def _client_secret_variable(self) -> str:
        return self.source_config.get("client_secret_variable") or self.default_client_secret_variable

    def _refresh_token_variable(self) -> str:
        return self.source_config.get("refresh_token_variable") or self.default_refresh_token_variable

    # Subclasses override.
    default_client_id_variable: str = ""
    default_client_secret_variable: str = ""
    default_refresh_token_variable: str = ""

    def describe(self) -> dict[str, Any]:
        """Expose the resolved variable names alongside the base config.

        The OAuth triple is stored as *references* (variable names),
        so the describe payload is safe to show in the UI — it tells
        the user which variables this source reads without leaking
        any resolved value.
        """
        base = super().describe()
        base.setdefault("config", {})
        base["config"].setdefault("client_id_variable", self._client_id_variable())
        base["config"].setdefault("client_secret_variable", self._client_secret_variable())
        base["config"].setdefault("refresh_token_variable", self._refresh_token_variable())
        return base
