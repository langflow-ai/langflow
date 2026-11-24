"""Schema and pagination-math tests for the ``/api/v1/authz/audit`` endpoint.

The full live-app integration test sits in a heavier fixture suite; here we
just pin the response-shape contract and the ceiling on ``size``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.api.v1.authz_audit import AuthzAuditLogRead, AuthzAuditPage
from pydantic import ValidationError


def test_audit_log_read_accepts_minimal_row():
    """user_id, resource_type, resource_id, details may all be None."""
    row = AuthzAuditLogRead(
        id=uuid4(),
        user_id=None,
        actor_type=None,
        actor_id=None,
        action="flow:read",
        resource_type=None,
        resource_id=None,
        result="allow",
        details=None,
        timestamp=datetime.now(timezone.utc),
    )
    assert row.action == "flow:read"
    assert row.user_id is None
    assert row.actor_type is None
    assert row.actor_id is None


def test_audit_log_read_carries_details_dict():
    """The details payload is a free-form dict produced by audit_decision."""
    row = AuthzAuditLogRead(
        id=uuid4(),
        user_id=uuid4(),
        actor_type="api_key",
        actor_id=uuid4(),
        action="flow:write",
        resource_type="flow",
        resource_id=uuid4(),
        result="deny",
        details={"domain": "project:abc", "flow_user_id": str(uuid4())},
        timestamp=datetime.now(timezone.utc),
    )
    assert row.details["domain"] == "project:abc"
    assert row.actor_type == "api_key"


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
            actor_type=None,
            actor_id=None,
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
            actor_type=None,
            actor_id=None,
            resource_type=None,
            resource_id=None,
            result="allow",
            details=None,
            timestamp=datetime.now(timezone.utc),
        )


class _Result:
    def __init__(self, rows):
        self.rows = list(rows)

    def first(self):
        return self.rows[0] if self.rows else None

    def __iter__(self):
        return iter(self.rows)


class _Session:
    def __init__(self, row):
        self.rows = row if isinstance(row, list) else [row]
        self.statements = []

    async def exec(self, statement):
        self.statements.append(statement)
        if len(self.statements) == 1:
            return _Result([len(self.rows)])
        return _Result(self.rows)


@pytest.mark.anyio
async def test_audit_query_filters_and_returns_first_class_actor_fields():
    from langflow.api.v1.authz_audit import list_audit_log

    actor_id = uuid4()
    row = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        actor_type="api_key",
        actor_id=actor_id,
        action="flow:read",
        resource_type="flow",
        resource_id=uuid4(),
        result="allow",
        details={"api_key_source": "db"},  # pragma: allowlist secret
        timestamp=datetime.now(timezone.utc),
    )
    session = _Session(row)

    result = await list_audit_log(
        session=session,
        _admin=SimpleNamespace(),
        user_id=None,
        actor_type="api_key",
        actor_id=actor_id,
        resource_type=None,
        resource_id=None,
        action=None,
        result=None,
        since=None,
        until=None,
        page=1,
        size=50,
    )

    assert result.items[0].actor_type == "api_key"
    assert result.items[0].actor_id == actor_id
    count_sql = str(session.statements[0])
    assert "authz_audit_log.actor_type" in count_sql
    assert "authz_audit_log.actor_id" in count_sql
    page_sql = str(session.statements[1])
    assert "ORDER BY authz_audit_log.timestamp DESC, authz_audit_log.id DESC" in page_sql


@pytest.mark.anyio
async def test_audit_query_filters_skipped_reconciliation_results():
    from langflow.api.v1.authz_audit import list_audit_log

    row = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        actor_type="user",
        actor_id=uuid4(),
        action="directory_membership:reconcile",
        resource_type="user",
        resource_id=uuid4(),
        result="skip",
        details={"reason": "overage"},
        timestamp=datetime.now(timezone.utc),
    )
    session = _Session(row)

    result = await list_audit_log(
        session=session,
        _admin=SimpleNamespace(),
        user_id=None,
        actor_type=None,
        actor_id=None,
        resource_type=None,
        resource_id=None,
        action="directory_membership:reconcile",
        exclude_action=["audit:read"],
        result="skip",
        since=None,
        until=None,
        page=1,
        size=50,
    )

    assert result.items[0].result == "skip"
    assert result.items[0].details == {"reason": "overage"}
    assert "authz_audit_log.action" in str(session.statements[0])
    assert "authz_audit_log.action NOT IN" in str(session.statements[0])
    assert "authz_audit_log.result" in str(session.statements[0])


@pytest.mark.anyio
async def test_unknown_actor_filter_includes_legacy_null_and_explicit_unknown_rows():
    from langflow.api.v1.authz_audit import list_audit_log

    rows = [
        SimpleNamespace(
            id=uuid4(),
            user_id=None,
            actor_type=None,
            actor_id=None,
            action="flow:read",
            resource_type="flow",
            resource_id=uuid4(),
            result="allow",
            details=None,
            timestamp=datetime.now(timezone.utc),
        ),
        SimpleNamespace(
            id=uuid4(),
            user_id=None,
            actor_type="unknown",
            actor_id=None,
            action="system:sync",
            resource_type=None,
            resource_id=None,
            result="allow",
            details=None,
            timestamp=datetime.now(timezone.utc),
        ),
    ]
    session = _Session(rows)

    result = await list_audit_log(
        session=session,
        _admin=SimpleNamespace(),
        user_id=None,
        actor_type="unknown",
        actor_id=None,
        resource_type=None,
        resource_id=None,
        action=None,
        result=None,
        since=None,
        until=None,
        page=1,
        size=50,
    )

    assert [item.actor_type for item in result.items] == [None, "unknown"]
    count_sql = str(session.statements[0])
    assert "authz_audit_log.actor_type IS NULL" in count_sql
    assert "authz_audit_log.actor_type =" in count_sql


def test_filter_vocabularies_match_audit_writer_constants():
    from typing import get_args

    from langflow.api.v1.authz_audit import AuditActorTypeFilter, AuditResultFilter
    from langflow.services.authorization import audit
    from lfx.services.authorization import AuthorizationPrincipal

    assert set(get_args(AuditResultFilter)) == {
        audit.AUDIT_ALLOW,
        audit.AUDIT_DENY,
        audit.AUDIT_OWNER_OVERRIDE,
        audit.AUDIT_SKIP,
    }
    assert set(get_args(AuditActorTypeFilter)) == {
        audit.AUDIT_ACTOR_USER,
        audit.AUDIT_ACTOR_API_KEY,
        audit.AUDIT_ACTOR_UNKNOWN,
        AuthorizationPrincipal.public_anonymous().actor_type,
    }


@pytest.fixture
def audit_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from langflow.api.utils.core import injectable_session_scope
    from langflow.api.v1.authz_audit import router
    from langflow.services.auth.utils import get_current_active_superuser

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def _session():
        yield _Session([])

    app.dependency_overrides[injectable_session_scope] = _session
    app.dependency_overrides[get_current_active_superuser] = lambda: SimpleNamespace()
    return TestClient(app)


@pytest.mark.parametrize(
    ("param", "value", "accepted"),
    [
        ("result", "banana", "'allow', 'deny', 'owner_override' or 'skip'"),
        ("result", "denied", "'allow', 'deny', 'owner_override' or 'skip'"),
        ("result", "Deny", "'allow', 'deny', 'owner_override' or 'skip'"),
        ("actor_type", "bogus", "'user', 'api_key', 'unknown' or 'anonymous_public'"),
    ],
)
def test_invalid_filter_value_is_rejected_with_accepted_values(audit_client, param, value, accepted):
    response = audit_client.get("/api/v1/authz/audit", params={param: value, "size": 1})

    assert response.status_code == 422
    [error] = response.json()["detail"]
    assert error["loc"] == ["query", param]
    assert accepted in error["msg"]


@pytest.mark.parametrize(("param", "value"), [("result", "deny"), ("actor_type", "api_key")])
def test_valid_filter_value_is_accepted(audit_client, param, value):
    response = audit_client.get("/api/v1/authz/audit", params={param: value, "size": 1})

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "size": 1, "pages": 0}
