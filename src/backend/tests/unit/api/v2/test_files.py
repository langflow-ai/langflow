import asyncio
import contextlib
import json
import os
import tempfile
import uuid
from contextlib import suppress
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# we need to import tmpdir
import anyio
import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from langflow.api.v2.files import (
    delete_all_files,
    delete_file,
    delete_files_batch,
    is_permanent_storage_failure,
)
from langflow.api.v2.mcp import get_mcp_file
from langflow.main import create_app
from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.api_key.model import ApiKey, UnmaskedApiKeyRead
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
            existing_api_key = UnmaskedApiKeyRead.model_validate(existing_api_key, from_attributes=True)
            yield existing_api_key
            return
        session.add(api_key)
        await session.flush()
        await session.refresh(api_key)
        api_key = UnmaskedApiKeyRead.model_validate(api_key, from_attributes=True)

    yield api_key

    async with session_scope() as session:
        db_key = await session.get(ApiKey, api_key.id)
        if db_key:
            await session.delete(db_key)


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


async def test_upload_file(files_client, files_created_api_key):
    headers = {"x-api-key": files_created_api_key.api_key}

    response = await files_client.post(
        "api/v2/files",
        files={"file": ("test.txt", b"test content")},
        headers=headers,
    )
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.json()}"

    response_json = response.json()
    assert "id" in response_json


async def test_download_file(files_client, files_created_api_key):
    headers = {"x-api-key": files_created_api_key.api_key}

    # First upload a file
    response = await files_client.post(
        "api/v2/files",
        files={"file": ("test.txt", b"test content")},
        headers=headers,
    )
    assert response.status_code == 201
    upload_response = response.json()

    # Then try to download it
    response = await files_client.get(f"api/v2/files/{upload_response['id']}", headers=headers)

    assert response.status_code == 200
    assert response.content == b"test content"


async def test_download_file_not_found(files_client, files_created_api_key):
    """Test that downloading a non-existent file returns 404 error."""
    headers = {"x-api-key": files_created_api_key.api_key}

    # Try to download a file that doesn't exist
    fake_file_id = "00000000-0000-0000-0000-000000000000"
    response = await files_client.get(f"api/v2/files/{fake_file_id}", headers=headers)

    assert response.status_code == 404
    error_response = response.json()
    assert "File not found" in error_response["detail"]


async def test_list_files(files_client, files_created_api_key):
    headers = {"x-api-key": files_created_api_key.api_key}

    # First upload a file
    response = await files_client.post(
        "api/v2/files",
        files={"file": ("test.txt", b"test content")},
        headers=headers,
    )
    assert response.status_code == 201

    # Then list the files
    response = await files_client.get("api/v2/files", headers=headers)
    assert response.status_code == 200
    files = response.json()
    assert len(files) == 1


async def test_delete_file(files_client, files_created_api_key):
    headers = {"x-api-key": files_created_api_key.api_key}

    response = await files_client.post(
        "api/v2/files",
        files={"file": ("test.txt", b"test content")},
        headers=headers,
    )
    assert response.status_code == 201
    upload_response = response.json()

    response = await files_client.delete(f"api/v2/files/{upload_response['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"detail": "File test deleted successfully"}


async def test_edit_file(files_client, files_created_api_key):
    headers = {"x-api-key": files_created_api_key.api_key}

    # First upload a file
    response = await files_client.post(
        "api/v2/files",
        files={"file": ("test.txt", b"test content")},
        headers=headers,
    )
    assert response.status_code == 201
    upload_response = response.json()

    # Then list the files
    response = await files_client.put(f"api/v2/files/{upload_response['id']}?name=potato.txt", headers=headers)
    assert response.status_code == 200
    file = response.json()
    assert file["name"] == "potato.txt"


async def test_upload_list_delete_and_validate_files(files_client, files_created_api_key):
    headers = {"x-api-key": files_created_api_key.api_key}

    # Upload two files
    response1 = await files_client.post(
        "api/v2/files",
        files={"file": ("file1.txt", b"content1")},
        headers=headers,
    )
    assert response1.status_code == 201
    file1 = response1.json()

    response2 = await files_client.post(
        "api/v2/files",
        files={"file": ("file2.txt", b"content2")},
        headers=headers,
    )
    assert response2.status_code == 201
    file2 = response2.json()

    # List files and validate both are present
    response = await files_client.get("api/v2/files", headers=headers)
    assert response.status_code == 200
    files = response.json()
    file_names = [f["name"] for f in files]
    file_ids = [f["id"] for f in files]
    assert file1["name"] in file_names
    assert file2["name"] in file_names
    assert file1["id"] in file_ids
    assert file2["id"] in file_ids
    assert len(files) == 2

    # Delete one file
    response = await files_client.delete(f"api/v2/files/{file1['id']}", headers=headers)
    assert response.status_code == 200

    # List files again and validate only the other remains
    response = await files_client.get("api/v2/files", headers=headers)
    assert response.status_code == 200
    files = response.json()
    file_names = [f["name"] for f in files]
    file_ids = [f["id"] for f in files]
    assert file1["name"] not in file_names
    assert file1["id"] not in file_ids
    assert file2["name"] in file_names
    assert file2["id"] in file_ids
    assert len(files) == 1


async def test_upload_files_with_same_name_creates_unique_names(files_client, files_created_api_key):
    """Test that uploading files with the same name creates unique filenames."""
    headers = {"x-api-key": files_created_api_key.api_key}

    # Upload first file
    response1 = await files_client.post(
        "api/v2/files",
        files={"file": ("duplicate.txt", b"content1")},
        headers=headers,
    )
    assert response1.status_code == 201
    file1 = response1.json()
    assert file1["name"] == "duplicate"

    # Upload second file with same name
    response2 = await files_client.post(
        "api/v2/files",
        files={"file": ("duplicate.txt", b"content2")},
        headers=headers,
    )
    assert response2.status_code == 201
    file2 = response2.json()
    assert file2["name"] == "duplicate (1)"

    # Upload third file with same name
    response3 = await files_client.post(
        "api/v2/files",
        files={"file": ("duplicate.txt", b"content3")},
        headers=headers,
    )
    assert response3.status_code == 201
    file3 = response3.json()
    assert file3["name"] == "duplicate (2)"

    # Verify all files can be downloaded with their unique content
    download1 = await files_client.get(f"api/v2/files/{file1['id']}", headers=headers)
    assert download1.status_code == 200
    assert download1.content == b"content1"

    download2 = await files_client.get(f"api/v2/files/{file2['id']}", headers=headers)
    assert download2.status_code == 200
    assert download2.content == b"content2"

    download3 = await files_client.get(f"api/v2/files/{file3['id']}", headers=headers)
    assert download3.status_code == 200
    assert download3.content == b"content3"

    # List files and verify all three are present with unique names
    response = await files_client.get("api/v2/files", headers=headers)
    assert response.status_code == 200
    files = response.json()
    file_names = [f["name"] for f in files]
    assert "duplicate" in file_names
    assert "duplicate (1)" in file_names
    assert "duplicate (2)" in file_names
    assert len(files) == 3


async def test_upload_files_without_extension_creates_unique_names(files_client, files_created_api_key):
    """Test that uploading files without extensions also creates unique filenames."""
    headers = {"x-api-key": files_created_api_key.api_key}

    # Upload first file without extension
    response1 = await files_client.post(
        "api/v2/files",
        files={"file": ("noextension", b"content1")},
        headers=headers,
    )
    assert response1.status_code == 201
    file1 = response1.json()
    assert file1["name"] == "noextension"

    # Upload second file with same name
    response2 = await files_client.post(
        "api/v2/files",
        files={"file": ("noextension", b"content2")},
        headers=headers,
    )
    assert response2.status_code == 201
    file2 = response2.json()
    assert file2["name"] == "noextension (1)"

    # Verify both files can be downloaded
    download1 = await files_client.get(f"api/v2/files/{file1['id']}", headers=headers)
    assert download1.status_code == 200
    assert download1.content == b"content1"

    download2 = await files_client.get(f"api/v2/files/{file2['id']}", headers=headers)
    assert download2.status_code == 200
    assert download2.content == b"content2"


async def test_upload_files_with_different_extensions_same_name(files_client, files_created_api_key):
    """Test that files with same root name but different extensions create unique names."""
    headers = {"x-api-key": files_created_api_key.api_key}

    # Upload file with .txt extension
    response1 = await files_client.post(
        "api/v2/files",
        files={"file": ("document.txt", b"text content")},
        headers=headers,
    )
    assert response1.status_code == 201
    file1 = response1.json()
    assert file1["name"] == "document"

    # Upload file with .md extension and same root name
    response2 = await files_client.post(
        "api/v2/files",
        files={"file": ("document.md", b"markdown content")},
        headers=headers,
    )
    assert response2.status_code == 201
    file2 = response2.json()
    assert file2["name"] == "document (1)"

    # Upload another .txt file with same root name
    response3 = await files_client.post(
        "api/v2/files",
        files={"file": ("document.txt", b"more text content")},
        headers=headers,
    )
    assert response3.status_code == 201
    file3 = response3.json()
    assert file3["name"] == "document (2)"


async def test_mcp_servers_file_replacement(files_client, files_created_api_key, files_active_user):
    """Test that _mcp_servers file gets replaced instead of creating unique names."""
    headers = {"x-api-key": files_created_api_key.api_key}

    mcp_file_ext = await get_mcp_file(files_active_user, extension=True)
    mcp_file = await get_mcp_file(files_active_user)

    # Upload first _mcp_servers file
    response1 = await files_client.post(
        "api/v2/files",
        files={"file": (mcp_file_ext, b'{"servers": ["server1"]}')},
        headers=headers,
    )
    assert response1.status_code == 201
    file1 = response1.json()
    assert file1["name"] == mcp_file

    # Upload second _mcp_servers file - should replace the first one
    response2 = await files_client.post(
        "api/v2/files",
        files={"file": (mcp_file_ext, b'{"servers": ["server2"]}')},
        headers=headers,
    )
    assert response2.status_code == 201
    file2 = response2.json()
    assert file2["name"] == mcp_file

    # Note: _mcp_servers files are filtered out from the regular file list
    # This is expected behavior since they're managed separately
    response = await files_client.get("api/v2/files", headers=headers)
    assert response.status_code == 200
    files = response.json()
    mcp_files = [f for f in files if f["name"] == mcp_file]
    assert len(mcp_files) == 0  # MCP servers files are filtered out from regular list

    # Verify the second file can be downloaded with the updated content
    download2 = await files_client.get(f"api/v2/files/{file2['id']}", headers=headers)
    assert download2.status_code == 200
    assert download2.content == b'{"servers": ["server2"]}'

    # Verify the first file no longer exists (should return 404)
    download1 = await files_client.get(f"api/v2/files/{file1['id']}", headers=headers)
    assert download1.status_code == 404

    # Verify the file IDs are different (new file replaced old one)
    assert file1["id"] != file2["id"]


async def test_unique_filename_counter_handles_gaps(files_client, files_created_api_key):
    """Test that the unique filename counter properly handles gaps in sequence."""
    headers = {"x-api-key": files_created_api_key.api_key}

    # Upload original file
    response1 = await files_client.post(
        "api/v2/files",
        files={"file": ("gaptest.txt", b"content1")},
        headers=headers,
    )
    assert response1.status_code == 201
    file1 = response1.json()
    assert file1["name"] == "gaptest"

    # Upload second file (should be gaptest (1))
    response2 = await files_client.post(
        "api/v2/files",
        files={"file": ("gaptest.txt", b"content2")},
        headers=headers,
    )
    assert response2.status_code == 201
    file2 = response2.json()
    assert file2["name"] == "gaptest (1)"

    # Upload third file (should be gaptest (2))
    response3 = await files_client.post(
        "api/v2/files",
        files={"file": ("gaptest.txt", b"content3")},
        headers=headers,
    )
    assert response3.status_code == 201
    file3 = response3.json()
    assert file3["name"] == "gaptest (2)"

    # Delete the middle file (gaptest (1))
    delete_response = await files_client.delete(f"api/v2/files/{file2['id']}", headers=headers)
    assert delete_response.status_code == 200

    # Upload another file - should be gaptest (3), not filling the gap
    response4 = await files_client.post(
        "api/v2/files",
        files={"file": ("gaptest.txt", b"content4")},
        headers=headers,
    )
    assert response4.status_code == 201
    file4 = response4.json()
    assert file4["name"] == "gaptest (3)"

    # Verify final state
    response = await files_client.get("api/v2/files", headers=headers)
    assert response.status_code == 200
    files = response.json()
    file_names = [f["name"] for f in files]
    assert "gaptest" in file_names
    assert "gaptest (1)" not in file_names  # deleted
    assert "gaptest (2)" in file_names
    assert "gaptest (3)" in file_names
    assert len([name for name in file_names if name.startswith("gaptest")]) == 3


async def test_unique_filename_path_storage(files_client, files_created_api_key):
    """Test that files with unique names are stored with unique paths."""
    headers = {"x-api-key": files_created_api_key.api_key}

    # Upload two files with same name
    response1 = await files_client.post(
        "api/v2/files",
        files={"file": ("pathtest.txt", b"path content 1")},
        headers=headers,
    )
    assert response1.status_code == 201
    file1 = response1.json()

    response2 = await files_client.post(
        "api/v2/files",
        files={"file": ("pathtest.txt", b"path content 2")},
        headers=headers,
    )
    assert response2.status_code == 201
    file2 = response2.json()

    # Verify both files have different paths and can be downloaded independently
    assert file1["path"] != file2["path"]

    download1 = await files_client.get(f"api/v2/files/{file1['id']}", headers=headers)
    assert download1.status_code == 200
    assert download1.content == b"path content 1"

    download2 = await files_client.get(f"api/v2/files/{file2['id']}", headers=headers)
    assert download2.status_code == 200
    assert download2.content == b"path content 2"


# ==================== S3 STORAGE TESTS ====================


@pytest.fixture
def aws_credentials():
    """Verify AWS credentials are set via environment variables."""
    required_vars = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]
    missing_vars = [var for var in required_vars if not os.environ.get(var)]

    if missing_vars:
        pytest.skip(f"Missing required environment variables: {', '.join(missing_vars)}")

    # Set default region if not provided
    if not os.environ.get("AWS_DEFAULT_REGION"):
        os.environ["AWS_DEFAULT_REGION"] = "us-west-2"

    # No cleanup needed - we're using existing env vars


@pytest.fixture(name="s3_files_created_api_key")
async def s3_files_created_api_key(s3_files_client, s3_files_active_user):  # noqa: ARG001
    hashed = get_password_hash("s3_random_key")
    api_key = ApiKey(
        name="s3_files_created_api_key",
        user_id=s3_files_active_user.id,
        api_key="s3_random_key",  # pragma: allowlist secret
        hashed_api_key=hashed,
    )
    async with session_scope() as session:
        stmt = select(ApiKey).where(ApiKey.api_key == api_key.api_key)
        if existing_api_key := (await session.exec(stmt)).first():
            existing_api_key = UnmaskedApiKeyRead.model_validate(existing_api_key, from_attributes=True)
            yield existing_api_key
            return
        session.add(api_key)
        await session.flush()
        await session.refresh(api_key)
        api_key = UnmaskedApiKeyRead.model_validate(api_key, from_attributes=True)

    yield api_key

    async with session_scope() as session:
        db_key = await session.get(ApiKey, api_key.id)
        if db_key:
            await session.delete(db_key)


@pytest.fixture(name="s3_files_active_user")
async def s3_files_active_user(s3_files_client):  # noqa: ARG001
    async with session_scope() as session:
        user = User(
            username="s3_files_active_user",
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


@pytest.fixture(name="s3_files_client")
async def s3_files_client_fixture(
    monkeypatch,
    request,
    aws_credentials,  # noqa: ARG001
):
    """S3 storage client fixture for testing with real S3."""
    # Set the database url to a test database
    if "noclient" in request.keywords:
        yield
    else:

        def init_app():
            db_dir = tempfile.mkdtemp()
            db_path = Path(db_dir) / "test_s3.db"
            monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite:///{db_path}")
            monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "false")
            # Configure S3 storage
            monkeypatch.setenv("LANGFLOW_STORAGE_TYPE", "s3")
            monkeypatch.setenv(
                "LANGFLOW_OBJECT_STORAGE_BUCKET_NAME",
                os.environ.get("LANGFLOW_OBJECT_STORAGE_BUCKET_NAME", "langflow-ci"),
            )
            # Use unique prefix per test run to avoid conflicts
            test_prefix = f"test-files-api-{uuid.uuid4().hex[:8]}"
            monkeypatch.setenv("LANGFLOW_OBJECT_STORAGE_PREFIX", test_prefix)
            tags_json = json.dumps({"env": "test-api", "type": "file-upload"})
            monkeypatch.setenv("LANGFLOW_OBJECT_STORAGE_TAGS", tags_json)

            from langflow.services.manager import service_manager

            service_manager.factories.clear()
            service_manager.services.clear()  # Clear the services cache
            app = create_app()
            return app, db_path, test_prefix

        app, db_path, test_prefix = await asyncio.to_thread(init_app)

        async with (
            LifespanManager(app, startup_timeout=None, shutdown_timeout=None) as manager,
            AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://testserver/") as client,
        ):
            yield client

        # Cleanup: Delete all test files from S3
        try:
            import boto3

            s3 = boto3.client("s3")
            bucket_name = os.environ.get("LANGFLOW_OBJECT_STORAGE_BUCKET_NAME", "langflow-ci")

            # List and delete all objects with our test prefix
            with contextlib.suppress(Exception):
                response = s3.list_objects_v2(Bucket=bucket_name, Prefix=test_prefix)
                if "Contents" in response:
                    for obj in response["Contents"]:
                        s3.delete_object(Bucket=bucket_name, Key=obj["Key"])
        except Exception:  # noqa: S110
            pass  # Ignore cleanup errors - outer exception handler

        monkeypatch.undo()
        # clear the temp db
        with suppress(FileNotFoundError):
            await anyio.Path(db_path).unlink()


# Mark all S3 tests as requiring API keys
pytestmark_s3 = pytest.mark.api_key_required


@pytest.mark.api_key_required
class TestS3FileOperations:
    """Test file operations with S3 storage backend.

    These tests use actual AWS S3 and verify that file operations work correctly
    with S3 storage, including the delete bug fix.
    """

    async def test_s3_upload_file(self, s3_files_client, s3_files_created_api_key):
        """Test uploading a file to S3 storage."""
        headers = {"x-api-key": s3_files_created_api_key.api_key}

        response = await s3_files_client.post(
            "api/v2/files",
            files={"file": ("s3_test.txt", b"S3 test content")},
            headers=headers,
        )
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.json()}"

        response_json = response.json()
        assert "id" in response_json
        assert response_json["name"] == "s3_test"

    async def test_s3_upload_and_download_file(self, s3_files_client, s3_files_created_api_key):
        """Test uploading and downloading a file with S3 storage."""
        headers = {"x-api-key": s3_files_created_api_key.api_key}

        # Upload file
        response = await s3_files_client.post(
            "api/v2/files",
            files={"file": ("s3_download_test.txt", b"S3 download content")},
            headers=headers,
        )
        assert response.status_code == 201
        upload_response = response.json()

        # Download file
        response = await s3_files_client.get(f"api/v2/files/{upload_response['id']}", headers=headers)

        assert response.status_code == 200
        assert response.content == b"S3 download content"

    async def test_s3_list_files(self, s3_files_client, s3_files_created_api_key):
        """Test listing files with S3 storage."""
        headers = {"x-api-key": s3_files_created_api_key.api_key}

        # Upload a file
        response = await s3_files_client.post(
            "api/v2/files",
            files={"file": ("s3_list_test.txt", b"S3 list content")},
            headers=headers,
        )
        assert response.status_code == 201

        # List files
        response = await s3_files_client.get("api/v2/files", headers=headers)
        assert response.status_code == 200
        files = response.json()
        assert len(files) >= 1
        file_names = [f["name"] for f in files]
        assert "s3_list_test" in file_names

    async def test_s3_delete_file(self, s3_files_client, s3_files_created_api_key):
        """Test deleting a file from S3 storage (verifies delete bug fix)."""
        headers = {"x-api-key": s3_files_created_api_key.api_key}

        # Upload a file
        response = await s3_files_client.post(
            "api/v2/files",
            files={"file": ("s3_delete_test.txt", b"S3 delete content")},
            headers=headers,
        )
        assert response.status_code == 201
        upload_response = response.json()

        # Delete the file
        response = await s3_files_client.delete(f"api/v2/files/{upload_response['id']}", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"detail": "File s3_delete_test deleted successfully"}

        # Verify file is deleted from database
        response = await s3_files_client.get("api/v2/files", headers=headers)
        assert response.status_code == 200
        files = response.json()
        file_names = [f["name"] for f in files]
        assert "s3_delete_test" not in file_names

        # Verify file is deleted from S3 (should return 404)
        response = await s3_files_client.get(f"api/v2/files/{upload_response['id']}", headers=headers)
        assert response.status_code == 404

    async def test_s3_upload_list_delete_multiple_files(self, s3_files_client, s3_files_created_api_key):
        """Test uploading, listing, and deleting multiple files with S3 storage."""
        headers = {"x-api-key": s3_files_created_api_key.api_key}

        # Upload two files
        response1 = await s3_files_client.post(
            "api/v2/files",
            files={"file": ("s3_file1.txt", b"S3 content1")},
            headers=headers,
        )
        assert response1.status_code == 201
        file1 = response1.json()

        response2 = await s3_files_client.post(
            "api/v2/files",
            files={"file": ("s3_file2.txt", b"S3 content2")},
            headers=headers,
        )
        assert response2.status_code == 201
        file2 = response2.json()

        # List files and validate both are present
        response = await s3_files_client.get("api/v2/files", headers=headers)
        assert response.status_code == 200
        files = response.json()
        file_names = [f["name"] for f in files]
        file_ids = [f["id"] for f in files]
        assert file1["name"] in file_names
        assert file2["name"] in file_names
        assert file1["id"] in file_ids
        assert file2["id"] in file_ids

        # Delete one file
        response = await s3_files_client.delete(f"api/v2/files/{file1['id']}", headers=headers)
        assert response.status_code == 200

        # List files again and validate only the other remains
        response = await s3_files_client.get("api/v2/files", headers=headers)
        assert response.status_code == 200
        files = response.json()
        file_names = [f["name"] for f in files]
        file_ids = [f["id"] for f in files]
        assert file1["name"] not in file_names
        assert file1["id"] not in file_ids
        assert file2["name"] in file_names
        assert file2["id"] in file_ids

    async def test_s3_upload_binary_file(self, s3_files_client, s3_files_created_api_key):
        """Test uploading and downloading binary data with S3 storage."""
        headers = {"x-api-key": s3_files_created_api_key.api_key}

        # Create binary data
        binary_data = bytes(range(256))

        # Upload binary file
        response = await s3_files_client.post(
            "api/v2/files",
            files={"file": ("s3_binary.bin", binary_data)},
            headers=headers,
        )
        assert response.status_code == 201
        upload_response = response.json()

        # Download and verify binary data
        response = await s3_files_client.get(f"api/v2/files/{upload_response['id']}", headers=headers)
        assert response.status_code == 200
        assert response.content == binary_data

    async def test_s3_delete_verifies_s3_cleanup(self, s3_files_client, s3_files_created_api_key):
        """Test that delete properly cleans up S3 storage (verifies the bug fix)."""
        headers = {"x-api-key": s3_files_created_api_key.api_key}

        # Upload a file
        response = await s3_files_client.post(
            "api/v2/files",
            files={"file": ("s3_cleanup_test.txt", b"S3 cleanup content")},
            headers=headers,
        )
        assert response.status_code == 201
        upload_response = response.json()

        # Get the user ID from the response path
        file_path = upload_response["path"]
        user_id = file_path.split("/")[0]

        # Delete the file
        response = await s3_files_client.delete(f"api/v2/files/{upload_response['id']}", headers=headers)
        assert response.status_code == 200

        # Verify file is actually deleted from S3 by checking directly
        import boto3

        s3 = boto3.client("s3")
        bucket_name = os.environ.get("LANGFLOW_OBJECT_STORAGE_BUCKET_NAME", "langflow-ci")

        # Extract file name from path
        file_name = file_path.split("/")[-1]

        # Build the S3 key using the correct pattern (prefix/user_id/filename)
        test_prefix = os.environ.get("LANGFLOW_OBJECT_STORAGE_PREFIX")
        s3_key = f"{test_prefix}/{user_id}/{file_name}"

        # Try to get the object - should raise NoSuchKey
        try:
            s3.head_object(Bucket=bucket_name, Key=s3_key)
            pytest.fail(f"File {s3_key} should have been deleted from S3 but still exists")
        except s3.exceptions.NoSuchKey:
            pass  # Expected - file was properly deleted
        except Exception as e:
            # Check if it's a 404-related error (different boto3 versions)
            if "404" not in str(e) and "NoSuchKey" not in str(e):
                raise


class TestStorageFailureHandling:
    """Test permanent vs transient storage failure handling in delete operations."""

    def test_is_permanent_storage_failure_file_not_found_error(self):
        """Test that FileNotFoundError is recognized as permanent failure."""
        error = FileNotFoundError("File not found")
        assert is_permanent_storage_failure(error) is True

    def test_is_permanent_storage_failure_s3_no_such_bucket(self):
        """Test that S3 NoSuchBucket error is recognized as permanent failure."""

        # Mock S3 error with NoSuchBucket code
        class MockS3Error(Exception):
            def __init__(self):
                self.response = {"Error": {"Code": "NoSuchBucket", "Message": "Bucket does not exist"}}

        error = MockS3Error()
        assert is_permanent_storage_failure(error) is True

    def test_is_permanent_storage_failure_s3_no_such_key(self):
        """Test that S3 NoSuchKey error is recognized as permanent failure."""

        # Mock S3 error with NoSuchKey code
        class MockS3Error(Exception):
            def __init__(self):
                self.response = {"Error": {"Code": "NoSuchKey", "Message": "Key does not exist"}}

        error = MockS3Error()
        assert is_permanent_storage_failure(error) is True

    def test_is_permanent_storage_failure_transient_error(self):
        """Test that transient errors (network, timeout) are not permanent failures."""

        # Mock transient errors
        class NetworkError(Exception):
            pass

        class CustomTimeoutError(Exception):
            pass

        class CustomPermissionError(Exception):
            pass

        assert is_permanent_storage_failure(NetworkError("Connection failed")) is False
        assert is_permanent_storage_failure(CustomTimeoutError("Request timed out")) is False
        assert is_permanent_storage_failure(CustomPermissionError("Access denied")) is False

    def test_is_permanent_storage_failure_fallback_string_matching(self):
        """Test fallback string matching for edge cases."""

        # Test with error messages that match permanent patterns
        class CustomError(Exception):
            pass

        assert is_permanent_storage_failure(CustomError("NoSuchBucket error")) is True
        assert is_permanent_storage_failure(CustomError("NoSuchKey error")) is True
        assert is_permanent_storage_failure(CustomError("File not found")) is True
        assert is_permanent_storage_failure(CustomError("FileNotFoundError occurred")) is True

    async def test_delete_file_with_permanent_failure_deletes_from_db(self):
        """Test that permanent storage failures still delete from database."""
        from langflow.services.database.models.file.model import File as UserFile

        file_id = uuid.uuid4()
        user_id = uuid.uuid4()
        file_name = "test_file.txt"
        file_path = f"{file_id}.txt"

        mock_file = UserFile(
            id=file_id,
            user_id=user_id,
            name=file_name,
            path=file_path,
            size=100,
        )

        mock_current_user = MagicMock()
        mock_current_user.id = user_id

        mock_exec_result = MagicMock()
        mock_exec_result.first = MagicMock(return_value=mock_file)
        mock_session = AsyncMock()
        mock_session.exec = AsyncMock(return_value=mock_exec_result)
        mock_session.delete = AsyncMock()

        mock_storage_service = AsyncMock()
        mock_storage_service.delete_file = AsyncMock(side_effect=FileNotFoundError(f"File {file_path} not found"))

        result = await delete_file(
            file_id=file_id,
            current_user=mock_current_user,
            session=mock_session,
            storage_service=mock_storage_service,
        )

        expected_file_name = file_path.split("/")[-1]
        mock_storage_service.delete_file.assert_called_once_with(
            flow_id=str(user_id),
            file_name=expected_file_name,
        )
        mock_session.delete.assert_called_once_with(mock_file)
        assert result["detail"] == f"File {file_name} deleted successfully"

    async def test_delete_file_with_transient_failure_keeps_in_db(self):
        """Test that transient storage failures keep file in database for retry."""
        from fastapi import HTTPException
        from langflow.services.database.models.file.model import File as UserFile

        file_id = uuid.uuid4()
        user_id = uuid.uuid4()
        file_name = "test_file.txt"
        file_path = f"{file_id}.txt"

        mock_file = UserFile(
            id=file_id,
            user_id=user_id,
            name=file_name,
            path=file_path,
            size=100,
        )

        mock_current_user = MagicMock()
        mock_current_user.id = user_id

        mock_exec_result = MagicMock()
        mock_exec_result.first = MagicMock(return_value=mock_file)
        mock_session = AsyncMock()
        mock_session.exec = AsyncMock(return_value=mock_exec_result)
        mock_session.delete = AsyncMock()

        mock_storage_service = AsyncMock()
        mock_storage_service.delete_file = AsyncMock(side_effect=ConnectionError("Network connection failed"))

        with pytest.raises(HTTPException) as exc_info:
            await delete_file(
                file_id=file_id,
                current_user=mock_current_user,
                session=mock_session,
                storage_service=mock_storage_service,
            )

        assert exc_info.value.status_code == 500
        assert "Failed to delete file from storage" in exc_info.value.detail

        expected_file_name = file_path.split("/")[-1]
        mock_storage_service.delete_file.assert_called_once_with(
            flow_id=str(user_id),
            file_name=expected_file_name,
        )
        mock_session.delete.assert_not_called()

    async def test_batch_delete_with_mixed_failures(self):
        """Test batch delete with mix of permanent and transient failures."""
        from langflow.services.database.models.file.model import File as UserFile

        user_id = uuid.uuid4()
        file_ids = [uuid.uuid4() for _ in range(3)]
        file_names = [f"batch_test_{i}.txt" for i in range(3)]

        mock_files = [
            UserFile(
                id=file_ids[i],
                user_id=user_id,
                name=file_names[i],
                path=f"{file_ids[i]}.txt",
                size=100,
            )
            for i in range(3)
        ]

        mock_current_user = MagicMock()
        mock_current_user.id = user_id

        mock_exec_result = MagicMock()
        mock_exec_result.all = MagicMock(return_value=mock_files)
        mock_session = AsyncMock()
        mock_session.exec = AsyncMock(return_value=mock_exec_result)
        mock_session.delete = AsyncMock()

        deleted_file_ids = set()

        async def mock_delete_file(*, flow_id: str | None = None, file_name: str | None = None) -> None:  # noqa: ARG001
            if file_name == f"{file_ids[0]}.txt":
                msg = f"File {file_name} not found"
                raise FileNotFoundError(msg)
            if file_name == f"{file_ids[1]}.txt":
                msg = "Network error"
                raise ConnectionError(msg)
            deleted_file_ids.add(file_name)

        mock_storage_service = AsyncMock()
        mock_storage_service.delete_file = AsyncMock(side_effect=mock_delete_file)

        result = await delete_files_batch(
            file_ids=file_ids,
            current_user=mock_current_user,
            session=mock_session,
            storage_service=mock_storage_service,
        )

        assert (
            result["message"]
            == "2 files deleted successfully, 1 files kept in database due to transient storage errors (can retry)"
        )

        assert mock_storage_service.delete_file.call_count == 3

        delete_calls = [call[0][0] for call in mock_session.delete.call_args_list]
        assert len(delete_calls) == 2
        assert mock_files[0] in delete_calls
        assert mock_files[2] in delete_calls
        assert mock_files[1] not in delete_calls

    async def test_delete_all_files_message_all_successful(self):
        """Test delete_all_files returns correct message when all files deleted successfully."""
        from langflow.services.database.models.file.model import File as UserFile

        user_id = uuid.uuid4()
        mock_files = [
            UserFile(
                id=uuid.uuid4(),
                user_id=user_id,
                name=f"msg_test_{i}.txt",
                path=f"{uuid.uuid4()}.txt",
                size=100,
            )
            for i in range(3)
        ]

        mock_current_user = MagicMock()
        mock_current_user.id = user_id

        mock_exec_result = MagicMock()
        mock_exec_result.all = MagicMock(return_value=mock_files)
        mock_session = AsyncMock()
        mock_session.exec = AsyncMock(return_value=mock_exec_result)
        mock_session.delete = AsyncMock()

        mock_storage_service = AsyncMock()
        mock_storage_service.delete_file = AsyncMock()

        result = await delete_all_files(
            current_user=mock_current_user,
            session=mock_session,
            storage_service=mock_storage_service,
        )

        assert result["message"] == "All 3 files deleted successfully"

    async def test_delete_all_files_message_with_transient_failures(self):
        """Test delete_all_files returns correct message when some files have transient storage failures."""
        from langflow.services.database.models.file.model import File as UserFile

        user_id = uuid.uuid4()
        mock_files = [
            UserFile(
                id=uuid.uuid4(),
                user_id=user_id,
                name=f"transient_msg_test_{i}.txt",
                path=f"{uuid.uuid4()}.txt",
                size=100,
            )
            for i in range(3)
        ]

        mock_current_user = MagicMock()
        mock_current_user.id = user_id

        mock_exec_result = MagicMock()
        mock_exec_result.all = MagicMock(return_value=mock_files)
        mock_session = AsyncMock()
        mock_session.exec = AsyncMock(return_value=mock_exec_result)
        mock_session.delete = AsyncMock()

        call_count = 0

        async def mock_delete_file(*, flow_id: str | None = None, file_name: str | None = None) -> None:  # noqa: ARG001
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                msg = "Network error"
                raise ConnectionError(msg)

        mock_storage_service = AsyncMock()
        mock_storage_service.delete_file = AsyncMock(side_effect=mock_delete_file)

        result = await delete_all_files(
            current_user=mock_current_user,
            session=mock_session,
            storage_service=mock_storage_service,
        )

        assert result["message"] == "2 files deleted successfully, 1 files failed to delete. See logs for details."

    async def test_batch_delete_message_all_successful(self):
        """Test batch delete returns correct message when all files deleted successfully."""
        from langflow.services.database.models.file.model import File as UserFile

        user_id = uuid.uuid4()
        file_ids = [uuid.uuid4() for _ in range(2)]
        mock_files = [
            UserFile(
                id=file_ids[i],
                user_id=user_id,
                name=f"batch_msg_test_{i}.txt",
                path=f"{file_ids[i]}.txt",
                size=100,
            )
            for i in range(2)
        ]

        mock_current_user = MagicMock()
        mock_current_user.id = user_id

        mock_exec_result = MagicMock()
        mock_exec_result.all = MagicMock(return_value=mock_files)
        mock_session = AsyncMock()
        mock_session.exec = AsyncMock(return_value=mock_exec_result)
        mock_session.delete = AsyncMock()

        mock_storage_service = AsyncMock()
        mock_storage_service.delete_file = AsyncMock()

        result = await delete_files_batch(
            file_ids=file_ids,
            current_user=mock_current_user,
            session=mock_session,
            storage_service=mock_storage_service,
        )

        assert result["message"] == "2 files deleted successfully"

    async def test_batch_delete_message_with_transient_failures(self):
        """Test batch delete returns correct message when some files have transient storage failures."""
        from langflow.services.database.models.file.model import File as UserFile

        user_id = uuid.uuid4()
        file_ids = [uuid.uuid4() for _ in range(3)]
        mock_files = [
            UserFile(
                id=file_ids[i],
                user_id=user_id,
                name=f"batch_transient_msg_{i}.txt",
                path=f"{file_ids[i]}.txt",
                size=100,
            )
            for i in range(3)
        ]

        mock_current_user = MagicMock()
        mock_current_user.id = user_id

        mock_exec_result = MagicMock()
        mock_exec_result.all = MagicMock(return_value=mock_files)
        mock_session = AsyncMock()
        mock_session.exec = AsyncMock(return_value=mock_exec_result)
        mock_session.delete = AsyncMock()

        call_count = 0

        async def mock_delete_file(*, flow_id: str | None = None, file_name: str | None = None) -> None:  # noqa: ARG001
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                msg = "Network error"
                raise ConnectionError(msg)

        mock_storage_service = AsyncMock()
        mock_storage_service.delete_file = AsyncMock(side_effect=mock_delete_file)

        result = await delete_files_batch(
            file_ids=file_ids,
            current_user=mock_current_user,
            session=mock_session,
            storage_service=mock_storage_service,
        )

        assert (
            result["message"]
            == "2 files deleted successfully, 1 files kept in database due to transient storage errors (can retry)"
        )
