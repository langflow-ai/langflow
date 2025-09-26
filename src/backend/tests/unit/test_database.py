import json
from typing import NamedTuple
from uuid import UUID, uuid4

import orjson
import pytest
from httpx import AsyncClient
from langflow.api.v1.schemas import FlowListCreate, ResultDataResponse
from langflow.initial_setup.setup import load_starter_projects
from langflow.services.database.models.base import orjson_dumps
from langflow.services.database.models.flow import Flow, FlowCreate, FlowUpdate
from langflow.services.database.models.folder.model import FolderCreate
from langflow.services.database.utils import session_getter
from langflow.services.deps import get_db_service
from lfx.graph.utils import log_transaction, log_vertex_build
from sqlalchemy import text


@pytest.fixture(scope="module")
def json_style():
    # class FlowStyleBase(SQLModel):
    # color: str = Field(index=True)
    # emoji: str = Field(index=False)
    # flow_id: UUID = Field(default=None, foreign_key="flow.id")
    return orjson_dumps(
        {
            "color": "red",
            "emoji": "👍",
        }
    )


@pytest.mark.usefixtures("active_user")
async def test_create_flow(client: AsyncClient, json_flow: str, logged_in_headers):
    flow = orjson.loads(json_flow)
    data = flow["data"]
    flow = FlowCreate(name=str(uuid4()), description="description", data=data)
    response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201
    assert response.json()["name"] == flow.name
    assert response.json()["data"] == flow.data
    # flow is optional so we can create a flow without a flow
    flow = FlowCreate(name=str(uuid4()))
    response = await client.post("api/v1/flows/", json=flow.model_dump(exclude_unset=True), headers=logged_in_headers)
    assert response.status_code == 201
    assert response.json()["name"] == flow.name
    assert response.json()["data"] == flow.data


@pytest.mark.usefixtures("active_user")
async def test_read_flows(client: AsyncClient, json_flow: str, logged_in_headers):
    flow_data = orjson.loads(json_flow)
    data = flow_data["data"]
    flow = FlowCreate(name=str(uuid4()), description="description", data=data)
    response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201
    assert response.json()["name"] == flow.name
    assert response.json()["data"] == flow.data

    flow = FlowCreate(name=str(uuid4()), description="description", data=data)
    response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201
    assert response.json()["name"] == flow.name
    assert response.json()["data"] == flow.data

    response = await client.get("api/v1/flows/", headers=logged_in_headers)
    assert response.status_code == 200
    assert len(response.json()) > 0


async def test_read_flows_pagination_with_params(client: AsyncClient, logged_in_headers):
    response = await client.get(
        "api/v1/flows/", headers=logged_in_headers, params={"page": 3, "size": 10, "get_all": False}
    )
    assert response.status_code == 200
    assert response.json()["page"] == 3
    assert response.json()["size"] == 10
    assert response.json()["pages"] == 0
    assert response.json()["total"] == 0
    assert len(response.json()["items"]) == 0


async def test_read_flows_pagination_with_flows(client: AsyncClient, logged_in_headers):
    number_of_flows = 30
    flows = [FlowCreate(name=f"Flow {i}", description="description", data={}) for i in range(number_of_flows)]
    flow_ids = []
    for flow in flows:
        response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert response.status_code == 201
        flow_ids.append(response.json()["id"])

    response = await client.get(
        "api/v1/flows/", headers=logged_in_headers, params={"page": 3, "size": 10, "get_all": False}
    )
    assert response.status_code == 200
    assert response.json()["page"] == 3
    assert response.json()["size"] == 10
    assert response.json()["pages"] == 3
    assert response.json()["total"] == number_of_flows
    assert len(response.json()["items"]) == 10

    response = await client.get(
        "api/v1/flows/", headers=logged_in_headers, params={"page": 4, "size": 10, "get_all": False}
    )
    assert response.status_code == 200
    assert response.json()["page"] == 4
    assert response.json()["size"] == 10
    assert response.json()["pages"] == 3
    assert response.json()["total"] == number_of_flows
    assert len(response.json()["items"]) == 0


async def test_read_flows_custom_page_size(client: AsyncClient, logged_in_headers):
    number_of_flows = 30
    flows = [FlowCreate(name=f"Flow {i}", description="description", data={}) for i in range(number_of_flows)]
    for flow in flows:
        response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert response.status_code == 201

    response = await client.get(
        "api/v1/flows/", headers=logged_in_headers, params={"page": 1, "size": 15, "get_all": False}
    )
    assert response.status_code == 200
    assert response.json()["page"] == 1
    assert response.json()["size"] == 15
    assert response.json()["pages"] == 2
    assert response.json()["total"] == number_of_flows
    assert len(response.json()["items"]) == 15


async def test_read_flows_invalid_page(client: AsyncClient, logged_in_headers):
    number_of_flows = 30
    flows = [FlowCreate(name=f"Flow {i}", description="description", data={}) for i in range(number_of_flows)]
    flow_ids = []
    for flow in flows:
        response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert response.status_code == 201
        flow_ids.append(response.json()["id"])

    response = await client.get(
        "api/v1/flows/", headers=logged_in_headers, params={"page": 0, "size": 10, "get_all": False}
    )
    assert response.status_code == 422  # Assuming 422 is the status code for invalid input


async def test_read_flows_invalid_size(client: AsyncClient, logged_in_headers):
    number_of_flows = 30
    flows = [FlowCreate(name=f"Flow {i}", description="description", data={}) for i in range(number_of_flows)]
    flow_ids = []
    for flow in flows:
        response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert response.status_code == 201
        flow_ids.append(response.json()["id"])

    response = await client.get(
        "api/v1/flows/", headers=logged_in_headers, params={"page": 1, "size": 0, "get_all": False}
    )
    assert response.status_code == 422  # Assuming 422 is the status code for invalid input


async def test_read_flows_no_pagination_params(client: AsyncClient, logged_in_headers):
    number_of_flows = 30
    flows = [FlowCreate(name=f"Flow {i}", description="description", data={}) for i in range(number_of_flows)]
    for flow in flows:
        response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert response.status_code == 201

    response = await client.get("api/v1/flows/", headers=logged_in_headers, params={"get_all": False})
    assert response.status_code == 200
    # Assert default pagination values, adjust these according to your API's default behavior
    assert response.json()["page"] == 1
    assert response.json()["size"] == 50
    assert response.json()["pages"] == 1
    assert response.json()["total"] == number_of_flows
    assert len(response.json()["items"]) == number_of_flows


async def test_read_flows_components_only_paginated(client: AsyncClient, logged_in_headers):
    number_of_flows = 10
    flows = [
        FlowCreate(name=f"Flow {i}", description="description", data={}, is_component=True)
        for i in range(number_of_flows)
    ]

    for flow in flows:
        response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert response.status_code == 201

    response = await client.get(
        "api/v1/flows/", headers=logged_in_headers, params={"components_only": True, "get_all": False}
    )

    assert response.status_code == 200
    response_json = response.json()
    assert response_json["total"] == 10
    assert response_json["pages"] == 1
    assert response_json["page"] == 1
    assert response_json["size"] == 50
    assert all(flow["is_component"] is True for flow in response_json["items"])


async def test_read_flows_components_only(client: AsyncClient, logged_in_headers):
    number_of_flows = 10
    flows = [
        FlowCreate(name=f"Flow {i}", description="description", data={}, is_component=True)
        for i in range(number_of_flows)
    ]
    for flow in flows:
        response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert response.status_code == 201
    response = await client.get("api/v1/flows/", headers=logged_in_headers, params={"components_only": True})
    assert response.status_code == 200
    response_json = response.json()
    assert all(flow["is_component"] is True for flow in response_json)


async def test_read_flow(client: AsyncClient, json_flow: str, logged_in_headers):
    flow = orjson.loads(json_flow)
    data = flow["data"]
    unique_name = str(uuid4())
    flow = FlowCreate(name=unique_name, description="description", data=data)
    response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
    flow_id = response.json()["id"]  # flow_id should be a UUID but is a string
    # turn it into a UUID
    flow_id = UUID(flow_id)

    response = await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert response.status_code == 200
    assert response.json()["name"] == flow.name
    assert response.json()["data"] == flow.data


@pytest.mark.usefixtures("active_user")
async def test_update_flow(client: AsyncClient, json_flow: str, logged_in_headers):
    flow = orjson.loads(json_flow)
    data = flow["data"]

    flow = FlowCreate(name="Test Flow", description="description", data=data)
    response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)

    flow_id = response.json()["id"]
    updated_flow = FlowUpdate(
        name="Updated Flow",
        description="updated description",
        data=data,
    )
    response = await client.patch(f"api/v1/flows/{flow_id}", json=updated_flow.model_dump(), headers=logged_in_headers)

    assert response.status_code == 200
    assert response.json()["name"] == updated_flow.name
    assert response.json()["description"] == updated_flow.description
    # assert response.json()["data"] == updated_flow.data


@pytest.mark.usefixtures("active_user")
async def test_delete_flow(client: AsyncClient, json_flow: str, logged_in_headers):
    flow = orjson.loads(json_flow)
    data = flow["data"]
    flow = FlowCreate(name="Test Flow", description="description", data=data)
    response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
    flow_id = response.json()["id"]
    response = await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Flow deleted successfully"


@pytest.mark.usefixtures("active_user")
async def test_delete_flows(client: AsyncClient, logged_in_headers):
    # Create ten flows
    number_of_flows = 10
    flows = [FlowCreate(name=f"Flow {i}", description="description", data={}) for i in range(number_of_flows)]
    flow_ids = []
    for flow in flows:
        response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert response.status_code == 201
        flow_ids.append(response.json()["id"])

    response = await client.request("DELETE", "api/v1/flows/", headers=logged_in_headers, json=flow_ids)
    assert response.status_code == 200, response.content
    assert response.json().get("deleted") == number_of_flows


@pytest.mark.usefixtures("active_user")
async def test_delete_flows_with_transaction_and_build(client: AsyncClient, logged_in_headers):
    # Create ten flows
    number_of_flows = 10
    flows = [FlowCreate(name=f"Flow {i}", description="description", data={}) for i in range(number_of_flows)]
    flow_ids = []
    for flow in flows:
        response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert response.status_code == 201
        flow_ids.append(response.json()["id"])

    class VertexTuple(NamedTuple):
        id: str

    # Create a transaction for each flow
    for flow_id in flow_ids:
        await log_transaction(
            str(flow_id), source=VertexTuple(id="vid"), target=VertexTuple(id="tid"), status="success"
        )

    # Create a build for each flow
    for flow_id in flow_ids:
        build = {
            "valid": True,
            "params": {},
            "data": ResultDataResponse(),
            "artifacts": {},
            "vertex_id": "vid",
            "flow_id": flow_id,
        }
        await log_vertex_build(
            flow_id=build["flow_id"],
            vertex_id=build["vertex_id"],
            valid=build["valid"],
            params=build["params"],
            data=build["data"],
            artifacts=build.get("artifacts"),
        )

    response = await client.request("DELETE", "api/v1/flows/", headers=logged_in_headers, json=flow_ids)
    assert response.status_code == 200, response.content
    assert response.json().get("deleted") == number_of_flows

    for flow_id in flow_ids:
        response = await client.request(
            "GET", "api/v1/monitor/transactions", params={"flow_id": flow_id}, headers=logged_in_headers
        )
        assert response.status_code == 200
        json_response = response.json()
        assert json_response["items"] == []

    for flow_id in flow_ids:
        response = await client.request(
            "GET", "api/v1/monitor/builds", params={"flow_id": flow_id}, headers=logged_in_headers
        )
        assert response.status_code == 200
        assert response.json() == {"vertex_builds": {}}


@pytest.mark.usefixtures("active_user")
async def test_delete_folder_with_flows_with_transaction_and_build(client: AsyncClient, logged_in_headers):
    # Create a new project
    folder_name = f"Test Project {uuid4()}"
    project = FolderCreate(name=folder_name, description="Test project description", components_list=[], flows_list=[])

    response = await client.post("api/v1/projects/", json=project.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201, f"Expected status code 201, but got {response.status_code}"

    created_folder = response.json()
    folder_id = created_folder["id"]

    # Create ten flows
    number_of_flows = 10
    flows = [FlowCreate(name=f"Flow {i}", description="description", data={}) for i in range(number_of_flows)]
    flow_ids = []
    for flow in flows:
        flow.folder_id = folder_id
        response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
        assert response.status_code == 201
        flow_ids.append(response.json()["id"])

    class VertexTuple(NamedTuple):
        id: str
        params: dict

    # Create a transaction for each flow
    for flow_id in flow_ids:
        await log_transaction(
            str(flow_id),
            source=VertexTuple(id="vid", params={}),
            target=VertexTuple(id="tid", params={}),
            status="success",
        )

    # Create a build for each flow
    for flow_id in flow_ids:
        build = {
            "valid": True,
            "params": {},
            "data": ResultDataResponse(),
            "artifacts": {},
            "vertex_id": "vid",
            "flow_id": flow_id,
        }
        await log_vertex_build(
            flow_id=build["flow_id"],
            vertex_id=build["vertex_id"],
            valid=build["valid"],
            params=build["params"],
            data=build["data"],
            artifacts=build.get("artifacts"),
        )

    response = await client.request("DELETE", f"api/v1/projects/{folder_id}", headers=logged_in_headers)
    assert response.status_code == 204

    for flow_id in flow_ids:
        response = await client.request(
            "GET", "api/v1/monitor/transactions", params={"flow_id": flow_id}, headers=logged_in_headers
        )
        assert response.status_code == 200, response.json()
        json_response = response.json()
        assert json_response["items"] == []

    for flow_id in flow_ids:
        response = await client.request(
            "GET", "api/v1/monitor/builds", params={"flow_id": flow_id}, headers=logged_in_headers
        )
        assert response.status_code == 200
        assert response.json() == {"vertex_builds": {}}


async def test_get_flows_from_folder_pagination(client: AsyncClient, logged_in_headers):
    # Create a new project
    folder_name = f"Test Project {uuid4()}"
    project = FolderCreate(name=folder_name, description="Test project description", components_list=[], flows_list=[])

    response = await client.post("api/v1/projects/", json=project.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201, f"Expected status code 201, but got {response.status_code}"

    created_folder = response.json()
    folder_id = created_folder["id"]

    response = await client.get(
        f"api/v1/projects/{folder_id}", headers=logged_in_headers, params={"page": 1, "size": 50}
    )
    assert response.status_code == 200
    assert response.json()["folder"]["name"] == folder_name
    assert response.json()["folder"]["description"] == "Test project description"
    assert response.json()["flows"]["page"] == 1
    assert response.json()["flows"]["size"] == 50
    assert response.json()["flows"]["pages"] == 0
    assert response.json()["flows"]["total"] == 0
    assert len(response.json()["flows"]["items"]) == 0


async def test_get_flows_from_folder_pagination_with_params(client: AsyncClient, logged_in_headers):
    # Create a new project
    folder_name = f"Test Project {uuid4()}"
    project = FolderCreate(name=folder_name, description="Test project description", components_list=[], flows_list=[])

    response = await client.post("api/v1/projects/", json=project.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201, f"Expected status code 201, but got {response.status_code}"

    created_folder = response.json()
    folder_id = created_folder["id"]

    response = await client.get(
        f"api/v1/projects/{folder_id}", headers=logged_in_headers, params={"page": 3, "size": 10}
    )
    assert response.status_code == 200
    assert response.json()["folder"]["name"] == folder_name
    assert response.json()["folder"]["description"] == "Test project description"
    assert response.json()["flows"]["page"] == 3
    assert response.json()["flows"]["size"] == 10
    assert response.json()["flows"]["pages"] == 0
    assert response.json()["flows"]["total"] == 0
    assert len(response.json()["flows"]["items"]) == 0


@pytest.mark.usefixtures("session")
async def test_create_flows(client: AsyncClient, json_flow: str, logged_in_headers):
    flow = orjson.loads(json_flow)
    data = flow["data"]
    # Create test data
    flow_unique_name = str(uuid4())
    flow_2_unique_name = str(uuid4())
    flow_list = FlowListCreate(
        flows=[
            FlowCreate(name=flow_unique_name, description="description", data=data),
            FlowCreate(name=flow_2_unique_name, description="description", data=data),
        ]
    )
    # Make request to endpoint
    response = await client.post("api/v1/flows/batch/", json=flow_list.dict(), headers=logged_in_headers)
    # Check response status code
    assert response.status_code == 201
    # Check response data
    response_data = response.json()
    assert len(response_data) == 2
    assert flow_unique_name in response_data[0]["name"]
    assert response_data[0]["description"] == "description"
    assert response_data[0]["data"] == data
    assert response_data[1]["name"] == flow_2_unique_name
    assert response_data[1]["description"] == "description"
    assert response_data[1]["data"] == data


@pytest.mark.usefixtures("session")
async def test_upload_file(client: AsyncClient, json_flow: str, logged_in_headers):
    flow = orjson.loads(json_flow)
    data = flow["data"]
    # Create test data
    flow_unique_name = str(uuid4())
    flow_2_unique_name = str(uuid4())
    flow_list = FlowListCreate(
        flows=[
            FlowCreate(name=flow_unique_name, description="description", data=data),
            FlowCreate(name=flow_2_unique_name, description="description", data=data),
        ]
    )
    file_contents = orjson_dumps(flow_list.dict())
    response = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("examples.json", file_contents, "application/json")},
        headers=logged_in_headers,
    )
    # Check response status code
    assert response.status_code == 201
    # Check response data
    response_data = response.json()
    assert len(response_data) == 2
    assert flow_unique_name in response_data[0]["name"]
    assert response_data[0]["description"] == "description"
    assert response_data[0]["data"] == data
    assert response_data[1]["name"] == flow_2_unique_name
    assert response_data[1]["description"] == "description"
    assert response_data[1]["data"] == data


@pytest.mark.usefixtures("session")
async def test_download_file(
    client: AsyncClient,
    json_flow,
    active_user,
    logged_in_headers,
):
    flow = orjson.loads(json_flow)
    data = flow["data"]
    # Create test data
    flow_unique_name = str(uuid4())
    flow_2_unique_name = str(uuid4())
    flow_list = FlowListCreate(
        flows=[
            FlowCreate(name=flow_unique_name, description="description", data=data),
            FlowCreate(name=flow_2_unique_name, description="description", data=data),
        ]
    )
    db_manager = get_db_service()
    async with session_getter(db_manager) as _session:
        saved_flows = []
        for flow in flow_list.flows:
            flow.user_id = active_user.id
            db_flow = Flow.model_validate(flow, from_attributes=True)
            _session.add(db_flow)
            saved_flows.append(db_flow)
        await _session.commit()
        # Make request to endpoint inside the session context
        flow_ids = [str(db_flow.id) for db_flow in saved_flows]  # Convert UUIDs to strings
        flow_ids_json = json.dumps(flow_ids)
        response = await client.post(
            "api/v1/flows/download/",
            data=flow_ids_json,
            headers={**logged_in_headers, "Content-Type": "application/json"},
        )
    # Check response status code
    assert response.status_code == 200, response.json()
    # Check response data
    # Since the endpoint now returns a zip file, we need to check the content type and the filename in the headers
    assert response.headers["Content-Type"] == "application/x-zip-compressed"
    assert "attachment; filename=" in response.headers["Content-Disposition"]


@pytest.mark.usefixtures("active_user")
async def test_create_flow_with_invalid_data(client: AsyncClient, logged_in_headers):
    flow = {"name": "a" * 256, "data": "Invalid flow data"}
    response = await client.post("api/v1/flows/", json=flow, headers=logged_in_headers)
    assert response.status_code == 422


@pytest.mark.usefixtures("active_user")
async def test_get_nonexistent_flow(client: AsyncClient, logged_in_headers):
    uuid = uuid4()
    response = await client.get(f"api/v1/flows/{uuid}", headers=logged_in_headers)
    assert response.status_code == 404


@pytest.mark.usefixtures("active_user")
async def test_update_flow_idempotency(client: AsyncClient, json_flow: str, logged_in_headers):
    flow_data = orjson.loads(json_flow)
    data = flow_data["data"]
    flow_data = FlowCreate(name="Test Flow", description="description", data=data)
    response = await client.post("api/v1/flows/", json=flow_data.dict(), headers=logged_in_headers)
    flow_id = response.json()["id"]
    updated_flow = FlowCreate(name="Updated Flow", description="description", data=data)
    response1 = await client.put(f"api/v1/flows/{flow_id}", json=updated_flow.model_dump(), headers=logged_in_headers)
    response2 = await client.put(f"api/v1/flows/{flow_id}", json=updated_flow.model_dump(), headers=logged_in_headers)
    assert response1.json() == response2.json()


@pytest.mark.usefixtures("active_user")
async def test_update_nonexistent_flow(client: AsyncClient, json_flow: str, logged_in_headers):
    flow_data = orjson.loads(json_flow)
    data = flow_data["data"]
    uuid = uuid4()
    updated_flow = FlowCreate(
        name="Updated Flow",
        description="description",
        data=data,
    )
    response = await client.patch(f"api/v1/flows/{uuid}", json=updated_flow.model_dump(), headers=logged_in_headers)
    assert response.status_code == 404, response.text


@pytest.mark.usefixtures("active_user")
async def test_delete_nonexistent_flow(client: AsyncClient, logged_in_headers):
    uuid = uuid4()
    response = await client.delete(f"api/v1/flows/{uuid}", headers=logged_in_headers)
    assert response.status_code == 404


@pytest.mark.usefixtures("active_user")
async def test_read_only_starter_projects(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/flows/basic_examples/", headers=logged_in_headers)
    starter_projects = await load_starter_projects()
    assert response.status_code == 200
    assert len(response.json()) == len(starter_projects)


async def test_sqlite_pragmas():
    db_service = get_db_service()

    async with db_service.with_session() as session:
        assert (await session.exec(text("PRAGMA journal_mode;"))).scalar() == "wal"
        assert (await session.exec(text("PRAGMA synchronous;"))).scalar() == 1


@pytest.mark.usefixtures("active_user")
async def test_read_folder(client: AsyncClient, logged_in_headers):
    # Create a new project
    folder_name = f"Test Project {uuid4()}"
    project = FolderCreate(name=folder_name, description="Test project description")
    response = await client.post("api/v1/projects/", json=project.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201
    created_folder = response.json()
    folder_id = created_folder["id"]

    # Read the project
    response = await client.get(f"api/v1/projects/{folder_id}", headers=logged_in_headers)
    assert response.status_code == 200
    folder_data = response.json()
    assert folder_data["name"] == folder_name
    assert folder_data["description"] == "Test project description"
    assert "flows" in folder_data
    assert isinstance(folder_data["flows"], list)


@pytest.mark.usefixtures("active_user")
async def test_read_folder_with_pagination(client: AsyncClient, logged_in_headers):
    # Create a new project
    folder_name = f"Test Project {uuid4()}"
    project = FolderCreate(name=folder_name, description="Test project description")
    response = await client.post("api/v1/projects/", json=project.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201
    created_folder = response.json()
    folder_id = created_folder["id"]

    # Read the project with pagination
    response = await client.get(
        f"api/v1/projects/{folder_id}", headers=logged_in_headers, params={"page": 1, "size": 10}
    )
    assert response.status_code == 200
    folder_data = response.json()
    assert isinstance(folder_data, dict)
    assert "folder" in folder_data
    assert "flows" in folder_data
    assert folder_data["folder"]["name"] == folder_name
    assert folder_data["folder"]["description"] == "Test project description"
    assert folder_data["flows"]["page"] == 1
    assert folder_data["flows"]["size"] == 10
    assert isinstance(folder_data["flows"]["items"], list)


@pytest.mark.usefixtures("active_user")
async def test_read_folder_with_flows(client: AsyncClient, json_flow: str, logged_in_headers):
    # Create a new project
    folder_name = f"Test Project {uuid4()}"
    flow_name = f"Test Flow {uuid4()}"
    project = FolderCreate(name=folder_name, description="Test project description")
    response = await client.post("api/v1/projects/", json=project.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201
    created_folder = response.json()
    folder_id = created_folder["id"]

    # Create a flow in the project
    flow_data = orjson.loads(json_flow)
    data = flow_data["data"]
    flow = FlowCreate(name=flow_name, description="description", data=data)
    flow.folder_id = folder_id
    response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201

    # Read the project with flows
    response = await client.get(f"api/v1/projects/{folder_id}", headers=logged_in_headers)
    assert response.status_code == 200
    folder_data = response.json()
    assert folder_data["name"] == folder_name
    assert folder_data["description"] == "Test project description"
    assert len(folder_data["flows"]) == 1
    assert folder_data["flows"][0]["name"] == flow_name


@pytest.mark.usefixtures("active_user")
async def test_read_nonexistent_folder(client: AsyncClient, logged_in_headers):
    nonexistent_id = str(uuid4())
    response = await client.get(f"api/v1/projects/{nonexistent_id}", headers=logged_in_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


@pytest.mark.usefixtures("active_user")
async def test_read_folder_with_search(client: AsyncClient, json_flow: str, logged_in_headers):
    # Create a new project
    folder_name = f"Test Project {uuid4()}"
    project = FolderCreate(name=folder_name, description="Test project description")
    response = await client.post("api/v1/projects/", json=project.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201
    created_folder = response.json()
    folder_id = created_folder["id"]

    # Create two flows in the project
    flow_data = orjson.loads(json_flow)
    flow_name_1 = f"Test Flow 1 {uuid4()}"
    flow_name_2 = f"Another Flow {uuid4()}"

    flow1 = FlowCreate(
        name=flow_name_1, description="Test flow description", data=flow_data["data"], folder_id=folder_id
    )
    flow2 = FlowCreate(
        name=flow_name_2, description="Another flow description", data=flow_data["data"], folder_id=folder_id
    )
    flow1.folder_id = folder_id
    flow2.folder_id = folder_id
    await client.post("api/v1/flows/", json=flow1.model_dump(), headers=logged_in_headers)
    await client.post("api/v1/flows/", json=flow2.model_dump(), headers=logged_in_headers)

    # Read the project with search
    response = await client.get(
        f"api/v1/projects/{folder_id}", headers=logged_in_headers, params={"search": "Test", "page": 1, "size": 10}
    )
    assert response.status_code == 200
    folder_data = response.json()
    assert len(folder_data["flows"]["items"]) == 1
    assert folder_data["flows"]["items"][0]["name"] == flow_name_1


@pytest.mark.usefixtures("active_user")
async def test_read_folder_with_component_filter(client: AsyncClient, json_flow: str, logged_in_headers):
    # Create a new project
    folder_name = f"Test Project {uuid4()}"
    project = FolderCreate(name=folder_name, description="Test project description")
    response = await client.post("api/v1/projects/", json=project.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201
    created_folder = response.json()
    folder_id = created_folder["id"]

    # Create a component flow in the project
    flow_data = orjson.loads(json_flow)
    component_flow_name = f"Component Flow {uuid4()}"
    component_flow = FlowCreate(
        name=component_flow_name,
        description="Component flow description",
        data=flow_data["data"],
        folder_id=folder_id,
        is_component=True,
    )
    component_flow.folder_id = folder_id
    await client.post("api/v1/flows/", json=component_flow.model_dump(), headers=logged_in_headers)

    # Read the project with component filter
    response = await client.get(
        f"api/v1/projects/{folder_id}", headers=logged_in_headers, params={"is_component": True, "page": 1, "size": 10}
    )
    assert response.status_code == 200
    folder_data = response.json()
    assert len(folder_data["flows"]["items"]) == 1
    assert folder_data["flows"]["items"][0]["name"] == component_flow_name
    assert folder_data["flows"]["items"][0]["is_component"] == True  # noqa: E712
