from fastapi.testclient import TestClient
from langflow.services.utils import get_settings_manager


# check that all agents are in settings.agents
# are in json_response["agents"]
def test_vectorstores_settings(client: TestClient):
    settings_manager = get_settings_manager()
    response = client.get("api/v1/all")
    assert response.status_code == 200
    json_response = response.json()
    vectorstores = json_response["vectorstores"]
    assert set(vectorstores.keys()) == set(settings_manager.settings.VECTORSTORES)
