import pytest
from fastapi import status
from httpx import AsyncClient


async def test_get_version(client: AsyncClient):
    response = await client.get("api/v1/version")
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "version" in result.keys(), "The dictionary must contain a key called 'version'"
    assert "main_version" in result.keys(), "The dictionary must contain a key called 'main_version'"
    assert "package" in result.keys(), "The dictionary must contain a key called 'package'"
