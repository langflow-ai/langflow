from unittest.mock import MagicMock

import pytest
from langflow.services.deps import get_storage_service
from langflow.services.storage.service import StorageService
from langflow.services.storage.utils import build_content_type_from_extension


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


def test_upload_file(client, mock_storage_service):
    # Replace the actual storage service with the mock
    client.app.dependency_overrides[get_storage_service] = lambda: mock_storage_service

    response = client.post("api/v1/files/upload/test_flow", files={"file": ("test.txt", b"test content")})
    assert response.status_code == 201
    assert response.json() == {"message": "File uploaded successfully", "file_path": "test_flow/test.txt"}


def test_download_file(client, mock_storage_service):
    client.app.dependency_overrides[get_storage_service] = lambda: mock_storage_service

    response = client.get("api/v1/files/download/test_flow/test.txt")
    assert response.status_code == 200
    assert response.content == b"file content"


def test_list_files(client, mock_storage_service):
    client.app.dependency_overrides[get_storage_service] = lambda: mock_storage_service

    response = client.get("api/v1/files/list/test_flow")
    assert response.status_code == 200
    assert response.json() == {"files": ["file1.txt", "file2.jpg"]}


def test_delete_file(client, mock_storage_service):
    client.app.dependency_overrides[get_storage_service] = lambda: mock_storage_service

    response = client.delete("api/v1/files/delete/test_flow/test.txt")
    assert response.status_code == 200
    assert response.json() == {"message": "File test.txt deleted successfully"}


def test_file_operations(client):
    flow_id = "test_flow"
    file_name = "test.txt"
    file_content = b"Hello, world!"

    # Step 1: Upload the file
    response = client.post(f"api/v1/files/upload/{flow_id}", files={"file": (file_name, file_content)})
    assert response.status_code == 201
    assert response.json() == {"message": "File uploaded successfully", "file_path": f"{flow_id}/{file_name}"}

    # Step 2: List files in the folder
    response = client.get(f"api/v1/files/list/{flow_id}")
    assert response.status_code == 200
    assert file_name in response.json()["files"]

    # Step 3: Download the file and verify its content
    mime_type = build_content_type_from_extension(file_name.split(".")[-1])
    response = client.get(f"api/v1/files/download/{flow_id}/{file_name}")
    assert response.status_code == 200
    assert response.content == file_content
    assert mime_type in response.headers["content-type"]

    # Step 4: Delete the file
    response = client.delete(f"api/v1/files/delete/{flow_id}/{file_name}")
    assert response.status_code == 200
    assert response.json() == {"message": f"File {file_name} deleted successfully"}

    # Verify that the file is indeed deleted
    response = client.get(f"api/v1/files/list/{flow_id}")
    assert file_name not in response.json()["files"]
