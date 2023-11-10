from langflow.services.database.models.base import orjson_dumps
from langflow.services.database.utils import session_getter
from langflow.services.getters import get_db_service
import orjson
import pytest

from uuid import UUID, uuid4
from sqlmodel import Session

from fastapi.testclient import TestClient

from langflow.api.v1.schemas import FlowListCreate
from langflow.services.database.models.flow import Flow, FlowCreate, FlowUpdate


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


def test_create_flow(
    client: TestClient, json_flow: str, active_user, logged_in_headers
):
    flow = orjson.loads(json_flow)
    data = flow["data"]
    flow = FlowCreate(name="Test Flow", description="description", data=data)
    response = client.post("api/v1/flows/", json=flow.dict(), headers=logged_in_headers)
    assert response.status_code == 201
    assert response.json()["name"] == flow.name
    assert response.json()["data"] == flow.data
    # flow is optional so we can create a flow without a flow
    flow = FlowCreate(name="Test Flow", description="description")
    response = client.post(
        "api/v1/flows/", json=flow.dict(exclude_unset=True), headers=logged_in_headers
    )
    assert response.status_code == 201
    assert response.json()["name"] == flow.name
    assert response.json()["data"] == flow.data


def test_read_flows(client: TestClient, json_flow: str, active_user, logged_in_headers):
    flow_data = orjson.loads(json_flow)
    data = flow_data["data"]
    flow = FlowCreate(name="Test Flow", description="description", data=data)
    response = client.post("api/v1/flows/", json=flow.dict(), headers=logged_in_headers)
    assert response.status_code == 201
    assert response.json()["name"] == flow.name
    assert response.json()["data"] == flow.data

    flow = FlowCreate(name="Test Flow", description="description", data=data)
    response = client.post("api/v1/flows/", json=flow.dict(), headers=logged_in_headers)
    assert response.status_code == 201
    assert response.json()["name"] == flow.name
    assert response.json()["data"] == flow.data

    response = client.get("api/v1/flows/", headers=logged_in_headers)
    assert response.status_code == 200
    assert len(response.json()) > 0


def test_read_flow(client: TestClient, json_flow: str, active_user, logged_in_headers):
    flow = orjson.loads(json_flow)
    data = flow["data"]
    flow = FlowCreate(name="Test Flow", description="description", data=data)
    response = client.post("api/v1/flows/", json=flow.dict(), headers=logged_in_headers)
    flow_id = response.json()["id"]  # flow_id should be a UUID but is a string
    # turn it into a UUID
    flow_id = UUID(flow_id)

    response = client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert response.status_code == 200
    assert response.json()["name"] == flow.name
    assert response.json()["data"] == flow.data


def test_update_flow(
    client: TestClient, json_flow: str, active_user, logged_in_headers
):
    flow = orjson.loads(json_flow)
    data = flow["data"]

    flow = FlowCreate(name="Test Flow", description="description", data=data)
    response = client.post("api/v1/flows/", json=flow.dict(), headers=logged_in_headers)

    flow_id = response.json()["id"]
    updated_flow = FlowUpdate(
        name="Updated Flow",
        description="updated description",
        data=data,
    )
    response = client.patch(
        f"api/v1/flows/{flow_id}", json=updated_flow.dict(), headers=logged_in_headers
    )

    assert response.status_code == 200
    assert response.json()["name"] == updated_flow.name
    assert response.json()["description"] == updated_flow.description
    # assert response.json()["data"] == updated_flow.data


def test_delete_flow(
    client: TestClient, json_flow: str, active_user, logged_in_headers
):
    flow = orjson.loads(json_flow)
    data = flow["data"]
    flow = FlowCreate(name="Test Flow", description="description", data=data)
    response = client.post("api/v1/flows/", json=flow.dict(), headers=logged_in_headers)
    flow_id = response.json()["id"]
    response = client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Flow deleted successfully"


def test_create_flows(
    client: TestClient, session: Session, json_flow: str, logged_in_headers
):
    flow = orjson.loads(json_flow)
    data = flow["data"]
    # Create test data
    flow_list = FlowListCreate(
        flows=[
            FlowCreate(name="Flow 1", description="description", data=data),
            FlowCreate(name="Flow 2", description="description", data=data),
        ]
    )
    # Make request to endpoint
    response = client.post(
        "api/v1/flows/batch/", json=flow_list.dict(), headers=logged_in_headers
    )
    # Check response status code
    assert response.status_code == 201
    # Check response data
    response_data = response.json()
    assert len(response_data) == 2
    assert response_data[0]["name"] == "Flow 1"
    assert response_data[0]["description"] == "description"
    assert response_data[0]["data"] == data
    assert response_data[1]["name"] == "Flow 2"
    assert response_data[1]["description"] == "description"
    assert response_data[1]["data"] == data


def test_upload_file(
    client: TestClient, session: Session, json_flow: str, logged_in_headers
):
    flow = orjson.loads(json_flow)
    data = flow["data"]
    # Create test data
    flow_list = FlowListCreate(
        flows=[
            FlowCreate(name="Flow 1", description="description", data=data),
            FlowCreate(name="Flow 2", description="description", data=data),
        ]
    )
    file_contents = orjson_dumps(flow_list.dict())
    response = client.post(
        "api/v1/flows/upload/",
        files={"file": ("examples.json", file_contents, "application/json")},
        headers=logged_in_headers,
    )
    # Check response status code
    assert response.status_code == 201
    # Check response data
    response_data = response.json()
    assert len(response_data) == 2
    assert response_data[0]["name"] == "Flow 1"
    assert response_data[0]["description"] == "description"
    assert response_data[0]["data"] == data
    assert response_data[1]["name"] == "Flow 2"
    assert response_data[1]["description"] == "description"
    assert response_data[1]["data"] == data


def test_download_file(
    client: TestClient,
    session: Session,
    json_flow,
    active_user,
    logged_in_headers,
):
    flow = orjson.loads(json_flow)
    data = flow["data"]
    # Create test data
    flow_list = FlowListCreate(
        flows=[
            FlowCreate(name="Flow 1", description="description", data=data),
            FlowCreate(name="Flow 2", description="description", data=data),
        ]
    )
    db_manager = get_db_service()
    with session_getter(db_manager) as session:
        for flow in flow_list.flows:
            flow.user_id = active_user.id
            db_flow = Flow.from_orm(flow)
            session.add(db_flow)
        session.commit()
    # Make request to endpoint
    response = client.get("api/v1/flows/download/", headers=logged_in_headers)
    # Check response status code
    assert response.status_code == 200, response.json()
    # Check response data
    response_data = response.json()["flows"]
    assert len(response_data) == 2, response_data
    assert response_data[0]["name"] == "Flow 1"
    assert response_data[0]["description"] == "description"
    assert response_data[0]["data"] == data
    assert response_data[1]["name"] == "Flow 2"
    assert response_data[1]["description"] == "description"
    assert response_data[1]["data"] == data


def test_create_flow_with_invalid_data(
    client: TestClient, active_user, logged_in_headers
):
    flow = {"name": "a" * 256, "data": "Invalid flow data"}
    response = client.post("api/v1/flows/", json=flow, headers=logged_in_headers)
    assert response.status_code == 422


def test_get_nonexistent_flow(client: TestClient, active_user, logged_in_headers):
    uuid = uuid4()
    response = client.get(f"api/v1/flows/{uuid}", headers=logged_in_headers)
    assert response.status_code == 404


def test_update_flow_idempotency(
    client: TestClient, json_flow: str, active_user, logged_in_headers
):
    flow_data = orjson.loads(json_flow)
    data = flow_data["data"]
    flow_data = FlowCreate(name="Test Flow", description="description", data=data)
    response = client.post(
        "api/v1/flows/", json=flow_data.dict(), headers=logged_in_headers
    )
    flow_id = response.json()["id"]
    updated_flow = FlowCreate(name="Updated Flow", description="description", data=data)
    response1 = client.put(
        f"api/v1/flows/{flow_id}", json=updated_flow.dict(), headers=logged_in_headers
    )
    response2 = client.put(
        f"api/v1/flows/{flow_id}", json=updated_flow.dict(), headers=logged_in_headers
    )
    assert response1.json() == response2.json()


def test_update_nonexistent_flow(
    client: TestClient, json_flow: str, active_user, logged_in_headers
):
    flow_data = orjson.loads(json_flow)
    data = flow_data["data"]
    uuid = uuid4()
    updated_flow = FlowCreate(
        name="Updated Flow",
        description="description",
        data=data,
    )
    response = client.patch(
        f"api/v1/flows/{uuid}", json=updated_flow.dict(), headers=logged_in_headers
    )
    assert response.status_code == 404


def test_delete_nonexistent_flow(client: TestClient, active_user, logged_in_headers):
    uuid = uuid4()
    response = client.delete(f"api/v1/flows/{uuid}", headers=logged_in_headers)
    assert response.status_code == 404


def test_read_empty_flows(client: TestClient, active_user, logged_in_headers):
    response = client.get("api/v1/flows/", headers=logged_in_headers)
    assert response.status_code == 200
    assert len(response.json()) == 0
