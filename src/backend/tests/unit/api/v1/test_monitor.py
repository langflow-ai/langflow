import pytest
from fastapi import status
from httpx import AsyncClient


async def test_get_vertex_builds(client: AsyncClient):
    params = {"flow_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}

    response = await client.get("api/v1/monitor/builds", params=params)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "vertex_builds" in result, "The result must contain the key 'vertex_builds'"


async def test_delete_vertex_builds(client: AsyncClient):
    params = {"flow_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}

    response = await client.delete("api/v1/monitor/builds", params=params)

    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_get_messages(client: AsyncClient):
    params = {"flow_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}

    response = await client.get("api/v1/monitor/messages", params=params)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, list), "The result must be a list"


async def test_delete_messages(client: AsyncClient, logged_in_headers):
    messages = ["3fa85f64-5717-4562-b3fc-2c963f66afa6"]

    response = await client.request("DELETE", "api/v1/monitor/messages", json=messages, headers=logged_in_headers)

    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.skip(reason="Temporarily disabled: This is currently broken")
async def test_update_message(client: AsyncClient, logged_in_headers):
    message_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    basic_case = {
        "text": "string",
        "sender": "string",
        "sender_name": "string",
        "session_id": "string",
        "files": ["string"],
        "edit": True,
        "error": True,
    }

    response = await client.put(f"api/v1/monitor/messages/{message_id}", json=basic_case, headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.skip(reason="Temporarily disabled: This is currently broken")
async def test_update_session_id(client: AsyncClient, logged_in_headers):
    old_session_id = "string"
    endpoint = f"api/v1/monitor/messages/session/{old_session_id}"
    params = {"new_session_id": "string"}

    response = await client.patch(endpoint, params=params, headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK


async def test_delete_messages_session(client: AsyncClient, logged_in_headers):
    old_session_id = "string"

    response = await client.delete(f"api/v1/monitor/messages/session/{old_session_id}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_get_transactions(client: AsyncClient, logged_in_headers):
    params = {"flow_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}

    response = await client.get("api/v1/monitor/transactions", params=params, headers=logged_in_headers)
    response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list), "The result must be a list"
