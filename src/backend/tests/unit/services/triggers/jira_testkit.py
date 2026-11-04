"""Synthetic Jira credentials without importing the server package."""

from dataclasses import replace

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


def credential(**changes):
    return replace(
        ResolvedCredential(
            access_token=SecretStr("synthetic-jira-access"),
            provider="jira",
            name="work",
            granted_scopes=frozenset({"read:jira-work", "write:jira-work", "read:jira-user", "offline_access"}),
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
            ref=ConnectionRef.parse("jira/work"),
            principal=ExecutionPrincipal(kind="actor", user_id="owner", interactive=True),
        ),
    ), resolver


def issue(
    identifier="1", *, updated="2026-10-22T10:00:00Z", status="1", created="2026-10-21T10:00:00Z", project="DEMO"
):
    return {
        "id": identifier,
        "key": f"{project}-{identifier}",
        "self": "https://untrusted.invalid/synthetic-jira-access",
        "fields": {
            "summary": "Example",
            "status": {"id": status, "name": "Open"},
            "created": created,
            "updated": updated,
            "project": {"key": project},
            "issuetype": {"id": "10001"},
            "unexpected_secret": "must-not-escape",  # pragma: allowlist secret
        },
    }
