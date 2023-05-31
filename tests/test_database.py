from langflow.database.models.flow import FlowCreate


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
