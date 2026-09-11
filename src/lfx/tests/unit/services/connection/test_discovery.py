from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Literal

import pytest
from lfx.integrations import (
    ConnectionNotAuthorizedError,
    ConnectionRef,
    ConnectionResolutionRequest,
    ResolvedCredential,
    ScopeMissingError,
)
from lfx.services.authorization.base import ExecutionPrincipal
from lfx.services.connection.base import BaseConnectionResolverService, ConnectionAccessPolicy
from lfx.services.connection.env_resolver import EnvConnectionResolver
from lfx.services.deps import get_connection_resolver
from lfx.services.factory import ServiceFactory
from lfx.services.manager import ServiceManager
from lfx.services.schema import ServiceType
from pydantic import SecretStr

if TYPE_CHECKING:
    from pathlib import Path


def _request(principal: ExecutionPrincipal) -> ConnectionResolutionRequest:
    return ConnectionResolutionRequest(ref=ConnectionRef.parse("google/work"), principal=principal)


class PolicyResolver(BaseConnectionResolverService):
    """A host that deliberately omits the portable authorization helper."""

    def __init__(self, policy: ConnectionAccessPolicy):
        super().__init__()
        self.policy = policy
        self.policy_reads = 0
        self.credential_reads = 0
        self.credential = ResolvedCredential(access_token=SecretStr("host-token"), owner_kind=policy.owner_kind)
        self.set_ready()

    def authorize_principal(self, *_args, **_kwargs):
        # Even an override cannot weaken the base resolve entry point.
        return None

    async def _get_access_policy(self, _request):
        self.policy_reads += 1
        return self.policy

    async def _resolve(self, _request, policy):
        assert policy is self.policy
        self.credential_reads += 1
        return self.credential


async def _assert_resolution(resolver: PolicyResolver, principal: ExecutionPrincipal, *, allowed: bool) -> None:
    if allowed:
        assert (await resolver.resolve(_request(principal))).access_token.get_secret_value() == "host-token"
    else:
        with pytest.raises(ConnectionNotAuthorizedError):
            await resolver.resolve(_request(principal))
    assert resolver.credential_reads == int(allowed)
    if principal.kind in {"unknown", "anonymous_public"}:
        assert resolver.policy_reads == 0


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
        # INT-6: owner-only families still resolve their OWN rows; allow_explicit_shares
        # only governs the host's share branch, which the portable floor never reaches.
        (
            ExecutionPrincipal(kind="actor", user_id="user-1", interactive=True, allow_explicit_shares=False),
            "user",
            "user-1",
            False,
            True,
        ),
        (
            ExecutionPrincipal(kind="actor", user_id="user-1", interactive=True, allow_explicit_shares=False),
            "user",
            "user-2",
            False,
            False,
        ),
        # INT-6: anonymous/public execution never reaches an instance credential either.
        (ExecutionPrincipal(kind="anonymous_public", family="workflow_public_v2"), "instance", None, True, False),
    ],
)
async def test_portable_principal_authorization_floor(
    principal: ExecutionPrincipal,
    owner_kind: Literal["user", "instance", "env"],
    owner_id: str | None,
    allow_non_interactive: bool,  # noqa: FBT001 - parametrized contract dimension
    allowed: bool,  # noqa: FBT001 - expected authorization result
) -> None:
    resolver = PolicyResolver(
        ConnectionAccessPolicy(
            connection_owner_id=owner_id, owner_kind=owner_kind, allow_non_interactive=allow_non_interactive
        )
    )
    await _assert_resolution(resolver, principal, allowed=allowed)


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
    assert ServiceType.CONNECTION_RESOLVER_SERVICE not in manager.services
    assert get_connection_resolver() is resolver


class HostResolver(EnvConnectionResolver):
    """Distinct host implementation for discovery and registration tests."""


@pytest.mark.parametrize("registration", ["class", "factory"])
def test_late_resolver_registration_replaces_environment_fallback(monkeypatch: pytest.MonkeyPatch, registration: str):
    manager = ServiceManager()
    manager._plugins_discovered = True
    monkeypatch.setattr("lfx.services.manager.get_service_manager", lambda: manager)
    fallback = get_connection_resolver()

    if registration == "class":
        manager.register_service_class(ServiceType.CONNECTION_RESOLVER_SERVICE, HostResolver)
    else:

        class HostFactory(ServiceFactory):
            def __init__(self):
                super().__init__()
                self.service_class = HostResolver

            def create(self):
                return HostResolver()

        manager.register_factory(HostFactory())

    assert isinstance(get_connection_resolver(), HostResolver)
    assert get_connection_resolver() is not fallback


@pytest.mark.parametrize("failure", ["wrong_base", "import", "attribute", "value", "resolve_override"])
def test_entry_point_failures_never_select_environment_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str
) -> None:
    def load():
        if failure == "wrong_base":
            return str
        if failure == "resolve_override":

            class UnsafeResolver(EnvConnectionResolver):
                async def resolve(self, _request):
                    return ResolvedCredential(access_token=SecretStr("unguarded-token"), owner_kind="user")

            return UnsafeResolver
        msg = "broken plugin"
        raise {"import": ImportError, "attribute": AttributeError, "value": ValueError}[failure](msg)

    ep = SimpleNamespace(name=ServiceType.CONNECTION_RESOLVER_SERVICE.value, load=load)
    monkeypatch.setattr("importlib.metadata.entry_points", lambda **_kwargs: [ep])
    manager = ServiceManager()
    monkeypatch.setattr("lfx.services.manager.get_service_manager", lambda: manager)
    with pytest.raises(RuntimeError, match="refusing"):
        manager.discover_plugins(tmp_path)
    assert manager._plugins_discovered is False
    with pytest.raises(RuntimeError, match="refusing"):
        get_connection_resolver()
    assert ServiceType.CONNECTION_RESOLVER_SERVICE not in manager.services


def test_missing_configured_resolver_path_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "lfx.toml").write_text('[services]\nconnection_resolver_service = "missing_resolver:Service"\n')
    monkeypatch.setattr("importlib.metadata.entry_points", lambda **_kwargs: [])
    with pytest.raises(RuntimeError, match="refusing"):
        ServiceManager().discover_plugins(tmp_path)


@pytest.mark.parametrize("failure", ["constructor", "not_ready", "missing_factory"])
def test_broken_registered_resolver_never_falls_back(monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    from lfx.services.manager import NoFactoryRegisteredError

    class BrokenResolver(EnvConnectionResolver):
        def __init__(self):
            if failure == "constructor":
                msg = "constructor failed"
                raise RuntimeError(msg)
            if failure == "missing_factory":
                msg = "dependency is absent"
                raise NoFactoryRegisteredError(msg)
            super().__init__()
            self._ready = False

    manager = ServiceManager()
    manager._plugins_discovered = True
    monkeypatch.setattr("lfx.services.manager.get_service_manager", lambda: manager)
    manager.register_service_class(ServiceType.CONNECTION_RESOLVER_SERVICE, BrokenResolver)
    with pytest.raises((RuntimeError, NoFactoryRegisteredError)):
        get_connection_resolver()


@pytest.mark.parametrize(
    ("principal", "owner_kind", "owner_id", "allow_non_interactive", "allowed"),
    [
        (ExecutionPrincipal(kind="actor", user_id="actor", interactive=True), "user", "owner", False, True),
        (ExecutionPrincipal(kind="actor", user_id="actor", interactive=True), "user", None, True, False),
        (ExecutionPrincipal(kind="actor", interactive=True), "user", "owner", True, False),
        (ExecutionPrincipal(kind="actor", user_id="actor"), "user", "owner", False, False),
        (ExecutionPrincipal(kind="flow_owner", user_id="actor"), "user", "owner", True, False),
        (ExecutionPrincipal(kind="anonymous_public", user_id="actor"), "user", "owner", True, False),
        (ExecutionPrincipal(kind="unknown", user_id="actor"), "user", "owner", True, False),
        (ExecutionPrincipal(kind="actor", user_id="actor", interactive=True), "env", None, True, False),
    ],
)
async def test_verified_share_only_satisfies_actor_ownership_mismatch(
    principal: ExecutionPrincipal,
    owner_kind: Literal["user", "instance", "env"],
    owner_id: str | None,
    allow_non_interactive: bool,  # noqa: FBT001 - authorization contract dimension
    allowed: bool,  # noqa: FBT001 - expected result
) -> None:
    resolver = PolicyResolver(
        ConnectionAccessPolicy(
            connection_owner_id=owner_id,
            owner_kind=owner_kind,
            allow_non_interactive=allow_non_interactive,
            explicit_share_authorized=True,
        )
    )
    await _assert_resolution(resolver, principal, allowed=allowed)


@pytest.mark.parametrize("base", [BaseConnectionResolverService, EnvConnectionResolver])
def test_resolve_override_is_rejected_at_class_definition(base):
    with pytest.raises(TypeError, match="resolve cannot be overridden"):

        class UnsafeResolver(base):
            async def resolve(self, _request):
                return ResolvedCredential(access_token=SecretStr("unguarded-token"), owner_kind="user")


def test_mixin_cannot_replace_guarded_entry_point():
    class UnsafeMixin:
        async def resolve(self, _request):
            return ResolvedCredential(access_token=SecretStr("unguarded-token"), owner_kind="user")

    with pytest.raises(TypeError, match="resolve cannot be overridden"):

        class UnsafeResolver(UnsafeMixin, EnvConnectionResolver):
            pass


def test_host_cannot_omit_policy_hook():
    class IncompleteResolver(BaseConnectionResolverService):
        async def _resolve(self, _request, _policy):
            return ResolvedCredential(access_token=SecretStr("unguarded-token"))

    with pytest.raises(TypeError, match="_get_access_policy"):
        IncompleteResolver()


async def test_invalid_host_policy_never_reads_credentials():
    resolver = PolicyResolver(ConnectionAccessPolicy(owner_kind="user"))
    resolver.policy = None
    await _assert_resolution(
        resolver, ExecutionPrincipal(kind="actor", user_id="owner", interactive=True), allowed=False
    )


@pytest.mark.parametrize(
    ("scopes_verified", "granted", "allowed"),
    [
        (False, frozenset({"drive.readonly"}), False),
        (True, frozenset(), False),
        (True, frozenset({"drive.readonly"}), True),
    ],
)
async def test_host_resolver_cannot_skip_scope_enforcement(scopes_verified, granted, allowed):
    resolver = PolicyResolver(ConnectionAccessPolicy(owner_kind="user", connection_owner_id="owner"))
    resolver.credential = ResolvedCredential(
        access_token=SecretStr("host-token"),
        owner_kind="user",
        scopes_verified=scopes_verified,
        granted_scopes=granted,
    )
    request = ConnectionResolutionRequest(
        ref=ConnectionRef.parse("google/work"),
        principal=ExecutionPrincipal(kind="actor", user_id="owner", interactive=True),
        required_scopes=frozenset({"https://www.googleapis.com/auth/drive.readonly"}),
    )
    if allowed:
        assert await resolver.resolve(request) is resolver.credential
    else:
        with pytest.raises(ScopeMissingError) as caught:
            await resolver.resolve(request)
        assert caught.value.details["scopes_verified"] is scopes_verified
    assert resolver.credential_reads == 1


async def test_manager_teardown_disposes_separate_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = ServiceManager()
    manager._plugins_discovered = True
    monkeypatch.setattr("lfx.services.manager.get_service_manager", lambda: manager)
    fallback = get_connection_resolver()
    disposed = []

    async def teardown():
        disposed.append(True)

    monkeypatch.setattr(fallback, "teardown", teardown)
    await manager.teardown()
    assert disposed == [True]
    assert manager.connection_resolver_fallback is None
