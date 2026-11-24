"""Schema-level tests for the AuthzShare CRUD payloads.

The integration-level test (live app fixture, DB row roundtrip) lives in
``test_authz_shares.py``; here we just pin the validator that enforces the
``scope_target_consistency`` rule at the API boundary so callers get 422 with
a readable message instead of a SQL constraint failure.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from langflow.api.v1.schemas.authz_shares import ShareCreate
from pydantic import ValidationError


def test_user_scope_requires_target_id():
    """scope=user must carry a target_id (the user being granted access)."""
    with pytest.raises(ValidationError) as exc:
        ShareCreate(
            resource_type="flow",
            resource_id=uuid4(),
            scope="user",
            target_id=None,
            permission_level="read",
        )
    assert "target_id" in str(exc.value)


def test_team_scope_requires_target_id():
    with pytest.raises(ValidationError) as exc:
        ShareCreate(
            resource_type="flow",
            resource_id=uuid4(),
            scope="team",
            target_id=None,
            permission_level="read",
        )
    assert "target_id" in str(exc.value)


def test_public_scope_rejects_target_id():
    """scope=public is meaningless with a target_id; reject at the API edge."""
    with pytest.raises(ValidationError) as exc:
        ShareCreate(
            resource_type="flow",
            resource_id=uuid4(),
            scope="public",
            target_id=uuid4(),
            permission_level="read",
        )
    assert "target_id" in str(exc.value)


def test_private_scope_rejects_target_id():
    with pytest.raises(ValidationError) as exc:
        ShareCreate(
            resource_type="flow",
            resource_id=uuid4(),
            scope="private",
            target_id=uuid4(),
            permission_level="read",
        )
    assert "target_id" in str(exc.value)


def test_user_scope_with_target_is_valid():
    payload = ShareCreate(
        resource_type="flow",
        resource_id=uuid4(),
        scope="user",
        target_id=uuid4(),
        permission_level="write",
    )
    assert payload.scope == "user"
    assert payload.permission_level == "write"


def test_public_scope_without_target_is_valid():
    payload = ShareCreate(
        resource_type="deployment",
        resource_id=uuid4(),
        scope="public",
        permission_level="read",
    )
    assert payload.target_id is None


def test_unknown_resource_type_rejected():
    """Resource type is a Literal so unknown values 422 at the schema edge."""
    with pytest.raises(ValidationError):
        ShareCreate(
            resource_type="banana",  # type: ignore[arg-type]
            resource_id=uuid4(),
            scope="public",
            permission_level="read",
        )


def test_unknown_permission_level_rejected():
    with pytest.raises(ValidationError):
        ShareCreate(
            resource_type="flow",
            resource_id=uuid4(),
            scope="public",
            permission_level="execute_with_extra_steps",  # type: ignore[arg-type]
        )
