"""Offline consistency checks and explicit repairs for authorization teams."""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path  # noqa: TC003 - Typer resolves this annotation at runtime
from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID

import typer
from lfx.services.authorization import AuthorizationMutation, AuthorizationMutationKind
from sqlalchemy import delete, update
from sqlmodel import col, select

from langflow.services.authorization.audit import stage_mutation_audit
from langflow.services.authorization.lifecycle import safe_identity_mutation_committed, stage_identity_mutation
from langflow.services.authorization.repository import load_resource, supported_actions
from langflow.services.database.models.auth import AuthzShare, AuthzTeam, AuthzTeamMember, TeamRole
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_authorization_service, session_scope
from langflow.services.utils import initialize_services

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


authz_app = typer.Typer(no_args_is_help=True, help="Inspect and repair authorization data.")


@dataclass(frozen=True, slots=True)
class TeamConsistencyFinding:
    code: str
    team_id: str | None
    detail: str
    reference_id: str | None = None


@dataclass(frozen=True, slots=True)
class TeamConsistencyReport:
    teams_checked: int
    findings: tuple[TeamConsistencyFinding, ...]

    @property
    def valid(self) -> bool:
        return not self.findings

    def to_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "teams_checked": self.teams_checked,
            "finding_count": len(self.findings),
            "findings": [asdict(finding) for finding in self.findings],
        }


@dataclass(frozen=True, slots=True)
class TeamRepairInstruction:
    team_id: UUID
    admin_user_id: UUID | None = None
    retire: bool = False


async def inspect_team_consistency(session: AsyncSession) -> TeamConsistencyReport:
    """Return a deterministic, non-secret snapshot of invalid team references."""
    teams = list((await session.exec(select(AuthzTeam).order_by(col(AuthzTeam.id)))).all())
    members = list((await session.exec(select(AuthzTeamMember).order_by(col(AuthzTeamMember.team_id)))).all())
    users = list((await session.exec(select(User.id, User.is_active))).all())
    shares = list((await session.exec(select(AuthzShare).order_by(col(AuthzShare.id)))).all())
    team_by_id = {team.id: team for team in teams}
    user_active = dict(users)
    by_team: dict[UUID, list[AuthzTeamMember]] = {}
    findings: list[TeamConsistencyFinding] = []

    pairs = Counter((member.team_id, member.user_id) for member in members)
    for member in members:
        by_team.setdefault(member.team_id, []).append(member)
        if member.team_id not in team_by_id:
            findings.append(
                TeamConsistencyFinding(
                    "ORPHAN_TEAM_MEMBERSHIP",
                    str(member.team_id),
                    "Membership references a missing team.",
                    str(member.id),
                )
            )
        if member.user_id not in user_active:
            findings.append(
                TeamConsistencyFinding(
                    "ORPHAN_USER_MEMBERSHIP",
                    str(member.team_id),
                    "Membership references a missing user.",
                    str(member.id),
                )
            )
        if not member.source.strip():
            findings.append(
                TeamConsistencyFinding(
                    "INVALID_MEMBERSHIP_SOURCE",
                    str(member.team_id),
                    "Membership source is empty.",
                    str(member.id),
                )
            )
    for (team_id, user_id), count in pairs.items():
        if count > 1:
            findings.append(
                TeamConsistencyFinding(
                    "DUPLICATE_TEAM_MEMBERSHIP",
                    str(team_id),
                    f"User has {count} membership records in one team.",
                    str(user_id),
                )
            )

    for team in teams:
        roster = by_team.get(team.id, [])
        active = [member for member in roster if user_active.get(member.user_id) is True]
        active_admins = [member for member in active if member.role == TeamRole.ADMIN.value]
        if not roster:
            findings.append(TeamConsistencyFinding("EMPTY_TEAM", str(team.id), "Team has no memberships."))
        elif not active:
            findings.append(
                TeamConsistencyFinding("NO_ACTIVE_MEMBERS", str(team.id), "Team has no active user memberships.")
            )
        if team.is_active and not active_admins:
            findings.append(
                TeamConsistencyFinding(
                    "ACTIVE_TEAM_WITHOUT_ADMIN",
                    str(team.id),
                    "Active team has no active Team Admin.",
                )
            )

    for share in shares:
        if share.scope == "team" and share.target_id not in team_by_id:
            findings.append(
                TeamConsistencyFinding(
                    "ORPHAN_TEAM_SHARE",
                    str(share.target_id) if share.target_id else None,
                    "Share references a missing team.",
                    str(share.id),
                )
            )
        elif share.scope == "user" and share.target_id not in user_active:
            findings.append(
                TeamConsistencyFinding(
                    "ORPHAN_USER_SHARE",
                    None,
                    "Share references a missing user.",
                    str(share.id),
                )
            )
        if (
            supported_actions(share.resource_type)
            and await load_resource(
                session,
                resource_type=share.resource_type,
                resource_id=share.resource_id,
            )
            is None
        ):
            findings.append(
                TeamConsistencyFinding(
                    "ORPHAN_RESOURCE_SHARE",
                    None,
                    "Share references a missing canonical resource.",
                    str(share.id),
                )
            )
    findings.sort(key=lambda finding: (finding.code, finding.team_id or "", finding.reference_id or ""))
    return TeamConsistencyReport(teams_checked=len(teams), findings=tuple(findings))


def _parse_mapping(raw: Any) -> tuple[TeamRepairInstruction, ...]:
    entries = raw.get("teams") if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        msg = "Repair mapping must be a list or an object with a 'teams' list."
        raise TypeError(msg)
    instructions: list[TeamRepairInstruction] = []
    seen: set[UUID] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            msg = f"Repair entry {index} must be an object."
            raise TypeError(msg)
        unknown = set(entry) - {"team_id", "admin_user_id", "retire"}
        if unknown:
            msg = f"Repair entry {index} has unsupported fields: {', '.join(sorted(unknown))}."
            raise ValueError(msg)
        try:
            team_id = UUID(str(entry["team_id"]))
            admin_id = UUID(str(entry["admin_user_id"])) if entry.get("admin_user_id") else None
        except (KeyError, TypeError, ValueError) as exc:
            msg = f"Repair entry {index} contains an invalid UUID."
            raise ValueError(msg) from exc
        retire = entry.get("retire", False)
        if not isinstance(retire, bool) or (admin_id is None) == (not retire):
            msg = f"Repair entry {index} must specify exactly one of admin_user_id or retire=true."
            raise ValueError(msg)
        if team_id in seen:
            msg = f"Team {team_id} occurs more than once in the repair mapping."
            raise ValueError(msg)
        seen.add(team_id)
        instructions.append(TeamRepairInstruction(team_id, admin_id, retire))
    return tuple(instructions)


async def repair_teams(
    session: AsyncSession,
    instructions: tuple[TeamRepairInstruction, ...],
) -> tuple[int, tuple[AuthorizationMutation, ...]]:
    """Validate the complete mapping, then apply it in one transaction."""
    await get_authorization_service().acquire_identity_mutation_lock(
        session=session,
        kind=AuthorizationMutationKind.TEAM_UPDATED,
    )
    validated: list[tuple[TeamRepairInstruction, AuthzTeam, AuthzTeamMember | None]] = []
    for instruction in sorted(instructions, key=lambda item: str(item.team_id)):
        team = await session.get(AuthzTeam, instruction.team_id)
        if team is None:
            msg = f"Team {instruction.team_id} does not exist."
            raise ValueError(msg)
        members = list(
            (await session.exec(select(AuthzTeamMember).where(AuthzTeamMember.team_id == instruction.team_id))).all()
        )
        if instruction.retire:
            if members:
                msg = f"Team {instruction.team_id} is not empty and cannot be retired by legacy repair."
                raise ValueError(msg)
            validated.append((instruction, team, None))
            continue
        user = await session.get(User, instruction.admin_user_id)
        member = next((row for row in members if row.user_id == instruction.admin_user_id), None)
        if user is None or user.is_active is not True or member is None:
            msg = f"Nominated administrator for team {instruction.team_id} must be an active existing member."
            raise ValueError(msg)
        validated.append((instruction, team, member))

    service = get_authorization_service()
    events: list[AuthorizationMutation] = []
    now = datetime.now(timezone.utc)
    for instruction, _team_hint, member_hint in validated:
        if session.get_bind().dialect.name == "sqlite":
            await session.exec(
                update(AuthzTeam)
                .where(col(AuthzTeam.id) == instruction.team_id)
                .values(updated_at=AuthzTeam.updated_at)
            )
        team = (
            await session.exec(select(AuthzTeam).where(AuthzTeam.id == instruction.team_id).with_for_update())
        ).one()
        if instruction.retire:
            shares = list(
                (
                    await session.exec(
                        select(AuthzShare)
                        .where(AuthzShare.scope == "team", AuthzShare.target_id == team.id)
                        .with_for_update()
                    )
                ).all()
            )
            for share in shares:
                stage_mutation_audit(
                    session=session,
                    user_id=None,
                    action="share:delete",
                    obj=f"{share.resource_type}:{share.resource_id}",
                    details={"share_id": str(share.id), "reason": "legacy_team_retired"},
                )
            if shares:
                await session.exec(delete(AuthzShare).where(col(AuthzShare.id).in_([share.id for share in shares])))
            await session.delete(team)
            event = AuthorizationMutation(
                kind=AuthorizationMutationKind.TEAM_DELETED,
                entity_id=team.id,
                team_id=team.id,
                policy_relevant_fields=("adom_name", "is_active"),
                previous_identifier=team.adom_name,
            )
            stage_mutation_audit(
                session=session,
                user_id=None,
                action="team:retire",
                obj=f"team:{team.id}",
                details={"reason": "legacy_repair", "team_shares_removed": len(shares)},
            )
        else:
            assert member_hint is not None  # noqa: S101 - validated mapping invariant
            member = (
                await session.exec(
                    select(AuthzTeamMember).where(AuthzTeamMember.id == member_hint.id).with_for_update()
                )
            ).one()
            previous_role = member.role
            member.role = TeamRole.ADMIN.value
            member.updated_at = now
            team.is_active = True
            team.inactivation_reason = None
            team.updated_at = now
            session.add(member)
            session.add(team)
            if previous_role != member.role:
                role_event = AuthorizationMutation(
                    kind=AuthorizationMutationKind.TEAM_MEMBER_ROLE_CHANGED,
                    entity_id=member.id,
                    affected_user_ids=(member.user_id,),
                    team_id=team.id,
                    policy_relevant_fields=("role",),
                    previous_identifier=previous_role,
                )
                events.append(role_event)
                stage_mutation_audit(
                    session=session,
                    user_id=None,
                    action="team_member:role_changed",
                    obj=f"team:{team.id}",
                    details={
                        "user_id": str(member.user_id),
                        "previous_role": previous_role,
                        "new_role": member.role,
                        "reason": "legacy_repair",
                    },
                )
            event = AuthorizationMutation(
                kind=AuthorizationMutationKind.TEAM_UPDATED,
                entity_id=team.id,
                affected_user_ids=(member.user_id,),
                team_id=team.id,
                policy_relevant_fields=("is_active", "inactivation_reason"),
            )
            stage_mutation_audit(
                session=session,
                user_id=None,
                action="team:repair",
                obj=f"team:{team.id}",
                details={"admin_user_id": str(member.user_id), "reason": "legacy_repair"},
            )
        events.append(event)
    await session.flush()
    for event in events:
        await stage_identity_mutation(service, session, event)
    return len(validated), tuple(events)


async def _run_check() -> TeamConsistencyReport:
    await initialize_services(skip_superuser_setup=True, skip_authorization_readiness=True)
    async with session_scope() as session:
        return await inspect_team_consistency(session)


@authz_app.command("teams-check")
def teams_check() -> None:
    """Report invalid legacy teams and dangling authorization references."""
    report = asyncio.run(_run_check())
    typer.echo(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    if not report.valid:
        raise typer.Exit(code=1)


async def _run_repair(mapping_file: Path) -> tuple[int, TeamConsistencyReport]:
    raw = json.loads(mapping_file.read_text(encoding="utf-8"))
    instructions = _parse_mapping(raw)
    await initialize_services(skip_superuser_setup=True, skip_authorization_readiness=True)
    service = get_authorization_service()
    async with session_scope() as session:
        try:
            from langflow.services.database.lock_retry import run_with_lock_retry

            async def operation(_attempt: int):
                return await repair_teams(session, instructions)

            repaired, events = await run_with_lock_retry(operation, session=session, description="repair legacy teams")
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    for event in events:
        await safe_identity_mutation_committed(service, event)
    async with session_scope() as session:
        report = await inspect_team_consistency(session)
    return repaired, report


@authz_app.command("teams-repair")
def teams_repair(
    mapping_file: Path = typer.Option(..., "--mapping-file", exists=True, file_okay=True, dir_okay=False),
) -> None:
    """Apply an explicit, fully validated legacy-team repair mapping."""
    try:
        repaired, report = asyncio.run(_run_repair(mapping_file))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        typer.echo(f"Repair rejected: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    output = {"repaired": repaired, "post_repair": report.to_dict()}
    typer.echo(json.dumps(output, indent=2, sort_keys=True))
    if not report.valid:
        raise typer.Exit(code=1)


async def _policy_operation(*, rebuild: bool, replace_existing: bool = False) -> dict[str, int | bool]:
    # Optional imports stay behind the explicit operator command; ordinary
    # Langflow/LFX installations do not need or import the policy dependency.
    from langflow.services.authorization.casbin import store
    from langflow.services.authorization.casbin.service import CasbinAuthorizationService
    from langflow.services.database.lock_retry import run_with_lock_retry

    await initialize_services(skip_superuser_setup=True, skip_authorization_readiness=True)
    if not isinstance(get_authorization_service(), CasbinAuthorizationService):
        msg = "Register the Casbin authorization service before checking or rebuilding its projection."
        raise TypeError(msg)
    if not rebuild:
        async with store.read_snapshot() as session:
            return await store.verify_projection(session)
    async with session_scope() as session:

        async def operation(_attempt: int) -> dict[str, int | bool]:
            await store.acquire_writer_lock(session)
            before = await store.verify_projection(session)
            if (before["unexpected"] or before["invalid"]) and not replace_existing:
                msg = (
                    "Existing policy cannot be replaced implicitly. "
                    "Verify canonical state, then use --replace-existing."
                )
                raise ValueError(msg)
            wanted = store.compile_policy(await store.canonical_snapshot(session, validate_teams=True))
            result = await store.reconcile_rules(session, wanted, replace_invalid=replace_existing)
            store.enforcer_for(wanted)
            stage_mutation_audit(
                session=session,
                user_id=None,
                action="authorization:rebuild",
                obj="authorization:*",
                details={"inserted": result.inserted, "deleted": result.deleted, "total": result.total},
            )
            return {"valid": True, "inserted": result.inserted, "deleted": result.deleted, "total": result.total}

        return await run_with_lock_retry(operation, session=session, description="rebuild authorization policy")


@authz_app.command("policy-check")
def policy_check() -> None:
    """Verify canonical policy against the selected service's derived projection."""
    report = asyncio.run(_policy_operation(rebuild=False))
    typer.echo(json.dumps(report, sort_keys=True))
    if not report["valid"]:
        raise typer.Exit(code=1)


@authz_app.command("policy-rebuild")
def policy_rebuild(*, replace_existing: Annotated[bool, typer.Option("--replace-existing")] = False) -> None:
    """Reconcile canonical policy atomically; explicitly authorize foreign-policy replacement."""
    try:
        report = asyncio.run(_policy_operation(rebuild=True, replace_existing=replace_existing))
    except (TypeError, ValueError) as exc:
        typer.echo(f"Rebuild rejected: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(json.dumps(report, sort_keys=True))


__all__ = [
    "TeamConsistencyFinding",
    "TeamConsistencyReport",
    "TeamRepairInstruction",
    "authz_app",
    "inspect_team_consistency",
    "repair_teams",
]
