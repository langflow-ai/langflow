"""Contract tests for superuser administration of the shared policy bundle."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from langflow.api.v1 import policy_bundle as policy_api
from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.policy_bundle import (
    PolicyBundleApplicationNotSupportedError,
    PolicyBundleRevisionConflictError,
)
from lfx.services.deps import injectable_session_scope, injectable_session_scope_readonly
from lfx.services.policy_bundle import PolicyBundleSnapshot


async def _unused_session():
    yield SimpleNamespace()


def _client(monkeypatch, *, superuser: bool = True):
    app = FastAPI()
    app.include_router(policy_api.router, prefix="/api/v1")
    admin = SimpleNamespace(id=uuid4(), is_superuser=True)

    if superuser:
        app.dependency_overrides[get_current_active_superuser] = lambda: admin
    else:

        def reject_non_superuser():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The user doesn't have enough privileges",
            )

        app.dependency_overrides[get_current_active_superuser] = reject_non_superuser

    app.dependency_overrides[injectable_session_scope] = _unused_session
    app.dependency_overrides[injectable_session_scope_readonly] = _unused_session
    read_state = AsyncMock()
    replace_state = AsyncMock()
    list_history = AsyncMock()
    rollback_state = AsyncMock()
    apply_state = Mock()
    monkeypatch.setattr(policy_api, "get_policy_bundle_state", read_state)
    monkeypatch.setattr(policy_api, "replace_policy_bundle_state", replace_state)
    monkeypatch.setattr(policy_api, "list_policy_bundle_history", list_history)
    monkeypatch.setattr(policy_api, "rollback_policy_bundle_state", rollback_state)
    monkeypatch.setattr(policy_api, "apply_policy_bundle_state", apply_state)
    monkeypatch.setattr(policy_api, "_managed_externally", lambda: False)
    monkeypatch.setattr(policy_api, "ensure_policy_bundle_application_supported", lambda: None)
    monkeypatch.setattr(policy_api, "audit_decision", AsyncMock())
    return TestClient(app), admin, read_state, replace_state, list_history, rollback_state, apply_state


def _snapshot(*, revision: int, actor_id=None, reason: str | None = None) -> PolicyBundleSnapshot:
    return PolicyBundleSnapshot(
        revision=revision,
        initialized=True,
        source="api",
        approved_provider_ids={"openai", "anthropic"},
        blocked_component_keys={"ZetaComponent", "AlphaComponent"},
        blocked_template_keys={"template-z", "template-a"},
        blocked_model_keys={"openai::gpt-blocked", "anthropic::claude-blocked"},
        content_hash=f"{revision:064x}",
        created_at=datetime(2026, 8, 5, 12, 30, tzinfo=timezone.utc),
        created_by=actor_id,
        reason=reason,
        rollback_of_revision=None,
    )


def test_router_exposes_only_the_shared_bundle_administration_contract():
    routes = [route for route in policy_api.router.routes if isinstance(route, APIRoute)]
    schema_routes = [route for route in routes if route.include_in_schema]

    assert {(route.path, frozenset(route.methods)) for route in schema_routes} == {
        ("/policy-bundle", frozenset({"GET"})),
        ("/policy-bundle", frozenset({"PUT"})),
        ("/policy-bundle/history", frozenset({"GET"})),
        ("/policy-bundle/rollback/{revision}", frozenset({"POST"})),
    }
    for route in routes:
        dependency_calls = [dependency.call for dependency in route.dependant.dependencies]
        assert get_current_active_superuser in dependency_calls


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/policy-bundle"),
        ("put", "/api/v1/policy-bundle"),
        ("get", "/api/v1/policy-bundle/history"),
        ("post", "/api/v1/policy-bundle/rollback/1"),
    ],
)
def test_policy_bundle_routes_reject_non_superusers_without_database_access(monkeypatch, method, path):
    client, _admin, read_state, replace_state, list_history, rollback_state, apply_state = _client(
        monkeypatch, superuser=False
    )
    payload = {
        "expected_revision": 1,
        "approved_provider_ids": [],
        "blocked_component_keys": [],
        "blocked_template_keys": [],
    }

    response = getattr(client, method)(path, **({"json": payload} if method in {"put", "post"} else {}))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    read_state.assert_not_awaited()
    replace_state.assert_not_awaited()
    list_history.assert_not_awaited()
    rollback_state.assert_not_awaited()
    apply_state.assert_not_called()


def test_get_returns_the_complete_active_bundle_with_stable_sorted_lists(monkeypatch):
    client, admin, read_state, replace_state, list_history, rollback_state, apply_state = _client(monkeypatch)
    active = _snapshot(revision=4, actor_id=admin.id, reason="approved rollout")
    read_state.return_value = active

    response = client.get("/api/v1/policy-bundle")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "revision": 4,
        "initialized": True,
        "source": "api",
        "approved_provider_ids": ["anthropic", "openai"],
        "blocked_component_keys": ["AlphaComponent", "ZetaComponent"],
        "blocked_template_keys": ["template-a", "template-z"],
        "blocked_model_keys": ["anthropic::claude-blocked", "openai::gpt-blocked"],
        "content_hash": f"{4:064x}",
        "created_by": str(admin.id),
        "created_at": "2026-08-05T12:30:00Z",
        "reason": "approved rollout",
        "rollback_of_revision": None,
        "managed_externally": False,
    }
    read_state.assert_awaited_once_with(ANY)
    replace_state.assert_not_awaited()
    list_history.assert_not_awaited()
    rollback_state.assert_not_awaited()
    apply_state.assert_not_called()


def test_put_forwards_one_complete_cas_replacement_and_publishes_committed_snapshot(monkeypatch):
    client, admin, read_state, replace_state, _list_history, _rollback_state, apply_state = _client(monkeypatch)
    committed = _snapshot(revision=8, actor_id=admin.id, reason="quarterly policy refresh")
    replace_state.return_value = committed
    payload = {
        "expected_revision": 7,
        "approved_provider_ids": ["anthropic", "openai"],
        "blocked_component_keys": ["AlphaComponent", "ZetaComponent"],
        "blocked_template_keys": ["template-a", "template-z"],
        "blocked_model_keys": ["OpenAI::gpt-blocked", "openai::gpt-blocked", "claude-blocked"],
        "reason": "quarterly policy refresh",
    }

    response = client.put("/api/v1/policy-bundle", json=payload)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["revision"] == 8
    assert response.json()["reason"] == "quarterly policy refresh"
    replace_state.assert_awaited_once_with(
        ANY,
        expected_revision=7,
        approved_provider_ids=["anthropic", "openai"],
        blocked_component_keys=["AlphaComponent", "ZetaComponent"],
        blocked_template_keys=["template-a", "template-z"],
        blocked_model_keys=["claude-blocked", "openai::gpt-blocked"],
        actor_user_id=admin.id,
        reason="quarterly policy refresh",
    )
    apply_state.assert_called_once_with(committed)
    read_state.assert_not_awaited()


def test_put_without_model_keys_blocks_no_models_for_legacy_writers(monkeypatch):
    client, admin, _read_state, replace_state, _list_history, _rollback_state, apply_state = _client(monkeypatch)
    committed = _snapshot(revision=8, actor_id=admin.id)
    replace_state.return_value = committed

    response = client.put(
        "/api/v1/policy-bundle",
        json={
            "expected_revision": 7,
            "approved_provider_ids": ["openai"],
            "blocked_component_keys": [],
            "blocked_template_keys": [],
        },
    )

    assert response.status_code == status.HTTP_200_OK
    replace_state.assert_awaited_once_with(
        ANY,
        expected_revision=7,
        approved_provider_ids=["openai"],
        blocked_component_keys=[],
        blocked_template_keys=[],
        blocked_model_keys=[],
        actor_user_id=admin.id,
        reason=None,
    )
    apply_state.assert_called_once_with(committed)


@pytest.mark.parametrize(
    "invalid_keys",
    [
        ["::claude-blocked"],
        ["OpenAI::"],
        ["   "],
        ["x" * 256],
        [f"provider::model-{index}" for index in range(1001)],
    ],
    ids=["empty-provider", "empty-model", "blank", "key-too-long", "too-many-keys"],
)
def test_put_rejects_malformed_model_keys_without_writing(monkeypatch, invalid_keys):
    client, _admin, _read_state, replace_state, _list_history, _rollback_state, apply_state = _client(monkeypatch)

    response = client.put(
        "/api/v1/policy-bundle",
        json={
            "expected_revision": 1,
            "approved_provider_ids": [],
            "blocked_component_keys": [],
            "blocked_template_keys": [],
            "blocked_model_keys": invalid_keys,
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    replace_state.assert_not_awaited()
    apply_state.assert_not_called()


def test_put_maps_stale_expected_revision_to_conflict_without_runtime_publication(monkeypatch):
    client, _admin, _read_state, replace_state, _list_history, _rollback_state, apply_state = _client(monkeypatch)
    replace_state.side_effect = PolicyBundleRevisionConflictError(
        expected_revision=3,
        active_revision=4,
    )

    response = client.put(
        "/api/v1/policy-bundle",
        json={
            "expected_revision": 3,
            "approved_provider_ids": ["openai"],
            "blocked_component_keys": [],
            "blocked_template_keys": [],
        },
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == {
        "message": "Policy bundle revision conflict",
        "expected_revision": 3,
        "active_revision": 4,
    }
    apply_state.assert_not_called()


def test_put_rejects_legacy_catalog_plugin_before_database_write(monkeypatch):
    client, _admin, _read_state, replace_state, _list_history, _rollback_state, apply_state = _client(monkeypatch)

    def reject_legacy_plugin():
        msg = "Configured catalog policy service does not support shared policy bundle updates"
        raise PolicyBundleApplicationNotSupportedError(msg)

    monkeypatch.setattr(policy_api, "ensure_policy_bundle_application_supported", reject_legacy_plugin)
    response = client.put(
        "/api/v1/policy-bundle",
        json={
            "expected_revision": 3,
            "approved_provider_ids": ["openai"],
            "blocked_component_keys": [],
            "blocked_template_keys": [],
        },
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert "does not support shared policy bundle updates" in response.json()["detail"]
    replace_state.assert_not_awaited()
    apply_state.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "expected_revision": 1,
            "approved_provider_ids": [],
            "blocked_component_keys": [],
        },
        {
            "expected_revision": None,
            "approved_provider_ids": [],
            "blocked_component_keys": [],
            "blocked_template_keys": [],
        },
        {
            "expected_revision": 1,
            "approved_provider_ids": "openai",
            "blocked_component_keys": [],
            "blocked_template_keys": [],
        },
        {
            "expected_revision": 1,
            "approved_provider_ids": [],
            "blocked_component_keys": None,
            "blocked_template_keys": [],
        },
    ],
)
def test_put_requires_expected_revision_and_all_three_lists(monkeypatch, payload):
    client, _admin, _read_state, replace_state, _list_history, _rollback_state, apply_state = _client(monkeypatch)

    response = client.put("/api/v1/policy-bundle", json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    replace_state.assert_not_awaited()
    apply_state.assert_not_called()


@pytest.mark.parametrize("field_name", ["blocked_component_keys", "blocked_template_keys"])
@pytest.mark.parametrize(
    "invalid_keys",
    [
        ["x" * 256],
        [f"catalog-key-{index}" for index in range(1001)],
    ],
    ids=["key-too-long", "too-many-keys"],
)
def test_put_bounds_each_catalog_key_set_without_writing(monkeypatch, field_name, invalid_keys):
    client, _admin, _read_state, replace_state, _list_history, _rollback_state, apply_state = _client(monkeypatch)
    payload = {
        "expected_revision": 1,
        "approved_provider_ids": [],
        "blocked_component_keys": [],
        "blocked_template_keys": [],
    }
    payload[field_name] = invalid_keys

    response = client.put("/api/v1/policy-bundle", json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    replace_state.assert_not_awaited()
    policy_api.audit_decision.assert_not_awaited()
    apply_state.assert_not_called()


def test_history_is_newest_first_and_forwards_pagination(monkeypatch):
    client, admin, read_state, replace_state, list_history, rollback_state, apply_state = _client(monkeypatch)
    list_history.return_value = [
        _snapshot(revision=4, actor_id=admin.id, reason="current"),
        _snapshot(revision=3, actor_id=admin.id, reason="previous"),
    ]

    response = client.get("/api/v1/policy-bundle/history?limit=2&before_revision=5")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert [item["revision"] for item in body["items"]] == [4, 3]
    assert all(item["initialized"] is True for item in body["items"])
    assert all(item["source"] == "api" for item in body["items"])
    assert body["next_before_revision"] == 3
    list_history.assert_awaited_once_with(ANY, limit=2, before_revision=5)
    read_state.assert_not_awaited()
    replace_state.assert_not_awaited()
    rollback_state.assert_not_awaited()
    apply_state.assert_not_called()


def test_rollback_endpoint_creates_and_publishes_a_new_revision(monkeypatch):
    client, admin, read_state, replace_state, list_history, rollback_state, apply_state = _client(monkeypatch)
    rolled_back = replace(
        _snapshot(revision=9, actor_id=admin.id, reason="incident rollback"),
        source="rollback",
        rollback_of_revision=3,
    )
    rollback_state.return_value = rolled_back

    response = client.post(
        "/api/v1/policy-bundle/rollback/3",
        json={"expected_revision": 8, "reason": "incident rollback"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["revision"] == 9
    assert response.json()["source"] == "rollback"
    assert response.json()["rollback_of_revision"] == 3
    rollback_state.assert_awaited_once_with(
        ANY,
        expected_revision=8,
        target_revision=3,
        actor_user_id=admin.id,
        reason="incident rollback",
    )
    apply_state.assert_called_once_with(rolled_back)
    read_state.assert_not_awaited()
    replace_state.assert_not_awaited()
    list_history.assert_not_awaited()


def test_rollback_maps_stale_revision_to_conflict_without_audit_or_publication(monkeypatch):
    client, _admin, read_state, replace_state, list_history, rollback_state, apply_state = _client(monkeypatch)
    rollback_state.side_effect = PolicyBundleRevisionConflictError(
        expected_revision=8,
        active_revision=9,
    )

    response = client.post(
        "/api/v1/policy-bundle/rollback/3",
        json={"expected_revision": 8, "reason": "incident rollback"},
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {
        "detail": {
            "message": "Policy bundle revision conflict",
            "expected_revision": 8,
            "active_revision": 9,
        }
    }
    rollback_state.assert_awaited_once()
    policy_api.audit_decision.assert_not_awaited()
    apply_state.assert_not_called()
    read_state.assert_not_awaited()
    replace_state.assert_not_awaited()
    list_history.assert_not_awaited()
