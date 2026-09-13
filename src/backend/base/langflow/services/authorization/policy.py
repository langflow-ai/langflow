"""Shared grant vocabulary and team-management invariants for collaboration.

These rules consume server-resolved state. They do not authenticate a caller,
load grants, authorize a resource lookup, or replace transactional invariant
checks. The authorization service and mutation helpers own those boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING

from langflow.services.authorization.actions import (
    DeploymentAction,
    FileAction,
    FlowAction,
    KnowledgeBaseAction,
    ProjectAction,
    VariableAction,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID


TEAM_ROLES = frozenset({"admin", "maintainer", "user"})

# Preserve the existing API vocabulary; the dialog is a two-choice projection.
_SHARE_ACTIONS = MappingProxyType(
    {
        "read": frozenset({"read"}),
        "execute": frozenset({"read", "execute"}),
        "write": frozenset({"read", "write", "execute"}),
        "admin": frozenset({"read", "write", "execute", "delete"}),
    }
)
_RESOURCE_ACTIONS = MappingProxyType(
    {
        "flow": frozenset(action.value for action in FlowAction),
        "project": frozenset(action.value for action in ProjectAction),
        "deployment": frozenset(action.value for action in DeploymentAction),
        "knowledge_base": frozenset(action.value for action in KnowledgeBaseAction),
        "variable": frozenset(action.value for action in VariableAction),
        "file": frozenset(action.value for action in FileAction),
    }
)


class TeamOperation(str, Enum):
    """Team-management operations, separate from resource permission levels."""

    CREATE = "create"
    DELETE = "delete"
    LIST_ALL = "list_all"
    READ = "read"
    UPDATE = "update"
    SET_ACTIVE = "set_active"
    CHANGE_DIRECTORY_BINDING = "change_directory_binding"
    ADD_MEMBER = "add_member"
    REMOVE_MEMBER = "remove_member"
    CHANGE_ROLE = "change_role"


@dataclass(frozen=True, slots=True)
class TeamMemberState:
    """Minimal member state resolved from canonical membership and user rows."""

    user_id: UUID
    role: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class TeamRosterCounts:
    """Derived counts; never a second persisted membership source."""

    member_count: int
    active_member_count: int
    active_admin_count: int


class TeamRosterError(ValueError):
    """Invalid proposed roster; the mutation context determines HTTP status."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def share_actions(resource_type: str, permission_level: str) -> frozenset[str]:
    """Expand one applicable grant into supported actions on its resource.

    Args:
        resource_type: Canonical shareable resource slug.
        permission_level: Stored read, execute, write, or admin value.

    Returns:
        Supported actions; unknown resources or levels grant nothing. This
        expansion does not establish that the grant targets the current user.
    """
    return _SHARE_ACTIONS.get(permission_level, frozenset()) & _RESOURCE_ACTIONS.get(resource_type, frozenset())


def project_flow_actions(permission_level: str) -> frozenset[str]:
    """Expand an applicable project grant for its directly contained flows.

    Args:
        permission_level: Stored permission on the actual parent project.

    Returns:
        Child actions, including creation for editable projects. This does not
        grant access to sibling projects, recursively nested folders, or shares.
    """
    # A project grant must not authorize deletion of collaborator-owned children.
    actions = share_actions("flow", permission_level) - {FlowAction.DELETE.value}
    if FlowAction.WRITE.value in actions:
        return actions | {FlowAction.CREATE.value}
    return actions


def team_operation_action(
    operation: TeamOperation | str,
    *,
    target_role: str | None = None,
    new_role: str | None = None,
) -> str | None:
    """Classify a validated canonical operation; the service decides authority."""
    try:
        resolved = TeamOperation(operation)
    except ValueError:
        return None

    if resolved in {TeamOperation.ADD_MEMBER, TeamOperation.CHANGE_ROLE} and new_role not in TEAM_ROLES:
        return None
    if resolved in {TeamOperation.REMOVE_MEMBER, TeamOperation.CHANGE_ROLE} and target_role not in TEAM_ROLES:
        return None
    if resolved is TeamOperation.ADD_MEMBER:
        return f"add_member:{new_role}"
    if resolved is TeamOperation.REMOVE_MEMBER:
        return f"remove_member:{target_role}"
    if resolved is TeamOperation.CHANGE_ROLE:
        return f"change_role:{target_role}:{new_role}"
    return resolved.value


def validate_team_roster(members: Sequence[TeamMemberState], *, team_is_active: bool) -> TeamRosterCounts:
    """Validate a final roster already resolved under the mutation's DB locks.

    Args:
        members: Proposed final membership with current user activation state.
        team_is_active: Proposed final team activation state.

    Returns:
        Derived membership counts for the validated roster.

    Raises:
        TeamRosterError: Empty/duplicate/invalid-role roster or an active team
            without an active administrator. This function acquires no locks.
    """
    if not members:
        message = "A team must contain at least one member."
        raise TeamRosterError(code="TEAM_MEMBERS_REQUIRED", message=message)
    seen: set[UUID] = set()
    active_members = 0
    active_admins = 0
    for member in members:
        if member.user_id in seen:
            message = "Duplicate user in the proposed team roster."
            raise TeamRosterError(code="TEAM_MEMBERSHIP_EXISTS", message=message)
        seen.add(member.user_id)
        if member.role not in TEAM_ROLES:
            message = "Invalid team member role."
            raise TeamRosterError(code="TEAM_MEMBER_ROLE_INVALID", message=message)
        if member.is_active is True:
            active_members += 1
            active_admins += int(member.role == "admin")
    if team_is_active is True and not active_admins:
        message = "An active team must contain an active Team Admin."
        raise TeamRosterError(code="TEAM_ACTIVE_ADMIN_REQUIRED", message=message)
    return TeamRosterCounts(len(seen), active_members, active_admins)
