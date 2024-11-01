from fastapi import status
from httpx import AsyncClient


async def test_get_version(client: AsyncClient):
    response = await client.get("api/v1/version")
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "version" in result, "The dictionary must contain a key called 'version'"
    assert "main_version" in result, "The dictionary must contain a key called 'main_version'"
    assert "package" in result, "The dictionary must contain a key called 'package'"


async def test_get_config(client: AsyncClient):
    response = await client.get("api/v1/config")
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "frontend_timeout" in result, "The dictionary must contain a key called 'frontend_timeout'"
    assert "auto_saving" in result, "The dictionary must contain a key called 'auto_saving'"
    assert "health_check_max_retries" in result, "The dictionary must contain a 'health_check_max_retries' key"
    assert "max_file_size_upload" in result, "The dictionary must contain a key called 'max_file_size_upload'"
