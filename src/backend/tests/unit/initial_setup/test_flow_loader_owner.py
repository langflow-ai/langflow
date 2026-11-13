import io
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID, uuid4

import httpx
import orjson
import pytest
from langflow.initial_setup import setup
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service
from sqlalchemy.exc import NoResultFound


@pytest.fixture
def loader_settings(async_session, monkeypatch, tmp_path):
    settings = get_settings_service()
    monkeypatch.setattr(settings.settings, "load_flows_path", str(tmp_path))
    monkeypatch.setattr(settings.settings, "bundle_urls", ["https://example.test/flows.zip"])

    @asynccontextmanager
    async def session_scope():
        yield async_session
        await async_session.commit()

    monkeypatch.setattr(setup, "session_scope", session_scope)
    return settings


async def _load_flows(loader, payloads, tmp_path, monkeypatch):
    if loader == "directory":
        for index, payload in enumerate(payloads):
            (tmp_path / f"flow-{index}.json").write_bytes(orjson.dumps(payload))
        await setup.load_flows_from_directory()
        return

    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("bundle/", "")
        for index, payload in enumerate(payloads):
            bundle.writestr(f"bundle/flows/flow-{index}.json", orjson.dumps(payload))

    async_client = httpx.AsyncClient

    def respond(request):
        assert str(request.url) == "https://example.test/flows.zip"
        return httpx.Response(200, content=archive.getvalue())

    monkeypatch.setattr(
        setup.httpx,
        "AsyncClient",
        lambda **kwargs: async_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    assert await setup.load_bundles_from_urls() == ([], [])


@pytest.mark.parametrize("loader", ["directory", "bundle"])
async def test_flow_loader_prefers_configured_active_superuser(
    async_session, loader_settings, tmp_path, monkeypatch, loader
):
    retired = User(
        id=UUID(int=1),
        username="langflow",
        password=uuid4().hex,
        is_superuser=True,
        is_active=False,
        retired_at=datetime.now(timezone.utc),
    )
    other = User(id=UUID(int=2), username="aardvark", password=uuid4().hex, is_superuser=True, is_active=True)
    configured = User(id=UUID(int=3), username="admin", password=uuid4().hex, is_superuser=True, is_active=True)
    async_session.add_all([retired, other, configured])
    folder = Folder(name="Existing project", user_id=configured.id)
    async_session.add(folder)
    await async_session.flush()
    existing = Flow(name="Existing flow", user_id=configured.id, folder_id=folder.id, data={})
    async_session.add(existing)
    await async_session.commit()
    monkeypatch.setattr(loader_settings.auth_settings, "SUPERUSER", "AdMiN")
    new_flow_id = uuid4()
    payloads = [
        {"id": str(existing.id), "name": existing.name, "description": "updated", "data": {}},
        {"id": str(new_flow_id), "name": "New flow", "data": {}},
    ]

    await _load_flows(loader, payloads, tmp_path, monkeypatch)

    await async_session.refresh(existing)
    assert existing.user_id == configured.id
    assert existing.folder_id == folder.id
    assert existing.description == "updated"
    assert (await async_session.get(Flow, new_flow_id)).user_id == configured.id
    assert retired.is_active is False


@pytest.mark.parametrize("loader", ["directory", "bundle"])
@pytest.mark.parametrize("configured_username", ["missing", "langflow"])
async def test_flow_loader_falls_back_to_an_active_superuser(
    async_session, loader_settings, tmp_path, monkeypatch, loader, configured_username
):
    retired = User(id=UUID(int=1), username="langflow", password=uuid4().hex, is_superuser=True, is_active=False)
    later = User(id=UUID(int=2), username="zulu", password=uuid4().hex, is_superuser=True, is_active=True)
    first = User(id=UUID(int=3), username="alpha", password=uuid4().hex, is_superuser=True, is_active=True)
    async_session.add_all([retired, later, first])
    await async_session.commit()
    monkeypatch.setattr(loader_settings.auth_settings, "SUPERUSER", configured_username)
    flow_id = uuid4()

    await _load_flows(loader, [{"id": str(flow_id), "name": "Imported flow", "data": {}}], tmp_path, monkeypatch)

    assert (await async_session.get(Flow, flow_id)).user_id == first.id


@pytest.mark.parametrize("loader", ["directory", "bundle"])
async def test_flow_loader_rejects_an_inactive_superuser_only(
    async_session, loader_settings, tmp_path, monkeypatch, loader
):
    async_session.add(User(username="langflow", password=uuid4().hex, is_superuser=True, is_active=False))
    await async_session.commit()
    monkeypatch.setattr(loader_settings.auth_settings, "SUPERUSER", "langflow")

    with pytest.raises(NoResultFound, match="No active superuser"):
        await _load_flows(loader, [], tmp_path, monkeypatch)
