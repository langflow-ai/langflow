"""Tests for the sensitive-field sets that gate MANAGE-level actions."""

from __future__ import annotations

import pytest
from langflow.services.authorization import (
    SENSITIVE_DEPLOYMENT_FIELDS,
    SENSITIVE_FLOW_FIELDS,
    SENSITIVE_PROJECT_FIELDS,
    requires_deployment_manage,
    requires_flow_manage,
    requires_project_manage,
)


def test_flow_sensitive_fields_locked_in():
    """The contract for flow MANAGE is exactly these five administrative fields."""
    assert (
        frozenset(
            {"locked", "access_type", "endpoint_name", "webhook", "mcp_enabled"},
        )
        == SENSITIVE_FLOW_FIELDS
    )


def test_project_sensitive_fields_locked_in():
    """Projects gate MANAGE on governance (auth_settings) and reparenting (parent_id)."""
    assert frozenset({"auth_settings", "parent_id"}) == SENSITIVE_PROJECT_FIELDS


def test_deployment_sensitive_fields_empty_today():
    """No deployment PATCH field is administrative yet; the set is intentionally empty."""
    assert frozenset() == SENSITIVE_DEPLOYMENT_FIELDS


@pytest.mark.parametrize(
    ("payload_field_set", "expected"),
    [
        (set(), False),
        ({"name"}, False),
        ({"name", "description"}, False),
        ({"locked"}, True),
        ({"name", "access_type"}, True),
        ({"endpoint_name"}, True),
        ({"webhook", "name"}, True),
        ({"mcp_enabled"}, True),
    ],
)
def test_requires_flow_manage(payload_field_set, expected):
    assert requires_flow_manage(payload_field_set) is expected


@pytest.mark.parametrize(
    ("payload_field_set", "expected"),
    [
        (set(), False),
        ({"name"}, False),
        ({"description"}, False),
        ({"parent_id"}, True),
        ({"auth_settings"}, True),
        ({"name", "parent_id"}, True),
    ],
)
def test_requires_project_manage(payload_field_set, expected):
    assert requires_project_manage(payload_field_set) is expected


def test_requires_deployment_manage_always_false_today():
    """Until sensitive deployment fields exist, the predicate is a constant False."""
    assert requires_deployment_manage(set()) is False
    assert requires_deployment_manage({"name", "description", "provider_data"}) is False
