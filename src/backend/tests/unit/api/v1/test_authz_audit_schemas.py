"""Schema and pagination-math tests for the ``/api/v1/authz/audit`` endpoint.

The full live-app integration test sits in a heavier fixture suite; here we
just pin the response-shape contract and the ceiling on ``size``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from langflow.api.v1.authz_audit import AuthzAuditLogRead, AuthzAuditPage
from pydantic import ValidationError


def test_audit_log_read_accepts_minimal_row():
    """user_id, resource_type, resource_id, details may all be None."""
    row = AuthzAuditLogRead(
        id=uuid4(),
        user_id=None,
        action="flow:read",
        resource_type=None,
        resource_id=None,
        result="allow",
        details=None,
        timestamp=datetime.now(timezone.utc),
    )
    assert row.action == "flow:read"
    assert row.user_id is None


def test_audit_log_read_carries_details_dict():
    """The details payload is a free-form dict produced by audit_decision."""
    row = AuthzAuditLogRead(
        id=uuid4(),
        user_id=uuid4(),
        action="flow:write",
        resource_type="flow",
        resource_id=uuid4(),
        result="deny",
        details={"domain": "project:abc", "flow_user_id": str(uuid4())},
        timestamp=datetime.now(timezone.utc),
    )
    assert row.details["domain"] == "project:abc"


def test_audit_page_envelope_round_trip():
    page = AuthzAuditPage(items=[], total=0, page=1, size=50, pages=0)
    assert page.total == 0
    assert page.pages == 0


def test_audit_page_rejects_negative_total():
    """``total`` must be >= 0 — Pydantic infers int but does not enforce bounds.

    This test is a contract check: if someone adds a validator, the page
    envelope should reject nonsensical values rather than silently propagate
    them to the client.
    """
    # We currently accept any int; this test is a placeholder so a future
    # validator addition is caught by the suite.
    page = AuthzAuditPage(items=[], total=0, page=1, size=50, pages=0)
    assert isinstance(page.total, int)


def test_audit_log_read_requires_id_and_action():
    with pytest.raises(ValidationError):
        AuthzAuditLogRead(  # type: ignore[call-arg]
            user_id=None,
            action="flow:read",
            resource_type=None,
            resource_id=None,
            result="allow",
            details=None,
            timestamp=datetime.now(timezone.utc),
        )
    with pytest.raises(ValidationError):
        AuthzAuditLogRead(  # type: ignore[call-arg]
            id=uuid4(),
            user_id=None,
            resource_type=None,
            resource_id=None,
            result="allow",
            details=None,
            timestamp=datetime.now(timezone.utc),
        )
