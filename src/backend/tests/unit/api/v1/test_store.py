import pytest
from fastapi import status
from httpx import AsyncClient


async def test_check_if_store_is_enabled(client: AsyncClient):
    response = await client.get("api/v1/store/check/")
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The variable must be a dictionary"
    assert "enabled" in result, "The dictionary must contain a key called 'enabled'"
    assert isinstance(result["enabled"], bool), "There must be a boolean value for the key 'enabled' in the dictionary"


async def test_check_if_store_has_api_key(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/store/check/api_key", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The variable must be a dictionary"
    assert "has_api_key" in result, "The dictionary must contain a key called 'has_api_key'"
    assert "is_valid" in result, "The dictionary must contain a key called 'is_valid'"


@pytest.mark.skip(reason="Temporarily disabled: Apparently, the store is unusable")
async def test_share_component(client: AsyncClient, logged_in_headers):
    response = await client.post("api/v1/store/components/", headers=logged_in_headers)

    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.skip(reason="Temporarily disabled: Apparently, the store is unusable")
async def test_update_shared_component(client: AsyncClient, logged_in_headers):
    component_id = "string"
    response = await client.patch(f"api/v1/store/{component_id}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK


async def test_get_components(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/store/components/", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The variable must be a dict"
    assert "count" in result, "The list must contain a key called 'count'"
    assert "authorized" in result, "The list must contain a key called 'authorized'"
    assert "results" in result, "The list must contain a key called 'results'"


@pytest.mark.skip(reason="Temporarily disabled: This is currently broken")
async def test_download_component(client: AsyncClient, logged_in_headers):
    component_id = "string"
    response = await client.get(f"api/v1/store/{component_id}/download", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.skip(reason="Temporarily disabled: This is currently broken")
async def test_get_tags(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/tags", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.skip(reason="Temporarily disabled: This is currently broken")
async def test_get_list_of_components_liked_by_user(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/usesr/likes", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.skip(reason="Temporarily disabled: This is currently broken")
async def test_like_component(client: AsyncClient, logged_in_headers):
    response = await client.post("api/v1/usesr/likes", headers=logged_in_headers)

    assert response.status_code == status.HTTP_201_CREATED
