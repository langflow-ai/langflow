import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.skip(reason="Temporarily disabled: This is currently broken")
async def test_upload_file(client: AsyncClient, logged_in_headers):
    flow_id = "123e4567-e89b-12d3-a456-426614174000"
    file_content = b"sample file content"
    file_name = "test_file.txt"
    files = {"file": (file_name, file_content, "text/plain")}

    response = await client.post(f"/api/v1/files/upload/{flow_id}", files=files, headers=logged_in_headers)

    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.skip(reason="Temporarily disabled: This is currently broken")
async def test_download_file(client: AsyncClient):
    flow_id = "123e4567-e89b-12d3-a456-426614174000"
    file_name = "test.txt"

    response = await client.get(f"api/v1/files/download/{flow_id}/{file_name}")

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.skip(reason="Temporarily disabled: This is currently broken")
async def test_download_image(client: AsyncClient):
    flow_id = "123e4567-e89b-12d3-a456-426614174000"
    file_name = "test.jpg"

    response = await client.get(f"api/v1/files/images/{flow_id}/{file_name}")

    assert response.status_code == status.HTTP_200_OK


async def test_download_profile_picture(client: AsyncClient):
    files = (await client.get("api/v1/files/profile_pictures/list")).json().get("files")
    folder_name, file_name = files[0].split("/")
    endpoint = f"api/v1/files/profile_pictures/{folder_name}/{file_name}"

    response = await client.get(endpoint)

    assert response.status_code == status.HTTP_200_OK
    assert "image/svg+xml" in response.headers.get("content-type", "")


async def test_list_profile_pictures(client: AsyncClient):
    response = await client.get("api/v1/files/profile_pictures/list")
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "files" in result, "The result must contain a 'files' key"
    assert isinstance(result["files"], list), "The 'files' key must contain a list"


@pytest.mark.skip(reason="Temporarily disabled: This is currently broken")
async def test_list_files(client: AsyncClient, logged_in_headers):
    flow_id = "123e4567-e89b-12d3-a456-426614174000"

    response = await client.get(f"api/v1/files/list/{flow_id}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.skip(reason="Temporarily disabled: This is currently broken")
async def test_delete_file(client: AsyncClient, logged_in_headers):
    flow_id = "123e4567-e89b-12d3-a456-426614174000"
    file_name = "test.txt"

    response = await client.delete(f"api/v1/files/delete/{flow_id}/{file_name}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_204_NO_CONTENT
