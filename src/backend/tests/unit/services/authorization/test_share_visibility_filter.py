"""Unit tests for share_visibility_filter (SQL share-backed list prefilter).

We don't need a live DB to verify the shape of the SQL — the helper returns
a SQLAlchemy ``ColumnElement``; compiling it against the SQLite dialect gives
us a deterministic string we can assert against. That covers the two important
contracts:

* AUTHZ off → resolves to an exact owner-scoped equality
  (matches the pre-authz query).
* AUTHZ on → ORs in owner, optional PUBLIC, and the share subquery.
"""

from __future__ import annotations

from enum import Enum
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.authorization import fetch as fetch_module
from langflow.services.authorization import share_visibility_filter
from sqlalchemy.dialects import sqlite


def _install_settings(monkeypatch, *, authz_enabled: bool) -> None:
    settings = SimpleNamespace(auth_settings=SimpleNamespace(AUTHZ_ENABLED=authz_enabled))
    monkeypatch.setattr(fetch_module, "get_settings_service", lambda: settings)


def _compile(expr) -> str:
    return str(
        expr.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}),
    )


class _AccessType(str, Enum):
    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"


def test_returns_owner_equality_when_authz_disabled(monkeypatch):
    """AUTHZ off must yield exactly the owner-scoped query, no share JOIN."""
    from langflow.services.database.models.flow.model import Flow

    _install_settings(monkeypatch, authz_enabled=False)
    user = SimpleNamespace(id=uuid4())

    expr = share_visibility_filter(
        user,
        resource_type="flow",
        id_column=Flow.id,
        owner_column=Flow.user_id,
    )
    sql = _compile(expr)
    assert "flow.user_id" in sql
    # SQLite renders UUIDs as 32-character hex (no dashes) when bound literally.
    assert str(user.id).replace("-", "") in sql
    assert "authz_share" not in sql, "AUTHZ-off path must never touch authz_share"
    assert "OR" not in sql.upper() or sql.upper().count("OR") == 0, sql


def test_combines_owner_public_and_share_subquery_when_authz_enabled(monkeypatch):
    """AUTHZ on must OR together owner, PUBLIC, and the authz_share subquery."""
    from langflow.services.database.models.flow.model import Flow

    _install_settings(monkeypatch, authz_enabled=True)
    user = SimpleNamespace(id=uuid4())

    expr = share_visibility_filter(
        user,
        resource_type="flow",
        id_column=Flow.id,
        owner_column=Flow.user_id,
        access_type_column=Flow.access_type,
        public_value=_AccessType.PUBLIC,
    )
    sql = _compile(expr)
    assert "flow.user_id" in sql
    assert "authz_share" in sql, "AUTHZ-on path must consult authz_share"
    assert "authz_team_member" in sql, "team scope must join authz_team_member"
    assert "PUBLIC" in sql
    # All three branches must be ORed together at the top level.
    assert sql.upper().count(" OR ") >= 2


def test_omits_public_branch_when_no_access_type_column(monkeypatch):
    from langflow.services.database.models.flow.model import Flow

    _install_settings(monkeypatch, authz_enabled=True)
    user = SimpleNamespace(id=uuid4())

    expr = share_visibility_filter(
        user,
        resource_type="flow",
        id_column=Flow.id,
        owner_column=Flow.user_id,
    )
    sql = _compile(expr)
    assert "authz_share" in sql
    assert "PUBLIC" not in sql, "no access_type_column → no PUBLIC clause"


def test_public_value_required_when_access_type_column_provided(monkeypatch):
    from langflow.services.database.models.flow.model import Flow

    _install_settings(monkeypatch, authz_enabled=True)
    user = SimpleNamespace(id=uuid4())

    with pytest.raises(ValueError, match="public_value"):
        share_visibility_filter(
            user,
            resource_type="flow",
            id_column=Flow.id,
            owner_column=Flow.user_id,
            access_type_column=Flow.access_type,
        )


def test_subquery_filters_on_resource_type_and_permission_levels(monkeypatch):
    from langflow.services.database.models.flow.model import Flow

    _install_settings(monkeypatch, authz_enabled=True)
    user = SimpleNamespace(id=uuid4())

    expr = share_visibility_filter(
        user,
        resource_type="deployment",
        id_column=Flow.id,  # using Flow.id for compile shape only
        owner_column=Flow.user_id,
    )
    sql = _compile(expr)
    assert "resource_type = 'deployment'" in sql.replace('"', "")
    # Default permission levels include the full read-or-above ladder.
    for level in ("read", "write", "execute", "admin"):
        assert level in sql
