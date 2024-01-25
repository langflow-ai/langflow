from fastapi.testclient import TestClient
from langflow.services.deps import get_settings_service


# check that all agents are in settings.agents
# are in json_response["agents"]
def test_vectorstores_settings(client: TestClient, logged_in_headers):
    settings_service = get_settings_service()
    response = client.get("api/v1/all", headers=logged_in_headers)
    assert response.status_code == 200
    json_response = response.json()
    vectorstores = json_response["vectorstores"]
    settings_vecs = set(settings_service.settings.VECTORSTORES)
    assert all(vs in vectorstores for vs in settings_vecs)
