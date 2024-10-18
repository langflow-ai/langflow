import re
import shutil
import tempfile
from contextlib import suppress
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from langflow.services.deps import get_storage_service
from langflow.services.storage.service import StorageService
from sqlmodel import Session


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


@pytest.fixture(name="files_client")
async def files_client_fixture(session: Session, monkeypatch, request, load_flows_dir, mock_storage_service):
    # Set the database url to a test database
    if "noclient" in request.keywords:
        yield
    else:
        db_dir = tempfile.mkdtemp()
        db_path = Path(db_dir) / "test.db"
        monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite:///{db_path}")
        monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "false")
        if "load_flows" in request.keywords:
            shutil.copyfile(
                pytest.BASIC_EXAMPLE_PATH, Path(load_flows_dir) / "c54f9130-f2fa-4a3e-b22a-3856d946351b.json"
            )
            monkeypatch.setenv("LANGFLOW_LOAD_FLOWS_PATH", load_flows_dir)
            monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "true")

        from langflow.main import create_app

        app = create_app()

        app.dependency_overrides[get_storage_service] = lambda: mock_storage_service
        async with LifespanManager(app, startup_timeout=None, shutdown_timeout=None) as manager:
            async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://testserver/") as client:
                yield client
        # app.dependency_overrides.clear()
        monkeypatch.undo()
        # clear the temp db
        with suppress(FileNotFoundError):
            db_path.unlink()


async def test_upload_file(files_client, created_api_key, flow):
    headers = {"x-api-key": created_api_key.api_key}

    response = await files_client.post(
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


async def test_download_file(files_client, created_api_key, flow):
    headers = {"x-api-key": created_api_key.api_key}
    response = await files_client.get(f"api/v1/files/download/{flow.id}/test.txt", headers=headers)
    assert response.status_code == 200
    assert response.content == b"file content"


async def test_list_files(files_client, created_api_key, flow):
    headers = {"x-api-key": created_api_key.api_key}
    response = await files_client.get(f"api/v1/files/list/{flow.id}", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"files": ["file1.txt", "file2.jpg"]}


async def test_delete_file(files_client, created_api_key, flow):
    headers = {"x-api-key": created_api_key.api_key}

    response = await files_client.delete(f"api/v1/files/delete/{flow.id}/test.txt", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"message": "File test.txt deleted successfully"}


async def test_file_operations(client, created_api_key, flow):
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = flow.id
    file_name = "test.txt"
    file_content = b"Hello, world!"

    # Step 1: Upload the file
    response = await client.post(
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
    response = await client.get(f"api/v1/files/list/{flow_id}", headers=headers)
    assert response.status_code == 200
    assert full_file_name in response.json()["files"]

    # Step 3: Download the file and verify its content
    response = await client.get(f"api/v1/files/download/{flow_id}/{full_file_name}", headers=headers)
    assert response.status_code == 200
    assert response.content == file_content
    assert response.headers["content-type"] == "application/octet-stream"

    # Step 4: Delete the file
    response = await client.delete(f"api/v1/files/delete/{flow_id}/{full_file_name}", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"message": f"File {full_file_name} deleted successfully"}

    # Verify that the file is indeed deleted
    response = await client.get(f"api/v1/files/list/{flow_id}", headers=headers)
    assert full_file_name not in response.json()["files"]
