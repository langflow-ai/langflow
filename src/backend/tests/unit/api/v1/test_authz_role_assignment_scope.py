"""A user holds at most one role per assignment scope (``domain_type`` + ``domain_id``).

Runs the real ``/api/v1/authz/role-assignments`` route against the test
database so the uniqueness rule is checked end-to-end, not against a fake
session.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langflow.services.database.models.auth import AuthzRole, AuthzRoleAssignment, AuthzRoleAssignmentGrant
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from sqlalchemy import event
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from sqlmodel import select

ASSIGNMENTS_URL = "api/v1/authz/role-assignments"
SCOPE_CONFLICT_DETAIL = (
    "A role already exists for this user with this scope. "
    "Please update the existing role or revoke it before assigning a new one."
)


@pytest.fixture
async def roles():
    """Three roles standing in for the seeded admin / editor / viewer catalog."""
    suffix = uuid4().hex[:8]
    async with session_scope() as session:
        created = {
            name: AuthzRole(name=f"role-scope-{name}-{suffix}", permissions=[])
            for name in ("admin", "editor", "viewer")
        }
        for role in created.values():
            session.add(role)
        await session.flush()
        ids = {name: role.id for name, role in created.items()}
    yield ids
    async with session_scope() as session:
        for role_id in ids.values():
            assignments = (
                await session.exec(select(AuthzRoleAssignment).where(AuthzRoleAssignment.role_id == role_id))
            ).all()
            for assignment in assignments:
                await session.delete(assignment)
            await session.flush()
            role = await session.get(AuthzRole, role_id)
            if role is not None:
                await session.delete(role)


@pytest.fixture
async def target_users(client):  # noqa: ARG001
    """Two plain users to receive assignments, distinct from the superuser caller."""
    suffix = uuid4().hex[:8]
    async with session_scope() as session:
        users = [User(username=f"role-scope-{n}-{suffix}", password=uuid4().hex, is_active=True) for n in ("a", "b")]
        for user in users:
            session.add(user)
        await session.flush()
        ids = [user.id for user in users]
    yield ids
    async with session_scope() as session:
        for user_id in ids:
            assignments = (
                await session.exec(select(AuthzRoleAssignment).where(AuthzRoleAssignment.user_id == user_id))
            ).all()
            for assignment in assignments:
                await session.delete(assignment)
            await session.flush()
            user = await session.get(User, user_id)
            if user is not None:
                await session.delete(user)


async def _assign(client, headers: dict, *, user_id, role_id, domain_type="global", domain_id=None):
    payload = {"user_id": str(user_id), "role_id": str(role_id), "domain_type": domain_type}
    if domain_id is not None:
        payload["domain_id"] = str(domain_id)
    return await client.post(ASSIGNMENTS_URL, json=payload, headers=headers)


async def _assignments_for(user_id) -> list[AuthzRoleAssignment]:
    async with session_scope() as session:
        return list(
            (await session.exec(select(AuthzRoleAssignment).where(AuthzRoleAssignment.user_id == user_id))).all()
        )


async def test_second_role_at_global_scope_is_rejected(client, logged_in_headers_super_user, target_users, roles):
    """Ticket repro: Admin, then Editor, then Viewer — all Global — for one user."""
    first = await _assign(client, logged_in_headers_super_user, user_id=target_users[0], role_id=roles["admin"])
    assert first.status_code == 201, first.text

    for role in ("editor", "viewer"):
        response = await _assign(client, logged_in_headers_super_user, user_id=target_users[0], role_id=roles[role])
        assert response.status_code == 409, response.text
        assert response.json()["detail"] == SCOPE_CONFLICT_DETAIL

    assignments = await _assignments_for(target_users[0])
    assert [(a.role_id, a.domain_type, a.domain_id) for a in assignments] == [(roles["admin"], "global", None)]


@pytest.mark.parametrize("domain_type", ["org", "workspace", "project"])
async def test_second_role_on_same_scoped_target_is_rejected(
    client, logged_in_headers_super_user, target_users, roles, domain_type
):
    target = uuid4()
    first = await _assign(
        client,
        logged_in_headers_super_user,
        user_id=target_users[0],
        role_id=roles["editor"],
        domain_type=domain_type,
        domain_id=target,
    )
    assert first.status_code == 201, first.text

    response = await _assign(
        client,
        logged_in_headers_super_user,
        user_id=target_users[0],
        role_id=roles["viewer"],
        domain_type=domain_type,
        domain_id=target,
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == SCOPE_CONFLICT_DETAIL
    assert [a.role_id for a in await _assignments_for(target_users[0])] == [roles["editor"]]


async def test_different_scopes_and_targets_can_each_hold_a_role(
    client, logged_in_headers_super_user, target_users, roles
):
    """The rule is per (scope, target): other targets and other scopes stay independent."""
    project_a, project_b, workspace = uuid4(), uuid4(), uuid4()
    requests = [
        {"role_id": roles["admin"]},
        {"role_id": roles["editor"], "domain_type": "project", "domain_id": project_a},
        {"role_id": roles["viewer"], "domain_type": "project", "domain_id": project_b},
        # Same target id under a different scope type is a different scope.
        {"role_id": roles["viewer"], "domain_type": "workspace", "domain_id": project_a},
        {"role_id": roles["editor"], "domain_type": "workspace", "domain_id": workspace},
    ]
    for request in requests:
        response = await _assign(client, logged_in_headers_super_user, user_id=target_users[0], **request)
        assert response.status_code == 201, (request, response.text)

    assert len(await _assignments_for(target_users[0])) == len(requests)


async def test_scope_rule_is_per_user(client, logged_in_headers_super_user, target_users, roles):
    first = await _assign(client, logged_in_headers_super_user, user_id=target_users[0], role_id=roles["admin"])
    assert first.status_code == 201, first.text
    other_user = await _assign(client, logged_in_headers_super_user, user_id=target_users[1], role_id=roles["viewer"])
    assert other_user.status_code == 201, other_user.text


async def test_repeating_the_same_role_keeps_the_manual_duplicate_error(
    client, logged_in_headers_super_user, target_users, roles
):
    first = await _assign(client, logged_in_headers_super_user, user_id=target_users[0], role_id=roles["viewer"])
    assert first.status_code == 201, first.text

    again = await _assign(client, logged_in_headers_super_user, user_id=target_users[0], role_id=roles["viewer"])
    assert again.status_code == 409, again.text
    assert again.json()["detail"] == "Manual assignment already exists for this user/role/domain"


async def test_revoking_the_existing_role_frees_the_scope(client, logged_in_headers_super_user, target_users, roles):
    first = await _assign(client, logged_in_headers_super_user, user_id=target_users[0], role_id=roles["admin"])
    assert first.status_code == 201, first.text

    revoke = await client.delete(f"{ASSIGNMENTS_URL}/{first.json()['id']}", headers=logged_in_headers_super_user)
    assert revoke.status_code == 204, revoke.text

    replacement = await _assign(client, logged_in_headers_super_user, user_id=target_users[0], role_id=roles["viewer"])
    assert replacement.status_code == 201, replacement.text
    assert [a.role_id for a in await _assignments_for(target_users[0])] == [roles["viewer"]]


async def test_manual_source_can_still_join_an_idp_assignment_of_the_same_role(
    client, logged_in_headers_super_user, target_users, roles
):
    """Adding a manual source to an existing role adds no new role, so the scope rule does not apply.

    An identity provider can map one user into two roles at the same scope;
    the manual API must still be able to pin either of them.
    """
    async with session_scope() as session:
        for role in ("editor", "viewer"):
            assignment = AuthzRoleAssignment(user_id=target_users[0], role_id=roles[role])
            session.add(assignment)
            await session.flush()
            session.add(
                AuthzRoleAssignmentGrant(
                    assignment_id=assignment.id,
                    source_kind="idp",
                    provider_id="entra",
                    external_group=f"corp-{role}",
                )
            )

    response = await _assign(client, logged_in_headers_super_user, user_id=target_users[0], role_id=roles["editor"])
    assert response.status_code == 201, response.text
    assert {source["source_kind"] for source in response.json()["grant_sources"]} == {"idp", "manual"}

    # A third role at that scope is still a new role and is refused.
    third = await _assign(client, logged_in_headers_super_user, user_id=target_users[0], role_id=roles["admin"])
    assert third.status_code == 409, third.text
    assert third.json()["detail"] == SCOPE_CONFLICT_DETAIL


async def test_create_locks_the_target_user_row(client, logged_in_headers_super_user, target_users, roles):
    """The target user's row is read FOR UPDATE, which serializes concurrent creates for that user.

    The scope check has no unique index behind it, so on Postgres this lock is
    what stops two overlapping requests from both finding the scope free.
    SQLite drops FOR UPDATE, so the captured read is compiled for Postgres.
    """
    locked_user_reads: list[str] = []

    def record_locked_user_reads(orm_execute_state) -> None:
        if not orm_execute_state.is_select:
            return
        sql = str(orm_execute_state.statement.compile(dialect=postgresql.dialect()))
        if 'FROM "user"' in sql and "FOR UPDATE" in sql:
            locked_user_reads.append(sql)

    event.listen(Session, "do_orm_execute", record_locked_user_reads)
    try:
        response = await _assign(client, logged_in_headers_super_user, user_id=target_users[0], role_id=roles["viewer"])
    finally:
        event.remove(Session, "do_orm_execute", record_locked_user_reads)

    assert response.status_code == 201, response.text
    assert locked_user_reads, "create_assignment no longer locks the target user's row"


@pytest.mark.parametrize("domain_type", ["global", "org", "workspace", "project"])
async def test_inactive_user_cannot_receive_a_role(
    client, logged_in_headers_super_user, target_users, roles, monkeypatch, domain_type
):
    from langflow.api.v1 import authz_role_assignments
    from langflow.services.authorization.audit import AUDIT_EVENT_ACCESS

    async with session_scope() as session:
        user = await session.get(User, target_users[0])
        user.is_active = False
        session.add(user)

    audit = AsyncMock()
    monkeypatch.setattr(authz_role_assignments, "audit_decision", audit)
    response = await _assign(
        client,
        {**logged_in_headers_super_user, "X-Langflow-Operation-ID": "inactive-role-assignment"},
        user_id=target_users[0],
        role_id=roles["viewer"],
        domain_type=domain_type,
        domain_id=None if domain_type == "global" else uuid4(),
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "Cannot assign roles to an inactive user"
    assert await _assignments_for(target_users[0]) == []
    audit.assert_awaited_once()
    assert audit.await_args.kwargs["action"] == "role_assignment:create"
    assert audit.await_args.kwargs["result"] == "deny"
    assert audit.await_args.kwargs["details"] == {
        "event": AUDIT_EVENT_ACCESS,
        "status_code": 409,
        "reason": "user_inactive",
        "source": "manual",
        "operation_id": "inactive-role-assignment",
    }


async def test_inactive_user_cannot_add_a_manual_source_to_an_idp_assignment(
    client, logged_in_headers_super_user, target_users, roles
):
    async with session_scope() as session:
        user = await session.get(User, target_users[0])
        user.is_active = False
        session.add(user)
        assignment = AuthzRoleAssignment(user_id=user.id, role_id=roles["viewer"])
        session.add(assignment)
        await session.flush()
        assignment_id = assignment.id
        grant = AuthzRoleAssignmentGrant(
            assignment_id=assignment_id,
            source_kind="idp",
            provider_id="entra",
            external_group="corp-viewer",
        )
        session.add(grant)
        grant_id = grant.id

    response = await _assign(client, logged_in_headers_super_user, user_id=target_users[0], role_id=roles["viewer"])

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "Cannot assign roles to an inactive user"
    assert [a.id for a in await _assignments_for(target_users[0])] == [assignment_id]
    async with session_scope() as session:
        grants = (
            await session.exec(
                select(AuthzRoleAssignmentGrant).where(AuthzRoleAssignmentGrant.assignment_id == assignment_id)
            )
        ).all()
    assert [(g.id, g.source_kind) for g in grants] == [(grant_id, "idp")]
