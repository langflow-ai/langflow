import re
from unittest.mock import MagicMock

import pytest

from langflow.services.deps import get_storage_service
from langflow.services.storage.service import StorageService


@pytest.fixture
def mock_storage_service():
    # Create a mock instance of StorageService
    service = MagicMock(spec=StorageService)
    # Setup mock behaviors for the service methods as needed
    service.save_file.return_value = None
    service.get_file.return_value = b"file content"  # Binary content for files
    service.list_files.return_value = ["file1.txt", "file2.jpg"]
    service.delete_file.return_value = None
    return service


def test_upload_file(client, mock_storage_service, created_api_key, flow):
    headers = {"x-api-key": created_api_key.api_key}
    # Replace the actual storage service with the mock
    client.app.dependency_overrides[get_storage_service] = lambda: mock_storage_service

    response = client.post(
        f"api/v1/files/upload/{flow.id}",
        files={"file": ("test.txt", b"test content")},
        headers=headers,
    )
    assert response.status_code == 201

    response_json = response.json()
    assert response_json["flowId"] == str(flow.id)

    # Check that the file_path matches the expected pattern
    file_path_pattern = re.compile(rf"{flow.id}/\d{{4}}-\d{{2}}-\d{{2}}_\d{{2}}-\d{{2}}-\d{{2}}_test\.txt")
    assert file_path_pattern.match(response_json["file_path"])


def test_download_file(client, mock_storage_service, created_api_key, flow):
    headers = {"x-api-key": created_api_key.api_key}
    client.app.dependency_overrides[get_storage_service] = lambda: mock_storage_service

    response = client.get(f"api/v1/files/download/{flow.id}/test.txt", headers=headers)
    assert response.status_code == 200
    assert response.content == b"file content"


def test_list_files(client, mock_storage_service, created_api_key, flow):
    headers = {"x-api-key": created_api_key.api_key}
    client.app.dependency_overrides[get_storage_service] = lambda: mock_storage_service

    response = client.get(f"api/v1/files/list/{flow.id}", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"files": ["file1.txt", "file2.jpg"]}


def test_delete_file(client, mock_storage_service, created_api_key, flow):
    headers = {"x-api-key": created_api_key.api_key}
    client.app.dependency_overrides[get_storage_service] = lambda: mock_storage_service

    response = client.delete(f"api/v1/files/delete/{flow.id}/test.txt", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"message": "File test.txt deleted successfully"}


def test_file_operations(client, created_api_key, flow):
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = flow.id
    file_name = "test.txt"
    file_content = b"Hello, world!"

    # Step 1: Upload the file
    response = client.post(
        f"api/v1/files/upload/{flow_id}",
        files={"file": (file_name, file_content)},
        headers=headers,
    )
    assert response.status_code == 201

    response_json = response.json()
    assert response_json["flowId"] == str(flow_id)

    # Check that the file_path matches the expected pattern
    file_path_pattern = re.compile(rf"{flow_id}/\d{{4}}-\d{{2}}-\d{{2}}_\d{{2}}-\d{{2}}-\d{{2}}_{file_name}")
    assert file_path_pattern.match(response_json["file_path"])

    # Extract the full file name with timestamp from the response
    full_file_name = response_json["file_path"].split("/")[-1]

    # Step 2: List files in the folder
    response = client.get(f"api/v1/files/list/{flow_id}", headers=headers)
    assert response.status_code == 200
    assert full_file_name in response.json()["files"]

    # Step 3: Download the file and verify its content
    response = client.get(f"api/v1/files/download/{flow_id}/{full_file_name}", headers=headers)
    assert response.status_code == 200
    assert response.content == file_content
    assert response.headers["content-type"] == "application/octet-stream"

    # Step 4: Delete the file
    response = client.delete(f"api/v1/files/delete/{flow_id}/{full_file_name}", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"message": f"File {full_file_name} deleted successfully"}

    # Verify that the file is indeed deleted
    response = client.get(f"api/v1/files/list/{flow_id}", headers=headers)
    assert full_file_name not in response.json()["files"]
