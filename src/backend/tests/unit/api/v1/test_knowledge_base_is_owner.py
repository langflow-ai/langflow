"""``is_owner`` on knowledge base list and detail responses."""

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from langflow.api.utils import knowledge_base_service
from langflow.api.v1 import knowledge_bases as kb_api
from langflow.schema.knowledge_base import KnowledgeBaseInfo
from lfx.services.authorization.base import ResourceVisibilityScope

KB_LIST_URL = "api/v1/knowledge_bases"


async def _seed(user_id, name: str):
    return await knowledge_base_service.create_record(
        user_id=user_id,
        name=name,
        model_selection={"name": "model", "provider": "OpenAI"},
        backend_type="opensearch",
        backend_config={"index_name": name.lower()},
    )


def _grant(monkeypatch, scope: ResourceVisibilityScope) -> None:
    # Stands in for an authz plugin; the real owned-or-visible SQL query still runs.
    monkeypatch.setattr(kb_api, "visible_scope_prefilter", AsyncMock(return_value=scope))


async def _list(client: AsyncClient, headers) -> dict[str, dict]:
    response = await client.get(KB_LIST_URL, headers=headers)
    assert response.status_code == 200, response.text
    return {kb["id"]: kb for kb in response.json()}


async def test_should_mark_own_kb_as_owned_when_listing(client, logged_in_headers, active_user):
    own = await _seed(active_user.id, "Own_KB")

    listed = await _list(client, logged_in_headers)

    assert listed[str(own.id)]["is_owner"] is True


async def test_should_mark_shared_kb_as_not_owned(client, logged_in_headers, active_user, user_two, monkeypatch):
    own = await _seed(active_user.id, "Own_KB")
    shared = await _seed(user_two.id, "Shared_KB")
    hidden = await _seed(user_two.id, "Hidden_KB")
    _grant(monkeypatch, ResourceVisibilityScope(resource_ids=(shared.id,)))

    listed = await _list(client, logged_in_headers)

    assert listed[str(own.id)]["is_owner"] is True
    assert listed[str(shared.id)]["is_owner"] is False
    assert str(hidden.id) not in listed


async def test_should_mark_role_visible_kb_as_not_owned(client, logged_in_headers, active_user, user_two, monkeypatch):
    own = await _seed(active_user.id, "Own_KB")
    role_visible = await _seed(user_two.id, "Role_KB")
    _grant(monkeypatch, ResourceVisibilityScope(all_resources=True))

    listed = await _list(client, logged_in_headers)

    assert listed[str(own.id)]["is_owner"] is True
    assert listed[str(role_visible.id)]["is_owner"] is False


async def test_should_return_empty_list_when_user_has_no_kbs(client, logged_in_headers, user_two):
    await _seed(user_two.id, "Not_Mine_KB")

    response = await client.get(KB_LIST_URL, headers=logged_in_headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_should_keep_other_fields_unchanged_when_adding_is_owner(client, logged_in_headers, active_user):
    own = await _seed(active_user.id, "Fields_KB")
    await knowledge_base_service.update_stats(own.id, chunks=3, words=30, characters=150, size_bytes=512)

    kb = (await _list(client, logged_in_headers))[str(own.id)]

    assert set(kb) == set(KnowledgeBaseInfo.model_fields)
    assert {k: kb[k] for k in ("name", "dir_name", "backend_type", "backend_config", "size", "chunks", "status")} == {
        "name": "Fields KB",
        "dir_name": "Fields_KB",
        "backend_type": "opensearch",
        "backend_config": {"index_name": "fields_kb"},
        "size": 512,
        "chunks": 3,
        "status": "ready",
    }


async def test_should_mark_own_kb_as_owned_in_detail(client, logged_in_headers, active_user):
    await _seed(active_user.id, "Detail_Own_KB")

    response = await client.get(f"{KB_LIST_URL}/Detail_Own_KB", headers=logged_in_headers)

    assert response.status_code == 200
    assert response.json()["is_owner"] is True


async def test_should_mark_shared_kb_as_not_owned_in_detail(active_user, user_two, monkeypatch):
    shared = await _seed(user_two.id, "Detail_Shared_KB")
    # The guard resolves a share grant to the owner's row; this is its result for a non-owner.
    guard = kb_api._KbGuardResult(record=shared, owner_user=user_two)
    monkeypatch.setattr(kb_api, "_guard_kb_action", AsyncMock(return_value=guard))
    monkeypatch.setattr(kb_api, "_assert_kb_not_memory_base", AsyncMock())

    info = await kb_api.get_knowledge_base("Detail_Shared_KB", current_user=active_user)

    assert info.is_owner is False
    assert info.id == str(shared.id)


def test_should_serialize_null_is_owner_when_ownership_is_unresolved():
    assert KnowledgeBaseInfo(id="kb", name="kb").model_dump()["is_owner"] is None


@pytest.mark.parametrize("value", [True, False])
def test_should_round_trip_is_owner(value):
    assert KnowledgeBaseInfo(id="kb", name="kb", is_owner=value).model_dump()["is_owner"] is value
