"""Pure canonical-state compiler; assignment lifetime belongs to canonical writers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from langflow.services.authorization.policy import (
    TEAM_ROLES,
    TeamRosterError,
    project_flow_actions,
    share_actions,
    validate_team_roster,
)

from .grammar import TEAM_ACTIONS, Rule, canonical_uuid, policy_actions, validate_rule

if TYPE_CHECKING:
    from collections.abc import Mapping
    from uuid import UUID

    from lfx.services.authorization.base import ShareRuleSnapshot

    from langflow.services.authorization.policy import TeamMemberState
    from langflow.services.authorization.repository import ResourceRecord


@dataclass(frozen=True, slots=True)
class RoleSnapshot:
    id: UUID
    permissions: tuple[str, ...]
    parent_role_id: UUID | None = None
    workspace_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class AssignmentSource:
    source_kind: str
    provider_id: str | None = None
    external_group: str | None = None


@dataclass(frozen=True, slots=True)
class AssignmentSnapshot:
    id: UUID
    user_id: UUID
    role_id: UUID
    domain_type: str = "global"
    domain_id: UUID | None = None
    sources: tuple[AssignmentSource, ...] = ()


@dataclass(frozen=True, slots=True)
class TeamSnapshot:
    id: UUID
    is_active: bool
    members: tuple[TeamMemberState, ...]


@dataclass(frozen=True, slots=True)
class PolicySnapshot:
    active_user_ids: frozenset[UUID] = frozenset()
    roles: tuple[RoleSnapshot, ...] = ()
    assignments: tuple[AssignmentSnapshot, ...] = ()
    teams: tuple[TeamSnapshot, ...] = ()
    shares: tuple[ShareRuleSnapshot, ...] = ()
    resources: tuple[ResourceRecord, ...] = ()


def canonical_domains(resource: ResourceRecord, projects: Mapping[UUID, ResourceRecord]) -> tuple[str, ...]:
    """Resolve literal domains without treating missing or conflicting context as global."""
    canonical_uuid(str(resource.resource_id))
    if not policy_actions(resource.resource_type):
        msg = "Unknown canonical resource."
        raise ValueError(msg)
    project_id = resource.resource_id if resource.resource_type == "project" else resource.project_id
    if resource.resource_type == "project" and resource.project_id not in {None, resource.resource_id}:
        msg = "A project cannot inherit from another project."
        raise ValueError(msg)
    if resource.resource_type not in {"flow", "project", "deployment"} and (
        resource.project_id is not None or resource.workspace_id is not None
    ):
        msg = "Personal resources have no project or workspace containment."
        raise ValueError(msg)
    domains: list[str] = []
    if project_id is not None:
        project = projects.get(project_id)
        if project is None or project.workspace_id != resource.workspace_id:
            msg = "Missing or inconsistent canonical project context."
            raise ValueError(msg)
        domains.append(f"project:{canonical_uuid(str(project_id))}")
    if resource.workspace_id is not None:
        domains.append(f"workspace:{canonical_uuid(str(resource.workspace_id))}")
    return (*domains, "*")


def _permissions(role_id: UUID, roles: Mapping[UUID, RoleSnapshot]) -> frozenset[str]:
    permissions: set[str] = set()
    seen: set[UUID] = set()
    current_id: UUID | None = role_id
    # Preserve the native traversal boundary, including its terminal iteration.
    for _ in range(32):
        if current_id is None:
            return frozenset(permissions)
        if current_id in seen or current_id not in roles:
            return frozenset()
        seen.add(current_id)
        role = roles[current_id]
        permissions.update(permission for permission in role.permissions if isinstance(permission, str))
        current_id = role.parent_role_id
    return frozenset()


def _assignment_domain(
    assignment: AssignmentSnapshot, role: RoleSnapshot, projects: Mapping[UUID, ResourceRecord]
) -> str | None:
    if assignment.domain_type == "global" and assignment.domain_id is None:
        return "*" if role.workspace_id is None else f"workspace:{canonical_uuid(str(role.workspace_id))}"
    if assignment.domain_id is None:
        return None
    canonical_uuid(str(assignment.domain_id))
    if assignment.domain_type == "workspace" and role.workspace_id in {None, assignment.domain_id}:
        return f"workspace:{assignment.domain_id}"
    if assignment.domain_type == "project":
        project = projects.get(assignment.domain_id)
        if project is not None and role.workspace_id in {None, project.workspace_id}:
            return f"project:{assignment.domain_id}"
    return None


def _surviving_assignment(assignment: AssignmentSnapshot) -> bool:
    # The canonical assignment is removed by its writer when its final source
    # ends. Requiring a source row here would erase supported legacy assignments.
    if not assignment.sources:
        return True
    return any(
        (source.source_kind == "manual" and source.provider_id is None and source.external_group is None)
        or (source.source_kind == "idp" and source.provider_id is not None and source.external_group is not None)
        for source in assignment.sources
    )


def role_rules(snapshot: PolicySnapshot, projects: Mapping[UUID, ResourceRecord]) -> set[Rule]:
    roles = {role.id: role for role in snapshot.roles}
    if len(roles) != len(snapshot.roles):
        msg = "Duplicate canonical role identity."
        raise ValueError(msg)
    rules: set[Rule] = set()
    for assignment in snapshot.assignments:
        role = roles.get(assignment.role_id)
        if role is None or assignment.user_id not in snapshot.active_user_ids or not _surviving_assignment(assignment):
            continue
        domain = _assignment_domain(assignment, role, projects)
        if domain is None:
            continue
        for permission in _permissions(role.id, roles):
            resource_type, separator, action = permission.partition(":")
            supported = policy_actions(resource_type)
            if not separator or not supported:
                continue
            actions = supported if action == "*" else supported & {action}
            rules.update(Rule("p", f"user:{assignment.user_id}", domain, f"{resource_type}/*", act) for act in actions)
    return rules


def _team_rules(snapshot: PolicySnapshot) -> tuple[set[Rule], set[UUID]]:
    rules: set[Rule] = set()
    eligible: set[UUID] = set()
    seen: set[UUID] = set()
    for team in snapshot.teams:
        canonical_uuid(str(team.id))
        if team.id in seen:
            msg = "Duplicate canonical team identity."
            raise ValueError(msg)
        seen.add(team.id)
        if any(member.is_active != (member.user_id in snapshot.active_user_ids) for member in team.members):
            msg = "Inconsistent canonical user activation state."
            raise ValueError(msg)
        try:
            validate_team_roster(team.members, team_is_active=team.is_active)
        except TeamRosterError as exc:
            if exc.code != "TEAM_ACTIVE_ADMIN_REQUIRED":
                raise
        else:
            if team.is_active:
                eligible.add(team.id)
        for member in team.members:
            if member.user_id not in snapshot.active_user_ids or member.role not in TEAM_ROLES:
                continue
            principal = f"team-role/{team.id}/{member.role}"
            rules.add(Rule("g", f"user:{member.user_id}", principal))
            rules.update(Rule("p", principal, "*", f"team/{team.id}", action) for action in TEAM_ACTIONS[member.role])
            if team.id in eligible:
                rules.add(Rule("g", f"user:{member.user_id}", f"team/{team.id}"))
    return rules, eligible


def _validate_identifiers(snapshot: PolicySnapshot) -> None:
    identifiers: list[UUID] = list(snapshot.active_user_ids)
    optional_identifiers: list[UUID | None] = []
    for role in snapshot.roles:
        identifiers.append(role.id)
        optional_identifiers.extend((role.parent_role_id, role.workspace_id))
    for assignment in snapshot.assignments:
        identifiers.extend((assignment.id, assignment.user_id, assignment.role_id))
        optional_identifiers.append(assignment.domain_id)
    for share in snapshot.shares:
        identifiers.extend((share.share_id, share.resource_id))
        optional_identifiers.append(share.target_id)
    for team in snapshot.teams:
        identifiers.append(team.id)
        identifiers.extend(member.user_id for member in team.members)
    for identifier in identifiers:
        canonical_uuid(str(identifier))
    for optional_identifier in optional_identifiers:
        if optional_identifier is not None:
            canonical_uuid(str(optional_identifier))


def compile_policy(snapshot: PolicySnapshot) -> tuple[Rule, ...]:
    """Compile complete immutable canonical input to sorted, deduplicated tuples.

    Unknown grants are inert. Incomplete or inconsistent canonical context and
    malformed derived output raise rather than returning a partial projection.
    This function performs no policy decision, SQL, I/O, or transaction action.
    """
    _validate_identifiers(snapshot)
    resources = {(resource.resource_type, resource.resource_id): resource for resource in snapshot.resources}
    if len(resources) != len(snapshot.resources):
        msg = "Duplicate canonical resource identity."
        raise ValueError(msg)
    projects = {
        resource.resource_id: resource for resource in snapshot.resources if resource.resource_type == "project"
    }
    for resource in snapshot.resources:
        canonical_domains(resource, projects)
    rules = role_rules(snapshot, projects)
    team_rules, eligible_teams = _team_rules(snapshot)
    rules.update(team_rules)
    for share in snapshot.shares:
        if share.scope == "user" and share.target_id in snapshot.active_user_ids:
            principal = f"user:{share.target_id}"
        elif share.scope == "team" and share.target_id in eligible_teams:
            principal = f"team/{share.target_id}"
        else:
            # PRIVATE/PUBLIC have separate application boundaries; they must
            # never become authenticated discovery or a synthetic user policy.
            continue
        if (share.resource_type, share.resource_id) not in resources:
            continue
        rules.update(share_rules(share, principal=principal))
    for rule in rules:
        validate_rule(rule)
    return tuple(sorted(rules))


def share_rules(share: ShareRuleSnapshot, *, principal: str) -> set[Rule]:
    """Expand one canonical share; eligibility is established by the complete compiler."""
    rules = {
        Rule("p", principal, "*", f"{share.resource_type}/{share.resource_id}", action)
        for action in share_actions(share.resource_type, share.permission_level)
    }
    if share.resource_type == "project":
        rules.update(
            Rule("p", principal, f"project:{share.resource_id}", "flow/*", action)
            for action in project_flow_actions(share.permission_level)
        )
    return rules
