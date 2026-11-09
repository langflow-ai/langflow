"""Synthetic Confluence credentials and pages without server imports."""

from dataclasses import replace

import pytest
from lfx.custom.custom_component.component import Component  # noqa: F401
from lfx.integrations.models import (
    ConnectionAccount,
    ConnectionRef,
    ConnectionResolutionRequest,
    CredentialLease,
    ResolvedCredential,
)
from lfx.services.authorization.base import ExecutionPrincipal
from pydantic import SecretStr

SITE = "12345678-1234-1234-1234-123456789abc"
SCOPES = frozenset({"read:page:confluence", "write:page:confluence", "read:confluence-user", "offline_access"})


def credential(**changes):
    return replace(
        ResolvedCredential(
            access_token=SecretStr("synthetic-confluence-access"),
            provider="confluence",
            name="work",
            granted_scopes=SCOPES,
            scopes_verified=True,
            identity="user_delegated",
            account=ConnectionAccount(id="user-1", tenant_id=SITE),
        ),
        **changes,
    )


class Resolver:
    def __init__(self, credentials):
        self.credentials = credentials
        self.calls = []

    async def resolve(self, request):
        self.calls.append(request)
        return self.credentials[min(len(self.calls) - 1, len(self.credentials) - 1)]


def lease_for(*credentials):
    resolver = Resolver(list(credentials) or [credential()])
    return CredentialLease(
        resolver,
        ConnectionResolutionRequest(
            ref=ConnectionRef.parse("confluence/work"),
            principal=ExecutionPrincipal(kind="actor", user_id="owner", interactive=True),
        ),
    ), resolver


def page(identifier="1", *, version=1, space="10", created="2026-10-21T10:00:00Z", title="Example"):
    return {
        "id": identifier,
        "spaceId": space,
        "title": title,
        "status": "current",
        "createdAt": created,
        "version": {"number": version, "createdAt": "2026-10-22T10:00:00Z"},
        "body": {"storage": {"value": "<p>Example</p>"}},
        "_links": {"self": "https://evil.invalid/synthetic-confluence-access"},
        "unexpected_secret": "must-not-escape",  # pragma: allowlist secret
    }


@pytest.fixture(autouse=True)
def configured_site(monkeypatch):
    monkeypatch.setenv("LANGFLOW_CONFLUENCE_CLOUD_ID", SITE)
    monkeypatch.setenv("LANGFLOW_CONFLUENCE_SPACE_IDS", "10,20")
