"""Validate API key permission policies without starting an application."""

from uuid import uuid4

import pytest
from langflow.services.database.models.api_key.model import ApiKeyCreate
from pydantic import ValidationError


def restriction(**changes):
    return {
        "resource_type": "flow",
        "actions": ["read", "execute"],
        "domain_type": "project",
        "domain_id": str(uuid4()),
        **changes,
    }


def test_creation_preserves_permission_policy():
    policy = {"roles": [], "restrictions": [restriction()]}
    key = ApiKeyCreate.model_validate({"name": "Project runner", "permissions": policy})
    assert key.model_dump(mode="json")["permissions"] == policy


def test_legacy_creation_has_no_permission_policy():
    assert ApiKeyCreate(name="Legacy").model_dump().get("permissions") is None


@pytest.mark.parametrize(
    "policy",
    [
        {},
        {"roles": [], "restrictions": []},
        {"restrictions": [restriction(actions=["manage"])]},
        {"restrictions": [restriction(resource_type="variable")]},
        {"restrictions": [restriction(domain_id=None)]},
        {"restrictions": [restriction(resource_ids=[])]},
        {"restrictions": [restriction(resource_type="user", actions=["manage"], domain_type="global", domain_id=None)]},
        {"restrictions": [restriction(actions=["read"], typo="ignored")]},
        {
            "restrictions": [
                restriction(resource_type="connection", actions=["create"], domain_type="global", domain_id=None)
            ]
        },
        {
            "restrictions": [
                restriction(resource_type="provider_account", actions=["delete"], domain_type="global", domain_id=None)
            ]
        },
    ],
)
def test_creation_rejects_invalid_permission_policy(policy):
    with pytest.raises(ValidationError):
        ApiKeyCreate.model_validate({"name": "Invalid", "permissions": policy})


def test_creation_accepts_role_only_policy():
    role = {"role_id": str(uuid4()), "domain_type": "global", "domain_id": None}
    key = ApiKeyCreate.model_validate({"permissions": {"roles": [role]}})
    assert key.model_dump(mode="json")["permissions"]["roles"] == [role]
