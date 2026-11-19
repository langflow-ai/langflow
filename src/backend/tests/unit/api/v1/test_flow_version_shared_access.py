"""Version history for people who may edit a flow they do not own.

Without an authorization plugin, history stays with the flow's owner. With one,
the plugin's answer decides, the same way it does for reading or saving the flow
itself, and the owner keeps their own history whatever the plugin says.
"""

import uuid

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.crud import create_flow_version_entry
from langflow.services.deps import session_scope

GRAPH = {"nodes": [{"id": "n-owner", "data": {}}], "edges": []}


class _FlowPermissions:
    """Grant a fixed set of flow actions, as a registered authorization plugin would."""

    def __init__(self, granted: set[str]) -> None:
        self.granted = granted

    async def supports_cross_user_fetch(self) -> bool:
        return True

    async def is_enabled(self) -> bool:
        return True

    async def enforce(self, *, user_id, domain, obj, act, context) -> bool:  # noqa: ARG002
        return act in self.granted


def _install_plugin(monkeypatch: pytest.MonkeyPatch, granted: set[str]) -> None:
    from langflow.services.authorization import fetch, guards
    from langflow.services.deps import get_settings_service

    plugin = _FlowPermissions(granted)
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTHZ_ENABLED", True)
    monkeypatch.setattr(fetch, "get_authorization_service", lambda: plugin)
    monkeypatch.setattr(guards, "get_authorization_service", lambda: plugin)


async def _flow_owned_by(owner_id: uuid.UUID) -> tuple[str, str]:
    """Create a flow for ``owner_id`` with one version its owner saved; return both ids."""
    async with session_scope() as session:
        flow = Flow(name=f"shared-history-{uuid.uuid4().hex}", user_id=owner_id, data=GRAPH)
        session.add(flow)
        await session.flush()
        entry = await create_flow_version_entry(session, flow_id=flow.id, user_id=owner_id, data=GRAPH)
        return str(flow.id), str(entry.id)


async def test_an_editor_sees_the_whole_history_of_a_flow_they_do_not_own(
    client: AsyncClient, logged_in_headers, user_two, monkeypatch
):
    """The "Update Current Flow" notice sends an editor to history; that history must open."""
    flow_id, owners_entry = await _flow_owned_by(user_two.id)
    _install_plugin(monkeypatch, {"read", "write"})

    listed = await client.get(f"api/v1/flows/{flow_id}/versions/", headers=logged_in_headers)
    assert listed.status_code == status.HTTP_200_OK, listed.text
    assert [e["id"] for e in listed.json()["entries"]] == [owners_entry], "versions the owner wrote must show"

    opened = await client.get(f"api/v1/flows/{flow_id}/versions/{owners_entry}", headers=logged_in_headers)
    assert opened.status_code == status.HTTP_200_OK, opened.text
    assert opened.json()["data"]["nodes"][0]["id"] == "n-owner"


async def test_an_editor_can_save_and_restore_versions_of_a_flow_they_do_not_own(
    client: AsyncClient, logged_in_headers, active_user, user_two, monkeypatch
):
    flow_id, owners_entry = await _flow_owned_by(user_two.id)
    _install_plugin(monkeypatch, {"read", "write"})

    saved = await client.post(
        f"api/v1/flows/{flow_id}/versions/", json={"description": "editor"}, headers=logged_in_headers
    )
    assert saved.status_code == status.HTTP_201_CREATED, saved.text
    assert saved.json()["user_id"] == str(active_user.id), "a saved version is credited to who saved it"

    restored = await client.post(f"api/v1/flows/{flow_id}/versions/{owners_entry}/activate", headers=logged_in_headers)
    assert restored.status_code == status.HTTP_200_OK, restored.text
    assert restored.json()["user_id"] == str(user_two.id), "restoring must not take the flow from its owner"


async def test_a_viewer_reads_history_but_cannot_change_it(
    client: AsyncClient, logged_in_headers, user_two, monkeypatch
):
    flow_id, owners_entry = await _flow_owned_by(user_two.id)
    _install_plugin(monkeypatch, {"read"})

    listed = await client.get(f"api/v1/flows/{flow_id}/versions/", headers=logged_in_headers)
    assert listed.status_code == status.HTTP_200_OK, listed.text

    saved = await client.post(f"api/v1/flows/{flow_id}/versions/", json={}, headers=logged_in_headers)
    restored = await client.post(f"api/v1/flows/{flow_id}/versions/{owners_entry}/activate", headers=logged_in_headers)
    deleted = await client.delete(f"api/v1/flows/{flow_id}/versions/{owners_entry}", headers=logged_in_headers)
    assert saved.status_code == status.HTTP_403_FORBIDDEN, saved.text
    assert restored.status_code == status.HTTP_403_FORBIDDEN, restored.text
    assert deleted.status_code == status.HTTP_403_FORBIDDEN, deleted.text


async def test_someone_without_access_cannot_tell_the_history_exists(
    client: AsyncClient, logged_in_headers, user_two, monkeypatch
):
    flow_id, owners_entry = await _flow_owned_by(user_two.id)
    _install_plugin(monkeypatch, set())

    listed = await client.get(f"api/v1/flows/{flow_id}/versions/", headers=logged_in_headers)
    opened = await client.get(f"api/v1/flows/{flow_id}/versions/{owners_entry}", headers=logged_in_headers)
    assert listed.status_code == status.HTTP_404_NOT_FOUND, listed.text
    assert opened.status_code == status.HTTP_404_NOT_FOUND, opened.text


async def test_without_a_plugin_history_stays_with_the_owner(client: AsyncClient, logged_in_headers, user_two):
    """Plain OSS has no sharing, so a flow someone else owns is not there to look at."""
    flow_id, owners_entry = await _flow_owned_by(user_two.id)

    listed = await client.get(f"api/v1/flows/{flow_id}/versions/", headers=logged_in_headers)
    opened = await client.get(f"api/v1/flows/{flow_id}/versions/{owners_entry}", headers=logged_in_headers)
    saved = await client.post(f"api/v1/flows/{flow_id}/versions/", json={}, headers=logged_in_headers)
    assert listed.status_code == status.HTTP_404_NOT_FOUND, listed.text
    assert opened.status_code == status.HTTP_404_NOT_FOUND, opened.text
    assert saved.status_code == status.HTTP_404_NOT_FOUND, saved.text


async def test_the_owner_keeps_their_history_whatever_the_plugin_says(
    client: AsyncClient, logged_in_headers, active_user, monkeypatch
):
    flow_id, owners_entry = await _flow_owned_by(active_user.id)
    _install_plugin(monkeypatch, set())

    listed = await client.get(f"api/v1/flows/{flow_id}/versions/", headers=logged_in_headers)
    saved = await client.post(f"api/v1/flows/{flow_id}/versions/", json={}, headers=logged_in_headers)
    deleted = await client.delete(f"api/v1/flows/{flow_id}/versions/{owners_entry}", headers=logged_in_headers)
    assert listed.status_code == status.HTTP_200_OK, listed.text
    assert saved.status_code == status.HTTP_201_CREATED, saved.text
    assert deleted.status_code == status.HTTP_204_NO_CONTENT, deleted.text
