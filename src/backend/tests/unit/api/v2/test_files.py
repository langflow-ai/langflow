import asyncio
import contextlib
import io
import json
import os
import tempfile
import unicodedata
import uuid
import zipfile
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
            monkeypatch.setenv("LANGFLOW_SUPERUSER", "langflow")
            monkeypatch.setenv("LANGFLOW_SUPERUSER_PASSWORD", "test-superuser-password")
            from lfx.services.manager import get_service_manager

            get_service_manager().factories.clear()
            get_service_manager().services.clear()  # Clear the services cache
            app = create_app()
            return app, db_path

        app, db_path = await asyncio.to_thread(init_app)

        async with (
            LifespanManager(app, startup_timeout=None, shutdown_timeout=60) as manager,
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
    assert response_json["path"].startswith(f"user-{files_created_api_key.user_id}/")

    from langflow.services.deps import get_storage_service

    stored = await get_storage_service().get_file(flow_id=f"user-{files_created_api_key.user_id}", file_name="test.txt")
    assert stored == b"test content"


async def test_should_reject_with_400_when_uploaded_file_is_empty(files_client, files_created_api_key, save_file_spy):
    headers = {"x-api-key": files_created_api_key.api_key}

    response = await files_client.post(
        "api/v2/files",
        files={"file": ("empty.txt", b"")},
        headers=headers,
    )

    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.json()}"
    assert response.json()["detail"] == "Empty file not allowed"
    assert save_file_spy == [], f"An empty upload must not reach storage, but these were saved: {save_file_spy}"

    list_response = await files_client.get("api/v2/files", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json() == [], f"A rejected upload must not create a DB row, got: {list_response.json()}"


async def test_should_accept_when_uploaded_file_is_one_byte(files_client, files_created_api_key, save_file_spy):
    """One byte is the smallest accepted upload: the guard rejects size 0, not falsy content."""
    headers = {"x-api-key": files_created_api_key.api_key}

    response = await files_client.post(
        "api/v2/files",
        files={"file": ("one_byte.txt", b"0")},
        headers=headers,
    )

    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.json()}"
    assert len(save_file_spy) == 1, f"Expected exactly one stored file, got: {save_file_spy}"


async def test_should_report_no_file_provided_when_filename_is_missing(
    files_client, files_created_api_key, save_file_spy
):
    """The filename guard runs before the empty-size guard, so its message must not change.

    The body is hand-rolled because httpx omits ``filename`` entirely for an empty
    string, which makes the part a plain form field and gets it rejected as a 422 by
    FastAPI before the route runs. Only an explicit ``filename=""`` reaches the guard.
    """
    boundary = "testboundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename=""\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
        "test content\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    headers = {
        "x-api-key": files_created_api_key.api_key,
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }

    response = await files_client.post("api/v2/files", content=body, headers=headers)

    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.json()}"
    assert response.json()["detail"] == "No file provided"
    assert save_file_spy == [], f"A nameless upload must not reach storage, but these were saved: {save_file_spy}"


async def test_should_reject_with_400_when_mcp_servers_config_is_empty(
    files_client, files_created_api_key, files_active_user, save_file_spy
):
    """An empty MCP config is rejected for being empty, not mis-reported as invalid JSON.

    Before the size guard, the empty body reached _validate_uploaded_mcp_config and
    surfaced as 422 "not valid JSON", which hid the actual problem from the caller.
    """
    headers = {"x-api-key": files_created_api_key.api_key}
    mcp_file_ext = await get_mcp_file(files_active_user, extension=True)

    response = await files_client.post(
        "api/v2/files",
        files={"file": (mcp_file_ext, b"")},
        headers=headers,
    )

    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.json()}"
    assert response.json()["detail"] == "Empty file not allowed"
    assert save_file_spy == [], f"An empty MCP config must not reach storage, but these were saved: {save_file_spy}"


@pytest.mark.usefixtures("max_file_size_upload_fixture")
async def test_should_reject_with_413_when_uploaded_file_is_oversize(
    files_client, files_created_api_key, save_file_spy
):
    """Rejecting empty uploads must not disturb the upper bound, which still answers 413.

    The 413 is raised by ContentSizeLimitMiddleware, which counts body bytes before the
    route runs, so the route's own 413 branch stays shadowed for this request shape.
    """
    headers = {"x-api-key": files_created_api_key.api_key}
    oversize_content = b"x" * (1024 * 1024 + 1024)

    response = await files_client.post(
        "api/v2/files",
        files={"file": ("oversize.txt", io.BytesIO(oversize_content), "application/octet-stream")},
        headers=headers,
    )

    assert response.status_code == 413, f"Expected 413, got {response.status_code}: {response.json()}"
    # The reported size is chunk-dependent: the middleware raises on the first chunk that
    # crosses the limit, so only the fixed part of the message is stable enough to assert on.
    assert "Content size limit exceeded. Maximum allowed is 1MB" in response.json()["detail"]
    assert save_file_spy == [], f"An oversize upload must not reach storage, but these were saved: {save_file_spy}"


@pytest.fixture
def langflow_local_storage(files_client):  # noqa: ARG001
    """Use the Langflow local storage service, as the upload-race test does."""
    from langflow.services.deps import get_session_service, get_settings_service
    from langflow.services.storage.local import LocalStorageService
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType

    services = get_service_manager().services
    usual = services[ServiceType.STORAGE_SERVICE]
    services[ServiceType.STORAGE_SERVICE] = LocalStorageService(get_session_service(), get_settings_service())
    yield
    services[ServiceType.STORAGE_SERVICE] = usual


@pytest.fixture
def post_creation_registry():
    from langflow.services import creation_hooks

    saved = {resource: list(hooks) for resource, hooks in creation_hooks._post_creation_hooks.items()}
    yield creation_hooks
    for resource, hooks in saved.items():
        creation_hooks._post_creation_hooks[resource][:] = hooks


async def test_upload_runs_post_creation_hooks_once_for_a_new_tracked_file(
    files_client,
    files_created_api_key,
    post_creation_registry,
    langflow_local_storage,  # noqa: ARG001
):
    from langflow.services.database.models.file.model import File as UserFile

    seen = []

    async def hook(context):
        # The hook gets no session: the row has to be durable already.
        async with session_scope() as session:
            seen.append((context, await session.get(UserFile, context.resource_id)))

    post_creation_registry.register_post_creation_hook(post_creation_registry.RESOURCE_FILE, hook)
    headers = {"x-api-key": files_created_api_key.api_key}

    response = await files_client.post("api/v2/files", files={"file": ("hooked.txt", b"abc")}, headers=headers)
    # An append to the file that now exists, and an ephemeral upload, create no row to hook.
    appended = await files_client.post(
        "api/v2/files", params={"append": True}, files={"file": ("hooked.txt", b"def")}, headers=headers
    )
    ephemeral = await files_client.post(
        "api/v2/files", params={"ephemeral": True}, files={"file": ("gone.txt", b"x")}, headers=headers
    )

    assert response.status_code == 201, response.text
    assert appended.status_code == 201, appended.text
    assert ephemeral.status_code == 201, ephemeral.text
    assert len(seen) == 1
    context, row = seen[0]
    assert row is not None
    assert (context.resource, str(context.resource_id), context.owner_id) == (
        "file",
        response.json()["id"],
        files_created_api_key.user_id,
    )
    assert context.name == response.json()["name"]


async def test_an_upload_keeps_its_file_when_a_hook_fails_the_request(
    files_client,
    files_created_api_key,
    post_creation_registry,
    langflow_local_storage,  # noqa: ARG001
):
    from fastapi import HTTPException

    async def hook(_context):
        raise HTTPException(status_code=500, detail="follow-up failed")

    post_creation_registry.register_post_creation_hook(post_creation_registry.RESOURCE_FILE, hook)
    headers = {"x-api-key": files_created_api_key.api_key}

    failed = await files_client.post("api/v2/files", files={"file": ("kept.txt", b"abc")}, headers=headers)
    listed = await files_client.get("api/v2/files", headers=headers)

    assert failed.status_code == 500
    assert failed.json()["detail"] == "follow-up failed"
    assert "kept" in [item["name"] for item in listed.json()]


async def test_an_upload_that_loses_its_name_gets_409_and_leaves_the_winners_file(files_client, files_created_api_key):
    """Before: both picked the name before either row existed, and the loser's cleanup deleted the file.

    That left the winner's row pointing at nothing: a retry after a 504 on local disk lost the upload.
    """
    from langflow.services.database.models.file.model import File as UserFile
    from langflow.services.deps import get_session_service, get_settings_service
    from langflow.services.storage.local import LocalStorageService
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType

    user_id = files_created_api_key.user_id

    class OtherUploadFinishesFirst(LocalStorageService):
        async def save_upload_stream(self, flow_id, file_name, chunks):
            written = await super().save_upload_stream(flow_id, file_name, chunks)
            async with session_scope() as session:
                session.add(UserFile(user_id=user_id, name="race", path=f"{flow_id}/{file_name}", size=written))
            return written

    storage = OtherUploadFinishesFirst(get_session_service(), get_settings_service())
    services = get_service_manager().services
    usual = services[ServiceType.STORAGE_SERVICE]
    services[ServiceType.STORAGE_SERVICE] = storage
    try:
        response = await files_client.post(
            "api/v2/files",
            files={"file": ("race.txt", b"same bytes")},
            headers={"x-api-key": files_created_api_key.api_key},
        )
    finally:
        services[ServiceType.STORAGE_SERVICE] = usual

    assert response.status_code == 409, response.text
    assert "Another upload named race.txt finished first" in response.json()["detail"]
    assert await storage.get_file(flow_id=f"user-{user_id}", file_name="race.txt") == b"same bytes"


async def test_should_not_persist_in_my_files_when_upload_is_ephemeral(files_client, files_created_api_key):
    """Ephemeral uploads save the file to storage but do NOT create a UserFile DB record.

    This is the expected behavior for chat playground uploads in Desktop,
    where the file must be servable (for chat history) but should not
    appear in the user's 'My Files' list.
    """
    headers = {"x-api-key": files_created_api_key.api_key}

    # Upload with ephemeral=true
    response = await files_client.post(
        "api/v2/files",
        files={"file": ("playground_image.png", b"fake image content")},
        params={"ephemeral": "true"},
        headers=headers,
    )
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"

    upload_response = response.json()
    assert "path" in upload_response

    # The file must NOT appear in the user's file list
    list_response = await files_client.get("api/v2/files", headers=headers)
    assert list_response.status_code == 200
    file_names = [f["name"] for f in list_response.json()]
    assert "playground_image" not in file_names, (
        f"Ephemeral file should not appear in My Files, but found: {file_names}"
    )

    # The file is saved in storage and the response includes a valid path
    file_path = upload_response["path"]
    assert file_path, "Ephemeral upload should return a non-empty path"
    # Path format: {user_id}/{stored_file_name}
    parts = file_path.split("/")
    assert len(parts) == 2, f"Expected path format 'user-<user_id>/filename', got: {file_path}"
    assert parts[0] == f"user-{files_created_api_key.user_id}"


async def test_should_return_path_with_forward_slashes_when_uploading_file(files_client, files_created_api_key):
    """Upload response path must use forward slashes on all platforms.

    On Windows, pathlib.Path serializes with backslashes, but the GET list
    endpoint returns the raw DB string with forward slashes. If the POST
    response uses backslashes, the frontend cannot match them with
    selectedFiles.includes(file.path), leaving checkboxes unchecked.
    """
    headers = {"x-api-key": files_created_api_key.api_key}

    response = await files_client.post(
        "api/v2/files",
        files={"file": ("test_path.txt", b"path test content")},
        headers=headers,
    )
    assert response.status_code == 201

    upload_path = response.json()["path"]
    assert "\\" not in upload_path, (
        f"Upload response path contains backslashes: '{upload_path}'. "
        "Path must use forward slashes on all platforms for frontend compatibility."
    )

    # Verify the upload path matches what GET /files returns
    list_response = await files_client.get("api/v2/files", headers=headers)
    assert list_response.status_code == 200

    listed_paths = [f["path"] for f in list_response.json()]
    assert upload_path in listed_paths, (
        f"Upload path '{upload_path}' not found in listed paths {listed_paths}. "
        "POST and GET must return identical path strings."
    )


async def test_legacy_user_file_still_downloads(files_client, files_created_api_key):
    """Existing raw user namespaces remain readable without a storage migration."""
    from langflow.services.database.models.file.model import File as UserFile
    from langflow.services.deps import get_storage_service

    user_id = files_created_api_key.user_id
    storage_service = get_storage_service()
    await storage_service.save_file(flow_id=str(user_id), file_name="legacy.txt", data=b"legacy content")
    async with session_scope() as session:
        legacy_file = UserFile(
            user_id=user_id,
            name="legacy",
            path=f"{user_id}/legacy.txt",
            size=len(b"legacy content"),
        )
        session.add(legacy_file)
        await session.commit()
        await session.refresh(legacy_file)
        file_id = legacy_file.id

    response = await files_client.get(f"api/v2/files/{file_id}", headers={"x-api-key": files_created_api_key.api_key})

    assert response.status_code == 200, response.text
    assert response.content == b"legacy content"


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


async def test_edit_file_uses_upload_name_rules(files_client, files_created_api_key):
    headers = {"x-api-key": files_created_api_key.api_key}
    upload = await files_client.post("api/v2/files", files={"file": ("Meeting 10:30.txt", b"content")}, headers=headers)
    assert upload.status_code == 201, upload.text
    file_id = upload.json()["id"]

    for name in ("Meeting 10:30", 'report?*"<>|', "a\tb", ".private", "trailing ", "a\x85b"):
        response = await files_client.put(f"api/v2/files/{file_id}", params={"name": name}, headers=headers)
        assert response.status_code == 200, name
        assert response.json()["name"] == name

    for name in (
        "../escape",
        "..\\escape",
        "/absolute",
        "C:\\Windows\\file",
        "CON",
        "COM0",
        "LPT0",
        "COM0.foo.bar",
        "CON.foo.bar",
        "inv\u202etxt.exe",
        "a\u2028b",
        "a\u2029b",
        "a\ufeffb",
        "a\x00b",
        "a\nb",
        "a\rb",
        "a..b",
        "é" * 128,
    ):
        response = await files_client.put(f"api/v2/files/{file_id}", params={"name": name}, headers=headers)
        assert response.status_code == 400, name

    maximum_length_name = "é" * 127 + "a"
    response = await files_client.put(f"api/v2/files/{file_id}", params={"name": maximum_length_name}, headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == maximum_length_name

    response = await files_client.post("api/v2/files", files={"file": ("é" * 128, b"content")}, headers=headers)
    assert response.status_code == 400

    for name in ("inv\u202etxt.exe", "COM0.txt", "LPT0.txt"):
        response = await files_client.post("api/v2/files", files={"file": (name, b"content")}, headers=headers)
        assert response.status_code == 400, name


@pytest.mark.parametrize(
    "invalid_name", ["../escape", "..\\escape", "nested/path", "nested\\path", "/absolute", "a\x00b"]
)
async def test_rejected_rename_preserves_name_and_safe_batch_download(
    files_client, files_created_api_key, invalid_name: str
):
    headers = {"x-api-key": files_created_api_key.api_key}
    content = b"original uploaded content"
    upload = await files_client.post("api/v2/files", files={"file": ("safe.txt", content)}, headers=headers)
    assert upload.status_code == 201, upload.text
    original = upload.json()

    rename = await files_client.put(f"api/v2/files/{original['id']}", params={"name": invalid_name}, headers=headers)
    assert rename.status_code == 400, rename.text

    listed = await files_client.get("api/v2/files", headers=headers)
    assert listed.status_code == 200, listed.text
    persisted = next(file for file in listed.json() if file["id"] == original["id"])
    assert persisted["name"] == original["name"]

    download = await files_client.post("api/v2/files/batch/", json=[original["id"]], headers=headers)
    assert download.status_code == 200, download.text
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        assert archive.namelist() == [f"{original['name']}.txt"]
        assert archive.read(archive.namelist()[0]) == content


async def test_batch_download_limits_legacy_names_with_collision_suffix(files_client, files_created_api_key):
    from langflow.services.database.models.file.model import File as UserFile

    headers = {"x-api-key": files_created_api_key.api_key}
    file_ids = []
    for filename in ("first.txt", "second.txt"):
        upload = await files_client.post("api/v2/files", files={"file": (filename, filename.encode())}, headers=headers)
        assert upload.status_code == 201, upload.text
        file_ids.append(upload.json()["id"])

    async with session_scope() as session:
        for index, file_id in enumerate(file_ids):
            stored = await session.get(UserFile, uuid.UUID(file_id))
            assert stored is not None
            stored.name = "é" * 150 + str(index)
            session.add(stored)
        await session.commit()

    response = await files_client.post("api/v2/files/batch/", json=file_ids, headers=headers)
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()
        assert len(names) == 2
        assert len(set(names)) == 2
        assert all(name.endswith(".txt") and len(name.encode("utf-8")) <= 255 for name in names)
        assert {archive.read(name) for name in names} == {b"first.txt", b"second.txt"}


async def test_batch_download_truncated_stem_is_not_windows_device(files_client, files_created_api_key):
    headers = {"x-api-key": files_created_api_key.api_key}
    file_ids = []
    for original, display_name in (("a", "COM1extra"), ("b", "COM1extra2")):
        filename = f"{original}.{'x' * 250}"
        upload = await files_client.post("api/v2/files", files={"file": (filename, original.encode())}, headers=headers)
        assert upload.status_code == 201, upload.text
        file_id = upload.json()["id"]
        rename = await files_client.put(f"api/v2/files/{file_id}", params={"name": display_name}, headers=headers)
        assert rename.status_code == 200, rename.text
        file_ids.append(file_id)

    response = await files_client.post("api/v2/files/batch/", json=file_ids, headers=headers)
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names)) == 2
        assert all(name.startswith("_COM") and len(name.encode("utf-8")) <= 255 for name in names)
        assert {archive.read(name) for name in names} == {b"a", b"b"}


async def test_batch_download_sanitizes_legacy_file_names(files_client, files_created_api_key):
    from langflow.services.database.models.file.model import File as UserFile

    headers = {"x-api-key": files_created_api_key.api_key}
    file_ids = []
    for filename, content in (
        ("safe.txt", b"first"),
        ("other.txt", b"second"),
        ("third.txt", b"third"),
        ("fourth.txt", b"fourth"),
        ("fifth.txt", b"fifth"),
        ("sixth.txt", b"sixth"),
        ("seventh.txt", b"seventh"),
        ("eighth.txt", b"eighth"),
        ("ninth.txt", b"ninth"),
    ):
        upload = await files_client.post("api/v2/files", files={"file": (filename, content)}, headers=headers)
        assert upload.status_code == 201, upload.text
        file_ids.append(upload.json()["id"])

    # Legacy rows may predate rename validation. They must be safe in new ZIPs.
    async with session_scope() as session:
        legacy_names = (
            "../../escape",
            "..\\..\\escape",
            "Foo",
            "foo",
            "a\x85b",
            "é",
            "e\u0301",
            "inv\u202etxt.exe",
            "COM0",
        )
        for file_id, legacy_name in zip(file_ids, legacy_names, strict=True):
            stored = await session.get(UserFile, uuid.UUID(file_id))
            assert stored is not None
            stored.name = legacy_name
            session.add(stored)
        await session.commit()

    response = await files_client.post("api/v2/files/batch/", json=file_ids, headers=headers)
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert len(archive.namelist()) == 9
        assert len({unicodedata.normalize("NFC", entry).casefold() for entry in archive.namelist()}) == 9
        assert any(entry.startswith("_COM0") for entry in archive.namelist())
        for entry in archive.namelist():
            assert entry.endswith(".txt")
            assert "/" not in entry
            assert "\\" not in entry
            assert ".." not in entry
            assert "\x85" not in entry
            assert "\u202e" not in entry
        assert {archive.read(entry) for entry in archive.namelist()} == {
            b"first",
            b"second",
            b"third",
            b"fourth",
            b"fifth",
            b"sixth",
            b"seventh",
            b"eighth",
            b"ninth",
        }


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


async def test_duplicate_upload_does_not_exceed_filename_byte_limit(files_client, files_created_api_key):
    headers = {"x-api-key": files_created_api_key.api_key}
    filename = f"{'é' * 125}a.txt"  # 255 UTF-8 bytes

    first = await files_client.post("api/v2/files", files={"file": (filename, b"first")}, headers=headers)
    assert first.status_code == 201, first.text

    duplicate = await files_client.post("api/v2/files", files={"file": (filename, b"second")}, headers=headers)
    assert duplicate.status_code == 400, duplicate.text
    assert "too long" in duplicate.json()["detail"]

    original = await files_client.get(f"api/v2/files/{first.json()['id']}", headers=headers)
    assert original.status_code == 200
    assert original.content == b"first"


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
    async with session_scope() as session:
        user = await session.get(User, files_active_user.id)
        user.is_superuser = True
        session.add(user)
    files_active_user.is_superuser = True
    headers = {"x-api-key": files_created_api_key.api_key}

    mcp_file_ext = await get_mcp_file(files_active_user, extension=True)
    mcp_file = await get_mcp_file(files_active_user)
    first_mcp_config = b'{"mcpServers": {"fetch": {"command": "uvx", "args": ["mcp-server-fetch"]}}}'
    second_mcp_config = b'{"mcpServers": {"everything": {}}}'

    # Upload first _mcp_servers file
    response1 = await files_client.post(
        "api/v2/files",
        files={"file": (mcp_file_ext, first_mcp_config)},
        headers=headers,
    )
    assert response1.status_code == 201
    file1 = response1.json()
    assert file1["name"] == mcp_file

    # Upload second _mcp_servers file - should replace the first one
    response2 = await files_client.post(
        "api/v2/files",
        files={"file": (mcp_file_ext, second_mcp_config)},
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
    assert download2.content == second_mcp_config

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


@pytest.mark.parametrize(
    ("filename", "expected_rfc5987"),
    [
        ("龙.txt", "%E9%BE%99.txt"),
        ("测试文件.txt", "%E6%B5%8B%E8%AF%95%E6%96%87%E4%BB%B6.txt"),
        ("日本語ファイル.txt", "%E6%97%A5%E6%9C%AC%E8%AA%9E%E3%83%95%E3%82%A1%E3%82%A4%E3%83%AB.txt"),
        ("naïve_résumé.txt", "na%C3%AFve_r%C3%A9sum%C3%A9.txt"),
        ("normal_file.txt", "normal_file.txt"),
    ],
)
async def test_download_file_non_ascii_content_disposition(
    files_client, files_created_api_key, filename, expected_rfc5987
):
    """Non-ASCII filenames must be RFC 5987 encoded in Content-Disposition for single file download."""
    from urllib.parse import unquote

    headers = {"x-api-key": files_created_api_key.api_key}

    upload_response = await files_client.post(
        "api/v2/files",
        files={"file": (filename, b"content")},
        headers=headers,
    )
    assert upload_response.status_code == 201
    upload_json = upload_response.json()
    file_id = upload_json["id"]
    stored_name = upload_json["path"].split("/")[-1]

    download_response = await files_client.get(f"api/v2/files/{file_id}", headers=headers)
    assert download_response.status_code == 200

    content_disposition = download_response.headers["content-disposition"]
    assert "attachment" in content_disposition
    assert "filename*=UTF-8''" in content_disposition
    assert expected_rfc5987 in content_disposition
    rfc5987_value = content_disposition.split("filename*=UTF-8''")[-1].split(";")[0].strip()
    assert unquote(rfc5987_value) == stored_name


async def test_batch_download_files_non_ascii_content_disposition(files_client, files_created_api_key):
    """Batch download ZIP must have ASCII-safe Content-Disposition (timestamp-based filename)."""
    import re

    headers = {"x-api-key": files_created_api_key.api_key}

    file_ids = []
    for name in ("龙.txt", "测试.txt"):
        resp = await files_client.post(
            "api/v2/files",
            files={"file": (name, b"data")},
            headers=headers,
        )
        assert resp.status_code == 201
        file_ids.append(resp.json()["id"])

    batch_response = await files_client.post(
        "api/v2/files/batch/",
        json=file_ids,
        headers=headers,
    )
    assert batch_response.status_code == 200
    assert batch_response.headers["content-type"] == "application/x-zip-compressed"

    content_disposition = batch_response.headers["content-disposition"]
    assert "attachment" in content_disposition
    # Batch ZIP filename is timestamp-based (pure ASCII) — verify RFC 5987 encoding is present
    assert "filename*=UTF-8''" in content_disposition
    assert re.search(r"\d{8}_\d{6}_langflow_files\.zip", content_disposition)


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
            monkeypatch.setenv("LANGFLOW_SUPERUSER", "langflow")
            monkeypatch.setenv("LANGFLOW_SUPERUSER_PASSWORD", "test-superuser-password")
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
            LifespanManager(app, startup_timeout=None, shutdown_timeout=60) as manager,
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


class _Upload:
    """An upload that records how much each read asks for, as a large file cares about."""

    def __init__(self, data: bytes):
        self.filename, self._data, self.asked = "upload.bin", data, []

    async def read(self, size: int = -1) -> bytes:
        self.asked.append(size)
        size = len(self._data) if size < 0 else size
        piece, self._data = self._data[:size], self._data[size:]
        return piece

    async def close(self) -> None:
        pass


def _local_storage(tmp_path):
    from unittest.mock import MagicMock

    from langflow.services.storage.local import LocalStorageService

    settings_service = MagicMock()
    settings_service.settings.config_dir = str(tmp_path)
    return LocalStorageService(MagicMock(), settings_service)


async def _saved(tmp_path, data: bytes, *, append: bool = False, already: bytes | None = None):
    from types import SimpleNamespace

    from langflow.api.v2.files import save_file_routine

    storage = _local_storage(tmp_path)
    if already is not None:
        await storage.save_file("ns", "upload.bin", already)
    upload = _Upload(data)
    await save_file_routine(
        upload, storage, SimpleNamespace(id="u1"), file_name="upload.bin", namespace="ns", append=append
    )
    return upload, await storage.get_file("ns", "upload.bin")


async def test_a_large_upload_is_never_read_whole(tmp_path):
    """Before: one read of the whole body, which is what ran a 4 GiB Editor out of memory."""
    from langflow.api.v2.files import UPLOAD_READ_CHUNK

    data = b"x" * (UPLOAD_READ_CHUNK * 2 + 5)

    upload, stored = await _saved(tmp_path, data)

    assert stored == data
    assert all(0 < size <= UPLOAD_READ_CHUNK for size in upload.asked), upload.asked


async def test_an_empty_upload_still_stores_a_file(tmp_path):
    _, stored = await _saved(tmp_path, b"")
    assert stored == b""


async def test_an_upload_replaces_what_was_there(tmp_path):
    _, stored = await _saved(tmp_path, b"new", already=b"older and longer")
    assert stored == b"new"


async def test_appending_still_adds_to_the_end(tmp_path):
    _, stored = await _saved(tmp_path, b"new", append=True, already=b"old")
    assert stored == b"oldnew"


async def test_an_s3_upload_passes_its_md5_so_no_label_copy_is_needed():
    """Before: S3 learned the MD5 only at the end and copied the whole object to label it."""
    import hashlib
    from types import SimpleNamespace

    from langflow.api.v2.files import UPLOAD_READ_CHUNK, save_file_routine
    from langflow.services.storage.s3 import S3StorageService
    from starlette.datastructures import UploadFile as StarletteUpload

    data = b"y" * (UPLOAD_READ_CHUNK * 2 + 7)
    spooled = tempfile.SpooledTemporaryFile(max_size=1024)  # noqa: SIM115 - the UploadFile owns it
    spooled.write(data)
    spooled.seek(0)
    upload = StarletteUpload(file=spooled, filename="big.bin")
    seen: dict = {}

    async def save_upload_stream(_flow_id, _file_name, chunks, *, md5=None):
        seen["md5"] = md5
        seen["body"] = b"".join([chunk async for chunk in chunks])
        return len(seen["body"])

    storage = MagicMock(spec=S3StorageService)
    storage.save_upload_stream = save_upload_stream

    await save_file_routine(upload, storage, SimpleNamespace(id="u1"), file_name="big.bin", namespace="ns")

    assert seen["md5"] == hashlib.md5(data, usedforsecurity=False).hexdigest()
    assert seen["body"] == data  # rewound after hashing, so the save still sends every byte


async def test_a_storage_failure_on_upload_names_no_address():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    from fastapi import HTTPException
    from langflow.api.v2.files import upload_user_file

    url = "https://bucket.s3.amazonaws.com/files/user-1/upload.bin"
    storage = MagicMock()
    storage.save_upload_stream = AsyncMock(side_effect=RuntimeError(f"Could not connect to the endpoint URL: {url}"))
    session = MagicMock()
    session.exec = AsyncMock(return_value=MagicMock(all=list, first=lambda: None))
    upload = SimpleNamespace(filename="upload.bin", size=1, read=AsyncMock(return_value=b""), close=AsyncMock())

    with pytest.raises(HTTPException) as raised:
        await upload_user_file(
            file=upload,
            session=session,
            current_user=SimpleNamespace(id="u1", is_superuser=False),
            storage_service=storage,
            settings_service=SimpleNamespace(settings=SimpleNamespace(max_file_size_upload=100)),
        )

    assert raised.value.status_code == 500
    assert "amazonaws" not in str(raised.value.detail)
