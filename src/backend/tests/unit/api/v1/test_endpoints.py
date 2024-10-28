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


async def test_get_config(client: AsyncClient):
    response = await client.get("api/v1/config")
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "frontend_timeout" in result.keys(), "The dictionary must contain a key called 'frontend_timeout'"
    assert "auto_saving" in result.keys(), "The dictionary must contain a key called 'auto_saving'"
    assert "health_check_max_retries" in result.keys(), "The dictionary must contain a 'health_check_max_retries' key"
    assert "max_file_size_upload" in result.keys(), "The dictionary must contain a key called 'max_file_size_upload'"


async def test_get_sidebar_components(client: AsyncClient):
    response = await client.get("api/v1/sidebar_components")
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "categories" in result.keys(), "The dictionary must contain a key called 'categories'"
    assert len(result["categories"]) > 0, "The categories list must not be empty"
    assert isinstance(result["categories"], list), "The categories must be a list"
    assert "bundles" in result.keys(), "The dictionary must contain a key called 'bundles'"
    assert isinstance(result["bundles"], list), "The bundles must be a list"
    assert len(result["bundles"]) > 0, "The bundles list must not be empty"
