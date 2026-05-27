"""Route-level tests for the new authz admin endpoints.

Covers ``/authz/roles``, ``/authz/role-assignments``, ``/authz/teams`` (+ members),
and ``/authz/me/permissions``. Focuses on the security floor (superuser gate),
input validation, conflict handling, and cycle detection — paths that protect
ops invariants and would silently break without coverage.

Pattern follows ``test_authz_share_routes.py`` — a fake async session + a stub
authz service installed via monkeypatch.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

# --- shared fakes ----------------------------------------------------- #


class _FakeAsyncSession:
    """Minimal async-session stand-in that records writes + commits."""

    def __init__(
        self,
        get_by_type: dict[tuple[type, UUID], Any] | None = None,
        *,
        exec_results: list[Any] | None = None,
        commit_raises: Exception | None = None,
    ) -> None:
        self._get_by_type = get_by_type or {}
        self._exec_results = exec_results or []
        self._commit_raises = commit_raises
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.committed = 0
        self.rolled_back = 0

    async def get(self, model: type, key: UUID) -> Any:
        return self._get_by_type.get((model, key))

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def delete(self, obj: Any) -> None:
        self.deleted.append(obj)

    async def commit(self) -> None:
        self.committed += 1
        if self._commit_raises is not None:
            raise self._commit_raises

    async def rollback(self) -> None:
        self.rolled_back += 1

    async def refresh(self, _obj: Any) -> None:
        return None

    async def exec(self, _stmt: Any):
        if not self._exec_results:
            return _ExecResult([])
        return _ExecResult(self._exec_results.pop(0))


class _ExecResult:
    """Mimics ``await session.exec(stmt)`` then ``.first()`` / ``.all()`` / iter."""

    def __init__(self, rows: list[Any]):
        self._rows = list(rows)

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return list(self._rows)

    def __iter__(self):
        return iter(self._rows)


class _StubAuthz:
    def __init__(self, *, allow: bool = True) -> None:
        self._allow = allow
        self.invalidate_user_calls: list[UUID] = []
        self.invalidate_role_calls: list[UUID] = []
        self.invalidate_all_calls = 0
        self.effective_perms_payload: dict[UUID, list[str]] | None = None

    async def supports_cross_user_fetch(self) -> bool:
        return False

    async def is_enabled(self) -> bool:
        return False

    async def enforce(self, **_kwargs) -> bool:
        return self._allow

    async def batch_enforce(self, **kwargs) -> list[bool]:
        return [self._allow] * len(kwargs.get("requests", []))

    async def invalidate_user(self, user_id: UUID) -> None:
        self.invalidate_user_calls.append(user_id)

    async def invalidate_role(self, role_id: UUID) -> None:
        self.invalidate_role_calls.append(role_id)

    async def invalidate_all(self) -> None:
        self.invalidate_all_calls += 1

    async def get_effective_permissions(self, **_kwargs) -> dict[UUID, list[str]]:
        return self.effective_perms_payload or {}


def _make_user(*, is_superuser: bool = False) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), is_superuser=is_superuser, username="u")


@pytest.fixture
def stub_authz(monkeypatch):
    from langflow.api.v1 import authz_me, authz_role_assignments, authz_roles, authz_teams

    def _apply(*, allow: bool = True) -> _StubAuthz:
        stub = _StubAuthz(allow=allow)
        for module in (authz_roles, authz_role_assignments, authz_teams, authz_me):
            monkeypatch.setattr(module, "get_authorization_service", lambda s=stub: s)
        return stub

    return _apply


# =====================================================================
# /authz/roles
# =====================================================================


@pytest.mark.asyncio
async def test_create_role_requires_superuser(stub_authz):
    from langflow.api.v1 import authz_roles
    from langflow.api.v1.schemas.authz_roles import RoleCreate

    stub_authz()
    session = _FakeAsyncSession()
    user = _make_user(is_superuser=False)
    payload = RoleCreate(name="custom", description=None, permissions=["flow:*:read"])

    with pytest.raises(HTTPException) as excinfo:
        await authz_roles.create_role(payload=payload, current_user=user, session=session)
    assert excinfo.value.status_code == 403
    assert session.added == []
    assert session.committed == 0


@pytest.mark.asyncio
async def test_create_role_persists_and_invalidates(stub_authz):
    from langflow.api.v1 import authz_roles
    from langflow.api.v1.schemas.authz_roles import RoleCreate
    from langflow.services.database.models.auth import AuthzRole  # noqa: F401 — keeps import path live

    authz = stub_authz()
    session = _FakeAsyncSession()
    user = _make_user(is_superuser=True)
    payload = RoleCreate(name="runner", description="x", permissions=["flow:*:execute"])

    result = await authz_roles.create_role(payload=payload, current_user=user, session=session)
    assert result.name == "runner"
    assert result.is_system is False
    assert len(session.added) == 1
    assert session.committed == 1
    assert authz.invalidate_all_calls == 1


@pytest.mark.asyncio
async def test_create_role_409_on_name_conflict(stub_authz):
    from langflow.api.v1 import authz_roles
    from langflow.api.v1.schemas.authz_roles import RoleCreate

    stub_authz()
    session = _FakeAsyncSession(commit_raises=IntegrityError("dup", {}, Exception()))
    user = _make_user(is_superuser=True)
    payload = RoleCreate(name="viewer", permissions=[])

    with pytest.raises(HTTPException) as excinfo:
        await authz_roles.create_role(payload=payload, current_user=user, session=session)
    assert excinfo.value.status_code == 409
    assert "already exists" in excinfo.value.detail
    assert session.rolled_back == 1


@pytest.mark.asyncio
async def test_update_role_blocks_system_role(stub_authz):
    from langflow.api.v1 import authz_roles
    from langflow.api.v1.schemas.authz_roles import RoleUpdate
    from langflow.services.database.models.auth import AuthzRole

    stub_authz()
    role_id = uuid4()
    system_role = SimpleNamespace(
        id=role_id,
        name="viewer",
        description=None,
        is_system=True,
        permissions=[],
        parent_role_id=None,
    )
    session = _FakeAsyncSession({(AuthzRole, role_id): system_role})
    user = _make_user(is_superuser=True)
    payload = RoleUpdate(name="hacked")

    with pytest.raises(HTTPException) as excinfo:
        await authz_roles.update_role(
            role_id=role_id,
            payload=payload,
            current_user=user,
            session=session,
        )
    assert excinfo.value.status_code == 400
    assert "System roles" in excinfo.value.detail


@pytest.mark.asyncio
async def test_update_role_rejects_self_parent(stub_authz):
    from langflow.api.v1 import authz_roles
    from langflow.api.v1.schemas.authz_roles import RoleUpdate
    from langflow.services.database.models.auth import AuthzRole

    stub_authz()
    role_id = uuid4()
    role = SimpleNamespace(
        id=role_id,
        name="custom",
        description=None,
        is_system=False,
        permissions=[],
        parent_role_id=None,
    )
    session = _FakeAsyncSession({(AuthzRole, role_id): role})
    user = _make_user(is_superuser=True)
    payload = RoleUpdate(parent_role_id=role_id)

    with pytest.raises(HTTPException) as excinfo:
        await authz_roles.update_role(
            role_id=role_id,
            payload=payload,
            current_user=user,
            session=session,
        )
    assert excinfo.value.status_code == 400
    assert "cannot be its own parent" in excinfo.value.detail


@pytest.mark.asyncio
async def test_delete_role_409_when_assigned(stub_authz):
    from langflow.api.v1 import authz_roles
    from langflow.services.database.models.auth import AuthzRole, AuthzRoleAssignment  # noqa: F401

    stub_authz()
    role_id = uuid4()
    role = SimpleNamespace(id=role_id, is_system=False)
    # First exec is the "is anyone assigned?" probe — return a fake assignment.
    fake_assignment = SimpleNamespace(id=uuid4())
    session = _FakeAsyncSession(
        {(AuthzRole, role_id): role},
        exec_results=[[fake_assignment]],
    )
    user = _make_user(is_superuser=True)

    with pytest.raises(HTTPException) as excinfo:
        await authz_roles.delete_role(role_id=role_id, current_user=user, session=session)
    assert excinfo.value.status_code == 409
    assert "active assignments" in excinfo.value.detail
    assert session.deleted == []


@pytest.mark.asyncio
async def test_delete_role_blocks_system_role(stub_authz):
    from langflow.api.v1 import authz_roles
    from langflow.services.database.models.auth import AuthzRole

    stub_authz()
    role_id = uuid4()
    role = SimpleNamespace(id=role_id, is_system=True)
    session = _FakeAsyncSession({(AuthzRole, role_id): role})
    user = _make_user(is_superuser=True)

    with pytest.raises(HTTPException) as excinfo:
        await authz_roles.delete_role(role_id=role_id, current_user=user, session=session)
    assert excinfo.value.status_code == 400
    assert "System roles" in excinfo.value.detail


# =====================================================================
# /authz/role-assignments
# =====================================================================


@pytest.mark.asyncio
async def test_list_assignments_non_superuser_blocked_from_other_user(stub_authz):
    from langflow.api.v1 import authz_role_assignments

    stub_authz()
    session = _FakeAsyncSession()
    user = _make_user(is_superuser=False)
    other_user_id = uuid4()

    with pytest.raises(HTTPException) as excinfo:
        await authz_role_assignments.list_assignments(
            session=session,
            current_user=user,
            user_id=other_user_id,
        )
    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_list_assignments_self_allowed_for_non_superuser(stub_authz):
    from langflow.api.v1 import authz_role_assignments

    stub_authz()
    session = _FakeAsyncSession(exec_results=[[]])  # empty list
    user = _make_user(is_superuser=False)

    result = await authz_role_assignments.list_assignments(
        session=session,
        current_user=user,
        user_id=user.id,
    )
    assert result == []


@pytest.mark.asyncio
async def test_create_assignment_invalid_user_404(stub_authz):
    from langflow.api.v1 import authz_role_assignments
    from langflow.api.v1.schemas.authz_role_assignments import RoleAssignmentCreate

    stub_authz()
    session = _FakeAsyncSession()  # get() returns None
    user = _make_user(is_superuser=True)
    payload = RoleAssignmentCreate(user_id=uuid4(), role_id=uuid4())

    with pytest.raises(HTTPException) as excinfo:
        await authz_role_assignments.create_assignment(
            payload=payload,
            current_user=user,
            session=session,
        )
    assert excinfo.value.status_code == 404
    assert "user_id" in excinfo.value.detail


@pytest.mark.asyncio
async def test_create_assignment_invokes_invalidate_user(stub_authz):
    from langflow.api.v1 import authz_role_assignments
    from langflow.api.v1.schemas.authz_role_assignments import RoleAssignmentCreate
    from langflow.services.database.models.auth import AuthzRole
    from langflow.services.database.models.user.model import User

    authz = stub_authz()
    target_user = SimpleNamespace(id=uuid4())
    role = SimpleNamespace(id=uuid4(), name="viewer")
    session = _FakeAsyncSession(
        {(User, target_user.id): target_user, (AuthzRole, role.id): role},
    )
    actor = _make_user(is_superuser=True)
    payload = RoleAssignmentCreate(user_id=target_user.id, role_id=role.id)

    await authz_role_assignments.create_assignment(
        payload=payload,
        current_user=actor,
        session=session,
    )
    assert len(session.added) == 1
    assert session.committed == 1
    assert authz.invalidate_user_calls == [target_user.id]


# =====================================================================
# /authz/teams
# =====================================================================


@pytest.mark.asyncio
async def test_create_team_requires_superuser(stub_authz):
    from langflow.api.v1 import authz_teams
    from langflow.api.v1.schemas.authz_teams import TeamCreate

    stub_authz()
    session = _FakeAsyncSession()
    user = _make_user(is_superuser=False)
    payload = TeamCreate(team_name="Eng", adom_name="eng")

    with pytest.raises(HTTPException) as excinfo:
        await authz_teams.create_team(payload=payload, current_user=user, session=session)
    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_add_member_invalidates_target_user(stub_authz):
    from langflow.api.v1 import authz_teams
    from langflow.api.v1.schemas.authz_teams import TeamMemberCreate
    from langflow.services.database.models.auth import AuthzTeam
    from langflow.services.database.models.user.model import User

    authz = stub_authz()
    team = SimpleNamespace(id=uuid4(), team_name="Eng")
    target_user = SimpleNamespace(id=uuid4())
    session = _FakeAsyncSession(
        {(AuthzTeam, team.id): team, (User, target_user.id): target_user},
    )
    actor = _make_user(is_superuser=True)
    payload = TeamMemberCreate(user_id=target_user.id)

    await authz_teams.add_member(
        team_id=team.id,
        payload=payload,
        current_user=actor,
        session=session,
    )
    assert len(session.added) == 1
    assert authz.invalidate_user_calls == [target_user.id]


@pytest.mark.asyncio
async def test_add_member_duplicate_returns_409(stub_authz):
    from langflow.api.v1 import authz_teams
    from langflow.api.v1.schemas.authz_teams import TeamMemberCreate
    from langflow.services.database.models.auth import AuthzTeam
    from langflow.services.database.models.user.model import User

    stub_authz()
    team = SimpleNamespace(id=uuid4(), team_name="Eng")
    target_user = SimpleNamespace(id=uuid4())
    session = _FakeAsyncSession(
        {(AuthzTeam, team.id): team, (User, target_user.id): target_user},
        commit_raises=IntegrityError("dup", {}, Exception()),
    )
    actor = _make_user(is_superuser=True)
    payload = TeamMemberCreate(user_id=target_user.id)

    with pytest.raises(HTTPException) as excinfo:
        await authz_teams.add_member(
            team_id=team.id,
            payload=payload,
            current_user=actor,
            session=session,
        )
    assert excinfo.value.status_code == 409
    assert "already a member" in excinfo.value.detail


# =====================================================================
# /authz/me/permissions
# =====================================================================


@pytest.mark.asyncio
async def test_me_permissions_returns_per_resource_actions(stub_authz):
    from langflow.api.v1 import authz_me
    from langflow.api.v1.authz_me import EffectivePermissionsRequest

    authz = stub_authz()
    resource_ids = [uuid4(), uuid4()]
    authz.effective_perms_payload = {
        resource_ids[0]: ["read", "execute"],
        resource_ids[1]: ["read", "write", "execute", "delete"],
    }
    user = _make_user()

    body = EffectivePermissionsRequest(
        resource_type="flow",
        resource_ids=resource_ids,
    )
    result = await authz_me.get_effective_permissions(body=body, current_user=user)
    assert result.resource_type == "flow"
    assert set(result.permissions[resource_ids[0]]) == {"read", "execute"}
    assert "delete" in result.permissions[resource_ids[1]]


@pytest.mark.asyncio
async def test_me_permissions_caps_resource_ids_at_500(stub_authz):
    from langflow.api.v1 import authz_me
    from langflow.api.v1.authz_me import EffectivePermissionsRequest

    stub_authz()
    user = _make_user()

    body = EffectivePermissionsRequest(
        resource_type="flow",
        resource_ids=[uuid4() for _ in range(501)],
    )
    with pytest.raises(HTTPException) as excinfo:
        await authz_me.get_effective_permissions(body=body, current_user=user)
    assert excinfo.value.status_code == 400
    assert "capped at 500" in excinfo.value.detail


@pytest.mark.asyncio
async def test_me_permissions_empty_request_returns_empty(stub_authz):
    from langflow.api.v1 import authz_me
    from langflow.api.v1.authz_me import EffectivePermissionsRequest

    stub_authz()
    user = _make_user()

    body = EffectivePermissionsRequest(resource_type="flow", resource_ids=[])
    result = await authz_me.get_effective_permissions(body=body, current_user=user)
    assert result.permissions == {}
