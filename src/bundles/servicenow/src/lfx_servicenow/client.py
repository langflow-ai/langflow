"""Origin-bound bearer transport that never exposes provider error bodies."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
from lfx.integrations.errors import (
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    InvalidRequestError,
    ProviderUnavailableError,
    RateLimitedError,
    ResourceNotFoundError,
    ScopeMissingError,
)

from lfx_servicenow.schema import PROVIDER, READ_FIELDS, READ_SCOPE, WRITE_SCOPE, origin, record_id, table

if TYPE_CHECKING:
    from lfx.integrations.models import CredentialLease

_TABLE_PATH_PARTS = 6
_RECORD_PATH_PARTS = 7


class ServiceNowClient:
    def __init__(self, lease: CredentialLease, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.lease = lease
        self.origin = origin()
        self.http = httpx.AsyncClient(timeout=20, follow_redirects=False, transport=transport)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        await self.http.aclose()

    async def request(self, method: str, path: str, *, params: dict | None = None, body: dict | None = None) -> dict:
        parts = path.split("/")
        if (
            method not in {"GET", "POST", "PATCH"}
            or len(parts) not in {6, 7}
            or parts[:5] != ["", "api", "now", "v1", "table"]
        ):
            msg = "Unsupported ServiceNow API path."
            raise InvalidRequestError(msg, provider=PROVIDER)
        table(parts[5])
        if len(parts) == _RECORD_PATH_PARTS:
            record_id(parts[6])
        if (method == "POST" and len(parts) != _TABLE_PATH_PARTS) or (
            method == "PATCH" and len(parts) != _RECORD_PATH_PARTS
        ):
            msg = "Unsupported ServiceNow API operation."
            raise InvalidRequestError(msg, provider=PROVIDER)
        required = READ_SCOPE if method == "GET" else WRITE_SCOPE
        for attempt in range(2):
            credential = await self.lease.get_credential()
            if (
                credential.provider != PROVIDER
                or credential.identity != "user_delegated"
                or credential.account is None
                or credential.account.tenant_id != self.origin
                or credential.token_type.lower() != "bearer"
            ):
                raise ConnectionNotAuthorizedError(provider=PROVIDER)
            if not credential.scopes_verified or required not in credential.granted_scopes:
                raise ScopeMissingError(
                    frozenset({required}), provider=PROVIDER, scopes_verified=credential.scopes_verified
                )
            token = credential.access_token.get_secret_value()
            try:
                response = await self.http.request(
                    method,
                    self.origin + path,
                    params={
                        "sysparm_fields": ",".join(READ_FIELDS),
                        "sysparm_display_value": "false",
                        "sysparm_exclude_reference_link": "true",
                        **(params or {}),
                    },
                    json=body,
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                )
            except httpx.HTTPError:
                raise ProviderUnavailableError(provider=PROVIDER) from None
            if response.status_code == httpx.codes.UNAUTHORIZED and attempt == 0:
                await self.lease.get_token_after_auth_error(AuthExpiredError(provider=PROVIDER), rejected_token=token)
                continue
            if response.status_code == httpx.codes.UNAUTHORIZED:
                raise AuthExpiredError(provider=PROVIDER)
            if response.status_code == httpx.codes.FORBIDDEN:
                raise ConnectionNotAuthorizedError(provider=PROVIDER, reason="provider")
            if response.status_code == httpx.codes.NOT_FOUND:
                raise ResourceNotFoundError(provider=PROVIDER)
            if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
                try:
                    delay = min(3600.0, max(0.0, float(response.headers.get("Retry-After", ""))))
                except ValueError:
                    delay = None
                raise RateLimitedError(provider=PROVIDER, retry_after=delay)
            if response.status_code in {400, 422}:
                msg = "ServiceNow rejected the approved-table request."
                raise InvalidRequestError(msg, provider=PROVIDER)
            if response.status_code not in {200, 201}:
                raise ProviderUnavailableError(provider=PROVIDER)
            try:
                payload = response.json()
            except ValueError:
                raise ProviderUnavailableError(provider=PROVIDER) from None
            if not isinstance(payload, dict) or "result" not in payload:
                raise ProviderUnavailableError(provider=PROVIDER)
            count = response.headers.get("X-Total-Count")
            total = int(count) if count is not None and count.isdigit() else None
            return {"result": payload["result"], "total_count": total}
        raise AuthExpiredError(provider=PROVIDER)
