"""Permission contracts from the approved team-sharing implementation plan."""

from __future__ import annotations

from uuid import uuid4

import pytest
from langflow.services.authorization.policy import (
    TeamMemberState,
    TeamOperation,
    TeamRosterError,
    project_flow_actions,
    share_actions,
    team_operation_action,
    validate_team_roster,
)


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        ("read", {"read"}),
        ("execute", {"read", "execute"}),
        ("write", {"read", "execute", "write"}),
        ("admin", {"read", "execute", "write", "delete"}),
    ],
)
def test_flow_share_levels_preserve_existing_contract(level: str, expected: set[str]) -> None:
    assert share_actions("flow", level) == expected


@pytest.mark.parametrize("level", ["execute", "write"])
def test_dialog_modes_never_grant_deletion_deployment_or_sharing(level: str) -> None:
    assert not share_actions("flow", level) & {"delete", "deploy", "share", "create"}


@pytest.mark.parametrize("resource", ["project", "file", "variable", "knowledge_base"])
@pytest.mark.parametrize("level", ["execute", "write", "admin"])
def test_resource_actions_do_not_invent_execute_on_nonexecutable_resources(resource: str, level: str) -> None:
    assert "read" in share_actions(resource, level)
    assert "execute" not in share_actions(resource, level)
    assert "create" not in share_actions(resource, level)
    assert "ingest" not in share_actions(resource, level)


@pytest.mark.parametrize("resource", ["", "FLOW", "team", "share", "provider_account", "unknown"])
def test_unsupported_share_resources_grant_nothing(resource: str) -> None:
    assert share_actions(resource, "admin") == frozenset()


@pytest.mark.parametrize("level", ["", "WRITE", "editor", "maintainer", "owner", "*", "unknown"])
def test_unknown_permission_levels_grant_nothing(level: str) -> None:
    assert share_actions("flow", level) == frozenset()
    assert project_flow_actions(level) == frozenset()


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        ("read", {"read"}),
        ("execute", {"read", "execute"}),
        ("write", {"read", "execute", "write", "create"}),
        ("admin", {"read", "execute", "write", "create"}),
    ],
)
def test_project_inheritance_applies_to_children_not_project_execute(level: str, expected: set[str]) -> None:
    assert project_flow_actions(level) == expected
    assert "execute" not in share_actions("project", level)
    assert not project_flow_actions(level) & {"deploy", "delete"}


def test_direct_share_downgrade_does_not_cancel_an_independent_team_edit_grant() -> None:
    direct_actions = share_actions("flow", "execute")
    team_actions = share_actions("flow", "write")
    assert direct_actions | team_actions == {"read", "write", "execute"}


@pytest.mark.parametrize("role", ["admin", "maintainer", "user", None])
@pytest.mark.parametrize(
    "operation",
    [
        TeamOperation.CREATE,
        TeamOperation.DELETE,
        TeamOperation.LIST_ALL,
        TeamOperation.SET_ACTIVE,
        TeamOperation.CHANGE_DIRECTORY_BINDING,
    ],
)
@pytest.mark.asyncio
async def test_platform_operations_are_not_granted_by_team_roles(
    team_policy, role: str | None, operation: TeamOperation
) -> None:
    assert not await team_policy(operation, actor_is_active=True, actor_can_administer_platform=False, actor_role=role)
    assert await team_policy(operation, actor_is_active=True, actor_can_administer_platform=True, actor_role=role)


@pytest.mark.parametrize("role", ["admin", "maintainer", "user"])
@pytest.mark.asyncio
async def test_team_members_can_read_their_own_team(team_policy, role: str) -> None:
    assert await team_policy(
        TeamOperation.READ, actor_is_active=True, actor_can_administer_platform=False, actor_role=role
    )


@pytest.mark.parametrize("role", [None, "", "administrator", "owner", "ADMIN"])
@pytest.mark.asyncio
async def test_nonmembers_or_unrecognized_roles_cannot_manage_a_team(team_policy, role: str | None) -> None:
    for operation in [TeamOperation.READ, TeamOperation.UPDATE, TeamOperation.ADD_MEMBER]:
        assert not await team_policy(
            operation,
            actor_is_active=True,
            actor_can_administer_platform=False,
            actor_role=role,
            new_role="user",
        )


@pytest.mark.parametrize("role", ["maintainer", "user"])
@pytest.mark.asyncio
async def test_only_team_admin_can_edit_team_metadata(team_policy, role: str) -> None:
    assert not await team_policy(
        TeamOperation.UPDATE, actor_is_active=True, actor_can_administer_platform=False, actor_role=role
    )
    assert await team_policy(
        TeamOperation.UPDATE, actor_is_active=True, actor_can_administer_platform=False, actor_role="admin"
    )


@pytest.mark.parametrize("target_role", ["admin", "maintainer", "user"])
@pytest.mark.asyncio
async def test_maintainer_can_remove_only_ordinary_members(team_policy, target_role: str) -> None:
    assert await team_policy(
        TeamOperation.REMOVE_MEMBER,
        actor_is_active=True,
        actor_can_administer_platform=False,
        actor_role="maintainer",
        target_role=target_role,
    ) is (target_role == "user")


@pytest.mark.parametrize("new_role", ["admin", "maintainer", "user"])
@pytest.mark.asyncio
async def test_maintainer_can_add_only_ordinary_members_and_never_change_roles(team_policy, new_role: str) -> None:
    assert await team_policy(
        TeamOperation.ADD_MEMBER,
        actor_is_active=True,
        actor_can_administer_platform=False,
        actor_role="maintainer",
        new_role=new_role,
    ) is (new_role == "user")
    assert not await team_policy(
        TeamOperation.CHANGE_ROLE,
        actor_is_active=True,
        actor_can_administer_platform=False,
        actor_role="maintainer",
        target_role="maintainer",
        new_role=new_role,
    )


@pytest.mark.parametrize("target_role", ["admin", "maintainer", "user"])
@pytest.mark.parametrize("new_role", ["admin", "maintainer", "user"])
@pytest.mark.asyncio
async def test_team_admin_can_assign_roles_subject_to_separate_roster_invariants(
    team_policy, target_role: str, new_role: str
) -> None:
    assert await team_policy(
        TeamOperation.CHANGE_ROLE,
        actor_is_active=True,
        actor_can_administer_platform=False,
        actor_role="admin",
        target_role=target_role,
        new_role=new_role,
    )


@pytest.mark.parametrize("operation", list(TeamOperation))
@pytest.mark.asyncio
async def test_inactive_actor_has_no_team_authority_even_with_platform_flag(
    team_policy, operation: TeamOperation
) -> None:
    assert not await team_policy(
        operation,
        actor_is_active=False,
        actor_can_administer_platform=True,
        actor_role="admin",
        target_role="user",
        new_role="admin",
    )


@pytest.mark.parametrize("role", ["admin", "maintainer", "user", None])
@pytest.mark.asyncio
async def test_unknown_team_operation_is_denied(team_policy, role: str | None) -> None:
    assert not await team_policy("unknown", actor_is_active=True, actor_can_administer_platform=True, actor_role=role)


@pytest.mark.parametrize("invalid_role", [None, "", "ADMIN", "owner"])
@pytest.mark.asyncio
async def test_privileged_actor_cannot_assign_invalid_roles(team_policy, invalid_role: str | None) -> None:
    assert not await team_policy(
        TeamOperation.ADD_MEMBER,
        actor_is_active=True,
        actor_can_administer_platform=True,
        actor_role=None,
        new_role=invalid_role,
    )


@pytest.mark.parametrize("active", [False, True])
def test_empty_team_is_invalid_even_when_inactive(*, active: bool) -> None:
    with pytest.raises(TeamRosterError) as exc:
        validate_team_roster([], team_is_active=active)
    assert exc.value.code == "TEAM_MEMBERS_REQUIRED"


def test_active_team_needs_an_active_admin_not_just_an_admin_record() -> None:
    members = [
        TeamMemberState(user_id=uuid4(), role="admin", is_active=False),
        TeamMemberState(user_id=uuid4(), role="maintainer", is_active=True),
    ]
    with pytest.raises(TeamRosterError) as exc:
        validate_team_roster(members, team_is_active=True)
    assert exc.value.code == "TEAM_ACTIVE_ADMIN_REQUIRED"


def test_inactive_team_can_retain_members_while_waiting_for_admin_repair() -> None:
    members = [TeamMemberState(user_id=uuid4(), role="user", is_active=False)]
    counts = validate_team_roster(members, team_is_active=False)
    assert (counts.member_count, counts.active_member_count, counts.active_admin_count) == (1, 0, 0)


def test_valid_roster_counts_do_not_promote_maintainers() -> None:
    members = [
        TeamMemberState(user_id=uuid4(), role="admin", is_active=True),
        TeamMemberState(user_id=uuid4(), role="maintainer", is_active=True),
        TeamMemberState(user_id=uuid4(), role="user", is_active=False),
    ]
    counts = validate_team_roster(members, team_is_active=True)
    assert (counts.member_count, counts.active_member_count, counts.active_admin_count) == (3, 2, 1)


def test_duplicate_members_cannot_satisfy_invariants_as_distinct_users() -> None:
    user_id = uuid4()
    members = [
        TeamMemberState(user_id=user_id, role="admin", is_active=True),
        TeamMemberState(user_id=user_id, role="user", is_active=True),
    ]
    with pytest.raises(TeamRosterError, match="Duplicate"):
        validate_team_roster(members, team_is_active=True)


def test_invalid_role_is_not_accepted_as_an_inactive_legacy_member() -> None:
    members = [TeamMemberState(user_id=uuid4(), role="owner", is_active=False)]
    with pytest.raises(TeamRosterError, match="role"):
        validate_team_roster(members, team_is_active=False)


@pytest.mark.parametrize(
    "operation",
    [TeamOperation.ADD_MEMBER, TeamOperation.REMOVE_MEMBER, TeamOperation.CHANGE_ROLE],
)
@pytest.mark.asyncio
async def test_ordinary_member_cannot_mutate_membership(team_policy, operation: TeamOperation) -> None:
    assert not await team_policy(
        operation,
        actor_is_active=True,
        actor_can_administer_platform=False,
        actor_role="user",
        target_role="user",
        new_role="user",
    )


def test_deployment_share_does_not_grant_flow_deployment_or_creation() -> None:
    assert share_actions("deployment", "admin") == {"read", "write", "execute", "delete"}


@pytest.mark.parametrize("operation", [TeamOperation.REMOVE_MEMBER, TeamOperation.CHANGE_ROLE])
@pytest.mark.asyncio
async def test_missing_current_role_is_not_treated_as_an_ordinary_member(team_policy, operation: TeamOperation) -> None:
    assert not await team_policy(
        operation,
        actor_is_active=True,
        actor_can_administer_platform=True,
        actor_role=None,
        target_role=None,
        new_role="user",
    )


@pytest.fixture
def team_policy(policy_db):
    """Run the preserved team matrix on the actual service and its real database."""
    from types import SimpleNamespace

    from langflow.services.authorization.casbin import store
    from langflow.services.authorization.casbin.service import CasbinAuthorizationService
    from langflow.services.database.models.auth import AuthzTeam, AuthzTeamMember
    from langflow.services.database.models.user.model import User
    from lfx.services.authorization.context import authorization_session
    from sqlmodel.ext.asyncio.session import AsyncSession

    service = CasbinAuthorizationService(
        SimpleNamespace(
            auth_settings=SimpleNamespace(
                AUTHZ_ENABLED=True,
                AUTHZ_SUPERUSER_BYPASS=True,
            )
        )
    )

    async def allowed(
        operation, *, actor_is_active, actor_can_administer_platform, actor_role, target_role=None, new_role=None
    ):
        action = team_operation_action(operation, target_role=target_role, new_role=new_role)
        if action is None:
            return False
        actor = User(
            username=str(uuid4()),
            password=str(uuid4()),
            is_active=actor_is_active,
            is_superuser=actor_can_administer_platform,
        )
        admin = User(username=str(uuid4()), password=str(uuid4()), is_active=True)
        team = AuthzTeam(team_name=str(uuid4()), adom_name=uuid4().hex)
        async with AsyncSession(policy_db, expire_on_commit=False) as session:
            await store.acquire_writer_lock(session)
            session.add_all([actor, admin])
            await session.flush()
            session.add(team)
            await session.flush()
            session.add(AuthzTeamMember(team_id=team.id, user_id=admin.id, role="admin"))
            if actor_role in {"admin", "maintainer", "user"}:
                session.add(AuthzTeamMember(team_id=team.id, user_id=actor.id, role=actor_role))
            await store.reconcile_policy(session)
            with authorization_session(session):
                return await service.enforce(user_id=actor.id, domain="*", obj=f"team:{team.id}", act=action)

    return allowed
