import pytest
from langflow.services.database.models.api_key import ApiKeyCreate


@pytest.fixture
def api_key(client, logged_in_headers, active_user):
    api_key = ApiKeyCreate(name="test-api-key")

    response = client.post("api/v1/api_key", data=api_key.model_dump_json(), headers=logged_in_headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_get_api_keys(client, logged_in_headers, api_key):
    response = client.get("api/v1/api_key", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert "total_count" in data
    assert "user_id" in data
    assert "api_keys" in data
    assert any("test-api-key" in api_key["name"] for api_key in data["api_keys"])
    # assert all api keys in data["api_keys"] are masked
    assert all("**" in api_key["api_key"] for api_key in data["api_keys"])


def test_create_api_key(client, logged_in_headers):
    api_key_name = "test-api-key"
    response = client.post("api/v1/api_key", json={"name": api_key_name}, headers=logged_in_headers)
    assert response.status_code == 200
    data = response.json()
    assert "name" in data and data["name"] == api_key_name
    assert "api_key" in data
    # When creating the API key is returned which is
    # the only time the API key is unmasked
    assert "**" not in data["api_key"]


def test_delete_api_key(client, logged_in_headers, active_user, api_key):
    # Assuming a function to create a test API key, returning the key ID
    api_key_id = api_key["id"]
    response = client.delete(f"api/v1/api_key/{api_key_id}", headers=logged_in_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["detail"] == "API Key deleted"
    # Optionally, add a follow-up check to ensure that the key is actually removed from the database
