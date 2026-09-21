from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from fastapi import HTTPException
from httpx import AsyncClient
from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import session_scope


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


async def test_replacement_operation_replays_and_gets_committed_snapshot(
    client: AsyncClient, active_user, logged_in_headers: dict[str, str]
):
    project = await _create_project(active_user)
    project_id = project["id"]
    operation_id = str(uuid4())
    body = {
        "description": "first replacement",
        "flows": [_flow_payload(flow_id=uuid4(), name=f"flow-{uuid4().hex[:8]}")],
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

    changed_body = {**body, "description": "different request"}
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


async def test_restore_creates_project_and_receipt_survives_project_deletion(
    client: AsyncClient, active_user, logged_in_headers: dict[str, str], monkeypatch
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
            _flow_payload(
                flow_id=UUID(first_flow["id"]), name=first_flow["name"], endpoint_name="endpoint_two"
            ),
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
            raise RuntimeError("injected trigger reconciliation failure")

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
