"""Observable compilation contracts; these tests require no Casbin installation."""

from dataclasses import FrozenInstanceError, replace
from random import Random
from uuid import UUID

import pytest
from langflow.services.authorization.casbin.compiler import (
    AssignmentSnapshot,
    AssignmentSource,
    PolicySnapshot,
    RoleSnapshot,
    TeamSnapshot,
    canonical_domains,
    compile_policy,
)
from langflow.services.authorization.casbin.grammar import PolicyFormatError, Rule, normalize_request, validate_rule
from langflow.services.authorization.policy import TeamMemberState
from langflow.services.authorization.repository import ResourceRecord
from lfx.services.authorization.base import ShareRuleSnapshot

USER = UUID(int=1)
ADMIN = UUID(int=2)
TEAM = UUID(int=3)
PROJECT = UUID(int=4)
WORKSPACE = UUID(int=5)
OTHER_WORKSPACE = UUID(int=6)
FLOW = UUID(int=7)
ROLE = UUID(int=8)


def project(workspace_id: UUID | None = WORKSPACE) -> ResourceRecord:
    return ResourceRecord("project", PROJECT, ADMIN, PROJECT, workspace_id)


def test_empty_snapshot_has_no_synthetic_owner_or_platform_policy() -> None:
    snapshot = PolicySnapshot(active_user_ids=frozenset({ADMIN}), resources=(project(),))
    assert compile_policy(snapshot) == ()


@pytest.mark.parametrize(
    ("scope", "scope_id", "restriction", "expected_domain"),
    [
        ("global", None, None, "*"),
        ("global", None, WORKSPACE, f"workspace:{WORKSPACE}"),
        ("workspace", WORKSPACE, None, f"workspace:{WORKSPACE}"),
        ("workspace", WORKSPACE, WORKSPACE, f"workspace:{WORKSPACE}"),
        ("workspace", WORKSPACE, OTHER_WORKSPACE, None),
        ("project", PROJECT, None, f"project:{PROJECT}"),
        ("project", PROJECT, WORKSPACE, f"project:{PROJECT}"),
        ("project", PROJECT, OTHER_WORKSPACE, None),
        ("global", WORKSPACE, None, None),
        ("workspace", None, None, None),
        ("project", None, None, None),
        ("organization", WORKSPACE, None, None),
    ],
)
def test_role_and_assignment_scopes_intersect_without_widening(
    scope: str, scope_id: UUID | None, restriction: UUID | None, expected_domain: str | None
) -> None:
    """Given a restricted role, its compiled authority stays in the intersection."""
    snapshot = PolicySnapshot(
        active_user_ids=frozenset({USER}),
        roles=(RoleSnapshot(ROLE, ("flow:write",), workspace_id=restriction),),
        assignments=(AssignmentSnapshot(UUID(int=9), USER, ROLE, scope, scope_id),),
        resources=(project(),),
    )
    rules = compile_policy(snapshot)
    expected = (
        () if expected_domain is None else (("p", f"user:{USER}", expected_domain, "flow/*", "write", None, None),)
    )
    assert rules == expected


def test_suspended_team_keeps_management_but_loses_resource_sharing() -> None:
    """Given suspension, management remains exact-team while resource links disappear."""
    team = TeamSnapshot(
        TEAM,
        is_active=False,
        members=(TeamMemberState(ADMIN, "admin", is_active=True), TeamMemberState(USER, "user", is_active=True)),
    )
    snapshot = PolicySnapshot(
        active_user_ids=frozenset({ADMIN, USER}),
        teams=(team,),
        shares=(ShareRuleSnapshot(UUID(int=10), "project", PROJECT, "team", TEAM, "write"),),
        resources=(project(),),
    )
    rules = compile_policy(snapshot)
    assert ("g", f"user:{ADMIN}", f"team-role/{TEAM}/admin", None, None, None, None) in rules
    assert ("g", f"user:{USER}", f"team-role/{TEAM}/user", None, None, None, None) in rules
    assert not any(rule.v0 == f"team/{TEAM}" or rule.v1 == f"team/{TEAM}" for rule in rules)
    active_rules = compile_policy(replace(snapshot, teams=(replace(team, is_active=True),)))
    assert ("g", f"user:{USER}", f"team/{TEAM}", None, None, None, None) in active_rules


def test_project_edit_share_has_child_creation_without_child_deletion_or_fanout() -> None:
    """An editable project compiles one child pattern, including future creations."""
    snapshot = PolicySnapshot(
        active_user_ids=frozenset({USER}),
        resources=(project(), ResourceRecord("flow", FLOW, ADMIN, PROJECT, WORKSPACE)),
        shares=(ShareRuleSnapshot(UUID(int=10), "project", PROJECT, "user", USER, "admin"),),
    )
    rules = compile_policy(snapshot)
    assert {rule.v3 for rule in rules if rule.v2 == "flow/*"} == {"read", "write", "execute", "create"}
    assert not any(rule.v2 == f"flow/{FLOW}" for rule in rules)
    assert {rule.v3 for rule in rules if rule.v2 == f"project/{PROJECT}"} == {"read", "write", "delete"}


def test_disabled_user_has_no_derived_role_share_or_group_authority() -> None:
    snapshot = PolicySnapshot(
        active_user_ids=frozenset({ADMIN}),
        teams=(
            TeamSnapshot(
                TEAM,
                is_active=True,
                members=(
                    TeamMemberState(ADMIN, "admin", is_active=True),
                    TeamMemberState(USER, "user", is_active=False),
                ),
            ),
        ),
        roles=(RoleSnapshot(ROLE, ("flow:*",)),),
        assignments=(AssignmentSnapshot(UUID(int=9), USER, ROLE),),
        shares=(ShareRuleSnapshot(UUID(int=10), "project", PROJECT, "user", USER, "write"),),
        resources=(project(),),
    )
    assert not any(rule.v0 == f"user:{USER}" for rule in compile_policy(snapshot))


def test_output_is_deterministic_and_duplicate_sources_survive_independent_removal() -> None:
    shares = tuple(ShareRuleSnapshot(UUID(int=20 + i), "flow", FLOW, "user", USER, "execute") for i in range(6))
    snapshot = PolicySnapshot(
        active_user_ids=frozenset({USER}),
        shares=shares,
        resources=(ResourceRecord("flow", FLOW, ADMIN),),
        roles=(RoleSnapshot(ROLE, ("flow:read", "flow:read")), RoleSnapshot(UUID(int=90), ("file:read",))),
        assignments=(AssignmentSnapshot(UUID(int=9), USER, ROLE),),
    )
    expected = compile_policy(snapshot)
    random = Random(17)  # noqa: S311 - reproducible input-order permutations
    for _ in range(8):
        shuffled = replace(
            snapshot,
            shares=tuple(random.sample(shares, len(shares))),
            roles=tuple(random.sample(snapshot.roles, len(snapshot.roles))),
        )
        assert compile_policy(shuffled) == expected == tuple(sorted(set(expected)))
    assert compile_policy(replace(snapshot, shares=shares[:1])) == expected
    assert not any(rule.v2 == f"flow/{FLOW}" for rule in compile_policy(replace(snapshot, shares=())))


@pytest.mark.parametrize("chain_length", [1, 31, 32, 33])
def test_parent_depth_boundary_matches_existing_canonical_semantics(chain_length: int) -> None:
    roles = tuple(
        RoleSnapshot(UUID(int=100 + i), ("flow:read",), UUID(int=101 + i) if i < chain_length - 1 else None)
        for i in range(chain_length)
    )
    snapshot = PolicySnapshot(
        active_user_ids=frozenset({USER}),
        roles=roles,
        assignments=(AssignmentSnapshot(UUID(int=9), USER, roles[0].id),),
    )
    assert bool(compile_policy(snapshot)) is (chain_length < 32)


@pytest.mark.parametrize("parent_id", [ROLE, UUID(int=99)])
def test_cyclic_or_missing_parent_does_not_partially_grant_child_permissions(parent_id: UUID) -> None:
    snapshot = PolicySnapshot(
        active_user_ids=frozenset({USER}),
        roles=(RoleSnapshot(ROLE, ("flow:write",), parent_id),),
        assignments=(AssignmentSnapshot(UUID(int=9), USER, ROLE),),
    )
    assert compile_policy(snapshot) == ()


def test_parent_permissions_flatten_without_inventing_parent_workspace_restrictions() -> None:
    parent = RoleSnapshot(UUID(int=99), ("flow:read", "share:*"), workspace_id=OTHER_WORKSPACE)
    child = RoleSnapshot(ROLE, ("flow:write", "flow:future", "unknown:*"), parent.id, WORKSPACE)
    snapshot = PolicySnapshot(
        active_user_ids=frozenset({USER}),
        roles=(parent, child),
        assignments=(AssignmentSnapshot(UUID(int=9), USER, ROLE),),
    )
    rules = compile_policy(snapshot)
    assert {rule.v1 for rule in rules} == {f"workspace:{WORKSPACE}"}
    assert {rule.v3 for rule in rules if rule.v2 == "flow/*"} == {"read", "write"}
    assert {rule.v3 for rule in rules if rule.v2 == "share/*"} == {"read", "create", "update", "delete"}
    assert all(rule.v3 != "*" for rule in rules)


@pytest.mark.parametrize(
    "sources",
    [
        (),
        (AssignmentSource("manual"),),
        (AssignmentSource("idp", "test-provider", "test-group"),),
        (AssignmentSource("manual"), AssignmentSource("idp", "test-provider", "test-group")),
    ],
)
def test_existing_legacy_manual_or_idp_assignment_survives_while_canonical_row_exists(
    sources: tuple[AssignmentSource, ...],
) -> None:
    snapshot = PolicySnapshot(
        active_user_ids=frozenset({USER}),
        roles=(RoleSnapshot(ROLE, ("flow:read",)),),
        assignments=(AssignmentSnapshot(UUID(int=9), USER, ROLE, sources=sources),),
    )
    assert compile_policy(snapshot) == (("p", f"user:{USER}", "*", "flow/*", "read", None, None),)
    assert compile_policy(replace(snapshot, assignments=())) == ()


@pytest.mark.parametrize(
    "source", [AssignmentSource("unknown"), AssignmentSource("manual", "invalid"), AssignmentSource("idp")]
)
def test_malformed_provenance_does_not_create_authority(source: AssignmentSource) -> None:
    snapshot = PolicySnapshot(
        active_user_ids=frozenset({USER}),
        roles=(RoleSnapshot(ROLE, ("flow:read",)),),
        assignments=(AssignmentSnapshot(UUID(int=9), USER, ROLE, sources=(source,)),),
    )
    assert compile_policy(snapshot) == ()


def test_project_move_recomputes_role_intersection_without_moving_direct_share() -> None:
    snapshot = PolicySnapshot(
        active_user_ids=frozenset({USER}),
        roles=(RoleSnapshot(ROLE, ("flow:write",), workspace_id=WORKSPACE),),
        assignments=(AssignmentSnapshot(UUID(int=9), USER, ROLE, "project", PROJECT),),
        resources=(project(), ResourceRecord("flow", FLOW, ADMIN, PROJECT, WORKSPACE)),
        shares=(ShareRuleSnapshot(UUID(int=10), "flow", FLOW, "user", USER, "read"),),
    )
    before = compile_policy(snapshot)
    moved = replace(
        snapshot, resources=(project(OTHER_WORKSPACE), ResourceRecord("flow", FLOW, ADMIN, PROJECT, OTHER_WORKSPACE))
    )
    after = compile_policy(moved)
    assert any(rule.v2 == "flow/*" and rule.v3 == "write" for rule in before)
    assert after == (("p", f"user:{USER}", "*", f"flow/{FLOW}", "read", None, None),)
    assert compile_policy(replace(moved, resources=snapshot.resources)) == before


def test_domains_keep_unscoped_distinct_from_unresolved_or_inconsistent_parent() -> None:
    flow = ResourceRecord("flow", FLOW, ADMIN, PROJECT, WORKSPACE)
    assert canonical_domains(flow, {PROJECT: project()}) == (f"project:{PROJECT}", f"workspace:{WORKSPACE}", "*")
    assert canonical_domains(ResourceRecord("variable", FLOW, ADMIN), {}) == ("*",)
    with pytest.raises(ValueError, match="project context"):
        canonical_domains(flow, {})
    with pytest.raises(ValueError, match="project context"):
        canonical_domains(flow, {PROJECT: project(OTHER_WORKSPACE)})
    with pytest.raises(ValueError, match="Personal resources"):
        canonical_domains(ResourceRecord("file", FLOW, ADMIN, PROJECT, WORKSPACE), {PROJECT: project()})


@pytest.mark.parametrize("scope", ["public", "private", "unknown"])
def test_public_private_and_unknown_scopes_do_not_become_authenticated_grants(scope: str) -> None:
    snapshot = PolicySnapshot(
        active_user_ids=frozenset({USER}),
        resources=(project(),),
        shares=(ShareRuleSnapshot(UUID(int=10), "project", PROJECT, scope, USER, "admin"),),
    )
    assert compile_policy(snapshot) == ()


def test_frozen_snapshot_cannot_mutate_during_compilation() -> None:
    snapshot = PolicySnapshot(active_user_ids=frozenset({USER}))
    with pytest.raises(FrozenInstanceError):
        snapshot.roles = ()  # type: ignore[misc]


@pytest.mark.parametrize(
    "rule",
    [
        Rule("p", f"user:{USER}", "project:*", "flow/*", "read"),
        Rule("p", str(USER), "*", "flow/*", "read"),
        Rule("p", f"user:{USER}", "*", f"flow:{FLOW}", "read"),
        Rule("p", f"user:{USER}", "*", "flow/:id", "read"),
        Rule("p", f"user:{USER}", "*", "flow/.*", "read"),
        Rule("p", f"user:{USER}", "*", "flow/**", "read"),
        Rule("p", f"user:{USER}", "*", "flow/*/child", "read"),
        Rule("p", f"user:{USER}", "*", "flow/*", "*"),
        Rule("p", f"user:{USER}", "*", "flow/*", "future"),
        Rule("p", f"user:{USER}", "*", "flow/*", "read", "deny"),
        Rule("p", f"user:{USER}", "*", "flow/*", "read", None, "1"),
        Rule("g2", f"user:{USER}", f"team/{TEAM}"),
        Rule("g", f"team/{TEAM}", f"team-role/{TEAM}/admin"),
        Rule("g", f"user:{USER}", f"user:{ADMIN}"),
        Rule("g", f"user:{USER}", f"team/{TEAM}", "*"),
        Rule("g", f"user:{USER}", f"team-role/{TEAM}/owner"),
        Rule("p", f"team-role/{TEAM}/admin", "*", f"team/{PROJECT}", "update"),
        Rule("p", f"team-role/{TEAM}/admin", "*", f"flow/{FLOW}", "write"),
        Rule("p", f"team/{TEAM}", "*", f"team/{TEAM}", "update"),
        Rule("p", f"team-role/{TEAM}/admin", "*", f"team/{TEAM}", "set_active"),
        Rule("p", f"team-role/{TEAM}/admin", "*", f"team/{TEAM}", "change_role:*"),
    ],
)
def test_malformed_policy_never_reaches_the_matcher(rule: Rule) -> None:
    with pytest.raises(PolicyFormatError):
        validate_rule(rule)


@pytest.mark.parametrize("obj", ["flow:*", f"flow/{FLOW}", "flow:bad", "flow::id", "flow:.*", "unknown:*", "team:*"])
def test_client_object_cannot_substitute_a_collection_or_pattern(obj: str) -> None:
    with pytest.raises(PolicyFormatError):
        normalize_request(USER, "*", obj, "read")


def test_existing_create_shape_normalizes_once_only_when_server_classified() -> None:
    assert normalize_request(USER, f"project:{PROJECT}", "flow:*", "create", collection_operation=True) == (
        f"user:{USER}",
        f"project:{PROJECT}",
        "flow/*",
        "create",
    )
    with pytest.raises(PolicyFormatError):
        normalize_request(USER, f"project:{PROJECT}", f"project:{PROJECT}", "flow:create")


def test_invalid_active_team_cannot_share_but_existing_members_can_inspect_it() -> None:
    snapshot = PolicySnapshot(
        active_user_ids=frozenset({USER}),
        teams=(TeamSnapshot(TEAM, is_active=True, members=(TeamMemberState(USER, "user", is_active=True),)),),
        resources=(project(),),
        shares=(ShareRuleSnapshot(UUID(int=10), "project", PROJECT, "team", TEAM, "write"),),
    )
    rules = compile_policy(snapshot)
    assert rules == (
        Rule("g", f"user:{USER}", f"team-role/{TEAM}/user"),
        Rule("p", f"team-role/{TEAM}/user", "*", f"team/{TEAM}", "read"),
    )


@pytest.mark.parametrize("member_count", [10, 1000])
def test_rule_growth_has_no_member_by_child_resource_fanout(member_count: int) -> None:
    members = tuple(
        TeamMemberState(UUID(int=100 + i), "admin" if i == 0 else "user", is_active=True) for i in range(member_count)
    )
    snapshot = PolicySnapshot(
        active_user_ids=frozenset(member.user_id for member in members),
        teams=(TeamSnapshot(TEAM, is_active=True, members=members),),
        resources=(project(),),
        shares=(ShareRuleSnapshot(UUID(int=10), "project", PROJECT, "team", TEAM, "write"),),
    )
    expected = compile_policy(snapshot)
    many_children = tuple(ResourceRecord("flow", UUID(int=2000 + i), ADMIN, PROJECT, WORKSPACE) for i in range(1000))
    assert compile_policy(replace(snapshot, resources=(*snapshot.resources, *many_children))) == expected
    assert len(expected) == 2 * member_count + 24
    assert len([rule for rule in expected if rule.v0 == f"team/{TEAM}"]) == 6


def test_normalization_rejects_noncanonical_uuid_and_missing_required_policy_slots() -> None:
    for identifier in (str(FLOW).replace("-", ""), "{00000000-0000-0000-0000-000000000007}", "bad"):
        with pytest.raises(PolicyFormatError):
            normalize_request(USER, "*", f"flow:{identifier}", "read")
    with pytest.raises(PolicyFormatError):
        validate_rule(Rule("p", None, "*", "flow/*", "read"))  # type: ignore[arg-type]
    with pytest.raises(PolicyFormatError):
        validate_rule(Rule("p", f"user:{USER}", "*", None, "read"))


@pytest.mark.parametrize("role_id", ["not-a-uuid", "role:*", "role/owner"])
def test_malformed_canonical_role_identity_cannot_emit_valid_looking_policy(role_id: str) -> None:
    snapshot = PolicySnapshot(
        active_user_ids=frozenset({USER}),
        roles=(RoleSnapshot(role_id, ("flow:write",)),),  # type: ignore[arg-type]
        assignments=(AssignmentSnapshot(UUID(int=9), USER, role_id),),  # type: ignore[arg-type]
    )
    with pytest.raises(PolicyFormatError):
        compile_policy(snapshot)


@pytest.mark.parametrize("source", ["assignment", "share"])
def test_missing_canonical_grant_identity_cannot_emit_valid_looking_policy(source: str) -> None:
    snapshot = PolicySnapshot(
        active_user_ids=frozenset({USER}),
        resources=(project(),),
        roles=(RoleSnapshot(ROLE, ("flow:read",)),),
    )
    if source == "assignment":
        snapshot = replace(snapshot, assignments=(AssignmentSnapshot(None, USER, ROLE),))  # type: ignore[arg-type]
    else:
        snapshot = replace(
            snapshot,
            shares=(ShareRuleSnapshot(None, "project", PROJECT, "user", USER, "read"),),  # type: ignore[arg-type]
        )
    with pytest.raises(PolicyFormatError):
        compile_policy(snapshot)
