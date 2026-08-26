"""Deterministic diff, export, and apply for administration state."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from langflow.cli.admin.manifest import (
    AdminState,
    ManifestAssignment,
    ManifestDomain,
    ManifestRole,
    ManifestSubject,
    ManifestTeam,
    ManifestUser,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from langflow.cli.admin.client import AdminClient


class ManifestResolutionError(ValueError):
    """Raised before writes when a complete manifest cannot be resolved."""


@dataclass
class _Operation:
    action: str
    resource: str
    key: str
    changes: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        result: dict[str, Any] = {"action": self.action, "resource": self.resource, "key": self.key}
        if self.changes:
            result["changes"] = self.changes
        return result


@dataclass
class _Plan:
    operations: list[_Operation]
    skipped: list[dict[str, Any]]


class AdminReconciler:
    """Converge a Langflow deployment on one strict ``AdminState`` manifest."""

    def __init__(self, client: AdminClient, *, environ: Mapping[str, str] | None = None) -> None:
        self.client = client
        self.environ = os.environ if environ is None else environ

    def diff(self, state: AdminState, *, prune: bool = False) -> list[dict[str, Any]]:
        """Return a stable, secret-free ordered drift description."""
        return [operation.public() for operation in self._build_plan(state, prune=prune).operations]

    def apply(self, state: AdminState, *, prune: bool = False) -> dict[str, Any]:
        """Validate fully, then stop at the first failed deterministic operation."""
        plan = self._build_plan(state, prune=prune)
        report: dict[str, Any] = {
            "status": "success",
            "applied": [],
            "skipped": plan.skipped,
            "failed": [],
            "pending": [],
        }
        for index, operation in enumerate(plan.operations):
            try:
                self._execute(operation)
            except Exception as exc:  # noqa: BLE001 - report an API/transport failure and stop
                failed = operation.public()
                failed["error"] = str(exc)
                report["status"] = "failed"
                report["failed"] = [failed]
                report["pending"] = [item.public() for item in plan.operations[index + 1 :]]
                return report
            report["applied"].append(operation.public())
        return report

    def export_state(self) -> AdminState:
        """Read complete current state into a portable, secret-free manifest."""
        users = self.client.list_users()
        teams = self.client.list_teams()
        roles = self.client.list_roles()
        users_by_id = {str(user["id"]): user for user in users}
        roles_by_id = {str(role["id"]): role for role in roles}

        manifest_users = [
            ManifestUser(username=user["username"], state="active" if user["is_active"] else "disabled")
            for user in users
        ]
        manifest_teams: list[ManifestTeam] = []
        for team in teams:
            members = self.client.list_team_members(str(team["id"]))
            member_names = sorted(
                users_by_id[str(member["user_id"])]["username"]
                for member in members
                if member.get("source", "manual") == "manual" and str(member["user_id"]) in users_by_id
            )
            manifest_teams.append(
                ManifestTeam(
                    adom_name=team["adom_name"],
                    display_name=team["team_name"],
                    description=team.get("description"),
                    state="active" if team["is_active"] else "disabled",
                    members=member_names,
                )
            )

        manifest_roles = [
            ManifestRole(
                name=role["name"],
                description=role.get("description"),
                parent=(roles_by_id.get(str(role.get("parent_role_id"))) or {}).get("name"),
                permissions=sorted(role.get("permissions", [])),
            )
            for role in roles
        ]
        assignments: list[ManifestAssignment] = []
        for user in users:
            for assignment in self.client.list_role_assignments(user=user["username"]):
                if not _has_manual_source(assignment):
                    continue
                role = roles_by_id.get(str(assignment["role_id"]))
                if role is None:
                    continue
                assignments.append(
                    ManifestAssignment(
                        subject=ManifestSubject(type="user", name=user["username"]),
                        role=role["name"],
                        domain=ManifestDomain(
                            type=assignment["domain_type"],
                            domain_id=assignment.get("domain_id"),
                        ),
                    )
                )
        if self._team_assignments_available():
            for team in teams:
                for assignment in self.client.list_role_assignments(team=team["adom_name"]):
                    if not _has_manual_source(assignment):
                        continue
                    role = roles_by_id.get(str(assignment["role_id"]))
                    if role is None:
                        continue
                    assignments.append(
                        ManifestAssignment(
                            subject=ManifestSubject(type="team", name=team["adom_name"]),
                            role=role["name"],
                            domain=ManifestDomain(
                                type=assignment["domain_type"],
                                domain_id=assignment.get("domain_id"),
                            ),
                        )
                    )

        return AdminState(
            apiVersion="langflow.ai/v1",
            kind="AdminState",
            users=sorted(manifest_users, key=lambda item: item.username),
            teams=sorted(manifest_teams, key=lambda item: item.adom_name),
            roles=sorted(manifest_roles, key=lambda item: item.name),
            assignments=sorted(
                assignments,
                key=lambda item: (item.subject.type, item.subject.name, item.role, item.domain.type),
            ),
        )

    def _build_plan(self, state: AdminState, *, prune: bool) -> _Plan:
        users = self.client.list_users()
        teams = self.client.list_teams()
        roles = self.client.list_roles()
        users_by_id = {str(item["id"]): item for item in users}
        users_by_name = {item["username"]: item for item in users}
        teams_by_id = {str(item["id"]): item for item in teams}
        teams_by_name = {item["adom_name"]: item for item in teams}
        roles_by_id = {str(item["id"]): item for item in roles}
        roles_by_name = {item["name"]: item for item in roles}
        operations: list[_Operation] = []
        skipped: list[dict[str, Any]] = []

        desired_user_names = {item.username for item in state.users}
        desired_team_names = {item.adom_name for item in state.teams}
        desired_role_names = {item.name for item in state.roles}
        desired_users_to_current = {
            item.username: users_by_id.get(str(item.id)) if item.id else users_by_name.get(item.username)
            for item in state.users
        }
        desired_teams_to_current = {
            item.adom_name: teams_by_id.get(str(item.id)) if item.id else teams_by_name.get(item.adom_name)
            for item in state.teams
        }
        desired_user_names_by_id = {
            str(current["id"]): desired_name
            for desired_name, current in desired_users_to_current.items()
            if current is not None
        }
        desired_role_names_by_id = {
            str(current["id"]): desired.name
            for desired in state.roles
            if (current := roles_by_id.get(str(desired.id)) if desired.id else roles_by_name.get(desired.name))
            is not None
        }
        available_user_names = set(users_by_name) | desired_user_names
        available_team_names = set(teams_by_name) | desired_team_names
        available_role_names = set(roles_by_name) | desired_role_names

        for desired in state.users:
            if desired.id is not None and str(desired.id) not in users_by_id:
                msg = f"User id {desired.id} does not exist on this target"
                raise ManifestResolutionError(msg)
        for desired in state.teams:
            if desired.id is not None and str(desired.id) not in teams_by_id:
                msg = f"Team id {desired.id} does not exist on this target"
                raise ManifestResolutionError(msg)
        for desired in state.roles:
            if desired.id is not None and str(desired.id) not in roles_by_id:
                msg = f"Role id {desired.id} does not exist on this target"
                raise ManifestResolutionError(msg)

        for desired_name, current in desired_users_to_current.items():
            conflict = users_by_name.get(desired_name)
            if current is not None and conflict is not None and conflict["id"] != current["id"]:
                msg = f"User rename to {desired_name!r} conflicts with an existing user"
                raise ManifestResolutionError(msg)
        for desired_name, current in desired_teams_to_current.items():
            conflict = teams_by_name.get(desired_name)
            if current is not None and conflict is not None and conflict["id"] != current["id"]:
                msg = f"Team rename to {desired_name!r} conflicts with an existing team"
                raise ManifestResolutionError(msg)
        for desired in state.roles:
            current = roles_by_id.get(str(desired.id)) if desired.id else roles_by_name.get(desired.name)
            conflict = roles_by_name.get(desired.name)
            if current is not None and conflict is not None and conflict["id"] != current["id"]:
                msg = f"Role rename to {desired.name!r} conflicts with an existing role"
                raise ManifestResolutionError(msg)

        for team in state.teams:
            unknown = sorted(set(team.members) - available_user_names)
            if unknown:
                msg = f"Team {team.adom_name!r} references unknown users: {unknown}"
                raise ManifestResolutionError(msg)
        for role in state.roles:
            if role.parent and role.parent not in available_role_names:
                msg = f"Role {role.name!r} references unknown parent role {role.parent!r}"
                raise ManifestResolutionError(msg)
        for assignment in state.assignments:
            if assignment.role not in available_role_names:
                msg = f"Assignment references unknown role {assignment.role!r}"
                raise ManifestResolutionError(msg)
            if assignment.subject.type == "user" and assignment.subject.name not in available_user_names:
                msg = f"Assignment references unknown user {assignment.subject.name!r}"
                raise ManifestResolutionError(msg)
            if assignment.subject.type == "team" and assignment.subject.name not in available_team_names:
                msg = f"Assignment references unknown team {assignment.subject.name!r}"
                raise ManifestResolutionError(msg)
            if assignment.subject.type == "team" and not self._team_assignments_available():
                msg = "This Langflow target does not advertise team-role assignment support"
                raise ManifestResolutionError(msg)

        for desired in _roles_in_parent_order(state.roles):
            current = roles_by_id.get(str(desired.id)) if desired.id else roles_by_name.get(desired.name)
            if current is None:
                operations.append(
                    _Operation(
                        "create",
                        "role",
                        desired.name,
                        payload={
                            "name": desired.name,
                            "description": desired.description,
                            "permissions": desired.permissions,
                            "parent": desired.parent,
                        },
                    )
                )
                continue
            changes = _role_changes(desired, current, roles_by_id)
            if changes and current.get("is_system"):
                msg = f"System role {current['name']!r} is readable and assignable but not editable"
                raise ManifestResolutionError(msg)
            if changes:
                operations.append(
                    _Operation(
                        "update",
                        "role",
                        desired.name,
                        changes,
                        {"identifier": str(current["id"]), **_role_payload(desired)},
                    )
                )

        for desired in sorted(state.users, key=lambda item: item.username):
            current = users_by_id.get(str(desired.id)) if desired.id else users_by_name.get(desired.username)
            if current is None:
                if not desired.password_env:
                    msg = f"New user {desired.username!r} requires a creation-only password_env reference"
                    raise ManifestResolutionError(msg)
                if not self.environ.get(desired.password_env):
                    msg = f"New user {desired.username!r} requires environment variable {desired.password_env!r}"
                    raise ManifestResolutionError(msg)
                operations.append(
                    _Operation(
                        "create",
                        "user",
                        desired.username,
                        payload={
                            "username": desired.username,
                            "password_env": desired.password_env,
                            "state": desired.state,
                        },
                    )
                )
                continue
            changes: list[str] = []
            payload: dict[str, Any] = {"identifier": str(current["id"])}
            if current["username"] != desired.username:
                changes.append("username")
                payload["username"] = desired.username
            desired_active = desired.state == "active"
            if current["is_active"] != desired_active:
                changes.append("state")
                payload["is_active"] = desired_active
            if changes:
                operations.append(_Operation("update", "user", desired.username, changes, payload))

        for desired in sorted(state.teams, key=lambda item: item.adom_name):
            current = teams_by_id.get(str(desired.id)) if desired.id else teams_by_name.get(desired.adom_name)
            if current is None:
                operations.append(
                    _Operation(
                        "create",
                        "team",
                        desired.adom_name,
                        payload={
                            "adom_name": desired.adom_name,
                            "display_name": desired.display_name,
                            "description": desired.description,
                            "active": desired.state == "active",
                        },
                    )
                )
                continue
            changes: list[str] = []
            payload = {"identifier": str(current["id"])}
            for manifest_field, api_field in (
                ("adom_name", "adom_name"),
                ("display_name", "team_name"),
                ("description", "description"),
            ):
                value = getattr(desired, manifest_field)
                if value != current.get(api_field):
                    changes.append(manifest_field)
                    payload[manifest_field] = value
            desired_active = desired.state == "active"
            if desired_active != current["is_active"]:
                changes.append("state")
                payload["active"] = desired_active
            if changes:
                operations.append(_Operation("update", "team", desired.adom_name, changes, payload))

        for desired in sorted(state.teams, key=lambda item: item.adom_name):
            current = teams_by_id.get(str(desired.id)) if desired.id else teams_by_name.get(desired.adom_name)
            if current is None:
                current_members: list[dict[str, Any]] = []
            else:
                current_members = self.client.list_team_members(str(current["id"]))
            members_by_user_id = {str(item["user_id"]): item for item in current_members}
            desired_member_ids = {
                str((desired_users_to_current.get(name) or users_by_name[name])["id"])
                for name in desired.members
                if desired_users_to_current.get(name) is not None or name in users_by_name
            }
            current_member_names = {
                desired_user_names_by_id.get(user_id, users_by_id[user_id]["username"])
                for user_id in members_by_user_id
                if user_id in users_by_id
            }
            operations.extend(
                _Operation(
                    "add",
                    "membership",
                    f"{desired.adom_name}/{username}",
                    payload={"team": desired.adom_name, "user": username},
                )
                for username in sorted(set(desired.members) - current_member_names)
            )
            if prune:
                for user_id, membership in sorted(members_by_user_id.items()):
                    if user_id in desired_member_ids:
                        continue
                    username = users_by_id.get(user_id, {}).get("username", user_id)
                    public = {"action": "remove", "resource": "membership", "key": f"{desired.adom_name}/{username}"}
                    if membership.get("source") != "manual":
                        skipped.append({**public, "reason": "externally_managed"})
                        continue
                    operations.append(
                        _Operation(
                            "remove",
                            "membership",
                            f"{desired.adom_name}/{username}",
                            payload={"team": desired.adom_name, "user": username},
                        )
                    )

        desired_assignments_by_subject: dict[tuple[str, str], set[tuple[str, str, str | None]]] = {}
        for item in state.assignments:
            desired_assignments_by_subject.setdefault((item.subject.type, item.subject.name), set()).add(
                (item.role, item.domain.type, str(item.domain.domain_id) if item.domain.domain_id else None)
            )
        prune_subjects = {("user", item.username) for item in state.users} | {
            ("team", item.adom_name) for item in state.teams
        }
        subjects = set(desired_assignments_by_subject) | (prune_subjects if prune else set())
        for subject_type, subject_name in sorted(subjects):
            if subject_type == "user":
                current_subject = desired_users_to_current.get(subject_name) or users_by_name.get(subject_name)
                lookup_name = current_subject["username"] if current_subject else subject_name
            else:
                current_subject = desired_teams_to_current.get(subject_name) or teams_by_name.get(subject_name)
                lookup_name = current_subject["adom_name"] if current_subject else subject_name
            if current_subject is None:
                current_assignments = []
            else:
                current_assignments = self.client.list_role_assignments(
                    user=lookup_name if subject_type == "user" else None,
                    team=lookup_name if subject_type == "team" else None,
                )
            current_by_key = {
                (
                    desired_role_names_by_id.get(
                        str(item["role_id"]),
                        roles_by_id.get(str(item["role_id"]), {}).get("name", str(item["role_id"])),
                    ),
                    item["domain_type"],
                    str(item.get("domain_id")) if item.get("domain_id") else None,
                ): item
                for item in current_assignments
            }
            desired_keys = desired_assignments_by_subject.get((subject_type, subject_name), set())
            for role_name, domain_type, domain_id in sorted(desired_keys - set(current_by_key)):
                operations.append(
                    _Operation(
                        "grant",
                        "role_assignment",
                        _assignment_key(subject_type, subject_name, role_name, domain_type, domain_id),
                        payload={
                            "user": subject_name if subject_type == "user" else None,
                            "team": subject_name if subject_type == "team" else None,
                            "role": role_name,
                            "domain_type": domain_type,
                            "domain_id": domain_id,
                        },
                    )
                )
            if prune:
                for key in sorted(set(current_by_key) - desired_keys):
                    assignment = current_by_key[key]
                    public_key = _assignment_key(subject_type, subject_name, *key)
                    if not _has_manual_source(assignment):
                        skipped.append(
                            {
                                "action": "revoke",
                                "resource": "role_assignment",
                                "key": public_key,
                                "reason": "externally_managed",
                            }
                        )
                        continue
                    operations.append(
                        _Operation(
                            "revoke",
                            "role_assignment",
                            public_key,
                            payload={"assignment_id": str(assignment["id"]), "team": subject_type == "team"},
                        )
                    )

        return _Plan(operations=operations, skipped=skipped)

    def _execute(self, operation: _Operation) -> None:
        payload = dict(operation.payload)
        if operation.resource == "role":
            if operation.action == "create":
                self.client.create_role(**payload)
            else:
                identifier = payload.pop("identifier")
                self.client.update_role(identifier, **payload)
            return
        if operation.resource == "user":
            if operation.action == "create":
                password_env = payload.pop("password_env")
                state = payload.pop("state")
                user = self.client.create_user(password=self.environ[password_env], **payload)
                desired_active = state == "active"
                if user.get("is_active") != desired_active:
                    self.client.update_user(str(user["id"]), is_active=desired_active)
            else:
                identifier = payload.pop("identifier")
                self.client.update_user(identifier, **payload)
            return
        if operation.resource == "team":
            if operation.action == "create":
                self.client.create_team(**payload)
            else:
                identifier = payload.pop("identifier")
                self.client.update_team(identifier, **payload)
            return
        if operation.resource == "membership":
            if operation.action == "add":
                self.client.add_team_member(payload["team"], payload["user"])
            else:
                self.client.remove_team_member(payload["team"], payload["user"])
            return
        if operation.resource == "role_assignment":
            if operation.action == "grant":
                self.client.grant_role(**payload)
            else:
                self.client.revoke_role_assignment(payload["assignment_id"], team=payload["team"])
            return
        msg = f"Unsupported administration operation {operation.public()}"
        raise RuntimeError(msg)

    def _team_assignments_available(self) -> bool:
        capabilities = self.client.capabilities()
        return bool(capabilities.get("features", {}).get("team_role_assignments", False))


def _roles_in_parent_order(roles: list[ManifestRole]) -> list[ManifestRole]:
    """Topologically order manifest roles and reject cycles before any write."""
    by_name = {role.name: role for role in roles}
    ordered: list[ManifestRole] = []
    temporary: set[str] = set()
    permanent: set[str] = set()

    def visit(role: ManifestRole) -> None:
        if role.name in permanent:
            return
        if role.name in temporary:
            msg = f"Role inheritance cycle includes {role.name!r}"
            raise ManifestResolutionError(msg)
        temporary.add(role.name)
        if role.parent in by_name:
            visit(by_name[role.parent])
        temporary.remove(role.name)
        permanent.add(role.name)
        ordered.append(role)

    for role in sorted(roles, key=lambda item: item.name):
        visit(role)
    return ordered


def _role_changes(desired: ManifestRole, current: dict[str, Any], roles_by_id: dict[str, dict[str, Any]]) -> list[str]:
    current_parent = roles_by_id.get(str(current.get("parent_role_id")), {}).get("name")
    changes = []
    if desired.name != current["name"]:
        changes.append("name")
    if desired.description != current.get("description"):
        changes.append("description")
    if sorted(desired.permissions) != sorted(current.get("permissions", [])):
        changes.append("permissions")
    if desired.parent != current_parent:
        changes.append("parent")
    return changes


def _role_payload(desired: ManifestRole) -> dict[str, Any]:
    return {
        "name": desired.name,
        "description": desired.description,
        "permissions": desired.permissions,
        "parent": desired.parent,
    }


def _assignment_key(
    subject_type: str,
    subject_name: str,
    role_name: str,
    domain_type: str,
    domain_id: str | None,
) -> str:
    domain = domain_type if domain_id is None else f"{domain_type}:{domain_id}"
    return f"{subject_type}:{subject_name}/{role_name}@{domain}"


def _has_manual_source(assignment: dict[str, Any]) -> bool:
    grants = assignment.get("grant_sources")
    if isinstance(grants, list):
        return any(grant.get("source_kind") == "manual" for grant in grants)
    return assignment.get("source", "manual") == "manual"
