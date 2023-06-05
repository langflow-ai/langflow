from langflow.api.schemas import FlowListCreate
from langflow.database.models.flow import FlowCreate
import json
from sqlalchemy.orm import Session
from langflow.database.models.flow import Flow


def test_create_flow(client, json_flow):
    flow = FlowCreate(name="Test Flow", flow=json_flow)
    response = client.post("/flows/", json=flow.dict())
    assert response.status_code == 200
    assert response.json()["name"] == flow.name
    assert response.json()["flow"] == flow.flow


def test_read_flows(client, json_flow):
    flow = FlowCreate(name="Test Flow", flow=json_flow)
    response = client.post("/flows/", json=flow.dict())
    assert response.status_code == 200
    assert response.json()["name"] == flow.name
    assert response.json()["flow"] == flow.flow
    flow = FlowCreate(name="Test Flow", flow=json_flow)
    response = client.post("/flows/", json=flow.dict())
    assert response.status_code == 200
    assert response.json()["name"] == flow.name
    assert response.json()["flow"] == flow.flow

    response = client.get("/flows/")
    assert response.status_code == 200
    assert len(response.json()) > 0


def test_read_flow(client, json_flow):
    flow = FlowCreate(name="Test Flow", flow=json_flow)
    response = client.post("/flows/", json=flow.dict())
    flow_id = response.json()["id"]
    response = client.get(f"/flows/{flow_id}")
    assert response.status_code == 200
    assert response.json()["name"] == flow.name
    assert response.json()["flow"] == flow.flow


def test_update_flow(client, json_flow):
    flow = FlowCreate(name="Test Flow", flow=json_flow)
    response = client.post("/flows/", json=flow.dict())
    flow_id = response.json()["id"]
    updated_flow = FlowCreate(
        name="Updated Flow", flow=json_flow.replace("BasicExample", "Updated Flow")
    )
    response = client.put(f"/flows/{flow_id}", json=updated_flow.dict())
    assert response.status_code == 200
    assert response.json()["name"] == updated_flow.name
    assert response.json()["flow"] == updated_flow.flow


def test_delete_flow(client, json_flow):
    flow = FlowCreate(name="Test Flow", flow=json_flow)
    response = client.post("/flows/", json=flow.dict())
    flow_id = response.json()["id"]
    response = client.delete(f"/flows/{flow_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Flow deleted successfully"


def test_create_flows(client, session: Session):
    # Create test data
    flow_list = FlowListCreate(
        flows=[
            FlowCreate(name="Flow 1", flow="Test flow 1"),
            FlowCreate(name="Flow 2", flow="Test flow 2"),
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
    assert response_data[0]["flow"] == "Test flow 1"
    assert response_data[1]["name"] == "Flow 2"
    assert response_data[1]["flow"] == "Test flow 2"


def test_upload_file(client, session: Session):
    # Create test data
    flow_list = FlowListCreate(
        flows=[
            FlowCreate(name="Flow 1", flow="Test flow 1"),
            FlowCreate(name="Flow 2", flow="Test flow 2"),
        ]
    )
    file_contents = json.dumps(flow_list.dict())
    # Make request to endpoint
    #     curl -X 'POST' \
    #   'http://127.0.0.1:7860/flows/upload/' \
    #   -H 'accept: application/json' \
    #   -H 'Content-Type: multipart/form-data' \
    #   -F 'file=@examples.json;type=application/json'
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
    assert response_data[0]["flow"] == "Test flow 1"
    assert response_data[1]["name"] == "Flow 2"
    assert response_data[1]["flow"] == "Test flow 2"


def test_download_file(client, session: Session):
    # Create test data
    flow_list = FlowListCreate(
        flows=[
            FlowCreate(name="Flow 1", flow="Test flow 1"),
            FlowCreate(name="Flow 2", flow="Test flow 2"),
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
    assert response_data[0]["flow"] == "Test flow 1"
    assert response_data[1]["name"] == "Flow 2"
    assert response_data[1]["flow"] == "Test flow 2"
