"""Scoped upload permissions apply to the namespace used for storage."""

import anyio
import pytest
from langflow.services.deps import get_storage_service
from lfx.utils.file_path_security import user_storage_scope

from tests.unit.api.v1.test_scoped_key_resource_lists import exact_resource_plugin, scoped_headers


@pytest.mark.parametrize("append", [False, True])
async def test_create_only_key_cannot_replace_unrecorded_file(
    client, logged_in_headers, active_user, monkeypatch, tmp_path, append
):
    """A real ephemeral upload cannot be replaced or appended to with only create access."""
    storage = get_storage_service()
    monkeypatch.setattr(storage, "data_dir", anyio.Path(tmp_path))
    original = await client.post(
        "api/v2/files/",
        headers=logged_in_headers,
        params={"ephemeral": True},
        files={"file": ("existing.txt", b"before", "text/plain")},
    )
    assert original.status_code == 201, original.text
    assert original.json()["path"] == f"{user_storage_scope(active_user.id)}/existing.txt"
    with exact_resource_plugin(monkeypatch):
        headers = await scoped_headers(client, logged_in_headers, resource_type="file", actions=["create"])
        response = await client.post(
            "api/v2/files/",
            headers=headers,
            params={"append": append, "ephemeral": True},
            files={"file": ("existing.txt", b"after", "text/plain")},
        )
        assert response.status_code == 403, response.text
        created = await client.post(
            "api/v2/files/",
            headers=headers,
            params={"append": append, "ephemeral": True},
            files={"file": ("new.txt", b"new", "text/plain")},
        )
        assert created.status_code == 201, created.text
    assert await storage.get_file(flow_id=user_storage_scope(active_user.id), file_name="existing.txt") == b"before"
    assert await storage.get_file(flow_id=user_storage_scope(active_user.id), file_name="new.txt") == b"new"


@pytest.mark.parametrize("legacy", [False, True])
async def test_scoped_append_preserves_recorded_storage_namespace(
    client, logged_in_headers, active_user, monkeypatch, tmp_path, legacy
):
    """Write access permits appending to typed and legacy files without moving them."""
    from langflow.services.database.models.file.model import File
    from langflow.services.deps import session_scope

    storage = get_storage_service()
    monkeypatch.setattr(storage, "data_dir", anyio.Path(tmp_path))
    namespace = str(active_user.id) if legacy else user_storage_scope(active_user.id)
    await storage.save_file(flow_id=namespace, file_name="recorded.txt", data=b"before")
    async with session_scope() as session:
        row = File(user_id=active_user.id, name="recorded", path=f"{namespace}/recorded.txt", size=6)
        session.add(row)
        await session.flush()
        file_id = row.id
    with exact_resource_plugin(monkeypatch):
        headers = await scoped_headers(client, logged_in_headers, resource_type="file", actions=["create", "write"])
        response = await client.post(
            "api/v2/files/",
            headers=headers,
            params={"append": True},
            files={"file": ("recorded.txt", b"after", "text/plain")},
        )
        assert response.status_code == 201, response.text
        assert response.json()["id"] == str(file_id)
        assert response.json()["path"] == f"{namespace}/recorded.txt"
    assert await storage.get_file(flow_id=namespace, file_name="recorded.txt") == b"beforeafter"
