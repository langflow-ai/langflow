"""Salesforce HTTP contract fixtures with synthetic credentials."""

from dataclasses import replace

import pytest
from lfx.integrations.models import (
    ConnectionAccount,
    ConnectionRef,
    ConnectionResolutionRequest,
    CredentialLease,
    ResolvedCredential,
)
from lfx.services.authorization.base import ExecutionPrincipal
from pydantic import SecretStr

ORG = "https://example.my.salesforce.com"
RECORD = "001000000000001AAA"


def credential(**changes):
    return replace(
        ResolvedCredential(
            access_token=SecretStr("synthetic-access"),
            provider="salesforce",
            name="work",
            granted_scopes=frozenset({"api", "id", "refresh_token"}),
            scopes_verified=True,
            identity="user_delegated",
            account=ConnectionAccount(id="org/user", tenant_id=ORG),
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
    lease = CredentialLease(
        resolver,
        ConnectionResolutionRequest(
            ref=ConnectionRef.parse("salesforce/work"),
            principal=ExecutionPrincipal(kind="actor", user_id="owner", interactive=True),
        ),
    )
    return lease, resolver


def metadata(obj="Account"):
    from lfx_salesforce.schema import FIELDS, SYSTEM_FIELDS

    return {
        "queryable": True,
        "replicateable": True,
        "createable": True,
        "updateable": True,
        "fields": [
            {"name": name, "createable": name not in SYSTEM_FIELDS, "updateable": name not in SYSTEM_FIELDS}
            for name in [*SYSTEM_FIELDS, *FIELDS[obj]]
        ],
    }


@pytest.fixture(autouse=True)
def configured_org(monkeypatch):
    monkeypatch.setenv("LANGFLOW_SALESFORCE_ORIGIN", ORG)
