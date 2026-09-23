from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from langflow.api.v1 import projects as projects_module
from langflow.api.v1.schemas.replacement_operations import ProjectReplacementRequest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.project_replacement_operation import ProjectReplacementOperation
from langflow.services.deps import session_scope
from psycopg.errors import DeadlockDetected
from sqlalchemy.exc import OperationalError
from sqlmodel import select


def _flow_payload(*, flow_id: UUID | None = None, name: str, endpoint_name: str | None = None) -> dict:
    payload = {
        "name": name,
        "description": f"description for {name}",
        "data": {"nodes": [], "edges": []},
    }
    if flow_id is not None:
        payload["id"] = str(flow_id)
    if endpoint_name is not None:
        payload["endpoint_name"] = endpoint_name
    return payload


async def _create_project(active_user, name: str | None = None) -> dict:
    project_name = name or f"t194-{uuid4().hex[:16]}"
    async with session_scope() as session:
        project = Folder(name=project_name, description="original description", user_id=active_user.id)
        session.add(project)
        await session.flush()
        return {"id": str(project.id), "name": project.name, "description": project.description}


async def _create_flow(active_user, project_id: str, flow_payload: dict) -> dict:
    flow_id = UUID(flow_payload["id"]) if flow_payload.get("id") else uuid4()
    async with session_scope() as session:
        flow = Flow(
            id=flow_id,
            name=flow_payload["name"],
            description=flow_payload["description"],
            data=flow_payload["data"],
            endpoint_name=flow_payload.get("endpoint_name"),
            fs_path=flow_payload.get("fs_path"),
            user_id=active_user.id,
            folder_id=UUID(project_id),
        )
        session.add(flow)
        await session.flush()
        return {
            "id": str(flow.id),
            "name": flow.name,
            "endpoint_name": flow.endpoint_name,
            "description": flow.description,
            "data": flow.data,
            "fs_path": flow.fs_path,
        }


def test_replacement_digest_preserves_legacy_no_dependency_shape() -> None:
    base = ProjectReplacementRequest(description="digest", flows=[])
    empty = ProjectReplacementRequest(description="digest", flows=[], dependencies={})
    with_dependency = ProjectReplacementRequest(
        description="digest",
        flows=[],
        dependencies={"knowledgeBases": [{"name": "kb"}]},
    )

    assert projects_module._replacement_request_digest(base) == projects_module._replacement_request_digest(empty)
    assert projects_module._replacement_request_digest(base) != projects_module._replacement_request_digest(
        with_dependency
    )


async def test_replacement_deadlock_retry_uses_original_request_body(monkeypatch):
    request_body = ProjectReplacementRequest(
        description="retry me",
        flows=[_flow_payload(flow_id=uuid4(), name="retry-flow")],
    )
    expected_data = request_body.flows[0].data.copy()
    calls = 0

    async def replace_once(**kwargs):
        nonlocal calls
        calls += 1
        flow_data = kwargs["request_body"].flows[0].data
        if calls == 1:
            flow_data["attempt_only"] = True
            statement = "UPDATE flow"
            deadlock_message = "simulated deadlock"
            driver_error = DeadlockDetected(deadlock_message)
            raise OperationalError(statement, None, driver_error)
        assert flow_data == expected_data
        return "committed"

    session = MagicMock()
    session.__contains__.return_value = False
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    monkeypatch.setattr(projects_module, "_replace_project_operation_once", replace_once)
    monkeypatch.setattr(projects_module.asyncio, "sleep", AsyncMock())

    result = await projects_module.replace_project_operation(
        session=session,
        project_id=uuid4(),
        operation_id=uuid4(),
        request_body=request_body,
        current_user=SimpleNamespace(id=uuid4()),
        storage_service=MagicMock(),
    )

    assert result == "committed"
    assert calls == 2
    assert request_body.flows[0].data == expected_data
    session.rollback.assert_awaited_once()


async def test_replacement_deadlock_retry_exhaustion_is_generic_503(monkeypatch):
    async def always_deadlock(**_kwargs):
        statement = "private SQL details"
        deadlock_message = "private database detail"
        driver_error = DeadlockDetected(deadlock_message)
        raise OperationalError(statement, None, driver_error)

    session = MagicMock()
    session.__contains__.return_value = False
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    monkeypatch.setattr(projects_module, "_replace_project_operation_once", always_deadlock)
    monkeypatch.setattr(projects_module.asyncio, "sleep", AsyncMock())

    with pytest.raises(HTTPException) as raised:
        await projects_module.replace_project_operation(
            session=session,
            project_id=uuid4(),
            operation_id=uuid4(),
            request_body=ProjectReplacementRequest(description="retry", flows=[]),
            current_user=SimpleNamespace(id=uuid4()),
            storage_service=MagicMock(),
        )

    assert raised.value.status_code == 503
    assert raised.value.detail == "The database is busy. Please retry the request."
    assert "private" not in str(raised.value.detail)
    assert session.rollback.await_count == projects_module._REPLACEMENT_MAX_ATTEMPTS


async def test_wrapped_cascade_deadlock_retries_replacement_from_clean_transaction(
    client: AsyncClient,
    active_user,
    logged_in_headers: dict[str, str],
    monkeypatch,
):
    project = await _create_project(active_user)
    project_id = project["id"]
    stale_flow = await _create_flow(active_user, project_id, _flow_payload(name=f"stale-{uuid4().hex[:8]}"))
    operation_id = str(uuid4())
    url = f"api/v1/projects/{project_id}/replacement-operations/{operation_id}"
    body = {"description": "committed after retry", "flows": []}
    original_cascade_delete_flow = projects_module.cascade_delete_flow
    cascade_calls = 0

    async def raise_wrapped_deadlock_once(*args, **kwargs):
        nonlocal cascade_calls
        cascade_calls += 1
        if cascade_calls == 1:
            statement = "DELETE FROM flow"
            deadlock_message = "simulated cascade deadlock"
            driver_error = DeadlockDetected(deadlock_message)
            database_error = OperationalError(statement, None, driver_error)
            wrapper_message = "cascade helper failed"
            raise RuntimeError(wrapper_message) from database_error
        return await original_cascade_delete_flow(*args, **kwargs)

    monkeypatch.setattr(projects_module, "cascade_delete_flow", raise_wrapped_deadlock_once)

    replaced = await client.put(url, json=body, headers=logged_in_headers)
    assert replaced.status_code == 200, replaced.text
    assert cascade_calls == 2
    assert replaced.json()["project"]["description"] == body["description"]
    assert replaced.json()["flows"] == []

    async with session_scope() as session:
        stored_project = await session.get(Folder, UUID(project_id))
        stored_flow = await session.get(Flow, UUID(stale_flow["id"]))
        receipts = list(
            (
                await session.exec(
                    select(ProjectReplacementOperation).where(
                        ProjectReplacementOperation.project_id == UUID(project_id),
                        ProjectReplacementOperation.operation_id == UUID(operation_id),
                    )
                )
            ).all()
        )
        assert stored_project.description == body["description"]
        assert stored_flow is None
        assert len(receipts) == 1
        expected_receipt = replaced.json()
        expected_receipt.pop("dependencies", None)
        assert receipts[0].result == expected_receipt

    replay = await client.put(url, json=body, headers=logged_in_headers)
    receipt = await client.get(url, headers=logged_in_headers)
    assert replay.status_code == 200, replay.text
    assert receipt.status_code == 200, receipt.text
    assert replay.json() == replaced.json()
    assert receipt.json() == replaced.json()


async def test_replacement_operation_replays_and_gets_committed_snapshot(
    client: AsyncClient, active_user, logged_in_headers: dict[str, str]
):
    project = await _create_project(active_user)
    project_id = project["id"]
    operation_id = str(uuid4())
    body = {
        "description": "first replacement",
        "flows": [_flow_payload(flow_id=uuid4(), name=f"flow-{uuid4().hex[:8]}")],
        "dependencies": {
            "knowledgeBases": [{"name": "shared-kb", "backendType": "postgres"}],
            "memoryBases": [],
        },
    }
    url = f"api/v1/projects/{project_id}/replacement-operations/{operation_id}"

    first = await client.put(url, json=body, headers=logged_in_headers)
    replay = await client.put(url, json=body, headers=logged_in_headers)

    assert first.status_code == 200, first.text
    assert replay.status_code == 200, replay.text
    assert first.json() == replay.json()
    assert first.json()["project"]["description"] == "first replacement"
    assert first.json()["project"]["auth_settings"] is None
    assert len(first.json()["flows"]) == 1
    assert first.json()["dependencies"] == body["dependencies"]

    changed_body = {
        **body,
        "dependencies": {
            "knowledgeBases": [{"name": "different-kb", "backendType": "postgres"}],
            "memoryBases": [],
        },
    }
    conflict = await client.put(url, json=changed_body, headers=logged_in_headers)
    assert conflict.status_code == 409

    next_operation = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{uuid4()}",
        json={"description": "later replacement", "flows": []},
        headers=logged_in_headers,
    )
    assert next_operation.status_code == 200, next_operation.text

    receipt = await client.get(url, headers=logged_in_headers)
    assert receipt.status_code == 200, receipt.text
    assert receipt.json() == first.json()

    missing = await client.get(
        f"api/v1/projects/{project_id}/replacement-operations/{uuid4()}",
        headers=logged_in_headers,
    )
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Replacement operation not found"


async def test_replacement_receipt_without_dependency_snapshot_remains_readable(
    client: AsyncClient, active_user, logged_in_headers: dict[str, str]
):
    project = await _create_project(active_user)
    project_id = project["id"]
    operation_id = str(uuid4())
    url = f"api/v1/projects/{project_id}/replacement-operations/{operation_id}"
    body = {
        "description": "historical replacement",
        "flows": [_flow_payload(flow_id=uuid4(), name=f"legacy-{uuid4().hex[:8]}")],
    }

    created = await client.put(url, json=body, headers=logged_in_headers)
    assert created.status_code == 200, created.text

    async with session_scope() as session:
        receipt = await session.get(ProjectReplacementOperation, (UUID(project_id), UUID(operation_id)))
        assert receipt is not None
        assert "dependencies" not in receipt.result
        receipt.result = {key: value for key, value in receipt.result.items() if key != "dependencies"}
        session.add(receipt)
        await session.commit()

    replay = await client.put(url, json=body, headers=logged_in_headers)
    recovered = await client.get(url, headers=logged_in_headers)

    assert replay.status_code == 200, replay.text
    assert recovered.status_code == 200, recovered.text
    assert replay.json()["project"] == created.json()["project"]
    assert recovered.json()["project"] == created.json()["project"]
    assert replay.json().get("dependencies") is None
    assert recovered.json().get("dependencies") is None


async def test_restore_creates_project_and_receipt_survives_project_deletion(
    client: AsyncClient, logged_in_headers: dict[str, str], monkeypatch
):
    from langflow.api.v1 import projects as projects_module

    monkeypatch.setattr(
        projects_module,
        "get_settings_service",
        lambda: SimpleNamespace(
            settings=SimpleNamespace(add_projects_to_mcp_servers=False),
            auth_settings=SimpleNamespace(AUTO_LOGIN=True),
        ),
    )
    project_id = str(uuid4())
    operation_id = str(uuid4())
    url = f"api/v1/projects/{project_id}/replacement-operations/{operation_id}"
    body = {"project_name": f"restore-{uuid4().hex[:16]}", "description": "restored", "flows": []}

    created = await client.put(url, json=body, headers=logged_in_headers)
    replay = await client.put(url, json=body, headers=logged_in_headers)

    assert created.status_code == 200, created.text
    assert replay.status_code == 200, replay.text
    assert replay.json() == created.json()
    assert created.json()["project"]["id"] == project_id
    assert created.json()["project"]["name"] == body["project_name"]
    assert created.json()["flows"] == []

    deleted = await client.delete(f"api/v1/projects/{project_id}", headers=logged_in_headers)
    assert deleted.status_code == 204, deleted.text

    receipt = await client.get(url, headers=logged_in_headers)
    assert receipt.status_code == 200, receipt.text
    assert receipt.json() == created.json()


async def test_replacement_receipts_are_owner_only_before_and_after_project_deletion(
    client: AsyncClient,
    active_user,
    logged_in_headers: dict[str, str],
    user_two_api_key: str,
):
    project = await _create_project(active_user)
    project_id = project["id"]
    operation_id = str(uuid4())
    url = f"api/v1/projects/{project_id}/replacement-operations/{operation_id}"
    body = {"description": "owner receipt", "flows": []}
    changed_body = {"description": "different digest", "flows": []}

    created = await client.put(url, json=body, headers=logged_in_headers)
    assert created.status_code == 200, created.text

    # Use an API key tied to the second DB user and remove the owner's login
    # cookie so every cross-user request has an unambiguous principal.
    client.cookies.clear()
    other_headers = {"x-api-key": user_two_api_key}

    async def assert_not_found_for_other_user() -> None:
        read = await client.get(url, headers=other_headers)
        same_digest_replay = await client.put(url, json=body, headers=other_headers)
        different_digest_replay = await client.put(url, json=changed_body, headers=other_headers)
        assert read.status_code == 404
        assert same_digest_replay.status_code == 404
        assert different_digest_replay.status_code == 404

    await assert_not_found_for_other_user()

    owner_receipt = await client.get(url, headers=logged_in_headers)
    assert owner_receipt.status_code == 200, owner_receipt.text
    assert owner_receipt.json() == created.json()

    deleted = await client.delete(f"api/v1/projects/{project_id}", headers=logged_in_headers)
    assert deleted.status_code == 204, deleted.text

    await assert_not_found_for_other_user()

    owner_receipt_after_delete = await client.get(url, headers=logged_in_headers)
    assert owner_receipt_after_delete.status_code == 200, owner_receipt_after_delete.text
    assert owner_receipt_after_delete.json() == created.json()


async def test_replacement_can_explicitly_clear_nullable_flow_fields_and_replay_receipt(
    client: AsyncClient,
    active_user,
    logged_in_headers: dict[str, str],
):
    project = await _create_project(active_user)
    project_id = project["id"]
    flow = await _create_flow(active_user, project_id, _flow_payload(name=f"clear-{uuid4().hex[:8]}"))
    operation_id = str(uuid4())
    url = f"api/v1/projects/{project_id}/replacement-operations/{operation_id}"
    body = {
        "description": "clear nullable flow fields",
        "flows": [
            {
                "id": flow["id"],
                "name": flow["name"],
                "description": None,
                "data": None,
            }
        ],
    }

    replaced = await client.put(url, json=body, headers=logged_in_headers)
    assert replaced.status_code == 200, replaced.text
    replaced_flow = replaced.json()["flows"][0]
    assert replaced_flow["description"] is None
    assert replaced_flow["data"] is None

    async with session_scope() as session:
        stored_flow = await session.get(Flow, UUID(flow["id"]))
        assert stored_flow.description is None
        assert stored_flow.data is None

    replay = await client.put(url, json=body, headers=logged_in_headers)
    receipt = await client.get(url, headers=logged_in_headers)
    assert replay.status_code == 200, replay.text
    assert receipt.status_code == 200, receipt.text
    assert replay.json() == replaced.json()
    assert receipt.json() == replaced.json()


async def test_restore_refuses_a_project_that_already_reappeared(
    client: AsyncClient, active_user, logged_in_headers: dict[str, str]
):
    project_id = uuid4()
    project_name = f"restore-{uuid4().hex[:16]}"
    flow_id = uuid4()
    async with session_scope() as session:
        project = Folder(
            id=project_id,
            name=project_name,
            description="external recreation",
            user_id=active_user.id,
        )
        flow = Flow(
            id=flow_id,
            name="keep-me",
            description="untouched",
            data={"nodes": [{"id": "unchanged"}], "edges": []},
            user_id=active_user.id,
            folder_id=project_id,
        )
        session.add(project)
        session.add(flow)
        await session.flush()

    operation_id = uuid4()
    url = f"api/v1/projects/{project_id}/replacement-operations/{operation_id}"
    body = {
        "project_name": project_name,
        "description": "restore must not replace the recreated project",
        "flows": [],
    }

    refused = await client.put(url, json=body, headers=logged_in_headers)

    assert refused.status_code == 409
    assert refused.json()["detail"] == "Project already exists"
    async with session_scope() as session:
        stored_project = await session.get(Folder, project_id)
        stored_flow = await session.get(Flow, flow_id)
        assert stored_project.description == "external recreation"
        assert stored_flow.description == "untouched"
        assert stored_flow.data == {"nodes": [{"id": "unchanged"}], "edges": []}
    assert (await client.get(url, headers=logged_in_headers)).status_code == 404


async def test_invalid_deployment_project_name_is_hidden_without_mutation(
    client: AsyncClient, active_user, logged_in_headers: dict[str, str]
):
    project = await _create_project(active_user, name=f"Ordinary Project {uuid4().hex[:6]}")
    project_id = project["id"]
    existing_flow = await _create_flow(
        active_user,
        project_id,
        _flow_payload(name=f"existing-{uuid4().hex[:8]}", endpoint_name="existing_endpoint"),
    )
    response = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{uuid4()}",
        json={"description": "must not commit", "flows": []},
        headers=logged_in_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"

    unchanged = await client.get(f"api/v1/projects/{project_id}", headers=logged_in_headers)
    assert unchanged.status_code == 200
    project_read = unchanged.json().get("folder", unchanged.json())
    assert project_read["description"] == "original description"
    assert [flow["id"] for flow in unchanged.json().get("flows", [])] == [existing_flow["id"]]


async def test_replacement_preserves_omitted_endpoint(client: AsyncClient, active_user, logged_in_headers):
    project = await _create_project(active_user)
    project_id = project["id"]
    first_flow = await _create_flow(
        active_user,
        project_id,
        _flow_payload(name=f"first-{uuid4().hex[:8]}", endpoint_name="endpoint_one"),
    )

    response = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{uuid4()}",
        json={
            "description": "endpoint omitted",
            "flows": [_flow_payload(flow_id=UUID(first_flow["id"]), name=first_flow["name"])],
        },
        headers=logged_in_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["flows"][0]["endpoint_name"] == "endpoint_one"


async def test_replacement_allows_endpoint_swaps(client: AsyncClient, active_user, logged_in_headers):
    project = await _create_project(active_user)
    project_id = project["id"]
    first_flow = await _create_flow(
        active_user,
        project_id,
        _flow_payload(name=f"first-{uuid4().hex[:8]}", endpoint_name="endpoint_one"),
    )
    second_flow = await _create_flow(
        active_user,
        project_id,
        _flow_payload(name=f"second-{uuid4().hex[:8]}", endpoint_name="endpoint_two"),
    )

    body = {
        "description": "endpoints updated",
        "flows": [
            _flow_payload(flow_id=UUID(first_flow["id"]), name=first_flow["name"], endpoint_name="endpoint_two"),
            _flow_payload(
                flow_id=UUID(second_flow["id"]),
                name=second_flow["name"],
                endpoint_name="endpoint_one",
            ),
        ],
    }
    response = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{uuid4()}",
        json=body,
        headers=logged_in_headers,
    )

    assert response.status_code == 200, response.text
    by_id = {flow["id"]: flow for flow in response.json()["flows"]}
    assert by_id[first_flow["id"]]["endpoint_name"] == "endpoint_two"
    assert by_id[second_flow["id"]]["endpoint_name"] == "endpoint_one"


async def test_replacement_rolls_back_everything_when_second_trigger_reconcile_fails(
    client: AsyncClient, active_user, logged_in_headers, monkeypatch
):
    from langflow.api.v1 import projects as projects_module

    project = await _create_project(active_user)
    project_id = project["id"]
    live_flows = [
        await _create_flow(
            active_user,
            project_id,
            {
                **_flow_payload(name=f"live-{index}-{uuid4().hex[:8]}", endpoint_name=f"live_endpoint_{index}"),
                "data": {"nodes": [], "edges": [], "marker": f"original-{index}"},
            },
        )
        for index in range(3)
    ]
    request_flows = []
    for index, live_flow in enumerate(live_flows[:2]):
        request_flows.append(
            {
                **_flow_payload(
                    flow_id=UUID(live_flow["id"]),
                    name=f"requested-{index}-{uuid4().hex[:8]}",
                    endpoint_name=f"requested_endpoint_{index}",
                ),
                "data": {"nodes": [], "edges": [], "marker": f"target-{index}"},
            }
        )

    calls = 0

    async def fail_on_second_reconcile(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            failure_message = "injected trigger reconciliation failure"
            raise RuntimeError(failure_message)

    monkeypatch.setattr(projects_module, "reconcile_flow_triggers", fail_on_second_reconcile)
    operation_id = str(uuid4())
    response = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{operation_id}",
        json={"description": "editor target", "flows": request_flows},
        headers=logged_in_headers,
    )

    assert response.status_code == 500
    assert calls == 2
    async with session_scope() as session:
        stored_project = await session.get(Folder, UUID(project_id))
        stored_flows = list((await session.exec(select(Flow).where(Flow.folder_id == UUID(project_id)))).all())
        assert stored_project.description == "original description"
        assert {flow.id for flow in stored_flows} == {UUID(flow["id"]) for flow in live_flows}
        by_id = {str(flow.id): flow for flow in stored_flows}
        for original_flow in live_flows:
            stored_flow = by_id[original_flow["id"]]
            assert stored_flow.name == original_flow["name"]
            assert stored_flow.endpoint_name == original_flow["endpoint_name"]
            assert stored_flow.data == original_flow["data"]

    missing_receipt = await client.get(
        f"api/v1/projects/{project_id}/replacement-operations/{operation_id}", headers=logged_in_headers
    )
    assert missing_receipt.status_code == 404
    assert missing_receipt.json()["detail"] == "Replacement operation not found"


async def test_replacement_rejects_filesystem_flows_without_mutation(
    client: AsyncClient, active_user, logged_in_headers
):
    project = await _create_project(active_user)
    project_id = project["id"]
    flow = await _create_flow(
        active_user,
        project_id,
        {**_flow_payload(name=f"fs-{uuid4().hex[:8]}"), "fs_path": "flow-files/legacy.json"},
    )

    response = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{uuid4()}",
        json={"description": "must not commit", "flows": []},
        headers=logged_in_headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Atomic replacement does not support filesystem-backed flows"
    async with session_scope() as session:
        stored_project = await session.get(Folder, UUID(project_id))
        stored_flow = await session.get(Flow, UUID(flow["id"]))
        assert stored_project.description == "original description"
        assert stored_flow.fs_path == "flow-files/legacy.json"


async def test_project_authorization_denial_leaves_replacement_content_unchanged(
    client: AsyncClient, active_user, logged_in_headers, monkeypatch
):
    from langflow.api.v1 import projects as projects_module

    project = await _create_project(active_user)
    project_id = project["id"]
    flow = await _create_flow(active_user, project_id, _flow_payload(name=f"auth-{uuid4().hex[:8]}"))
    monkeypatch.setattr(
        projects_module,
        "ensure_project_permission",
        AsyncMock(side_effect=HTTPException(status_code=403, detail="denied")),
    )
    operation_id = str(uuid4())

    response = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{operation_id}",
        json={"description": "must not commit", "flows": []},
        headers=logged_in_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"
    async with session_scope() as session:
        stored_project = await session.get(Folder, UUID(project_id))
        stored_flow = await session.get(Flow, UUID(flow["id"]))
        assert stored_project.description == "original description"
        assert stored_flow is not None
    receipt = await client.get(
        f"api/v1/projects/{project_id}/replacement-operations/{operation_id}", headers=logged_in_headers
    )
    assert receipt.status_code == 404
