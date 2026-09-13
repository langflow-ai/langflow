"""Freshness and publication contracts against independent real database connections."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from langflow.services.authorization.casbin import store
from langflow.services.authorization.casbin.service import CasbinAuthorizationService
from langflow.services.database.models.auth import AuthzShare, AuthzTeam, AuthzTeamMember, CasbinRule
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from lfx.services.authorization.context import authorization_session
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def scenario(policy_db, monkeypatch):
    """Use the registered class and the application's existing session entry points."""
    import lfx.services.deps

    @asynccontextmanager
    async def readonly():
        async with AsyncSession(policy_db, expire_on_commit=False) as session:
            yield session

    @asynccontextmanager
    async def writable():
        async with readonly() as session:
            yield session
            await session.commit()

    monkeypatch.setattr(lfx.services.deps, "session_scope", writable)
    monkeypatch.setattr(lfx.services.deps, "session_scope_readonly", readonly)
    owner = User(username=str(uuid4()), password=str(uuid4()), is_active=True)
    recipient = User(username=str(uuid4()), password=str(uuid4()), is_active=True)
    project = Folder(name=str(uuid4()), user_id=owner.id)
    flow = Flow(name=str(uuid4()), user_id=owner.id, folder_id=project.id)
    team = AuthzTeam(team_name=str(uuid4()), adom_name=str(uuid4()), is_active=True)
    share = AuthzShare(
        resource_type="flow",
        resource_id=flow.id,
        scope="team",
        target_id=team.id,
        permission_level="write",
        created_by=owner.id,
    )
    member = AuthzTeamMember(team_id=team.id, user_id=recipient.id, role="user")
    async with writable() as session:
        await store.acquire_writer_lock(session)
        session.add_all([owner, recipient, project, flow, team])
        await session.flush()
        session.add_all([share, member, AuthzTeamMember(team_id=team.id, user_id=owner.id, role="admin")])
        await store.reconcile_policy(session)
    settings = SimpleNamespace(auth_settings=SimpleNamespace(AUTHZ_ENABLED=True, AUTHZ_SUPERUSER_BYPASS=True))
    services = [CasbinAuthorizationService(settings), CasbinAuthorizationService(settings)]
    for service in services:
        await service.initialize_authorization()
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType

    monkeypatch.setitem(get_service_manager().services, ServiceType.AUTHORIZATION_SERVICE, services[0])
    return SimpleNamespace(
        engine=policy_db,
        services=services,
        writable=writable,
        readonly=readonly,
        owner=owner.id,
        recipient=recipient.id,
        flow=flow.id,
        project=project.id,
        team=team.id,
        member=member.id,
        share=share.id,
    )


async def permits(service, state):
    return await service.enforce(user_id=state.recipient, domain="*", obj=f"flow:{state.flow}", act="read")


@pytest.mark.parametrize("group_claim", ["matching", "empty"])
async def test_default_service_keeps_membership_locally_managed(scenario, group_claim):
    """Verified group claims neither add nor remove members without a directory integration."""
    from langflow.services.auth.external import ExternalIdentity
    from langflow.services.auth.service import AuthService
    from langflow.services.deps import get_settings_service

    state = scenario
    outsider = User(username=str(uuid4()), password=str(uuid4()), is_active=True)
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        writer.add(outsider)
        await store.reconcile_policy(writer)

    auth = AuthService(get_settings_service())
    async with state.writable() as session:
        team = await session.get(AuthzTeam, state.team)
        before = {
            (member.id, member.team_id, member.user_id, member.source, member.role)
            for member in (await session.exec(select(AuthzTeamMember))).all()
        }
        for user_id in (state.recipient, outsider.id):
            user = await session.get(User, user_id)
            identity = ExternalIdentity(
                provider="test-directory",
                subject=str(user_id),
                username=user.username,
                claims={"groups": [team.adom_name] if group_claim == "matching" else []},
            )
            await auth._reconcile_verified_external_groups(identity=identity, user=user, db=session)

    async with state.readonly() as reader:
        after = {
            (member.id, member.team_id, member.user_id, member.source, member.role)
            for member in (await reader.exec(select(AuthzTeamMember))).all()
        }
        assert after == before
        assert (await store.verify_projection(reader))["valid"] is True
    assert await permits(state.services[1], state) is True
    assert not await state.services[1].enforce(user_id=outsider.id, domain="*", obj=f"flow:{state.flow}", act="read")


@pytest.mark.parametrize("replace", [False, True])
async def test_unused_superuser_teardown_keeps_policy_coherent(scenario, monkeypatch, replace):
    """Shutdown and restart publish bootstrap identity deletion with its derived policy."""
    from langflow.services.deps import get_settings_service
    from langflow.services.utils import get_or_create_super_user, teardown_superuser
    from lfx.services.settings.constants import DEFAULT_SUPERUSER

    state = scenario
    settings = get_settings_service()
    monkeypatch.setattr(settings.auth_settings, "AUTO_LOGIN", False)
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        user = await writer.get(User, state.recipient)
        user.username = DEFAULT_SUPERUSER
        user.is_superuser = True
        await store.reconcile_policy(writer)

    async with state.writable() as writer:
        await teardown_superuser(settings, writer)
        if replace:
            replacement = await get_or_create_super_user(writer, DEFAULT_SUPERUSER, str(uuid4()), is_default=False)
            assert replacement.id != state.recipient
            assert replacement.is_active is True
            assert replacement.is_superuser is True

    async with state.readonly() as reader:
        assert await reader.get(User, state.recipient) is None
        assert (await store.verify_projection(reader))["valid"] is True
    assert await permits(state.services[1], state) is False


@pytest.mark.parametrize("operation", ["post", "put_create", "patch", "put_update"])
async def test_project_success_is_committed_before_the_http_response(scenario, monkeypatch, operation):
    """A successful project response and ETag must already be visible to the next request."""
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from langflow.api.v1.projects import router
    from langflow.services.auth.utils import get_current_active_user
    from langflow.services.deps import get_settings_service

    state = scenario
    settings = get_settings_service()
    monkeypatch.setattr(settings.auth_settings, "AUTHZ_ENABLED", True)
    monkeypatch.setattr(settings.settings, "add_projects_to_mcp_servers", False)
    project_id = uuid4()
    description = f"committed-{uuid4()}"
    updating = operation in {"patch", "put_update"}
    if updating:
        async with state.writable() as writer:
            await store.acquire_writer_lock(writer)
            writer.add(Folder(id=project_id, name=str(project_id), user_id=state.owner))

    async def actor():
        async with state.readonly() as reader:
            return await reader.get(User, state.owner)

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_active_user] = actor
    observed = []

    async def observe_response(scope, receive, send):
        async def record(message):
            if message["type"] == "http.response.start" and message["status"] in {200, 201}:
                # FastAPI can send the response before request-scope dependency
                # teardown. An independent connection models the next caller.
                async with state.readonly() as reader:
                    row = (await reader.exec(select(Folder).where(Folder.description == description))).first()
                    observed.append(None if row is None else (row.id, row.edit_revision))
            await send(message)

        await app(scope, receive, record)

    method = "POST" if operation == "post" else "PATCH" if operation == "patch" else "PUT"
    path = "/projects/" if operation == "post" else f"/projects/{project_id}"
    headers = {"If-Match": f'"project:{project_id}:1"'} if updating else {"If-None-Match": "*"}
    async with AsyncClient(transport=ASGITransport(app=observe_response), base_url="http://test") as client:
        response = await client.request(
            method,
            path,
            headers=headers,
            json={"name": str(project_id), "description": description},
        )
    assert response.status_code == (200 if updating else 201), response.text
    body = response.json()
    assert observed == [(UUID(body["id"]), body["edit_revision"])]
    assert response.headers["ETag"] == f'"project:{body["id"]}:{body["edit_revision"]}"'


@pytest.mark.parametrize("view", ["member", "managed"])
async def test_team_listing_returns_the_requested_authorized_page(scenario, view):
    """Given managed memberships, pagination returns the same ordered authorized teams."""
    from langflow.api.v1.authz_teams import list_teams

    state = scenario
    teams = [AuthzTeam(team_name=f"pagination-{index}", adom_name=str(uuid4()), is_active=True) for index in range(3)]
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        writer.add_all(teams)
        await writer.flush()
        writer.add_all([AuthzTeamMember(team_id=team.id, user_id=state.owner, role="admin") for team in teams])
        await store.reconcile_policy(writer)

    async with state.readonly() as session:
        actor = await session.get(User, state.owner)
        page = await list_teams(session=session, current_user=actor, view=view, search="pagination-", limit=1, offset=1)
    assert [team.id for team in page] == [teams[1].id]
    assert page[0].current_user_role == "admin"


async def test_committed_revocation_is_fresh_on_two_workers_with_an_inflight_admission(scenario):
    """TX-07/14: an existing snapshot stays coherent; every later admission sees revocation."""
    state = scenario
    first, second = state.services
    assert await permits(first, state)
    assert await permits(second, state)
    async with first.admission_context():
        assert await permits(first, state)
        async with state.writable() as writer:
            await store.acquire_writer_lock(writer)
            await writer.delete(await writer.get(AuthzShare, state.share))
            await store.reconcile_policy(writer)
        assert await permits(first, state)
    assert not await permits(first, state)
    assert not await permits(second, state)


async def test_grouping_and_policy_queries_cannot_combine_two_denied_states(scenario):
    """TX-08/09: membership without a share cannot combine with a later share without membership."""
    state = scenario
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        await writer.delete(await writer.get(AuthzShare, state.share))
        await store.reconcile_policy(writer)
    grouping_read = asyncio.Event()
    committed = asyncio.Event()

    class PausingSession(AsyncSession):
        async def exec(self, statement, *args, **kwargs):
            result = await super().exec(statement, *args, **kwargs)
            if statement.compile().params.get("ptype_1") == "g":
                grouping_read.set()
                await asyncio.wait_for(committed.wait(), 5)
            return result

    async def reader():
        async with PausingSession(state.engine) as session:
            await store.establish_read_snapshot(session)
            with authorization_session(session, admission=True):
                return await permits(state.services[0], state)

    task = asyncio.create_task(reader())
    await asyncio.wait_for(grouping_read.wait(), 5)
    try:
        async with state.writable() as writer:
            await store.acquire_writer_lock(writer)
            await writer.delete(await writer.get(AuthzTeamMember, state.member))
            writer.add(
                AuthzShare(
                    resource_type="flow",
                    resource_id=state.flow,
                    scope="team",
                    target_id=state.team,
                    permission_level="write",
                    created_by=state.owner,
                )
            )
            await store.reconcile_policy(writer)
    finally:
        committed.set()
    assert not await asyncio.wait_for(task, 5)
    assert not await permits(state.services[1], state)


async def test_download_cannot_combine_private_content_with_a_later_share(scenario, monkeypatch):
    """TX-09: export content and its authorization come from one admission snapshot."""
    import lfx.services.deps
    from fastapi import HTTPException
    from langflow.api.v1.flows import download_multiple_file
    from langflow.services.deps import get_settings_service

    state = scenario
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTHZ_ENABLED", True)
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        await writer.delete(await writer.get(AuthzShare, state.share))
        flow = await writer.get(Flow, state.flow)
        flow.description = "private before sharing"
        flow.data = {"nodes": [], "edges": []}
        await store.reconcile_policy(writer)

    content_read, published = asyncio.Event(), asyncio.Event()

    class PausingSession(AsyncSession):
        async def exec(self, statement, *args, **kwargs):
            result = await super().exec(statement, *args, **kwargs)
            descriptions = getattr(statement, "column_descriptions", ())
            if descriptions and descriptions[0].get("expr") is Flow and not content_read.is_set():
                content_read.set()
                await asyncio.wait_for(published.wait(), 10)
            return result

    @asynccontextmanager
    async def readonly():
        async with PausingSession(state.engine, expire_on_commit=False) as session:
            yield session

    monkeypatch.setattr(lfx.services.deps, "session_scope_readonly", readonly)

    async def download():
        async with readonly() as reader:
            actor = await reader.get(User, state.recipient)
            return await download_multiple_file(flow_ids=[state.flow], user=actor, db=reader)

    request = asyncio.create_task(download())
    await asyncio.wait_for(content_read.wait(), 10)
    try:
        async with state.writable() as writer:
            await store.acquire_writer_lock(writer)
            (await writer.get(Flow, state.flow)).description = "shared after grant"
            writer.add(
                AuthzShare(
                    resource_type="flow",
                    resource_id=state.flow,
                    scope="user",
                    target_id=state.recipient,
                    permission_level="read",
                    created_by=state.owner,
                )
            )
            await store.reconcile_policy(writer)
    finally:
        published.set()
    with pytest.raises(HTTPException) as denied:
        await request
    assert denied.value.status_code == 404
    assert (await download())["description"] == "shared after grant"


async def test_waiting_writer_rereads_after_revocation_and_rebuilds_converge(scenario):
    """TX-03/04/05/11: global ordering applies even with incomplete early-hook hints."""
    state = scenario
    started = asyncio.Event()
    acquired = asyncio.Event()

    async def waiting_writer():
        async with state.writable() as writer:
            started.set()
            await state.services[1].acquire_resource_mutation_lock(session=writer)
            acquired.set()
            await store.reconcile_policy(writer)

    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        await writer.delete(await writer.get(AuthzShare, state.share))
        await store.reconcile_policy(writer)
        task = asyncio.create_task(waiting_writer())
        await asyncio.wait_for(started.wait(), 5)
        await asyncio.sleep(0.05)
        assert not acquired.is_set()
    await asyncio.wait_for(task, 5)
    await asyncio.gather(*(service.initialize_authorization() for service in state.services))
    async with state.readonly() as reader:
        assert (await store.verify_projection(reader))["valid"] is True
    assert not await permits(state.services[0], state)


async def test_cancelled_writer_does_not_publish_policy_or_leak_its_lock(scenario):
    """TX-18: cancellation closes the caller's connection with the whole mutation uncommitted."""
    state = scenario
    staged = asyncio.Event()

    async def cancelled_writer():
        async with state.writable() as writer:
            await store.acquire_writer_lock(writer)
            await writer.delete(await writer.get(AuthzShare, state.share))
            await store.reconcile_policy(writer)
            staged.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(cancelled_writer())
    await asyncio.wait_for(staged.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    async with state.writable() as writer:
        await asyncio.wait_for(store.acquire_writer_lock(writer), 5)
        assert await writer.get(AuthzShare, state.share) is not None
        assert (await store.verify_projection(writer))["valid"] is True
    assert await permits(state.services[1], state)


async def test_deployment_repair_releases_writer_and_replays_authorization(scenario, monkeypatch):
    """TX-10: external repair sees rollback; the next whole attempt reauthorizes."""
    from langflow.api.v1.mappers.deployments import sync
    from langflow.services.database.lock_retry import run_with_lock_retry
    from langflow.services.database.models.deployment.exceptions import DeploymentGuardError

    state = scenario
    attempts = []

    async def provider_repair(*, db, flow_ids, user_id):
        assert flow_ids == [state.flow]
        assert user_id == state.owner
        # Acquiring from another connection would block if the original writer
        # or its savepoint still retained the projection lock.
        await asyncio.wait_for(store.acquire_writer_lock(db), 5)
        assert (await db.get(Flow, state.flow)).description != "uncommitted parent write"
        await db.delete(await db.get(AuthzShare, state.share))
        await store.reconcile_policy(db)

    monkeypatch.setattr(sync, "sync_flow_deployment_state", provider_repair)
    async with state.writable() as writer:

        async def attempt(number):
            attempts.append(number)
            await store.acquire_writer_lock(writer)
            with authorization_session(writer):
                if not await permits(state.services[0], state):
                    return False
            flow = await writer.get(Flow, state.flow)
            flow.description = "uncommitted parent write"
            await writer.flush()

            async def guarded_operation():
                raise DeploymentGuardError(
                    code="FLOW_FOLDER_MOVE", technical_detail="Flow is deployed.", detail="Flow is deployed."
                )

            return await sync.retry_flow_operation_on_deployment_guard(
                db=writer, flow_owner_ids={state.flow: state.owner}, operation=guarded_operation
            )

        assert await run_with_lock_retry(attempt, session=writer, description="real deployment repair") is False
    assert attempts == [0, 1]
    assert not await permits(state.services[1], state)


@pytest.mark.parametrize("matching_workspace", [False, True])
async def test_concurrent_project_move_intersects_final_role_workspace(scenario, matching_workspace):
    """TX-06: a waiting project move uses the role restriction committed ahead of it."""
    from langflow.services.database.models.auth import AuthzRole, AuthzRoleAssignment
    from lfx.services.authorization.base import AuthorizationMutation, AuthorizationMutationKind, ResourcePolicyMutation

    state = scenario
    before_workspace, next_workspace = uuid4(), uuid4()
    role = AuthzRole(name=str(uuid4()), permissions=["flow:read"], workspace_id=before_workspace)
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        await writer.delete(await writer.get(AuthzShare, state.share))
        (await writer.get(Folder, state.project)).workspace_id = before_workspace
        (await writer.get(Flow, state.flow)).workspace_id = before_workspace
        writer.add(role)
        await writer.flush()
        writer.add(
            AuthzRoleAssignment(
                user_id=state.recipient, role_id=role.id, domain_type="project", domain_id=state.project
            )
        )
        await store.reconcile_policy(writer)
    assert await permits(state.services[0], state)
    started = asyncio.Event()
    acquired = asyncio.Event()

    async def move():
        async with state.writable() as writer:
            started.set()
            await state.services[1].acquire_resource_mutation_lock(session=writer)
            acquired.set()
            destination_workspace = next_workspace if matching_workspace else uuid4()
            (await writer.get(Folder, state.project)).workspace_id = destination_workspace
            (await writer.get(Flow, state.flow)).workspace_id = destination_workspace
            await state.services[1].stage_resource_mutation(
                session=writer,
                event=ResourcePolicyMutation("project", state.project, changed_fields=("workspace_id",)),
            )

    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        (await writer.get(AuthzRole, role.id)).workspace_id = next_workspace
        await state.services[0].stage_identity_mutation(
            session=writer, event=AuthorizationMutation(AuthorizationMutationKind.ROLE_UPDATED, role.id)
        )
        task = asyncio.create_task(move())
        await asyncio.wait_for(started.wait(), 5)
        await asyncio.sleep(0.05)
        assert not acquired.is_set()
    await asyncio.wait_for(task, 5)
    assert await permits(state.services[0], state) is matching_workspace
    async with state.readonly() as reader:
        assert (await store.verify_projection(reader))["valid"] is True


async def test_staged_identity_is_visible_only_to_its_authentication_session(scenario):
    """TX-12: JIT identity/assignment staging admits its caller without exposing uncommitted policy."""
    from langflow.services.database.models.auth import AuthzRole, AuthzRoleAssignment
    from lfx.services.authorization.base import AuthorizationMutation, AuthorizationMutationKind

    state = scenario
    user = User(username=str(uuid4()), password=str(uuid4()), is_active=True)
    role = AuthzRole(name=str(uuid4()), permissions=["flow:read"])

    async def permission(service):
        return await service.enforce(user_id=user.id, domain="*", obj=f"flow:{state.flow}", act="read")

    async with state.writable() as writer:
        await state.services[0].acquire_identity_mutation_lock(
            session=writer, kind=AuthorizationMutationKind.USER_CREATED
        )
        writer.add_all([user, role])
        await writer.flush()
        writer.add(AuthzRoleAssignment(user_id=user.id, role_id=role.id, domain_type="global"))
        await state.services[0].stage_identity_mutation(
            session=writer, event=AuthorizationMutation(AuthorizationMutationKind.USER_CREATED, user.id)
        )
        with authorization_session(writer):
            assert await permission(state.services[0])
            # Task ownership prevents a child request from borrowing this writer.
            assert not await asyncio.create_task(permission(state.services[1]))
    assert await permission(state.services[1])


async def test_late_events_cannot_restore_suspended_team_access(scenario):
    """TX-16/17: late delivery is inert; suspension retains management, never sharing."""
    from lfx.services.authorization.base import AuthorizationMutation, AuthorizationMutationKind, ShareRuleSnapshot

    state = scenario
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        team = await writer.get(AuthzTeam, state.team)
        team.is_active = False
        team.inactivation_reason = "manual"
        await state.services[0].stage_identity_mutation(
            session=writer,
            event=AuthorizationMutation(
                AuthorizationMutationKind.TEAM_UPDATED, state.team, policy_relevant_fields=("is_active",)
            ),
        )
    await state.services[0].identity_mutation_committed(
        AuthorizationMutation(AuthorizationMutationKind.TEAM_MEMBER_ADDED, state.member, team_id=state.team)
    )
    await state.services[0].sync_share(state.share)
    await state.services[0].remove_share_rules(
        ShareRuleSnapshot(state.share, "flow", state.flow, "team", state.team, "write")
    )
    assert not await permits(state.services[1], state)
    assert await state.services[1].enforce(user_id=state.recipient, domain="*", obj=f"team:{state.team}", act="read")


@pytest.mark.parametrize("failure", ["compiler", "derived", "audit"])
async def test_failed_share_mutation_rolls_back_grant_projection_and_required_audit(scenario, monkeypatch, failure):
    """TX-01/02: no canonical/derived/audit subset can survive a failed real mutation."""
    from langflow.services.authorization.share_management import update_share
    from langflow.services.database.models.auth import AuthzAuditLog
    from sqlalchemy import event

    state = scenario
    async with state.readonly() as reader:
        before = {store.semantic_rule(row) for row in (await reader.exec(select(CasbinRule))).all()}

    def unavailable(*_args, **_kwargs):
        msg = "injected persistence failure"
        raise RuntimeError(msg)

    def fail_statement(_connection, _cursor, statement, _parameters, _context, _many):
        if (failure == "derived" and "DELETE FROM casbin_rule" in statement) or (
            failure == "audit" and "INSERT INTO authz_audit_log" in statement
        ):
            unavailable()

    if failure == "compiler":
        monkeypatch.setattr(store, "compile_policy", unavailable)
    event.listen(state.engine.sync_engine, "before_cursor_execute", fail_statement)
    try:
        with pytest.raises(RuntimeError, match="injected persistence failure"):
            async with state.writable() as writer:
                await update_share(
                    writer,
                    actor_id=state.owner,
                    share_id=state.share,
                    permission_level="read",
                    if_match=None,
                    precondition_required=False,
                )
    finally:
        event.remove(state.engine.sync_engine, "before_cursor_execute", fail_statement)
    async with state.readonly() as reader:
        share = await reader.get(AuthzShare, state.share)
        assert share.permission_level == "write"
        assert share.revision == 1
        assert not (await reader.exec(select(AuthzAuditLog))).all()
        assert {store.semantic_rule(row) for row in (await reader.exec(select(CasbinRule))).all()} == before


async def test_capability_reads_and_noop_reconciliation_do_not_rewrite_rules(scenario, monkeypatch):
    """TX-13: discovery needs no complete compilation; unchanged reconciliation preserves row IDs."""
    state = scenario
    async with state.readonly() as reader:
        before = list((await reader.exec(select(CasbinRule.id))).all())
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        result = await store.reconcile_policy(writer)
        assert result.inserted == result.deleted == 0

    def forbidden_compile(*_args, **_kwargs):
        pytest.fail("A capability read invoked the complete compiler")

    monkeypatch.setattr(store, "compile_policy", forbidden_compile)
    assert await state.services[0].collaboration_ready()
    assert await permits(state.services[0], state)
    async with state.readonly() as reader:
        assert list((await reader.exec(select(CasbinRule.id))).all()) == before


async def test_file_deletion_stages_projection_without_expanding_canonical_cleanup(scenario):
    """TX-15: the existing deletion removes derived access in the same transaction."""
    from langflow.services.database.models.file.crud import delete_file_records
    from langflow.services.database.models.file.model import File

    state = scenario
    file = File(name=str(uuid4()), path="test.txt", size=1, user_id=state.owner)
    share = AuthzShare(
        resource_type="file",
        resource_id=file.id,
        scope="user",
        target_id=state.recipient,
        permission_level="read",
        created_by=state.owner,
    )
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        writer.add_all([file, share])
        await store.reconcile_policy(writer)
    assert await state.services[0].enforce(user_id=state.recipient, domain="*", obj=f"file:{file.id}", act="read")
    async with state.writable() as writer:
        await delete_file_records(writer, file_ids=(file.id,), actor_id=state.owner)
        assert (await store.verify_projection(writer))["valid"] is True
    async with state.readonly() as reader:
        assert await reader.get(File, file.id) is None
        assert await reader.get(AuthzShare, share.id) is not None
    assert not await state.services[1].enforce(user_id=state.recipient, domain="*", obj=f"file:{file.id}", act="read")
    assert await permits(state.services[1], state)


@pytest.mark.parametrize("delete_kind", ["deployment_id", "deployment_ids", "resource_key"])
async def test_deployment_deletions_reconcile_derived_policy(scenario, delete_kind):
    """TX-15: all existing deployment delete entrypoints retain a complete projection."""
    from langflow.services.database.models.deployment import crud
    from langflow.services.database.models.deployment.model import Deployment
    from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
    from langflow.services.database.models.deployment_provider_account.schemas import DeploymentProviderKey

    state = scenario
    provider = DeploymentProviderAccount(
        user_id=state.owner,
        name=str(uuid4()),
        provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
        provider_url="https://example.test",
        api_key=str(uuid4()),
    )
    deployment = Deployment(
        user_id=state.owner,
        project_id=state.project,
        deployment_provider_account_id=provider.id,
        resource_key=str(uuid4()),
        display_name="test",
        deployment_type="agent",
    )
    resource_type = "deployment"
    resource_id = deployment.id
    share = AuthzShare(
        resource_type=resource_type,
        resource_id=resource_id,
        scope="user",
        target_id=state.recipient,
        permission_level="read",
        created_by=state.owner,
    )
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        writer.add(provider)
        await writer.flush()
        writer.add(deployment)
        writer.add(share)
        await store.reconcile_policy(writer)
    assert await state.services[0].enforce(
        user_id=state.recipient, domain="*", obj=f"{resource_type}:{resource_id}", act="read"
    )
    async with state.writable() as writer:
        if delete_kind == "deployment_ids":
            await crud.delete_deployments_by_ids(writer, user_id=state.owner, deployment_ids=[deployment.id])
        elif delete_kind == "resource_key":
            await crud.delete_deployment_by_resource_key(
                writer,
                user_id=state.owner,
                deployment_provider_account_id=provider.id,
                resource_key=deployment.resource_key,
            )
        else:
            await crud.delete_deployment_by_id(writer, user_id=state.owner, deployment_id=deployment.id)
        assert (await store.verify_projection(writer))["valid"] is True
    assert not await state.services[1].enforce(
        user_id=state.recipient, domain="*", obj=f"{resource_type}:{resource_id}", act="read"
    )
    async with state.readonly() as reader:
        assert await reader.get(AuthzShare, share.id) is not None


@pytest.mark.parametrize("compiler_failure", [False, True])
async def test_provider_reconciliation_releases_network_before_atomic_policy_writes(
    scenario, monkeypatch, compiler_failure
):
    """TX-01/15: provider I/O never owns the writer; failed staging leaves every row intact."""
    from langflow.api.v1.mappers.deployments import sync
    from langflow.services.database.models.deployment.model import Deployment
    from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
    from langflow.services.database.models.deployment_provider_account.schemas import DeploymentProviderKey

    state = scenario
    providers = [
        DeploymentProviderAccount(
            user_id=state.owner,
            name=str(uuid4()),
            provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
            provider_url=f"https://example.test/{index}",
            api_key=str(uuid4()),
        )
        for index in range(2)
    ]
    deployments = [
        Deployment(
            user_id=state.owner,
            project_id=state.project,
            deployment_provider_account_id=provider.id,
            resource_key=str(uuid4()),
            display_name="test",
            deployment_type="agent",
        )
        for provider in providers
    ]
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        writer.add_all(providers)
        await writer.flush()
        writer.add_all(deployments)
        writer.add_all(
            AuthzShare(
                resource_type="deployment",
                resource_id=row.id,
                scope="user",
                target_id=state.recipient,
                permission_level="read",
                created_by=state.owner,
            )
            for row in deployments
        )
        await store.reconcile_policy(writer)

    calls = []

    async def provider_fetch(**kwargs):
        assert not store.owns_writer_lock(kwargs["db"])
        async with state.writable() as competing_writer:
            await asyncio.wait_for(store.acquire_writer_lock(competing_writer), 2)
        calls.append(kwargs["provider_id"])
        return set(), SimpleNamespace()

    monkeypatch.setattr(sync, "fetch_provider_resource_keys", provider_fetch)
    monkeypatch.setattr(sync, "get_deployment_adapter", lambda _key: object())
    async with state.writable() as writer:
        with monkeypatch.context() as fault:
            if compiler_failure:

                def fail_compile(_snapshot):
                    msg = "projection fault"
                    raise RuntimeError(msg)

                fault.setattr(store, "compile_policy", fail_compile)
            operation = sync._sync_deployments_and_attachments_by_provider(
                db=writer,
                user_id=state.owner,
                deployments_with_provider=[(row, DeploymentProviderKey.WATSONX_ORCHESTRATE) for row in deployments],
                stale_scope_label="project",
                failure_log_message="provider failed %s %s",
                failure_scope_value=state.project,
            )
            if compiler_failure:
                with pytest.raises(RuntimeError, match="projection fault"):
                    await operation
            else:
                await operation
        assert (await store.verify_projection(writer))["valid"] is True
    assert set(calls) == {row.id for row in providers}
    async with state.readonly() as reader:
        assert len((await reader.exec(select(Deployment))).all()) == (2 if compiler_failure else 0)


async def test_memory_deletion_reconciles_derived_policy_after_job_cancellation(scenario, monkeypatch):
    """TX-15: Memory Base deletion stages policy after external cancellation finishes."""
    from unittest.mock import AsyncMock

    from langflow.api.utils import knowledge_base_service
    from langflow.services.database.models.memory_base.model import MemoryBase
    from langflow.services.memory_base import service as memory_service

    state = scenario
    memory = MemoryBase(name=str(uuid4()), user_id=state.owner, flow_id=state.flow, kb_name="test-memory")
    share = AuthzShare(
        resource_type="knowledge_base",
        resource_id=memory.id,
        scope="user",
        target_id=state.recipient,
        permission_level="read",
        created_by=state.owner,
    )
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        writer.add_all([memory, share])
        await store.reconcile_policy(writer)
    assert await state.services[0].enforce(
        user_id=state.recipient, domain="*", obj=f"knowledge_base:{memory.id}", act="read"
    )

    async def cancel_jobs(**kwargs):
        assert not store.owns_writer_lock(kwargs["db"])
        async with state.writable() as writer:
            await asyncio.wait_for(store.acquire_writer_lock(writer), 2)

    monkeypatch.setattr(memory_service, "session_scope", state.writable)
    monkeypatch.setattr(memory_service, "cancel_active_jobs", cancel_jobs)
    monkeypatch.setattr(memory_service, "resolve_kb_username", AsyncMock(return_value="test"))
    monkeypatch.setattr(memory_service, "delete_kb_remote_collection", AsyncMock())
    monkeypatch.setattr(memory_service, "delete_kb", AsyncMock())
    monkeypatch.setattr(knowledge_base_service, "delete_by_user_and_name", AsyncMock())
    assert await memory_service.MemoryBaseService().delete(memory.id, state.owner, actor_user_id=state.owner)
    async with state.readonly() as reader:
        assert await reader.get(MemoryBase, memory.id) is None
        assert await reader.get(AuthzShare, share.id) is not None
        assert (await store.verify_projection(reader))["valid"] is True


async def test_flow_import_scope_change_rolls_back_when_projection_fails(scenario, monkeypatch):
    """TX-01/15: file import is a canonical scope writer, with caller-owned rollback."""
    import orjson
    from langflow.initial_setup.setup import upsert_flow_from_file

    state = scenario
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        flow = await writer.get(Flow, state.flow)
        flow.folder_id = None
        await store.reconcile_policy(writer)

    def fail_compile(_snapshot):
        msg = "import projection fault"
        raise RuntimeError(msg)

    with monkeypatch.context() as fault:
        fault.setattr(store, "compile_policy", fail_compile)
        with pytest.raises(RuntimeError, match="import projection fault"):
            async with state.writable() as writer:
                await upsert_flow_from_file(
                    orjson.dumps({"id": str(state.flow), "name": "imported"}),
                    str(state.flow),
                    writer,
                    state.owner,
                )
    async with state.readonly() as reader:
        assert (await reader.get(Flow, state.flow)).folder_id is None
        assert (await store.verify_projection(reader))["valid"] is True


@pytest.mark.parametrize("compiler_failure", [False, True])
async def test_filesystem_scope_change_and_projection_commit_together(
    scenario, monkeypatch, tmp_path, compiler_failure
):
    """TX-01/15: the existing file poll must stage a move in its own transaction."""
    import orjson
    from langflow.initial_setup import setup

    state = scenario
    destination = Folder(name=str(uuid4()), user_id=state.owner, workspace_id=uuid4())
    path = tmp_path / "flow.json"
    path.write_bytes(orjson.dumps({"folder_id": str(destination.id), "name": "from disk"}))
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        writer.add(destination)
        flow = await writer.get(Flow, state.flow)
        flow.fs_path = str(path)
        await store.reconcile_policy(writer)

    async def stop_poll(_delay):
        raise asyncio.CancelledError

    def fail_compile(_snapshot):
        msg = "filesystem projection fault"
        raise RuntimeError(msg)

    monkeypatch.setattr(setup, "session_scope", state.writable)
    monkeypatch.setattr(
        setup,
        "get_settings_service",
        lambda: SimpleNamespace(
            settings=SimpleNamespace(fs_flows_polling_interval=1),
        ),
    )
    monkeypatch.setattr(setup, "get_storage_service", SimpleNamespace)
    with monkeypatch.context() as poll:
        poll.setattr(setup.asyncio, "sleep", stop_poll)
        if compiler_failure:
            poll.setattr(store, "compile_policy", fail_compile)
        await setup.sync_flows_from_fs()
    async with state.readonly() as reader:
        flow = await reader.get(Flow, state.flow)
        assert flow.folder_id == (state.project if compiler_failure else destination.id)
        assert flow.workspace_id == (None if compiler_failure else destination.workspace_id)
        assert (await store.verify_projection(reader))["valid"] is True


async def test_model_status_deletion_keeps_the_complete_caller_transaction(scenario, monkeypatch):
    """TX-10: a deletion hook must not roll back the preceding model-list update."""
    import json

    from langflow.api.v1 import models
    from langflow.services.database.models.variable.model import Variable
    from langflow.services.deps import get_settings_service
    from langflow.services.variable.service import DatabaseVariableService
    from lfx.base.models.unified_models.credentials import model_status_key

    state = scenario
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTHZ_ENABLED", True)
    identity = model_status_key("OpenAI", "test-model", "llm")
    disabled = Variable(name=models.DISABLED_MODELS_VAR, value="[]", type="Generic", user_id=state.owner)
    enabled = Variable(
        name=models.ENABLED_MODELS_VAR, value=json.dumps([identity]), type="Generic", user_id=state.owner
    )
    async with state.writable() as writer:
        writer.add_all([disabled, enabled])
    variables = DatabaseVariableService(get_settings_service())
    monkeypatch.setattr(models, "get_variable_service", lambda: variables)
    monkeypatch.setattr(
        models,
        "get_unified_models_detailed",
        lambda **_kwargs: [
            {
                "provider": "OpenAI",
                "models": [
                    {
                        "model_name": "test-model",
                        "model_type": "llm",
                        "metadata": {"default": False},
                    }
                ],
            }
        ],
    )
    async with state.writable() as writer:
        actor = await writer.get(User, state.owner)
        await models.update_enabled_models(
            session=writer,
            current_user=actor,
            provider_policy_attributes=None,
            updates=[
                models.ModelStatusUpdate(
                    provider="OpenAI",
                    model_id="test-model",
                    model_type="llm",
                    enabled=False,
                )
            ],
        )
    async with state.readonly() as reader:
        assert json.loads((await reader.get(Variable, disabled.id)).value) == [identity]
        assert await reader.get(Variable, enabled.id) is None
        assert (await store.verify_projection(reader))["valid"] is True


@pytest.mark.parametrize("action", ["read", "write", "delete"])
async def test_personal_variable_collection_requires_active_owner_and_credential_ceiling(scenario, action):
    """PC-20/23: personal model settings preserve ownership without broad variable authority."""
    from langflow.services.authorization.access_ceiling import (
        ExternalAccessContext,
        clear_current_external_access_context,
        set_current_external_access_context,
    )

    state = scenario
    service = state.services[0]
    context = {"resource_type": "variable", "resource_id": None, "variable_user_id": state.owner}
    request = {"user_id": state.owner, "domain": "*", "obj": "variable:*", "act": action}
    assert await service.enforce(**request, context=context)
    assert not await service.enforce(**request, context={})
    assert not await service.enforce(**request, context={**context, "variable_user_id": state.recipient})
    set_current_external_access_context(ExternalAccessContext(provider="test", subject="test", level="viewer"))
    try:
        assert await service.enforce(**request, context=context) is (action == "read")
    finally:
        clear_current_external_access_context()
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        owner = await writer.get(User, state.owner)
        owner.is_active = False
        writer.add(owner)
        await store.reconcile_policy(writer)
    assert not await service.enforce(**request, context=context)


async def test_starter_deletion_reconciles_policy_in_the_caller_transaction(scenario):
    """TX-15: initialization cleanup is a participating resource writer."""
    from langflow.initial_setup.setup import delete_starter_projects

    state = scenario
    async with state.writable() as writer:
        await delete_starter_projects(writer, state.project)
    async with state.readonly() as reader:
        assert await reader.get(Flow, state.flow) is None
        assert (await store.verify_projection(reader))["valid"] is True


async def test_rejected_assistant_flow_cleanup_removes_derived_policy(scenario, monkeypatch):
    """TX-15: provisional-flow cleanup uses the same policy deletion transaction."""
    from unittest.mock import AsyncMock

    from fastapi import HTTPException
    from langflow.agentic.utils import assistant_runner

    state = scenario
    context = SimpleNamespace(
        global_vars={}, max_retries=0, session_id="test", provider="test", model_name="test", api_key_name=None
    )
    monkeypatch.setattr(assistant_runner, "_resolve_assistant_context", AsyncMock(return_value=context))
    monkeypatch.setattr(assistant_runner, "execute_flow_with_validation_streaming", lambda **_kwargs: None)
    monkeypatch.setattr(
        assistant_runner,
        "_consume_stream",
        AsyncMock(
            return_value=(
                SimpleNamespace(changed=True, data={}),
                None,
                "",
                "",
                [],
            )
        ),
    )

    def reject_graph(*_args, **_kwargs):
        raise HTTPException(status_code=403, detail="catalog rejection")

    monkeypatch.setattr(assistant_runner, "_validate_catalog_policy_for_write", reject_graph)
    async with state.writable() as writer:
        flow = await writer.get(Flow, state.flow)
        monkeypatch.setattr(assistant_runner, "_ensure_flow", AsyncMock(return_value=(flow, True)))
        with pytest.raises(HTTPException, match="catalog rejection"):
            await assistant_runner.run_assistant_and_persist(session=writer, user_id=state.owner, instruction="test")
    async with state.readonly() as reader:
        assert await reader.get(Flow, state.flow) is None
        assert (await store.verify_projection(reader))["valid"] is True


async def test_user_reactivation_restores_surviving_team_share_policy(scenario):
    """PC-14: reactivating a member restores surviving grants on the next admission."""
    from langflow.api.v1.users import patch_user
    from langflow.services.database.models.user.model import UserUpdate

    state = scenario
    platform_admin = User(username=str(uuid4()), password=str(uuid4()), is_active=True, is_superuser=True)
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        writer.add(platform_admin)
        (await writer.get(User, state.recipient)).is_active = False
        await store.reconcile_policy(writer)
    assert not await permits(state.services[0], state)

    async with state.writable() as writer:
        updated = await patch_user(
            user_id=state.recipient,
            user_update=UserUpdate(is_active=True),
            user=platform_admin,
            session=writer,
        )
        assert updated.is_active is True

    assert await permits(state.services[1], state)
    async with state.readonly() as reader:
        assert (await store.verify_projection(reader))["valid"] is True


@pytest.mark.parametrize("actor_kind", ["recipient", "owner", "platform"])
async def test_visibility_rejects_inconsistent_canonical_project_context(scenario, actor_kind):
    """A list must omit a flow denied by direct admission for conflicting containment."""
    from langflow.services.authorization.listing import resource_visible_in_scope, restrict_to_owned_or_visible_scope
    from langflow.services.database.models.auth import AuthzRole, AuthzRoleAssignment
    from sqlalchemy import false

    state = scenario
    malformed = Flow(name="000-conflicting-context", user_id=state.owner, folder_id=state.project, workspace_id=uuid4())
    role = AuthzRole(name=str(uuid4()), permissions=["flow:read"])
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        writer.add_all([malformed, role])
        await writer.flush()
        writer.add(AuthzRoleAssignment(user_id=state.recipient, role_id=role.id, domain_type="global"))
        if actor_kind == "platform":
            (await writer.get(User, state.owner)).is_superuser = True
        await store.reconcile_policy(writer)

    service = state.services[0]
    actor_id = state.recipient if actor_kind == "recipient" else state.owner
    assert not await service.enforce(user_id=actor_id, domain="*", obj=f"flow:{malformed.id}", act="read")
    visibility = await service.get_resource_visibility(user_id=actor_id, resource_type="flow", act="read")
    statement = restrict_to_owned_or_visible_scope(
        select(Flow.id).outerjoin(Folder, Folder.id == Flow.folder_id),
        id_column=Flow.id,
        owner_clause=false(),
        visibility=visibility,
        workspace_column=Folder.workspace_id,
        project_column=Flow.folder_id,
    )
    async with state.readonly() as reader:
        listed_ids = (await reader.exec(statement)).all()
        first_page = (await reader.exec(statement.order_by(Flow.name).limit(1))).all()
    assert malformed.id not in listed_ids
    assert first_page == [state.flow]
    assert not resource_visible_in_scope(
        resource_id=malformed.id,
        owner_id=state.owner,
        project_owner_id=state.owner,
        project_id=state.project,
        visibility=visibility,
        canonical_context_valid=False,
    )


async def test_visibility_does_not_restore_a_disabled_owner_through_the_legacy_override(scenario):
    """Canonical list admission denies an inactive owner even in legacy SQL callers."""
    from langflow.services.authorization.listing import restrict_to_owned_or_visible_scope

    state = scenario
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        (await writer.get(User, state.owner)).is_active = False
        await store.reconcile_policy(writer)
    visibility = await state.services[0].get_resource_visibility(user_id=state.owner, resource_type="flow")
    statement = restrict_to_owned_or_visible_scope(
        select(Flow.id),
        id_column=Flow.id,
        owner_clause=Flow.user_id == state.owner,
        visibility=visibility,
    )
    async with state.readonly() as reader:
        assert not (await reader.exec(statement)).all()


@pytest.mark.parametrize("action", ["read", "write", "delete"])
async def test_compact_project_ownership_keeps_direct_child_boundaries(scenario, action):
    """Project ownership includes a foreign-owned direct flow but never its deletion."""
    from langflow.services.authorization.listing import restrict_to_owned_or_visible_scope
    from sqlalchemy import false

    state = scenario
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        await writer.delete(await writer.get(AuthzShare, state.share))
        (await writer.get(Flow, state.flow)).user_id = state.recipient
        await store.reconcile_policy(writer)
    service = state.services[0]
    visibility = await service.get_resource_visibility(user_id=state.owner, resource_type="flow", act=action)
    assert not visibility.resource_ids
    assert not visibility.project_ids
    statement = restrict_to_owned_or_visible_scope(
        select(Flow.id), id_column=Flow.id, owner_clause=false(), visibility=visibility
    )
    async with state.readonly() as reader:
        listed_ids = (await reader.exec(statement)).all()
    assert listed_ids == ([state.flow] if action != "delete" else [])
    assert await service.enforce(user_id=state.owner, domain="*", obj=f"flow:{state.flow}", act=action) == (
        action != "delete"
    )


@pytest.mark.parametrize("operation", ["create", "patch", "delete"])
@pytest.mark.parametrize(("revoked_field", "expected_status"), [("is_superuser", 403), ("is_active", 401)])
async def test_user_lifecycle_reloads_revoked_platform_authority(
    scenario, monkeypatch, operation, revoked_field, expected_status
):
    """A request identity captured before revocation cannot authorize an identity writer."""
    from fastapi import HTTPException
    from langflow.api.v1.users import add_user, delete_user, patch_user
    from langflow.services.database.models.user.model import UserCreate, UserRead, UserUpdate
    from langflow.services.deps import get_settings_service

    state = scenario
    monkeypatch.setattr(get_settings_service().auth_settings, "ENABLE_SIGNUP", False)
    new_username = str(uuid4())
    admin = User(username=str(uuid4()), password=str(uuid4()), is_active=True, is_superuser=True)
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        writer.add(admin)
        await store.reconcile_policy(writer)
    request_actor = UserRead.model_validate(admin, from_attributes=True)
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        setattr(await writer.get(User, admin.id), revoked_field, False)
        await store.reconcile_policy(writer)
    async with state.writable() as writer:
        if operation == "create":
            mutation = add_user(
                user=UserCreate(username=new_username, password=str(uuid4())),
                current_user=request_actor,
                session=writer,
            )
        elif operation == "patch":
            mutation = patch_user(
                user_id=state.recipient,
                user_update=UserUpdate(is_active=False),
                user=request_actor,
                session=writer,
            )
        else:
            mutation = delete_user(user_id=state.recipient, current_user=request_actor, session=writer)
        with pytest.raises(HTTPException) as denied:
            await mutation
        assert denied.value.status_code == expected_status
    async with state.readonly() as reader:
        assert (await reader.exec(select(User).where(User.username == new_username))).first() is None
        assert (await reader.get(User, state.recipient)).is_active is True
        assert (await store.verify_projection(reader))["valid"] is True


@pytest.mark.parametrize(
    "operation", ["create_role", "update_role", "delete_role", "create_assignment", "delete_assignment"]
)
@pytest.mark.parametrize(("revoked_field", "expected_status"), [("is_superuser", 403), ("is_active", 401)])
async def test_role_writers_reload_revoked_platform_authority(scenario, operation, revoked_field, expected_status):
    """Revocation committed before a policy writer must prevent every role mutation."""
    from fastapi import HTTPException
    from langflow.api.v1 import authz_role_assignments, authz_roles
    from langflow.api.v1.schemas.authz_role_assignments import RoleAssignmentCreate
    from langflow.api.v1.schemas.authz_roles import RoleCreate, RoleUpdate
    from langflow.services.database.models.auth import AuthzRole, AuthzRoleAssignment, AuthzRoleAssignmentGrant
    from langflow.services.database.models.user.model import UserRead

    state = scenario
    admin = User(username=str(uuid4()), password=str(uuid4()), is_active=True, is_superuser=True)
    role = AuthzRole(name=str(uuid4()), permissions=["flow:read"])
    assignment = AuthzRoleAssignment(user_id=state.recipient, role_id=role.id, domain_type="global")
    new_name = str(uuid4())
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        writer.add_all([admin, role])
        await writer.flush()
        if operation == "delete_assignment":
            writer.add(assignment)
            await writer.flush()
            writer.add(AuthzRoleAssignmentGrant(assignment_id=assignment.id, source_kind="manual"))
        await store.reconcile_policy(writer)
    request_actor = UserRead.model_validate(admin, from_attributes=True)
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        setattr(await writer.get(User, admin.id), revoked_field, False)
        await store.reconcile_policy(writer)
    async with state.writable() as writer:
        if operation == "create_role":
            mutation = authz_roles.create_role(
                payload=RoleCreate(name=new_name, permissions=["flow:write"]),
                current_user=request_actor,
                session=writer,
            )
        elif operation == "update_role":
            mutation = authz_roles.update_role(
                role_id=role.id,
                payload=RoleUpdate(permissions=["flow:write"]),
                current_user=request_actor,
                session=writer,
            )
        elif operation == "delete_role":
            mutation = authz_roles.delete_role(role_id=role.id, current_user=request_actor, session=writer)
        elif operation == "create_assignment":
            mutation = authz_role_assignments.create_assignment(
                payload=RoleAssignmentCreate(user_id=state.recipient, role_id=role.id),
                current_user=request_actor,
                session=writer,
            )
        else:
            mutation = authz_role_assignments.delete_assignment(
                assignment_id=assignment.id, current_user=request_actor, session=writer
            )
        with pytest.raises(HTTPException) as denied:
            await mutation
        assert denied.value.status_code == expected_status
    async with state.readonly() as reader:
        assert (await reader.exec(select(AuthzRole).where(AuthzRole.name == new_name))).first() is None
        assert (await reader.get(AuthzRole, role.id)).permissions == ["flow:read"]
        assignments = (
            await reader.exec(select(AuthzRoleAssignment).where(AuthzRoleAssignment.role_id == role.id))
        ).all()
        assert len(assignments) == (1 if operation == "delete_assignment" else 0)
        assert (await store.verify_projection(reader))["valid"] is True


async def test_project_share_growth_and_admission_cost(scenario, record_property):
    """Measure actual compiler, lock, SQL and rule growth without child/member grant fanout."""
    import json
    import time
    import tracemalloc

    from sqlalchemy import event

    state = scenario
    users = [User(username=str(uuid4()), password=str(uuid4()), is_active=True) for _ in range(200)]
    children = [Flow(name=str(uuid4()), user_id=state.owner, folder_id=state.project) for _ in range(1000)]
    async with state.writable() as writer:
        await store.acquire_writer_lock(writer)
        writer.add_all(users)
        await writer.flush()
        writer.add_all(AuthzTeamMember(team_id=state.team, user_id=user.id, role="user") for user in users)
        writer.add(
            AuthzShare(
                resource_type="project",
                resource_id=state.project,
                scope="team",
                target_id=state.team,
                permission_level="write",
                created_by=state.owner,
            )
        )
        before_children = await store.reconcile_policy(writer)
        writer.add_all(children)
        await writer.flush()
        after_children = await store.reconcile_policy(writer)
        assert after_children.total == before_children.total
        assert after_children.inserted == after_children.deleted == 0

    metrics = {"users": 202, "teams": 1, "direct_flows": 1001, "rules": after_children.total}
    async with state.writable() as writer:
        start = time.perf_counter()
        await store.acquire_writer_lock(writer)
        locked = time.perf_counter()
        snapshot = await store.canonical_snapshot(writer)
        tracemalloc.start()
        compile_start = time.perf_counter()
        rules = store.compile_policy(snapshot)
        metrics["compile_ms"] = (time.perf_counter() - compile_start) * 1000
        metrics["compile_peak_bytes"] = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        result = await store.reconcile_rules(writer, rules)
        metrics["lock_wait_ms"] = (locked - start) * 1000
        metrics["noop_writes"] = result.inserted + result.deleted
        assert metrics["noop_writes"] == 0
    # Writer ownership lasts through the caller's commit, not just reconciliation.
    metrics["lock_hold_ms"] = (time.perf_counter() - locked) * 1000

    statements = []

    def count_query(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(state.engine.sync_engine, "before_cursor_execute", count_query)
    try:
        for name, operation in (
            ("single", lambda: permits(state.services[0], state)),
            (
                "batch_1000",
                lambda: state.services[0].batch_enforce(
                    user_id=state.recipient,
                    domain="*",
                    requests=tuple((f"flow:{flow.id}", "read") for flow in children),
                ),
            ),
            (
                "list_scope",
                lambda: state.services[0].get_resource_visibility(
                    user_id=state.recipient,
                    resource_type="flow",
                    act="read",
                ),
            ),
            (
                "owner_list_scope",
                lambda: state.services[0].get_resource_visibility(
                    user_id=state.owner,
                    resource_type="flow",
                    act="read",
                ),
            ),
        ):
            statements.clear()
            start = time.perf_counter()
            result = await operation()
            metrics[f"{name}_ms"] = (time.perf_counter() - start) * 1000
            metrics[f"{name}_queries"] = len(statements)
            if name == "single":
                assert result is True
            elif name == "batch_1000":
                assert result == [True] * 1000
            elif name == "list_scope":
                assert state.project in result.project_ids
                assert len(result.resource_ids) == 1
            else:
                metrics["owner_list_materialized_ids"] = len(result.resource_ids)
                assert result.owner_id == state.owner
                assert result.project_owner_id == state.owner
                # The owner's team grants survive, but 1,000 other owned
                # children never become concrete scope entries.
                assert result.resource_ids == (state.flow,)
                assert result.project_ids == (state.project,)
        async with state.readonly() as reader:
            metrics["loaded_rules"] = len(await store.load_rules(reader, user_id=state.recipient))
    finally:
        event.remove(state.engine.sync_engine, "before_cursor_execute", count_query)
    record_property("authorization_performance", json.dumps(metrics))
    print(json.dumps(metrics, sort_keys=True))  # noqa: T201 - measured acceptance output
