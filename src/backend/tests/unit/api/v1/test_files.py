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


# ============================================================================
# Tests for package fallback functionality (PR #10758)
# ============================================================================


@pytest.fixture
async def empty_config_dir(monkeypatch):
    """Fixture that sets up an empty config directory without profile pictures.

    This simulates the scenario where copy_profile_pictures() was never called,
    so the endpoints should fallback to the package bundled profile pictures.
    """
    temp_dir = tempfile.mkdtemp()
    config_path = Path(temp_dir)

    # Create an empty profile_pictures directory (no files inside)
    (config_path / "profile_pictures").mkdir(parents=True, exist_ok=True)

    # Override the config_dir setting BEFORE app initialization
    monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(config_path))

    yield config_path

    # Cleanup
    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


async def test_download_profile_picture_fallback_to_package(empty_config_dir, files_client):  # noqa: ARG001
    """Test that profile pictures fallback to package when not in config_dir.

    This tests the core fix from PR #10758 - when profile pictures don't exist
    in config_dir, they should be served from the package's bundled directory.
    """
    # The 046-rocket.svg should be found in the package's bundled directory
    response = await files_client.get("api/v1/files/profile_pictures/Space/046-rocket.svg")
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}. Fallback to package profile pictures should work."
    )

    # Verify content type
    assert "image/svg+xml" in response.headers["content-type"]

    # Verify SVG content
    content = response.content
    assert b"<svg" in content
    assert b"</svg>" in content


async def test_list_profile_pictures_fallback_to_package(empty_config_dir, files_client):  # noqa: ARG001
    """Test that list endpoint fallbacks to package when config_dir is empty.

    This tests the list fallback from PR #10758 - when config_dir has no
    profile pictures, it should list from the package's bundled directory.
    """
    response = await files_client.get("api/v1/files/profile_pictures/list")
    assert response.status_code == 200

    data = response.json()
    assert "files" in data
    files = data["files"]

    # Should have files from the package
    assert len(files) > 0, "Should have profile pictures from package fallback"
    assert any(f.startswith("Space/") for f in files), "Should have Space profile pictures"
    assert any(f.startswith("People/") for f in files), "Should have People profile pictures"

    # The bundled rocket should be available
    assert "Space/046-rocket.svg" in files


async def test_download_profile_picture_not_found_in_both_locations(empty_config_dir, files_client):  # noqa: ARG001
    """Test 404 when profile picture doesn't exist in config_dir OR package.

    This ensures the fallback logic correctly returns 404 when the file
    is not found in either location.
    """
    response = await files_client.get("api/v1/files/profile_pictures/Space/nonexistent-file-xyz.svg")
    assert response.status_code == 404

    data = response.json()
    assert "not found" in data["detail"].lower()
    assert "Space/nonexistent-file-xyz.svg" in data["detail"]


async def test_download_profile_picture_invalid_folder(empty_config_dir, files_client):  # noqa: ARG001
    """Test 400 when using an invalid folder name.

    Only 'People' and 'Space' folders are whitelisted for security.
    Invalid folder names should be rejected with 400 Bad Request.
    """
    response = await files_client.get("api/v1/files/profile_pictures/InvalidFolder/file.svg")
    assert response.status_code == 400

    data = response.json()
    # Check for the new specific error message
    assert "folder must be one of" in data["detail"].lower()


async def test_download_profile_picture_config_dir_takes_precedence(setup_profile_pictures, files_client):
    """Test that config_dir profile pictures take precedence over package.

    When a file exists in both config_dir and package, the config_dir
    version should be served.
    """
    config_path = setup_profile_pictures

    # Create a custom rocket SVG in config_dir with identifiable content
    custom_svg = b'<svg xmlns="http://www.w3.org/2000/svg"><text>CUSTOM_CONFIG_DIR_VERSION</text></svg>'
    space_dir = config_path / "profile_pictures" / "Space"
    space_dir.mkdir(parents=True, exist_ok=True)
    (space_dir / "046-rocket.svg").write_bytes(custom_svg)

    response = await files_client.get("api/v1/files/profile_pictures/Space/046-rocket.svg")
    assert response.status_code == 200

    # Should get the config_dir version, not the package version
    content = response.content
    assert b"CUSTOM_CONFIG_DIR_VERSION" in content


async def test_list_profile_pictures_config_dir_takes_precedence(setup_profile_pictures, files_client):
    """Test that config_dir listing takes precedence over package.

    When config_dir has profile pictures, they should be listed instead
    of the package's bundled ones.
    """
    config_path = setup_profile_pictures

    # Ensure we have a file in config_dir
    space_dir = config_path / "profile_pictures" / "Space"
    space_dir.mkdir(parents=True, exist_ok=True)
    (space_dir / "custom-test-file.svg").write_bytes(b"<svg></svg>")

    response = await files_client.get("api/v1/files/profile_pictures/list")
    assert response.status_code == 200

    data = response.json()
    files = data["files"]

    # Should include our custom file from config_dir
    assert "Space/custom-test-file.svg" in files


async def test_download_profile_picture_path_traversal_attempt(empty_config_dir, files_client):  # noqa: ARG001
    """Test that path traversal attacks are prevented.

    Attempting to access files outside the profile_pictures directory
    using '../' should not work.
    """
    # Try path traversal to access parent directories
    response = await files_client.get("api/v1/files/profile_pictures/../../../etc/passwd")
    # Should either be 404 (file not found) or the path should be sanitized
    assert response.status_code in [404, 500]


async def test_download_profile_picture_special_characters_in_filename(empty_config_dir, files_client):  # noqa: ARG001
    """Test handling of special characters in filename.

    Filenames with spaces or special characters should be handled properly.
    """
    # Test with URL-encoded space (the real file has a space: "042-space shuttle.svg")
    response = await files_client.get("api/v1/files/profile_pictures/Space/042-space%20shuttle.svg")
    # Should work if the file exists with that name, or 404 if not
    assert response.status_code in [200, 404]


async def test_list_profile_pictures_empty_response_format(empty_config_dir, files_client):  # noqa: ARG001
    """Test that the list response format is correct even with fallback.

    The response should always have the correct format: {"files": [...]}
    """
    response = await files_client.get("api/v1/files/profile_pictures/list")
    assert response.status_code == 200

    data = response.json()

    # Verify response structure
    assert isinstance(data, dict)
    assert "files" in data
    assert isinstance(data["files"], list)

    # Verify file path format (should be "Folder/filename")
    for file_path in data["files"]:
        assert "/" in file_path, f"File path should contain '/': {file_path}"
        folder, filename = file_path.split("/", 1)
        assert folder in ["People", "Space"], f"Invalid folder: {folder}"
        assert len(filename) > 0, "Filename should not be empty"


async def test_download_profile_picture_content_is_valid_svg(empty_config_dir, files_client):  # noqa: ARG001
    """Test that downloaded profile pictures are valid SVG files.

    This ensures the fallback serves actual SVG content, not corrupted data.
    """
    # Download the rocket from package fallback
    response = await files_client.get("api/v1/files/profile_pictures/Space/046-rocket.svg")
    assert response.status_code == 200

    content = response.content

    # Verify it's valid XML/SVG
    assert content.startswith((b"<", b"<?xml")), "Should start with XML/SVG tag"
    assert b"<svg" in content.lower(), "Should contain svg tag"
    assert b"</svg>" in content.lower(), "Should have closing svg tag"


@pytest.fixture
async def partial_config_dir(monkeypatch):
    """Fixture that sets up a config directory with only People folder (no Space).

    This tests the edge case where config_dir is partially populated.
    """
    temp_dir = tempfile.mkdtemp()
    config_path = Path(temp_dir)

    # Create only People directory with a file
    people_dir = config_path / "profile_pictures" / "People"
    people_dir.mkdir(parents=True, exist_ok=True)
    (people_dir / "test-person.svg").write_bytes(b"<svg><circle/></svg>")

    # Note: Space directory is NOT created intentionally

    # Override the config_dir setting BEFORE app initialization
    monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(config_path))

    yield config_path

    # Cleanup
    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


async def test_profile_pictures_fallback_with_partial_config_dir(partial_config_dir, files_client):  # noqa: ARG001
    """Test fallback when config_dir has only People folder but not Space.

    This is an edge case where config_dir is partially populated.
    """
    # For list: since we have at least one file in People, it should NOT fallback completely
    # The current implementation only falls back if BOTH people AND space are empty
    response = await files_client.get("api/v1/files/profile_pictures/list")
    assert response.status_code == 200

    data = response.json()
    files = data["files"]

    # Should have our People file from config_dir
    assert "People/test-person.svg" in files

    # For download: Space files should still work via fallback to package
    response = await files_client.get("api/v1/files/profile_pictures/Space/046-rocket.svg")
    assert response.status_code == 200, "Space files should fallback to package"


# ============================================================================
# Tests for image download endpoint
# These tests ensure the /images endpoint works correctly for browser <img> tags.
# Regression tests for the fix that reverted commit 7ba8c73 changes to /images.
# ============================================================================


async def test_download_image_for_browser(files_client, files_created_api_key, files_flow):
    """Test that images can be downloaded for browser <img> tag rendering.

    Regression test: commit 7ba8c73 broke browser image display.
    """
    headers = {"x-api-key": files_created_api_key.api_key}

    # First upload an image (this requires auth)
    # Create a minimal valid PNG (1x1 transparent pixel)
    png_content = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    response = await files_client.post(
        f"api/v1/files/upload/{files_flow.id}",
        files={"file": ("test_image.png", png_content, "image/png")},
        headers=headers,
    )
    assert response.status_code == 201, f"Upload failed: {response.json()}"

    # Get the actual filename from the response
    file_path = response.json()["file_path"]
    file_name = file_path.split("/")[-1]

    # Download the image - simulates browser <img> tag behavior
    response = await files_client.get(
        f"api/v1/files/images/{files_flow.id}/{file_name}",
    )

    assert response.status_code == 200, (
        f"Image download failed with {response.status_code}. This breaks browser <img> tags in chat."
    )

    # Verify content type is image
    assert "image" in response.headers.get("content-type", ""), "Response should be an image"


async def test_download_image_returns_correct_content_type(files_client, files_created_api_key, files_flow):
    """Test that the /images endpoint returns correct content-type for images."""
    headers = {"x-api-key": files_created_api_key.api_key}

    # Create a minimal valid PNG
    png_content = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    response = await files_client.post(
        f"api/v1/files/upload/{files_flow.id}",
        files={"file": ("test.png", png_content, "image/png")},
        headers=headers,
    )
    assert response.status_code == 201

    file_path = response.json()["file_path"]
    file_name = file_path.split("/")[-1]

    # Download image
    response = await files_client.get(f"api/v1/files/images/{files_flow.id}/{file_name}")

    assert response.status_code == 200
    assert "image/png" in response.headers.get("content-type", "")


async def test_download_image_rejects_non_image_files(files_client, files_created_api_key, files_flow):
    """Test that the /images endpoint rejects non-image files."""
    headers = {"x-api-key": files_created_api_key.api_key}

    # Upload a text file
    response = await files_client.post(
        f"api/v1/files/upload/{files_flow.id}",
        files={"file": ("test.txt", b"not an image", "text/plain")},
        headers=headers,
    )
    assert response.status_code == 201

    file_path = response.json()["file_path"]
    file_name = file_path.split("/")[-1]

    # Try to download via /images endpoint (should fail)
    response = await files_client.get(f"api/v1/files/images/{files_flow.id}/{file_name}")

    # Should reject non-image content types
    assert response.status_code == 500
    assert "not an image" in response.json().get("detail", "").lower()


async def test_download_image_with_invalid_flow_id(files_client):
    """Test that /images returns 500 for non-existent flow_id."""
    import uuid

    fake_flow_id = uuid.uuid4()

    response = await files_client.get(f"api/v1/files/images/{fake_flow_id}/nonexistent.png")

    # Should return 500 (file not found)
    assert response.status_code == 500


async def test_download_image_browser_compatible(files_client, files_created_api_key, files_flow):
    """Test that /images endpoint works for browser <img> tag rendering.

    This ensures the endpoint correctly serves images for chat display.
    """
    headers = {"x-api-key": files_created_api_key.api_key}

    # Upload an image
    png_content = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    upload_response = await files_client.post(
        f"api/v1/files/upload/{files_flow.id}",
        files={"file": ("browser_test.png", png_content, "image/png")},
        headers=headers,
    )
    assert upload_response.status_code == 201

    file_path = upload_response.json()["file_path"]
    file_name = file_path.split("/")[-1]

    # Download - simulates browser <img> tag
    download_response = await files_client.get(f"api/v1/files/images/{files_flow.id}/{file_name}")

    assert download_response.status_code == 200, (
        f"REGRESSION: /images endpoint broken! "
        f"Got status {download_response.status_code}. "
        "This breaks browser <img> tags in chat."
    )


# ============================================================================
# Tests for path traversal protection (ValidatedFileName)
# ============================================================================


@pytest.mark.parametrize(
    "malicious_filename",
    [
        # Backslash-based traversal (Windows style)
        "..\\..\\..\\etc\\passwd",
        "..\\secret.txt",
        # Double-dot embedded in filename
        "..txt",
        "test..secret",
    ],
)
async def test_download_file_path_traversal_rejected(
    files_client, files_created_api_key, files_flow, malicious_filename
):
    """Test that path traversal attempts are rejected on /download endpoint."""
    headers = {"x-api-key": files_created_api_key.api_key}

    response = await files_client.get(
        f"api/v1/files/download/{files_flow.id}/{malicious_filename}",
        headers=headers,
    )

    assert response.status_code == 400, f"Path traversal should be rejected: {malicious_filename}"
    assert "invalid file name" in response.json()["detail"].lower()
    assert "simple file name" in response.json()["detail"].lower()


@pytest.mark.parametrize(
    "malicious_filename",
    [
        # Forward slashes in URL path are treated as path separators by FastAPI,
        # so the router returns 404 (route not found) - this is defense in depth
        "../../../etc/passwd",
        "../secret.txt",
        "subdir/file.txt",
        # URL-encoded forward slashes are also decoded by FastAPI and treated as path separators
        "..%2F..%2F..%2Fetc%2Fpasswd",
        "subdir%2Ffile.txt",
    ],
)
async def test_download_file_forward_slash_traversal_blocked(
    files_client, files_created_api_key, files_flow, malicious_filename
):
    """Test that forward slash path traversal is blocked by FastAPI routing.

    FastAPI treats both literal and URL-encoded forward slashes as path separators,
    providing defense in depth before our validation layer is reached.
    """
    headers = {"x-api-key": files_created_api_key.api_key}
    url = f"api/v1/files/download/{files_flow.id}/{malicious_filename}"
    response = await files_client.get(url, headers=headers)

    # FastAPI returns 404 because the path with slashes doesn't match any route
    assert response.status_code == 404, (
        f"Forward slash traversal should be blocked by routing: {malicious_filename}, got {response.status_code}"
    )


@pytest.mark.parametrize(
    "malicious_filename",
    [
        # Backslash-based traversal (Windows style)
        "..\\..\\..\\etc\\passwd.png",
        "..\\secret.png",
        # Double-dot embedded in filename
        "..png",
    ],
)
async def test_download_image_path_traversal_rejected(files_client, files_flow, malicious_filename):
    """Test that path traversal attempts are rejected on /images endpoint."""
    response = await files_client.get(
        f"api/v1/files/images/{files_flow.id}/{malicious_filename}",
    )

    assert response.status_code == 400, f"Path traversal should be rejected: {malicious_filename}"
    assert "invalid file name" in response.json()["detail"].lower()
    assert "simple file name" in response.json()["detail"].lower()


@pytest.mark.parametrize(
    "malicious_filename",
    [
        # Forward slashes in URL path are treated as path separators by FastAPI,
        # so the router returns 404 (route not found) - this is defense in depth
        "../../../etc/passwd.png",
        "../secret.png",
        "subdir/image.png",
        # URL-encoded forward slashes are also decoded by FastAPI and treated as path separators
        "..%2F..%2Fimage.png",
        "subdir%2Fimage.png",
    ],
)
async def test_download_image_forward_slash_traversal_blocked(files_client, files_flow, malicious_filename):
    """Test that forward slash path traversal is blocked by FastAPI routing on /images endpoint."""
    url = f"api/v1/files/images/{files_flow.id}/{malicious_filename}"
    response = await files_client.get(url)

    # FastAPI returns 404 because the path with slashes doesn't match any route
    assert response.status_code == 404, (
        f"Forward slash traversal should be blocked by routing: {malicious_filename}, got {response.status_code}"
    )


@pytest.mark.parametrize(
    "malicious_filename",
    [
        # Backslash-based traversal (Windows style)
        "..\\..\\..\\etc\\passwd",
        "..\\secret.txt",
        # Double-dot embedded in filename
        "..txt",
    ],
)
async def test_delete_file_path_traversal_rejected(files_client, files_created_api_key, files_flow, malicious_filename):
    """Test that path traversal attempts are rejected on /delete endpoint."""
    headers = {"x-api-key": files_created_api_key.api_key}

    response = await files_client.delete(
        f"api/v1/files/delete/{files_flow.id}/{malicious_filename}",
        headers=headers,
    )

    assert response.status_code == 400, f"Path traversal should be rejected: {malicious_filename}"
    assert "invalid file name" in response.json()["detail"].lower()
    assert "simple file name" in response.json()["detail"].lower()


@pytest.mark.parametrize(
    "malicious_filename",
    [
        # Forward slashes in URL path are treated as path separators by FastAPI,
        # so the router returns 404 (route not found) - this is defense in depth
        "../../../etc/passwd",
        "../secret.txt",
        "subdir/file.txt",
        # URL-encoded forward slashes are also decoded by FastAPI and treated as path separators
        "..%2F..%2F..%2Fetc%2Fpasswd",
        "subdir%2Ffile.txt",
    ],
)
async def test_delete_file_forward_slash_traversal_blocked(
    files_client, files_created_api_key, files_flow, malicious_filename
):
    """Test that forward slash path traversal is blocked by FastAPI routing on /delete endpoint."""
    headers = {"x-api-key": files_created_api_key.api_key}
    url = f"api/v1/files/delete/{files_flow.id}/{malicious_filename}"
    response = await files_client.delete(url, headers=headers)

    # FastAPI returns 404 because the path with slashes doesn't match any route
    assert response.status_code == 404, (
        f"Forward slash traversal should be blocked by routing: {malicious_filename}, got {response.status_code}"
    )
