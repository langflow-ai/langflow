"""INT-14 GA: the connection and integration API schemas are frozen contracts.

The connection picker (INT-8) and the operator policy panel render these field
names verbatim, so a rename or removal is a breaking change. These tests pin the
exact field sets and vocabularies, and pin that no read model can ever carry
credential material.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import get_args
from uuid import uuid4

import pytest
from langflow.api.v1.connections import OAuthStartRequest, OAuthStartResponse
from langflow.api.v1.integrations import (
    EffectiveIntegrationPolicyRead,
    IntegrationCapabilityRead,
    IntegrationListRead,
    IntegrationProviderRead,
)
from langflow.services.database.models.connection.schemas import (
    ConnectionCreate,
    ConnectionCredentialWrite,
    ConnectionHealth,
    ConnectionOwnershipMode,
    ConnectionRead,
    ConnectionRevokeRead,
    ConnectionStatusReason,
    ConnectionTestRequest,
    ConnectionUpdate,
    ExecutingIdentityDescriptor,
    PersistedConnectionStatus,
)
from pydantic import SecretStr, ValidationError

# Names that must never appear on a read schema, in the error bodies the routes
# build from them, or in a JSON dump. A read model gaining one of these is the
# regression this file exists to catch.
SECRET_FIELD_NAMES = {"access_token", "refresh_token", "credentials", "encrypted_payload", "client_secret"}


def _fields(model: type) -> set[str]:
    return set(model.model_fields)


def test_connection_read_fields_are_frozen() -> None:
    assert _fields(ConnectionRead) == {
        "id",
        "owner_id",
        "ownership_mode",
        "provider_key",
        "name",
        "display_name",
        "status",
        "status_reason",
        "health",
        "granted_scopes",
        "executing_identity",
        "allow_non_interactive",
        "has_credentials",
        "health_checked_at",
        "created_at",
        "updated_at",
    }


@pytest.mark.parametrize(
    "model",
    [
        ConnectionRead,
        ConnectionRevokeRead,
        IntegrationCapabilityRead,
        IntegrationProviderRead,
        IntegrationListRead,
        EffectiveIntegrationPolicyRead,
        OAuthStartResponse,
        ExecutingIdentityDescriptor,
    ],
)
def test_no_read_model_exposes_credential_fields(model: type) -> None:
    assert SECRET_FIELD_NAMES.isdisjoint(_fields(model))


def test_connection_revoke_read_adds_only_the_provider_outcome() -> None:
    assert _fields(ConnectionRevokeRead) == _fields(ConnectionRead) | {"provider_revocation"}
    annotation = ConnectionRevokeRead.model_fields["provider_revocation"].annotation
    assert set(get_args(annotation)) == {"revoked", "unsupported", "failed", "not_applicable"}


def test_connection_status_vocabularies_are_frozen() -> None:
    assert {member.value for member in PersistedConnectionStatus} == {
        "pending",
        "ready",
        "expired",
        "revoked",
        "error",
    }
    assert {member.value for member in ConnectionStatusReason} == {
        "credential-missing",
        "credential-undecryptable",
    }
    assert {member.value for member in ConnectionHealth} == {"unknown", "healthy", "unhealthy"}
    assert {member.value for member in ConnectionOwnershipMode} == {"user", "instance"}


def test_connection_create_is_the_only_write_schema_accepting_credentials() -> None:
    assert _fields(ConnectionCreate) == {
        "provider_key",
        "name",
        "display_name",
        "ownership_mode",
        "granted_scopes",
        "executing_identity",
        "allow_non_interactive",
        "credentials",
    }
    assert _fields(ConnectionCredentialWrite) == {
        "access_token",
        "refresh_token",
        "token_type",
        "expires_at",
    }
    # Credential material may only enter through ConnectionCreate.credentials;
    # nothing else on the API surface accepts it.
    assert "credentials" not in _fields(ConnectionUpdate)
    with pytest.raises(ValidationError):
        ConnectionCreate.model_validate(
            {
                "provider_key": "google",
                "name": "work",
                "display_name": "Work",
                "executing_identity": {"identity": "user_delegated"},
                "access_token": "must-be-rejected",
            }
        )


def test_credential_write_masks_secrets_in_json_and_repr() -> None:
    credentials = ConnectionCredentialWrite(
        access_token=SecretStr("access-must-not-leak"),  # pragma: allowlist secret
        refresh_token=SecretStr("refresh-must-not-leak"),  # pragma: allowlist secret
    )

    dumped = json.dumps(credentials.model_dump(mode="json"))
    assert "must-not-leak" not in dumped
    assert "must-not-leak" not in repr(credentials)
    assert "must-not-leak" not in str(credentials)


def test_connection_update_exposes_only_owner_editable_metadata() -> None:
    assert _fields(ConnectionUpdate) == {"display_name", "allow_non_interactive"}
    # Rebinding a handle, widening scopes, or replacing the executing identity
    # is re-authorization, not an update.
    for field in ("provider_key", "name", "granted_scopes", "executing_identity", "credentials"):
        assert field not in _fields(ConnectionUpdate)


def test_oauth_and_test_request_schemas_are_frozen() -> None:
    assert _fields(OAuthStartRequest) == {"registration_id", "scopes"}
    assert _fields(OAuthStartResponse) == {"authorization_url"}
    assert _fields(ConnectionTestRequest) == {"required_scopes"}


def test_executing_identity_descriptor_is_frozen() -> None:
    assert _fields(ExecutingIdentityDescriptor) == {"identity", "account"}


def test_integration_catalog_schemas_are_frozen() -> None:
    assert _fields(IntegrationCapabilityRead) == {
        "id",
        "display_name",
        "policy_keys",
        "risk",
        "maturity",
        "substrate",
        "identity",
        "auth_profile_id",
        "deployment_contexts",
        "component_ref",
        "mcp_tool",
        "allowed",
        "blocked_policy_key",
    }
    assert _fields(IntegrationProviderRead) == {
        "provider_id",
        "display_name",
        "icon",
        "docs_url",
        "approved",
        "enabled",
        "connection_count",
        "capabilities",
    }
    assert _fields(IntegrationListRead) == {"providers"}


def test_effective_policy_schema_is_frozen() -> None:
    assert _fields(EffectiveIntegrationPolicyRead) == {
        "approved_provider_ids",
        "blocked_action_keys",
        "loaded_provider_ids",
        "unrestricted",
        "managed_externally",
        "policy_revision",
    }


def test_connection_read_json_round_trip_carries_no_token_material() -> None:
    """A fully populated read model cannot serialize a token even by accident."""
    read = ConnectionRead(
        id=uuid4(),
        owner_id=uuid4(),
        ownership_mode=ConnectionOwnershipMode.USER,
        provider_key="google_workspace",
        name="work",
        display_name="Work Google",
        status=PersistedConnectionStatus.READY,
        status_reason=None,
        health=ConnectionHealth.HEALTHY,
        granted_scopes=["calendar.readonly"],
        executing_identity=ExecutingIdentityDescriptor(
            identity="user_delegated", account={"id": "account-123", "display": "Work", "tenant_id": "tenant-123"}
        ),
        allow_non_interactive=False,
        has_credentials=True,
        health_checked_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    rendered = read.model_dump_json()

    assert SECRET_FIELD_NAMES.isdisjoint(json.loads(rendered))
    # has_credentials is the only signal a client gets about stored material.
    assert json.loads(rendered)["has_credentials"] is True
