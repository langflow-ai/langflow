from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from lfx.integrations import (
    AuthExpiredError,
    ConnectionRef,
    ConnectionResolutionRequest,
    CredentialLease,
    ResolvedCredential,
)
from lfx.services.authorization.base import ExecutionPrincipal
from pydantic import SecretStr


class Resolver:
    def __init__(self, credentials: list[ResolvedCredential]) -> None:
        self.credentials = credentials
        self.calls = 0

    async def resolve(self, _request: ConnectionResolutionRequest) -> ResolvedCredential:
        await asyncio.sleep(0)
        credential = self.credentials[min(self.calls, len(self.credentials) - 1)]
        self.calls += 1
        return credential

    async def describe(self, _ref, _principal):
        return None


class FailingResolver(Resolver):
    async def resolve(self, request: ConnectionResolutionRequest) -> ResolvedCredential:
        self.calls += 1
        if self.calls > 1:
            raise AuthExpiredError(provider=request.ref.provider)
        return self.credentials[0]


def _credential(token: str, expires_at: datetime | None = None) -> ResolvedCredential:
    return ResolvedCredential(access_token=SecretStr(token), expires_at=expires_at, provider="google", name="work")


def _request() -> ConnectionResolutionRequest:
    return ConnectionResolutionRequest(
        ref=ConnectionRef.parse("google/work"),
        principal=ExecutionPrincipal(kind="headless_operator"),
    )


@pytest.mark.asyncio
async def test_initial_resolution_is_single_flight() -> None:
    resolver = Resolver([_credential("token")])
    lease = CredentialLease(resolver, _request())

    assert await asyncio.gather(*(lease.get_token() for _ in range(10))) == ["token"] * 10
    assert resolver.calls == 1


@pytest.mark.asyncio
async def test_expiring_credential_is_refreshed() -> None:
    now = datetime.now(timezone.utc)
    resolver = Resolver([_credential("old", now + timedelta(seconds=30)), _credential("new", now + timedelta(hours=1))])
    lease = CredentialLease(resolver, _request(), now=lambda: now)

    assert await lease.get_token() == "old"
    assert await lease.get_token() == "new"
    assert resolver.calls == 2


@pytest.mark.asyncio
async def test_no_expiry_credential_refreshes_reactively_once() -> None:
    resolver = Resolver([_credential("old"), _credential("new")])
    lease = CredentialLease(resolver, _request())
    error = AuthExpiredError(provider="google")

    assert await lease.get_token() == "old"
    assert await lease.get_token_after_auth_error(error) == "new"
    with pytest.raises(AuthExpiredError):
        await lease.get_token_after_auth_error(error)
    assert resolver.calls == 2


@pytest.mark.asyncio
async def test_failed_reactive_refresh_is_not_retried() -> None:
    resolver = FailingResolver([_credential("old")])
    lease = CredentialLease(resolver, _request())
    error = AuthExpiredError(provider="google")

    assert await lease.get_token() == "old"
    with pytest.raises(AuthExpiredError):
        await lease.get_token_after_auth_error(error)
    with pytest.raises(AuthExpiredError):
        await lease.get_token_after_auth_error(error)
    assert resolver.calls == 2
