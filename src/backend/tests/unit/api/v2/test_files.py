import asyncio
import tempfile
from contextlib import suppress
from pathlib import Path

# we need to import tmpdir
import anyio
import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from langflow.main import create_app
from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.api_key.model import ApiKey
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
            from langflow.services.manager import service_manager

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


async def test_mcp_servers_file_replacement(files_client, files_created_api_key):
    """Test that _mcp_servers file gets replaced instead of creating unique names."""
    headers = {"x-api-key": files_created_api_key.api_key}

    # Upload first _mcp_servers file
    response1 = await files_client.post(
        "api/v2/files",
        files={"file": ("_mcp_servers.json", b'{"servers": ["server1"]}')},
        headers=headers,
    )
    assert response1.status_code == 201
    file1 = response1.json()
    assert file1["name"] == "_mcp_servers"

    # Upload second _mcp_servers file - should replace the first one
    response2 = await files_client.post(
        "api/v2/files",
        files={"file": ("_mcp_servers.json", b'{"servers": ["server2"]}')},
        headers=headers,
    )
    assert response2.status_code == 201
    file2 = response2.json()
    assert file2["name"] == "_mcp_servers"

    # Note: _mcp_servers files are filtered out from the regular file list
    # This is expected behavior since they're managed separately
    response = await files_client.get("api/v2/files", headers=headers)
    assert response.status_code == 200
    files = response.json()
    mcp_files = [f for f in files if f["name"] == "_mcp_servers"]
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


# ========== AUTHENTICATION AND AUTHORIZATION TESTS ==========

async def test_upload_file_without_api_key(files_client):
    """Test that uploading a file without API key returns 401."""
    response = await files_client.post(
        "api/v2/files",
        files={"file": ("test.txt", b"test content")},
    )
    assert response.status_code == 401


async def test_upload_file_with_invalid_api_key(files_client):
    """Test that uploading a file with invalid API key returns 401."""
    headers = {"x-api-key": "invalid_key"}
    response = await files_client.post(
        "api/v2/files",
        files={"file": ("test.txt", b"test content")},
        headers=headers,
    )
    assert response.status_code == 401


async def test_download_file_without_api_key(files_client, files_created_api_key):
    """Test that downloading a file without API key returns 401."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    # Upload file first
    response = await files_client.post(
        "api/v2/files",
        files={"file": ("test.txt", b"test content")},
        headers=headers,
    )
    assert response.status_code == 201
    file_id = response.json()["id"]
    
    # Try to download without API key
    response = await files_client.get(f"api/v2/files/{file_id}")
    assert response.status_code == 401


async def test_list_files_without_api_key(files_client):
    """Test that listing files without API key returns 401."""
    response = await files_client.get("api/v2/files")
    assert response.status_code == 401


async def test_delete_file_without_api_key(files_client, files_created_api_key):
    """Test that deleting a file without API key returns 401."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    # Upload file first
    response = await files_client.post(
        "api/v2/files",
        files={"file": ("test.txt", b"test content")},
        headers=headers,
    )
    assert response.status_code == 201
    file_id = response.json()["id"]
    
    # Try to delete without API key
    response = await files_client.delete(f"api/v2/files/{file_id}")
    assert response.status_code == 401


async def test_edit_file_without_api_key(files_client, files_created_api_key):
    """Test that editing a file without API key returns 401."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    # Upload file first
    response = await files_client.post(
        "api/v2/files",
        files={"file": ("test.txt", b"test content")},
        headers=headers,
    )
    assert response.status_code == 201
    file_id = response.json()["id"]
    
    # Try to edit without API key
    response = await files_client.put(f"api/v2/files/{file_id}?name=new_name.txt")
    assert response.status_code == 401


# ========== FILE SIZE LIMIT TESTS ==========

async def test_upload_file_exceeding_size_limit(files_client, files_created_api_key, max_file_size_upload_fixture):
    """Test that uploading a file exceeding the size limit fails."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    # Create a file larger than 1MB (the fixture sets limit to 1MB)
    large_content = b"x" * (2 * 1024 * 1024)  # 2MB
    
    response = await files_client.post(
        "api/v2/files",
        files={"file": ("large.txt", large_content)},
        headers=headers,
    )
    assert response.status_code == 413 or response.status_code == 400  # Request entity too large or bad request


async def test_upload_file_at_size_limit(files_client, files_created_api_key, max_file_size_upload_10mb_fixture):
    """Test that uploading a file at exactly the size limit succeeds."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    # Create a file exactly at the 10MB limit
    limit_content = b"x" * (10 * 1024 * 1024)  # Exactly 10MB
    
    response = await files_client.post(
        "api/v2/files",
        files={"file": ("limit.txt", limit_content)},
        headers=headers,
    )
    assert response.status_code == 201


async def test_upload_empty_file(files_client, files_created_api_key):
    """Test that uploading an empty file works."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    response = await files_client.post(
        "api/v2/files",
        files={"file": ("empty.txt", b"")},
        headers=headers,
    )
    assert response.status_code == 201
    
    # Verify empty file can be downloaded
    file_id = response.json()["id"]
    download_response = await files_client.get(f"api/v2/files/{file_id}", headers=headers)
    assert download_response.status_code == 200
    assert download_response.content == b""


# ========== MALFORMED REQUEST TESTS ==========

async def test_upload_without_file_field(files_client, files_created_api_key):
    """Test that uploading without file field returns 400."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    response = await files_client.post(
        "api/v2/files",
        data={"not_file": "value"},
        headers=headers,
    )
    assert response.status_code == 400 or response.status_code == 422


async def test_upload_with_empty_filename(files_client, files_created_api_key):
    """Test that uploading with empty filename works (should generate name)."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    response = await files_client.post(
        "api/v2/files",
        files={"file": ("", b"content")},
        headers=headers,
    )
    assert response.status_code == 201
    file_data = response.json()
    assert file_data["name"] is not None
    assert len(file_data["name"]) > 0


async def test_upload_with_none_filename(files_client, files_created_api_key):
    """Test that uploading with None filename works."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    response = await files_client.post(
        "api/v2/files",
        files={"file": (None, b"content")},
        headers=headers,
    )
    assert response.status_code == 201


# ========== SPECIAL CHARACTERS AND EDGE CASES ==========

async def test_upload_file_with_special_characters_in_name(files_client, files_created_api_key):
    """Test that uploading files with special characters in names works."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    special_names = [
        "file with spaces.txt",
        "file-with-dashes.txt",
        "file_with_underscores.txt",
        "file.with.dots.txt",
        "file(with)parentheses.txt",
        "file[with]brackets.txt",
        "file{with}braces.txt",
        "file@symbol.txt",
        "file#hash.txt",
        "file$dollar.txt",
        "file%percent.txt",
        "file&ampersand.txt",
    ]
    
    for filename in special_names:
        response = await files_client.post(
            "api/v2/files",
            files={"file": (filename, b"content")},
            headers=headers,
        )
        assert response.status_code == 201, f"Failed to upload file with name: {filename}"


async def test_upload_file_with_unicode_characters(files_client, files_created_api_key):
    """Test that uploading files with Unicode characters works."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    unicode_names = [
        "файл.txt",  # Russian
        "文件.txt",    # Chinese
        "ファイル.txt",  # Japanese
        "archivo.txt", # Spanish
        "fichier.txt", # French
        "😀emoji.txt", # Emoji
    ]
    
    for filename in unicode_names:
        response = await files_client.post(
            "api/v2/files",
            files={"file": (filename, b"content")},
            headers=headers,
        )
        assert response.status_code == 201, f"Failed to upload file with Unicode name: {filename}"


async def test_upload_file_with_very_long_name(files_client, files_created_api_key):
    """Test that uploading files with very long names works or fails gracefully."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    # Create a very long filename (255 characters)
    long_name = "a" * 250 + ".txt"
    
    response = await files_client.post(
        "api/v2/files",
        files={"file": (long_name, b"content")},
        headers=headers,
    )
    # Should either succeed or fail with appropriate error
    assert response.status_code in [201, 400, 413, 422]


# ========== ERROR HANDLING TESTS ==========

async def test_download_nonexistent_file(files_client, files_created_api_key):
    """Test that downloading a non-existent file returns 404."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    response = await files_client.get("api/v2/files/nonexistent-id", headers=headers)
    assert response.status_code == 404


async def test_delete_nonexistent_file(files_client, files_created_api_key):
    """Test that deleting a non-existent file returns 404."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    response = await files_client.delete("api/v2/files/nonexistent-id", headers=headers)
    assert response.status_code == 404


async def test_edit_nonexistent_file(files_client, files_created_api_key):
    """Test that editing a non-existent file returns 404."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    response = await files_client.put("api/v2/files/nonexistent-id?name=new_name.txt", headers=headers)
    assert response.status_code == 404


async def test_edit_file_with_invalid_name(files_client, files_created_api_key):
    """Test that editing a file with invalid name parameters fails gracefully."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    # Upload file first
    response = await files_client.post(
        "api/v2/files",
        files={"file": ("test.txt", b"test content")},
        headers=headers,
    )
    assert response.status_code == 201
    file_id = response.json()["id"]
    
    # Try to edit with empty name
    response = await files_client.put(f"api/v2/files/{file_id}?name=", headers=headers)
    assert response.status_code in [400, 422]


async def test_edit_file_without_name_parameter(files_client, files_created_api_key):
    """Test that editing a file without name parameter fails."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    # Upload file first
    response = await files_client.post(
        "api/v2/files",
        files={"file": ("test.txt", b"test content")},
        headers=headers,
    )
    assert response.status_code == 201
    file_id = response.json()["id"]
    
    # Try to edit without name parameter
    response = await files_client.put(f"api/v2/files/{file_id}", headers=headers)
    assert response.status_code in [400, 422]


# ========== CROSS-USER SECURITY TESTS ==========

async def test_user_cannot_access_other_users_files(files_client, files_created_api_key):
    """Test that users cannot access files uploaded by other users."""
    # Create a second user and API key
    db_manager = get_db_service()
    async with db_manager.with_session() as session:
        user2 = User(
            username="files_user2",
            password=get_password_hash("testpassword2"),
            is_active=True,
            is_superuser=False,
        )
        session.add(user2)
        await session.commit()
        await session.refresh(user2)
        
        hashed2 = get_password_hash("random_key2")
        api_key2 = ApiKey(
            name="files_user2_api_key",
            user_id=user2.id,
            api_key="random_key2",
            hashed_api_key=hashed2,
        )
        session.add(api_key2)
        await session.commit()
        await session.refresh(api_key2)
    
    headers1 = {"x-api-key": files_created_api_key.api_key}
    headers2 = {"x-api-key": api_key2.api_key}
    
    # User 1 uploads a file
    response = await files_client.post(
        "api/v2/files",
        files={"file": ("user1_file.txt", b"user1 content")},
        headers=headers1,
    )
    assert response.status_code == 201
    file_id = response.json()["id"]
    
    # User 2 tries to access user 1's file
    response = await files_client.get(f"api/v2/files/{file_id}", headers=headers2)
    assert response.status_code == 404  # Should not be able to access other user's files
    
    # User 2 tries to delete user 1's file
    response = await files_client.delete(f"api/v2/files/{file_id}", headers=headers2)
    assert response.status_code == 404  # Should not be able to delete other user's files
    
    # User 2 tries to edit user 1's file
    response = await files_client.put(f"api/v2/files/{file_id}?name=hacked.txt", headers=headers2)
    assert response.status_code == 404  # Should not be able to edit other user's files
    
    # Cleanup
    async with db_manager.with_session() as session:
        await session.delete(api_key2)
        await session.delete(user2)
        await session.commit()


# ========== CONCURRENT OPERATIONS TESTS ==========

async def test_concurrent_file_uploads(files_client, files_created_api_key):
    """Test that concurrent file uploads work correctly."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    # Create multiple upload tasks
    async def upload_file(filename, content):
        return await files_client.post(
            "api/v2/files",
            files={"file": (filename, content)},
            headers=headers,
        )
    
    tasks = [
        upload_file(f"concurrent_{i}.txt", f"content_{i}".encode())
        for i in range(5)
    ]
    
    # Execute all uploads concurrently
    responses = await asyncio.gather(*tasks)
    
    # Verify all uploads succeeded
    for response in responses:
        assert response.status_code == 201
    
    # Verify all files can be listed
    response = await files_client.get("api/v2/files", headers=headers)
    assert response.status_code == 200
    files = response.json()
    concurrent_files = [f for f in files if f["name"].startswith("concurrent_")]
    assert len(concurrent_files) == 5


async def test_concurrent_file_operations_same_name(files_client, files_created_api_key):
    """Test that concurrent uploads with same filename create unique names."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    # Create multiple upload tasks with same filename
    async def upload_file(content):
        return await files_client.post(
            "api/v2/files",
            files={"file": ("same_name.txt", content)},
            headers=headers,
        )
    
    tasks = [
        upload_file(f"content_{i}".encode())
        for i in range(3)
    ]
    
    # Execute all uploads concurrently
    responses = await asyncio.gather(*tasks)
    
    # Verify all uploads succeeded
    for response in responses:
        assert response.status_code == 201
    
    # Verify all files have unique names
    response = await files_client.get("api/v2/files", headers=headers)
    assert response.status_code == 200
    files = response.json()
    same_name_files = [f for f in files if f["name"].startswith("same_name")]
    assert len(same_name_files) == 3
    
    # Verify names are unique
    names = [f["name"] for f in same_name_files]
    assert len(set(names)) == 3  # All names should be unique


# ========== BINARY FILE TESTS ==========

async def test_upload_binary_file(files_client, files_created_api_key):
    """Test that uploading binary files works correctly."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    # Create some binary content
    binary_content = bytes(range(256))  # All possible byte values
    
    response = await files_client.post(
        "api/v2/files",
        files={"file": ("binary.bin", binary_content)},
        headers=headers,
    )
    assert response.status_code == 201
    
    # Verify binary file can be downloaded correctly
    file_id = response.json()["id"]
    download_response = await files_client.get(f"api/v2/files/{file_id}", headers=headers)
    assert download_response.status_code == 200
    assert download_response.content == binary_content


async def test_upload_image_file(files_client, files_created_api_key):
    """Test that uploading image-like files works correctly."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    # Create fake image header (PNG signature)
    png_header = b'\x89PNG\r\n\x1a\n'
    fake_png_content = png_header + b'fake image data'
    
    response = await files_client.post(
        "api/v2/files",
        files={"file": ("image.png", fake_png_content)},
        headers=headers,
    )
    assert response.status_code == 201
    
    # Verify image file can be downloaded correctly
    file_id = response.json()["id"]
    download_response = await files_client.get(f"api/v2/files/{file_id}", headers=headers)
    assert download_response.status_code == 200
    assert download_response.content == fake_png_content


# ========== EDGE CASES FOR UNIQUE NAMING ==========

async def test_unique_naming_with_parentheses_in_original_name(files_client, files_created_api_key):
    """Test unique naming when original filename contains parentheses."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    # Upload file with parentheses in name
    response1 = await files_client.post(
        "api/v2/files",
        files={"file": ("file(original).txt", b"content1")},
        headers=headers,
    )
    assert response1.status_code == 201
    file1 = response1.json()
    assert file1["name"] == "file(original)"
    
    # Upload another file with same name
    response2 = await files_client.post(
        "api/v2/files",
        files={"file": ("file(original).txt", b"content2")},
        headers=headers,
    )
    assert response2.status_code == 201
    file2 = response2.json()
    assert file2["name"] == "file(original) (1)"


async def test_unique_naming_with_numbers_in_original_name(files_client, files_created_api_key):
    """Test unique naming when original filename contains numbers."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    # Upload file with numbers in name
    response1 = await files_client.post(
        "api/v2/files",
        files={"file": ("file123.txt", b"content1")},
        headers=headers,
    )
    assert response1.status_code == 201
    file1 = response1.json()
    assert file1["name"] == "file123"
    
    # Upload another file with same name
    response2 = await files_client.post(
        "api/v2/files",
        files={"file": ("file123.txt", b"content2")},
        headers=headers,
    )
    assert response2.status_code == 201
    file2 = response2.json()
    assert file2["name"] == "file123 (1)"


# ========== RESPONSE VALIDATION TESTS ==========

async def test_upload_response_structure(files_client, files_created_api_key):
    """Test that upload response has expected structure."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    response = await files_client.post(
        "api/v2/files",
        files={"file": ("test.txt", b"test content")},
        headers=headers,
    )
    assert response.status_code == 201
    
    data = response.json()
    assert "id" in data
    assert "name" in data
    assert "path" in data
    assert isinstance(data["id"], str)
    assert isinstance(data["name"], str)
    assert isinstance(data["path"], str)
    assert len(data["id"]) > 0
    assert len(data["name"]) > 0
    assert len(data["path"]) > 0


async def test_list_files_response_structure(files_client, files_created_api_key):
    """Test that list files response has expected structure."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    # Upload a file first
    await files_client.post(
        "api/v2/files",
        files={"file": ("test.txt", b"test content")},
        headers=headers,
    )
    
    response = await files_client.get("api/v2/files", headers=headers)
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    
    for file_info in data:
        assert "id" in file_info
        assert "name" in file_info
        assert "path" in file_info
        assert isinstance(file_info["id"], str)
        assert isinstance(file_info["name"], str)
        assert isinstance(file_info["path"], str)


# ========== PERFORMANCE AND STRESS TESTS ==========

async def test_upload_many_small_files(files_client, files_created_api_key):
    """Test uploading many small files to check performance."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    # Upload 20 small files
    for i in range(20):
        response = await files_client.post(
            "api/v2/files",
            files={"file": (f"small_{i}.txt", f"content_{i}".encode())},
            headers=headers,
        )
        assert response.status_code == 201
    
    # Verify all files can be listed
    response = await files_client.get("api/v2/files", headers=headers)
    assert response.status_code == 200
    files = response.json()
    small_files = [f for f in files if f["name"].startswith("small_")]
    assert len(small_files) == 20


async def test_upload_download_cycle_integrity(files_client, files_created_api_key):
    """Test that multiple upload/download cycles maintain data integrity."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    test_contents = [
        b"simple text",
        b"text with\nnewlines\nand\ttabs",
        b"binary\x00\x01\x02\x03data",
        b"unicode content: 你好世界",
        b"",  # empty content
    ]
    
    for i, content in enumerate(test_contents):
        # Upload file
        response = await files_client.post(
            "api/v2/files",
            files={"file": (f"integrity_{i}.txt", content)},
            headers=headers,
        )
        assert response.status_code == 201
        file_id = response.json()["id"]
        
        # Download file
        download_response = await files_client.get(f"api/v2/files/{file_id}", headers=headers)
        assert download_response.status_code == 200
        assert download_response.content == content, f"Content mismatch for file {i}"


# ========== CLEANUP AND IDEMPOTENCY TESTS ==========

async def test_delete_file_idempotency(files_client, files_created_api_key):
    """Test that deleting a file multiple times is handled gracefully."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    # Upload file
    response = await files_client.post(
        "api/v2/files",
        files={"file": ("delete_test.txt", b"content")},
        headers=headers,
    )
    assert response.status_code == 201
    file_id = response.json()["id"]
    
    # First delete should succeed
    response = await files_client.delete(f"api/v2/files/{file_id}", headers=headers)
    assert response.status_code == 200
    
    # Second delete should return 404
    response = await files_client.delete(f"api/v2/files/{file_id}", headers=headers)
    assert response.status_code == 404


async def test_edit_file_name_persistence(files_client, files_created_api_key):
    """Test that file name edits persist correctly across operations."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    # Upload file
    response = await files_client.post(
        "api/v2/files",
        files={"file": ("original.txt", b"content")},
        headers=headers,
    )
    assert response.status_code == 201
    file_id = response.json()["id"]
    
    # Edit file name
    response = await files_client.put(f"api/v2/files/{file_id}?name=renamed.txt", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "renamed"
    
    # Verify name persists in file list
    response = await files_client.get("api/v2/files", headers=headers)
    assert response.status_code == 200
    files = response.json()
    renamed_files = [f for f in files if f["id"] == file_id]
    assert len(renamed_files) == 1
    assert renamed_files[0]["name"] == "renamed"
    
    # Verify name persists after download
    response = await files_client.get(f"api/v2/files/{file_id}", headers=headers)
    assert response.status_code == 200
    assert response.content == b"content"


# ========== ADDITIONAL EDGE CASE TESTS ==========

async def test_edit_file_name_with_special_characters(files_client, files_created_api_key):
    """Test that editing file names with special characters works."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    # Upload file
    response = await files_client.post(
        "api/v2/files",
        files={"file": ("original.txt", b"content")},
        headers=headers,
    )
    assert response.status_code == 201
    file_id = response.json()["id"]
    
    # Edit to name with special characters
    response = await files_client.put(f"api/v2/files/{file_id}?name=new name (with) chars.txt", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "new name (with) chars"


async def test_upload_file_with_path_traversal_attempt(files_client, files_created_api_key):
    """Test that path traversal attempts in filenames are handled safely."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    malicious_names = [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\config\\sam",
        "/etc/passwd",
        "C:\\Windows\\System32\\config\\sam",
        "....//....//....//etc/passwd",
    ]
    
    for filename in malicious_names:
        response = await files_client.post(
            "api/v2/files",
            files={"file": (filename, b"malicious content")},
            headers=headers,
        )
        # Should either succeed with sanitized name or fail appropriately
        assert response.status_code in [201, 400, 422]
        if response.status_code == 201:
            # If successful, verify the filename is sanitized
            file_data = response.json()
            assert "../" not in file_data["name"]
            assert "\\" not in file_data["name"]


async def test_upload_file_with_null_bytes_in_name(files_client, files_created_api_key):
    """Test that null bytes in filenames are handled safely."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    # Filename with null byte
    filename_with_null = "test\x00file.txt"
    
    response = await files_client.post(
        "api/v2/files",
        files={"file": (filename_with_null, b"content")},
        headers=headers,
    )
    # Should either succeed with sanitized name or fail appropriately
    assert response.status_code in [201, 400, 422]
    if response.status_code == 201:
        # If successful, verify null bytes are removed
        file_data = response.json()
        assert "\x00" not in file_data["name"]


async def test_file_operations_with_different_content_types(files_client, files_created_api_key):
    """Test file operations with various content types."""
    headers = {"x-api-key": files_created_api_key.api_key}
    
    # Test different file types
    test_files = [
        ("text.txt", b"plain text", "text/plain"),
        ("data.json", b'{"key": "value"}', "application/json"),
        ("styles.css", b"body { color: red; }", "text/css"),
        ("script.js", b"console.log('hello');", "application/javascript"),
        ("image.png", b"\x89PNG\r\n\x1a\n", "image/png"),
        ("archive.zip", b"PK\x03\x04", "application/zip"),
    ]
    
    for filename, content, expected_content_type in test_files:
        response = await files_client.post(
            "api/v2/files",
            files={"file": (filename, content)},
            headers=headers,
        )
        assert response.status_code == 201, f"Failed to upload {filename}"
        
        # Verify file can be downloaded
        file_id = response.json()["id"]
        download_response = await files_client.get(f"api/v2/files/{file_id}", headers=headers)
        assert download_response.status_code == 200
        assert download_response.content == content


