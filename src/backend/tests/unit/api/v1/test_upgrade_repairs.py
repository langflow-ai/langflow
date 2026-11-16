"""Selected repairs keep ownership, recovery, and author concurrency intact."""

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, get_settings_service, session_scope
from langflow.services.flow_repair import service
from langflow.services.flow_repair.planning import data_digest
from langflow.services.flow_repair.retention import REPAIR_RETENTION_REASON
from lfx.services.settings.feature_flags import FEATURE_FLAGS
from sqlmodel import select

from tests.unit.services.flow_repair.test_planning import graph, registry

PREVIEW = "/api/v1/upgrade-repairs/preview"
APPLY = "/api/v1/upgrade-repairs/apply"


@pytest.fixture(autouse=True)
def installed_target(client, monkeypatch):  # noqa: ARG001
    async def load():
        return registry()

    monkeypatch.setattr(service, "target_registry", load)
    monkeypatch.setattr(FEATURE_FLAGS, "instance_migration", False)
    # Client startup replaces the settings service. Patch the live instance so
    # synthetic repair fixtures do not depend on the deployment's default policy.
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "allow_custom_components", True)
    monkeypatch.setattr(settings, "custom_component_admin_only", False)


@pytest.fixture
async def repair_admin(client):
    credential = str(uuid4())
    async with session_scope() as session:
        user = User(
            username=f"repair-admin-{uuid4()}",
            password=get_auth_service().get_password_hash(credential),
            is_active=True,
            is_superuser=True,
        )
        session.add(user)
        await session.flush()
        user_id = user.id
    response = await client.post("/api/v1/login", data={"username": user.username, "password": credential})
    assert response.status_code == 200
    client.cookies.clear()
    return user_id, {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _flow(owner_id, *, data=None, token=True, **kwargs):
    async with session_scope() as session:
        row = Flow(
            name=f"repair-flow-{uuid4()}",
            user_id=owner_id,
            data=data if data is not None else graph(),
            version_token=uuid4() if token else None,
            **kwargs,
        )
        session.add(row)
        await session.flush()
        return row.id


async def _read(flow_id):
    async with session_scope() as session:
        row = await session.get(Flow, flow_id)
        versions = (await session.exec(select(FlowVersion).where(FlowVersion.flow_id == flow_id))).all()
        return row.model_dump(), [entry.model_dump() for entry in versions]


async def _preview(client, headers, flow_id):
    response = await client.post(PREVIEW, json={"flow_ids": [str(flow_id)]}, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    [result] = body["results"]
    assert result["status"] == "ready", result
    return {
        "target_sha256": body["target_sha256"],
        "flows": [{key: result[key] for key in ("flow_id", "version_token", "data_sha256")}],
    }


async def _freeze(client, headers):
    response = await client.post("/api/v1/maintenance/on", json={"reason": "repair test"}, headers=headers)
    assert response.status_code == 200, response.text


async def test_repair_endpoints_require_verified_admin(client, logged_in_headers):
    client.cookies.clear()
    assert (await client.post(PREVIEW, json={"flow_ids": [str(uuid4())]})).status_code in {401, 403}
    assert (await client.post(PREVIEW, json={"flow_ids": [str(uuid4())]}, headers=logged_in_headers)).status_code == 403


@pytest.mark.parametrize("legacy_token", [False, True])
async def test_selected_cross_user_repair_preserves_owner_and_protected_recovery(
    client, active_user, logged_in_headers, repair_admin, legacy_token, monkeypatch
):
    actor_id, headers = repair_admin
    selected = await _flow(active_user.id, token=not legacy_token)
    unselected = await _flow(active_user.id)
    before, _versions = await _read(selected)
    other_before, _versions = await _read(unselected)
    payload = await _preview(client, headers, selected)
    await _freeze(client, headers)

    response = await client.post(APPLY, json=payload, headers=headers)

    assert response.status_code == 200, response.text
    [result] = response.json()["results"]
    assert result["status"] == "updated", result
    saved, versions = await _read(selected)
    assert saved["user_id"] == active_user.id
    assert saved["last_modified_by"] == actor_id
    assert saved["version_token"] is not None
    assert saved["version_token"] != before["version_token"]
    template = saved["data"]["nodes"][0]["data"]["node"]["template"]
    assert template["code"]["value"] == "target source"
    assert template["text"] == before["data"]["nodes"][0]["data"]["node"]["template"]["text"]
    [recovery] = versions
    assert recovery["data"] == before["data"]
    assert recovery["user_id"] == active_user.id
    assert recovery["retained"] is True
    assert recovery["retained_reason"] == REPAIR_RETENTION_REASON
    assert str(recovery["id"]) == result["recovery_version_id"]
    assert (await _read(unselected))[0] == other_before
    await client.post("/api/v1/maintenance/off", headers=headers)
    owner_versions = await client.get(f"/api/v1/flows/{selected}/versions/", headers=logged_in_headers)
    assert owner_versions.status_code == 200
    assert result["recovery_version_id"] in {entry["id"] for entry in owner_versions.json()["entries"]}
    monkeypatch.setattr(get_settings_service().settings, "max_flow_version_entries_per_flow", 1)
    for _ in range(3):
        snapshot = await client.post(f"/api/v1/flows/{selected}/versions/", json={}, headers=logged_in_headers)
        assert snapshot.status_code == 201
    assert any(entry["id"] == recovery["id"] for entry in (await _read(selected))[1])
    deletion = await client.delete(f"/api/v1/flows/{selected}/versions/{recovery['id']}", headers=logged_in_headers)
    assert deletion.status_code == 409


async def test_apply_requires_freeze_and_rejects_request_code(client, active_user, repair_admin):
    _actor, headers = repair_admin
    flow_id = await _flow(active_user.id)
    payload = await _preview(client, headers, flow_id)
    assert (await client.post(APPLY, json=payload, headers=headers)).status_code == 409
    await _freeze(client, headers)
    assert (await client.post(APPLY, json={**payload, "code": "request source"}, headers=headers)).status_code == 422
    assert not (await _read(flow_id))[1]


@pytest.mark.parametrize("change", ["data", "target", "token"])
async def test_stale_preview_is_refused_without_recovery(client, active_user, repair_admin, change):
    _actor, headers = repair_admin
    flow_id = await _flow(active_user.id)
    payload = await _preview(client, headers, flow_id)
    if change == "data":
        payload["flows"][0]["data_sha256"] = data_digest({"stale": "graph"})
    elif change == "token":
        payload["flows"][0]["version_token"] = str(uuid4())
    else:
        payload["target_sha256"] = data_digest({"stale": "target"})
    before, _versions = await _read(flow_id)
    await _freeze(client, headers)

    response = await client.post(APPLY, json=payload, headers=headers)

    if change == "target":
        assert response.status_code == 409
    else:
        assert response.status_code == 200
        assert response.json()["results"][0]["status"] == "conflict"
    assert (await _read(flow_id)) == (before, [])


@pytest.mark.parametrize("missing", [True, False])
async def test_stale_author_cannot_erase_repair_even_without_a_token(
    client, active_user, logged_in_headers, repair_admin, missing
):
    _actor, headers = repair_admin
    flow_id = await _flow(active_user.id, token=not missing)
    before, _versions = await _read(flow_id)
    payload = await _preview(client, headers, flow_id)
    await _freeze(client, headers)
    applied = await client.post(APPLY, json=payload, headers=headers)
    assert applied.json()["results"][0]["status"] == "updated"
    await client.post("/api/v1/maintenance/off", headers=headers)
    stale_headers = logged_in_headers if missing else {**logged_in_headers, "If-Match": str(before["version_token"])}

    stale = await client.patch(f"/api/v1/flows/{flow_id}", json={"data": before["data"]}, headers=stale_headers)

    assert stale.status_code == (428 if missing else 409), stale.text
    saved, _versions = await _read(flow_id)
    assert saved["data"] != before["data"]
    renamed = await client.patch(
        f"/api/v1/flows/{flow_id}", json={"name": f"renamed-{uuid4()}"}, headers=logged_in_headers
    )
    assert renamed.status_code == 200, renamed.text
    fresh = await client.patch(
        f"/api/v1/flows/{flow_id}",
        json={"data": before["data"]},
        headers={**logged_in_headers, "If-Match": str(saved["version_token"])},
    )
    assert fresh.status_code == 200, fresh.text


async def test_late_failure_rolls_back_graph_token_and_recovery(client, active_user, repair_admin, monkeypatch):
    _actor, headers = repair_admin
    flow_id = await _flow(active_user.id)
    payload = await _preview(client, headers, flow_id)
    before, _versions = await _read(flow_id)
    original = service.set_flow_version_retained

    async def fail_after_recovery(*args, **kwargs):
        await original(*args, **kwargs)
        msg = "injected failure after recovery creation"
        raise RuntimeError(msg)

    monkeypatch.setattr(service, "set_flow_version_retained", fail_after_recovery)
    await _freeze(client, headers)

    response = await client.post(APPLY, json=payload, headers=headers)

    assert response.status_code == 200
    assert response.json()["results"][0]["status"] == "failed"
    assert (await _read(flow_id)) == (before, [])


async def test_simultaneous_repair_commits_exactly_one_recovery(client, active_user, repair_admin):
    _actor, headers = repair_admin
    flow_id = await _flow(active_user.id)
    payload = await _preview(client, headers, flow_id)
    await _freeze(client, headers)

    responses = await asyncio.gather(*(client.post(APPLY, json=payload, headers=headers) for _ in range(3)))

    assert all(response.status_code == 200 for response in responses)
    statuses = [response.json()["results"][0]["status"] for response in responses]
    assert statuses.count("updated") == 1, statuses
    _saved, versions = await _read(flow_id)
    assert len(versions) == 1
    assert versions[0]["retained"] is True


async def test_registered_authorization_can_deny_cross_user_repair(client, active_user, repair_admin, monkeypatch):
    from langflow.services.flow_repair import policy

    _actor, headers = repair_admin
    flow_id = await _flow(active_user.id)
    payload = await _preview(client, headers, flow_id)

    async def deny(*_args, **_kwargs):
        raise HTTPException(status_code=403, detail="Denied")

    monkeypatch.setattr(policy, "ensure_flow_permission", deny)
    await _freeze(client, headers)
    before = await _read(flow_id)

    response = await client.post(APPLY, json=payload, headers=headers)

    assert response.status_code == 200
    assert response.json()["results"][0]["status"] == "forbidden"
    assert await _read(flow_id) == before


@pytest.mark.parametrize("kind", ["locked", "file", "orphan", "unsafe", "malformed"])
async def test_manual_cases_have_explicit_outcomes_and_never_write(client, active_user, repair_admin, kind):
    _actor, headers = repair_admin
    kwargs = {"locked": True} if kind == "locked" else {"fs_path": "/local/manual.json"} if kind == "file" else {}
    data = graph()
    if kind == "unsafe":
        data["nodes"][0]["data"]["node"]["template"]["removed"] = {"type": "str", "value": "keep"}
    elif kind == "malformed":
        data["nodes"][0]["data"]["node"] = None
    flow_id = await _flow(None if kind == "orphan" else active_user.id, data=data, **kwargs)
    before = await _read(flow_id)

    response = await client.post(PREVIEW, json={"flow_ids": [str(flow_id)]}, headers=headers)

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["status"] == "manual"
    assert result["reason_codes"]
    await _freeze(client, headers)
    payload = {
        "target_sha256": response.json()["target_sha256"],
        "flows": [
            {"flow_id": str(flow_id), "version_token": result["version_token"], "data_sha256": data_digest(data)}
        ],
    }
    applied = await client.post(APPLY, json=payload, headers=headers)
    assert applied.status_code == 200
    assert applied.json()["results"][0]["status"] == "manual"
    assert await _read(flow_id) == before


async def test_owner_policy_uses_owner_project_and_workspace_without_admin_privilege(
    client, active_user, repair_admin, monkeypatch
):
    from langflow.services.database.models.folder.model import Folder
    from langflow.services.flow_repair import policy
    from lfx.services.model_provider_policy import (
        ModelProviderPolicyContext,
        ModelProviderPolicySnapshot,
        current_model_provider_policy_context,
    )

    _actor_id, headers = repair_admin
    target = registry()
    target["helpers"]["Example"]["metadata"] = {"model_provider_id": "openai"}

    async def load():
        return target

    monkeypatch.setattr(service, "target_registry", load)
    workspace_id = uuid4()
    async with session_scope() as session:
        folder = Folder(name=f"owner-project-{uuid4()}", user_id=active_user.id, workspace_id=workspace_id)
        session.add(folder)
        await session.flush()
        folder_id = folder.id
    flow_id = await _flow(active_user.id, folder_id=folder_id, workspace_id=workspace_id)
    calls = []

    async def deny_provider(*, user_id, providers, purpose):
        context = current_model_provider_policy_context()
        calls.append((user_id, dict(context.attributes)))
        return ModelProviderPolicySnapshot(
            context=ModelProviderPolicyContext(user_id=user_id, attributes=context.attributes),
            purpose=purpose,
            candidate_provider_ids=frozenset(providers),
            allowed_provider_ids=frozenset(),
        )

    monkeypatch.setattr(policy, "aresolve_model_provider_policy", deny_provider)
    before = await _read(flow_id)

    response = await client.post(PREVIEW, json={"flow_ids": [str(flow_id)]}, headers=headers)

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["status"] == "manual"
    assert result["reason_codes"] == ["owner_policy_denied"]
    assert calls == [
        (
            active_user.id,
            {
                "is_superuser": False,
                "project_id": folder_id,
                "workspace_id": workspace_id,
                "provider_scope_required": True,
            },
        )
    ]
    assert await _read(flow_id) == before


async def test_file_migration_pause_still_blocks_admin_repair(client, active_user, repair_admin, monkeypatch, tmp_path):
    import json

    _actor, headers = repair_admin
    flow_id = await _flow(active_user.id)
    payload = await _preview(client, headers, flow_id)
    await _freeze(client, headers)
    before = await _read(flow_id)
    monkeypatch.setattr(FEATURE_FLAGS, "instance_migration", True)
    monkeypatch.setattr(get_settings_service().settings, "config_dir", str(tmp_path))
    (tmp_path / "migrations").mkdir()
    (tmp_path / "migrations" / "migration.json").write_text(
        json.dumps({"pause": {"frozen_at": "2026-11-04T00:00:00Z"}})
    )

    response = await client.post(APPLY, json=payload, headers=headers)

    assert response.status_code == 503
    assert await _read(flow_id) == before


@pytest.mark.parametrize("route", ["put", "activate"])
async def test_other_graph_replacement_routes_require_review_after_repair(
    client, active_user, logged_in_headers, repair_admin, route
):
    _actor, headers = repair_admin
    flow_id = await _flow(active_user.id)
    before, _versions = await _read(flow_id)
    payload = await _preview(client, headers, flow_id)
    await _freeze(client, headers)
    repaired = await client.post(APPLY, json=payload, headers=headers)
    result = repaired.json()["results"][0]
    assert result["status"] == "updated"
    await client.post("/api/v1/maintenance/off", headers=headers)
    after = await _read(flow_id)

    if route == "put":
        response = await client.put(
            f"/api/v1/flows/{flow_id}", json={"name": before["name"], "data": before["data"]}, headers=logged_in_headers
        )
    else:
        response = await client.post(
            f"/api/v1/flows/{flow_id}/versions/{result['recovery_version_id']}/activate", headers=logged_in_headers
        )

    assert response.status_code == 428, response.text
    assert await _read(flow_id) == after


async def test_null_token_cannot_bypass_protection_on_a_repaired_row(
    client, active_user, logged_in_headers, repair_admin
):
    _actor, headers = repair_admin
    flow_id = await _flow(active_user.id)
    before, _versions = await _read(flow_id)
    payload = await _preview(client, headers, flow_id)
    await _freeze(client, headers)
    response = await client.post(APPLY, json=payload, headers=headers)
    assert response.json()["results"][0]["status"] == "updated"
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        flow.version_token = None
        session.add(flow)
    await client.post("/api/v1/maintenance/off", headers=headers)
    saved = await _read(flow_id)

    response = await client.patch(f"/api/v1/flows/{flow_id}", json={"data": before["data"]}, headers=logged_in_headers)

    assert response.status_code == 428
    assert await _read(flow_id) == saved


async def _import_report(client, headers):
    content = (Path(__file__).parent / "fixtures" / "upgrade-report-v1.json").read_bytes()
    response = await client.post("/api/v1/upgrade-reports", content=content, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"], content


async def test_report_linked_repair_persists_server_outcome_and_preserves_export(client, active_user, repair_admin):
    _actor, headers = repair_admin
    flow_id = await _flow(active_user.id)
    report_id, original = await _import_report(client, headers)
    payload = {**await _preview(client, headers, flow_id), "report_id": report_id}
    await _freeze(client, headers)

    response = await client.post(APPLY, json=payload, headers=headers)

    assert response.status_code == 200, response.text
    [result] = response.json()["results"]
    assert result["status"] == "updated", result
    history = await client.get(f"/api/v1/upgrade-reports/{report_id}/repairs", headers=headers)
    assert history.status_code == 200, history.text
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["result"] == result
    [recovery] = (await _read(flow_id))[1]
    assert result["recovery_version_id"] == str(recovery["id"])
    assert recovery["user_id"] == active_user.id
    exported = await client.get(f"/api/v1/upgrade-reports/{report_id}/export", headers=headers)
    assert exported.content == original


async def test_report_outcome_failure_rolls_back_the_repair_transaction(client, active_user, repair_admin, monkeypatch):
    _actor, headers = repair_admin
    flow_id = await _flow(active_user.id)
    before = await _read(flow_id)
    report_id, original = await _import_report(client, headers)
    payload = {**await _preview(client, headers, flow_id), "report_id": report_id}
    record = service._record_result

    async def fail_after_flush(session, result, **kwargs):
        await record(session, result, **kwargs)
        if result.status == "updated":
            msg = "injected failure after report outcome flush"
            raise RuntimeError(msg)

    monkeypatch.setattr(service, "_record_result", fail_after_flush)
    await _freeze(client, headers)

    response = await client.post(APPLY, json=payload, headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["results"][0]["status"] == "failed"
    assert await _read(flow_id) == before
    history = (await client.get(f"/api/v1/upgrade-reports/{report_id}/repairs", headers=headers)).json()
    assert [row["result"]["status"] for row in history["items"]] == ["failed"]
    assert (await client.get(f"/api/v1/upgrade-reports/{report_id}/export", headers=headers)).content == original


async def test_missing_linked_report_never_changes_selected_flows(client, active_user, repair_admin):
    _actor, headers = repair_admin
    flow_id = await _flow(active_user.id)
    unknown_report = str(uuid4())
    before = await _read(flow_id)
    preview = await client.post(
        PREVIEW, json={"flow_ids": [str(flow_id)], "report_id": unknown_report}, headers=headers
    )
    assert preview.status_code == 404
    payload = {**await _preview(client, headers, flow_id), "report_id": unknown_report}
    await _freeze(client, headers)

    applied = await client.post(APPLY, json=payload, headers=headers)

    assert applied.status_code == 404
    assert await _read(flow_id) == before


@pytest.mark.parametrize("policy_kind", ["custom", "catalog"])
async def test_custom_and_catalog_policy_denials_are_not_malformed_flows(
    client, active_user, repair_admin, monkeypatch, policy_kind
):
    from lfx.utils.flow_validation import CatalogPolicyValidationError, CustomComponentValidationError

    _actor, headers = repair_admin
    flow_id = await _flow(active_user.id)
    payload = await _preview(client, headers, flow_id)
    before = await _read(flow_id)
    error_type = CatalogPolicyValidationError if policy_kind == "catalog" else CustomComponentValidationError

    async def deny(*_args, **_kwargs):
        msg = "fixture owner policy denial"
        raise error_type(msg)

    monkeypatch.setattr(service, "validate_owner_policy", deny)
    preview = await client.post(PREVIEW, json={"flow_ids": [str(flow_id)]}, headers=headers)
    assert preview.status_code == 200
    assert preview.json()["results"][0]["reason_codes"] == ["owner_policy_denied"]
    await _freeze(client, headers)
    applied = await client.post(APPLY, json=payload, headers=headers)
    assert applied.status_code == 200
    assert applied.json()["results"][0]["reason_codes"] == ["owner_policy_denied"]
    assert await _read(flow_id) == before


def _delegated_repair_fixture(kind, *, override=None, selection=None):
    from tests.unit.services.flow_repair.test_provider_selection import delegated_fixture

    saved, entries = delegated_fixture(kind, selection=selection, override=override)
    entry = entries[kind]
    entry["template"]["code"] = {"type": "code", "value": "target source"}
    entry["outputs"] = []
    info = saved["nodes"][0]["data"]["node"]
    info["template"]["code"] = {"type": "code", "value": "saved source"}
    info["outputs"] = []
    return saved, {"models": {kind: entry}}


@pytest.mark.parametrize("kind", ["LanguageModelComponent", "EmbeddingModelComponent"])
@pytest.mark.parametrize("override", [None, "Anthropic"])
@pytest.mark.parametrize("allowed", [True, False])
@pytest.mark.parametrize("nested", [False, True])
async def test_delegated_repairs_enforce_actual_owner_policy_without_hydration(
    client, active_user, repair_admin, monkeypatch, kind, override, allowed, nested
):
    from importlib.metadata import version

    from langflow.services.database.models.folder.model import Folder
    from langflow.services.flow_repair import policy
    from langflow.utils.version import get_version_info
    from lfx.base.models.unified_models import credentials
    from lfx.custom.custom_component.component import Component
    from lfx.services.model_provider_policy import (
        ModelProviderPolicyContext,
        ModelProviderPolicySnapshot,
        current_model_provider_policy_context,
    )

    actor_id, headers = repair_admin
    data, target = _delegated_repair_fixture(kind, override=override)
    if nested:
        data = {
            "nodes": [
                {
                    "id": "model-group",
                    "data": {"id": "model-group", "node": {"template": {}, "flow": {"data": data}}},
                }
            ],
            "edges": [],
        }
    workspace_id = uuid4()
    async with session_scope() as session:
        folder = Folder(name=f"delegated-owner-{uuid4()}", user_id=active_user.id, workspace_id=workspace_id)
        session.add(folder)
        await session.flush()
        folder_id = folder.id
    flow_id = await _flow(active_user.id, data=data, folder_id=folder_id, workspace_id=workspace_id)
    before = await _read(flow_id)
    report_id, _original = await _import_report(client, headers)
    calls = []

    async def load():
        return target

    async def resolve(*, user_id, providers, purpose):
        context = current_model_provider_policy_context()
        calls.append((user_id, dict(context.attributes), frozenset(providers)))
        return ModelProviderPolicySnapshot(
            context=ModelProviderPolicyContext(user_id=user_id, attributes=context.attributes),
            purpose=purpose,
            candidate_provider_ids=frozenset(providers),
            allowed_provider_ids=frozenset(providers) if allowed else frozenset(),
        )

    def no_hydration(*_args, **_kwargs):
        msg = "static repair must not construct a component or resolve credentials"
        raise AssertionError(msg)

    monkeypatch.setattr(service, "target_registry", load)
    monkeypatch.setattr(policy, "aresolve_model_provider_policy", resolve)
    monkeypatch.setattr(Component, "__init__", no_hydration)
    monkeypatch.setattr(credentials, "get_api_key_for_provider", no_hydration)
    monkeypatch.setattr(credentials, "get_all_variables_for_provider", no_hydration)
    preview = await client.post(PREVIEW, json={"flow_ids": [str(flow_id)], "report_id": report_id}, headers=headers)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["target_version"] == get_version_info()["version"]
    assert body["lfx_version"] == version("lfx")
    [result] = body["results"]
    assert result["status"] == ("ready" if allowed else "manual"), result
    await _freeze(client, headers)
    response = await client.post(
        APPLY,
        json={
            "target_sha256": body["target_sha256"],
            "report_id": report_id,
            "flows": [
                {
                    "flow_id": str(flow_id),
                    "version_token": str(before[0]["version_token"]),
                    "data_sha256": data_digest(data),
                }
            ],
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    [applied] = response.json()["results"]
    assert applied["status"] == ("updated" if allowed else "manual"), applied
    provider = "anthropic" if override else "openai"
    assert (
        calls
        == [
            (
                active_user.id,
                {
                    "is_superuser": False,
                    "project_id": folder_id,
                    "workspace_id": workspace_id,
                    "provider_scope_required": True,
                },
                frozenset({provider}),
            )
        ]
        * 2
    )
    assert active_user.id != actor_id
    if not allowed:
        assert applied["reason_codes"] == ["owner_policy_denied"]
        assert await _read(flow_id) == before
        history = (await client.get(f"/api/v1/upgrade-reports/{report_id}/repairs", headers=headers)).json()
        assert [row["result"]["status"] for row in history["items"]] == ["manual"]


@pytest.mark.parametrize("dynamic", ["unknown", "malformed", "connected", "variable", "provider_variable", "override"])
async def test_unverifiable_delegated_selection_is_explicit_and_never_writes(
    client, active_user, repair_admin, monkeypatch, dynamic
):
    from langflow.services.flow_repair import policy
    from lfx.base.models.unified_models import credentials

    _actor, headers = repair_admin
    data, target = _delegated_repair_fixture("LanguageModelComponent")
    template = data["nodes"][0]["data"]["node"]["template"]
    if dynamic == "unknown":
        template["model"]["value"] = [{"provider": "Unknown Provider", "name": "fixture"}]
    elif dynamic == "malformed":
        template["model"]["value"] = [{"provider": 123}]
    elif dynamic == "connected":
        data["edges"] = [{"target": data["nodes"][0]["id"], "data": {"targetHandle": {"fieldName": "model"}}}]
    elif dynamic == "variable":
        template["model"]["load_from_db"] = True
    elif dynamic == "provider_variable":
        template["provider"].update(value="provider-reference", load_from_db=True)
    else:
        template["provider"]["value"] = ["Anthropic"]
    flow_id = await _flow(active_user.id, data=data)
    before = await _read(flow_id)

    async def load():
        return target

    async def not_resolved(**_kwargs):
        msg = "an unverified selector cannot reach policy or credential resolution"
        raise AssertionError(msg)

    def no_credentials(*_args, **_kwargs):
        msg = "static repair cannot resolve credentials"
        raise AssertionError(msg)

    monkeypatch.setattr(service, "target_registry", load)
    monkeypatch.setattr(policy, "aresolve_model_provider_policy", not_resolved)
    monkeypatch.setattr(credentials, "get_api_key_for_provider", no_credentials)
    response = await client.post(PREVIEW, json={"flow_ids": [str(flow_id)]}, headers=headers)
    assert response.status_code == 200
    [result] = response.json()["results"]
    assert result["status"] == "manual", result
    assert result["reason_codes"] == ["provider_selection_unverifiable"]
    await _freeze(client, headers)
    applied = await client.post(
        APPLY,
        json={
            "target_sha256": response.json()["target_sha256"],
            "flows": [
                {
                    "flow_id": str(flow_id),
                    "version_token": str(before[0]["version_token"]),
                    "data_sha256": data_digest(data),
                }
            ],
        },
        headers=headers,
    )
    assert applied.status_code == 200
    assert applied.json()["results"][0]["reason_codes"] == ["provider_selection_unverifiable"]
    assert await _read(flow_id) == before
