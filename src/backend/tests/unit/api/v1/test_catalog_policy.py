"""Route tests for catalog-policy whole-set administration."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from langflow.api.v1 import catalog_policy
from langflow.services.auth.utils import get_current_active_superuser
from lfx.services.catalog_policy import CatalogPolicySnapshot, CatalogPolicyUpdate


class _StubCatalogPolicy:
    def __init__(self) -> None:
        self.snapshot = CatalogPolicySnapshot(
            blocked_component_keys=frozenset({"OldComponent"}),
            blocked_template_keys=frozenset({"OldTemplate"}),
        )
        self.component_calls = []
        self.template_calls = []

    async def replace_blocked_component_keys(self, keys, *, actor_user_id):
        desired = frozenset(keys)
        current = self.snapshot.blocked_component_keys
        self.component_calls.append((list(keys), actor_user_id))
        self.snapshot = CatalogPolicySnapshot(
            blocked_component_keys=desired,
            blocked_template_keys=self.snapshot.blocked_template_keys,
        )
        return CatalogPolicyUpdate(
            snapshot=self.snapshot,
            added=desired - current,
            removed=current - desired,
        )

    async def replace_blocked_template_keys(self, keys, *, actor_user_id):
        desired = frozenset(keys)
        current = self.snapshot.blocked_template_keys
        self.template_calls.append((list(keys), actor_user_id))
        self.snapshot = CatalogPolicySnapshot(
            blocked_component_keys=self.snapshot.blocked_component_keys,
            blocked_template_keys=desired,
        )
        return CatalogPolicyUpdate(
            snapshot=self.snapshot,
            added=desired - current,
            removed=current - desired,
        )


def _client(monkeypatch, *, service=None, superuser=True):
    stub = service or _StubCatalogPolicy()
    app = FastAPI()
    app.include_router(catalog_policy.router, prefix="/api/v1")

    if superuser:
        admin = SimpleNamespace(id=uuid4(), is_superuser=True)
        app.dependency_overrides[get_current_active_superuser] = lambda: admin
    else:
        admin = None

        def reject_non_superuser():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The user doesn't have enough privileges",
            )

        app.dependency_overrides[get_current_active_superuser] = reject_non_superuser

    monkeypatch.setattr(catalog_policy, "get_catalog_policy_service", lambda: stub)
    audit = AsyncMock()
    monkeypatch.setattr(catalog_policy, "audit_decision", audit)
    return TestClient(app), stub, admin, audit


def test_get_whole_sets_are_sorted_and_superuser_only(monkeypatch):
    client, _service, _admin, audit = _client(monkeypatch)

    components = client.get("/api/v1/catalog-policy/components")
    templates = client.get("/api/v1/catalog-policy/templates")

    assert components.status_code == 200
    assert components.json() == {"blocked": ["OldComponent"]}
    assert templates.status_code == 200
    assert templates.json() == {"blocked": ["OldTemplate"]}
    audit.assert_not_awaited()


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/catalog-policy/components"),
        ("put", "/api/v1/catalog-policy/components"),
        ("get", "/api/v1/catalog-policy/templates"),
        ("put", "/api/v1/catalog-policy/templates"),
    ],
)
def test_all_routes_require_superuser(monkeypatch, method, path):
    client, service, _admin, audit = _client(monkeypatch, superuser=False)

    response = client.put(path, json={"blocked": []}) if method == "put" else client.get(path)

    assert response.status_code == 403
    assert service.component_calls == []
    assert service.template_calls == []
    audit.assert_not_awaited()


def test_put_components_normalizes_whole_set_and_audits_each_delta(monkeypatch):
    client, service, admin, audit = _client(monkeypatch)

    response = client.put(
        "/api/v1/catalog-policy/components",
        json={"blocked": [" zeta ", "Alpha", "Alpha"]},
    )

    assert response.status_code == 200
    assert response.json() == {"blocked": ["Alpha", "zeta"]}
    assert service.component_calls == [(["Alpha", "zeta"], admin.id)]
    assert [call.kwargs for call in audit.await_args_list] == [
        {
            "user_id": admin.id,
            "action": "catalog:block",
            "obj": "component:Alpha",
            "result": "allow",
            "details": {"resource_kind": "component", "resource_key": "Alpha"},
        },
        {
            "user_id": admin.id,
            "action": "catalog:block",
            "obj": "component:zeta",
            "result": "allow",
            "details": {"resource_kind": "component", "resource_key": "zeta"},
        },
        {
            "user_id": admin.id,
            "action": "catalog:unblock",
            "obj": "component:OldComponent",
            "result": "allow",
            "details": {"resource_kind": "component", "resource_key": "OldComponent"},
        },
    ]


def test_put_templates_preserves_case_and_accepts_unknown_keys(monkeypatch):
    client, service, admin, audit = _client(monkeypatch)

    response = client.put(
        "/api/v1/catalog-policy/templates",
        json={"blocked": ["Unknown-ID", "unknown-id"]},
    )

    assert response.status_code == 200
    assert response.json() == {"blocked": ["Unknown-ID", "unknown-id"]}
    assert service.template_calls == [(["Unknown-ID", "unknown-id"], admin.id)]
    assert audit.await_count == 3


def test_put_rejects_empty_keys_without_writing_or_auditing(monkeypatch):
    client, service, _admin, audit = _client(monkeypatch)

    response = client.put(
        "/api/v1/catalog-policy/components",
        json={"blocked": ["valid", "   "]},
    )

    assert response.status_code == 422
    assert service.component_calls == []
    audit.assert_not_awaited()


def test_put_requires_explicit_whole_set_without_writing_or_auditing(monkeypatch):
    client, service, _admin, audit = _client(monkeypatch)

    response = client.put("/api/v1/catalog-policy/components", json={})

    assert response.status_code == 422
    assert service.component_calls == []
    audit.assert_not_awaited()
