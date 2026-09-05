"""The shipped capability manifest must match the frozen Microsoft matrix.

``design/dedicated-integrations/matrices/microsoft.json`` is the contract the
gate froze. Nothing else prevents ``capabilities.v1.json`` from drifting from
it, so this test pins the include set, the class names, the display names and
the scopes -- with the one deliberate difference the resolver forces:
``offline_access`` is a registration-level scope, never a per-action one.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from lfx.integrations.capabilities import IntegrationCapabilityManifest
from lfx_microsoft import components as component_package
from lfx_microsoft.manifest import MANIFEST_PATH, load_manifest

MATRIX_PATH = Path(__file__).resolve().parents[4] / "design" / "dedicated-integrations" / "matrices" / "microsoft.json"


def _matrix_actions() -> dict[str, dict]:
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    return {action["action_id"]: action for action in matrix["actions"] if action["decision"] == "include"}


requires_matrix = pytest.mark.skipif(
    not MATRIX_PATH.exists(),
    reason="design matrix is only present in the langflow monorepo checkout",
)


def test_manifest_validates_against_the_versioned_schema() -> None:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest = IntegrationCapabilityManifest.model_validate(payload)
    assert manifest.schema_version == 1
    assert manifest.provider_id == "microsoft"
    assert [profile.id for profile in manifest.auth_profiles] == ["user"]


def test_every_capability_declares_a_namespaced_policy_key() -> None:
    for capability in load_manifest().capabilities:
        assert capability.policy_keys, capability.id
        for key in capability.policy_keys:
            assert key.startswith("integrations.microsoft."), key


def test_component_refs_resolve_to_exported_classes() -> None:
    exported = set(component_package.microsoft.__all__)
    refs = {capability.component_ref for capability in load_manifest().capabilities}
    assert refs <= exported
    assert len(refs) == len(load_manifest().capabilities)


def test_offline_access_is_never_a_per_action_scope() -> None:
    """Entra never echoes ``offline_access`` in the token response.

    ``DatabaseConnectionResolverService`` computes ``required - granted`` as a
    raw set difference, so a literal transcription of the matrix would fail
    every Microsoft resolution with ``scope-missing``. The scope stays in the
    auth profile's default scopes and the registration ceiling instead.
    """
    manifest = load_manifest()
    profile = manifest.auth_profiles[0]
    assert "offline_access" in profile.default_scopes
    for capability in manifest.capabilities:
        assert "offline_access" not in capability.required_scopes
        assert all(entry.scope != "offline_access" for entry in capability.conditional_scopes)


@requires_matrix
def test_manifest_covers_exactly_the_matrix_include_set() -> None:
    actions = _matrix_actions()
    manifest = load_manifest()
    assert {capability.id for capability in manifest.capabilities} == set(actions)
    assert len(manifest.capabilities) == 8


@requires_matrix
def test_display_names_and_classes_match_the_matrix_verbatim() -> None:
    actions = _matrix_actions()
    for capability in load_manifest().capabilities:
        action = actions[capability.id]
        assert capability.display_name == action["display_name"]
        assert capability.component_ref == action["component_class"]
        assert capability.substrate == "rest"
        assert capability.identity == action["identity"]
        assert set(capability.deployment_contexts) == set(action["deployment_contexts"])


@requires_matrix
def test_scopes_match_the_matrix_minus_offline_access() -> None:
    actions = _matrix_actions()
    for capability in load_manifest().capabilities:
        scopes = actions[capability.id]["scopes"]
        expected_required = {
            entry["scope"] for entry in scopes if entry["role"] == "required" and entry["scope"] != "offline_access"
        }
        assert set(capability.required_scopes) == expected_required, capability.id

        expected_conditional = {
            (entry["scope"], entry["condition"]["kind"], entry["condition"]["input"])
            for entry in scopes
            if entry.get("condition")
        }
        actual_conditional = {
            (entry.scope, entry.condition.kind, entry.condition.input) for entry in capability.conditional_scopes
        }
        assert actual_conditional == expected_conditional, capability.id


@requires_matrix
def test_auth_profile_mirrors_the_matrix_ownership_matrix() -> None:
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    profile = load_manifest().auth_profiles[0]
    assert dict(profile.owner_by_context) == matrix["oauth_app_owner_by_context"]
    assert dict(profile.client_type_by_context) == matrix["oauth_client_type_by_context"]
    assert profile.client_type_by_context["headless"] == "external"
