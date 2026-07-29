from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import APIRouter, FastAPI, HTTPException, status
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from langflow.api.v1 import model_provider_policy as policy_api
from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.database.models.model_provider_policy import ModelProviderPolicy
from lfx.services.deps import injectable_session_scope, injectable_session_scope_readonly
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
        approved_provider_ids=["temporarily-missing.extension", "openai", "openai"]
    )

    assert payload.approved_provider_ids == ["openai", "temporarily-missing.extension"]
    with pytest.raises(ValidationError):
        policy_api.ModelProviderPolicyWrite(approved_provider_ids=["OpenAI"])


async def test_replace_policy_commits_before_runtime_invalidation(monkeypatch):
    session = _WriteSession()

    def apply(state):
        session.events.append(("apply", sorted(state.approved_provider_ids), state.version))

    monkeypatch.setattr(policy_api, "apply_model_provider_policy_state", apply)

    response = await policy_api.replace_model_provider_policy(
        policy_api.ModelProviderPolicyWrite(approved_provider_ids=["openai", "temporarily-missing.extension"]),
        _admin=SimpleNamespace(is_superuser=True),
        session=session,
    )

    assert session.events == [
        "atomic_update",
        "read_updated_state",
        "commit",
        ("apply", ["openai", "temporarily-missing.extension"], 3),
    ]
    assert response.approved_provider_ids == ["openai", "temporarily-missing.extension"]
    assert any(provider.provider_id == "openai" for provider in response.registered_providers)


def test_model_provider_policy_model_is_a_global_versioned_singleton():
    table = ModelProviderPolicy.__table__

    assert table.name == "model_provider_policy"
    assert [column.name for column in table.primary_key.columns] == ["id"]
    column_names = set(table.columns.keys())
    assert {"approved_provider_ids", "version"}.issubset(column_names)
    assert {"user_id", "workspace_id", "organization_id", "tenant_id"}.isdisjoint(column_names)
