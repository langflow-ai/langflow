"""Projection of independent sources into effective Team memberships."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from sqlalchemy import delete
from sqlmodel import col, select

from langflow.services.database.models.auth import AuthzTeamMember, AuthzTeamMemberGrant

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

TeamMemberGrantSource = Literal["manual", "directory", "legacy"]
_MEMBERSHIP_MISMATCH = "the supplied effective membership does not match the requested Team and user"
_GRANT_MISMATCH = "the supplied Team membership grant does not belong to the effective membership"
_MEMBERSHIP_NOT_FOUND = "Team membership not found"
_GRANT_NOT_FOUND = "Team membership grant not found"


class TeamMemberGrantNotFoundError(LookupError):
    """The requested provenance source does not exist."""

    def __init__(self, detail: str, *, membership: AuthzTeamMember | None = None) -> None:
        super().__init__(detail)
        self.membership = membership


@dataclass(frozen=True, slots=True)
class TeamMemberGrantChange:
    membership: AuthzTeamMember
    grant: AuthzTeamMemberGrant | None
    membership_created: bool = False
    grant_created: bool = False
    membership_removed: bool = False


@dataclass(frozen=True, slots=True)
class DirectoryTeamReconciliation:
    added_user_ids: frozenset[UUID]
    removed_user_ids: frozenset[UUID]
    preserved_user_ids: frozenset[UUID]


def _validate_source(
    *,
    source_kind: TeamMemberGrantSource,
    provider_id: str | None,
    external_group_id: str | None,
    legacy_source: str | None,
) -> None:
    if source_kind == "manual":
        valid = provider_id is None and external_group_id is None and legacy_source is None
    elif source_kind == "directory":
        valid = bool(provider_id and external_group_id) and legacy_source is None
    else:
        valid = provider_id is None and external_group_id is None and bool(legacy_source)
    if not valid:
        message = f"invalid {source_kind} Team membership grant provenance"
        raise ValueError(message)


def _grant_predicates(
    *,
    membership_id: UUID,
    source_kind: TeamMemberGrantSource,
    provider_id: str | None,
    external_group_id: str | None,
    legacy_source: str | None,
):
    predicates = [
        AuthzTeamMemberGrant.membership_id == membership_id,
        AuthzTeamMemberGrant.source_kind == source_kind,
    ]
    if source_kind == "directory":
        predicates.extend(
            [
                AuthzTeamMemberGrant.provider_id == provider_id,
                AuthzTeamMemberGrant.external_group_id == external_group_id,
            ]
        )
    elif source_kind == "legacy":
        predicates.append(AuthzTeamMemberGrant.legacy_source == legacy_source)
    return predicates


async def get_effective_team_member(
    session: AsyncSession,
    *,
    team_id: UUID,
    user_id: UUID,
) -> AuthzTeamMember | None:
    return (
        await session.exec(
            select(AuthzTeamMember).where(
                AuthzTeamMember.team_id == team_id,
                AuthzTeamMember.user_id == user_id,
            )
        )
    ).first()


async def get_team_member_grant(
    session: AsyncSession,
    *,
    membership_id: UUID,
    source_kind: TeamMemberGrantSource,
    provider_id: str | None = None,
    external_group_id: str | None = None,
    legacy_source: str | None = None,
) -> AuthzTeamMemberGrant | None:
    _validate_source(
        source_kind=source_kind,
        provider_id=provider_id,
        external_group_id=external_group_id,
        legacy_source=legacy_source,
    )
    return (
        await session.exec(
            select(AuthzTeamMemberGrant).where(
                *_grant_predicates(
                    membership_id=membership_id,
                    source_kind=source_kind,
                    provider_id=provider_id,
                    external_group_id=external_group_id,
                    legacy_source=legacy_source,
                )
            )
        )
    ).first()


async def _refresh_effective_source(session: AsyncSession, membership: AuthzTeamMember) -> bool:
    sources = set(
        (
            await session.exec(
                select(AuthzTeamMemberGrant.source_kind).where(AuthzTeamMemberGrant.membership_id == membership.id)
            )
        ).all()
    )
    if not sources:
        await session.delete(membership)
        await session.flush()
        return True
    membership.source = next(source for source in ("manual", "directory", "legacy") if source in sources)
    session.add(membership)
    await session.flush()
    return False


async def ensure_team_member_grant(
    session: AsyncSession,
    *,
    team_id: UUID,
    user_id: UUID,
    source_kind: TeamMemberGrantSource,
    provider_id: str | None = None,
    external_group_id: str | None = None,
    legacy_source: str | None = None,
    administrative_actor: UUID | None = None,
    membership: AuthzTeamMember | None = None,
    membership_is_new: bool = False,
) -> TeamMemberGrantChange:
    """Idempotently add one provenance source and materialize compatibility state."""
    _validate_source(
        source_kind=source_kind,
        provider_id=provider_id,
        external_group_id=external_group_id,
        legacy_source=legacy_source,
    )
    if membership is not None and (membership.team_id != team_id or membership.user_id != user_id):
        raise ValueError(_MEMBERSHIP_MISMATCH)
    if membership is None:
        membership = await get_effective_team_member(session, team_id=team_id, user_id=user_id)
    membership_created = membership is None or membership_is_new
    if membership is None:
        membership = AuthzTeamMember(team_id=team_id, user_id=user_id, source=source_kind)
        membership_is_new = True
    if membership_is_new:
        session.add(membership)
        await session.flush()
    grant = await get_team_member_grant(
        session,
        membership_id=membership.id,
        source_kind=source_kind,
        provider_id=provider_id,
        external_group_id=external_group_id,
        legacy_source=legacy_source,
    )
    grant_created = grant is None
    if grant is None:
        grant = AuthzTeamMemberGrant(
            membership_id=membership.id,
            source_kind=source_kind,
            provider_id=provider_id,
            external_group_id=external_group_id,
            legacy_source=legacy_source,
            administrative_actor=administrative_actor,
        )
        session.add(grant)
        await session.flush()
    await _refresh_effective_source(session, membership)
    return TeamMemberGrantChange(
        membership=membership,
        grant=grant,
        membership_created=membership_created,
        grant_created=grant_created,
    )


async def remove_team_member_grant(
    session: AsyncSession,
    *,
    team_id: UUID,
    user_id: UUID,
    source_kind: TeamMemberGrantSource,
    provider_id: str | None = None,
    external_group_id: str | None = None,
    legacy_source: str | None = None,
    membership: AuthzTeamMember | None = None,
    grant: AuthzTeamMemberGrant | None = None,
) -> TeamMemberGrantChange:
    """Remove only the named source and preserve membership while another remains."""
    _validate_source(
        source_kind=source_kind,
        provider_id=provider_id,
        external_group_id=external_group_id,
        legacy_source=legacy_source,
    )
    if membership is not None and (membership.team_id != team_id or membership.user_id != user_id):
        raise ValueError(_MEMBERSHIP_MISMATCH)
    if membership is None:
        membership = await get_effective_team_member(session, team_id=team_id, user_id=user_id)
    if membership is None:
        raise TeamMemberGrantNotFoundError(_MEMBERSHIP_NOT_FOUND)
    if grant is not None and grant.membership_id != membership.id:
        raise ValueError(_GRANT_MISMATCH)
    if grant is None:
        grant = await get_team_member_grant(
            session,
            membership_id=membership.id,
            source_kind=source_kind,
            provider_id=provider_id,
            external_group_id=external_group_id,
            legacy_source=legacy_source,
        )
    if grant is None:
        raise TeamMemberGrantNotFoundError(_GRANT_NOT_FOUND, membership=membership)
    await session.delete(grant)
    await session.flush()
    membership_removed = await _refresh_effective_source(session, membership)
    return TeamMemberGrantChange(
        membership=membership,
        grant=grant,
        membership_removed=membership_removed,
    )


async def reconcile_directory_team_members(
    session: AsyncSession,
    *,
    team_id: UUID,
    desired_user_ids: set[UUID],
    provider_id: str,
    external_group_id: str,
) -> DirectoryTeamReconciliation:
    """Apply one directory group's complete snapshot without touching other grants."""
    _validate_source(
        source_kind="directory",
        provider_id=provider_id,
        external_group_id=external_group_id,
        legacy_source=None,
    )
    existing_rows = list(
        (
            await session.exec(
                select(AuthzTeamMemberGrant, AuthzTeamMember)
                .join(AuthzTeamMember, AuthzTeamMember.id == AuthzTeamMemberGrant.membership_id)
                .where(
                    AuthzTeamMember.team_id == team_id,
                    AuthzTeamMemberGrant.source_kind == "directory",
                    AuthzTeamMemberGrant.provider_id == provider_id,
                    AuthzTeamMemberGrant.external_group_id == external_group_id,
                )
            )
        ).all()
    )
    existing_by_user = {membership.user_id: (grant, membership) for grant, membership in existing_rows}
    existing_user_ids = set(existing_by_user)
    added = desired_user_ids - existing_user_ids
    removed = existing_user_ids - desired_user_ids
    preserved = desired_user_ids & existing_user_ids

    if added:
        memberships = list(
            (
                await session.exec(
                    select(AuthzTeamMember).where(
                        AuthzTeamMember.team_id == team_id,
                        col(AuthzTeamMember.user_id).in_(added),
                    )
                )
            ).all()
        )
        by_user = {membership.user_id: membership for membership in memberships}
        new_memberships = [
            AuthzTeamMember(team_id=team_id, user_id=user_id, source="directory")
            for user_id in sorted(added - set(by_user), key=str)
        ]
        session.add_all(new_memberships)
        await session.flush()
        by_user.update({membership.user_id: membership for membership in new_memberships})
        session.add_all(
            AuthzTeamMemberGrant(
                membership_id=by_user[user_id].id,
                source_kind="directory",
                provider_id=provider_id,
                external_group_id=external_group_id,
            )
            for user_id in sorted(added, key=str)
        )
        await session.flush()

    if removed:
        removed_grant_ids = [existing_by_user[user_id][0].id for user_id in removed]
        await session.exec(delete(AuthzTeamMemberGrant).where(col(AuthzTeamMemberGrant.id).in_(removed_grant_ids)))
        await session.flush()
        for user_id in sorted(removed, key=str):
            await _refresh_effective_source(session, existing_by_user[user_id][1])

    return DirectoryTeamReconciliation(
        added_user_ids=frozenset(added),
        removed_user_ids=frozenset(removed),
        preserved_user_ids=frozenset(preserved),
    )


__all__ = [
    "DirectoryTeamReconciliation",
    "TeamMemberGrantChange",
    "TeamMemberGrantNotFoundError",
    "ensure_team_member_grant",
    "get_effective_team_member",
    "get_team_member_grant",
    "reconcile_directory_team_members",
    "remove_team_member_grant",
]
