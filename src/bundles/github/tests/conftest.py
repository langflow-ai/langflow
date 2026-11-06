"""Deterministic credentials and an authenticated graph for bundle tests."""

import importlib.abc
import sys

import pytest


class _NoBackend(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, _path=None, _target=None):
        if fullname == "langflow" or fullname.startswith("langflow."):
            msg = "The standalone GitHub bundle cannot import langflow"
            raise ModuleNotFoundError(msg, name=fullname)


_BACKEND_BLOCKER = _NoBackend()
sys.meta_path.insert(0, _BACKEND_BLOCKER)

from lfx.integrations.models import (  # noqa: E402 - block the optional backend before lfx imports
    ConnectionRef,
    ConnectionResolutionRequest,
    CredentialLease,
    ResolvedCredential,
)
from lfx.services.authorization.base import (  # noqa: E402 - block the optional backend before lfx imports
    ExecutionPrincipal,
)
from pydantic import SecretStr  # noqa: E402 - block the optional backend before lfx imports


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
            granted_scopes=frozenset(),
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


@pytest.fixture(scope="session", autouse=True)
def backend_unavailable():
    try:
        yield
        assert not any(name == "langflow" or name.startswith("langflow.") for name in sys.modules)
    finally:
        sys.meta_path.remove(_BACKEND_BLOCKER)
