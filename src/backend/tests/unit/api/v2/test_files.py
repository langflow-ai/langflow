import asyncio
import tempfile
from contextlib import suppress
from pathlib import Path

# we need to import tmpdir
import anyio
import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from langflow.api.v2.mcp import get_mcp_file
from langflow.main import create_app
from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.deps import get_db_service
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
