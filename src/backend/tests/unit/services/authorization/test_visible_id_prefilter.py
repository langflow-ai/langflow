"""Tests for the DB-layer authz prefilter helpers.

``visible_id_prefilter`` / ``restrict_to_owned_or_visible`` wire
``BaseAuthorizationService.list_visible_resource_ids`` into the list endpoints:
a registered plugin returns the concrete set of ids the caller may read so the
query can ``WHERE id IN (...)`` prefilter at the DB layer (unioned with owner
rows) instead of fetching everything and running a per-row enforce.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from langflow.services.authorization import listing as authz_listing
from langflow.services.authorization.actions import ProjectAction
from langflow.services.authorization.listing import restrict_to_owned_or_visible, visible_id_prefilter
from langflow.services.database.models.flow.model import Flow
from sqlmodel import select

from ._common import _StubAuthorizationService, install_authz, install_settings


@pytest.mark.anyio
async def test_visible_id_prefilter_returns_none_when_disabled(monkeypatch, fake_user):
    """AUTHZ_ENABLED=False short-circuits to None without contacting the service.

    This is what keeps OSS installs byte-for-byte unchanged: the caller treats
    None as "keep the owner-scoped query + filter_visible_resources".
    """
    install_settings(monkeypatch, authz_enabled=False)
    service = _StubAuthorizationService(visible_ids=[uuid4()])
    install_authz(monkeypatch, service)

    result = await visible_id_prefilter(fake_user, resource_type="flow")

    assert result is None
    assert service.visible_calls == []


@pytest.mark.anyio
async def test_visible_id_prefilter_returns_none_when_plugin_declines(monkeypatch, fake_user):
    """A registered service that returns None (OSS pass-through) yields None.

    The pass-through declines to prefilter, so the caller falls back to the
    in-memory filter exactly as before.
    """
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(visible_ids=None)
    install_authz(monkeypatch, service)

    result = await visible_id_prefilter(fake_user, resource_type="flow")

    assert result is None
    # The service WAS consulted (unlike the disabled case).
    assert len(service.visible_calls) == 1


@pytest.mark.anyio
async def test_visible_id_prefilter_returns_concrete_list_and_forwards_args(monkeypatch, fake_user):
    """A concrete list is returned verbatim; resource_type/domain/act/context forwarded."""
    install_settings(monkeypatch, authz_enabled=True)
    visible = [uuid4(), uuid4()]
    service = _StubAuthorizationService(visible_ids=visible)
    install_authz(monkeypatch, service)

    result = await visible_id_prefilter(
        fake_user,
        resource_type="project",
        domain="workspace:abc",
        act=ProjectAction.READ,
    )

    assert result == visible
    call = service.visible_calls[0]
    assert call["user_id"] == fake_user.id
    assert call["resource_type"] == "project"
    assert call["domain"] == "workspace:abc"
    # Action enum is coerced to its string value before reaching the service.
    assert call["act"] == "read"
    # Auth context carries the superuser flag for the plugin's policy check.
    assert call["context"]["is_superuser"] is False


@pytest.mark.anyio
async def test_visible_id_prefilter_default_domain_and_act(monkeypatch, fake_user):
    """Defaults: wildcard domain and READ action (the common cross-domain list case)."""
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(visible_ids=[])
    install_authz(monkeypatch, service)

    result = await visible_id_prefilter(fake_user, resource_type="flow")

    assert result == []
    call = service.visible_calls[0]
    assert call["domain"] == "*"
    assert call["act"] == "read"


def test_restrict_to_owned_or_visible_unions_ids_and_owner():
    """The constrained statement keeps a row when owned OR id-in-visible."""
    owner_id = uuid4()
    visible = [uuid4(), uuid4()]
    owner_clause = Flow.user_id == owner_id

    constrained = restrict_to_owned_or_visible(
        select(Flow),
        id_column=Flow.id,
        owner_clause=owner_clause,
        visible_ids=visible,
    )

    sql = str(constrained)
    # An ``id IN (...)`` prefilter OR-ed with the owner predicate.
    assert "flow.id IN" in sql
    assert "flow.user_id =" in sql
    assert " OR " in sql


def test_restrict_to_owned_or_visible_empty_ids_keeps_owner_rows():
    """An empty visible set still returns every owned row (owner-override invariant).

    A plugin reporting "no extra visible ids" must never hide the caller's own
    rows — the union degrades to "owned only", not "nothing".
    """
    owner_id = uuid4()
    owner_clause = Flow.user_id == owner_id

    constrained = restrict_to_owned_or_visible(
        select(Flow),
        id_column=Flow.id,
        owner_clause=owner_clause,
        visible_ids=[],
    )

    sql = str(constrained)
    # The owner predicate survives; the empty IN matches nothing at execution.
    assert "flow.user_id =" in sql


def test_helpers_are_exported_from_package():
    """Both helpers are part of the authorization package's public surface."""
    from langflow.services import authorization

    assert authorization.visible_id_prefilter is visible_id_prefilter
    assert authorization.restrict_to_owned_or_visible is restrict_to_owned_or_visible
    # Same callables the listing module defines (no shadowing).
    assert authz_listing.visible_id_prefilter is visible_id_prefilter
