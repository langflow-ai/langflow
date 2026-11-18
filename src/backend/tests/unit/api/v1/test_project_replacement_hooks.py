"""The replacement hook seam: ``langflow.services.replacement_hooks`` and its call sites in the replacement route."""

from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from langflow.api.v1 import projects as projects_module
from langflow.api.v1.schemas.replacement_operations import ProjectReplacementRequest
from langflow.services import replacement_hooks
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.project_replacement_operation import ProjectReplacementOperation
from langflow.services.database.models.variable.model import Variable
from langflow.services.deps import session_scope
from langflow.services.replacement_hooks import (
    COMMITTED_HOOK_FAILED_CODE,
    HOOK_FAILED_CODE,
    register_replacement_committed_hook,
    register_replacement_hook,
    registered_replacement_committed_hooks,
    registered_replacement_hooks,
)
from pydantic import ValidationError
from sqlmodel import select


@pytest.fixture(autouse=True)
def _clean_registry():
    saved_hooks = list(replacement_hooks._replacement_hooks)
    saved_committed = list(replacement_hooks._replacement_committed_hooks)
    replacement_hooks._replacement_hooks.clear()
    replacement_hooks._replacement_committed_hooks.clear()
    yield
    replacement_hooks._replacement_hooks[:] = saved_hooks
    replacement_hooks._replacement_committed_hooks[:] = saved_committed


def _flow(*, flow_id: UUID | None = None, name: str) -> dict:
    return {
        "id": str(flow_id or uuid4()),
        "name": name,
        "description": name,
        "data": {"nodes": [], "edges": []},
    }


async def _project_with_flow(active_user, flow_name: str = "before") -> tuple[UUID, UUID]:
    async with session_scope() as session:
        project = Folder(name=f"hooks-{uuid4().hex[:12]}", description="original", user_id=active_user.id)
        session.add(project)
        await session.flush()
        flow = Flow(
            name=flow_name,
            description=flow_name,
            data={"nodes": [], "edges": []},
            user_id=active_user.id,
            folder_id=project.id,
        )
        session.add(flow)
        await session.flush()
        return project.id, flow.id


def _url(project_id: UUID, operation_id: UUID) -> str:
    return f"api/v1/projects/{project_id}/replacement-operations/{operation_id}"


async def _receipt(operation_id: UUID):
    async with session_scope() as session:
        return (
            await session.exec(
                select(ProjectReplacementOperation).where(ProjectReplacementOperation.operation_id == operation_id)
            )
        ).first()


# --- registry -------------------------------------------------------------------------------------------------


def test_nothing_is_registered_by_default():
    assert registered_replacement_hooks() == []
    assert registered_replacement_committed_hooks() == []


def test_registering_twice_is_a_no_op():
    async def hook(_context):
        return None

    async def committed(_context):
        return None

    assert register_replacement_hook(hook) is True
    assert register_replacement_hook(hook) is False
    assert register_replacement_committed_hook(committed) is True
    assert register_replacement_committed_hook(committed) is False
    assert registered_replacement_hooks() == [hook]
    assert registered_replacement_committed_hooks() == [committed]


# --- digest and schema ---------------------------------------------------------------------------------------


def test_principal_id_changes_the_digest_and_null_does_not():
    base = ProjectReplacementRequest(description="d", flows=[])
    explicit_null = ProjectReplacementRequest(description="d", flows=[], execution_principal_id=None)
    with_one = ProjectReplacementRequest(description="d", flows=[], execution_principal_id=uuid4())
    with_other = ProjectReplacementRequest(description="d", flows=[], execution_principal_id=uuid4())

    digest = projects_module._replacement_request_digest
    assert digest(base) == digest(explicit_null)
    assert digest(base) != digest(with_one)
    assert digest(with_one) != digest(with_other)


def test_an_unknown_field_is_still_refused_and_a_bad_principal_id_is_too():
    body = {"description": "d", "flows": []}
    with pytest.raises(ValidationError):
        ProjectReplacementRequest.model_validate({**body, "execution_principal": str(uuid4())})
    with pytest.raises(ValidationError):
        ProjectReplacementRequest.model_validate({**body, "execution_principal_id": "not-a-uuid"})


async def test_without_a_hook_the_field_is_accepted_and_ignored(
    client: AsyncClient, active_user, logged_in_headers: dict[str, str]
):
    project_id, _ = await _project_with_flow(active_user)
    response = await client.put(
        _url(project_id, uuid4()),
        json={"description": "new", "flows": [], "execution_principal_id": str(uuid4())},
        headers=logged_in_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["project"]["description"] == "new"


async def test_a_retry_naming_another_principal_is_refused(
    client: AsyncClient, active_user, logged_in_headers: dict[str, str]
):
    project_id, _ = await _project_with_flow(active_user)
    operation_id = uuid4()
    body = {"description": "new", "flows": [], "execution_principal_id": str(uuid4())}
    first = await client.put(_url(project_id, operation_id), json=body, headers=logged_in_headers)
    same = await client.put(_url(project_id, operation_id), json=body, headers=logged_in_headers)
    other = await client.put(
        _url(project_id, operation_id),
        json={**body, "execution_principal_id": str(uuid4())},
        headers=logged_in_headers,
    )
    assert first.status_code == same.status_code == 200
    assert other.status_code == 409
    assert other.headers["x-langflow-error-code"] == "replacement_operation_id_conflict"


# --- in-transaction hooks ----------------------------------------------------------------------------------


async def test_the_hook_sees_a_coherent_before_and_after_inside_the_transaction(
    client: AsyncClient, active_user, logged_in_headers: dict[str, str]
):
    project_id, existing_id = await _project_with_flow(active_user, "before")
    new_id = uuid4()
    principal = uuid4()
    seen = {}

    async def hook(context):
        seen["before"] = dict(context.flows_before)
        seen["after"] = dict(context.flows_after)
        seen["created"] = context.created
        seen["project_id"] = context.project.id
        seen["principal"] = context.request.execution_principal_id
        seen["user"] = context.current_user.id
        # The new flow is already written in this transaction, the dropped one is already gone.
        seen["new_flow_visible"] = await context.session.get(Flow, new_id) is not None
        seen["dropped_flow_visible"] = await context.session.get(Flow, existing_id) is not None

    register_replacement_hook(hook)
    response = await client.put(
        _url(project_id, uuid4()),
        json={
            "description": "new",
            "flows": [_flow(flow_id=new_id, name="after")],
            "execution_principal_id": str(principal),
        },
        headers=logged_in_headers,
    )

    assert response.status_code == 200, response.text
    assert seen == {
        "before": {existing_id: "before"},
        "after": {new_id: "after"},
        "created": False,
        "project_id": project_id,
        "principal": principal,
        "user": active_user.id,
        "new_flow_visible": True,
        "dropped_flow_visible": False,
    }


async def test_the_hook_is_told_when_the_project_was_created(client: AsyncClient, logged_in_headers: dict[str, str]):
    project_id = uuid4()
    seen = {}

    async def hook(context):
        seen["created"] = context.created
        seen["before"] = dict(context.flows_before)

    register_replacement_hook(hook)
    response = await client.put(
        _url(project_id, uuid4()),
        json={"description": None, "project_name": f"new-{uuid4().hex[:8]}", "flows": [_flow(name="first")]},
        headers=logged_in_headers,
    )
    assert response.status_code == 200, response.text
    assert seen == {"created": True, "before": {}}


async def test_a_hook_refusal_rolls_back_the_flows_the_rows_it_added_and_the_receipt(
    client: AsyncClient, active_user, logged_in_headers: dict[str, str]
):
    project_id, existing_id = await _project_with_flow(active_user)
    operation_id = uuid4()
    marker = f"HOOK_ROW_{uuid4().hex[:8]}"

    async def add_a_row(context):
        context.session.add(Variable(name=marker, value="x", type="Generic", user_id=context.current_user.id))
        await context.session.flush()

    async def refuse(_context):
        raise HTTPException(status_code=422, detail="refused by hook", headers={"X-Langflow-Error-Code": "nope"})

    register_replacement_hook(add_a_row)
    register_replacement_hook(refuse)
    response = await client.put(
        _url(project_id, operation_id),
        json={"description": "new", "flows": [_flow(name="after")]},
        headers=logged_in_headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "refused by hook"
    assert response.headers["x-langflow-error-code"] == "nope"
    async with session_scope() as session:
        assert (await session.get(Flow, existing_id)).name == "before"
        assert (await session.get(Folder, project_id)).description == "original"
        assert (await session.exec(select(Variable).where(Variable.name == marker))).first() is None
    assert await _receipt(operation_id) is None


async def test_a_hook_can_add_rows_that_commit_with_the_replacement(
    client: AsyncClient, active_user, logged_in_headers: dict[str, str]
):
    project_id, _ = await _project_with_flow(active_user)
    marker = f"HOOK_ROW_{uuid4().hex[:8]}"

    async def add_a_row(context):
        context.session.add(Variable(name=marker, value="x", type="Generic", user_id=context.current_user.id))
        await context.session.flush()

    register_replacement_hook(add_a_row)
    response = await client.put(
        _url(project_id, uuid4()), json={"description": "new", "flows": []}, headers=logged_in_headers
    )
    assert response.status_code == 200, response.text
    async with session_scope() as session:
        assert (await session.exec(select(Variable).where(Variable.name == marker))).first() is not None


async def test_any_other_hook_exception_fails_closed_and_rolls_back(
    client: AsyncClient, active_user, logged_in_headers: dict[str, str]
):
    project_id, existing_id = await _project_with_flow(active_user)
    operation_id = uuid4()

    async def broken(_context):
        msg = "boom"
        raise RuntimeError(msg)

    register_replacement_hook(broken)
    response = await client.put(
        _url(project_id, operation_id),
        json={"description": "new", "flows": [_flow(name="after")]},
        headers=logged_in_headers,
    )

    assert response.status_code == 500
    assert response.headers["x-langflow-error-code"] == HOOK_FAILED_CODE
    assert "boom" not in response.text
    async with session_scope() as session:
        assert (await session.get(Flow, existing_id)).name == "before"
    assert await _receipt(operation_id) is None


# --- committed hooks ----------------------------------------------------------------------------------------


async def test_committed_hooks_run_after_the_commit_and_again_on_a_replay(
    client: AsyncClient, active_user, logged_in_headers: dict[str, str]
):
    project_id, existing_id = await _project_with_flow(active_user, "before")
    operation_id = uuid4()
    new_id = uuid4()
    calls = []

    async def committed(context):
        # No session is handed over: the receipt is already readable from a fresh one.
        calls.append(
            {
                "replayed": context.replayed,
                "before": None if context.flows_before is None else dict(context.flows_before),
                "after": dict(context.flows_after),
                "receipt_committed": await _receipt(context.operation_id) is not None,
                "project_user_id": context.project_user_id,
            }
        )

    register_replacement_committed_hook(committed)
    body = {"description": "new", "flows": [_flow(flow_id=new_id, name="after")]}
    first = await client.put(_url(project_id, operation_id), json=body, headers=logged_in_headers)
    replay = await client.put(_url(project_id, operation_id), json=body, headers=logged_in_headers)

    assert first.status_code == replay.status_code == 200, first.text + replay.text
    assert first.json() == replay.json()
    assert calls == [
        {
            "replayed": False,
            "before": {existing_id: "before"},
            "after": {new_id: "after"},
            "receipt_committed": True,
            "project_user_id": active_user.id,
        },
        {
            "replayed": True,
            "before": None,
            "after": {new_id: "after"},
            "receipt_committed": True,
            "project_user_id": active_user.id,
        },
    ]


async def test_committed_hooks_do_not_run_when_the_replacement_is_refused(
    client: AsyncClient, active_user, logged_in_headers: dict[str, str]
):
    project_id, _ = await _project_with_flow(active_user)
    calls = []

    async def refuse(_context):
        raise HTTPException(status_code=409, detail="no")

    async def committed(context):
        calls.append(context)

    register_replacement_hook(refuse)
    register_replacement_committed_hook(committed)
    response = await client.put(
        _url(project_id, uuid4()), json={"description": "new", "flows": []}, headers=logged_in_headers
    )
    assert response.status_code == 409
    assert calls == []


async def test_a_failed_committed_hook_leaves_the_replacement_saved_and_a_retry_runs_it_again(
    client: AsyncClient, active_user, logged_in_headers: dict[str, str]
):
    project_id, _ = await _project_with_flow(active_user)
    operation_id = uuid4()
    attempts = []

    async def flaky(context):
        attempts.append(context.replayed)
        if len(attempts) == 1:
            msg = "policy reload failed"
            raise RuntimeError(msg)

    register_replacement_committed_hook(flaky)
    body = {"description": "new", "flows": [_flow(name="after")]}
    first = await client.put(_url(project_id, operation_id), json=body, headers=logged_in_headers)
    assert first.status_code == 500
    assert first.headers["x-langflow-error-code"] == COMMITTED_HOOK_FAILED_CODE
    assert await _receipt(operation_id) is not None
    async with session_scope() as session:
        assert (await session.get(Folder, project_id)).description == "new"

    retry = await client.put(_url(project_id, operation_id), json=body, headers=logged_in_headers)
    assert retry.status_code == 200, retry.text
    assert attempts == [False, True]


async def test_a_replay_with_a_changed_body_does_not_run_committed_hooks(
    client: AsyncClient, active_user, logged_in_headers: dict[str, str]
):
    project_id, _ = await _project_with_flow(active_user)
    operation_id = uuid4()
    calls = []

    async def committed(context):
        calls.append(context.replayed)

    register_replacement_committed_hook(committed)
    body = {"description": "new", "flows": []}
    assert (await client.put(_url(project_id, operation_id), json=body, headers=logged_in_headers)).status_code == 200
    changed = await client.put(
        _url(project_id, operation_id), json={**body, "description": "other"}, headers=logged_in_headers
    )
    assert changed.status_code == 409
    assert calls == [False]
