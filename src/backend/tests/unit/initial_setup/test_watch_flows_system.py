"""System tests for ``LANGFLOW_WATCH_FLOWS_PATH``: boot the app, change files on disk, read flows over HTTP."""

import asyncio
import os

import orjson
import pytest

FLOW_ID = "5d2c7a1e-0f3b-4c6d-8e9a-1b2c3d4e5f60"
NEW_FLOW_ID = "9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d"
POLL_MS = 200


def _write_flow(path, flow_id, name, description):
    payload = {"id": flow_id, "name": name, "description": description, "data": {"nodes": [], "edges": []}}
    path.write_bytes(orjson.dumps(payload))


def _touch_later(path):
    # Filesystems with coarse timestamps can give a rewrite the same mtime as the original.
    later = path.stat().st_mtime + 5
    os.utime(path, (later, later))


@pytest.fixture
def flows_dir(tmp_path, monkeypatch):
    directory = tmp_path / "flows"
    directory.mkdir()
    _write_flow(directory / "watched.json", FLOW_ID, "Watched flow", "v1")
    monkeypatch.setenv("LANGFLOW_LOAD_FLOWS_PATH", str(directory))
    monkeypatch.setenv("LANGFLOW_FS_FLOWS_POLLING_INTERVAL", str(POLL_MS))
    return directory


@pytest.fixture
def watch_enabled(flows_dir, monkeypatch):
    monkeypatch.setenv("LANGFLOW_WATCH_FLOWS_PATH", "true")
    return flows_dir


@pytest.fixture
def watch_disabled(flows_dir, monkeypatch):
    monkeypatch.delenv("LANGFLOW_WATCH_FLOWS_PATH", raising=False)
    return flows_dir


async def _superuser_headers(client):
    # Startup imports LANGFLOW_LOAD_FLOWS_PATH flows for the bootstrap superuser the client fixture configures.
    credentials = {"username": "langflow", "password": "test-superuser-password"}  # pragma: allowlist secret
    response = await client.post("api/v1/login", data=credentials)
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _get_flow(client, headers, flow_id):
    return await client.get(f"api/v1/flows/{flow_id}", headers=headers)


async def _eventually(check, *, timeout_s=15.0):
    deadline = asyncio.get_running_loop().time() + timeout_s
    while asyncio.get_running_loop().time() < deadline:
        if await check():
            return True
        await asyncio.sleep(POLL_MS / 1000)
    return False


async def test_without_watch_a_changed_file_waits_for_restart(watch_disabled, client):
    headers = await _superuser_headers(client)
    path = watch_disabled / "watched.json"
    _write_flow(path, FLOW_ID, "Watched flow", "v2")
    _touch_later(path)

    # Several polling intervals pass; with the watch off nothing reads the directory again.
    await asyncio.sleep(10 * POLL_MS / 1000)

    response = await _get_flow(client, headers, FLOW_ID)
    assert response.status_code == 200
    assert response.json()["description"] == "v1"


async def test_with_watch_changed_and_new_files_apply_without_restart(watch_enabled, client):
    headers = await _superuser_headers(client)
    response = await _get_flow(client, headers, FLOW_ID)
    assert response.status_code == 200
    assert response.json()["description"] == "v1"

    path = watch_enabled / "watched.json"
    _write_flow(path, FLOW_ID, "Watched flow", "v2")
    _touch_later(path)
    _write_flow(watch_enabled / "added.json", NEW_FLOW_ID, "Added flow", "new")

    async def changed_file_applied():
        response = await _get_flow(client, headers, FLOW_ID)
        return response.status_code == 200 and response.json()["description"] == "v2"

    async def new_file_applied():
        response = await _get_flow(client, headers, NEW_FLOW_ID)
        return response.status_code == 200 and response.json()["name"] == "Added flow"

    assert await _eventually(changed_file_applied)
    assert await _eventually(new_file_applied)


async def test_with_watch_a_removed_file_keeps_its_flow(watch_enabled, client):
    headers = await _superuser_headers(client)
    (watch_enabled / "watched.json").unlink()

    await asyncio.sleep(10 * POLL_MS / 1000)

    response = await _get_flow(client, headers, FLOW_ID)
    assert response.status_code == 200
