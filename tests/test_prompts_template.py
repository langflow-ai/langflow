from fastapi.testclient import TestClient
from langflow.services.deps import get_settings_service


def test_prompts_settings(client: TestClient, logged_in_headers):
    settings_service = get_settings_service()
    response = client.get("api/v1/all", headers=logged_in_headers)
    assert response.status_code == 200
    json_response = response.json()
    prompts = json_response["prompts"]
    assert set(prompts.keys()) == set(settings_service.settings.PROMPTS)
