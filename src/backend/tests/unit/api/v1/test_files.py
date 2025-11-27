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
from lfx.services.deps import session_scope
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
    async with session_scope() as session:
        stmt = select(ApiKey).where(ApiKey.api_key == api_key.api_key)
        if existing_api_key := (await session.exec(stmt)).first():
            api_key = existing_api_key
        else:
            session.add(api_key)
            await session.flush()
            await session.refresh(api_key)
    # Yield outside session scope to avoid database locks
    yield api_key
    # Clean up
    async with session_scope() as session:
        # Re-attach api_key to new session
        key_to_delete = await session.get(ApiKey, api_key.id)
        if key_to_delete:
            await session.delete(key_to_delete)


@pytest.fixture(name="files_active_user")
async def files_active_user(files_client):  # noqa: ARG001
    async with session_scope() as session:
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
            await session.flush()
            await session.refresh(user)
        user = UserRead.model_validate(user, from_attributes=True)
    yield user
    # Clean up
    # Now cleanup transactions, vertex_build
    async with session_scope() as session:
        user = await session.get(User, user.id, options=[selectinload(User.flows)])
        await _delete_transactions_and_vertex_builds(session, user.flows)
        await session.delete(user)


@pytest.fixture(name="files_flow")
async def files_flow(
    files_client,  # noqa: ARG001
    json_flow: str,
    files_active_user,
):
    loaded_json = json.loads(json_flow)
    flow_data = FlowCreate(name="test_flow", data=loaded_json.get("data"), user_id=files_active_user.id)
    flow = Flow.model_validate(flow_data)
    async with session_scope() as session:
        session.add(flow)
        await session.flush()
        await session.refresh(flow)
    # Yield outside session scope to avoid database locks
    yield flow
    # Clean up
    async with session_scope() as session:
        # Re-attach flow to new session
        flow_to_delete = await session.get(Flow, flow.id)
        if flow_to_delete:
            await session.delete(flow_to_delete)


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
            from lfx.services.manager import get_service_manager

            get_service_manager().factories.clear()
            get_service_manager().services.clear()  # Clear the services cache
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


@pytest.fixture
async def setup_profile_pictures(monkeypatch):
    """Fixture to set up profile pictures in a temporary config directory.

    This fixture must run before files_client to set LANGFLOW_CONFIG_DIR
    before app initialization.

    Args:
        monkeypatch: For overriding environment variables
    """
    # Create a temporary directory for profile pictures
    temp_dir = tempfile.mkdtemp()
    config_path = Path(temp_dir)

    # Create profile pictures directory structure
    people_dir = config_path / "profile_pictures" / "People"
    space_dir = config_path / "profile_pictures" / "Space"
    people_dir.mkdir(parents=True, exist_ok=True)
    space_dir.mkdir(parents=True, exist_ok=True)

    # Create test profile picture files (must be > 100 bytes for test assertions)
    rocket_svg = (
        b'<svg height="100" width="100" xmlns="http://www.w3.org/2000/svg">'
        b'<circle cx="50" cy="50" r="40" fill="red" stroke="darkred" stroke-width="2"/>'
        b'<path d="M 50 10 L 60 30 L 50 25 L 40 30 Z" fill="orange"/></svg>'
    )
    person_svg = (
        b'<svg height="100" width="100" xmlns="http://www.w3.org/2000/svg">'
        b'<circle cx="50" cy="50" r="40" fill="blue" stroke="darkblue" stroke-width="2"/>'
        b'<circle cx="40" cy="40" r="5" fill="white"/><circle cx="60" cy="40" r="5" fill="white"/>'
        b'<path d="M 40 65 Q 50 70 60 65" stroke="white" stroke-width="2" fill="none"/></svg>'
    )

    (space_dir / "046-rocket.svg").write_bytes(rocket_svg)
    (people_dir / "001-person.svg").write_bytes(person_svg)

    # Override the config_dir setting BEFORE app initialization
    monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(config_path))

    yield config_path

    # Cleanup
    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


async def test_list_profile_pictures(setup_profile_pictures, files_client):  # noqa: ARG001
    """Test listing profile pictures from local filesystem.

    Args:
        files_client: HTTP client for making API requests
        setup_profile_pictures: Fixture that sets up profile pictures directory
    """
    response = await files_client.get("api/v1/files/profile_pictures/list")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.json()}"

    data = response.json()
    assert "files" in data
    files = data["files"]

    # The app copies all profile pictures during initialization,
    # so we should have many files including our test ones
    assert len(files) > 0, "Should have at least some profile pictures"

    # Check that files are properly formatted as "Folder/filename"
    assert any(file.startswith("Space/") for file in files), "Should have Space profile pictures"
    assert any(file.startswith("People/") for file in files), "Should have People profile pictures"

    # Check that the rocket file exists (either our test one or the real one)
    assert "Space/046-rocket.svg" in files, "Should have the rocket profile picture"


async def test_download_profile_picture_space_rocket(setup_profile_pictures, files_client):  # noqa: ARG001
    """Test downloading the rocket profile picture from Space folder.

    Args:
        files_client: HTTP client for making API requests
        setup_profile_pictures: Fixture that sets up profile pictures directory
    """
    response = await files_client.get("api/v1/files/profile_pictures/Space/046-rocket.svg")
    assert response.status_code == 200

    # Verify content type
    assert "image/svg+xml" in response.headers["content-type"]

    # Verify content - check for SVG structure (real rocket.svg has <path> elements)
    content = response.content
    assert b"<svg" in content
    assert b"</svg>" in content
    # Real rocket has path elements, not circles
    assert len(content) > 100, "SVG content should be substantial"


async def test_download_profile_picture_people(setup_profile_pictures, files_client):  # noqa: ARG001
    """Test downloading a profile picture from People folder.

    Note: The actual people profile pictures are copied during app init,
    so we test with whatever profile picture exists.

    Args:
        files_client: HTTP client for making API requests
        setup_profile_pictures: Fixture that sets up profile pictures directory
    """
    # List available people profile pictures first
    list_response = await files_client.get("api/v1/files/profile_pictures/list")
    assert list_response.status_code == 200
    people_files = [f for f in list_response.json()["files"] if f.startswith("People/")]

    # Skip test if no people profile pictures are available
    if not people_files:
        import pytest

        pytest.skip("No people profile pictures available")

    # Test downloading the first available people profile picture
    first_people_file = people_files[0].replace("People/", "")
    response = await files_client.get(f"api/v1/files/profile_pictures/People/{first_people_file}")
    assert response.status_code == 200

    # Verify content type
    assert "image/svg+xml" in response.headers["content-type"]

    # Verify content
    content = response.content
    assert b"<svg" in content
    assert b"</svg>" in content
    assert len(content) > 100, "SVG content should be substantial"


async def test_download_profile_picture_not_found(setup_profile_pictures, files_client):  # noqa: ARG001
    """Test downloading a non-existent profile picture returns 404.

    Args:
        files_client: HTTP client for making API requests
        setup_profile_pictures: Fixture that sets up profile pictures directory
    """
    response = await files_client.get("api/v1/files/profile_pictures/Space/nonexistent.svg")
    assert response.status_code == 404

    data = response.json()
    assert "not found" in data["detail"].lower()


async def test_profile_pictures_with_s3_storage(setup_profile_pictures, files_client, monkeypatch):  # noqa: ARG001
    """Test that profile pictures work with S3 storage type.

    Profile pictures should always be served from local filesystem,
    regardless of the storage_type setting.

    Args:
        files_client: HTTP client for making API requests
        setup_profile_pictures: Fixture that sets up profile pictures directory
        monkeypatch: For overriding environment variables
    """
    # Set storage type to S3 (simulating S3 configuration)
    monkeypatch.setenv("LANGFLOW_STORAGE_TYPE", "s3")

    # List should still work (from local filesystem)
    response = await files_client.get("api/v1/files/profile_pictures/list")
    assert response.status_code == 200
    data = response.json()
    # Should have profile pictures (app copies them during init)
    assert len(data["files"]) > 0, "Should have profile pictures even with S3 storage"
    assert "Space/046-rocket.svg" in data["files"], "Should have rocket profile picture"

    # Download should still work (from local filesystem)
    response = await files_client.get("api/v1/files/profile_pictures/Space/046-rocket.svg")
    assert response.status_code == 200
    assert b"<svg" in response.content


async def test_profile_pictures_different_file_types(setup_profile_pictures, files_client):  # noqa: ARG001
    """Test that content-type headers are correct for SVG files.

    The real profile pictures are all SVG files. This test verifies
    that the content-type detection works correctly.

    Args:
        files_client: HTTP client for making API requests
        setup_profile_pictures: Fixture that sets up profile pictures directory
    """
    # Test SVG content type (all real profile pictures are SVGs)
    response = await files_client.get("api/v1/files/profile_pictures/Space/046-rocket.svg")
    assert response.status_code == 200
    assert "image/svg+xml" in response.headers["content-type"]

    # Test with a people profile picture
    list_response = await files_client.get("api/v1/files/profile_pictures/list")
    people_files = [f for f in list_response.json()["files"] if f.startswith("People/")]

    if people_files:
        first_people_file = people_files[0].replace("People/", "")
        response = await files_client.get(f"api/v1/files/profile_pictures/People/{first_people_file}")
        assert response.status_code == 200
        # All profile pictures should be SVGs
        assert "image/svg+xml" in response.headers["content-type"]
