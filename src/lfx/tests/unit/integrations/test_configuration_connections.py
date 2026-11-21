"""Metadata refresh resolves only the authenticated configuring user's connections."""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from lfx.custom.custom_component.component import Component
from lfx.integrations.configuration import connection_configuration_context
from lfx.integrations.models import ResolvedCredential
from lfx.io import ConnectionRefInput
from lfx.services.authorization.base import ExecutionPrincipal
from pydantic import SecretStr


class MetadataComponent(Component):
    inputs = [ConnectionRefInput(name="connection", provider="whatsapp", value="whatsapp/business")]


class Resolver:
    def __init__(self):
        self.requests = []

    async def resolve(self, request):
        self.requests.append(request)
        return ResolvedCredential(access_token=SecretStr("metadata-token"), provider="whatsapp", identity="service")


@pytest.fixture
def resolver(monkeypatch):
    resolver = Resolver()
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: resolver)
    return resolver


async def test_configuration_lease_uses_trusted_user_without_serializing_identity(resolver):
    user = str(uuid4())
    component = MetadataComponent(_user_id="untrusted-template-user")
    with connection_configuration_context(user_id=user):
        lease = component.resolve_connection("connection")
    assert resolver.requests == []
    await lease.get_token()
    principal = resolver.requests[0].principal
    assert principal.user_id == principal.actor_id == user
    assert principal.interactive is True
    assert user not in str(component.to_frontend_node())


@pytest.mark.parametrize(
    "principal", [ExecutionPrincipal(kind="actor", user_id="runtime-user"), ExecutionPrincipal.unknown()]
)
async def test_configuration_scope_does_not_replace_runtime_identity(resolver, principal):
    component = MetadataComponent()
    component.set_vertex(SimpleNamespace(graph=SimpleNamespace(execution_principal=principal, flow_id=None)))
    with connection_configuration_context(user_id="configuring-user"):
        await component.resolve_connection("connection").get_token()
    assert resolver.requests[0].principal is principal


async def test_configuration_scope_is_reset_when_refresh_fails(resolver):
    msg = "refresh failed"
    with pytest.raises(RuntimeError), connection_configuration_context(user_id="configuring-user"):
        raise RuntimeError(msg)
    await MetadataComponent(_user_id="template-user").resolve_connection("connection").get_token()
    assert resolver.requests[0].principal.kind == "unknown"


async def test_configuration_scopes_are_isolated_between_requests(resolver):
    async def refresh(user):
        with connection_configuration_context(user_id=user):
            await asyncio.sleep(0)
            await MetadataComponent().resolve_connection("connection").get_token()

    await asyncio.gather(refresh("alice"), refresh("bob"))
    assert {request.principal.user_id for request in resolver.requests} == {"alice", "bob"}
