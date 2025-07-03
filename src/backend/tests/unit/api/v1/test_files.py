import asyncio
import json
import re
import tempfile
from contextlib import suppress
from io import BytesIO
from pathlib import Path

# we need to import tmpdir
import anyio
import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from langflow.main import create_app
from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.flow.model import Flow, FlowCreate
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.database.utils import session_getter
from langflow.services.deps import get_db_service
from sqlalchemy.orm import selectinload
from sqlmodel import select

from tests.conftest import _delete_transactions_and_vertex_builds


@pytest.fixture(name="files_created_api_key")
async def files_created_api_key(files_client, files_active_user):  # noqa: ARG001
    hashed = get_password_hash("random_key")
    api_key = ApiKey(
        name="files_created_api_key",
        user_id=files_active_user.id,
        api_key="random_key",
        hashed_api_key=hashed,
    )
    db_manager = get_db_service()
    async with session_getter(db_manager) as session:
        stmt = select(ApiKey).where(ApiKey.api_key == api_key.api_key)
        if existing_api_key := (await session.exec(stmt)).first():
            yield existing_api_key
            return
        session.add(api_key)
        await session.commit()
        await session.refresh(api_key)
        yield api_key
        # Clean up
        await session.delete(api_key)
        await session.commit()


@pytest.fixture(name="files_active_user")
async def files_active_user(files_client):  # noqa: ARG001
    db_manager = get_db_service()
    async with db_manager.with_session() as session:
        user = User(
            username="files_active_user",
            password=get_password_hash("testpassword"),
            is_active=True,
            is_superuser=False,
        )
        stmt = select(User).where(User.username == user.username)
        if active_user := (await session.exec(stmt)).first():
            user = active_user
        else:
            session.add(user)
            await session.commit()
            await session.refresh(user)
        user = UserRead.model_validate(user, from_attributes=True)
    yield user
    # Clean up
    # Now cleanup transactions, vertex_build
    async with db_manager.with_session() as session:
        user = await session.get(User, user.id, options=[selectinload(User.flows)])
        await _delete_transactions_and_vertex_builds(session, user.flows)
        await session.delete(user)

        await session.commit()


@pytest.fixture(name="files_flow")
async def files_flow(
    files_client,  # noqa: ARG001
    json_flow: str,
    files_active_user,
):
    loaded_json = json.loads(json_flow)
    flow_data = FlowCreate(name="test_flow", data=loaded_json.get("data"), user_id=files_active_user.id)
    db_manager = get_db_service()
    flow = Flow.model_validate(flow_data)
    async with db_manager.with_session() as session:
        session.add(flow)
        await session.commit()
        await session.refresh(flow)
        yield flow
        # Clean up
        await session.delete(flow)
        await session.commit()


@pytest.fixture
def max_file_size_upload_fixture(monkeypatch):
    monkeypatch.setenv("LANGFLOW_MAX_FILE_SIZE_UPLOAD", "1")
    yield
    monkeypatch.undo()


@pytest.fixture
def max_file_size_upload_10mb_fixture(monkeypatch):
    monkeypatch.setenv("LANGFLOW_MAX_FILE_SIZE_UPLOAD", "10")
    yield
    monkeypatch.undo()


@pytest.fixture(name="files_client")
async def files_client_fixture(
    monkeypatch,
    request,
):
    # Set the database url to a test database
    if "noclient" in request.keywords:
        yield
    else:

        def init_app():
            db_dir = tempfile.mkdtemp()
            db_path = Path(db_dir) / "test.db"
            monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite:///{db_path}")
            monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "false")
            from langflow.services.manager import get_service_manager

            service_manager = get_service_manager()
            service_manager.factories.clear()
            service_manager.services.clear()  # Clear the services cache
            app = create_app()
            return app, db_path

        app, db_path = await asyncio.to_thread(init_app)

        async with (
            LifespanManager(app, startup_timeout=None, shutdown_timeout=None) as manager,
            AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://testserver/") as client,
        ):
            yield client
        # app.dependency_overrides.clear()
        monkeypatch.undo()
        # clear the temp db
        with suppress(FileNotFoundError):
            await anyio.Path(db_path).unlink()


async def test_upload_file(files_client, files_created_api_key, files_flow):
    headers = {"x-api-key": files_created_api_key.api_key}

    response = await files_client.post(
        f"api/v1/files/upload/{files_flow.id}",
        files={"file": ("test.txt", b"test content")},
        headers=headers,
    )
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.json()}"

    response_json = response.json()
    assert response_json["flowId"] == str(files_flow.id)

    # Check that the file_path matches the expected pattern
    file_path_pattern = re.compile(rf"{files_flow.id}/\d{{4}}-\d{{2}}-\d{{2}}_\d{{2}}-\d{{2}}-\d{{2}}_test\.txt")
    assert file_path_pattern.match(response_json["file_path"])


async def test_download_file(files_client, files_created_api_key, files_flow):
    headers = {"x-api-key": files_created_api_key.api_key}

    # First upload a file
    response = await files_client.post(
        f"api/v1/files/upload/{files_flow.id}",
        files={"file": ("test.txt", b"test content")},
        headers=headers,
    )
    assert response.status_code == 201

    # Get the actual filename from the response
    file_path = response.json()["file_path"]
    file_name = file_path.split("/")[-1]

    # Then try to download it
    response = await files_client.get(f"api/v1/files/download/{files_flow.id}/{file_name}", headers=headers)
    assert response.status_code == 200
    assert response.content == b"test content"


async def test_list_files(files_client, files_created_api_key, files_flow):
    headers = {"x-api-key": files_created_api_key.api_key}

    # First upload a file
    response = await files_client.post(
        f"api/v1/files/upload/{files_flow.id}",
        files={"file": ("test.txt", b"test content")},
        headers=headers,
    )
    assert response.status_code == 201

    # Then list the files
    response = await files_client.get(f"api/v1/files/list/{files_flow.id}", headers=headers)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.json()}"
    files = response.json()["files"]
    assert len(files) == 1
    assert files[0].endswith("test.txt")


async def test_delete_file(files_client, files_created_api_key, files_flow):
    headers = {"x-api-key": files_created_api_key.api_key}

    response = await files_client.delete(f"api/v1/files/delete/{files_flow.id}/test.txt", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"message": "File test.txt deleted successfully"}


async def test_file_operations(files_client, files_created_api_key, files_flow):
    headers = {"x-api-key": files_created_api_key.api_key}
    flow_id = files_flow.id
    file_name = "test.txt"
    file_content = b"Hello, world!"

    # Step 1: Upload the file
    response = await files_client.post(
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
    response = await files_client.get(f"api/v1/files/list/{files_flow.id}", headers=headers)
    assert response.status_code == 200
    assert full_file_name in response.json()["files"]

    # Step 3: Download the file and verify its content
    response = await files_client.get(f"api/v1/files/download/{files_flow.id}/{full_file_name}", headers=headers)
    assert response.status_code == 200
    assert response.content == file_content
    assert response.headers["content-type"] == "application/octet-stream"

    # Step 4: Delete the file
    response = await files_client.delete(f"api/v1/files/delete/{files_flow.id}/{full_file_name}", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"message": f"File {full_file_name} deleted successfully"}

    # Verify that the file is indeed deleted
    response = await files_client.get(f"api/v1/files/list/{files_flow.id}", headers=headers)
    assert full_file_name not in response.json()["files"]


@pytest.mark.usefixtures("max_file_size_upload_fixture")
async def test_upload_file_size_limit(files_client, files_created_api_key, files_flow):
    headers = {"x-api-key": files_created_api_key.api_key}

    # Test file under the limit (500KB)
    small_content = b"x" * (500 * 1024)
    small_file = ("small_file.txt", small_content, "application/octet-stream")
    headers["Content-Length"] = str(len(small_content))
    response = await files_client.post(
        f"api/v1/files/upload/{files_flow.id}",
        files={"file": small_file},
        headers=headers,
    )
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.json()}"

    # Test file over the limit (1MB + 1KB)
    large_content = b"x" * (1024 * 1024 + 1024)

    bio = BytesIO(large_content)
    headers["Content-Length"] = str(len(large_content))
    response = await files_client.post(
        f"api/v1/files/upload/{files_flow.id}",
        files={"file": ("large_file.txt", bio, "application/octet-stream")},
        headers=headers,
    )

    assert response.status_code == 413, f"Expected 413, got {response.status_code}: {response.json()}"
    assert "Content size limit exceeded. Maximum allowed is 1MB and got 1.001MB." in response.json()["detail"]
