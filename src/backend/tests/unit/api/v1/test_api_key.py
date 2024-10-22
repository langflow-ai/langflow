import pytest
from fastapi import status
from httpx import AsyncClient


async def test_create_folder(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/api_key/", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "api_keys" in result.keys(), "The dictionary must contain a key called 'api_keys'"
    assert "user_id" in result.keys(), "The dictionary must contain a key called 'user_id'"
    assert "total_count" in result.keys(), "The dictionary must contain a key called 'total_count'"
