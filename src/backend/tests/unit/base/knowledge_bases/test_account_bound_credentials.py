"""Knowledge base lookups cannot turn account denials into environment credentials."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from lfx.base.knowledge_bases.backends import base as backend
from lfx.base.knowledge_bases.ingestion_sources import connector_base as connector
from lfx.services import deps
from lfx.services.variable.exceptions import RuntimeVariableError
from pydantic import SecretStr


@pytest.mark.asyncio
@pytest.mark.parametrize("resolver", ["connector", "backend"])
async def test_account_failure_never_uses_knowledge_base_environment(monkeypatch, resolver):
    owner = uuid4()

    class RefusedService:
        async def get_variable(self, **_kwargs):
            msg = "Account denied"
            raise RuntimeVariableError(msg, reason="variable_not_approved")

    @asynccontextmanager
    async def session_scope():
        yield None

    def forbidden_environment(_):
        msg = "An authoritative account lookup must not use process credentials"
        raise AssertionError(msg)

    monkeypatch.setattr(deps, "get_variable_service", RefusedService)
    monkeypatch.setattr(deps, "session_scope", session_scope)
    monkeypatch.setattr(backend, "safe_getenv", forbidden_environment)
    monkeypatch.setattr(connector, "safe_getenv", forbidden_environment)
    subject = SimpleNamespace(_coerce_user_uuid=lambda: owner)
    if resolver == "connector":
        subject._lookup_variable = lambda user, name: connector.KBConnectorSource._lookup_variable(subject, user, name)
        resolve = connector.KBConnectorSource.resolve_secret
    else:
        resolve = backend.BaseVectorStoreBackend.resolve_secret_with_source
    with pytest.raises(RuntimeVariableError, match="Account denied"):
        await resolve(subject, "KEY")


@pytest.mark.asyncio
async def test_connector_unwraps_approved_secret_at_credential_boundary(monkeypatch):
    class ApprovedService:
        async def get_variable(self, **_kwargs):
            return SecretStr("approved-value")

    @asynccontextmanager
    async def session_scope():
        yield None

    monkeypatch.setattr(deps, "get_variable_service", ApprovedService)
    monkeypatch.setattr(deps, "session_scope", session_scope)
    value = await connector.KBConnectorSource._lookup_variable(SimpleNamespace(), uuid4(), "KEY")
    assert value == "approved-value"
