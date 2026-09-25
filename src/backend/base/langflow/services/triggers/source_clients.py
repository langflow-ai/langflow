"""Fixed-origin OAuth clients used by Microsoft and Google trigger sources.

Provider continuation URLs are untrusted response data. They are accepted only
on the API origin that issued them, so a forged delta link cannot send an
owner's access token to another host.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

import httpx
from lfx.integrations.models import ConnectionRef, ConnectionResolutionRequest, CredentialLease

from langflow.services.database.models.connection.model import Connection
from langflow.services.deps import get_connection_resolver_service
from langflow.services.triggers.ownership import is_owned_by
from langflow.services.triggers.principal import trigger_execution_principal

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.trigger.model import Trigger

GRAPH_ORIGIN = "https://graph.microsoft.com"
GOOGLE_CALENDAR_ORIGIN = "https://www.googleapis.com"
GOOGLE_DRIVE_ORIGIN = "https://www.googleapis.com"
GOOGLE_GMAIL_ORIGIN = "https://gmail.googleapis.com"


async def source_lease(session: AsyncSession, trigger: Trigger, *, family: str) -> CredentialLease:
    """Resolve only a connection owned by this trigger's flow owner."""
    from langflow.services.triggers.source_arming import SourceArming, check_ready

    connection = await session.get(Connection, trigger.connection_id) if trigger.connection_id else None
    if connection is None or not is_owned_by(connection, trigger.user_id):
        msg = "A source trigger requires its owner's connection."
        raise ValueError(msg)
    if not connection.allow_non_interactive:
        msg = "Allow background runs on the source connection before enabling this trigger."
        raise ValueError(msg)
    await check_ready(
        session,
        kind=trigger.kind,
        arming=SourceArming(connection_id=connection.id, mechanism_id=(trigger.config or {}).get("mechanism_id") or ""),
        config=trigger.config,
    )
    request = ConnectionResolutionRequest(
        ref=ConnectionRef(provider=connection.provider_key, name=connection.name),
        principal=trigger_execution_principal(trigger, family=family),
        required_scopes=frozenset(),
    )
    return CredentialLease(get_connection_resolver_service(), request)


class SourceHTTP:
    """A small, origin-pinned bearer-token transport for source APIs."""

    def __init__(
        self,
        lease: CredentialLease,
        *,
        origin: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._lease = lease
        self._origin = httpx.URL(origin)
        self._client = httpx.AsyncClient(timeout=20, follow_redirects=False, transport=transport)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self._client.aclose()

    def _target(self, path: str) -> str:
        target = httpx.URL(path)
        if not target.is_absolute_url:
            target = self._origin.join(path.lstrip("/"))
        if (
            target.scheme != "https"
            or target.host != self._origin.host
            or target.port != self._origin.port
            or target.userinfo
            or target.fragment
        ):
            msg = "Provider continuation URL left its API origin."
            raise ValueError(msg)
        return str(target)

    async def request(self, method: str, path: str, *, params: dict[str, Any] | None = None, body: Any = None) -> dict:
        target = self._target(path)
        token = await self._lease.get_token()
        response = await self._client.request(
            method, target, params=params, json=body, headers={"Authorization": f"Bearer {token}"}
        )
        if response.status_code == httpx.codes.UNAUTHORIZED:
            from lfx.integrations.errors import AuthExpiredError

            refreshed = await self._lease.get_token_after_auth_error(
                AuthExpiredError(provider=self._lease.ref.provider), rejected_token=token
            )
            response = await self._client.request(
                method, target, params=params, json=body, headers={"Authorization": f"Bearer {refreshed}"}
            )
        quota_denied = False
        if response.status_code == httpx.codes.FORBIDDEN:
            try:
                errors = response.json().get("error", {}).get("errors", [])
                quota_denied = any(
                    isinstance(error, dict)
                    and error.get("reason") in {"rateLimitExceeded", "userRateLimitExceeded", "quotaExceeded"}
                    for error in errors
                )
            except (TypeError, ValueError, AttributeError):
                quota_denied = False
        if response.status_code == httpx.codes.TOO_MANY_REQUESTS or quota_denied:
            from lfx.integrations.errors import RateLimitedError

            try:
                retry_after = float(response.headers.get("Retry-After", ""))
            except ValueError:
                retry_after = None
            raise RateLimitedError(provider=self._lease.ref.provider, retry_after=retry_after)
        response.raise_for_status()
        if not response.content:
            return {}
        payload = response.json()
        if not isinstance(payload, dict):
            msg = "Provider returned a non-object response."
            raise TypeError(msg)
        return payload
