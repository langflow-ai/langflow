"""Source-grant projection for effective Team membership."""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from langflow.services.authorization.team_member_grants import (
    ensure_team_member_grant,
    reconcile_directory_team_members,
    remove_team_member_grant,
)
from langflow.services.database.models.auth import (
    AuthzTeam,
    AuthzTeamMember,
    AuthzTeamMemberGrant,
)
from langflow.services.database.models.user.model import User
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest_asyncio.fixture
async def grant_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(
            SQLModel.metadata.create_all,
            tables=[
                User.__table__,
                AuthzTeam.__table__,
                AuthzTeamMember.__table__,
                AuthzTeamMemberGrant.__table__,
            ],
        )
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


async def _seed(grant_session: AsyncSession):
    team = AuthzTeam(team_name="Engineering", adom_name="engineering")
    users = [
        User(username=f"user-{index}", password="")  # pragma: allowlist secret
        for index in range(3)
    ]
    grant_session.add(team)
    grant_session.add_all(users)
    await grant_session.flush()
    return team, users


@pytest.mark.asyncio
async def test_manual_and_directory_grants_share_one_effective_membership(grant_session: AsyncSession) -> None:
    team, users = await _seed(grant_session)

    directory = await ensure_team_member_grant(
        grant_session,
        team_id=team.id,
        user_id=users[0].id,
        source_kind="directory",
        provider_id="entra:tenant-a",
        external_group_id="group-a",
    )
    manual = await ensure_team_member_grant(
        grant_session,
        team_id=team.id,
        user_id=users[0].id,
        source_kind="manual",
        administrative_actor=uuid4(),
    )

    memberships = list((await grant_session.exec(select(AuthzTeamMember))).all())
    grants = list((await grant_session.exec(select(AuthzTeamMemberGrant))).all())
    assert directory.membership.id == manual.membership.id
    assert len(memberships) == 1
    assert memberships[0].source == "manual"
    assert {grant.source_kind for grant in grants} == {"directory", "manual"}


@pytest.mark.asyncio
async def test_removing_one_source_preserves_effective_membership(grant_session: AsyncSession) -> None:
    team, users = await _seed(grant_session)
    await ensure_team_member_grant(
        grant_session,
        team_id=team.id,
        user_id=users[0].id,
        source_kind="manual",
    )
    await ensure_team_member_grant(
        grant_session,
        team_id=team.id,
        user_id=users[0].id,
        source_kind="directory",
        provider_id="entra:tenant-a",
        external_group_id="group-a",
    )

    manual_removed = await remove_team_member_grant(
        grant_session,
        team_id=team.id,
        user_id=users[0].id,
        source_kind="manual",
    )
    assert manual_removed.membership_removed is False
    assert manual_removed.membership.source == "directory"

    directory_removed = await remove_team_member_grant(
        grant_session,
        team_id=team.id,
        user_id=users[0].id,
        source_kind="directory",
        provider_id="entra:tenant-a",
        external_group_id="group-a",
    )
    assert directory_removed.membership_removed is True
    assert (await grant_session.exec(select(AuthzTeamMember))).first() is None


@pytest.mark.asyncio
async def test_directory_reconciliation_is_idempotent_and_source_scoped(grant_session: AsyncSession) -> None:
    team, users = await _seed(grant_session)
    await ensure_team_member_grant(
        grant_session,
        team_id=team.id,
        user_id=users[0].id,
        source_kind="manual",
    )

    first = await reconcile_directory_team_members(
        grant_session,
        team_id=team.id,
        desired_user_ids={users[0].id, users[1].id},
        provider_id="entra:tenant-a",
        external_group_id="group-a",
    )
    second = await reconcile_directory_team_members(
        grant_session,
        team_id=team.id,
        desired_user_ids={users[0].id, users[1].id},
        provider_id="entra:tenant-a",
        external_group_id="group-a",
    )
    removed = await reconcile_directory_team_members(
        grant_session,
        team_id=team.id,
        desired_user_ids={users[2].id},
        provider_id="entra:tenant-a",
        external_group_id="group-a",
    )

    assert first.added_user_ids == frozenset({users[0].id, users[1].id})
    assert second.added_user_ids == frozenset()
    assert second.removed_user_ids == frozenset()
    assert removed.removed_user_ids == frozenset({users[0].id, users[1].id})
    assert removed.added_user_ids == frozenset({users[2].id})
    memberships = list((await grant_session.exec(select(AuthzTeamMember))).all())
    assert {membership.user_id for membership in memberships} == {users[0].id, users[2].id}


@pytest.mark.asyncio
async def test_directory_groups_are_independent_grant_sources(grant_session: AsyncSession) -> None:
    team, users = await _seed(grant_session)
    for group_id in ("group-a", "group-b"):
        await ensure_team_member_grant(
            grant_session,
            team_id=team.id,
            user_id=users[0].id,
            source_kind="directory",
            provider_id="entra:tenant-a",
            external_group_id=group_id,
        )

    result = await remove_team_member_grant(
        grant_session,
        team_id=team.id,
        user_id=users[0].id,
        source_kind="directory",
        provider_id="entra:tenant-a",
        external_group_id="group-a",
    )

    assert result.membership_removed is False
    grants = list((await grant_session.exec(select(AuthzTeamMemberGrant))).all())
    assert [(grant.provider_id, grant.external_group_id) for grant in grants] == [("entra:tenant-a", "group-b")]
