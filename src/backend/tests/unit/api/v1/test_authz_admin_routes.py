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


def _make_role_row(
    *,
    id: UUID,  # noqa: A002
    name: str,
    description: str | None,
    permissions: list[str],
    parent_role_id: UUID | None,
    is_system: bool = False,
) -> SimpleNamespace:
    """Build a fake AuthzRole row carrying every field RoleRead serializes."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=id,
        name=name,
        description=description,
        is_system=is_system,
        permissions=permissions,
        parent_role_id=parent_role_id,
        workspace_id=None,
        created_at=now,
        updated_at=now,
        created_by=None,
    )


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


def test_role_create_accepts_canonical_permission_slugs():
    """``<resource>:<action>`` slugs from the system-role catalog parse cleanly."""
    from langflow.api.v1.schemas.authz_roles import RoleCreate

    payload = RoleCreate(
        name="ops",
        permissions=[
            "flow:read",
            "flow:execute",
            "flow:deploy",  # deploy is a FLOW action, not deployment
            "deployment:execute",
            "share:create",
            "knowledge_base:ingest",
            "file:*",
        ],
    )
    # Wildcard action survives intact, no normalization surprises.
    assert payload.permissions[-1] == "file:*"


@pytest.mark.parametrize(
    "bad_slug",
    [
        "flow:*:read",  # legacy three-segment form rejected
        "flow",  # missing action
        "flow:read:extra",  # too many segments
        "Flow:read",  # uppercase resource
        "flow:READ",  # uppercase action
        "unknown:read",  # unknown resource
        "flow:invent",  # unknown action
        "*:read",  # resource wildcard not allowed
        "",  # empty
        # Per-resource action validation — these are syntactically valid
        # ``<resource>:<action>`` slugs whose action doesn't belong to that
        # resource's enum. Independent validation would let them through.
        "file:deploy",  # deploy is a flow-only action
        "share:execute",  # execute isn't a share action
        "project:ingest",  # ingest is knowledge_base-only
        "deployment:deploy",  # deploy is flow-only — deployments use execute
        "share:write",  # write isn't a share action
        "variable:execute",  # variables aren't executed
    ],
)
def test_role_create_rejects_non_canonical_permission_slugs(bad_slug):
    """Anything outside the canonical ``<resource>:<action>`` form is 422 at the API boundary."""
    from langflow.api.v1.schemas.authz_roles import RoleCreate
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RoleCreate(name="bad", permissions=[bad_slug])


@pytest.mark.parametrize(
    "good_slug",
    [
        # Action that's valid on its own resource shouldn't false-positive
        # the per-resource check. Cover the cross-product edges that the
        # bad-slug parametrize complements. ``deploy`` is intentionally
        # flow-only (matches FlowAction.DEPLOY); deployments use execute.
        "flow:deploy",
        "flow:execute",
        "deployment:execute",
        "knowledge_base:ingest",
        "share:update",
        "share:create",
        "file:read",
        "variable:write",
        "project:delete",
        # Wildcard remains valid on every resource.
        "flow:*",
        "share:*",
        "knowledge_base:*",
    ],
)
def test_role_create_accepts_per_resource_action_pairs(good_slug):
    """Per-resource validation must still accept every (resource, action) the enums define."""
    from langflow.api.v1.schemas.authz_roles import RoleCreate

    payload = RoleCreate(name="ok", permissions=[good_slug])
    assert payload.permissions == [good_slug]


def test_role_update_validates_permissions_when_provided():
    """RoleUpdate also runs the slug validator (so PATCH cannot smuggle bad slugs in)."""
    from langflow.api.v1.schemas.authz_roles import RoleUpdate
    from pydantic import ValidationError

    # None is still allowed (the handler maps it to a 400 separately).
    RoleUpdate(permissions=None)
    # Empty list is the canonical "clear permissions" payload.
    RoleUpdate(permissions=[])
    # Valid slugs pass.
    RoleUpdate(permissions=["flow:read", "deployment:execute"])
    # A single bad slug fails the whole payload.
    with pytest.raises(ValidationError):
        RoleUpdate(permissions=["flow:read", "flow:*:read"])


@pytest.mark.asyncio
async def test_create_role_requires_superuser(stub_authz):
    from langflow.api.v1 import authz_roles
    from langflow.api.v1.schemas.authz_roles import RoleCreate

    stub_authz()
    session = _FakeAsyncSession()
    user = _make_user(is_superuser=False)
    payload = RoleCreate(name="custom", description=None, permissions=["flow:read"])

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
    payload = RoleCreate(name="runner", description="x", permissions=["flow:execute"])

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
async def test_update_role_clears_description_via_explicit_null(stub_authz):
    """PATCH with description=null clears the field — presence check honors null."""
    from langflow.api.v1 import authz_roles
    from langflow.api.v1.schemas.authz_roles import RoleUpdate
    from langflow.services.database.models.auth import AuthzRole

    stub_authz()
    role_id = uuid4()
    role = _make_role_row(
        id=role_id,
        name="custom",
        description="old description",
        permissions=[],
        parent_role_id=None,
    )
    session = _FakeAsyncSession({(AuthzRole, role_id): role})
    user = _make_user(is_superuser=True)
    payload = RoleUpdate(description=None)
    # Sanity: description is in model_fields_set even though it's None
    assert "description" in payload.model_fields_set

    await authz_roles.update_role(
        role_id=role_id,
        payload=payload,
        current_user=user,
        session=session,
    )
    assert role.description is None


@pytest.mark.asyncio
async def test_update_role_clears_parent_via_explicit_null(stub_authz):
    """PATCH with parent_role_id=null removes the parent (no validation needed)."""
    from langflow.api.v1 import authz_roles
    from langflow.api.v1.schemas.authz_roles import RoleUpdate
    from langflow.services.database.models.auth import AuthzRole

    stub_authz()
    role_id = uuid4()
    role = _make_role_row(
        id=role_id,
        name="custom",
        description=None,
        permissions=[],
        parent_role_id=uuid4(),
    )
    session = _FakeAsyncSession({(AuthzRole, role_id): role})
    user = _make_user(is_superuser=True)
    payload = RoleUpdate(parent_role_id=None)
    assert "parent_role_id" in payload.model_fields_set

    await authz_roles.update_role(
        role_id=role_id,
        payload=payload,
        current_user=user,
        session=session,
    )
    assert role.parent_role_id is None


@pytest.mark.asyncio
async def test_update_role_omitted_fields_untouched(stub_authz):
    """Omitting a field leaves the existing row value alone (no clearing)."""
    from langflow.api.v1 import authz_roles
    from langflow.api.v1.schemas.authz_roles import RoleUpdate
    from langflow.services.database.models.auth import AuthzRole

    stub_authz()
    role_id = uuid4()
    parent_id = uuid4()
    role = _make_role_row(
        id=role_id,
        name="custom",
        description="keep me",
        permissions=["flow:read"],
        parent_role_id=parent_id,
    )
    session = _FakeAsyncSession({(AuthzRole, role_id): role})
    user = _make_user(is_superuser=True)
    # Only update name — description, permissions, parent_role_id must stay.
    payload = RoleUpdate(name="renamed")

    await authz_roles.update_role(
        role_id=role_id,
        payload=payload,
        current_user=user,
        session=session,
    )
    assert role.name == "renamed"
    assert role.description == "keep me"
    assert role.permissions == ["flow:read"]
    assert role.parent_role_id == parent_id


@pytest.mark.asyncio
async def test_update_role_rejects_null_name(stub_authz):
    """Explicit name=null returns 400 (DB column is NOT NULL)."""
    from langflow.api.v1 import authz_roles
    from langflow.api.v1.schemas.authz_roles import RoleUpdate
    from langflow.services.database.models.auth import AuthzRole

    stub_authz()
    role_id = uuid4()
    role = _make_role_row(
        id=role_id,
        name="custom",
        description=None,
        permissions=[],
        parent_role_id=None,
    )
    session = _FakeAsyncSession({(AuthzRole, role_id): role})
    user = _make_user(is_superuser=True)
    payload = RoleUpdate(name=None)

    with pytest.raises(HTTPException) as excinfo:
        await authz_roles.update_role(
            role_id=role_id,
            payload=payload,
            current_user=user,
            session=session,
        )
    assert excinfo.value.status_code == 400
    assert "name cannot be null" in excinfo.value.detail


@pytest.mark.asyncio
async def test_update_role_clears_permissions_via_empty_list(stub_authz):
    """An empty permissions list is the natural 'clear' — distinct from null."""
    from langflow.api.v1 import authz_roles
    from langflow.api.v1.schemas.authz_roles import RoleUpdate
    from langflow.services.database.models.auth import AuthzRole

    stub_authz()
    role_id = uuid4()
    role = _make_role_row(
        id=role_id,
        name="custom",
        description=None,
        permissions=["flow:read", "flow:write"],
        parent_role_id=None,
    )
    session = _FakeAsyncSession({(AuthzRole, role_id): role})
    user = _make_user(is_superuser=True)
    payload = RoleUpdate(permissions=[])

    await authz_roles.update_role(
        role_id=role_id,
        payload=payload,
        current_user=user,
        session=session,
    )
    assert role.permissions == []


@pytest.mark.asyncio
async def test_update_role_rejects_null_permissions(stub_authz):
    """Explicit permissions=null returns 400 (DB column is nullable=False)."""
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
        permissions=["flow:read"],
        parent_role_id=None,
        updated_at=None,
    )
    session = _FakeAsyncSession({(AuthzRole, role_id): role})
    user = _make_user(is_superuser=True)
    payload = RoleUpdate(permissions=None)

    with pytest.raises(HTTPException) as excinfo:
        await authz_roles.update_role(
            role_id=role_id,
            payload=payload,
            current_user=user,
            session=session,
        )
    assert excinfo.value.status_code == 400
    assert "permissions cannot be null" in excinfo.value.detail


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


def test_role_assignment_create_global_must_omit_domain_id():
    """``domain_type='global'`` with a ``domain_id`` is a 422 — the row would not match any domain."""
    from langflow.api.v1.schemas.authz_role_assignments import RoleAssignmentCreate
    from pydantic import ValidationError

    # Allowed: global + null id
    RoleAssignmentCreate(user_id=uuid4(), role_id=uuid4())
    # Rejected: global + non-null id
    with pytest.raises(ValidationError):
        RoleAssignmentCreate(
            user_id=uuid4(),
            role_id=uuid4(),
            domain_type="global",
            domain_id=uuid4(),
        )


@pytest.mark.parametrize("domain_type", ["org", "workspace", "project"])
def test_role_assignment_create_scoped_requires_domain_id(domain_type):
    """Scoped ``domain_type`` values without ``domain_id`` are 422."""
    from langflow.api.v1.schemas.authz_role_assignments import RoleAssignmentCreate
    from pydantic import ValidationError

    # Allowed when paired with an id
    RoleAssignmentCreate(
        user_id=uuid4(),
        role_id=uuid4(),
        domain_type=domain_type,
        domain_id=uuid4(),
    )
    # Rejected without an id
    with pytest.raises(ValidationError):
        RoleAssignmentCreate(
            user_id=uuid4(),
            role_id=uuid4(),
            domain_type=domain_type,
        )


def test_role_assignment_create_rejects_unknown_domain_type():
    """Free-form ``domain_type`` strings are 422 (typo guard)."""
    from langflow.api.v1.schemas.authz_role_assignments import RoleAssignmentCreate
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RoleAssignmentCreate(
            user_id=uuid4(),
            role_id=uuid4(),
            domain_type="organization",  # not in the Literal
            domain_id=uuid4(),
        )


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
async def test_list_assignments_no_user_id_defaults_to_self(stub_authz):
    """Omitting ``user_id`` scopes to the caller — no superuser required."""
    from langflow.api.v1 import authz_role_assignments

    stub_authz()
    session = _FakeAsyncSession(exec_results=[[]])
    user = _make_user(is_superuser=False)

    # No user_id passed — should NOT raise 403 (was the bug) and should return
    # the caller's own assignments (empty in this fake-session fixture).
    result = await authz_role_assignments.list_assignments(
        session=session,
        current_user=user,
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


def _make_team_row(
    *,
    id: UUID,  # noqa: A002
    team_name: str = "Eng",
    adom_name: str = "eng",
    description: str | None = "desc",
    is_active: bool = True,
) -> SimpleNamespace:
    """Build a fake AuthzTeam row carrying every field TeamRead serializes."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=id,
        team_name=team_name,
        adom_name=adom_name,
        description=description,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_update_team_clears_description_via_explicit_null(stub_authz):
    """PATCH with description=null clears the field via presence check."""
    from langflow.api.v1 import authz_teams
    from langflow.api.v1.schemas.authz_teams import TeamUpdate
    from langflow.services.database.models.auth import AuthzTeam

    stub_authz()
    team_id = uuid4()
    team = _make_team_row(id=team_id, description="old description")
    session = _FakeAsyncSession({(AuthzTeam, team_id): team})
    user = _make_user(is_superuser=True)
    payload = TeamUpdate(description=None)
    assert "description" in payload.model_fields_set

    await authz_teams.update_team(
        team_id=team_id,
        payload=payload,
        current_user=user,
        session=session,
    )
    assert team.description is None


@pytest.mark.asyncio
async def test_update_team_omitted_description_untouched(stub_authz):
    """Omitting description leaves the existing value alone."""
    from langflow.api.v1 import authz_teams
    from langflow.api.v1.schemas.authz_teams import TeamUpdate
    from langflow.services.database.models.auth import AuthzTeam

    stub_authz()
    team_id = uuid4()
    team = _make_team_row(id=team_id, description="keep me")
    session = _FakeAsyncSession({(AuthzTeam, team_id): team})
    user = _make_user(is_superuser=True)
    # Only update team_name — description must stay "keep me".
    payload = TeamUpdate(team_name="Renamed")

    await authz_teams.update_team(
        team_id=team_id,
        payload=payload,
        current_user=user,
        session=session,
    )
    assert team.team_name == "Renamed"
    assert team.description == "keep me"


@pytest.mark.asyncio
async def test_update_team_display_only_change_skips_invalidate_all(stub_authz):
    """Renaming or re-describing a team doesn't touch policy — no cache flush."""
    from langflow.api.v1 import authz_teams
    from langflow.api.v1.schemas.authz_teams import TeamUpdate
    from langflow.services.database.models.auth import AuthzTeam

    authz = stub_authz()
    team_id = uuid4()
    team = _make_team_row(id=team_id, team_name="Eng", adom_name="eng", is_active=True)
    session = _FakeAsyncSession({(AuthzTeam, team_id): team})
    user = _make_user(is_superuser=True)

    await authz_teams.update_team(
        team_id=team_id,
        payload=TeamUpdate(team_name="Engineering", description="new desc"),
        current_user=user,
        session=session,
    )
    assert authz.invalidate_all_calls == 0


@pytest.mark.asyncio
async def test_update_team_adom_change_triggers_invalidate_all(stub_authz):
    """``adom_name`` is the slug a plugin may compile against — invalidate on change."""
    from langflow.api.v1 import authz_teams
    from langflow.api.v1.schemas.authz_teams import TeamUpdate
    from langflow.services.database.models.auth import AuthzTeam

    authz = stub_authz()
    team_id = uuid4()
    team = _make_team_row(id=team_id, adom_name="eng")
    session = _FakeAsyncSession({(AuthzTeam, team_id): team})
    user = _make_user(is_superuser=True)

    await authz_teams.update_team(
        team_id=team_id,
        payload=TeamUpdate(adom_name="engineering"),
        current_user=user,
        session=session,
    )
    assert authz.invalidate_all_calls == 1


@pytest.mark.asyncio
async def test_update_team_is_active_change_triggers_invalidate_all(stub_authz):
    """Deactivating a team must take effect on the next enforce call."""
    from langflow.api.v1 import authz_teams
    from langflow.api.v1.schemas.authz_teams import TeamUpdate
    from langflow.services.database.models.auth import AuthzTeam

    authz = stub_authz()
    team_id = uuid4()
    team = _make_team_row(id=team_id, is_active=True)
    session = _FakeAsyncSession({(AuthzTeam, team_id): team})
    user = _make_user(is_superuser=True)

    await authz_teams.update_team(
        team_id=team_id,
        payload=TeamUpdate(is_active=False),
        current_user=user,
        session=session,
    )
    assert authz.invalidate_all_calls == 1


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


# --- actions validation: normalize, dedupe, cap ---------------------- #


def test_me_permissions_actions_normalized_and_deduped():
    """`["READ", "read", " Write "]` -> `["read", "write"]`."""
    from langflow.api.v1.authz_me import EffectivePermissionsRequest

    body = EffectivePermissionsRequest(
        resource_type="flow",
        resource_ids=[uuid4()],
        actions=["READ", "read", " Write ", "WRITE"],
    )
    assert body.actions == ["read", "write"]


def test_me_permissions_actions_empty_after_normalization_becomes_none():
    """All-whitespace input collapses to None so the handler falls back to defaults."""
    from langflow.api.v1.authz_me import EffectivePermissionsRequest

    body = EffectivePermissionsRequest(
        resource_type="flow",
        resource_ids=[uuid4()],
        actions=["", "   ", ""],
    )
    assert body.actions is None


def test_me_permissions_actions_over_cap_rejected():
    """More than 10 unique actions -> ValidationError (HTTP 422 at request boundary)."""
    from langflow.api.v1.authz_me import EffectivePermissionsRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as excinfo:
        EffectivePermissionsRequest(
            resource_type="flow",
            resource_ids=[uuid4()],
            actions=[f"action{i}" for i in range(11)],
        )
    assert "capped at 10" in str(excinfo.value)


def test_me_permissions_actions_dedupe_keeps_under_cap():
    """A 50-entry input with only 3 distinct values normalizes successfully."""
    from langflow.api.v1.authz_me import EffectivePermissionsRequest

    body = EffectivePermissionsRequest(
        resource_type="flow",
        resource_ids=[uuid4()],
        actions=["read", "write", "execute"] * 50,
    )
    assert body.actions == ["read", "write", "execute"]


def test_me_permissions_actions_none_stays_none():
    """Omitting actions stays None so the handler substitutes _DEFAULT_ACTIONS."""
    from langflow.api.v1.authz_me import EffectivePermissionsRequest

    body = EffectivePermissionsRequest(resource_type="flow", resource_ids=[uuid4()])
    assert body.actions is None


@pytest.mark.asyncio
async def test_me_permissions_handler_uses_normalized_actions(stub_authz):
    """The handler passes the normalized list (not the raw input) to the service."""
    from langflow.api.v1 import authz_me
    from langflow.api.v1.authz_me import EffectivePermissionsRequest

    authz = stub_authz()
    # Capture what the handler forwards to get_effective_permissions.
    captured: dict = {}

    async def _capture(**kwargs):
        captured.update(kwargs)
        return {rid: [] for rid in kwargs["resource_ids"]}

    authz.get_effective_permissions = _capture

    user = _make_user()
    rid = uuid4()
    body = EffectivePermissionsRequest(
        resource_type="flow",
        resource_ids=[rid],
        actions=["READ", "read", " Write "],
    )
    await authz_me.get_effective_permissions(body=body, current_user=user)
    # Normalization happened at the model layer; handler sees the bounded set.
    assert tuple(captured["actions"]) == ("read", "write")


# =====================================================================
# Cache-invalidation failure semantics
#
# The route handlers commit a policy-relevant DB change before asking the
# plugin to drop its cached decisions. A naive ``await invalidate_user(...)``
# would surface a plugin RPC failure as an API 5xx — leaving the DB write
# durable while the caller believes the mutation failed.
#
# ``safe_invalidate_*`` in services/authorization/invalidation.py instead
# (1) catches the plugin failure, (2) falls back to invalidate_all, and
# (3) never raises. Cover both grant and revoke paths so a regression to
# the un-safe pattern fails loudly.
# =====================================================================


class _FailingInvalidateUserAuthz(_StubAuthz):
    """Stub that raises on invalidate_user; tracks invalidate_all fallback."""

    def __init__(self, *, fail_invalidate_all: bool = False) -> None:
        super().__init__(allow=True)
        self._fail_invalidate_all = fail_invalidate_all

    async def invalidate_user(self, user_id: UUID) -> None:  # type: ignore[override]
        self.invalidate_user_calls.append(user_id)
        msg = "plugin RPC failure"
        raise RuntimeError(msg)

    async def invalidate_all(self) -> None:  # type: ignore[override]
        self.invalidate_all_calls += 1
        if self._fail_invalidate_all:
            msg = "plugin invalidate_all failure"
            raise RuntimeError(msg)


@pytest.fixture
def failing_invalidate_authz(monkeypatch):
    """Install a stub whose invalidate_user raises; assert no 5xx leaks out."""
    from langflow.api.v1 import authz_role_assignments, authz_roles, authz_teams

    def _apply(*, fail_invalidate_all: bool = False) -> _FailingInvalidateUserAuthz:
        stub = _FailingInvalidateUserAuthz(fail_invalidate_all=fail_invalidate_all)
        for module in (authz_roles, authz_role_assignments, authz_teams):
            monkeypatch.setattr(module, "get_authorization_service", lambda s=stub: s)
        return stub

    return _apply


@pytest.mark.asyncio
async def test_create_assignment_succeeds_when_invalidate_user_fails(failing_invalidate_authz):
    """Grant: DB write is durable, so a plugin invalidation failure must NOT 5xx."""
    from langflow.api.v1 import authz_role_assignments
    from langflow.api.v1.schemas.authz_role_assignments import RoleAssignmentCreate
    from langflow.services.database.models.auth import AuthzRole
    from langflow.services.database.models.user.model import User

    authz = failing_invalidate_authz()
    target_user = SimpleNamespace(id=uuid4())
    role = SimpleNamespace(id=uuid4(), name="viewer")
    session = _FakeAsyncSession(
        {(User, target_user.id): target_user, (AuthzRole, role.id): role},
    )
    actor = _make_user(is_superuser=True)
    payload = RoleAssignmentCreate(user_id=target_user.id, role_id=role.id)

    # Must NOT raise — the durable commit happened before invalidation.
    await authz_role_assignments.create_assignment(
        payload=payload,
        current_user=actor,
        session=session,
    )
    assert session.committed == 1
    # invalidate_user was attempted (and raised), then invalidate_all fallback ran.
    assert authz.invalidate_user_calls == [target_user.id]
    assert authz.invalidate_all_calls == 1


@pytest.mark.asyncio
async def test_delete_assignment_succeeds_when_invalidate_user_fails(failing_invalidate_authz):
    """Revoke: stale cache risk is sharpest here — must still report success and flush."""
    from langflow.api.v1 import authz_role_assignments
    from langflow.services.database.models.auth import AuthzRoleAssignment

    authz = failing_invalidate_authz()
    assignment_id = uuid4()
    target_user_id = uuid4()
    assignment = SimpleNamespace(
        id=assignment_id,
        user_id=target_user_id,
        role_id=uuid4(),
        domain_type="global",
        domain_id=None,
    )
    session = _FakeAsyncSession({(AuthzRoleAssignment, assignment_id): assignment})
    actor = _make_user(is_superuser=True)

    await authz_role_assignments.delete_assignment(
        assignment_id=assignment_id,
        current_user=actor,
        session=session,
    )
    assert session.deleted == [assignment]
    assert session.committed == 1
    assert authz.invalidate_user_calls == [target_user_id]
    assert authz.invalidate_all_calls == 1  # fallback fired


@pytest.mark.asyncio
async def test_delete_assignment_succeeds_when_both_invalidations_fail(failing_invalidate_authz):
    """Total invalidation failure is logged but still doesn't propagate — DB is durable."""
    from langflow.api.v1 import authz_role_assignments
    from langflow.services.database.models.auth import AuthzRoleAssignment

    authz = failing_invalidate_authz(fail_invalidate_all=True)
    assignment_id = uuid4()
    target_user_id = uuid4()
    assignment = SimpleNamespace(
        id=assignment_id,
        user_id=target_user_id,
        role_id=uuid4(),
        domain_type="global",
        domain_id=None,
    )
    session = _FakeAsyncSession({(AuthzRoleAssignment, assignment_id): assignment})
    actor = _make_user(is_superuser=True)

    # Even with both calls failing, the API must return success — there is no
    # way to undo a durable DB delete and a 5xx would just confuse the caller.
    await authz_role_assignments.delete_assignment(
        assignment_id=assignment_id,
        current_user=actor,
        session=session,
    )
    assert authz.invalidate_user_calls == [target_user_id]
    assert authz.invalidate_all_calls == 1


@pytest.mark.asyncio
async def test_remove_member_succeeds_when_invalidate_user_fails(failing_invalidate_authz):
    """Team membership revoke: same stale-cache concern as role-assignment revoke."""
    from langflow.api.v1 import authz_teams

    authz = failing_invalidate_authz()
    team_id = uuid4()
    user_id = uuid4()
    member = SimpleNamespace(team_id=team_id, user_id=user_id)
    session = _FakeAsyncSession(exec_results=[[member]])
    actor = _make_user(is_superuser=True)

    await authz_teams.remove_member(
        team_id=team_id,
        user_id=user_id,
        current_user=actor,
        session=session,
    )
    assert session.deleted == [member]
    assert session.committed == 1
    assert authz.invalidate_user_calls == [user_id]
    assert authz.invalidate_all_calls == 1


# Direct unit tests on the safe-invalidate helpers — keeps the contract
# (catches, falls back, never raises) covered even if every route handler
# is refactored later.


@pytest.mark.asyncio
async def test_safe_invalidate_user_falls_back_to_invalidate_all():
    """Helper-level test: invalidate_user raises, invalidate_all is attempted."""
    from langflow.services.authorization.invalidation import safe_invalidate_user

    stub = _FailingInvalidateUserAuthz()
    user_id = uuid4()

    # Must NOT raise.
    await safe_invalidate_user(stub, user_id, op="test")
    assert stub.invalidate_user_calls == [user_id]
    assert stub.invalidate_all_calls == 1


@pytest.mark.asyncio
async def test_safe_invalidate_user_swallows_invalidate_all_failure():
    """Helper-level test: both invalidations fail; the helper still returns cleanly."""
    from langflow.services.authorization.invalidation import safe_invalidate_user

    stub = _FailingInvalidateUserAuthz(fail_invalidate_all=True)
    user_id = uuid4()

    await safe_invalidate_user(stub, user_id, op="test")  # MUST NOT raise
    assert stub.invalidate_user_calls == [user_id]
    assert stub.invalidate_all_calls == 1


@pytest.mark.asyncio
async def test_safe_invalidate_user_happy_path_skips_invalidate_all():
    """Helper-level test: successful invalidate_user does NOT trigger fallback."""
    from langflow.services.authorization.invalidation import safe_invalidate_user

    stub = _StubAuthz()
    user_id = uuid4()
    await safe_invalidate_user(stub, user_id, op="test")
    assert stub.invalidate_user_calls == [user_id]
    assert stub.invalidate_all_calls == 0


# =====================================================================
# Pagination on list endpoints
#
# All three of list_roles / list_teams / list_members / list_assignments
# take ``limit`` (1..200) and ``offset`` (>=0) so an authenticated client
# can't enumerate the entire catalog in one call.
# =====================================================================


@pytest.mark.asyncio
async def test_list_roles_passes_limit_offset_to_query(stub_authz):
    """Listing roles applies the limit/offset args to the SQL statement."""
    from langflow.api.v1 import authz_roles

    stub_authz()
    # Record the executed statement so we can inspect the LIMIT/OFFSET clause.
    captured: dict = {}

    class _RecordingSession(_FakeAsyncSession):
        async def exec(self, stmt):  # type: ignore[override]
            captured["stmt"] = stmt
            return _ExecResult([])

    session = _RecordingSession()
    user = _make_user()

    await authz_roles.list_roles(
        session=session,
        current_user=user,
        limit=25,
        offset=50,
    )
    compiled = str(captured["stmt"].compile(compile_kwargs={"literal_binds": True}))
    assert "LIMIT 25" in compiled
    assert "OFFSET 50" in compiled


@pytest.mark.asyncio
async def test_list_teams_passes_limit_offset_to_query(stub_authz):
    from langflow.api.v1 import authz_teams

    stub_authz()
    captured: dict = {}

    class _RecordingSession(_FakeAsyncSession):
        async def exec(self, stmt):  # type: ignore[override]
            captured["stmt"] = stmt
            return _ExecResult([])

    session = _RecordingSession()
    user = _make_user()

    await authz_teams.list_teams(
        session=session,
        current_user=user,
        limit=10,
        offset=200,
    )
    compiled = str(captured["stmt"].compile(compile_kwargs={"literal_binds": True}))
    assert "LIMIT 10" in compiled
    assert "OFFSET 200" in compiled


@pytest.mark.asyncio
async def test_list_members_passes_limit_offset_to_query(stub_authz):
    from langflow.api.v1 import authz_teams
    from langflow.services.database.models.auth import AuthzTeam

    stub_authz()
    team_id = uuid4()
    team = _make_team_row(id=team_id)
    captured: dict = {}

    class _RecordingSession(_FakeAsyncSession):
        async def exec(self, stmt):  # type: ignore[override]
            captured["stmt"] = stmt
            return _ExecResult([])

    session = _RecordingSession({(AuthzTeam, team_id): team})
    user = _make_user()

    await authz_teams.list_members(
        team_id=team_id,
        session=session,
        current_user=user,
        limit=5,
        offset=15,
    )
    compiled = str(captured["stmt"].compile(compile_kwargs={"literal_binds": True}))
    assert "LIMIT 5" in compiled
    assert "OFFSET 15" in compiled


@pytest.mark.asyncio
async def test_list_assignments_passes_limit_offset_to_query(stub_authz):
    from langflow.api.v1 import authz_role_assignments

    stub_authz()
    captured: dict = {}

    class _RecordingSession(_FakeAsyncSession):
        async def exec(self, stmt):  # type: ignore[override]
            captured["stmt"] = stmt
            return _ExecResult([])

    session = _RecordingSession()
    user = _make_user(is_superuser=False)

    await authz_role_assignments.list_assignments(
        session=session,
        current_user=user,
        limit=12,
        offset=60,
    )
    compiled = str(captured["stmt"].compile(compile_kwargs={"literal_binds": True}))
    assert "LIMIT 12" in compiled
    assert "OFFSET 60" in compiled


@pytest.mark.parametrize(
    "endpoint_module",
    [
        "langflow.api.v1.authz_roles",
        "langflow.api.v1.authz_teams",
        "langflow.api.v1.authz_role_assignments",
    ],
)
def test_list_endpoint_pagination_bounds_match_convention(endpoint_module):
    """All four list endpoints share the same (1..200) / (>=0) cap as authz_shares.

    Couples the constants together so a future loosening to e.g. 1000 in one
    module fails a single fast test rather than landing silently.
    """
    import importlib

    module = importlib.import_module(endpoint_module)
    assert module._LIST_MAX_LIMIT == 200
    assert module._LIST_DEFAULT_LIMIT == 100
