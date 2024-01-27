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


@pytest.mark.asyncio
async def test_upload_file(client, mock_storage_service):
    # Replace the actual storage service with the mock
    client.app.dependency_overrides[get_storage_service] = lambda: mock_storage_service

    response = client.post("api/v1/files/upload/test_flow", files={"file": ("test.txt", b"test content")})
    assert response.status_code == 201
    assert response.json() == {"message": "File uploaded successfully", "file_path": "test_flow/test.txt"}


@pytest.mark.asyncio
async def test_download_file(client, mock_storage_service):
    client.app.dependency_overrides[get_storage_service] = lambda: mock_storage_service

    response = client.get("api/v1/files/download/test_flow/test.txt")
    assert response.status_code == 200
    assert response.content == b"file content"


@pytest.mark.asyncio
async def test_list_files(client, mock_storage_service):
    client.app.dependency_overrides[get_storage_service] = lambda: mock_storage_service

    response = client.get("api/v1/files/list/test_flow")
    assert response.status_code == 200
    assert response.json() == {"files": ["file1.txt", "file2.jpg"]}


@pytest.mark.asyncio
async def test_delete_file(client, mock_storage_service):
    client.app.dependency_overrides[get_storage_service] = lambda: mock_storage_service

    response = client.delete("api/v1/files/delete/test_flow/test.txt")
    assert response.status_code == 200
    assert response.json() == {"message": "File test.txt deleted successfully"}
