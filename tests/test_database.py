from uuid import uuid4
from langflow.api.schemas import FlowListCreate
from langflow.database.models.flow import FlowCreate
import json
from sqlalchemy.orm import Session
from langflow.database.models.flow import Flow
from fastapi.testclient import TestClient

import threading


def test_create_flow(client: TestClient, json_flow: str):
    flow = FlowCreate(name="Test Flow", flow=json.loads(json_flow))
    response = client.post("/flows/", json=flow.dict())
    assert response.status_code == 200
    assert response.json()["name"] == flow.name
    assert response.json()["flow"] == flow.flow


def test_read_flows(client: TestClient, json_flow: str):
    flow = FlowCreate(name="Test Flow", flow=json.loads(json_flow))
    response = client.post("/flows/", json=flow.dict())
    assert response.status_code == 200
    assert response.json()["name"] == flow.name
    assert response.json()["flow"] == flow.flow
    flow = FlowCreate(name="Test Flow", flow=json.loads(json_flow))
    response = client.post("/flows/", json=flow.dict())
    assert response.status_code == 200
    assert response.json()["name"] == flow.name
    assert response.json()["flow"] == flow.flow

    response = client.get("/flows/")
    assert response.status_code == 200
    assert len(response.json()) > 0


def test_read_flow(client: TestClient, json_flow: str):
    flow = FlowCreate(name="Test Flow", flow=json.loads(json_flow))
    response = client.post("/flows/", json=flow.dict())
    flow_id = response.json()["id"]
    response = client.get(f"/flows/{flow_id}")
    assert response.status_code == 200
    assert response.json()["name"] == flow.name
    assert response.json()["flow"] == flow.flow


def test_update_flow(client: TestClient, json_flow: str):
    flow = FlowCreate(name="Test Flow", flow=json.loads(json_flow))
    response = client.post("/flows/", json=flow.dict())
    flow_id = response.json()["id"]
    updated_flow = FlowCreate(
        name="Updated Flow",
        flow=json.loads(json_flow.replace("BasicExample", "Updated Flow")),
    )
    response = client.put(f"/flows/{flow_id}", json=updated_flow.dict())
    assert response.status_code == 200
    assert response.json()["name"] == updated_flow.name
    assert response.json()["flow"] == updated_flow.flow


def test_delete_flow(client: TestClient, json_flow: str):
    flow = FlowCreate(name="Test Flow", flow=json.loads(json_flow))
    response = client.post("/flows/", json=flow.dict())
    flow_id = response.json()["id"]
    response = client.delete(f"/flows/{flow_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Flow deleted successfully"


def test_create_flows(client: TestClient, session: Session, json_flow: str):
    # Create test data
    flow_list = FlowListCreate(
        flows=[
            FlowCreate(name="Flow 1", flow=json.loads(json_flow)),
            FlowCreate(name="Flow 2", flow=json.loads(json_flow)),
        ]
    )
    # Make request to endpoint
    response = client.post("/flows/batch/", json=flow_list.dict())
    # Check response status code
    assert response.status_code == 200
    # Check response data
    response_data = response.json()
    assert len(response_data) == 2
    assert response_data[0]["name"] == "Flow 1"
    assert response_data[0]["flow"] == json.loads(json_flow)
    assert response_data[1]["name"] == "Flow 2"
    assert response_data[1]["flow"] == json.loads(json_flow)


def test_upload_file(client: TestClient, session: Session, json_flow: str):
    # Create test data
    flow_list = FlowListCreate(
        flows=[
            FlowCreate(name="Flow 1", flow=json.loads(json_flow)),
            FlowCreate(name="Flow 2", flow=json.loads(json_flow)),
        ]
    )
    file_contents = json.dumps(flow_list.dict())
    response = client.post(
        "/flows/upload/",
        files={"file": ("examples.json", file_contents, "application/json")},
    )
    # Check response status code
    assert response.status_code == 200
    # Check response data
    response_data = response.json()
    assert len(response_data) == 2
    assert response_data[0]["name"] == "Flow 1"
    assert response_data[0]["flow"] == json.loads(json_flow)
    assert response_data[1]["name"] == "Flow 2"
    assert response_data[1]["flow"] == json.loads(json_flow)


def test_download_file(client: TestClient, session: Session, json_flow):
    # Create test data
    flow_list = FlowListCreate(
        flows=[
            FlowCreate(name="Flow 1", flow=json.loads(json_flow)),
            FlowCreate(name="Flow 2", flow=json.loads(json_flow)),
        ]
    )
    for flow in flow_list.flows:
        db_flow = Flow.from_orm(flow)
        session.add(db_flow)
    session.commit()
    # Make request to endpoint
    response = client.get("/flows/download/")
    # Check response status code
    assert response.status_code == 200
    # Check response data
    response_data = json.loads(response.json()["file"])
    assert len(response_data) == 2
    assert response_data[0]["name"] == "Flow 1"
    assert response_data[0]["flow"] == json.loads(json_flow)
    assert response_data[1]["name"] == "Flow 2"
    assert response_data[1]["flow"] == json.loads(json_flow)


def test_create_flow_with_invalid_data(client: TestClient):
    flow = {"name": "a" * 256, "flow": "Invalid flow data"}
    response = client.post("/flows/", json=flow)
    assert response.status_code == 422


def test_get_nonexistent_flow(client: TestClient):
    # uuid4 generates a random UUID
    uuid = uuid4()
    response = client.get(f"/flows/{uuid}")
    assert response.status_code == 404


def test_update_flow_idempotency(client: TestClient, json_flow: str):
    flow = FlowCreate(name="Test Flow", flow=json.loads(json_flow))
    response = client.post("/flows/", json=flow.dict())
    flow_id = response.json()["id"]
    updated_flow = FlowCreate(name="Updated Flow", flow=json.loads(json_flow))
    response1 = client.put(f"/flows/{flow_id}", json=updated_flow.dict())
    response2 = client.put(f"/flows/{flow_id}", json=updated_flow.dict())
    assert response1.json() == response2.json()


def test_update_nonexistent_flow(client: TestClient, json_flow: str):
    uuid = uuid4()
    updated_flow = FlowCreate(
        name="Updated Flow",
        flow=json.loads(json_flow.replace("BasicExample", "Updated Flow")),
    )
    response = client.put(f"/flows/{uuid}", json=updated_flow.dict())
    assert response.status_code == 404


def test_delete_nonexistent_flow(client: TestClient):
    uuid = uuid4()
    response = client.delete(f"/flows/{uuid}")
    assert response.status_code == 404


def test_read_empty_flows(client: TestClient):
    response = client.get("/flows/")
    assert response.status_code == 200
    assert len(response.json()) == 0


def test_stress_create_flow(client: TestClient, json_flow: str):
    flow = FlowCreate(name="Test Flow", flow=json.loads(json_flow))

    def create_flow():
        response = client.post("/flows/", json=flow.dict())
        assert response.status_code == 200

    threads = []
    for i in range(100):
        t = threading.Thread(target=create_flow)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
