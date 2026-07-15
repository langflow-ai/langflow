"""Structured DB prefilter coverage for scoped authorization grants."""

from __future__ import annotations

from uuid import uuid4

import pytest
from langflow.services.authorization.listing import (
    restrict_to_owned_or_visible_scope,
    visible_scope_prefilter,
)
from langflow.services.database.models.flow.model import Flow
from lfx.services.authorization.base import ResourceVisibilityScope
from sqlmodel import select

from ._common import _StubAuthorizationService, install_authz, install_settings


class _ScopedAuthorizationService(_StubAuthorizationService):
    def __init__(self, scope: ResourceVisibilityScope | None) -> None:
        super().__init__()
        self.scope = scope

    async def get_resource_visibility(self, **kwargs) -> ResourceVisibilityScope | None:
        self.visible_calls.append(kwargs)
        return self.scope


@pytest.mark.anyio
async def test_visible_scope_prefilter_forwards_structured_scope(monkeypatch, fake_user):
    install_settings(monkeypatch, authz_enabled=True)
    workspace_id = uuid4()
    project_id = uuid4()
    scope = ResourceVisibilityScope(workspace_ids=(workspace_id,), project_ids=(project_id,))
    service = _ScopedAuthorizationService(scope)
    install_authz(monkeypatch, service)

    result = await visible_scope_prefilter(fake_user, resource_type="flow", act="read")

    assert result == scope
    assert service.visible_calls == [
        {
            "user_id": fake_user.id,
            "resource_type": "flow",
            "domain": "*",
            "act": "read",
            "context": {"is_superuser": False},
        }
    ]


@pytest.mark.anyio
async def test_visible_scope_prefilter_adapts_legacy_concrete_id_service(monkeypatch, fake_user):
    install_settings(monkeypatch, authz_enabled=True)
    visible_ids = [uuid4(), uuid4()]
    service = _StubAuthorizationService(visible_ids=visible_ids)
    install_authz(monkeypatch, service)

    result = await visible_scope_prefilter(fake_user, resource_type="flow", act="read")

    assert result == ResourceVisibilityScope(resource_ids=tuple(visible_ids))
    assert len(service.visible_calls) == 1


def test_scope_predicate_unions_owner_explicit_workspace_and_project_grants():
    owner_id = uuid4()
    scope = ResourceVisibilityScope(
        resource_ids=(uuid4(),),
        workspace_ids=(uuid4(),),
        project_ids=(uuid4(),),
    )

    constrained = restrict_to_owned_or_visible_scope(
        select(Flow),
        id_column=Flow.id,
        owner_clause=Flow.user_id == owner_id,
        workspace_column=Flow.workspace_id,
        project_column=Flow.folder_id,
        visibility=scope,
    )

    sql = str(constrained)
    assert "flow.user_id =" in sql
    assert "flow.id IN" in sql
    assert "flow.workspace_id IN" in sql
    assert "flow.folder_id IN" in sql
    assert sql.count(" OR ") == 3


def test_global_scope_does_not_emit_an_unbounded_id_list():
    constrained = restrict_to_owned_or_visible_scope(
        select(Flow),
        id_column=Flow.id,
        owner_clause=Flow.user_id == uuid4(),
        workspace_column=Flow.workspace_id,
        project_column=Flow.folder_id,
        visibility=ResourceVisibilityScope(all_resources=True),
    )

    sql = str(constrained)
    assert "flow.id IN" not in sql
    assert "flow.user_id =" not in sql


def test_scope_reports_cross_user_access_without_resource_enumeration():
    assert ResourceVisibilityScope().has_cross_user_access is False
    assert ResourceVisibilityScope(all_resources=True).has_cross_user_access is True
    assert ResourceVisibilityScope(workspace_ids=(uuid4(),)).has_cross_user_access is True
