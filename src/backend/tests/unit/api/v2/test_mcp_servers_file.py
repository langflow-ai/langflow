import asyncio
import uuid
from pathlib import Path
from types import SimpleNamespace
import io

import pytest
from fastapi import UploadFile
from starlette.background import BackgroundTask

# Module under test
from langflow.api.v2.files import upload_user_file, MCP_SERVERS_FILE, get_file_by_name, delete_file
from langflow.services.database.models.file.model import File as UserFile


class FakeStorageService:  # Minimal stub for storage interactions
    def __init__(self):
        # key -> bytes
        self._store: dict[str, bytes] = {}

    async def save_file(self, flow_id: str, file_name: str, data: bytes):  # noqa: D401
        self._store[f"{flow_id}/{file_name}"] = data

    async def get_file_size(self, flow_id: str, file_name: str):
        return len(self._store.get(f"{flow_id}/{file_name}", b""))

    async def delete_file(self, flow_id: str, file_name: str):  # noqa: D401
        self._store.pop(f"{flow_id}/{file_name}", None)


class FakeResult:  # Helper for Session.exec return
    def __init__(self, rows):
        self._rows = rows

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return list(self._rows)


class FakeSession:  # Minimal async session stub
    def __init__(self):
        self._db: dict[str, UserFile] = {}

    async def exec(self, stmt):  # noqa: D401
        # Extremely simplified: detect by LIKE pattern or equality against name/id
        # We only support SELECT UserFile WHERE name LIKE pattern or id equality
        stmt_str = str(stmt)
        if "user_file.name" in stmt_str:
            # LIKE pattern extraction
            pattern = stmt_str.split("like(")[-1].split(")")[0].strip("\"%")
            rows = [f for name, f in self._db.items() if name.startswith(pattern)]
            return FakeResult(rows)
        if "user_file.id" in stmt_str:
            uid = stmt_str.split("=")[-1].strip().strip("'")
            rows = [f for f in self._db.values() if str(f.id) == uid]
            return FakeResult(rows)
        return FakeResult([])

    def add(self, obj):  # noqa: D401
        self._db[obj.name] = obj

    async def commit(self):  # noqa: D401
        return

    async def refresh(self, obj):  # noqa: D401
        return

    async def delete(self, obj):  # noqa: D401
        self._db.pop(obj.name, None)

    async def flush(self):
        return


class FakeSettings:
    max_file_size_upload: int = 10  # MB


@pytest.fixture
def current_user():
    class User(SimpleNamespace):
        id: str
    return User(id=str(uuid.uuid4()))


@pytest.fixture
def storage_service():
    return FakeStorageService()


@pytest.fixture
def settings_service():
    return SimpleNamespace(settings=FakeSettings())


@pytest.fixture
def session():
    return FakeSession()


@pytest.mark.asyncio
async def test_mcp_servers_upload_replace(session, storage_service, settings_service, current_user):
    """Uploading _mcp_servers.json twice should keep single DB record and no rename."""
    content1 = b"{\"mcpServers\": {}}"
    file1 = UploadFile(filename=f"{MCP_SERVERS_FILE}.json", file=io.BytesIO(content1))
    file1.size = len(content1)

    # First upload
    await upload_user_file(
        file=file1,
        session=session,
        current_user=current_user,
        storage_service=storage_service,
        settings_service=settings_service,
    )

    # DB should contain single entry named _mcp_servers
    assert list(session._db.keys()) == [MCP_SERVERS_FILE]

    # Upload again with different content
    content2 = b"{\"mcpServers\": {\"everything\": {}}}"
    file2 = UploadFile(filename=f"{MCP_SERVERS_FILE}.json", file=io.BytesIO(content2))
    file2.size = len(content2)

    await upload_user_file(
        file=file2,
        session=session,
        current_user=current_user,
        storage_service=storage_service,
        settings_service=settings_service,
    )

    # Still single record, same name
    assert list(session._db.keys()) == [MCP_SERVERS_FILE]

    record = session._db[MCP_SERVERS_FILE]
    # Storage path should match user_id/_mcp_servers.json
    expected_path = f"{current_user.id}/{MCP_SERVERS_FILE}.json"
    assert record.path == expected_path

    # Storage should have updated content
    stored_bytes = storage_service._store[expected_path]
    assert stored_bytes == content2

    # Third upload with server config provided by user
    content3 = (
        b'{"mcpServers": {"everything": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-everything"]}}}'
    )
    file3 = UploadFile(filename=f"{MCP_SERVERS_FILE}.json", file=io.BytesIO(content3))
    file3.size = len(content3)

    await upload_user_file(
        file=file3,
        session=session,
        current_user=current_user,
        storage_service=storage_service,
        settings_service=settings_service,
    )

    stored_bytes = storage_service._store[expected_path]
    assert stored_bytes == content3 