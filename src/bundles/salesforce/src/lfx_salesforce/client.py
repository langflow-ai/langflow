"""Credential-bound Salesforce requests with a fixed operator-owned origin."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
from lfx.integrations.errors import (
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    IntegrationNetworkError,
    InvalidRequestError,
    ProviderUnavailableError,
    RateLimitedError,
    ResourceNotFoundError,
    ScopeMissingError,
)

from lfx_salesforce.schema import API_ROOT, invalid, origin

if TYPE_CHECKING:
    from lfx.integrations.models import CredentialLease


MAX_RESPONSE_BYTES = 8_000_000


class SalesforceClient:
    """Use one org and never follow credential-bearing redirects."""

    def __init__(self, lease: CredentialLease, *, transport: httpx.AsyncBaseTransport | None = None):
        self.lease = lease
        self.origin = origin()
        self.http = httpx.AsyncClient(transport=transport, timeout=30, follow_redirects=False, trust_env=False)

    async def aclose(self) -> None:
        await self.http.aclose()

    async def request(self, method: str, path: str, *, params: dict | None = None, json: dict | None = None) -> Any:
        if (
            not path.startswith(API_ROOT + "/")
            or ".." in path
            or "?" in path
            or "#" in path
            or "\\" in path
            or "%" in path
        ):
            msg = "Unsupported Salesforce API resource."
            raise invalid(msg)
        credential = await self.lease.get_credential()
        if (
            credential.provider != "salesforce"
            or credential.identity != "user_delegated"
            or credential.account is None
            or credential.account.tenant_id != self.origin
        ):
            raise ConnectionNotAuthorizedError(provider="salesforce", reason="provider")
        if not credential.scopes_verified or "api" not in credential.granted_scopes:
            raise ScopeMissingError(
                frozenset({"api"}), provider="salesforce", scopes_verified=credential.scopes_verified
            )
        token = await self.lease.get_token()
        for attempt in range(2):
            try:
                response = await self.http.request(
                    method, self.origin + path, params=params, json=json, headers={"Authorization": f"Bearer {token}"}
                )
            except httpx.RequestError:
                raise IntegrationNetworkError(reason="connection", provider="salesforce") from None
            if response.status_code == httpx.codes.UNAUTHORIZED and attempt == 0:
                token = await self.lease.get_token_after_auth_error(
                    AuthExpiredError(provider="salesforce"), rejected_token=token
                )
                refreshed = await self.lease.get_credential()
                if (
                    refreshed.account is None
                    or refreshed.account.tenant_id != self.origin
                    or refreshed.provider != "salesforce"
                    or refreshed.identity != "user_delegated"
                ):
                    raise ConnectionNotAuthorizedError(provider="salesforce", reason="provider")
                if not refreshed.scopes_verified or "api" not in refreshed.granted_scopes:
                    raise ScopeMissingError(frozenset({"api"}), provider="salesforce")
                continue
            if response.status_code == httpx.codes.UNAUTHORIZED:
                raise AuthExpiredError(provider="salesforce")
            if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
                try:
                    retry = max(0, min(86400, float(response.headers.get("Retry-After", "60"))))
                except ValueError:
                    retry = 60
                raise RateLimitedError(provider="salesforce", retry_after=retry)
            if response.status_code == httpx.codes.FORBIDDEN:
                # Salesforce reports daily API exhaustion as REQUEST_LIMIT_EXCEEDED.
                try:
                    body = response.json()
                    exhausted = isinstance(body, list) and any(
                        isinstance(row, dict) and row.get("errorCode") == "REQUEST_LIMIT_EXCEEDED" for row in body
                    )
                except ValueError:
                    exhausted = False
                if exhausted:
                    raise RateLimitedError(provider="salesforce", http_status=403, retry_after=60)
                raise ConnectionNotAuthorizedError(provider="salesforce", reason="provider")
            if response.status_code == httpx.codes.NOT_FOUND:
                raise ResourceNotFoundError(provider="salesforce")
            if response.is_server_error or response.is_redirect:
                raise ProviderUnavailableError(provider="salesforce", http_status=response.status_code)
            if response.is_error:
                raise InvalidRequestError(provider="salesforce")
            expected = {"GET": httpx.codes.OK, "POST": httpx.codes.CREATED, "PATCH": httpx.codes.NO_CONTENT}
            if response.status_code != expected.get(method):
                raise ProviderUnavailableError(provider="salesforce", http_status=response.status_code)
            if response.status_code == httpx.codes.NO_CONTENT:
                return None
            if len(response.content) > MAX_RESPONSE_BYTES:
                raise ProviderUnavailableError(provider="salesforce")
            try:
                return response.json()
            except ValueError:
                raise ProviderUnavailableError(provider="salesforce") from None
        raise AuthExpiredError(provider="salesforce")

    async def describe(self, obj: str, *, operation: str, fields: list[str]) -> dict:
        body = await self.request("GET", f"{API_ROOT}/sobjects/{obj}/describe")
        flag = {"read": "queryable", "create": "createable", "update": "updateable", "poll": "replicateable"}[operation]
        if not isinstance(body, dict) or body.get(flag) is not True:
            msg = "This Salesforce account cannot perform the requested object operation."
            raise invalid(msg)
        rows = body.get("fields")
        if not isinstance(rows, list):
            msg = "Salesforce returned invalid field metadata."
            raise invalid(msg)
        metadata = {row.get("name"): row for row in rows if isinstance(row, dict)}
        for field in fields:
            row = metadata.get(field)
            if row is None or (operation in {"create", "update"} and row.get(flag) is not True):
                msg = "A selected field is unavailable for this account or operation."
                raise invalid(msg)
        return body
