"""Tests for ``filter_visible_resources`` (list-endpoint authorization filter)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.authorization import guards as authz_guards
from langflow.services.authorization import listing as authz_listing
from langflow.services.authorization.actions import FlowAction

from ._common import (
    _StubAuthorizationService,
    install_authz,
    install_settings,
)


@pytest.mark.anyio
async def test_filter_visible_resources_noop_when_disabled(monkeypatch, fake_user):
    """No batch_enforce call when AUTHZ_ENABLED=False; returns input unchanged."""
    install_settings(monkeypatch, authz_enabled=False)
    service = _StubAuthorizationService(allow=False)
    install_authz(monkeypatch, service)

    candidates = [SimpleNamespace(id=uuid4()) for _ in range(3)]
    result = await authz_listing.filter_visible_resources(
        fake_user,
        resource_type="flow",
        candidates=candidates,
    )
    assert result == candidates
    assert service.batch_calls == []


@pytest.mark.anyio
async def test_filter_visible_resources_empty_returns_empty(monkeypatch, fake_user):
    """An empty candidates list is returned unchanged without contacting the service."""
    install_settings(monkeypatch, authz_enabled=True)
    service = _StubAuthorizationService(allow=True)
    install_authz(monkeypatch, service)

    result = await authz_listing.filter_visible_resources(fake_user, resource_type="flow", candidates=[])
    assert result == []
    assert service.batch_calls == []


@pytest.mark.anyio
async def test_filter_visible_resources_filters_via_batch_enforce(monkeypatch, fake_user):
    """When AUTHZ_ENABLED=True, batch_enforce results filter the candidate list."""
    install_settings(monkeypatch, authz_enabled=True)
    candidates = [SimpleNamespace(id=uuid4()) for _ in range(3)]
    service = _StubAuthorizationService(batch_results=[True, False, True])
    install_authz(monkeypatch, service)

    result = await authz_listing.filter_visible_resources(
        fake_user,
        resource_type="flow",
        candidates=candidates,
    )

    assert result == [candidates[0], candidates[2]]
    assert service.batch_calls[0]["requests"] == [
        (f"flow:{candidates[0].id}", "read"),
        (f"flow:{candidates[1].id}", "read"),
        (f"flow:{candidates[2].id}", "read"),
    ]


@pytest.mark.anyio
async def test_filter_visible_resources_accepts_custom_key(monkeypatch, fake_user):
    """A custom key extractor lets callers filter non-id-bearing items."""
    install_settings(monkeypatch, authz_enabled=True)
    items = [{"resource_id": uuid4()}, {"resource_id": uuid4()}]
    service = _StubAuthorizationService(batch_results=[False, True])
    install_authz(monkeypatch, service)

    result = await authz_listing.filter_visible_resources(
        fake_user,
        resource_type="project",
        candidates=items,
        key=lambda r: r["resource_id"],
        act=FlowAction.WRITE,
    )

    assert result == [items[1]]
    assert service.batch_calls[0]["requests"][0][1] == "write"


@pytest.mark.anyio
async def test_filter_visible_resources_groups_by_extracted_domain(monkeypatch, fake_user):
    """With ``domain_extractor`` set, batch_enforce is called once per unique domain.

    Each call sees only the candidates that resolved to that domain, so the
    authorization plugin evaluates each candidate against the right policy tuple
    (the single-domain default would force every candidate through the same
    wildcard domain, hiding project-scoped grants).
    """
    install_settings(monkeypatch, authz_enabled=True)
    workspace_a = uuid4()
    workspace_b = uuid4()

    items = [
        SimpleNamespace(id=uuid4(), workspace_id=workspace_a, folder_id=None),
        SimpleNamespace(id=uuid4(), workspace_id=workspace_b, folder_id=None),
        SimpleNamespace(id=uuid4(), workspace_id=workspace_a, folder_id=None),
    ]

    # Deny everything in workspace_b, allow everything in workspace_a.
    class _DomainAwareStub:
        def __init__(self) -> None:
            self.batch_calls: list[dict] = []

        async def batch_enforce(self, **kwargs) -> list[bool]:
            self.batch_calls.append(kwargs)
            allowed = kwargs["domain"] != f"workspace:{workspace_b}"
            return [allowed] * len(kwargs["requests"])

    service = _DomainAwareStub()
    install_authz(monkeypatch, service)

    result = await authz_listing.filter_visible_resources(
        fake_user,
        resource_type="project",
        candidates=items,
        domain_extractor=lambda project: authz_guards._resolve_authz_domain(project.workspace_id, None),
        act=FlowAction.READ,
    )

    # Two calls — one per unique domain.
    domains_called = {call["domain"] for call in service.batch_calls}
    assert domains_called == {f"workspace:{workspace_a}", f"workspace:{workspace_b}"}

    # Output preserves the original order, with workspace_b's item dropped.
    assert result == [items[0], items[2]]


@pytest.mark.anyio
async def test_filter_visible_resources_owner_override_skips_enforcer(monkeypatch, fake_user):
    """Items owned by the caller are force-included without consulting the enforcer.

    Mirrors the owner-override short-circuit in ``_ensure_resource_permission``
    so list and direct-read agree under plugin enforcement. Without this,
    a deny-all plugin would hide the caller's own rows from the listing
    response while letting them read the same rows directly.
    """
    install_settings(monkeypatch, authz_enabled=True)
    other_user = uuid4()

    items = [
        SimpleNamespace(id=uuid4(), user_id=fake_user.id),  # owned → must keep
        SimpleNamespace(id=uuid4(), user_id=other_user),  # not owned → enforcer decides
        SimpleNamespace(id=uuid4(), user_id=fake_user.id),  # owned → must keep
    ]
    # Deny-all stub so any item that reaches the enforcer would be dropped.
    service = _StubAuthorizationService(allow=False)
    install_authz(monkeypatch, service)

    result = await authz_listing.filter_visible_resources(
        fake_user,
        resource_type="flow",
        candidates=items,
        owner_extractor=lambda item: item.user_id,
        act=FlowAction.READ,
    )

    # Owned items kept (positions 0 and 2); non-owned item dropped by deny.
    assert result == [items[0], items[2]]
    # Enforcer was consulted only for the non-owned item.
    assert len(service.batch_calls) == 1
    assert len(service.batch_calls[0]["requests"]) == 1
