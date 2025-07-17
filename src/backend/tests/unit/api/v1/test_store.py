from fastapi import status
from httpx import AsyncClient


async def test_check_if_store_is_enabled(client: AsyncClient):
    response = await client.get("api/v1/store/check/")
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The variable must be a dictionary"
    assert "enabled" in result, "The dictionary must contain a key called 'enabled'"
    assert isinstance(result["enabled"], bool), "There must be a boolean value for the key 'enabled' in the dictionary"
