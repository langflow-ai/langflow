from __future__ import annotations

from typing import Literal

import pytest
from lfx.integrations import ConnectionRef, ConnectionResolutionRequest
from lfx.services.authorization.base import ExecutionPrincipal
from lfx.services.connection.base import BaseConnectionResolverService
from lfx.services.connection.env_resolver import EnvConnectionResolver
from lfx.services.deps import get_connection_resolver
from lfx.services.manager import ServiceManager


def _request(principal: ExecutionPrincipal) -> ConnectionResolutionRequest:
    return ConnectionResolutionRequest(ref=ConnectionRef.parse("google/work"), principal=principal)


@pytest.mark.parametrize(
    ("principal", "owner_kind", "owner_id", "allow_non_interactive", "allowed"),
    [
        (ExecutionPrincipal(kind="headless_operator"), "env", None, True, True),
        (ExecutionPrincipal(kind="actor", user_id="user-1", interactive=True), "env", None, True, False),
        (ExecutionPrincipal(kind="unknown"), "instance", None, True, False),
        (ExecutionPrincipal(kind="anonymous_public"), "instance", None, True, False),
        (ExecutionPrincipal(kind="actor", user_id="user-1", interactive=True), "instance", None, True, True),
        (ExecutionPrincipal(kind="actor", user_id="user-1", interactive=True), "user", "user-1", False, True),
        (ExecutionPrincipal(kind="actor", user_id="user-1", interactive=True), "user", None, False, False),
        (ExecutionPrincipal(kind="actor", user_id="user-1", interactive=True), "user", "user-2", False, False),
        (ExecutionPrincipal(kind="flow_owner", user_id="user-1"), "user", "user-1", False, False),
        (ExecutionPrincipal(kind="flow_owner", user_id="user-1"), "user", "user-1", True, True),
    ],
)
def test_portable_principal_authorization_floor(
    principal: ExecutionPrincipal,
    owner_kind: Literal["user", "instance", "env"],
    owner_id: str | None,
    allow_non_interactive: bool,  # noqa: FBT001 - parametrized contract dimension
    allowed: bool,  # noqa: FBT001 - expected authorization result
) -> None:
    resolver = EnvConnectionResolver()

    denial = BaseConnectionResolverService.authorize_principal(
        resolver,
        _request(principal),
        connection_owner_id=owner_id,
        owner_kind=owner_kind,
        allow_non_interactive=allow_non_interactive,
    )

    assert (denial is None) is allowed


def test_configured_resolver_with_wrong_base_fails_closed() -> None:
    manager = ServiceManager()

    with pytest.raises(RuntimeError, match="must subclass BaseConnectionResolverService"):
        manager._register_service_from_path("connection_resolver_service", "builtins:str")


def test_absent_resolver_uses_headless_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = ServiceManager()
    manager._plugins_discovered = True
    monkeypatch.setattr("lfx.services.manager.get_service_manager", lambda: manager)

    resolver = get_connection_resolver()

    assert isinstance(resolver, EnvConnectionResolver)
    assert manager.services[resolver.name] is resolver
