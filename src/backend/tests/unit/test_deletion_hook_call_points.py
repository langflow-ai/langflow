"""The deletion hooks fire at the call points for flows, projects, memory bases and share revocation."""

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, status
from httpx import AsyncClient
from langflow.services.database.models.auth import AuthzShare
from langflow.services.database.models.flow.model import Flow
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
    assert seen[0].via == "request"
    assert str(seen[0].extra["project_id"]) == project_id
    assert seen[0].session is None


async def test_deleting_a_project_runs_the_hooks_for_the_project_and_each_of_its_flows(
    deletion_registry, client: AsyncClient, logged_in_headers, active_user, user_two
):
    project_id = await _project(client, logged_in_headers, "doomed-project")
    first = await _flow(client, logged_in_headers, project_id, "one")
    second = await _flow(client, logged_in_headers, project_id, "two")
    async with session_scope() as session:
        contributor = Flow(name="contributor", user_id=user_two.id, folder_id=uuid.UUID(project_id))
        session.add(contributor)
        await session.commit()
    seen = _recorder(deletion_registry, "project", "flow")

    response = await client.delete(f"api/v1/projects/{project_id}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
    await deletion_registry.wait_for_post_deletion_runs()

    assert {(c.resource, str(c.resource_id)) for c in seen} == {
        ("project", project_id),
        ("flow", first),
        ("flow", second),
        ("flow", str(contributor.id)),
    }
    assert {c.via for c in seen if c.resource == "flow"} == {"cascade"}
    project_event = next(c for c in seen if c.resource == "project")
    assert project_event.owner_id == active_user.id
    assert project_event.name == "doomed-project"


@pytest.mark.parametrize(("resource", "via"), [("flow", "request"), ("project", "request"), ("flow", "cascade")])
async def test_resource_pre_hook_refuses_deletion_before_cleanup(
    deletion_registry, client: AsyncClient, logged_in_headers, resource, via
):
    project_id = await _project(client, logged_in_headers)
    flow_id = await _flow(client, logged_in_headers, project_id)
    seen = _recorder(deletion_registry, "project", "flow")
    route = f"api/v1/flows/{flow_id}" if resource == "flow" and via == "request" else f"api/v1/projects/{project_id}"

    async def refuse(context):
        assert context.via == via
        assert context.session is not None
        raise HTTPException(status_code=409, detail="in use")

    deletion_registry.register_pre_deletion_hook(resource, refuse)
    with patch("langflow.api.v1.projects.cleanup_mcp_on_delete", new=AsyncMock()) as cleanup:
        response = await client.delete(route, headers=logged_in_headers)
    assert response.status_code == status.HTTP_409_CONFLICT, response.text
    cleanup.assert_not_awaited()
    assert (await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)).status_code == 200
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


async def test_builder_erase_dispatches_each_resource_with_erase_origin(deletion_registry, active_user):
    from langflow.services.data_subjects.builder_account_steps import erase_files, erase_folders, erase_variables
    from langflow.services.data_subjects.builder_flow_steps import erase_owned_flows
    from langflow.services.data_subjects.context import EraseContext
    from langflow.services.database.models.file.model import File
    from langflow.services.database.models.folder.model import Folder
    from langflow.services.database.models.variable.model import Variable

    owner = active_user.id
    flow = Flow(name="erased-flow", user_id=owner)
    memory = MemoryBase(name="erased-memory", kb_name="", flow_id=flow.id, user_id=owner)
    file = File(name="erased.txt", path="erased.txt", size=0, user_id=owner)
    variable = Variable(name="erased", value="", default_fields=None, user_id=owner)
    project = Folder(name="erased-project", user_id=owner)
    async with session_scope() as session:
        session.add_all([flow, memory, file, variable, project])
    contexts = {
        ("flow", flow.id),
        ("memory_base", memory.id),
        ("file", file.id),
        ("variable", variable.id),
        ("project", project.id),
    }
    checked = []

    async def pre(context):
        checked.append(context)

    resources = sorted({resource for resource, _ in contexts})
    seen = _recorder(deletion_registry, *resources)
    for resource in resources:
        deletion_registry.register_pre_deletion_hook(resource, pre)
    ctx = EraseContext(uuid.uuid4(), owner)
    async with session_scope() as session:
        assert await erase_owned_flows(session, ctx) == 1
        assert await erase_files(session, ctx) == 1
        assert await erase_variables(session, ctx) == 1
        assert await erase_folders(session, ctx) >= 1
        assert seen == []
    await deletion_registry.wait_for_post_deletion_runs()

    for events in (checked, seen):
        assert contexts <= {(event.resource, event.resource_id) for event in events}
        assert {event.via for event in events} == {"erase"}
    assert all(event.session is None for event in seen)


async def test_memory_base_deletion_guards_its_kb_and_finishes_cleanup_before_post_hooks(
    deletion_registry, active_user
):
    from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
    from langflow.services.deps import get_memory_base_service

    kb = KnowledgeBaseRecord(name="backing-kb", user_id=active_user.id)
    memory = MemoryBase(name="linked", kb_name=kb.name, flow_id=uuid.uuid4(), user_id=active_user.id)
    async with session_scope() as session:
        session.add_all([kb, memory])
    refuse = True

    async def guard(context):
        assert context.resource_id == kb.id
        assert context.via == "cascade"
        assert context.session is not None
        if refuse:
            raise HTTPException(status_code=409, detail="in use")

    async def broken(_context):
        raise HTTPException(status_code=500, detail="plugin cleanup failed")

    deletion_registry.register_pre_deletion_hook("knowledge_base", guard)
    deletion_registry.register_post_deletion_hook("memory_base", broken)
    seen = _recorder(deletion_registry, "knowledge_base")
    service = get_memory_base_service()
    with (
        patch("langflow.services.knowledge_base_storage.runtime.delete_storage_for_record", new=AsyncMock()) as storage,
        patch("langflow.services.memory_base.service.delete_kb", new=AsyncMock()) as cleanup,
    ):
        with pytest.raises(HTTPException) as denied:
            await service.delete(memory.id, user_id=active_user.id)
        assert denied.value.status_code == 409
        storage.assert_not_awaited()
        assert not seen
        refuse = False
        with pytest.raises(HTTPException) as cleanup_error:
            await service.delete(memory.id, user_id=active_user.id)
        assert cleanup_error.value.status_code == 500
        storage.assert_awaited_once()
        cleanup.assert_awaited_once()

    assert [(c.resource_id, c.via) for c in seen] == [(kb.id, "cascade")]
    async with session_scope() as session:
        assert await session.get(MemoryBase, memory.id) is None
        assert await session.get(KnowledgeBaseRecord, kb.id) is None


async def test_concurrent_memory_base_deletes_dispatch_post_hooks_once(deletion_registry, active_user):
    from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
    from langflow.services.deps import get_memory_base_service

    owner = active_user.id
    kb = KnowledgeBaseRecord(name="racing-kb", user_id=owner)
    memory = MemoryBase(name="racing", kb_name=kb.name, flow_id=uuid.uuid4(), user_id=owner)
    async with session_scope() as session:
        session.add_all([kb, memory])
    arrived = 0
    release = asyncio.Event()

    async def pause_storage(_record):
        nonlocal arrived
        arrived += 1
        if arrived == 2:
            release.set()
        await asyncio.wait_for(release.wait(), timeout=5)

    seen = _recorder(deletion_registry, "memory_base", "knowledge_base")
    service = get_memory_base_service()
    with (
        patch("langflow.services.knowledge_base_storage.runtime.delete_storage_for_record", side_effect=pause_storage),
        patch("langflow.services.memory_base.service.delete_kb", new=AsyncMock()) as cleanup,
    ):
        results = await asyncio.gather(
            service.delete(memory.id, user_id=owner),
            service.delete(memory.id, user_id=owner),
        )
    assert results == [True, True]
    cleanup.assert_awaited_once()
    assert [(event.resource, event.resource_id) for event in seen] == [
        ("memory_base", memory.id),
        ("knowledge_base", kb.id),
    ]


async def test_rollback_after_delete_savepoint_restores_the_flow_and_discards_the_event(deletion_registry, active_user):
    from langflow.api.utils.flow_utils import begin_flow_deletion_transaction, cascade_delete_flow

    flow = Flow(name="rollback-after-savepoint", user_id=active_user.id)
    async with session_scope() as session:
        session.add(flow)
    seen = _recorder(deletion_registry, "flow")

    async with session_scope() as session:
        # A SELECT triggers SQLAlchemy's autobegin even when SQLite's driver
        # has yet to begin a physical transaction.
        assert await session.get(Flow, flow.id) is not None
        await begin_flow_deletion_transaction(session)
        async with session.begin_nested():
            assert await cascade_delete_flow(session, flow.id)
        await session.rollback()
    await deletion_registry.wait_for_post_deletion_runs()

    assert seen == []
    async with session_scope() as session:
        assert await session.get(Flow, flow.id) is not None
