"""Tests for the custom-component/catalog policy interaction matrix."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status
from langflow.api.v1 import custom_component_policy
from lfx.services.catalog_policy.base import CatalogPolicySnapshot
from lfx.utils.flow_validation import CatalogPolicyIdentityUnavailableError, CatalogPolicyValidationError


@pytest.mark.parametrize(
    (
        "catalog_blocked",
        "known_template",
        "allow_custom_components",
        "admin_only",
        "is_superuser",
        "expected_status",
        "expected_code",
        "expected_detail",
    ),
    [
        (True, True, True, False, True, status.HTTP_403_FORBIDDEN, None, "Agent"),
        (True, True, False, True, False, status.HTTP_403_FORBIDDEN, None, "Agent"),
        (False, True, False, False, False, None, "trusted server code", None),
        (False, True, True, True, False, None, "trusted server code", None),
        (False, False, False, False, True, status.HTTP_403_FORBIDDEN, None, "disabled"),
        (False, False, True, True, False, status.HTTP_403_FORBIDDEN, None, "admin only"),
        (False, False, True, True, True, None, "submitted code", None),
        (False, False, True, False, False, None, "submitted code", None),
    ],
)
def test_resolve_component_code_interaction_matrix(
    monkeypatch,
    catalog_blocked,
    known_template,
    allow_custom_components,
    admin_only,
    is_superuser,
    expected_status,
    expected_code,
    expected_detail,
):
    """Catalog denial wins; otherwise known templates and custom lockdown compose."""

    def validate_catalog(_code, *, snapshot):
        assert isinstance(snapshot, CatalogPolicySnapshot)
        if catalog_blocked:
            message = "Catalog policy blocks components: Agent"
            raise CatalogPolicyValidationError(message)

    monkeypatch.setattr(custom_component_policy, "validate_catalog_policy_for_component_code", validate_catalog)
    monkeypatch.setattr(custom_component_policy, "get_component_hash_lookups_for_validation", dict)
    monkeypatch.setattr(custom_component_policy.component_cache, "all_known_hashes", {"known-hash"})
    monkeypatch.setattr(
        custom_component_policy,
        "code_hash_matches_any_template",
        lambda _code, _all_known: known_template,
    )
    monkeypatch.setattr(
        custom_component_policy,
        "get_trusted_code_for_validation",
        lambda _code: "trusted server code" if known_template else None,
    )

    call = lambda: custom_component_policy.resolve_component_code_for_action(  # noqa: E731
        "submitted code",
        user=SimpleNamespace(is_superuser=is_superuser),
        settings=SimpleNamespace(
            allow_custom_components=allow_custom_components,
            custom_component_admin_only=admin_only,
        ),
        snapshot=CatalogPolicySnapshot(blocked_component_keys={"Agent"})
        if catalog_blocked
        else CatalogPolicySnapshot(),
        disabled_detail="disabled",
        admin_only_detail="admin only",
    )

    if expected_status is None:
        assert call() == expected_code
    else:
        with pytest.raises(HTTPException) as exc_info:
            call()
        assert exc_info.value.status_code == expected_status
        assert expected_detail in exc_info.value.detail


def test_catalog_component_type_denial_has_no_superuser_bypass(monkeypatch):
    def deny_agent(component_type, *, snapshot):
        assert component_type == "Agent"
        assert snapshot.is_component_blocked("Agent")
        message = "Catalog policy blocks components: Agent"
        raise CatalogPolicyValidationError(message)

    monkeypatch.setattr(custom_component_policy, "validate_catalog_policy_for_component_type", deny_agent)

    with pytest.raises(HTTPException) as exc_info:
        custom_component_policy.enforce_catalog_policy_for_component_type(
            "Agent",
            snapshot=CatalogPolicySnapshot(blocked_component_keys={"Agent"}),
        )

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


def test_catalog_component_type_alias_resolution_initialization_maps_to_503(monkeypatch):
    def identities_unavailable(_component_type, *, snapshot):
        assert snapshot.blocked_component_keys
        message = "Catalog policy component identities are still initializing"
        raise CatalogPolicyIdentityUnavailableError(message)

    monkeypatch.setattr(
        custom_component_policy,
        "validate_catalog_policy_for_component_type",
        identities_unavailable,
    )

    with pytest.raises(HTTPException) as exc_info:
        custom_component_policy.enforce_catalog_policy_for_component_type(
            "PromptComponent",
            snapshot=CatalogPolicySnapshot(blocked_component_keys={"Prompt Template"}),
        )

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
