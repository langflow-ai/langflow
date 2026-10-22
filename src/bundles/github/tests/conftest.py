"""Deterministic credentials and an authenticated graph for bundle tests."""

from types import SimpleNamespace

import pytest
from lfx.integrations.models import ConnectionRef, ConnectionResolutionRequest, CredentialLease, ResolvedCredential
from lfx.services.authorization.base import ExecutionPrincipal
from pydantic import SecretStr


class Resolver:
    def __init__(self, *, identity="service"):
        self.calls = 0
        self.identity = identity

    async def resolve(self, _request):
        self.calls += 1
        return ResolvedCredential(
            access_token=SecretStr(f"test-installation-{self.calls}"),
            provider="github",
            identity=self.identity,
            granted_scopes=frozenset(
                {
                    "metadata:read",
                    "issues:read",
                    "issues:write",
                    "pull_requests:read",
                    "pull_requests:write",
                    "webhooks:write",
                }
            ),
            scopes_verified=True,
        )


@pytest.fixture
def lease():
    resolver = Resolver()
    request = ConnectionResolutionRequest(
        ref=ConnectionRef(provider="github", name="work"),
        principal=ExecutionPrincipal(kind="actor", user_id="owner", interactive=True),
    )
    return CredentialLease(resolver, request)


def component_graph():
    return SimpleNamespace(
        execution_principal=ExecutionPrincipal(kind="actor", user_id="owner", interactive=True),
        flow_id=None,
        run_id=None,
    )
