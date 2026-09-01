"""Behavioral tests for declarative administration reconciliation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

import pytest
from langflow.cli.admin.manifest import AdminState
from langflow.cli.admin.reconcile import AdminReconciler, ManifestResolutionError

ALICE_ID = "00000000-0000-0000-0000-000000000001"
BOB_ID = "00000000-0000-0000-0000-000000000002"
CAROL_ID = "00000000-0000-0000-0000-000000000003"
TEAM_ID = "00000000-0000-0000-0000-000000000010"
VIEWER_ID = "00000000-0000-0000-0000-000000000020"
OPERATOR_ID = "00000000-0000-0000-0000-000000000021"


class FakeAdminClient:
    """Stateful API double that makes convergence observable."""

    def __init__(self) -> None:
        self.users: list[dict[str, Any]] = []
        self.teams: list[dict[str, Any]] = []
        self.roles: list[dict[str, Any]] = [
            {
                "id": VIEWER_ID,
                "name": "viewer",
                "description": "System viewer",
                "permissions": ["flow:read"],
                "parent_role_id": None,
                "is_system": True,
            }
        ]
        self.members: dict[str, list[dict[str, Any]]] = {}
        self.assignments: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self.calls: list[str] = []
        self._next_id = 100

    def _id(self) -> str:
        self._next_id += 1
        return str(UUID(int=self._next_id))

    def capabilities(self) -> dict[str, Any]:
        return {"features": {"team_role_assignments": False}}

    def list_users(self) -> list[dict[str, Any]]:
        return deepcopy(self.users)

    def list_teams(self) -> list[dict[str, Any]]:
        return deepcopy(self.teams)

    def list_roles(self) -> list[dict[str, Any]]:
        return deepcopy(self.roles)

    def list_team_members(self, team: str) -> list[dict[str, Any]]:
        team_id = self._team(team)["id"]
        return deepcopy(self.members.get(team_id, []))

    def list_role_assignments(self, *, user=None, team=None, role=None) -> list[dict[str, Any]]:  # noqa: ARG002
        if user is not None:
            self._user(user)
        if team is not None:
            self._team(team)
        subject = ("user", user) if user is not None else ("team", team)
        return deepcopy(self.assignments.get(subject, []))

    def create_role(self, *, name: str, permissions: list[str], description=None, parent=None) -> dict[str, Any]:
        self.calls.append(f"role:create:{name}")
        parent_role_id = self._role(parent)["id"] if parent else None
        role = {
            "id": OPERATOR_ID if name == "operator" else self._id(),
            "name": name,
            "description": description,
            "permissions": permissions,
            "parent_role_id": parent_role_id,
            "is_system": False,
        }
        self.roles.append(role)
        return deepcopy(role)

    def update_role(self, identifier: str, **payload: Any) -> dict[str, Any]:
        role = self._role(identifier)
        self.calls.append(f"role:update:{role['name']}")
        parent = payload.pop("parent", None)
        role.update(payload)
        role["parent_role_id"] = self._role(parent)["id"] if parent else None
        return deepcopy(role)

    def create_user(self, *, username: str, password: str) -> dict[str, Any]:
        assert password  # pragma: allowlist secret
        self.calls.append(f"user:create:{username}")
        user = {"id": ALICE_ID if username == "alice" else self._id(), "username": username, "is_active": True}
        self.users.append(user)
        return deepcopy(user)

    def update_user(self, identifier: str, **payload: Any) -> dict[str, Any]:
        user = self._user(identifier)
        previous_username = user["username"]
        self.calls.append(f"user:update:{previous_username}")
        user.update({key: value for key, value in payload.items() if value is not None})
        if user["username"] != previous_username:
            previous_key = ("user", previous_username)
            if previous_key in self.assignments:
                self.assignments[("user", user["username"])] = self.assignments.pop(previous_key)
        return deepcopy(user)

    def create_team(self, *, adom_name: str, display_name: str, description=None, active=True) -> dict[str, Any]:
        self.calls.append(f"team:create:{adom_name}")
        team = {
            "id": TEAM_ID,
            "adom_name": adom_name,
            "team_name": display_name,
            "description": description,
            "is_active": active,
        }
        self.teams.append(team)
        return deepcopy(team)

    def update_team(self, identifier: str, **payload: Any) -> dict[str, Any]:
        team = self._team(identifier)
        self.calls.append(f"team:update:{team['adom_name']}")
        field_map = {"display_name": "team_name", "active": "is_active"}
        team.update({field_map.get(key, key): value for key, value in payload.items() if value is not None})
        return deepcopy(team)

    def add_team_member(self, team: str, user: str) -> dict[str, Any]:
        team_row = self._team(team)
        user_row = self._user(user)
        self.calls.append(f"membership:add:{team}/{user}")
        member = {"id": self._id(), "team_id": team_row["id"], "user_id": user_row["id"], "source": "manual"}
        self.members.setdefault(team_row["id"], []).append(member)
        return deepcopy(member)

    def remove_team_member(self, team: str, user: str) -> None:
        team_row = self._team(team)
        user_row = self._user(user)
        self.calls.append(f"membership:remove:{team}/{user}")
        self.members[team_row["id"]] = [
            row for row in self.members.get(team_row["id"], []) if row["user_id"] != user_row["id"]
        ]

    def grant_role(self, *, role: str, user=None, team=None, domain_type="global", domain_id=None) -> dict[str, Any]:
        subject = ("user", user) if user is not None else ("team", team)
        role_row = self._role(role)
        self.calls.append(f"assignment:grant:{subject[0]}:{subject[1]}/{role}")
        assignment = {
            "id": self._id(),
            "user_id": self._user(user)["id"] if user else None,
            "team_id": self._team(team)["id"] if team else None,
            "role_id": role_row["id"],
            "domain_type": domain_type,
            "domain_id": domain_id,
            "grant_sources": [{"source_kind": "manual"}],
        }
        self.assignments.setdefault(subject, []).append(assignment)
        return deepcopy(assignment)

    def revoke_role_assignment(self, assignment_id: str, *, team: bool = False) -> None:  # noqa: ARG002
        self.calls.append(f"assignment:revoke:{assignment_id}")
        for subject, rows in self.assignments.items():
            self.assignments[subject] = [row for row in rows if row["id"] != assignment_id]

    def _user(self, identifier: str) -> dict[str, Any]:
        return next(row for row in self.users if identifier in (row["id"], row["username"]))

    def _team(self, identifier: str) -> dict[str, Any]:
        return next(row for row in self.teams if identifier in (row["id"], row["adom_name"]))

    def _role(self, identifier: str) -> dict[str, Any]:
        return next(row for row in self.roles if identifier in (row["id"], row["name"]))


def test_apply_is_dependency_ordered_and_rerun_converges() -> None:
    client = FakeAdminClient()
    state = AdminState.model_validate(
        {
            "apiVersion": "langflow.ai/v1",
            "kind": "AdminState",
            "roles": [{"name": "operator", "permissions": ["team:manage"]}],
            "users": [
                {"username": "alice", "password_env": "ALICE_PASSWORD"}  # pragma: allowlist secret
            ],
            "teams": [{"adom_name": "ops", "display_name": "Operators", "members": ["alice"]}],
            "assignments": [
                {
                    "subject": {"type": "user", "name": "alice"},
                    "role": "operator",
                    "domain": {"type": "global"},
                }
            ],
        }
    )
    reconciler = AdminReconciler(client, environ={"ALICE_PASSWORD": "from-env"})

    first = reconciler.apply(state)
    second_drift = reconciler.diff(state)

    assert first["status"] == "success"
    assert client.calls == [
        "role:create:operator",
        "user:create:alice",
        "team:create:ops",
        "membership:add:ops/alice",
        "assignment:grant:user:alice/operator",
    ]
    assert second_drift == []


def test_prune_removes_only_manual_records_and_reports_idp_skips() -> None:
    client = FakeAdminClient()
    client.users = [
        {"id": ALICE_ID, "username": "alice", "is_active": True},
        {"id": BOB_ID, "username": "bob", "is_active": True},
        {"id": CAROL_ID, "username": "carol", "is_active": True},
    ]
    client.teams = [
        {"id": TEAM_ID, "adom_name": "ops", "team_name": "Operators", "description": None, "is_active": True}
    ]
    client.roles.append(
        {
            "id": OPERATOR_ID,
            "name": "operator",
            "description": None,
            "permissions": ["team:manage"],
            "parent_role_id": None,
            "is_system": False,
        }
    )
    client.members[TEAM_ID] = [
        {"id": "member-alice", "team_id": TEAM_ID, "user_id": ALICE_ID, "source": "manual"},
        {"id": "member-bob", "team_id": TEAM_ID, "user_id": BOB_ID, "source": "sso"},
        {"id": "member-carol", "team_id": TEAM_ID, "user_id": CAROL_ID, "source": "manual"},
    ]
    client.assignments[("user", "alice")] = [
        {
            "id": "manual-assignment",
            "user_id": ALICE_ID,
            "role_id": OPERATOR_ID,
            "domain_type": "global",
            "domain_id": None,
            "grant_sources": [{"source_kind": "manual"}],
        },
        {
            "id": "idp-assignment",
            "user_id": ALICE_ID,
            "role_id": VIEWER_ID,
            "domain_type": "global",
            "domain_id": None,
            "grant_sources": [{"source_kind": "idp"}],
        },
    ]
    state = AdminState.model_validate(
        {
            "apiVersion": "langflow.ai/v1",
            "kind": "AdminState",
            "users": [{"username": "alice"}],
            "teams": [{"adom_name": "ops", "display_name": "Operators", "members": ["alice"]}],
        }
    )

    plan = AdminReconciler(client).apply(state, prune=True)

    assert plan["status"] == "success"
    assert {item["key"] for item in plan["applied"]} == {
        "ops/carol",
        "user:alice/operator@global",
    }
    assert {item["key"] for item in plan["skipped"]} == {
        "ops/bob",
        "user:alice/viewer@global",
    }
    assert all(item["reason"] == "externally_managed" for item in plan["skipped"])


def test_apply_resolves_entire_manifest_before_writing() -> None:
    client = FakeAdminClient()
    state = AdminState.model_validate(
        {
            "apiVersion": "langflow.ai/v1",
            "kind": "AdminState",
            "roles": [{"name": "operator", "permissions": ["team:manage"]}],
            "users": [
                {"username": "alice", "password_env": "UNSET_PASSWORD"}  # pragma: allowlist secret
            ],
        }
    )

    with pytest.raises(ManifestResolutionError, match="UNSET_PASSWORD"):
        AdminReconciler(client, environ={}).apply(state)

    assert client.calls == []


def test_ids_allow_user_and_team_renames_without_duplicate_relationships() -> None:
    client = FakeAdminClient()
    client.users = [{"id": ALICE_ID, "username": "alice-old", "is_active": True}]
    client.teams = [
        {"id": TEAM_ID, "adom_name": "ops-old", "team_name": "Operators", "description": None, "is_active": True}
    ]
    client.members[TEAM_ID] = [{"id": "member-alice", "team_id": TEAM_ID, "user_id": ALICE_ID, "source": "manual"}]
    client.assignments[("user", "alice-old")] = [
        {
            "id": "viewer-assignment",
            "user_id": ALICE_ID,
            "role_id": VIEWER_ID,
            "domain_type": "global",
            "domain_id": None,
            "grant_sources": [{"source_kind": "manual"}],
        }
    ]
    state = AdminState.model_validate(
        {
            "apiVersion": "langflow.ai/v1",
            "kind": "AdminState",
            "users": [{"id": ALICE_ID, "username": "alice-new"}],
            "teams": [
                {
                    "id": TEAM_ID,
                    "adom_name": "ops-new",
                    "display_name": "Operators",
                    "members": ["alice-new"],
                }
            ],
            "assignments": [
                {
                    "subject": {"type": "user", "name": "alice-new"},
                    "role": "viewer",
                    "domain": {"type": "global"},
                }
            ],
        }
    )
    reconciler = AdminReconciler(client)

    report = reconciler.apply(state)

    assert report["status"] == "success"
    assert [item["resource"] for item in report["applied"]] == ["user", "team"]
    assert reconciler.diff(state) == []


def test_role_id_rename_preserves_existing_assignment_without_duplicate_grant() -> None:
    client = FakeAdminClient()
    client.users = [{"id": ALICE_ID, "username": "alice", "is_active": True}]
    client.roles.append(
        {
            "id": OPERATOR_ID,
            "name": "operator",
            "description": None,
            "permissions": ["team:manage"],
            "parent_role_id": None,
            "is_system": False,
        }
    )
    client.assignments[("user", "alice")] = [
        {
            "id": "existing-assignment",
            "user_id": ALICE_ID,
            "role_id": OPERATOR_ID,
            "domain_type": "global",
            "domain_id": None,
            "grant_sources": [{"source_kind": "manual"}],
        }
    ]
    state = AdminState.model_validate(
        {
            "apiVersion": "langflow.ai/v1",
            "kind": "AdminState",
            "users": [{"username": "alice"}],
            "roles": [
                {
                    "id": OPERATOR_ID,
                    "name": "renamed-operator",
                    "permissions": ["team:manage"],
                }
            ],
            "assignments": [
                {
                    "subject": {"type": "user", "name": "alice"},
                    "role": "renamed-operator",
                    "domain": {"type": "global"},
                }
            ],
        }
    )

    report = AdminReconciler(client).apply(state)

    assert report["status"] == "success"
    assert client.calls == ["role:update:operator"]


def test_export_is_portable_and_excludes_idp_owned_relationships() -> None:
    client = FakeAdminClient()
    client.users = [
        {"id": ALICE_ID, "username": "alice", "is_active": True},
        {"id": BOB_ID, "username": "bob", "is_active": True},
    ]
    client.teams = [
        {"id": TEAM_ID, "adom_name": "ops", "team_name": "Operators", "description": None, "is_active": True}
    ]
    client.members[TEAM_ID] = [
        {"id": "manual-member", "team_id": TEAM_ID, "user_id": ALICE_ID, "source": "manual"},
        {"id": "idp-member", "team_id": TEAM_ID, "user_id": BOB_ID, "source": "sso"},
    ]
    client.assignments[("user", "alice")] = [
        {
            "id": "manual-assignment",
            "user_id": ALICE_ID,
            "role_id": VIEWER_ID,
            "domain_type": "global",
            "domain_id": None,
            "grant_sources": [{"source_kind": "manual"}],
        }
    ]
    client.assignments[("user", "bob")] = [
        {
            "id": "idp-assignment",
            "user_id": BOB_ID,
            "role_id": VIEWER_ID,
            "domain_type": "global",
            "domain_id": None,
            "grant_sources": [{"source_kind": "idp"}],
        }
    ]

    exported = AdminReconciler(client).export_state()

    assert all(user.id is None for user in exported.users)
    assert all(team.id is None for team in exported.teams)
    assert all(role.id is None for role in exported.roles)
    assert exported.teams[0].members == ["alice"]
    assert [(item.subject.name, item.role) for item in exported.assignments] == [("alice", "viewer")]
