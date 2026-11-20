"""The deletion hooks fire at the call points for flows, projects, memory bases and share revocation."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, status
from httpx import AsyncClient
from langflow.services.database.models.auth import AuthzShare
from langflow.services.database.models.memory_base.model import MemoryBase
from langflow.services.deps import session_scope

FLOW_BODY = {"name": "hooked-flow", "description": "", "data": {"nodes": [], "edges": []}}


async def _project(client: AsyncClient, headers, name="hooked-project") -> str:
    response = await client.post("api/v1/projects/", json={"name": name, "description": ""}, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["id"]


async def _flow(client: AsyncClient, headers, project_id: str, name="hooked-flow") -> str:
    response = await client.post(
        "api/v1/flows/", json={**FLOW_BODY, "name": name, "folder_id": project_id}, headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["id"]


def _recorder(deletion_registry, *resources):
    seen = []

    async def post(context):
        seen.append(context)

    for resource in resources:
        deletion_registry.register_post_deletion_hook(resource, post)
    return seen


async def test_deleting_a_flow_runs_the_post_deletion_hooks_once_it_committed(
    deletion_registry, client: AsyncClient, logged_in_headers, active_user
):
    project_id = await _project(client, logged_in_headers)
    flow_id = await _flow(client, logged_in_headers, project_id)
    seen = _recorder(deletion_registry, "flow")

    response = await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    await deletion_registry.wait_for_post_deletion_runs()

    assert [(c.resource, str(c.resource_id), c.owner_id, c.name) for c in seen] == [
        ("flow", flow_id, active_user.id, "hooked-flow")
    ]
    assert str(seen[0].extra["project_id"]) == project_id
    assert seen[0].session is None


async def test_deleting_a_project_runs_the_hooks_for_the_project_and_each_of_its_flows(
    deletion_registry, client: AsyncClient, logged_in_headers, active_user
):
    project_id = await _project(client, logged_in_headers, "doomed-project")
    first = await _flow(client, logged_in_headers, project_id, "one")
    second = await _flow(client, logged_in_headers, project_id, "two")
    seen = _recorder(deletion_registry, "project", "flow")

    response = await client.delete(f"api/v1/projects/{project_id}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
    await deletion_registry.wait_for_post_deletion_runs()

    assert {(c.resource, str(c.resource_id)) for c in seen} == {
        ("project", project_id),
        ("flow", first),
        ("flow", second),
    }
    project_event = next(c for c in seen if c.resource == "project")
    assert project_event.owner_id == active_user.id
    assert project_event.name == "doomed-project"


async def test_a_project_delete_that_is_refused_runs_no_post_deletion_hook(
    deletion_registry, client: AsyncClient, logged_in_headers
):
    seen = _recorder(deletion_registry, "project", "flow")
    response = await client.delete(f"api/v1/projects/{uuid.uuid4()}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    await deletion_registry.wait_for_post_deletion_runs()
    assert seen == []


async def test_a_flow_delete_that_rolls_back_runs_no_post_deletion_hook(
    deletion_registry, client: AsyncClient, logged_in_headers
):
    project_id = await _project(client, logged_in_headers)
    flow_id = await _flow(client, logged_in_headers, project_id)
    seen = _recorder(deletion_registry, "flow")

    with patch("langflow.api.utils.flow_utils.delete_triggers", new=AsyncMock(side_effect=RuntimeError("boom"))):
        response = await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert response.status_code >= status.HTTP_400_BAD_REQUEST
    await deletion_registry.wait_for_post_deletion_runs()

    assert seen == []
    assert (await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)).status_code == 200


async def test_purging_a_flows_memory_bases_runs_the_hooks_after_commit(deletion_registry, active_user):
    from langflow.services.memory_base.flow_cleanup import purge_flow_memory_bases

    flow_id = uuid.uuid4()
    memory_base = MemoryBase(id=uuid.uuid4(), name="mb", kb_name="mb-kb", flow_id=flow_id, user_id=active_user.id)
    async with session_scope() as session:
        session.add(memory_base)
        await session.commit()
    seen = _recorder(deletion_registry, "memory_base")

    async with session_scope() as session:
        await purge_flow_memory_bases(session, flow_id)
        await deletion_registry.wait_for_post_deletion_runs()
        assert seen == []  # not before the transaction commits
        await session.commit()
    await deletion_registry.wait_for_post_deletion_runs()

    assert [(c.resource_id, c.owner_id, c.name, c.via) for c in seen] == [
        (memory_base.id, active_user.id, "mb", "cascade")
    ]
    assert seen[0].extra["flow_id"] == flow_id


async def test_memory_base_service_delete_runs_pre_then_post_hooks(deletion_registry, active_user):
    from langflow.services.deps import get_memory_base_service

    memory_base = MemoryBase(id=uuid.uuid4(), name="svc", kb_name="", flow_id=uuid.uuid4(), user_id=active_user.id)
    async with session_scope() as session:
        session.add(memory_base)
        await session.commit()
    order = []

    async def pre(context):
        async with session_scope() as other:
            order.append(("pre", await other.get(MemoryBase, context.resource_id) is not None, context.session))

    async def post(context):
        async with session_scope() as other:
            order.append(("post", await other.get(MemoryBase, context.resource_id) is not None, context.session))

    deletion_registry.register_pre_deletion_hook("memory_base", pre)
    deletion_registry.register_post_deletion_hook("memory_base", post)
    with patch("langflow.services.memory_base.service.delete_kb", new=AsyncMock()):
        assert await get_memory_base_service().delete(memory_base.id, user_id=active_user.id) is True

    assert [(phase, visible) for phase, visible, _ in order] == [("pre", True), ("post", False)]
    assert order[0][2] is not None
    assert order[1][2] is None


async def test_a_pre_deletion_refusal_keeps_the_memory_base(deletion_registry, active_user):
    from langflow.services.deps import get_memory_base_service

    memory_base = MemoryBase(id=uuid.uuid4(), name="kept", kb_name="", flow_id=uuid.uuid4(), user_id=active_user.id)
    async with session_scope() as session:
        session.add(memory_base)
        await session.commit()

    async def refuse(_context):
        raise HTTPException(status_code=409, detail="in use")

    deletion_registry.register_pre_deletion_hook("memory_base", refuse)
    with pytest.raises(HTTPException):
        await get_memory_base_service().delete(memory_base.id, user_id=active_user.id)
    async with session_scope() as session:
        assert await session.get(MemoryBase, memory_base.id) is not None


async def _own_variable_share(client: AsyncClient, headers, active_user) -> tuple[uuid.UUID, uuid.UUID]:
    response = await client.post(
        "api/v1/variables/",
        json={"name": "shared-var", "value": "x", "type": "Generic", "default_fields": ["f"]},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    variable = response.json()
    share = AuthzShare(
        resource_type="variable",
        resource_id=uuid.UUID(variable["id"]),
        scope="user",
        target_id=uuid.uuid4(),
        permission_level="read",
        created_by=active_user.id,
    )
    async with session_scope() as session:
        session.add(share)
        await session.commit()
    return share.id, uuid.UUID(variable["id"])


async def test_share_revocation_is_offered_to_the_plugin_with_operation_delete(
    client: AsyncClient, logged_in_headers, active_user
):
    share_id, variable_id = await _own_variable_share(client, logged_in_headers, active_user)
    calls = []

    async def validate(**kwargs):
        calls.append(kwargs)

    with patch("langflow.api.v1.authz_shares._validate_share_write", new=validate):
        response = await client.delete(f"api/v1/authz/shares/{share_id}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
    assert [(c["operation"], c["resource_type"], c["resource_id"], c["owner_id"]) for c in calls] == [
        ("delete", "variable", variable_id, active_user.id)
    ]
    async with session_scope() as session:
        assert await session.get(AuthzShare, share_id) is None


async def test_a_plugin_refusal_keeps_the_share_and_answers_like_any_refused_share(
    client: AsyncClient, logged_in_headers, active_user
):
    share_id, _ = await _own_variable_share(client, logged_in_headers, active_user)

    async def refuse(**_kwargs):
        raise HTTPException(status_code=403, detail="nothing leaves")

    with patch("langflow.api.v1.authz_shares._validate_share_write", new=refuse):
        response = await client.delete(f"api/v1/authz/shares/{share_id}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    async with session_scope() as session:
        assert await session.get(AuthzShare, share_id) is not None
