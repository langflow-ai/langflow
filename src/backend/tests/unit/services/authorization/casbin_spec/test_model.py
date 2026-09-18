"""Actual packaged Casbin model acceptance, including negative model mutations."""

from __future__ import annotations

from dataclasses import replace
from importlib.resources import files
from typing import TYPE_CHECKING
from uuid import UUID

import casbin
import pytest
from langflow.services.authorization.casbin.compiler import (
    AssignmentSnapshot,
    PolicySnapshot,
    RoleSnapshot,
    TeamSnapshot,
    compile_policy,
)
from langflow.services.authorization.casbin.grammar import Rule, normalize_request, validate_rule
from langflow.services.authorization.policy import TeamMemberState
from langflow.services.authorization.repository import ResourceRecord
from lfx.services.authorization.base import ShareRuleSnapshot

if TYPE_CHECKING:
    from collections.abc import Sequence

USER = UUID(int=1)
ADMIN = UUID(int=2)
TEAM = UUID(int=3)
PROJECT = UUID(int=4)
WORKSPACE = UUID(int=5)
OTHER_PROJECT = UUID(int=6)
FLOW = UUID(int=7)
ROLE = UUID(int=8)
OTHER_TEAM = UUID(int=9)


def model_enforcer(rules: Sequence[Rule], *, model_text: str | None = None) -> casbin.Enforcer:
    """Load complete validated rules into the actual Python engine, without an adapter."""
    for rule in rules:
        validate_rule(rule)
    model = casbin.Model()
    model.load_model_from_text(
        model_text or files("langflow.services.authorization.casbin").joinpath("model.conf").read_text(encoding="utf-8")
    )
    enforcer = casbin.Enforcer(model)
    enforcer.enable_auto_save(auto_save=False)
    for rule in rules:
        if rule.ptype == "g":
            enforcer.add_grouping_policy(rule.v0, rule.v1)
        else:
            enforcer.add_policy(rule.v0, rule.v1, rule.v2, rule.v3)
    return enforcer


def team_snapshot(role: str, *, active: bool = True) -> PolicySnapshot:
    return PolicySnapshot(
        active_user_ids=frozenset({USER, ADMIN}),
        teams=(
            TeamSnapshot(
                TEAM,
                is_active=active,
                members=(
                    TeamMemberState(ADMIN, "admin", is_active=True),
                    TeamMemberState(USER, role, is_active=True),
                ),
            ),
        ),
        resources=(ResourceRecord("project", PROJECT, ADMIN, PROJECT, WORKSPACE), ResourceRecord("flow", FLOW, ADMIN)),
    )


@pytest.mark.parametrize("role", ["admin", "maintainer", "user"])
@pytest.mark.parametrize(
    ("action", "expected_roles"),
    [
        ("read", {"admin", "maintainer", "user"}),
        ("update", {"admin"}),
        ("add_member:user", {"admin", "maintainer"}),
        ("add_member:admin", {"admin"}),
        ("add_member:maintainer", {"admin"}),
        ("remove_member:user", {"admin", "maintainer"}),
        ("remove_member:admin", {"admin"}),
        ("remove_member:maintainer", {"admin"}),
        *[
            (f"change_role:{old}:{new}", {"admin"})
            for old in ("admin", "maintainer", "user")
            for new in ("admin", "maintainer", "user")
        ],
        ("create", set()),
        ("delete", set()),
        ("list_all", set()),
        ("set_active", set()),
        ("change_directory_binding", set()),
        ("change_role:*", set()),
        ("*", set()),
        ("future", set()),
    ],
)
def test_exact_team_operation_matrix_uses_finite_actions(role: str, action: str, expected_roles: set[str]) -> None:
    """Given an exact membership, only that team's permitted operation can succeed."""
    engine = model_enforcer(compile_policy(team_snapshot(role)))
    assert engine.enforce(f"user:{USER}", "*", f"team/{TEAM}", action) is (role in expected_roles)
    assert not engine.enforce(f"user:{USER}", "*", f"team/{OTHER_TEAM}", action)
    assert not engine.enforce(f"user:{USER}", f"workspace:{WORKSPACE}", f"team/{TEAM}", action)


@pytest.mark.parametrize("role", ["admin", "maintainer", "user"])
def test_all_team_roles_share_equally_without_resource_management_escalation(role: str) -> None:
    snapshot = replace(
        team_snapshot(role), shares=(ShareRuleSnapshot(UUID(int=10), "flow", FLOW, "team", TEAM, "write"),)
    )
    engine = model_enforcer(compile_policy(snapshot))
    for action in ("read", "write", "execute"):
        assert engine.enforce(f"user:{USER}", "*", f"flow/{FLOW}", action)
    for action in ("delete", "create", "deploy", "share", "publish"):
        assert not engine.enforce(f"user:{USER}", "*", f"flow/{FLOW}", action)
    assert not engine.enforce(f"user:{USER}", "*", f"project/{PROJECT}", "read")
    assert not engine.enforce(f"user:{USER}", "*", f"flow/{UUID(int=11)}", "read")
    assert not engine.enforce(f"user:{USER}", "*", f"share/{FLOW}", "create")
    assert not model_enforcer(compile_policy(team_snapshot(role))).enforce(f"user:{USER}", "*", f"flow/{FLOW}", "read")


def test_suspension_and_disabled_users_remove_only_intended_authority() -> None:
    snapshot = replace(
        team_snapshot("admin"), shares=(ShareRuleSnapshot(UUID(int=10), "flow", FLOW, "team", TEAM, "write"),)
    )
    suspended = replace(snapshot, teams=(replace(snapshot.teams[0], is_active=False),))
    engine = model_enforcer(compile_policy(suspended))
    assert engine.enforce(f"user:{USER}", "*", f"team/{TEAM}", "update")
    assert not engine.enforce(f"user:{USER}", "*", f"team/{TEAM}", "set_active")
    assert not engine.enforce(f"user:{USER}", "*", f"flow/{FLOW}", "read")
    disabled = replace(
        snapshot,
        active_user_ids=frozenset({ADMIN}),
        teams=(
            replace(
                snapshot.teams[0],
                members=(
                    TeamMemberState(ADMIN, "admin", is_active=True),
                    TeamMemberState(USER, "admin", is_active=False),
                ),
            ),
        ),
    )
    engine = model_enforcer(compile_policy(disabled))
    assert not engine.enforce(f"user:{USER}", "*", f"team/{TEAM}", "read")
    assert not engine.enforce(f"user:{USER}", "*", f"flow/{FLOW}", "read")
    assert model_enforcer(compile_policy(snapshot)).enforce(f"user:{USER}", "*", f"flow/{FLOW}", "write")


@pytest.mark.parametrize("level", ["read", "execute", "write", "admin"])
def test_inherited_create_is_a_flow_collection_action_without_child_delete(level: str) -> None:
    snapshot = PolicySnapshot(
        active_user_ids=frozenset({USER}),
        resources=(ResourceRecord("project", PROJECT, ADMIN, PROJECT, WORKSPACE),),
        shares=(ShareRuleSnapshot(UUID(int=10), "project", PROJECT, "user", USER, level),),
    )
    engine = model_enforcer(compile_policy(snapshot))
    request = normalize_request(USER, f"project:{PROJECT}", "flow:*", "create", collection_operation=True)
    assert engine.enforce(*request) is (level in {"write", "admin"})
    assert engine.enforce(f"user:{USER}", f"project:{PROJECT}", f"flow/{FLOW}", "read")
    assert not engine.enforce(f"user:{USER}", f"project:{PROJECT}", f"flow/{FLOW}", "delete")
    assert not engine.enforce(f"user:{USER}", f"project:{OTHER_PROJECT}", f"flow/{FLOW}", "read")
    assert not engine.enforce(f"user:{USER}", "*", f"project/{OTHER_PROJECT}", "read")
    assert not engine.enforce(f"user:{USER}", f"project:{PROJECT}", f"project/{PROJECT}", "flow:create")


def test_concrete_role_write_does_not_inherit_share_expansion_or_creation() -> None:
    snapshot = PolicySnapshot(
        active_user_ids=frozenset({USER}),
        roles=(RoleSnapshot(ROLE, ("flow:write",)),),
        assignments=(AssignmentSnapshot(UUID(int=10), USER, ROLE),),
    )
    engine = model_enforcer(compile_policy(snapshot))
    assert engine.enforce(f"user:{USER}", "*", f"flow/{FLOW}", "write")
    for action in ("read", "execute", "create", "delete", "publish"):
        assert not engine.enforce(f"user:{USER}", "*", f"flow/{FLOW}", action)


def test_domain_union_uses_explicit_scopes_and_never_literal_domain_patterns() -> None:
    rules = (
        Rule("p", f"user:{USER}", f"project:{PROJECT}", "flow/*", "write"),
        Rule("p", f"user:{USER}", f"workspace:{WORKSPACE}", "flow/*", "read"),
        Rule("p", f"user:{USER}", "*", f"flow/{FLOW}", "execute"),
    )
    engine = model_enforcer(rules)
    for action in ("read", "write", "execute"):
        assert any(
            engine.enforce(f"user:{USER}", domain, f"flow/{FLOW}", action)
            for domain in (f"project:{PROJECT}", f"workspace:{WORKSPACE}", "*")
        )
    assert not engine.enforce(f"user:{USER}", f"project:{OTHER_PROJECT}", f"flow/{FLOW}", "write")
    assert not engine.enforce(f"user:{USER}", f"workspace:{OTHER_PROJECT}", f"flow/{FLOW}", "read")
    assert not engine.enforce(str(USER), "*", f"flow/{FLOW}", "execute")


def test_role_share_administration_is_distinct_from_resource_editing() -> None:
    snapshot = PolicySnapshot(
        active_user_ids=frozenset({USER}),
        roles=(RoleSnapshot(ROLE, ("share:create",), workspace_id=WORKSPACE),),
        assignments=(AssignmentSnapshot(UUID(int=10), USER, ROLE),),
    )
    engine = model_enforcer(compile_policy(snapshot))
    assert engine.enforce(f"user:{USER}", f"workspace:{WORKSPACE}", f"share/{FLOW}", "create")
    assert not engine.enforce(f"user:{USER}", "*", f"share/{FLOW}", "create")
    assert not engine.enforce(f"user:{USER}", f"workspace:{WORKSPACE}", f"flow/{FLOW}", "write")


def test_direct_share_survives_membership_removal_without_preserving_team_write() -> None:
    snapshot = replace(
        team_snapshot("user"),
        shares=(
            ShareRuleSnapshot(UUID(int=10), "flow", FLOW, "team", TEAM, "write"),
            ShareRuleSnapshot(UUID(int=11), "flow", FLOW, "user", USER, "execute"),
        ),
    )
    before = model_enforcer(compile_policy(snapshot))
    assert before.enforce(f"user:{USER}", "*", f"flow/{FLOW}", "write")
    removed = replace(snapshot, teams=(replace(snapshot.teams[0], members=(snapshot.teams[0].members[0],)),))
    after = model_enforcer(compile_policy(removed))
    assert after.enforce(f"user:{USER}", "*", f"flow/{FLOW}", "execute")
    assert not after.enforce(f"user:{USER}", "*", f"flow/{FLOW}", "write")
    assert not after.enforce(f"user:{USER}", "*", f"team/{TEAM}", "read")


def test_one_grouping_relation_keeps_both_principal_kinds_without_identity_collision() -> None:
    snapshot = replace(
        team_snapshot("user"), shares=(ShareRuleSnapshot(UUID(int=10), "flow", FLOW, "team", TEAM, "read"),)
    )
    rules = compile_policy(snapshot)
    engine = model_enforcer(rules)
    assert engine.enforce(f"user:{USER}", "*", f"flow/{FLOW}", "read")
    assert engine.enforce(f"user:{USER}", "*", f"team/{TEAM}", "read")
    assert not engine.enforce(f"user:{TEAM}", "*", f"flow/{FLOW}", "read")
    assert not engine.enforce(f"user:{USER}", "*", f"team/{TEAM}", "update")


@pytest.mark.parametrize("mutation", ["domain", "action", "grouping"])
def test_negative_contract_detects_matcher_mutation(mutation: str) -> None:
    """Each weakened matcher must violate an independently specified decision."""
    text = files("langflow.services.authorization.casbin").joinpath("model.conf").read_text(encoding="utf-8")
    rules = (
        Rule("g", f"user:{USER}", f"team/{TEAM}"),
        Rule("p", f"team/{TEAM}", f"project:{PROJECT}", "flow/*", "read"),
    )
    request = (f"user:{USER}", f"project:{PROJECT}", f"flow/{FLOW}", "read")
    expected = True
    if mutation == "domain":
        changed = text.replace("r.dom == p.dom", "r.dom == r.dom")
        request = (request[0], f"project:{OTHER_PROJECT}", request[2], request[3])
        expected = False
    elif mutation == "action":
        changed = text.replace("r.act == p.act", "r.act == r.act")
        request = (*request[:3], "delete")
        expected = False
    else:
        changed = text.replace(" || g(r.sub, p.sub)", "")
    assert model_enforcer(rules).enforce(*request) is expected
    assert model_enforcer(rules, model_text=changed).enforce(*request) is not expected
