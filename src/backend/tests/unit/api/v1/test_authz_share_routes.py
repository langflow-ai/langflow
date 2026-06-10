"""Route-level tests for the OSS share-administration owner floor."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from langflow.api.v1 import authz_shares as shares_module
from langflow.api.v1.schemas.authz_shares import ShareCreate, ShareUpdate
from langflow.services.database.models.auth import AuthzShare, SharePermissionLevel, ShareScope

pytestmark = pytest.mark.no_blockbuster


class _FakeAsyncSession:
    """Minimal async-session stand-in: stores get() results and records writes."""

    def __init__(self, get_by_type: dict[tuple[type, UUID], Any] | None = None) -> None:
        self._get_by_type = get_by_type or {}
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.flushed = 0
        self.rolled_back = 0

    async def get(self, model: type, key: UUID) -> Any:
        return self._get_by_type.get((model, key))

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def delete(self, obj: Any) -> None:
        self.deleted.append(obj)

    async def flush(self) -> None:
        self.flushed += 1

    async def refresh(self, obj: Any) -> None:  # noqa: ARG002
        return None

    async def rollback(self) -> None:
        self.rolled_back += 1

    async def exec(self, _stmt: Any) -> list[Any]:
        # list_shares is not exercised here; return empty by default.
        return []


class _StubAuthz:
    """Pass-through authz service: allow everything, no cross-user fetch."""

    def __init__(self, *, cross_user: bool = False, enabled: bool = False, allow: bool = True) -> None:
        self._cross_user = cross_user
        self._enabled = enabled
        self._allow = allow
        self.enforce_calls: list[dict] = []
        self.invalidated_users: list[UUID] = []
        self.invalidate_all_calls = 0

    async def supports_cross_user_fetch(self) -> bool:
        return self._cross_user

    async def is_enabled(self) -> bool:
        return self._enabled

    async def enforce(self, **kwargs) -> bool:
        self.enforce_calls.append(kwargs)
        return self._allow

    async def batch_enforce(self, **kwargs) -> list[bool]:
        return [self._allow] * len(kwargs.get("requests", []))

    async def invalidate_user(self, user_id: UUID, *_args, **_kwargs) -> None:
        self.invalidated_users.append(user_id)

    async def invalidate_all(self, *_args, **_kwargs) -> None:
        self.invalidate_all_calls += 1


@pytest.fixture
def patch_authz(monkeypatch):
    """Install a stub authz service into the shares module and the split helper modules."""
    from langflow.services.authorization import audit as authz_audit
    from langflow.services.authorization import guards as authz_guards
    from langflow.services.authorization import listing as authz_listing

    def _apply(*, cross_user: bool = False, enabled: bool = False, allow: bool = True) -> _StubAuthz:
        stub = _StubAuthz(cross_user=cross_user, enabled=enabled, allow=allow)
        monkeypatch.setattr(shares_module, "get_authorization_service", lambda: stub)
        for module in (authz_guards, authz_listing):
            monkeypatch.setattr(module, "get_authorization_service", lambda: stub)
        # Mirror the requested AUTHZ_ENABLED state so the guard's early-return
        # only fires under OSS. Audit is always off so we don't open real
        # sessions for background writes.
        settings = SimpleNamespace(
            auth_settings=SimpleNamespace(AUTHZ_ENABLED=enabled, AUTHZ_AUDIT_ENABLED=False),
        )
        for module in (authz_audit, authz_guards, authz_listing):
            monkeypatch.setattr(module, "get_settings_service", lambda s=settings: s)
        return stub

    return _apply


@pytest.fixture
def silence_audit(monkeypatch):
    """Replace audit_decision with a no-op so we don't spawn background tasks."""

    async def _noop(**_kwargs):
        return None

    monkeypatch.setattr(shares_module, "audit_decision", _noop)


def _make_user(*, is_superuser: bool = False) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), is_superuser=is_superuser, username="u")


def _make_flow_owned_by(owner_id: UUID) -> Any:
    from langflow.services.database.models.flow.model import Flow

    return SimpleNamespace(_model=Flow, id=uuid4(), user_id=owner_id)


def _payload_for(resource_id: UUID) -> ShareCreate:
    return ShareCreate(
        resource_type="flow",
        resource_id=resource_id,
        scope=ShareScope.USER.value,
        target_id=uuid4(),
        permission_level=SharePermissionLevel.READ.value,
    )


# --------------------------------------------------------------------------- #
# CREATE — OSS floor must block non-owner / non-superuser
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_create_share_blocks_non_owner_under_oss_passthrough(patch_authz, silence_audit):  # noqa: ARG001
    """A non-owner cannot mint a share row for another user's flow under OSS."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)

    owner = _make_user()
    attacker = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    session = _FakeAsyncSession({(Flow, flow.id): flow})
    payload = _payload_for(flow.id)

    with pytest.raises(HTTPException) as excinfo:
        await shares_module.create_share(payload=payload, current_user=attacker, session=session)

    assert excinfo.value.status_code == 403
    assert "Only the resource owner" in excinfo.value.detail
    # Floor fires before any DB write — no share row was added.
    assert session.added == []


@pytest.mark.asyncio
async def test_create_share_allows_owner_under_oss_passthrough(patch_authz, silence_audit):  # noqa: ARG001
    """The resource owner can mint a share row under OSS pass-through."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)

    owner = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    session = _FakeAsyncSession({(Flow, flow.id): flow})
    payload = _payload_for(flow.id)

    result = await shares_module.create_share(payload=payload, current_user=owner, session=session)

    assert result.resource_id == flow.id
    assert len(session.added) == 1
    assert session.flushed == 1


@pytest.mark.asyncio
async def test_create_share_allows_superuser_under_oss_passthrough(patch_authz, silence_audit):  # noqa: ARG001
    """A superuser can mint a share row for a resource they don't own."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)

    owner = _make_user()
    admin = _make_user(is_superuser=True)
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    session = _FakeAsyncSession({(Flow, flow.id): flow})
    payload = _payload_for(flow.id)

    result = await shares_module.create_share(payload=payload, current_user=admin, session=session)

    assert result.resource_id == flow.id
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_create_share_returns_404_when_resource_missing(patch_authz, silence_audit):  # noqa: ARG001
    """A missing resource yields 404 — not 403 — to preserve UUID privacy."""
    patch_authz(cross_user=False, enabled=False)

    attacker = _make_user()
    session = _FakeAsyncSession({})  # no resource present
    payload = _payload_for(uuid4())

    with pytest.raises(HTTPException) as excinfo:
        await shares_module.create_share(payload=payload, current_user=attacker, session=session)

    assert excinfo.value.status_code == 404


# --------------------------------------------------------------------------- #
# PATCH — same floor
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_update_share_blocks_non_owner_under_oss_passthrough(patch_authz, silence_audit):  # noqa: ARG001
    """A non-owner cannot PATCH a share on another user's resource under OSS."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)

    owner = _make_user()
    attacker = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    share = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.USER.value,
        target_id=uuid4(),
        permission_level=SharePermissionLevel.READ.value,
        created_by=attacker.id,  # attacker is even the creator — floor still blocks
    )
    session = _FakeAsyncSession({(AuthzShare, share.id): share, (Flow, flow.id): flow})
    update = ShareUpdate(permission_level=SharePermissionLevel.WRITE.value)

    with pytest.raises(HTTPException) as excinfo:
        await shares_module.update_share(
            share_id=share.id,
            payload=update,
            current_user=attacker,
            session=session,
        )

    assert excinfo.value.status_code == 403
    # PATCH was rejected — no flush should have happened.
    assert session.flushed == 0


@pytest.mark.asyncio
async def test_update_share_allows_owner_under_oss_passthrough(patch_authz, silence_audit):  # noqa: ARG001
    """The resource owner can PATCH a share on their resource under OSS."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)

    owner = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    share = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.USER.value,
        target_id=uuid4(),
        permission_level=SharePermissionLevel.READ.value,
        created_by=owner.id,
    )
    session = _FakeAsyncSession({(AuthzShare, share.id): share, (Flow, flow.id): flow})
    update = ShareUpdate(permission_level=SharePermissionLevel.WRITE.value)

    result = await shares_module.update_share(
        share_id=share.id,
        payload=update,
        current_user=owner,
        session=session,
    )

    assert result.permission_level == SharePermissionLevel.WRITE.value
    assert session.flushed == 1


# --------------------------------------------------------------------------- #
# DELETE — same floor
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_delete_share_blocks_non_owner_under_oss_passthrough(patch_authz, silence_audit):  # noqa: ARG001
    """A non-owner cannot DELETE a share on another user's resource under OSS."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)

    owner = _make_user()
    attacker = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    share = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.USER.value,
        target_id=uuid4(),
        permission_level=SharePermissionLevel.READ.value,
        created_by=attacker.id,  # attacker created it but is not the resource owner
    )
    session = _FakeAsyncSession({(AuthzShare, share.id): share, (Flow, flow.id): flow})

    with pytest.raises(HTTPException) as excinfo:
        await shares_module.delete_share(share_id=share.id, current_user=attacker, session=session)

    assert excinfo.value.status_code == 403
    # The floor blocks before the DELETE.
    assert session.deleted == []


@pytest.mark.asyncio
async def test_delete_share_allows_owner_under_oss_passthrough(patch_authz, silence_audit):  # noqa: ARG001
    """The resource owner can DELETE a share on their resource under OSS."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)

    owner = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    share = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.USER.value,
        target_id=uuid4(),
        permission_level=SharePermissionLevel.READ.value,
        created_by=owner.id,
    )
    session = _FakeAsyncSession({(AuthzShare, share.id): share, (Flow, flow.id): flow})

    await shares_module.delete_share(share_id=share.id, current_user=owner, session=session)

    assert len(session.deleted) == 1


# --------------------------------------------------------------------------- #
# Floor behavior when the authorization plugin is active
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_floor_is_skipped_when_plugin_active(patch_authz, silence_audit):  # noqa: ARG001
    """OSS floor is skipped when the authorization plugin is actively enforcing.

    When supports_cross_user_fetch=True AND AUTHZ_ENABLED=true, the OSS floor
    is skipped so a plugin-granted share:create role can administer shares on
    another user's resource. ``ensure_share_permission`` (mocked to allow here)
    becomes the authoritative check.
    """
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=True, enabled=True)

    owner = _make_user()
    delegate = _make_user()  # non-owner, but allowed by plugin policy
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    session = _FakeAsyncSession({(Flow, flow.id): flow})
    payload = _payload_for(flow.id)

    result = await shares_module.create_share(payload=payload, current_user=delegate, session=session)

    # The floor is skipped; the stub authz allows the operation; the row is
    # written. If the floor still fired we'd see a 403 instead.
    assert result.resource_id == flow.id
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_create_share_invokes_plugin_enforce_for_non_owner(patch_authz, silence_audit):  # noqa: ARG001
    """Regression: plugin enforce() must run for non-owner share-create.

    Previously ``create_share`` passed ``share_user_id=current_user.id`` which
    tripped the owner-override fast path in ``ensure_share_permission`` and
    the plugin was never consulted — letting any authenticated user mint share
    rows once the OSS floor was bypassed.  The fix passes the *resource*
    owner so only the resource owner gets the override.
    """
    from langflow.services.database.models.flow.model import Flow

    stub = patch_authz(cross_user=True, enabled=True)

    owner = _make_user()
    delegate = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    session = _FakeAsyncSession({(Flow, flow.id): flow})
    payload = _payload_for(flow.id)

    await shares_module.create_share(payload=payload, current_user=delegate, session=session)

    # enforce() was actually called for the non-owner.
    assert any(call.get("user_id") == delegate.id for call in stub.enforce_calls), (
        f"expected at least one enforce() call for delegate, got: {stub.enforce_calls}"
    )


@pytest.mark.asyncio
async def test_create_share_denied_when_plugin_denies_non_owner(patch_authz, silence_audit):  # noqa: ARG001
    """Regression: plugin deny on share-create must yield 403 and no DB write."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=True, enabled=True, allow=False)

    owner = _make_user()
    delegate = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    session = _FakeAsyncSession({(Flow, flow.id): flow})
    payload = _payload_for(flow.id)

    with pytest.raises(HTTPException) as excinfo:
        await shares_module.create_share(payload=payload, current_user=delegate, session=session)

    assert excinfo.value.status_code == 403
    assert session.added == []


@pytest.mark.asyncio
async def test_update_share_invokes_plugin_enforce_for_share_creator(patch_authz, silence_audit):  # noqa: ARG001
    """Regression: share *creator* who is not the resource owner must hit plugin enforce()."""
    from langflow.services.database.models.flow.model import Flow

    stub = patch_authz(cross_user=True, enabled=True)

    owner = _make_user()
    delegate = _make_user()  # not the resource owner, but is the share row creator
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    share = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.USER.value,
        target_id=uuid4(),
        permission_level=SharePermissionLevel.READ.value,
        created_by=delegate.id,
    )
    session = _FakeAsyncSession({(AuthzShare, share.id): share, (Flow, flow.id): flow})
    update = ShareUpdate(permission_level=SharePermissionLevel.WRITE.value)

    await shares_module.update_share(
        share_id=share.id,
        payload=update,
        current_user=delegate,
        session=session,
    )

    assert any(call.get("user_id") == delegate.id for call in stub.enforce_calls), (
        f"expected plugin enforce() to run for share creator non-owner, got: {stub.enforce_calls}"
    )


@pytest.mark.asyncio
async def test_delete_share_denied_when_plugin_denies_share_creator(patch_authz, silence_audit):  # noqa: ARG001
    """Regression: share creator can no longer bypass plugin policy on DELETE."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=True, enabled=True, allow=False)

    owner = _make_user()
    delegate = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    share = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.USER.value,
        target_id=uuid4(),
        permission_level=SharePermissionLevel.READ.value,
        created_by=delegate.id,
    )
    session = _FakeAsyncSession({(AuthzShare, share.id): share, (Flow, flow.id): flow})

    with pytest.raises(HTTPException) as excinfo:
        await shares_module.delete_share(share_id=share.id, current_user=delegate, session=session)

    assert excinfo.value.status_code == 403
    assert session.deleted == []


# --------------------------------------------------------------------------- #
# Visibility predicate — owner / creator / PUBLIC / USER / TEAM / PRIVATE
# --------------------------------------------------------------------------- #


def _share(*, scope: str, target_id: UUID | None, created_by: UUID) -> AuthzShare:
    return AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=uuid4(),
        scope=scope,
        target_id=target_id,
        permission_level=SharePermissionLevel.READ.value,
        created_by=created_by,
    )


def test_share_visible_owner_and_creator_always_see():
    """Resource owner and the share creator see the row regardless of scope."""
    owner = uuid4()
    creator = uuid4()
    # PRIVATE row owned by `owner`, created by `creator`.
    row = _share(scope=ShareScope.PRIVATE.value, target_id=None, created_by=creator)
    assert shares_module._share_visible(row=row, user_id=owner, resource_owner_id=owner, is_team_member=False)
    assert shares_module._share_visible(row=row, user_id=creator, resource_owner_id=owner, is_team_member=False)


def test_share_visible_public_is_visible_to_anyone():
    row = _share(scope=ShareScope.PUBLIC.value, target_id=None, created_by=uuid4())
    assert shares_module._share_visible(row=row, user_id=uuid4(), resource_owner_id=uuid4(), is_team_member=False)


def test_share_visible_user_scope_matches_target_only():
    target = uuid4()
    row = _share(scope=ShareScope.USER.value, target_id=target, created_by=uuid4())
    assert shares_module._share_visible(row=row, user_id=target, resource_owner_id=uuid4(), is_team_member=False)
    # A different user (not owner/creator/target) cannot see it.
    assert not shares_module._share_visible(row=row, user_id=uuid4(), resource_owner_id=uuid4(), is_team_member=False)


def test_share_visible_team_scope_follows_membership_flag():
    row = _share(scope=ShareScope.TEAM.value, target_id=uuid4(), created_by=uuid4())
    assert shares_module._share_visible(row=row, user_id=uuid4(), resource_owner_id=uuid4(), is_team_member=True)
    assert not shares_module._share_visible(row=row, user_id=uuid4(), resource_owner_id=uuid4(), is_team_member=False)


def test_share_visible_private_hidden_from_non_owner():
    row = _share(scope=ShareScope.PRIVATE.value, target_id=None, created_by=uuid4())
    assert not shares_module._share_visible(row=row, user_id=uuid4(), resource_owner_id=uuid4(), is_team_member=True)


# --------------------------------------------------------------------------- #
# Cache invalidation contract — USER scope targets the user; others drop all
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_invalidate_for_share_user_scope_targets_user(patch_authz):
    stub = patch_authz(cross_user=False, enabled=False)
    target = uuid4()
    await shares_module._invalidate_for_share(ShareScope.USER.value, target)
    assert stub.invalidated_users == [target]
    assert stub.invalidate_all_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scope", "target_id"),
    [
        (ShareScope.PUBLIC.value, None),
        (ShareScope.TEAM.value, "team"),
        (ShareScope.PRIVATE.value, None),
    ],
)
async def test_invalidate_for_share_non_user_scope_invalidates_all(patch_authz, scope, target_id):
    stub = patch_authz(cross_user=False, enabled=False)
    resolved = uuid4() if target_id == "team" else None
    await shares_module._invalidate_for_share(scope, resolved)
    assert stub.invalidate_all_calls == 1
    assert stub.invalidated_users == []


# --------------------------------------------------------------------------- #
# TEAM-scope reachability through get_share / list_shares
# --------------------------------------------------------------------------- #


class _ExecResult:
    """Result wrapper supporting the .first()/iteration shapes the routes use."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = list(rows)

    def first(self) -> Any:
        return self._rows[0] if self._rows else None

    def all(self) -> list[Any]:
        return list(self._rows)

    def __iter__(self):
        return iter(self._rows)


class _QueueSession(_FakeAsyncSession):
    """``_FakeAsyncSession`` whose exec() returns queued result-sets in order."""

    def __init__(self, get_by_type: dict[tuple[type, UUID], Any] | None = None, *, exec_queue=None) -> None:
        super().__init__(get_by_type)
        self._exec_queue = [list(rows) for rows in (exec_queue or [])]

    async def exec(self, _stmt: Any) -> _ExecResult:
        rows = self._exec_queue.pop(0) if self._exec_queue else []
        return _ExecResult(rows)


@pytest.mark.asyncio
async def test_get_share_team_member_can_see(patch_authz, silence_audit):  # noqa: ARG001
    """A team member (neither owner nor creator) can read a TEAM-scope share."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)

    owner = _make_user()
    creator = _make_user()
    viewer = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    share = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.TEAM.value,
        target_id=uuid4(),
        permission_level=SharePermissionLevel.READ.value,
        created_by=creator.id,
    )
    # Membership query returns one row → viewer is a team member.
    session = _QueueSession({(AuthzShare, share.id): share, (Flow, flow.id): flow}, exec_queue=[[SimpleNamespace()]])

    result = await shares_module.get_share(share_id=share.id, current_user=viewer, session=session)
    assert result.id == share.id


@pytest.mark.asyncio
async def test_get_share_team_non_member_gets_404(patch_authz, silence_audit):  # noqa: ARG001
    """A non-member sees 404 (not 403) for a TEAM-scope share — UUID privacy."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)

    owner = _make_user()
    creator = _make_user()
    outsider = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    share = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.TEAM.value,
        target_id=uuid4(),
        permission_level=SharePermissionLevel.READ.value,
        created_by=creator.id,
    )
    # Empty membership query → outsider is not a member.
    session = _QueueSession({(AuthzShare, share.id): share, (Flow, flow.id): flow}, exec_queue=[[]])

    with pytest.raises(HTTPException) as excinfo:
        await shares_module.get_share(share_id=share.id, current_user=outsider, session=session)
    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_list_shares_filters_by_visibility_for_non_superuser(patch_authz, silence_audit):  # noqa: ARG001
    """list_shares returns only rows the (non-superuser) caller may see."""
    from langflow.services.database.models.flow.model import Flow

    patch_authz(cross_user=False, enabled=False)

    caller = _make_user()
    owner = _make_user()
    flow = SimpleNamespace(id=uuid4(), user_id=owner.id)
    visible = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.USER.value,
        target_id=caller.id,  # targets the caller → visible
        permission_level=SharePermissionLevel.READ.value,
        created_by=owner.id,
    )
    hidden = AuthzShare(
        id=uuid4(),
        resource_type="flow",
        resource_id=flow.id,
        scope=ShareScope.USER.value,
        target_id=uuid4(),  # targets someone else → hidden
        permission_level=SharePermissionLevel.READ.value,
        created_by=owner.id,
    )
    # First exec → the share rows; second exec → caller's (empty) team ids.
    session = _QueueSession({(Flow, flow.id): flow}, exec_queue=[[visible, hidden], []])

    results = await shares_module.list_shares(current_user=caller, session=session)
    ids = {r.id for r in results}
    assert visible.id in ids
    assert hidden.id not in ids
