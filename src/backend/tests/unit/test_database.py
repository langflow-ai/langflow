import io
import json
import zipfile
from datetime import datetime, timezone
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


@pytest.mark.usefixtures("session")
async def test_upload_zip_file_to_flows(client: AsyncClient, json_flow: str, logged_in_headers):
    """Test uploading a ZIP file containing flow JSONs to the flows upload endpoint."""
    flow = orjson.loads(json_flow)
    data = flow["data"]

    flow_1_name = str(uuid4())
    flow_2_name = str(uuid4())
    flow_1 = {"name": flow_1_name, "description": "desc1", "data": data}
    flow_2 = {"name": flow_2_name, "description": "desc2", "data": data}

    # Create a ZIP file in memory with individual flow JSONs
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr(f"{flow_1_name}.json", json.dumps(flow_1))
        zf.writestr(f"{flow_2_name}.json", json.dumps(flow_2))
    zip_buffer.seek(0)

    response = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("flows.zip", zip_buffer.getvalue(), "application/zip")},
        headers=logged_in_headers,
    )
    assert response.status_code == 201
    response_data = response.json()
    assert len(response_data) == 2
    names = {r["name"] for r in response_data}
    assert flow_1_name in names
    assert flow_2_name in names


@pytest.mark.usefixtures("session")
async def test_upload_zip_file_to_projects(client: AsyncClient, json_flow: str, logged_in_headers):
    """Test uploading a ZIP file containing flow JSONs to the projects upload endpoint."""
    flow = orjson.loads(json_flow)
    data = flow["data"]

    flow_1_name = str(uuid4())
    flow_2_name = str(uuid4())
    flow_1 = {"name": flow_1_name, "description": "desc1", "data": data}
    flow_2 = {"name": flow_2_name, "description": "desc2", "data": data}

    # Create a ZIP file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr(f"{flow_1_name}.json", json.dumps(flow_1))
        zf.writestr(f"{flow_2_name}.json", json.dumps(flow_2))
    zip_buffer.seek(0)

    response = await client.post(
        "api/v1/projects/upload/",
        files={"file": ("My Project.zip", zip_buffer.getvalue(), "application/zip")},
        headers=logged_in_headers,
    )
    assert response.status_code == 201
    response_data = response.json()
    assert len(response_data) == 2
    # All flows should belong to the same folder
    folder_ids = {r["folder_id"] for r in response_data}
    assert len(folder_ids) == 1

    # Verify the project name was derived from the ZIP filename
    folder_id = folder_ids.pop()
    project_response = await client.get(f"api/v1/projects/{folder_id}", headers=logged_in_headers)
    assert project_response.status_code == 200
    assert project_response.json()["name"].startswith("My Project")


@pytest.mark.usefixtures("session")
async def test_upload_empty_zip_returns_400(client: AsyncClient, logged_in_headers):
    """Test that uploading a ZIP with no JSON files returns 400."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("readme.txt", "not a flow")
    zip_buffer.seek(0)

    response = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("empty.zip", zip_buffer.getvalue(), "application/zip")},
        headers=logged_in_headers,
    )
    assert response.status_code == 400
    assert "No valid flow JSON files" in response.json()["detail"]


@pytest.mark.usefixtures("session")
async def test_download_then_upload_roundtrip(client: AsyncClient, json_flow: str, active_user, logged_in_headers):
    """Test that downloading flows as ZIP and re-uploading works end-to-end."""
    flow = orjson.loads(json_flow)
    data = flow["data"]

    flow_1_name = str(uuid4())
    flow_2_name = str(uuid4())
    flow_list = FlowListCreate(
        flows=[
            FlowCreate(name=flow_1_name, description="description", data=data),
            FlowCreate(name=flow_2_name, description="description", data=data),
        ]
    )

    # Create flows in DB
    db_manager = get_db_service()
    async with session_getter(db_manager) as _session:
        saved_flows = []
        for f in flow_list.flows:
            f.user_id = active_user.id
            db_flow = Flow.model_validate(f, from_attributes=True)
            _session.add(db_flow)
            saved_flows.append(db_flow)
        await _session.commit()
        flow_ids = [str(db_flow.id) for db_flow in saved_flows]

    # Download as ZIP
    download_response = await client.post(
        "api/v1/flows/download/",
        data=json.dumps(flow_ids),
        headers={**logged_in_headers, "Content-Type": "application/json"},
    )
    assert download_response.status_code == 200
    assert download_response.headers["Content-Type"] == "application/x-zip-compressed"

    # Re-upload the ZIP
    upload_response = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("flows.zip", download_response.content, "application/zip")},
        headers=logged_in_headers,
    )
    assert upload_response.status_code == 201
    uploaded = upload_response.json()
    assert len(uploaded) == 2


@pytest.mark.usefixtures("session")
async def test_upload_zip_with_invalid_json(client: AsyncClient, json_flow: str, logged_in_headers):
    """ZIP entries with invalid JSON are skipped; valid entries are still processed."""
    flow = orjson.loads(json_flow)
    data = flow["data"]
    valid_flow = {"name": "valid_flow", "description": "good", "data": data}

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("valid.json", json.dumps(valid_flow))
        zf.writestr("broken.json", "{not valid json!!!}")
    zip_buffer.seek(0)

    response = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("mixed.zip", zip_buffer.getvalue(), "application/zip")},
        headers=logged_in_headers,
    )
    assert response.status_code == 201
    response_data = response.json()
    assert len(response_data) == 1
    assert response_data[0]["name"] == "valid_flow"


@pytest.mark.usefixtures("session")
async def test_upload_zip_exceeding_max_entries(client: AsyncClient, json_flow: str, logged_in_headers, monkeypatch):
    """ZIP with more JSON entries than the limit raises 400."""
    import langflow.api.utils.zip_utils as zip_utils_mod

    monkeypatch.setattr(zip_utils_mod, "MAX_ZIP_ENTRIES", 3)

    flow = orjson.loads(json_flow)
    data = flow["data"]

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for i in range(5):
            zf.writestr(f"flow_{i}.json", json.dumps({"name": f"flow_{i}", "data": data}))
    zip_buffer.seek(0)

    response = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("too_many.zip", zip_buffer.getvalue(), "application/zip")},
        headers=logged_in_headers,
    )
    assert response.status_code == 400
    assert "exceeding the limit" in response.json()["detail"]


@pytest.mark.usefixtures("session")
async def test_upload_zip_with_oversized_entry(client: AsyncClient, json_flow: str, logged_in_headers, monkeypatch):
    """Entries exceeding size limit are skipped; smaller valid entries are processed."""
    import langflow.api.utils.zip_utils as zip_utils_mod

    flow = orjson.loads(json_flow)
    data = flow["data"]
    small_flow = {"name": "small_flow", "data": {"nodes": [], "edges": []}}
    big_flow = {"name": "big_flow", "data": data}

    # Build the ZIP first, then set the limit between the two entry sizes
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("small.json", json.dumps(small_flow))
        zf.writestr("big.json", json.dumps(big_flow))

    # Re-read to find the actual sizes and pick a limit between them
    with zipfile.ZipFile(io.BytesIO(zip_buffer.getvalue()), "r") as zf:
        sizes = {info.filename: info.file_size for info in zf.infolist()}
    limit = (sizes["small.json"] + sizes["big.json"]) // 2
    monkeypatch.setattr(zip_utils_mod, "MAX_ENTRY_UNCOMPRESSED_BYTES", limit)

    zip_buffer.seek(0)
    response = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("oversized.zip", zip_buffer.getvalue(), "application/zip")},
        headers=logged_in_headers,
    )
    assert response.status_code == 201
    response_data = response.json()
    assert len(response_data) == 1
    assert response_data[0]["name"] == "small_flow"


@pytest.mark.usefixtures("session")
async def test_upload_zip_with_mixed_valid_invalid(client: AsyncClient, json_flow: str, logged_in_headers, monkeypatch):
    """Mix of valid flows, invalid JSON, and oversized entries → only valid flows returned."""
    import langflow.api.utils.zip_utils as zip_utils_mod

    flow = orjson.loads(json_flow)
    data = flow["data"]
    valid_flow = {"name": "keeper", "data": {"nodes": [], "edges": []}}
    oversized_flow = {"name": "too_big", "data": data, "padding": "x" * 500}

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("valid.json", json.dumps(valid_flow))
        zf.writestr("broken.json", "NOT JSON {{{")
        zf.writestr("huge.json", json.dumps(oversized_flow))
        zf.writestr("readme.txt", "ignored non-json")

    # Set limit between valid entry size and oversized entry size
    with zipfile.ZipFile(io.BytesIO(zip_buffer.getvalue()), "r") as zf:
        sizes = {info.filename: info.file_size for info in zf.infolist()}
    limit = (sizes["valid.json"] + sizes["huge.json"]) // 2
    monkeypatch.setattr(zip_utils_mod, "MAX_ENTRY_UNCOMPRESSED_BYTES", limit)

    zip_buffer.seek(0)
    response = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("mixed.zip", zip_buffer.getvalue(), "application/zip")},
        headers=logged_in_headers,
    )
    assert response.status_code == 201
    response_data = response.json()
    assert len(response_data) == 1
    assert response_data[0]["name"] == "keeper"


@pytest.mark.usefixtures("session")
async def test_upload_zip_to_projects_filename_none(client: AsyncClient, json_flow: str, logged_in_headers):
    """When filename has no stem (e.g. '.zip'), the project name defaults to 'Imported Project'."""
    flow = orjson.loads(json_flow)
    data = flow["data"]
    flow_data = {"name": "flow_none", "data": data}

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("flow.json", json.dumps(flow_data))
    zip_buffer.seek(0)

    # filename=".zip" → rsplit gives ("", "zip") → "" is falsy → "Imported Project"
    response = await client.post(
        "api/v1/projects/upload/",
        files={"file": (".zip", zip_buffer.getvalue(), "application/zip")},
        headers=logged_in_headers,
    )
    assert response.status_code == 201
    response_data = response.json()
    assert len(response_data) == 1

    folder_id = response_data[0]["folder_id"]
    project_response = await client.get(f"api/v1/projects/{folder_id}", headers=logged_in_headers)
    assert project_response.status_code == 200
    assert project_response.json()["name"].startswith("Imported Project")


@pytest.mark.usefixtures("session")
async def test_upload_bad_zip_file_returns_400(client: AsyncClient, logged_in_headers):
    """Uploading a corrupt/invalid ZIP file returns 400 with a descriptive error."""
    # Build a payload that passes zipfile.is_zipfile() but fails ZipFile() construction.
    # We keep only the end-of-central-directory record (last 22 bytes of a real ZIP)
    # prepended with garbage, so the EOCD signature is found but the central directory is invalid.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("dummy.json", '{"name":"x"}')
    valid_zip = buf.getvalue()
    # Minimal EOCD is 22 bytes; keep it and prepend garbage
    corrupt_zip = b"garbage" * 10 + valid_zip[-22:]

    response = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("corrupt.zip", corrupt_zip, "application/zip")},
        headers=logged_in_headers,
    )
    assert response.status_code == 400
    assert "not a valid ZIP" in response.json()["detail"]


@pytest.mark.usefixtures("session")
async def test_upload_no_file_to_flows_returns_400(client: AsyncClient, logged_in_headers):
    """Uploading with no file to flows endpoint returns 400."""
    response = await client.post(
        "api/v1/flows/upload/",
        headers=logged_in_headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "No file provided"


@pytest.mark.usefixtures("session")
async def test_upload_no_file_to_projects_returns_400(client: AsyncClient, logged_in_headers):
    """Uploading with no file to projects endpoint returns 400."""
    response = await client.post(
        "api/v1/projects/upload/",
        headers=logged_in_headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "No file provided"


@pytest.mark.usefixtures("session")
async def test_upload_empty_file_to_flows_returns_400(client: AsyncClient, logged_in_headers):
    """Uploading an empty file to flows endpoint returns 400."""
    response = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("empty.json", b"", "application/json")},
        headers=logged_in_headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "The uploaded file is empty"


@pytest.mark.usefixtures("session")
async def test_upload_empty_file_to_projects_returns_400(client: AsyncClient, logged_in_headers):
    """Uploading an empty file to projects endpoint returns 400."""
    response = await client.post(
        "api/v1/projects/upload/",
        files={"file": ("empty.json", b"", "application/json")},
        headers=logged_in_headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "The uploaded file is empty"


@pytest.mark.usefixtures("session")
async def test_upload_invalid_json_to_flows_returns_400(client: AsyncClient, logged_in_headers):
    """Uploading invalid JSON content to flows endpoint returns 400."""
    response = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("bad.json", b"this is not json", "application/json")},
        headers=logged_in_headers,
    )
    assert response.status_code == 400
    assert "Invalid JSON file" in response.json()["detail"]


@pytest.mark.usefixtures("session")
async def test_upload_invalid_json_to_projects_returns_400(client: AsyncClient, logged_in_headers):
    """Uploading invalid JSON content to projects endpoint returns 400."""
    response = await client.post(
        "api/v1/projects/upload/",
        files={"file": ("bad.json", b"this is not json", "application/json")},
        headers=logged_in_headers,
    )
    assert response.status_code == 400
    assert "Invalid JSON file" in response.json()["detail"]


@pytest.mark.usefixtures("session")
async def test_upload_zip_to_projects_batch_name_dedup(client: AsyncClient, json_flow: str, logged_in_headers):
    """Multiple flows with the same name get unique names within the batch."""
    flow = orjson.loads(json_flow)
    data = flow["data"]

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for i in range(3):
            zf.writestr(f"flow_{i}.json", json.dumps({"name": "duplicate_name", "data": data}))
    zip_buffer.seek(0)

    response = await client.post(
        "api/v1/projects/upload/",
        files={"file": ("dedup_test.zip", zip_buffer.getvalue(), "application/zip")},
        headers=logged_in_headers,
    )
    assert response.status_code == 201
    response_data = response.json()
    assert len(response_data) == 3
    names = [r["name"] for r in response_data]
    # All names must be unique
    assert len(set(names)) == 3


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
    import asyncio
    import sqlite3
    from urllib.parse import unquote

    # PRAGMA queries don't work well through SQLModel's async session abstraction
    # They need direct database access, so we use sqlite3 directly
    db_service = get_db_service()
    database_url = db_service.database_url

    if not database_url.startswith("sqlite"):
        pytest.skip("This test only works with SQLite databases")

    # Extract the database path from the URL
    if "///" in database_url:
        db_path = database_url.split("///", 1)[1]
    elif "//" in database_url:
        db_path = database_url.split("//", 1)[1]
    else:
        pytest.skip("Could not extract database path from URL")

    db_path = unquote(db_path)

    def get_pragmas():
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("PRAGMA journal_mode=wal;")
            journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            synchronous = conn.execute("PRAGMA synchronous;").fetchone()[0]
            return journal_mode, synchronous
        finally:
            conn.close()

    journal_mode, synchronous = await asyncio.to_thread(get_pragmas)
    assert journal_mode == "wal"
    assert synchronous in [0, 1, 2], f"Unexpected synchronous value: {synchronous}"


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


def test_transaction_excludes_code_key(session):
    """Test that the code key is excluded from transaction inputs when logged to the database."""
    from langflow.services.database.models.transactions.model import TransactionTable

    # Create a flow to associate with the transaction
    flow = Flow(name=str(uuid4()), description="Test flow", data={})
    session.add(flow)
    session.commit()
    session.refresh(flow)

    # Create input data with a code key
    input_data = {"param1": "value1", "param2": "value2", "code": "print('Hello, world!')"}

    # Create a transaction with inputs containing a code key
    transaction = TransactionTable(
        timestamp=datetime.now(timezone.utc),
        vertex_id="test-vertex",
        target_id="test-target",
        inputs=input_data,
        outputs={"result": "success"},
        status="completed",
        flow_id=flow.id,
    )

    # Verify that the code key is removed during transaction creation
    assert transaction.inputs is not None
    assert "code" not in transaction.inputs
    assert "param1" in transaction.inputs
    assert "param2" in transaction.inputs

    # Add the transaction to the database
    session.add(transaction)
    session.commit()
    session.refresh(transaction)

    # Verify that the code key is not in the saved transaction inputs
    assert transaction.inputs is not None
    assert "code" not in transaction.inputs
    assert "param1" in transaction.inputs
    assert "param2" in transaction.inputs
