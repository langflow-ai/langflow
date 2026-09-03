from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import get_args

import pytest
from lfx.cli.validation import is_valid_env_var_name
from lfx.extension.manifest import ExtensionManifest
from lfx.inputs.input_mixin import SENSITIVE_FIELD_TYPES, FieldTypes
from lfx.inputs.inputs import ConnectionRefInput, instantiate_input
from lfx.integrations import (
    ConditionalScopeRequirement,
    ConnectionRef,
    IntegrationCapability,
    IntegrationProvider,
    OAuthProfile,
    ResolvedCredential,
    ScopeCondition,
    ScopeSet,
)
from lfx.integrations.capabilities import CapabilityMaturity, DeploymentContext, ExecutionSubstrate, OAuthKind
from lfx.io.schema import create_input_schema, create_input_schema_from_dict
from lfx.schema.dotdict import dotdict
from pydantic import SecretStr, ValidationError


@pytest.mark.parametrize("handle", ["google", "google/", "/work", "Google/work", "google/Work", "google/work-a"])
def test_connection_ref_rejects_malformed_handles(handle: str) -> None:
    with pytest.raises((ValueError, ValidationError)):
        ConnectionRef.parse(handle)


def test_connection_ref_env_key_is_valid_and_collision_free() -> None:
    refs = [ConnectionRef.parse(handle) for handle in ("a.b/work", "a-b/work", "a_b/work")]
    keys = [ref.env_key() for ref in refs]

    assert keys == [
        "LF_CONNECTION__A_2EB__WORK",
        "LF_CONNECTION__A_2DB__WORK",
        "LF_CONNECTION__A_5FB__WORK",
    ]
    assert len(set(keys)) == len(keys)
    assert all(is_valid_env_var_name(key) for key in keys)


def test_resolved_credential_is_redacted_and_not_picklable() -> None:
    credential = ResolvedCredential(access_token=SecretStr("do-not-leak"), provider="google", name="work")

    assert "do-not-leak" not in repr(credential)
    with pytest.raises(TypeError, match="cannot be serialized"):
        pickle.dumps(credential)


def test_connection_ref_input_round_trip_and_tool_exclusion() -> None:
    input_model = ConnectionRefInput(name="connection", provider="google", value="google/work")

    assert input_model.field_type == FieldTypes.CONNECTION_REF
    assert FieldTypes.CONNECTION_REF in SENSITIVE_FIELD_TYPES
    assert input_model.track_in_telemetry is False
    assert input_model.load_from_db is False
    assert input_model.password is False
    serialized = input_model.model_dump(by_alias=True)
    serialized.pop("_input_type")
    assert isinstance(
        instantiate_input("ConnectionRefInput", serialized),
        ConnectionRefInput,
    )
    assert create_input_schema([input_model]).model_fields == {}
    assert create_input_schema_from_dict([dotdict(input_model.to_dict())]).model_fields == {}

    with pytest.raises(ValidationError, match="tool-call"):
        ConnectionRefInput(name="connection", provider="google", tool_mode=True)


def _provider(provider_id: str = "google") -> IntegrationProvider:
    profile = OAuthProfile(id="user", kind="oauth2_authorization_code", identity="user_delegated")
    capability = IntegrationCapability(
        id="google.drive.read",
        display_name="Read Drive",
        auth_profile_id="user",
        identity="user_delegated",
        required_scopes=("drive.read",),
        conditional_scopes=(
            ConditionalScopeRequirement(
                scope="drive.write",
                role="optional",
                condition=ScopeCondition(kind="input_truthy", input="write"),
            ),
        ),
        policy_keys=("integrations.google.drive.read",),
        substrate="sdk",
        maturity="ga",
        deployment_contexts=("hosted", "self_managed", "desktop", "headless"),
        risk="read",
        component_ref="GoogleDriveComponent",
    )
    return IntegrationProvider(
        provider_id=provider_id,
        display_name="Google",
        auth_profiles=(profile,),
        capabilities=(capability,),
    )


def test_scope_set_activates_conditional_requirements() -> None:
    capability = _provider().capabilities[0]

    assert ScopeSet.covers(capability, {"write": False}, {"drive.read"}, provider="google") == frozenset()
    assert ScopeSet.covers(capability, {"write": True}, {"drive.read"}, provider="google") == frozenset({"drive.write"})


def test_oauth_profile_kinds_match_discovery_schema() -> None:
    schema_path = Path(__file__).parents[5] / "design/dedicated-integrations/schema/capability_matrix.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert set(get_args(OAuthKind)) == set(schema["$defs"]["auth_mode"]["enum"])


def test_capability_enums_match_discovery_schema() -> None:
    schema_path = Path(__file__).parents[5] / "design/dedicated-integrations/schema/capability_matrix.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert set(get_args(ExecutionSubstrate)) == set(schema["$defs"]["substrate"]["enum"])
    assert set(get_args(CapabilityMaturity)) == set(schema["$defs"]["substrate_ga_status"]["enum"])
    deployment_contexts = schema["$defs"]["action"]["properties"]["deployment_contexts"]["properties"]
    assert set(get_args(DeploymentContext)) == set(deployment_contexts)


def test_extension_manifest_accepts_unique_integration_references() -> None:
    manifest_data = {
        "id": "lfx-google",
        "version": "1.0.0",
        "name": "Google",
        "lfx": {"compat": ["1"]},
        "bundles": [{"name": "google", "path": "google"}],
        "integrations": [{"provider_id": "google", "bundle": "google", "path": "capabilities.json"}],
    }

    manifest = ExtensionManifest.model_validate(manifest_data)
    assert manifest.integrations[0].provider_id == "google"


def test_extension_manifest_rejects_duplicate_integration_provider_ids() -> None:
    reference = {"provider_id": "google", "bundle": "google", "path": "capabilities.json"}
    with pytest.raises(ValidationError, match="must be unique"):
        ExtensionManifest.model_validate(
            {
                "id": "lfx-google",
                "version": "1.0.0",
                "name": "Google",
                "lfx": {"compat": ["1"]},
                "bundles": [{"name": "google", "path": "google"}],
                "integrations": [reference, reference],
            }
        )


def test_extension_manifest_rejects_integration_reference_to_unknown_bundle() -> None:
    with pytest.raises(ValidationError, match="unknown bundles"):
        ExtensionManifest.model_validate(
            {
                "id": "lfx-google",
                "version": "1.0.0",
                "name": "Google",
                "lfx": {"compat": ["1"]},
                "bundles": [{"name": "google", "path": "google"}],
                "integrations": [{"provider_id": "google", "bundle": "microsoft", "path": "capabilities.json"}],
            }
        )


def test_integration_provider_rejects_profile_identity_mismatch() -> None:
    provider = _provider().model_dump(mode="json")
    provider["capabilities"][0]["identity"] = "bot"

    with pytest.raises(ValidationError, match="identity does not match"):
        IntegrationProvider.model_validate(provider)
