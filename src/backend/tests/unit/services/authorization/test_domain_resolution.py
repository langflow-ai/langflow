"""Tests for ``_resolve_authz_domain``, ``_split_obj``, and action coercion."""

from __future__ import annotations

from uuid import uuid4

from langflow.services.authorization import audit as authz_audit
from langflow.services.authorization import guards as authz_guards


def test_resolve_authz_domain_precedence():
    """Domain precedence: project > workspace > '*'."""
    ws, scope = uuid4(), uuid4()
    assert authz_guards._resolve_authz_domain(workspace_id=ws, scope_id=scope) == f"project:{scope}"
    assert authz_guards._resolve_authz_domain(workspace_id=ws, scope_id=None) == f"workspace:{ws}"
    assert authz_guards._resolve_authz_domain(workspace_id=None, scope_id=scope) == f"project:{scope}"
    assert authz_guards._resolve_authz_domain(workspace_id=None, scope_id=None) == "*"
    # Backward-compatible alias still resolves to the same function.
    assert authz_guards._resolve_flow_domain is authz_guards._resolve_authz_domain


def test_split_obj_parses_uuid_suffix():
    """flow:<uuid> splits into ('flow', UUID)."""
    flow_id = uuid4()
    resource_type, resource_id = authz_audit._split_obj(f"flow:{flow_id}")
    assert resource_type == "flow"
    assert resource_id == flow_id


def test_split_obj_wildcard_returns_none_id():
    """flow:* keeps resource_type but emits None for resource_id."""
    resource_type, resource_id = authz_audit._split_obj("flow:*")
    assert resource_type == "flow"
    assert resource_id is None


def test_split_obj_malformed_returns_nones():
    """A key without a colon returns (None, None)."""
    assert authz_audit._split_obj("nothing") == (None, None)


def test_split_obj_non_uuid_suffix_returns_none_id():
    """A non-UUID suffix is treated as a wildcard for the resource_id field."""
    resource_type, resource_id = authz_audit._split_obj("flow:not-a-uuid")
    assert resource_type == "flow"
    assert resource_id is None
