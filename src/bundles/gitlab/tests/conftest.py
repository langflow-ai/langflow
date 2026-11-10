"""Standalone bundle tests reject application imports."""

import importlib.abc
import sys
from datetime import datetime, timedelta, timezone

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


class NoBackend(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):  # noqa: ARG002
        if fullname == "langflow" or fullname.startswith("langflow."):
            msg = "Standalone GitLab bundle cannot import langflow"
            raise ImportError(msg)


sys.meta_path.insert(0, NoBackend())


class Resolver:
    async def resolve(self, _request):
        return ResolvedCredential(
            access_token=SecretStr("test-only-gitlab-token"),
            provider="gitlab",
            identity="user_delegated",
            granted_scopes=frozenset({"api"}),
            scopes_verified=True,
            account=ConnectionAccount(id="9", tenant_id="https://gitlab.com"),
            expires_at=datetime.now(timezone.utc) + timedelta(days=10),
        )


@pytest.fixture
def lease(monkeypatch):
    monkeypatch.delenv("LANGFLOW_GITLAB_ORIGIN", raising=False)
    return CredentialLease(
        Resolver(),
        ConnectionResolutionRequest(
            ref=ConnectionRef(provider="gitlab", name="work"),
            principal=ExecutionPrincipal(kind="actor", user_id="owner", interactive=True),
        ),
    )
