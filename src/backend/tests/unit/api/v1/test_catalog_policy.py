"""Route tests for catalog-policy whole-set administration."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import anyio
import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from langflow.api.v1 import catalog_policy
from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.catalog_policy import CatalogPolicyRule
from langflow.services.policy_bundle import PolicyBundleRevisionConflictError
from lfx.services.catalog_policy import CatalogPolicySnapshot, CatalogPolicyUpdate
from lfx.services.deps import session_scope_readonly
from sqlmodel import select


class _StubCatalogPolicy:
    def __init__(self) -> None:
        self.snapshot = CatalogPolicySnapshot(
            blocked_component_keys=frozenset({"OldComponent"}),
            blocked_template_keys=frozenset({"OldTemplate"}),
        )
        self.component_calls = []
        self.template_calls = []

    @property
    def external_policy_snapshot(self):
        return None

    @property
    def supports_policy_bundle_updates(self):
        return True

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


class _ExternalCatalogPolicy(_StubCatalogPolicy):
    def __init__(self, *, external_snapshot: CatalogPolicySnapshot | None = None) -> None:
        super().__init__()
        self.snapshot = (
            external_snapshot
            if external_snapshot is not None
            else CatalogPolicySnapshot(
                blocked_component_keys={"ExternalComponent"},
                blocked_template_keys={"ExternalTemplate"},
            )
        )

    @property
    def external_policy_snapshot(self):
        return self.snapshot


class _ConflictingCatalogPolicy(_StubCatalogPolicy):
    async def replace_blocked_component_keys(self, keys, *, actor_user_id):
        _ = keys, actor_user_id
        raise PolicyBundleRevisionConflictError(expected_revision=7, active_revision=8)

    async def replace_blocked_template_keys(self, keys, *, actor_user_id):
        _ = keys, actor_user_id
        raise PolicyBundleRevisionConflictError(expected_revision=7, active_revision=8)


class _LegacyCatalogPolicy(_StubCatalogPolicy):
    @property
    def supports_policy_bundle_updates(self):
        return False


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
    assert components.json() == {"blocked": ["OldComponent"], "managed_externally": False}
    assert templates.status_code == 200
    assert templates.json() == {"blocked": ["OldTemplate"], "managed_externally": False}
    audit.assert_not_awaited()


def test_external_gets_return_the_active_external_snapshot(monkeypatch):
    client, service, _admin, audit = _client(monkeypatch, service=_ExternalCatalogPolicy())

    components = client.get("/api/v1/catalog-policy/components")
    templates = client.get("/api/v1/catalog-policy/templates")

    assert components.status_code == 200
    assert components.json() == {"blocked": ["ExternalComponent"], "managed_externally": True}
    assert templates.status_code == 200
    assert templates.json() == {"blocked": ["ExternalTemplate"], "managed_externally": True}
    assert service.external_policy_snapshot is service.snapshot
    audit.assert_not_awaited()


def test_empty_external_snapshot_still_reports_external_ownership(monkeypatch):
    client, _service, _admin, audit = _client(
        monkeypatch,
        service=_ExternalCatalogPolicy(external_snapshot=CatalogPolicySnapshot()),
    )

    components = client.get("/api/v1/catalog-policy/components")
    templates = client.get("/api/v1/catalog-policy/templates")

    assert components.status_code == 200
    assert templates.status_code == 200
    assert components.json() == {"blocked": [], "managed_externally": True}
    assert templates.json() == {"blocked": [], "managed_externally": True}
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
    assert response.json() == {"blocked": ["Alpha", "zeta"], "managed_externally": False}
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


def test_put_rejects_legacy_plugin_without_bundle_update_support(monkeypatch):
    client, service, _admin, audit = _client(monkeypatch, service=_LegacyCatalogPolicy())

    response = client.put(
        "/api/v1/catalog-policy/components",
        json={"blocked": ["NewComponent"]},
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert "does not support shared policy bundle updates" in response.json()["detail"]
    assert service.component_calls == []
    audit.assert_not_awaited()


def test_put_templates_preserves_case_and_accepts_unknown_keys(monkeypatch):
    client, service, admin, audit = _client(monkeypatch)

    response = client.put(
        "/api/v1/catalog-policy/templates",
        json={"blocked": ["Unknown-ID", "unknown-id"]},
    )

    assert response.status_code == 200
    assert response.json() == {"blocked": ["Unknown-ID", "unknown-id"], "managed_externally": False}
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


@pytest.mark.parametrize("resource_kind", ["components", "templates"])
@pytest.mark.parametrize(
    "invalid_keys",
    [
        ["x" * 256],
        [f"catalog-key-{index}" for index in range(1001)],
    ],
    ids=["key-too-long", "too-many-keys"],
)
def test_put_bounds_catalog_key_sets_without_writing_or_auditing(monkeypatch, resource_kind, invalid_keys):
    client, service, _admin, audit = _client(monkeypatch)

    response = client.put(
        f"/api/v1/catalog-policy/{resource_kind}",
        json={"blocked": invalid_keys},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert service.component_calls == []
    assert service.template_calls == []
    audit.assert_not_awaited()


@pytest.mark.parametrize("resource_kind", ["components", "templates"])
def test_concurrent_legacy_put_returns_bundle_revision_conflict(monkeypatch, resource_kind):
    client, _service, _admin, audit = _client(monkeypatch, service=_ConflictingCatalogPolicy())

    response = client.put(
        f"/api/v1/catalog-policy/{resource_kind}",
        json={"blocked": ["NewKey"]},
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {
        "detail": {
            "message": "Policy bundle revision conflict",
            "expected_revision": 7,
            "active_revision": 8,
        }
    }
    audit.assert_not_awaited()


@pytest.mark.anyio
async def test_x_api_key_puts_complete_and_persist_on_file_backed_sqlite(client, logged_in_headers_super_user):
    """API-key usage writes must not lock the policy service's separate SQLite transaction."""
    component_key = f"LE2097Component-{uuid4().hex}"
    template_key = f"LE2097Template-{uuid4().hex}"
    create_key = await client.post(
        "/api/v1/api_key/",
        headers=logged_in_headers_super_user,
        json={"name": "le-2097-sqlite-lock-regression"},
    )
    assert create_key.status_code == 200
    created_key = create_key.json()
    plaintext = created_key["api_key"]
    api_key_id = UUID(created_key["id"])

    # The login fixture sets an access-token cookie. Remove it so the policy
    # requests authenticate exclusively through the API-key path under test.
    client.cookies.clear()

    with anyio.fail_after(10):
        components = await client.put(
            "/api/v1/catalog-policy/components",
            headers={"x-api-key": plaintext},
            json={"blocked": [component_key]},
        )
    assert components.status_code == 200
    assert components.json() == {"blocked": [component_key], "managed_externally": False}

    with anyio.fail_after(10):
        templates = await client.put(
            "/api/v1/catalog-policy/templates",
            headers={"x-api-key": plaintext},
            json={"blocked": [template_key]},
        )
    assert templates.status_code == 200
    assert templates.json() == {"blocked": [template_key], "managed_externally": False}

    async with session_scope_readonly() as session:
        rows = (
            await session.exec(
                select(CatalogPolicyRule).where(CatalogPolicyRule.resource_key.in_([component_key, template_key]))
            )
        ).all()
        persisted_key = await session.get(ApiKey, api_key_id)

    assert {(row.resource_kind, row.resource_key) for row in rows} == {
        ("component", component_key),
        ("template", template_key),
    }
    assert persisted_key is not None
    assert persisted_key.total_uses == 2
    assert persisted_key.last_used_at is not None


@pytest.mark.parametrize("resource_kind", ["components", "templates"])
def test_external_policy_rejects_valid_puts_without_writing_or_auditing(monkeypatch, resource_kind):
    client, service, _admin, audit = _client(monkeypatch, service=_ExternalCatalogPolicy())

    response = client.put(
        f"/api/v1/catalog-policy/{resource_kind}",
        json={"blocked": ["ValidKey"]},
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {"detail": "Catalog policy is externally managed and cannot be changed through this API."}
    assert service.component_calls == []
    assert service.template_calls == []
    audit.assert_not_awaited()


def test_managed_marker_is_response_only():
    assert "managed_externally" not in catalog_policy.CatalogPolicyBlockedSet.model_fields
    assert "managed_externally" in catalog_policy.CatalogPolicyRead.model_fields
