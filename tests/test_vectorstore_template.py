from fastapi.testclient import TestClient
from langflow.settings import settings


# check that all agents are in settings.agents
# are in json_response["agents"]
def test_vectorstores_settings(client: TestClient):
    response = client.get("api/v1/all")
    assert response.status_code == 200
    json_response = response.json()
    vectorstores = json_response["vectorstores"]
    assert set(vectorstores.keys()) == set(settings.vectorstores)
