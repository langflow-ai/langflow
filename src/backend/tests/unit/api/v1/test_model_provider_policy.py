from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI, HTTPException, status
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from langflow.api.v1 import model_provider_policy as policy_api
from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.database.models.model_provider_policy import ModelProviderPolicy
from langflow.services.model_provider_policy import ModelProviderPolicyNotInitializedError
from langflow.services.policy_bundle import (
    PolicyBundleApplicationNotSupportedError,
    PolicyBundleRevisionConflictError,
)
from lfx.services.deps import injectable_session_scope, injectable_session_scope_readonly
from lfx.services.model_provider_policy import BaseModelProviderPolicyService, ModelProviderPolicyService
from pydantic import ValidationError


class _Result:
    def __init__(self, row=None, *, rowcount: int = 1):
        self._row = row
        self.rowcount = rowcount

    def one_or_none(self):
        return self._row


class _WriteSession:
    def __init__(self) -> None:
        self.events: list[object] = []
        self._executions = 0

    async def exec(self, statement):
        self._executions += 1
        if self._executions == 1:
            assert statement.is_update
            self.events.append("atomic_update")
            return _Result(rowcount=1)
        self.events.append("read_updated_state")
        return _Result(
            SimpleNamespace(
                approved_provider_ids=["openai", "temporarily-missing.extension"],
                version=3,
            )
        )

    async def commit(self):
        self.events.append("commit")


class _ExternalModelProviderPolicy(BaseModelProviderPolicyService):
    def __init__(self, provider_ids: set[str]) -> None:
        super().__init__()
        self._provider_ids = frozenset(provider_ids)
        self.set_ready()

    @property
    def external_approved_provider_ids(self) -> frozenset[str]:
        return self._provider_ids

    def get_allowed_provider_ids(self, *, context, candidate_provider_ids, purpose):
        _ = (context, purpose)
        return candidate_provider_ids & self._provider_ids


async def _unused_session():
    yield SimpleNamespace()


def _client_with_rejected_superuser(router: APIRouter) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    def reject_superuser():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )

    app.dependency_overrides[get_current_active_superuser] = reject_superuser
    app.dependency_overrides[injectable_session_scope] = _unused_session
    app.dependency_overrides[injectable_session_scope_readonly] = _unused_session
    return TestClient(app)


def _client_with_superuser(router: APIRouter) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_active_superuser] = lambda: SimpleNamespace(
        id=uuid4(),
        is_superuser=True,
    )
    app.dependency_overrides[injectable_session_scope] = _unused_session
    app.dependency_overrides[injectable_session_scope_readonly] = _unused_session
    return TestClient(app)


def test_policy_routes_require_superuser_dependency():
    routes = [route for route in policy_api.router.routes if isinstance(route, APIRoute)]

    assert routes
    for route in routes:
        dependency_calls = [dependency.call for dependency in route.dependant.dependencies]
        assert get_current_active_superuser in dependency_calls


@pytest.mark.parametrize("method", ["get", "post", "put"])
def test_policy_routes_reject_non_superuser(method):
    client = _client_with_rejected_superuser(policy_api.router)
    request = getattr(client, method)
    kwargs = {"json": {"approved_provider_ids": ["openai"]}} if method != "get" else {}

    response = request("/model-provider-policy", **kwargs)

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_policy_write_validates_canonical_ids_and_deduplicates():
    payload = policy_api.ModelProviderPolicyWrite(
        approved_provider_ids=["temporarily-missing.extension", "OpenAI", "openai"]
    )

    assert payload.approved_provider_ids == ["openai", "temporarily-missing.extension"]
    with pytest.raises(ValidationError):
        policy_api.ModelProviderPolicyWrite(approved_provider_ids=[""])


def test_trailing_slash_aliases_are_hidden_from_openapi():
    routes = [route for route in policy_api.router.routes if isinstance(route, APIRoute)]

    assert {route.path for route in routes if route.include_in_schema} == {"/model-provider-policy"}


async def test_read_internal_policy_reports_database_state_as_unmanaged(monkeypatch):
    state = SimpleNamespace(approved_provider_ids=frozenset({"openai"}), version=4)
    read_state = AsyncMock(return_value=state)
    monkeypatch.setattr(
        policy_api, "get_model_provider_policy_service", lambda: ModelProviderPolicyService(), raising=False
    )
    monkeypatch.setattr(policy_api, "get_model_provider_policy_state", read_state)

    response = await policy_api.read_model_provider_policy(
        _admin=SimpleNamespace(id=uuid4(), is_superuser=True),
        session=SimpleNamespace(),
    )

    assert response.approved_provider_ids == ["openai"]
    assert response.managed_externally is False
    read_state.assert_awaited_once()


@pytest.mark.parametrize("external_ids", [{"anthropic", "openai"}, set()])
async def test_read_external_policy_uses_active_service_state_without_database_access(monkeypatch, external_ids):
    service = _ExternalModelProviderPolicy(external_ids)
    read_state = AsyncMock()
    monkeypatch.setattr(policy_api, "get_model_provider_policy_service", lambda: service, raising=False)
    monkeypatch.setattr(policy_api, "get_model_provider_policy_state", read_state)

    response = await policy_api.read_model_provider_policy(
        _admin=SimpleNamespace(id=uuid4(), is_superuser=True),
        session=SimpleNamespace(),
    )

    assert response.approved_provider_ids == sorted(external_ids)
    assert response.managed_externally is True
    read_state.assert_not_awaited()


@pytest.mark.parametrize("method", ["post", "put"])
def test_external_policy_rejects_valid_writes_without_side_effects(monkeypatch, method):
    service = _ExternalModelProviderPolicy({"openai"})
    invalidate = Mock(wraps=service.invalidate)
    replace_state = AsyncMock()
    audit = AsyncMock()
    apply = Mock()
    monkeypatch.setattr(service, "invalidate", invalidate)
    monkeypatch.setattr(policy_api, "get_model_provider_policy_service", lambda: service, raising=False)
    monkeypatch.setattr(policy_api, "replace_model_provider_policy_state", replace_state)
    monkeypatch.setattr(policy_api, "audit_decision", audit)
    monkeypatch.setattr(policy_api, "apply_model_provider_policy_state", apply)
    client = _client_with_superuser(policy_api.router)

    response = getattr(client, method)(
        "/model-provider-policy",
        json={"approved_provider_ids": ["openai"]},
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {
        "detail": "Model-provider policy is externally managed and cannot be changed through this API."
    }
    replace_state.assert_not_awaited()
    audit.assert_not_awaited()
    apply.assert_not_called()
    invalidate.assert_not_called()


def test_shared_write_rejects_legacy_catalog_plugin_without_side_effects(monkeypatch):
    service = ModelProviderPolicyService()
    replace_state = AsyncMock(
        side_effect=PolicyBundleApplicationNotSupportedError(
            "Configured catalog policy service does not support shared policy bundle updates"
        )
    )
    audit = AsyncMock()
    apply = Mock()
    monkeypatch.setattr(policy_api, "get_model_provider_policy_service", lambda: service, raising=False)
    monkeypatch.setattr(policy_api, "replace_model_provider_policy_state", replace_state)
    monkeypatch.setattr(policy_api, "audit_decision", audit)
    monkeypatch.setattr(policy_api, "apply_model_provider_policy_state", apply)
    client = _client_with_superuser(policy_api.router)

    response = client.put(
        "/model-provider-policy",
        json={"approved_provider_ids": ["openai"]},
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert "does not support shared policy bundle updates" in response.json()["detail"]
    replace_state.assert_awaited_once()
    audit.assert_not_awaited()
    apply.assert_not_called()


@pytest.mark.parametrize("method", ["post", "put"])
def test_shared_write_returns_structured_revision_conflict_without_side_effects(monkeypatch, method):
    service = ModelProviderPolicyService()
    replace_state = AsyncMock(
        side_effect=PolicyBundleRevisionConflictError(
            expected_revision=7,
            active_revision=8,
        )
    )
    audit = AsyncMock()
    apply = Mock()
    monkeypatch.setattr(policy_api, "get_model_provider_policy_service", lambda: service, raising=False)
    monkeypatch.setattr(policy_api, "replace_model_provider_policy_state", replace_state)
    monkeypatch.setattr(policy_api, "audit_decision", audit)
    monkeypatch.setattr(policy_api, "apply_model_provider_policy_state", apply)
    client = _client_with_superuser(policy_api.router)

    response = getattr(client, method)(
        "/model-provider-policy",
        json={"approved_provider_ids": ["openai"]},
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {
        "detail": {
            "message": "Policy bundle revision conflict",
            "expected_revision": 7,
            "active_revision": 8,
        }
    }
    replace_state.assert_awaited_once()
    audit.assert_not_awaited()
    apply.assert_not_called()


async def test_replace_policy_commits_before_runtime_invalidation(monkeypatch):
    session = _WriteSession()
    admin_id = uuid4()

    def apply(state):
        session.events.append(("apply", sorted(state.approved_provider_ids), state.version))

    async def audit(**kwargs):
        session.events.append(("audit", kwargs))

    monkeypatch.setattr(policy_api, "apply_model_provider_policy_state", apply)
    monkeypatch.setattr(policy_api, "audit_decision", audit)

    response = await policy_api.replace_model_provider_policy(
        policy_api.ModelProviderPolicyWrite(approved_provider_ids=["openai", "temporarily-missing.extension"]),
        admin=SimpleNamespace(id=admin_id, is_superuser=True),
        session=session,
    )

    assert session.events == [
        "atomic_update",
        "read_updated_state",
        "commit",
        (
            "audit",
            {
                "user_id": admin_id,
                "action": "model_provider_policy:replace",
                "obj": "model_provider_policy:1",
                "result": "allow",
                "details": {
                    "approved_provider_ids": ["openai", "temporarily-missing.extension"],
                    "version": 3,
                },
            },
        ),
        ("apply", ["openai", "temporarily-missing.extension"], 3),
    ]
    assert response.approved_provider_ids == ["openai", "temporarily-missing.extension"]
    assert response.managed_externally is False
    assert any(provider.provider_id == "openai" for provider in response.registered_providers)


async def test_replace_policy_audits_committed_state_when_runtime_apply_fails(monkeypatch):
    session = _WriteSession()
    admin_id = uuid4()

    async def audit(**kwargs):
        session.events.append(("audit", kwargs["details"]["version"]))

    def apply(state):
        session.events.append(("apply", state.version))
        msg = "runtime invalidation failed"
        raise RuntimeError(msg)

    monkeypatch.setattr(policy_api, "audit_decision", audit)
    monkeypatch.setattr(policy_api, "apply_model_provider_policy_state", apply)

    with pytest.raises(RuntimeError, match="runtime invalidation failed"):
        await policy_api.replace_model_provider_policy(
            policy_api.ModelProviderPolicyWrite(approved_provider_ids=["openai"]),
            admin=SimpleNamespace(id=admin_id, is_superuser=True),
            session=session,
        )

    assert session.events == [
        "atomic_update",
        "read_updated_state",
        "commit",
        ("audit", 3),
        ("apply", 3),
    ]


async def test_replace_policy_applies_committed_state_when_audit_enqueue_fails(monkeypatch):
    session = _WriteSession()

    async def audit(**_kwargs):
        session.events.append("audit")
        msg = "audit enqueue failed"
        raise RuntimeError(msg)

    def apply(state):
        session.events.append(("apply", state.version))

    monkeypatch.setattr(policy_api, "audit_decision", audit)
    monkeypatch.setattr(policy_api, "apply_model_provider_policy_state", apply)

    with pytest.raises(RuntimeError, match="audit enqueue failed"):
        await policy_api.replace_model_provider_policy(
            policy_api.ModelProviderPolicyWrite(approved_provider_ids=["openai"]),
            admin=SimpleNamespace(id=uuid4(), is_superuser=True),
            session=session,
        )

    assert session.events == [
        "atomic_update",
        "read_updated_state",
        "commit",
        "audit",
        ("apply", 3),
    ]


@pytest.mark.parametrize("operation", ["read", "replace"])
async def test_missing_policy_singleton_returns_actionable_service_unavailable(monkeypatch, operation):
    async def missing(*_args, **_kwargs):
        msg = "singleton missing"
        raise ModelProviderPolicyNotInitializedError(msg)

    if operation == "read":
        monkeypatch.setattr(policy_api, "get_model_provider_policy_state", missing)
        call = policy_api.read_model_provider_policy(
            _admin=SimpleNamespace(id=uuid4(), is_superuser=True),
            session=SimpleNamespace(),
        )
    else:
        monkeypatch.setattr(policy_api, "replace_model_provider_policy_state", missing)
        call = policy_api.replace_model_provider_policy(
            policy_api.ModelProviderPolicyWrite(approved_provider_ids=["openai"]),
            admin=SimpleNamespace(id=uuid4(), is_superuser=True),
            session=SimpleNamespace(),
        )

    with pytest.raises(HTTPException) as exc_info:
        await call

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "migrations" in exc_info.value.detail


def test_model_provider_policy_model_is_a_global_versioned_singleton():
    table = ModelProviderPolicy.__table__

    assert table.name == "model_provider_policy"
    assert [column.name for column in table.primary_key.columns] == ["id"]
    column_names = set(table.columns.keys())
    assert {"approved_provider_ids", "version"}.issubset(column_names)
    assert {"user_id", "workspace_id", "organization_id", "tenant_id"}.isdisjoint(column_names)
