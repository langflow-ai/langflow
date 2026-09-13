"""Real-database coverage for the registered Casbin collaboration service."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import BackgroundTasks, HTTPException
from langflow.api.v1 import authz_capabilities, authz_recipients, authz_teams
from langflow.services import deps as langflow_deps
from langflow.services.authorization import collaboration, share_management, team_management
from langflow.services.authorization.access_ceiling import ExternalAccessContext, set_current_external_access_context
from langflow.services.authorization.casbin import store
from langflow.services.authorization.casbin.service import CasbinAuthorizationService
from langflow.services.authorization.concurrency import strong_etag
from langflow.services.authorization.listing import resource_visible_in_scope
from langflow.services.database.models.auth import (
    AuthzAuditLog,
    AuthzRole,
    AuthzRoleAssignment,
    AuthzRoleAssignmentGrant,
    AuthzShare,
    AuthzTeam,
    AuthzTeamMember,
    CasbinRule,
    SharePermissionLevel,
    ShareScope,
    TeamRole,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from lfx.services import deps as lfx_deps
from lfx.services.authorization.base import ResourceVisibilityScope
from lfx.services.authorization.context import authorization_session
from lfx.services.manager import get_service_manager
from lfx.services.schema import ServiceType
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@dataclass(frozen=True, slots=True)
class CollaborationDatabase:
    engine: AsyncEngine
    service: CasbinAuthorizationService
    dialect: str

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Start direct test mutations with the same early ordering as API writers."""
        async with AsyncSession(self.engine, expire_on_commit=False) as session:
            await self.service.acquire_resource_mutation_lock(session=session)
            with authorization_session(session):
                yield session


@pytest_asyncio.fixture
async def collaboration_db(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> AsyncIterator[CollaborationDatabase]:
    """Install the production enforcer over the selected real database."""
    database_url = os.getenv("LANGFLOW_AUTHZ_TEST_DATABASE_URI")
    if database_url is None:
        database_url = f"sqlite+aiosqlite:///{tmp_path / 'collaboration.db'}"
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("sqlite:///"):
        database_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

    connect_args = {"check_same_thread": False, "timeout": 30} if database_url.startswith("sqlite") else {}
    engine = create_async_engine(database_url, connect_args=connect_args)
    tables = [
        User.__table__,
        Folder.__table__,
        Flow.__table__,
        AuthzRole.__table__,
        AuthzRoleAssignment.__table__,
        AuthzRoleAssignmentGrant.__table__,
        AuthzTeam.__table__,
        AuthzTeamMember.__table__,
        AuthzShare.__table__,
        AuthzAuditLog.__table__,
        CasbinRule.__table__,
    ]
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync_connection: SQLModel.metadata.create_all(sync_connection, tables=tables))

    settings = SimpleNamespace(
        auth_settings=SimpleNamespace(
            AUTHZ_ENABLED=True,
            AUTHZ_SUPERUSER_BYPASS=True,
            AUTHZ_AUDIT_ENABLED=False,
            AUTHZ_AUDIT_DURABLE=False,
        )
    )
    service = CasbinAuthorizationService(settings)

    @asynccontextmanager
    async def session_scope_readonly() -> AsyncIterator[AsyncSession]:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    monkeypatch.setattr(lfx_deps, "session_scope_readonly", session_scope_readonly)

    @asynccontextmanager
    async def session_scope() -> AsyncIterator[AsyncSession]:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session
            await session.commit()

    monkeypatch.setattr(lfx_deps, "session_scope", session_scope)
    monkeypatch.setitem(get_service_manager().services, ServiceType.AUTHORIZATION_SERVICE, service)
    monkeypatch.setattr(langflow_deps, "get_authorization_service", lambda: service)
    monkeypatch.setattr(collaboration, "get_authorization_service", lambda: service)
    monkeypatch.setattr(team_management, "get_authorization_service", lambda: service)
    monkeypatch.setattr(team_management, "get_settings_service", lambda: settings)
    await service.initialize_authorization()

    try:
        database = CollaborationDatabase(engine=engine, service=service, dialect=engine.dialect.name)
        expected_dialect = os.getenv("LANGFLOW_AUTHZ_EXPECTED_DIALECT")
        if expected_dialect is not None:
            assert database.dialect == expected_dialect
        yield database
    finally:
        await engine.dispose()


def _user(label: str, *, is_active: bool = True, is_superuser: bool = False) -> User:
    return User(
        username=f"{label}-{uuid4()}",
        password=str(uuid4()),
        is_active=is_active,
        is_superuser=is_superuser,
    )


async def _seed_users(database: CollaborationDatabase, *users: User) -> tuple[UUID, ...]:
    async with database.session() as session:
        session.add_all(users)
        await session.commit()
    return tuple(user.id for user in users)


@pytest.mark.asyncio
async def test_unready_native_service_cannot_advertise_a_weaker_write_contract(collaboration_db: CollaborationDatabase):
    invalid_team = AuthzTeam(team_name="Unrepaired legacy team", adom_name=uuid4().hex)
    async with collaboration_db.session() as session:
        session.add(invalid_team)
        await session.commit()
    try:
        assert not await collaboration_db.service.collaboration_ready()
        with pytest.raises(collaboration.CollaborationCapabilityError):
            await collaboration.discover_collaboration_capabilities(collaboration_db.service)
    finally:
        async with collaboration_db.session() as session:
            await session.delete(await session.get(AuthzTeam, invalid_team.id))
            await session.commit()


@pytest.mark.asyncio
async def test_project_revision_check_refreshes_a_previously_loaded_row(collaboration_db: CollaborationDatabase):
    from langflow.api.v1.projects import _apply_project_update
    from langflow.services.authorization.concurrency import strong_etag
    from langflow.services.database.models.folder.model import FolderUpdate

    owner = _user("project-owner")
    await _seed_users(collaboration_db, owner)
    project = Folder(name=f"Revision project {uuid4()}", user_id=owner.id)
    async with collaboration_db.session() as seed:
        seed.add(project)
        await seed.commit()
    async with collaboration_db.session() as stale_session:
        stale = await stale_session.get(Folder, project.id)
        await stale_session.commit()  # End the read transaction, retaining the ORM identity.
        async with collaboration_db.session() as writer:
            current = await writer.get(Folder, project.id)
            current.description = "A separately committed change"
            current.edit_revision = 2
            await writer.commit()
        assert stale.edit_revision == 1
        with pytest.raises(HTTPException) as conflict:
            await _apply_project_update(
                session=stale_session,
                existing_project=stale,
                project=FolderUpdate(description="Stale overwrite"),
                current_user=owner,
                background_tasks=BackgroundTasks(),
                if_match=strong_etag("project", project.id, 1),
                precondition_required=True,
            )
        assert conflict.value.status_code == 412
        await stale_session.rollback()
    async with collaboration_db.session() as verify:
        current = await verify.get(Folder, project.id)
        assert current.description == "A separately committed change"
        assert current.edit_revision == 2


@pytest.mark.asyncio
async def test_team_mutations_enforce_real_roster_and_role_invariants(collaboration_db: CollaborationDatabase):
    platform = _user("platform", is_superuser=True)
    admin = _user("admin")
    maintainer = _user("maintainer")
    ordinary = _user("ordinary")
    extra = _user("extra")
    await _seed_users(collaboration_db, platform, admin, maintainer, ordinary, extra)

    async with collaboration_db.session() as session:
        actor = await session.get(User, platform.id)
        assert actor is not None
        with pytest.raises(team_management.TeamManagementError) as exc_info:
            await team_management.create_team(
                session,
                actor=actor,
                team_name="No admin",
                adom_name=f"no-admin-{uuid4()}",
                description=None,
                is_active=True,
                members=(team_management.MemberUpsert(ordinary.id, TeamRole.USER.value),),
            )
        assert exc_info.value.code == "TEAM_ACTIVE_ADMIN_REQUIRED"
        await session.rollback()

    async with collaboration_db.session() as session:
        actor = await session.get(User, platform.id)
        assert actor is not None
        created = await team_management.create_team(
            session,
            actor=actor,
            team_name="Runtime",
            adom_name=f"runtime-{uuid4()}",
            description="Production team",
            is_active=True,
            members=(
                team_management.MemberUpsert(admin.id, TeamRole.ADMIN.value),
                team_management.MemberUpsert(maintainer.id, TeamRole.MAINTAINER.value),
                team_management.MemberUpsert(ordinary.id, TeamRole.USER.value),
            ),
        )
        team_id = created.team.id
        assert created.counts.member_count == 3
        assert created.counts.active_admin_count == 1
        await session.commit()

    async with collaboration_db.session() as session:
        assert await team_management.team_is_valid_recipient(session, team_id)
        audit_actions = set((await session.exec(select(AuthzAuditLog.action))).all())
        assert {"team:create", "team_member:add"} <= audit_actions

    async with collaboration_db.session() as session:
        actor = await session.get(User, platform.id)
        assert actor is not None
        with pytest.raises(team_management.TeamManagementError) as exc_info:
            await team_management.change_member_role(
                session,
                actor=actor,
                team_id=team_id,
                user_id=admin.id,
                role=TeamRole.USER.value,
            )
        assert exc_info.value.code == "TEAM_LAST_ACTIVE_ADMIN"
        await session.rollback()

    async with collaboration_db.session() as session:
        actor = await session.get(User, maintainer.id)
        assert actor is not None
        with pytest.raises(team_management.TeamManagementError) as exc_info:
            await team_management.add_member(
                session,
                actor=actor,
                team_id=team_id,
                member=team_management.MemberUpsert(extra.id, TeamRole.ADMIN.value),
            )
        assert exc_info.value.code == "TEAM_OPERATION_FORBIDDEN"
        await session.rollback()

    async with collaboration_db.session() as session:
        actor = await session.get(User, maintainer.id)
        assert actor is not None
        added = await team_management.add_member(
            session,
            actor=actor,
            team_id=team_id,
            member=team_management.MemberUpsert(extra.id, TeamRole.USER.value),
        )
        assert added.member.role == TeamRole.USER.value
        await session.commit()

    async with collaboration_db.session() as session:
        actor = await session.get(User, platform.id)
        assert actor is not None
        await team_management.patch_team(
            session,
            actor=actor,
            team_id=team_id,
            patch=team_management.TeamPatch(is_active=False),
        )
        await session.commit()
        assert not await team_management.team_is_valid_recipient(session, team_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("actor_role", ["outsider", "user", "maintainer", "admin", "platform"])
@pytest.mark.parametrize("payload", [{}, {"team_name": None, "is_active": None, "member_upserts": []}])
async def test_empty_team_patch_requires_metadata_authority(
    collaboration_db: CollaborationDatabase,
    actor_role: str,
    payload: dict,
):
    """An empty PATCH must not bypass the role matrix or disclose another team's metadata."""
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from langflow.services.auth.utils import get_current_active_user

    admin = _user("team-admin")
    caller = _user("patch-caller", is_superuser=actor_role == "platform")
    await _seed_users(collaboration_db, admin, caller)
    team = AuthzTeam(team_name=f"private-{uuid4()}", adom_name=uuid4().hex)
    async with collaboration_db.session() as seed:
        seed.add(team)
        await seed.flush()
        seed.add(AuthzTeamMember(team_id=team.id, user_id=admin.id, role="admin"))
        if actor_role in {"user", "maintainer", "admin"}:
            seed.add(AuthzTeamMember(team_id=team.id, user_id=caller.id, role=actor_role))
        await store.reconcile_policy(seed)
        await seed.commit()
    async with collaboration_db.session() as reader:
        before = (await reader.get(AuthzTeam, team.id)).updated_at
        audits_before = set((await reader.exec(select(AuthzAuditLog.id))).all())

    async def actor():
        return caller

    app = FastAPI()
    app.include_router(authz_teams.router)
    app.dependency_overrides[get_current_active_user] = actor
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(f"/authz/teams/{team.id}", json=payload)

    permitted = actor_role in {"admin", "platform"}
    assert response.status_code == (200 if permitted else 403), response.text
    if permitted:
        assert response.json()["id"] == str(team.id)
    else:
        assert response.json()["detail"]["code"] == "TEAM_OPERATION_FORBIDDEN"
        assert team.team_name not in response.text
        async with collaboration_db.session() as reader:
            assert (await reader.get(AuthzTeam, team.id)).updated_at == before
            assert set((await reader.exec(select(AuthzAuditLog.id))).all()) == audits_before


@pytest.mark.asyncio
async def test_concurrent_final_admin_demotions_commit_only_one_valid_result(
    collaboration_db: CollaborationDatabase,
):
    platform = _user("platform", is_superuser=True)
    first_admin = _user("first-admin")
    second_admin = _user("second-admin")
    await _seed_users(collaboration_db, platform, first_admin, second_admin)

    async with collaboration_db.session() as session:
        actor = await session.get(User, platform.id)
        assert actor is not None
        created = await team_management.create_team(
            session,
            actor=actor,
            team_name=f"concurrent-{uuid4()}",
            adom_name=f"concurrent-{uuid4()}",
            description=None,
            is_active=True,
            members=(
                team_management.MemberUpsert(first_admin.id, TeamRole.ADMIN.value),
                team_management.MemberUpsert(second_admin.id, TeamRole.ADMIN.value),
            ),
        )
        team_id = created.team.id
        await session.commit()

    async def demote(user_id: UUID) -> str:
        async with collaboration_db.session() as session:
            actor = await session.get(User, platform.id)
            assert actor is not None
            try:
                await team_management.change_member_role(
                    session,
                    actor=actor,
                    team_id=team_id,
                    user_id=user_id,
                    role=TeamRole.USER.value,
                )
                await session.commit()
            except team_management.TeamManagementError as exc:
                await session.rollback()
                return exc.code
            return "committed"

    outcomes = await asyncio.gather(demote(first_admin.id), demote(second_admin.id))
    assert sorted(outcomes) == ["TEAM_LAST_ACTIVE_ADMIN", "committed"]

    async with collaboration_db.session() as session:
        counts = await team_management.team_roster_counts(session, team_id)
        assert counts.member_count == 2
        assert counts.active_admin_count == 1


@pytest.mark.asyncio
async def test_capabilities_endpoint_reports_only_ready_native_service_contract(
    collaboration_db: CollaborationDatabase,
):
    platform = _user("platform", is_superuser=True)
    await _seed_users(collaboration_db, platform)

    async with collaboration_db.session() as session:
        actor = await session.get(User, platform.id)
        assert actor is not None
        result = await authz_capabilities.get_authorization_capabilities(
            current_user=actor,
            session=session,
        )

    assert result.enforcement_active is True
    assert result.service_ready is True
    assert result.team_roles_supported is True
    assert result.user_team_sharing_supported is True
    assert result.share_modes == ["execute", "write"]
    assert result.conditional_writes_required is True
    assert result.can_administer_platform is True
    assert result.can_create_team is True

    set_current_external_access_context(ExternalAccessContext(provider="test-idp", subject="platform", level="editor"))
    try:
        async with collaboration_db.session() as session:
            actor = await session.get(User, platform.id)
            assert actor is not None
            credential_restricted = await authz_capabilities.get_authorization_capabilities(
                current_user=actor,
                session=session,
            )
    finally:
        set_current_external_access_context(None)

    assert credential_restricted.can_administer_platform is False
    assert credential_restricted.can_create_team is False

    collaboration_db.service.settings_service.auth_settings.AUTHZ_SUPERUSER_BYPASS = False
    async with collaboration_db.session() as session:
        actor = await session.get(User, platform.id)
        assert actor is not None
        restricted = await authz_capabilities.get_authorization_capabilities(
            current_user=actor,
            session=session,
        )

    assert restricted.can_administer_platform is False
    assert restricted.can_create_team is False


@pytest.mark.asyncio
async def test_recipient_lookup_is_authorized_and_filters_inactive_users(
    collaboration_db: CollaborationDatabase,
):
    platform = _user("platform", is_superuser=True)
    ordinary = _user("ordinary")
    active_match = _user("eligible-recipient")
    inactive_match = _user("eligible-inactive", is_active=False)
    await _seed_users(collaboration_db, platform, ordinary, active_match, inactive_match)

    async with collaboration_db.session() as session:
        actor = await session.get(User, ordinary.id)
        assert actor is not None
        with pytest.raises(HTTPException) as exc_info:
            await authz_recipients.search_authorization_recipients(
                current_user=actor,
                session=session,
                purpose="team_membership",
                kind="user",
                q="eligible",
            )
        assert exc_info.value.status_code == 403

    async with collaboration_db.session() as session:
        actor = await session.get(User, platform.id)
        assert actor is not None
        page = await authz_recipients.search_authorization_recipients(
            current_user=actor,
            session=session,
            purpose="team_membership",
            kind="user",
            q="eligible",
            limit=20,
            offset=0,
        )

    assert [(item.id, item.display_name) for item in page.items] == [(active_match.id, active_match.username)]
    assert page.has_more is False
    assert page.next_offset is None


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [TeamRole.ADMIN.value, TeamRole.MAINTAINER.value])
@pytest.mark.parametrize("level", ["viewer", "editor"])
async def test_team_capabilities_and_recipient_search_honor_credential_ceiling(
    collaboration_db: CollaborationDatabase, role: str, level: str
):
    platform = _user("platform", is_superuser=True)
    manager = _user("manager")
    recipient = _user("eligible-ceiling-recipient")
    await _seed_users(collaboration_db, platform, manager, recipient)
    async with collaboration_db.session() as session:
        created = await team_management.create_team(
            session,
            actor=platform,
            team_name="Credential ceilings",
            adom_name=uuid4().hex,
            description=None,
            is_active=True,
            members=(
                team_management.MemberUpsert(platform.id, TeamRole.ADMIN.value),
                team_management.MemberUpsert(manager.id, role),
            ),
        )
        team_id = created.team.id
        await session.commit()

    set_current_external_access_context(ExternalAccessContext(provider="openrag", subject="manager", level=level))
    try:
        async with collaboration_db.session() as session:
            team = await authz_teams.read_team(team_id=team_id, session=session, current_user=manager)
            assert team.current_user_role == role
            lookup = authz_recipients.search_authorization_recipients(
                current_user=manager,
                session=session,
                purpose="team_membership",
                kind="user",
                q=recipient.username,
                team_id=team_id,
            )
            if level == "viewer":
                with pytest.raises(HTTPException) as exc_info:
                    await lookup
                assert exc_info.value.status_code == 403
            else:
                page = await lookup
                assert [item.id for item in page.items] == [recipient.id]
    finally:
        set_current_external_access_context(None)

    can_write = level == "editor"
    can_manage_roles = can_write and role == TeamRole.ADMIN.value
    assert team.capabilities.model_dump() == {
        "can_update": can_manage_roles,
        "can_set_active": False,
        "can_delete": False,
        "can_add_user_member": can_write,
        "can_add_privileged_member": can_manage_roles,
        "can_change_roles": can_manage_roles,
        "can_remove_user_member": can_write,
    }


@pytest.mark.asyncio
async def test_native_service_enforces_direct_team_and_project_inherited_shares(
    collaboration_db: CollaborationDatabase,
):
    platform = _user("platform", is_superuser=True)
    owner = _user("owner")
    runner = _user("runner")
    editor = _user("editor")
    team_admin = _user("team-admin")
    await _seed_users(collaboration_db, platform, owner, runner, editor, team_admin)

    async with collaboration_db.session() as session:
        actor = await session.get(User, platform.id)
        assert actor is not None
        team_result = await team_management.create_team(
            session,
            actor=actor,
            team_name="Editors",
            adom_name=f"editors-{uuid4()}",
            description=None,
            is_active=True,
            members=(
                team_management.MemberUpsert(team_admin.id, TeamRole.ADMIN.value),
                team_management.MemberUpsert(editor.id, TeamRole.USER.value),
            ),
        )
        project = Folder(name=f"project-{uuid4()}", user_id=owner.id)
        sibling_project = Folder(name=f"sibling-{uuid4()}", user_id=owner.id)
        session.add_all([project, sibling_project])
        await session.flush()
        flow = Flow(name=f"flow-{uuid4()}", user_id=owner.id, folder_id=project.id, data={})
        sibling = Flow(name=f"sibling-flow-{uuid4()}", user_id=owner.id, folder_id=sibling_project.id, data={})
        session.add_all([flow, sibling])
        await session.flush()
        await share_management.create_share(
            session,
            actor_id=owner.id,
            resource_type="flow",
            resource_id=flow.id,
            scope=ShareScope.USER.value,
            target_id=runner.id,
            permission_level=SharePermissionLevel.EXECUTE.value,
        )
        await share_management.create_share(
            session,
            actor_id=owner.id,
            resource_type="project",
            resource_id=project.id,
            scope=ShareScope.TEAM.value,
            target_id=team_result.team.id,
            permission_level=SharePermissionLevel.WRITE.value,
        )
        team_id = team_result.team.id
        flow_id = flow.id
        sibling_id = sibling.id
        await session.commit()

    service = collaboration_db.service
    for action in ("read", "execute"):
        assert await service.enforce(user_id=runner.id, domain="*", obj=f"flow:{flow_id}", act=action)
    for action in ("write", "delete"):
        assert not await service.enforce(user_id=runner.id, domain="*", obj=f"flow:{flow_id}", act=action)

    for action in ("read", "write", "execute"):
        assert await service.enforce(user_id=editor.id, domain="*", obj=f"flow:{flow_id}", act=action)
    assert not await service.enforce(user_id=editor.id, domain="*", obj=f"flow:{flow_id}", act="delete")
    assert not await service.enforce(user_id=editor.id, domain="*", obj=f"flow:{sibling_id}", act="read")

    async with collaboration_db.session() as session:
        actor = await session.get(User, team_admin.id)
        assert actor is not None
        await team_management.remove_member(session, actor=actor, team_id=team_id, user_id=editor.id)
        await session.commit()

    assert not await service.enforce(user_id=editor.id, domain="*", obj=f"flow:{flow_id}", act="read")


@pytest.mark.asyncio
async def test_native_service_expands_role_wildcards_into_concrete_actions(
    collaboration_db: CollaborationDatabase,
):
    owner = _user("wildcard-owner")
    actor = _user("wildcard-actor")
    await _seed_users(collaboration_db, owner, actor)

    async with collaboration_db.session() as session:
        project = Folder(name=f"wildcard-project-{uuid4()}", user_id=owner.id)
        role = AuthzRole(
            name=f"wildcard-role-{uuid4()}",
            permissions=["flow:*", "share:*"],
        )
        session.add_all([project, role])
        await session.flush()
        flow = Flow(name=f"wildcard-flow-{uuid4()}", user_id=owner.id, folder_id=project.id, data={})
        assignment = AuthzRoleAssignment(
            user_id=actor.id,
            role_id=role.id,
            domain_type="global",
            domain_id=None,
        )
        session.add_all([flow, assignment])
        await store.reconcile_policy(session)
        await session.commit()
        flow_id = flow.id

    service = collaboration_db.service
    for action in ("read", "write", "execute", "delete", "deploy"):
        assert await service.enforce(user_id=actor.id, domain="*", obj=f"flow:{flow_id}", act=action)
    assert not await service.enforce(user_id=actor.id, domain="*", obj=f"flow:{flow_id}", act="unknown")
    assert await service.enforce(
        user_id=actor.id,
        domain="*",
        obj="share:*",
        act="create",
        context={"resource_type": "flow", "resource_id": flow_id},
    )

    permissions = await service.get_effective_permissions(
        user_id=actor.id,
        resource_type="flow",
        resource_ids=[flow_id],
        actions=["read", "write", "execute", "delete", "deploy", "unknown"],
    )
    assert permissions[flow_id] == ["read", "write", "execute", "delete", "deploy"]


@pytest.mark.asyncio
async def test_native_visibility_scope_matches_direct_enforcement_without_enumerating_scoped_rows(
    collaboration_db: CollaborationDatabase,
):
    owner = _user("scope-owner")
    actor = _user("scope-actor")
    await _seed_users(collaboration_db, owner, actor)
    workspace_id = uuid4()

    async with collaboration_db.session() as session:
        actor_project = Folder(name=f"actor-project-{uuid4()}", user_id=actor.id)
        shared_project = Folder(name=f"shared-project-{uuid4()}", user_id=owner.id)
        workspace_project = Folder(
            name=f"workspace-project-{uuid4()}",
            user_id=owner.id,
            workspace_id=workspace_id,
        )
        hidden_project = Folder(name=f"hidden-project-{uuid4()}", user_id=owner.id)
        inactive_team = AuthzTeam(
            team_name=f"inactive-team-{uuid4()}",
            adom_name=f"inactive-team-{uuid4()}",
            is_active=False,
            inactivation_reason="manual",
        )
        role = AuthzRole(name=f"workspace-reader-{uuid4()}", permissions=["flow:read"])
        session.add_all([actor_project, shared_project, workspace_project, hidden_project, inactive_team, role])
        await session.flush()
        actor_project_flow = Flow(
            name=f"actor-project-flow-{uuid4()}", user_id=owner.id, folder_id=actor_project.id, data={}
        )
        shared_project_flow = Flow(
            name=f"shared-project-flow-{uuid4()}", user_id=owner.id, folder_id=shared_project.id, data={}
        )
        workspace_flow = Flow(
            name=f"workspace-flow-{uuid4()}",
            user_id=owner.id,
            folder_id=workspace_project.id,
            workspace_id=workspace_id,
            data={},
        )
        direct_flow = Flow(name=f"direct-flow-{uuid4()}", user_id=owner.id, folder_id=hidden_project.id, data={})
        hidden_flow = Flow(name=f"hidden-flow-{uuid4()}", user_id=owner.id, folder_id=hidden_project.id, data={})
        inactive_team_flow = Flow(
            name=f"inactive-team-flow-{uuid4()}", user_id=owner.id, folder_id=hidden_project.id, data={}
        )
        system_example_flow = Flow(name=f"system-example-{uuid4()}", user_id=None, folder_id=None, data={})
        session.add_all(
            [
                actor_project_flow,
                shared_project_flow,
                workspace_flow,
                direct_flow,
                hidden_flow,
                inactive_team_flow,
                system_example_flow,
            ]
        )
        await session.flush()
        session.add_all(
            [
                AuthzRoleAssignment(
                    user_id=actor.id,
                    role_id=role.id,
                    domain_type="workspace",
                    domain_id=workspace_id,
                ),
                AuthzTeamMember(team_id=inactive_team.id, user_id=actor.id, role=TeamRole.USER.value),
                AuthzShare(
                    resource_type="flow",
                    resource_id=inactive_team_flow.id,
                    scope=ShareScope.TEAM.value,
                    target_id=inactive_team.id,
                    permission_level=SharePermissionLevel.EXECUTE.value,
                    created_by=owner.id,
                ),
            ]
        )
        await share_management.create_share(
            session,
            actor_id=owner.id,
            resource_type="project",
            resource_id=shared_project.id,
            scope=ShareScope.USER.value,
            target_id=actor.id,
            permission_level=SharePermissionLevel.EXECUTE.value,
        )
        await share_management.create_share(
            session,
            actor_id=owner.id,
            resource_type="flow",
            resource_id=direct_flow.id,
            scope=ShareScope.USER.value,
            target_id=actor.id,
            permission_level=SharePermissionLevel.EXECUTE.value,
        )
        # Deliberately overlap a direct grant with project inheritance. The
        # compact scope may retain both sources, but it must make the same
        # decision as direct enforcement.
        await share_management.create_share(
            session,
            actor_id=owner.id,
            resource_type="flow",
            resource_id=shared_project_flow.id,
            scope=ShareScope.USER.value,
            target_id=actor.id,
            permission_level=SharePermissionLevel.EXECUTE.value,
        )
        await session.commit()
        rows = (
            actor_project_flow,
            shared_project_flow,
            workspace_flow,
            direct_flow,
            hidden_flow,
            inactive_team_flow,
            system_example_flow,
        )

    scope = await collaboration_db.service.get_resource_visibility(
        user_id=actor.id,
        resource_type="flow",
        act="read",
    )
    assert scope is not None
    assert scope.all_resources is False
    assert set(scope.resource_ids) == {direct_flow.id, shared_project_flow.id}
    assert set(scope.project_ids) == {shared_project.id}
    assert scope.owner_id == actor.id
    assert scope.project_owner_id == actor.id
    assert scope.workspace_ids == (workspace_id,)
    assert actor_project_flow.id not in scope.resource_ids
    assert workspace_flow.id not in scope.resource_ids
    assert hidden_flow.id not in scope.resource_ids
    assert inactive_team_flow.id not in scope.resource_ids
    assert system_example_flow.id not in scope.resource_ids

    batch_decisions = await collaboration_db.service.batch_enforce(
        user_id=actor.id,
        domain="*",
        requests=[(f"flow:{flow.id}", "read") for flow in rows],
    )
    for flow, directly_allowed in zip(rows, batch_decisions, strict=True):
        prefilter_allowed = resource_visible_in_scope(
            resource_id=flow.id,
            workspace_id=flow.workspace_id,
            project_id=flow.folder_id,
            owner_id=flow.user_id,
            project_owner_id=actor.id if flow.folder_id == actor_project.id else owner.id,
            canonical_context_valid=True,
            visibility=scope,
        )
        assert prefilter_allowed is directly_allowed

    # Owning a project grants content operations on collaborator-owned flows,
    # not deletion. The compact scope must remain action-exact as well.
    delete_scope = await collaboration_db.service.get_resource_visibility(
        user_id=actor.id,
        resource_type="flow",
        act="delete",
    )
    assert delete_scope is not None
    assert actor_project.id not in delete_scope.project_ids
    assert not resource_visible_in_scope(
        resource_id=actor_project_flow.id,
        workspace_id=actor_project_flow.workspace_id,
        project_id=actor_project_flow.folder_id,
        owner_id=actor_project_flow.user_id,
        project_owner_id=actor.id,
        canonical_context_valid=True,
        visibility=delete_scope,
    )
    assert not await collaboration_db.service.enforce(
        user_id=actor.id,
        domain="*",
        obj=f"flow:{actor_project_flow.id}",
        act="delete",
    )


@pytest.mark.asyncio
async def test_superuser_bypass_still_requires_supported_actions_and_resolved_resources(
    collaboration_db: CollaborationDatabase,
):
    platform = _user("validated-platform", is_superuser=True)
    owner = _user("validated-owner")
    await _seed_users(collaboration_db, platform, owner)

    async with collaboration_db.session() as session:
        project = Folder(name=f"validated-project-{uuid4()}", user_id=owner.id)
        session.add(project)
        await session.flush()
        flow = Flow(name=f"validated-flow-{uuid4()}", user_id=owner.id, folder_id=project.id, data={})
        session.add(flow)
        await session.commit()
        project_id = project.id
        flow_id = flow.id

    service = collaboration_db.service
    missing_id = uuid4()
    assert await service.enforce(user_id=platform.id, domain="*", obj=f"flow:{flow_id}", act="delete")
    assert not await service.enforce(user_id=platform.id, domain="*", obj=f"flow:{missing_id}", act="read")
    assert not await service.enforce(user_id=platform.id, domain="*", obj=f"flow:{flow_id}", act="unknown")
    assert not await service.enforce(user_id=platform.id, domain="*", obj="unknown:*", act="read")
    assert not await service.enforce(user_id=platform.id, domain="*", obj="flow:*", act="create")
    assert not await service.enforce(
        user_id=platform.id,
        domain="*",
        obj="flow:*",
        act="create",
        context={"intrinsic_creation": True, "folder_id": missing_id},
    )
    assert await service.enforce(
        user_id=platform.id,
        domain="*",
        obj="flow:*",
        act="create",
        context={"intrinsic_creation": True, "folder_id": project_id},
    )
    assert not await service.enforce(
        user_id=platform.id,
        domain="*",
        obj="share:*",
        act="unknown",
        context={"resource_type": "flow", "resource_id": flow_id},
    )

    decisions = await service.batch_enforce(
        user_id=platform.id,
        domain="*",
        requests=[
            (f"flow:{flow_id}", "read"),
            (f"flow:{missing_id}", "read"),
            (f"flow:{flow_id}", "unknown"),
            ("unknown:*", "read"),
        ],
    )
    assert decisions == [True, False, False, False]
    assert await service.get_resource_visibility(
        user_id=platform.id,
        resource_type="flow",
        act="unknown",
    ) == ResourceVisibilityScope(require_canonical_context=True)


@pytest.mark.asyncio
async def test_share_mutation_revision_recipient_and_audit_contract(collaboration_db: CollaborationDatabase):
    owner = _user("owner")
    recipient = _user("recipient")
    inactive = _user("inactive", is_active=False)
    await _seed_users(collaboration_db, owner, recipient, inactive)

    async with collaboration_db.session() as session:
        project = Folder(name=f"project-{uuid4()}", user_id=owner.id)
        session.add(project)
        await session.flush()
        flow = Flow(name=f"flow-{uuid4()}", user_id=owner.id, folder_id=project.id, data={})
        session.add(flow)
        await session.commit()
        flow_id = flow.id

    async with collaboration_db.session() as session:
        with pytest.raises(share_management.ShareManagementError) as exc_info:
            await share_management.create_share(
                session,
                actor_id=owner.id,
                resource_type="flow",
                resource_id=flow_id,
                scope=ShareScope.USER.value,
                target_id=inactive.id,
                permission_level=SharePermissionLevel.EXECUTE.value,
            )
        assert exc_info.value.code == "SHARE_RECIPIENT_INELIGIBLE"
        await session.rollback()

    async with collaboration_db.session() as session:
        created = await share_management.create_share(
            session,
            actor_id=owner.id,
            resource_type="flow",
            resource_id=flow_id,
            scope=ShareScope.USER.value,
            target_id=recipient.id,
            permission_level=SharePermissionLevel.EXECUTE.value,
        )
        share_id = created.row.id
        initial_etag = strong_etag("share", share_id, created.row.revision)
        await session.commit()

    async with collaboration_db.session() as session:
        with pytest.raises(share_management.ShareManagementError) as exc_info:
            await share_management.update_share(
                session,
                actor_id=owner.id,
                share_id=share_id,
                permission_level=SharePermissionLevel.WRITE.value,
                if_match=None,
                precondition_required=True,
            )
        assert (exc_info.value.status_code, exc_info.value.code) == (428, "PRECONDITION_REQUIRED")
        await session.rollback()

    async with collaboration_db.session() as session:
        updated = await share_management.update_share(
            session,
            actor_id=owner.id,
            share_id=share_id,
            permission_level=SharePermissionLevel.WRITE.value,
            if_match=initial_etag,
            precondition_required=True,
        )
        assert updated.row.revision == 2
        current_etag = strong_etag("share", share_id, updated.row.revision)
        await session.commit()

    async with collaboration_db.session() as session:
        with pytest.raises(share_management.ShareManagementError) as exc_info:
            await share_management.update_share(
                session,
                actor_id=owner.id,
                share_id=share_id,
                permission_level=SharePermissionLevel.EXECUTE.value,
                if_match=initial_etag,
                precondition_required=False,
            )
        assert (exc_info.value.status_code, exc_info.value.code) == (412, "SHARE_CHANGED")
        await session.rollback()

    async with collaboration_db.session() as session:
        await share_management.delete_share(
            session,
            actor_id=owner.id,
            share_id=share_id,
            if_match=current_etag,
            precondition_required=True,
        )
        await session.commit()

    async with collaboration_db.session() as session:
        assert await session.get(AuthzShare, share_id) is None
        audits = list(
            (
                await session.exec(
                    select(AuthzAuditLog).where(
                        AuthzAuditLog.resource_type == "flow",
                        AuthzAuditLog.resource_id == flow_id,
                    )
                )
            ).all()
        )
        assert [audit.action for audit in audits] == ["share:create", "share:update", "share:delete"]
        assert all(audit.details and audit.details.get("event") == "mutation" for audit in audits)


@pytest.mark.asyncio
async def test_inactive_recipient_share_can_be_revoked_but_not_updated(
    collaboration_db: CollaborationDatabase,
):
    owner = _user("inactive-revocation-owner")
    recipient = _user("inactive-revocation-recipient")
    await _seed_users(collaboration_db, owner, recipient)

    async with collaboration_db.session() as session:
        flow = Flow(name=f"flow-{uuid4()}", user_id=owner.id, data={})
        session.add(flow)
        await session.flush()
        created = await share_management.create_share(
            session,
            actor_id=owner.id,
            resource_type="flow",
            resource_id=flow.id,
            scope=ShareScope.USER.value,
            target_id=recipient.id,
            permission_level=SharePermissionLevel.READ.value,
        )
        share_id = created.row.id
        etag = strong_etag("share", share_id, created.row.revision)
        await session.commit()

    async with collaboration_db.session() as session:
        stored_recipient = await session.get(User, recipient.id)
        assert stored_recipient is not None
        stored_recipient.is_active = False
        session.add(stored_recipient)
        await session.commit()

    async with collaboration_db.session() as session:
        with pytest.raises(share_management.ShareManagementError) as exc_info:
            await share_management.update_share(
                session,
                actor_id=owner.id,
                share_id=share_id,
                permission_level=SharePermissionLevel.WRITE.value,
                if_match=etag,
                precondition_required=True,
            )
        assert exc_info.value.code == "SHARE_RECIPIENT_INELIGIBLE"
        await session.rollback()

    async with collaboration_db.session() as session:
        await share_management.delete_share(
            session,
            actor_id=owner.id,
            share_id=share_id,
            if_match=etag,
            precondition_required=True,
        )
        await session.commit()

    async with collaboration_db.session() as session:
        assert await session.get(AuthzShare, share_id) is None
