from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from langflow.api.v1 import projects as projects_module
from langflow.api.v1.schemas.replacement_operations import ProjectReplacementRequest, ReplacementFlowCreate
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.project_replacement_operation import ProjectReplacementOperation
from langflow.services.deps import session_scope
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


class _DeadlockDetectedError(Exception):
    """Stand-in for psycopg's DeadlockDetected (SQLSTATE 40P01).

    psycopg is only available with the postgres extra, so importing it at
    module level breaks collection in a plain CI install. See
    test_auth_service.py for the same pattern.
    """

    sqlstate = "40P01"


def _deadlock_error(statement: str, message: str) -> OperationalError:
    return OperationalError(statement, None, _DeadlockDetectedError(message))


def _flow_payload(*, flow_id: UUID | None = None, name: str, endpoint_name: str | None = None) -> dict:
    payload = {
        "name": name,
        "description": f"description for {name}",
        "data": {"nodes": [], "edges": []},
    }
    if flow_id is not None:
        payload["id"] = str(flow_id)
    if endpoint_name is not None:
        payload["endpoint_name"] = endpoint_name
    return payload


async def _create_project(active_user, name: str | None = None) -> dict:
    project_name = name or f"t194-{uuid4().hex[:16]}"
    async with session_scope() as session:
        project = Folder(name=project_name, description="original description", user_id=active_user.id)
        session.add(project)
        await session.flush()
        return {"id": str(project.id), "name": project.name, "description": project.description}


async def _create_flow(active_user, project_id: str, flow_payload: dict) -> dict:
    flow_id = UUID(flow_payload["id"]) if flow_payload.get("id") else uuid4()
    async with session_scope() as session:
        flow = Flow(
            id=flow_id,
            name=flow_payload["name"],
            description=flow_payload["description"],
            data=flow_payload["data"],
            endpoint_name=flow_payload.get("endpoint_name"),
            fs_path=flow_payload.get("fs_path"),
            user_id=active_user.id,
            folder_id=UUID(project_id),
            locked=flow_payload.get("locked", False),
        )
        session.add(flow)
        await session.flush()
        return {
            "id": str(flow.id),
            "name": flow.name,
            "endpoint_name": flow.endpoint_name,
            "description": flow.description,
            "data": flow.data,
            "fs_path": flow.fs_path,
            "locked": flow.locked,
        }


def test_replacement_digest_preserves_legacy_no_dependency_shape() -> None:
    base = ProjectReplacementRequest(description="digest", flows=[])
    empty = ProjectReplacementRequest(description="digest", flows=[], dependencies={})
    with_dependency = ProjectReplacementRequest(
        description="digest",
        flows=[],
        dependencies={"knowledgeBases": [{"name": "kb"}]},
    )

    assert projects_module._replacement_request_digest(base) == projects_module._replacement_request_digest(empty)
    assert projects_module._replacement_request_digest(base) != projects_module._replacement_request_digest(
        with_dependency
    )


def test_replacement_digest_matches_a_pinned_value() -> None:
    """Pin one digest so silent encoding drift is caught instead of shipped.

    ``_replacement_request_digest`` binds a replacement receipt to the exact
    request body that produced it (see the digest comparison in
    ``_replace_project_operation_once``). If canonical_json_digest's encoding
    ever drifts (field order, separators, escaping), an identical retry of an
    old request would digest differently and get spuriously rejected as
    "Operation ID already used with a different request" - this hard-codes one
    known-good digest so that drift fails a test instead of a retry in
    production.
    """
    request = ProjectReplacementRequest(
        description="pinned digest",
        flows=[
            ReplacementFlowCreate(
                id=UUID("00000000-0000-0000-0000-000000000001"),
                name="Pinned Flow",
                data={"nodes": [], "edges": []},
            )
        ],
    )

    digest = projects_module._replacement_request_digest(request)

    assert digest == "c1ae5b89480dd418ac8f6369c41fdd1e9aeb6776ef523f152fb063f60da83abb"


def test_replacement_digest_distinguishes_null_from_present_description() -> None:
    """A null description is a real, distinct value — not the same digest as any string."""
    null_description = ProjectReplacementRequest(description=None, flows=[])
    empty_string_description = ProjectReplacementRequest(description="", flows=[])

    assert projects_module._replacement_request_digest(null_description) != projects_module._replacement_request_digest(
        empty_string_description
    )


def test_replacement_flow_rejects_blank_name() -> None:
    """A blank (or whitespace-only) flow name must fail request validation, not save as-is."""
    for blank_name in ("", "   "):
        with pytest.raises(ValidationError, match="name must not be blank"):
            ReplacementFlowCreate(id=uuid4(), name=blank_name, data={"nodes": [], "edges": []})


def test_replacement_flow_rejects_null_data() -> None:
    """`data: None` must fail request validation, not commit content the snapshot later refuses.

    The deployment snapshot's strict capture refuses a flow with no graph data
    ("flow has no graph data") - this catches the same content at request time.
    """
    with pytest.raises(ValidationError):
        ReplacementFlowCreate(id=uuid4(), name="valid name", data=None)


async def test_replacement_rejects_blank_flow_name_over_http(client: AsyncClient, active_user, logged_in_headers):
    project = await _create_project(active_user)
    project_id = project["id"]
    body = {
        "description": "must not commit",
        "flows": [{**_flow_payload(name="   "), "id": str(uuid4())}],
    }

    response = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{uuid4()}", json=body, headers=logged_in_headers
    )

    assert response.status_code == 422, response.text
    async with session_scope() as session:
        stored_flows = list((await session.exec(select(Flow).where(Flow.folder_id == UUID(project_id)))).all())
        assert stored_flows == []


async def test_replacement_rejects_null_flow_data_over_http(client: AsyncClient, active_user, logged_in_headers):
    project = await _create_project(active_user)
    project_id = project["id"]
    body = {
        "description": "must not commit",
        "flows": [{"id": str(uuid4()), "name": "no data", "data": None}],
    }

    response = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{uuid4()}", json=body, headers=logged_in_headers
    )

    assert response.status_code == 422, response.text
    async with session_scope() as session:
        stored_flows = list((await session.exec(select(Flow).where(Flow.folder_id == UUID(project_id)))).all())
        assert stored_flows == []


async def test_replacement_rejects_lone_unicode_surrogate_as_422(client: AsyncClient, active_user, logged_in_headers):
    r"""A lone (unpaired) Unicode surrogate must fail with 422 + an error code, not an unhandled 500.

    Sent as a raw request body with the surrogate *escaped* (``\ud800``, plain
    ASCII on the wire): httpx's own ``json=`` encoding tries to UTF-8 encode
    the raw character client-side and refuses to even send it, but a raw
    ``\ud800`` escape round-trips through JSON as an ordinary 6-byte ASCII
    sequence. The server's ``json.loads`` then reconstructs the same lone
    surrogate as a legal Python ``str`` - it passes pydantic validation, but
    canonical_json_digest's UTF-8 encode step cannot represent it and raised
    UnicodeEncodeError before this fix, escaping every exception handler in
    the replacement transaction as an unhandled 500.
    """
    project = await _create_project(active_user)
    project_id = project["id"]
    flow_id = uuid4()
    raw_body = (
        f'{{"description": "surrogate test", "flows": [{{"id": "{flow_id}", '
        '"name": "Invalid \\ud800 name", "data": {"nodes": [], "edges": []}}]}'
    ).encode("ascii")

    response = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{uuid4()}",
        content=raw_body,
        headers={**logged_in_headers, "Content-Type": "application/json"},
    )

    assert response.status_code == 422, response.text
    assert response.headers.get("x-langflow-error-code") == "replacement_invalid_unicode"
    async with session_scope() as session:
        stored_flows = list((await session.exec(select(Flow).where(Flow.folder_id == UUID(project_id)))).all())
        assert stored_flows == []


async def test_replacement_restores_a_null_description_unchanged(client: AsyncClient, active_user, logged_in_headers):
    """A snapshot can carry a null project description and must be restorable as-is."""
    project = await _create_project(active_user)
    project_id = project["id"]
    url = f"api/v1/projects/{project_id}/replacement-operations/{uuid4()}"
    body = {"description": None, "flows": []}

    response = await client.put(url, json=body, headers=logged_in_headers)

    assert response.status_code == 200, response.text
    assert response.json()["project"]["description"] is None

    async with session_scope() as session:
        stored_project = await session.get(Folder, UUID(project_id))
        assert stored_project.description is None

    replay = await client.put(url, json=body, headers=logged_in_headers)
    assert replay.status_code == 200, replay.text
    assert replay.json() == response.json()


async def test_replacement_deadlock_retry_recovers_from_a_real_transaction(
    client: AsyncClient, active_user, logged_in_headers, monkeypatch
):
    """A real 40P01 raised inside the transaction rolls back and retries from a clean body.

    Injects the deadlock at the first *explicit* ``session.flush()`` call reached while
    updating an existing flow (patching ``AsyncSession.flush`` at the class level does not
    intercept SQLAlchemy's internal autoflush, which calls the sync session's flush
    directly — only application code's own ``await session.flush()`` goes through this
    seam). The retried attempt must still land the originally requested content: if
    ``replace_project_operation`` reused a body a failed attempt had already mutated
    instead of a fresh copy, the persisted result would diverge from the request.
    """
    project = await _create_project(active_user)
    project_id = project["id"]
    flow = await _create_flow(active_user, project_id, _flow_payload(name=f"retry-{uuid4().hex[:8]}"))
    operation_id = str(uuid4())
    url = f"api/v1/projects/{project_id}/replacement-operations/{operation_id}"
    body = {
        "description": "retried replacement",
        "flows": [
            {
                **_flow_payload(flow_id=UUID(flow["id"]), name=f"retried-{uuid4().hex[:8]}"),
                "data": {"nodes": [], "edges": [], "marker": "target-after-retry"},
            }
        ],
    }

    original_flush = AsyncSession.flush
    flush_calls = 0

    async def flush_with_one_deadlock(self, *args, **kwargs):
        nonlocal flush_calls
        flush_calls += 1
        if flush_calls == 1:
            statement, message = "UPDATE flow", "simulated deadlock on first flush"
            raise _deadlock_error(statement, message)
        return await original_flush(self, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "flush", flush_with_one_deadlock)

    # Spy on _replace_project_operation_once itself (not just the flush count)
    # so a deadlock that happens to trigger more than one internal flush per
    # attempt cannot silently inflate flush_calls without a real whole-
    # transaction retry actually running.
    original_replace_once = projects_module._replace_project_operation_once
    attempt_calls = 0

    async def counting_replace_once(**kwargs):
        nonlocal attempt_calls
        attempt_calls += 1
        return await original_replace_once(**kwargs)

    monkeypatch.setattr(projects_module, "_replace_project_operation_once", counting_replace_once)

    replaced = await client.put(url, json=body, headers=logged_in_headers)

    assert replaced.status_code == 200, replaced.text
    assert flush_calls >= 2, "the first flush must have raised and the attempt retried"
    assert attempt_calls == 2, "the whole operation must run exactly twice: the deadlocked attempt, then recovery"
    assert replaced.json()["flows"][0]["name"] == body["flows"][0]["name"]
    assert replaced.json()["flows"][0]["data"] == body["flows"][0]["data"]

    async with session_scope() as session:
        stored_flow = await session.get(Flow, UUID(flow["id"]))
        assert stored_flow.name == body["flows"][0]["name"]
        assert stored_flow.data == body["flows"][0]["data"]
        receipts = list(
            (
                await session.exec(
                    select(ProjectReplacementOperation).where(
                        ProjectReplacementOperation.project_id == UUID(project_id),
                        ProjectReplacementOperation.operation_id == UUID(operation_id),
                    )
                )
            ).all()
        )
        assert len(receipts) == 1
        expected_receipt = replaced.json()
        expected_receipt.pop("dependencies", None)
        assert receipts[0].result == expected_receipt

    replay = await client.get(url, headers=logged_in_headers)
    assert replay.status_code == 200, replay.text
    assert replay.json() == replaced.json()


async def test_replacement_deadlock_retry_exhaustion_is_generic_503(
    client: AsyncClient, active_user, logged_in_headers, monkeypatch
):
    """Real 40P01s on every attempt exhaust the retry budget and leave nothing committed."""
    project = await _create_project(active_user)
    project_id = project["id"]
    flow = await _create_flow(active_user, project_id, _flow_payload(name=f"exhaust-{uuid4().hex[:8]}"))
    operation_id = str(uuid4())
    url = f"api/v1/projects/{project_id}/replacement-operations/{operation_id}"
    body = {
        "description": "must never commit",
        "flows": [_flow_payload(flow_id=UUID(flow["id"]), name=flow["name"])],
    }

    async def always_deadlock(self, *args, **kwargs):  # noqa: ARG001 - patched signature must match flush()
        statement, message = "private SQL details", "private database detail"
        raise _deadlock_error(statement, message)

    monkeypatch.setattr(AsyncSession, "flush", always_deadlock)
    monkeypatch.setattr(projects_module.asyncio, "sleep", AsyncMock())

    # Spy on _replace_project_operation_once so the retry budget is checked
    # against the number of whole-operation attempts, not just flush calls.
    original_replace_once = projects_module._replace_project_operation_once
    attempt_calls = 0

    async def counting_replace_once(**kwargs):
        nonlocal attempt_calls
        attempt_calls += 1
        return await original_replace_once(**kwargs)

    monkeypatch.setattr(projects_module, "_replace_project_operation_once", counting_replace_once)

    response = await client.put(url, json=body, headers=logged_in_headers)

    assert response.status_code == 503
    assert response.json()["detail"] == "The database is busy. Please retry the request."
    assert "private" not in response.text
    assert response.headers.get("x-langflow-error-code") == "replacement_retry_exhausted"
    assert attempt_calls == projects_module._REPLACEMENT_MAX_ATTEMPTS, (
        "every attempt in the retry budget must actually run the whole operation"
    )

    async with session_scope() as session:
        stored_flow = await session.get(Flow, UUID(flow["id"]))
        assert stored_flow.name == flow["name"]
        receipts = list(
            (
                await session.exec(
                    select(ProjectReplacementOperation).where(
                        ProjectReplacementOperation.project_id == UUID(project_id),
                        ProjectReplacementOperation.operation_id == UUID(operation_id),
                    )
                )
            ).all()
        )
        assert receipts == []


async def test_wrapped_cascade_deadlock_retries_replacement_from_clean_transaction(
    client: AsyncClient,
    active_user,
    logged_in_headers: dict[str, str],
    monkeypatch,
):
    project = await _create_project(active_user)
    project_id = project["id"]
    stale_flow = await _create_flow(active_user, project_id, _flow_payload(name=f"stale-{uuid4().hex[:8]}"))
    operation_id = str(uuid4())
    url = f"api/v1/projects/{project_id}/replacement-operations/{operation_id}"
    body = {"description": "committed after retry", "flows": []}
    original_cascade_delete_flow = projects_module.cascade_delete_flow
    cascade_calls = 0

    async def raise_wrapped_deadlock_once(*args, **kwargs):
        nonlocal cascade_calls
        cascade_calls += 1
        if cascade_calls == 1:
            database_error = _deadlock_error("DELETE FROM flow", "simulated cascade deadlock")
            wrapper_message = "cascade helper failed"
            raise RuntimeError(wrapper_message) from database_error
        return await original_cascade_delete_flow(*args, **kwargs)

    monkeypatch.setattr(projects_module, "cascade_delete_flow", raise_wrapped_deadlock_once)

    replaced = await client.put(url, json=body, headers=logged_in_headers)
    assert replaced.status_code == 200, replaced.text
    assert cascade_calls == 2
    assert replaced.json()["project"]["description"] == body["description"]
    assert replaced.json()["flows"] == []

    async with session_scope() as session:
        stored_project = await session.get(Folder, UUID(project_id))
        stored_flow = await session.get(Flow, UUID(stale_flow["id"]))
        receipts = list(
            (
                await session.exec(
                    select(ProjectReplacementOperation).where(
                        ProjectReplacementOperation.project_id == UUID(project_id),
                        ProjectReplacementOperation.operation_id == UUID(operation_id),
                    )
                )
            ).all()
        )
        assert stored_project.description == body["description"]
        assert stored_flow is None
        assert len(receipts) == 1
        expected_receipt = replaced.json()
        expected_receipt.pop("dependencies", None)
        assert receipts[0].result == expected_receipt

    replay = await client.put(url, json=body, headers=logged_in_headers)
    receipt = await client.get(url, headers=logged_in_headers)
    assert replay.status_code == 200, replay.text
    assert receipt.status_code == 200, receipt.text
    assert replay.json() == replaced.json()
    assert receipt.json() == replaced.json()


async def test_replacement_operation_replays_and_gets_committed_snapshot(
    client: AsyncClient, active_user, logged_in_headers: dict[str, str]
):
    project = await _create_project(active_user)
    project_id = project["id"]
    operation_id = str(uuid4())
    body = {
        "description": "first replacement",
        "flows": [_flow_payload(flow_id=uuid4(), name=f"flow-{uuid4().hex[:8]}")],
        "dependencies": {
            "knowledgeBases": [{"name": "shared-kb", "backendType": "postgres"}],
            "memoryBases": [],
        },
    }
    url = f"api/v1/projects/{project_id}/replacement-operations/{operation_id}"

    first = await client.put(url, json=body, headers=logged_in_headers)
    replay = await client.put(url, json=body, headers=logged_in_headers)

    assert first.status_code == 200, first.text
    assert replay.status_code == 200, replay.text
    assert first.json() == replay.json()
    assert first.json()["project"]["description"] == "first replacement"
    assert first.json()["project"]["auth_settings"] is None
    assert len(first.json()["flows"]) == 1
    assert first.json()["dependencies"] == body["dependencies"]

    changed_body = {
        **body,
        "dependencies": {
            "knowledgeBases": [{"name": "different-kb", "backendType": "postgres"}],
            "memoryBases": [],
        },
    }
    conflict = await client.put(url, json=changed_body, headers=logged_in_headers)
    assert conflict.status_code == 409

    next_operation = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{uuid4()}",
        json={"description": "later replacement", "flows": []},
        headers=logged_in_headers,
    )
    assert next_operation.status_code == 200, next_operation.text

    receipt = await client.get(url, headers=logged_in_headers)
    assert receipt.status_code == 200, receipt.text
    assert receipt.json() == first.json()

    missing = await client.get(
        f"api/v1/projects/{project_id}/replacement-operations/{uuid4()}",
        headers=logged_in_headers,
    )
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Replacement operation not found"
    assert missing.headers.get("x-langflow-error-code") == "replacement_operation_not_found"


async def test_replacement_receipt_without_dependency_snapshot_remains_readable(
    client: AsyncClient, active_user, logged_in_headers: dict[str, str]
):
    project = await _create_project(active_user)
    project_id = project["id"]
    operation_id = str(uuid4())
    url = f"api/v1/projects/{project_id}/replacement-operations/{operation_id}"
    body = {
        "description": "historical replacement",
        "flows": [_flow_payload(flow_id=uuid4(), name=f"legacy-{uuid4().hex[:8]}")],
    }

    created = await client.put(url, json=body, headers=logged_in_headers)
    assert created.status_code == 200, created.text

    async with session_scope() as session:
        receipt = await session.get(ProjectReplacementOperation, (UUID(project_id), UUID(operation_id)))
        assert receipt is not None
        assert "dependencies" not in receipt.result
        receipt.result = {key: value for key, value in receipt.result.items() if key != "dependencies"}
        session.add(receipt)
        await session.commit()

    replay = await client.put(url, json=body, headers=logged_in_headers)
    recovered = await client.get(url, headers=logged_in_headers)

    assert replay.status_code == 200, replay.text
    assert recovered.status_code == 200, recovered.text
    assert replay.json()["project"] == created.json()["project"]
    assert recovered.json()["project"] == created.json()["project"]
    assert replay.json().get("dependencies") is None
    assert recovered.json().get("dependencies") is None


async def test_restore_creates_project_and_receipt_survives_project_deletion(
    client: AsyncClient, logged_in_headers: dict[str, str], monkeypatch
):
    from langflow.api.v1 import projects as projects_module

    monkeypatch.setattr(
        projects_module,
        "get_settings_service",
        lambda: SimpleNamespace(
            settings=SimpleNamespace(add_projects_to_mcp_servers=False),
            auth_settings=SimpleNamespace(AUTO_LOGIN=True),
        ),
    )
    project_id = str(uuid4())
    operation_id = str(uuid4())
    url = f"api/v1/projects/{project_id}/replacement-operations/{operation_id}"
    body = {"project_name": f"restore-{uuid4().hex[:16]}", "description": "restored", "flows": []}

    created = await client.put(url, json=body, headers=logged_in_headers)
    replay = await client.put(url, json=body, headers=logged_in_headers)

    assert created.status_code == 200, created.text
    assert replay.status_code == 200, replay.text
    assert replay.json() == created.json()
    assert created.json()["project"]["id"] == project_id
    assert created.json()["project"]["name"] == body["project_name"]
    assert created.json()["flows"] == []

    deleted = await client.delete(f"api/v1/projects/{project_id}", headers=logged_in_headers)
    assert deleted.status_code == 204, deleted.text

    receipt = await client.get(url, headers=logged_in_headers)
    assert receipt.status_code == 200, receipt.text
    assert receipt.json() == created.json()


async def test_restore_creates_project_without_mcp_server_when_api_key_issuance_is_denied(
    client: AsyncClient, logged_in_headers: dict[str, str], monkeypatch
):
    """Mirrors _new_project's denial handling.

    AUTO_LOGIN=false always auto-chooses apikey auth here (there is no
    caller-supplied auth_settings on a replacement request), so a denied
    issuance must not fail the create — it drops the MCP server and clears
    auth_settings instead.
    """
    from langflow.api.v1 import projects as projects_module
    from langflow.services.database.models.api_key.policy import (
        ApiKeyIssuanceDeniedError,
        get_api_key_issuance_policy,
        set_api_key_issuance_policy,
    )

    monkeypatch.setattr(
        projects_module,
        "get_settings_service",
        lambda: SimpleNamespace(
            settings=SimpleNamespace(add_projects_to_mcp_servers=True),
            auth_settings=SimpleNamespace(AUTO_LOGIN=False),
        ),
    )
    previous_policy = get_api_key_issuance_policy()
    set_api_key_issuance_policy(AsyncMock(side_effect=ApiKeyIssuanceDeniedError("no sign-in source")))
    try:
        project_id = str(uuid4())
        operation_id = str(uuid4())
        url = f"api/v1/projects/{project_id}/replacement-operations/{operation_id}"
        body = {"project_name": f"restore-{uuid4().hex[:16]}", "description": "restored", "flows": []}

        created = await client.put(url, json=body, headers=logged_in_headers)

        assert created.status_code == 200, created.text
        assert created.json()["project"]["auth_settings"] is None

        async with session_scope() as session:
            stored_project = await session.get(Folder, UUID(project_id))
            assert stored_project is not None
            assert stored_project.auth_settings is None
    finally:
        set_api_key_issuance_policy(previous_policy)


async def test_replacement_receipts_are_owner_only_before_and_after_project_deletion(
    client: AsyncClient,
    active_user,
    logged_in_headers: dict[str, str],
    user_two_api_key: str,
):
    project = await _create_project(active_user)
    project_id = project["id"]
    operation_id = str(uuid4())
    url = f"api/v1/projects/{project_id}/replacement-operations/{operation_id}"
    body = {"description": "owner receipt", "flows": []}
    changed_body = {"description": "different digest", "flows": []}

    created = await client.put(url, json=body, headers=logged_in_headers)
    assert created.status_code == 200, created.text

    # Use an API key tied to the second DB user and remove the owner's login
    # cookie so every cross-user request has an unambiguous principal.
    client.cookies.clear()
    other_headers = {"x-api-key": user_two_api_key}

    async def assert_not_found_for_other_user() -> None:
        read = await client.get(url, headers=other_headers)
        same_digest_replay = await client.put(url, json=body, headers=other_headers)
        different_digest_replay = await client.put(url, json=changed_body, headers=other_headers)
        assert read.status_code == 404
        assert same_digest_replay.status_code == 404
        assert different_digest_replay.status_code == 404

    await assert_not_found_for_other_user()

    owner_receipt = await client.get(url, headers=logged_in_headers)
    assert owner_receipt.status_code == 200, owner_receipt.text
    assert owner_receipt.json() == created.json()

    deleted = await client.delete(f"api/v1/projects/{project_id}", headers=logged_in_headers)
    assert deleted.status_code == 204, deleted.text

    await assert_not_found_for_other_user()

    owner_receipt_after_delete = await client.get(url, headers=logged_in_headers)
    assert owner_receipt_after_delete.status_code == 200, owner_receipt_after_delete.text
    assert owner_receipt_after_delete.json() == created.json()


async def test_replacement_can_explicitly_clear_nullable_flow_fields_and_replay_receipt(
    client: AsyncClient,
    active_user,
    logged_in_headers: dict[str, str],
):
    project = await _create_project(active_user)
    project_id = project["id"]
    flow = await _create_flow(active_user, project_id, _flow_payload(name=f"clear-{uuid4().hex[:8]}"))
    operation_id = str(uuid4())
    url = f"api/v1/projects/{project_id}/replacement-operations/{operation_id}"
    # `data` is excluded here: ReplacementFlowCreate now requires it to be a
    # dict (see test_replacement_rejects_null_flow_data), so this only covers
    # the fields that remain genuinely nullable.
    body = {
        "description": "clear nullable flow fields",
        "flows": [
            {
                "id": flow["id"],
                "name": flow["name"],
                "description": None,
                "data": {"nodes": [], "edges": []},
            }
        ],
    }

    replaced = await client.put(url, json=body, headers=logged_in_headers)
    assert replaced.status_code == 200, replaced.text
    replaced_flow = replaced.json()["flows"][0]
    assert replaced_flow["description"] is None
    assert replaced_flow["data"] == {"nodes": [], "edges": []}

    async with session_scope() as session:
        stored_flow = await session.get(Flow, UUID(flow["id"]))
        assert stored_flow.description is None
        assert stored_flow.data == {"nodes": [], "edges": []}

    replay = await client.put(url, json=body, headers=logged_in_headers)
    receipt = await client.get(url, headers=logged_in_headers)
    assert replay.status_code == 200, replay.text
    assert receipt.status_code == 200, receipt.text
    assert replay.json() == replaced.json()
    assert receipt.json() == replaced.json()


async def test_restore_refuses_a_project_that_already_reappeared(
    client: AsyncClient, active_user, logged_in_headers: dict[str, str]
):
    project_id = uuid4()
    project_name = f"restore-{uuid4().hex[:16]}"
    flow_id = uuid4()
    async with session_scope() as session:
        project = Folder(
            id=project_id,
            name=project_name,
            description="external recreation",
            user_id=active_user.id,
        )
        flow = Flow(
            id=flow_id,
            name="keep-me",
            description="untouched",
            data={"nodes": [{"id": "unchanged"}], "edges": []},
            user_id=active_user.id,
            folder_id=project_id,
        )
        session.add(project)
        session.add(flow)
        await session.flush()

    operation_id = uuid4()
    url = f"api/v1/projects/{project_id}/replacement-operations/{operation_id}"
    body = {
        "project_name": project_name,
        "description": "restore must not replace the recreated project",
        "flows": [],
    }

    refused = await client.put(url, json=body, headers=logged_in_headers)

    assert refused.status_code == 409
    assert refused.json()["detail"] == "Project already exists"
    assert refused.headers.get("x-langflow-error-code") == "replacement_project_already_exists"
    async with session_scope() as session:
        stored_project = await session.get(Folder, project_id)
        stored_flow = await session.get(Flow, flow_id)
        assert stored_project.description == "external recreation"
        assert stored_flow.description == "untouched"
        assert stored_flow.data == {"nodes": [{"id": "unchanged"}], "edges": []}
    assert (await client.get(url, headers=logged_in_headers)).status_code == 404


async def test_invalid_deployment_project_name_is_hidden_without_mutation(
    client: AsyncClient, active_user, logged_in_headers: dict[str, str]
):
    project = await _create_project(active_user, name=f"Ordinary Project {uuid4().hex[:6]}")
    project_id = project["id"]
    existing_flow = await _create_flow(
        active_user,
        project_id,
        _flow_payload(name=f"existing-{uuid4().hex[:8]}", endpoint_name="existing_endpoint"),
    )
    response = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{uuid4()}",
        json={"description": "must not commit", "flows": []},
        headers=logged_in_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"
    assert response.headers.get("x-langflow-error-code") == "replacement_project_not_found"

    unchanged = await client.get(f"api/v1/projects/{project_id}", headers=logged_in_headers)
    assert unchanged.status_code == 200
    project_read = unchanged.json().get("folder", unchanged.json())
    assert project_read["description"] == "original description"
    assert [flow["id"] for flow in unchanged.json().get("flows", [])] == [existing_flow["id"]]


async def test_replacement_preserves_omitted_endpoint(client: AsyncClient, active_user, logged_in_headers):
    project = await _create_project(active_user)
    project_id = project["id"]
    first_flow = await _create_flow(
        active_user,
        project_id,
        _flow_payload(name=f"first-{uuid4().hex[:8]}", endpoint_name="endpoint_one"),
    )

    response = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{uuid4()}",
        json={
            "description": "endpoint omitted",
            "flows": [_flow_payload(flow_id=UUID(first_flow["id"]), name=first_flow["name"])],
        },
        headers=logged_in_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["flows"][0]["endpoint_name"] == "endpoint_one"


async def test_replacement_allows_endpoint_swaps(client: AsyncClient, active_user, logged_in_headers):
    project = await _create_project(active_user)
    project_id = project["id"]
    first_flow = await _create_flow(
        active_user,
        project_id,
        _flow_payload(name=f"first-{uuid4().hex[:8]}", endpoint_name="endpoint_one"),
    )
    second_flow = await _create_flow(
        active_user,
        project_id,
        _flow_payload(name=f"second-{uuid4().hex[:8]}", endpoint_name="endpoint_two"),
    )

    body = {
        "description": "endpoints updated",
        "flows": [
            _flow_payload(flow_id=UUID(first_flow["id"]), name=first_flow["name"], endpoint_name="endpoint_two"),
            _flow_payload(
                flow_id=UUID(second_flow["id"]),
                name=second_flow["name"],
                endpoint_name="endpoint_one",
            ),
        ],
    }
    response = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{uuid4()}",
        json=body,
        headers=logged_in_headers,
    )

    assert response.status_code == 200, response.text
    by_id = {flow["id"]: flow for flow in response.json()["flows"]}
    assert by_id[first_flow["id"]]["endpoint_name"] == "endpoint_two"
    assert by_id[second_flow["id"]]["endpoint_name"] == "endpoint_one"


async def test_replacement_of_a_locked_flow_with_identical_content_succeeds(
    client: AsyncClient, active_user, logged_in_headers
):
    """A locked flow's temporary rename must not make the lock guard see a name change.

    The replacement handler frees a project-local name by renaming the row to a
    ``__lf_replace_...`` placeholder before saving. Without comparing against the
    pre-rename name/endpoint_name, that interim value would always look like a
    change to the locked-flow guard, even for a request that changes nothing.
    """
    project = await _create_project(active_user)
    project_id = project["id"]
    flow = await _create_flow(
        active_user,
        project_id,
        {**_flow_payload(name=f"locked-{uuid4().hex[:8]}", endpoint_name="locked_endpoint"), "locked": True},
    )

    identical_body = {
        "description": project["description"],
        "flows": [
            {
                "id": flow["id"],
                "name": flow["name"],
                "description": flow["description"],
                "data": flow["data"],
                "endpoint_name": flow["endpoint_name"],
                "locked": True,
            }
        ],
    }
    identical_response = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{uuid4()}",
        json=identical_body,
        headers=logged_in_headers,
    )
    assert identical_response.status_code == 200, identical_response.text
    assert identical_response.json()["flows"][0]["name"] == flow["name"]
    assert identical_response.json()["flows"][0]["locked"] is True

    unlock_body = {
        "description": project["description"],
        "flows": [
            {
                "id": flow["id"],
                "name": flow["name"],
                "description": flow["description"],
                "data": flow["data"],
                "endpoint_name": flow["endpoint_name"],
                "locked": False,
            }
        ],
    }
    unlock_response = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{uuid4()}",
        json=unlock_body,
        headers=logged_in_headers,
    )
    assert unlock_response.status_code == 200, unlock_response.text
    assert unlock_response.json()["flows"][0]["locked"] is False

    async with session_scope() as session:
        stored_flow = await session.get(Flow, UUID(flow["id"]))
        assert stored_flow.name == flow["name"]
        assert stored_flow.endpoint_name == flow["endpoint_name"]
        assert stored_flow.locked is False


async def test_replacement_content_change_to_a_locked_flow_is_still_rejected(
    client: AsyncClient, active_user, logged_in_headers
):
    project = await _create_project(active_user)
    project_id = project["id"]
    flow = await _create_flow(
        active_user,
        project_id,
        {**_flow_payload(name=f"locked-{uuid4().hex[:8]}", endpoint_name="locked_endpoint"), "locked": True},
    )

    changed_body = {
        "description": project["description"],
        "flows": [
            {
                "id": flow["id"],
                "name": flow["name"],
                "description": "an actual content change",
                "data": flow["data"],
                "endpoint_name": flow["endpoint_name"],
                "locked": True,
            }
        ],
    }
    response = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{uuid4()}",
        json=changed_body,
        headers=logged_in_headers,
    )

    assert response.status_code == 423, response.text
    assert response.json()["detail"] == "Flow is locked. Unlock it before making changes."
    async with session_scope() as session:
        stored_flow = await session.get(Flow, UUID(flow["id"]))
        assert stored_flow.description == flow["description"]
        assert stored_flow.locked is True


async def test_replacement_commits_despite_trigger_reconciliation_failure(
    client: AsyncClient, active_user, logged_in_headers, monkeypatch
):
    """Trigger reconciliation (reconcile_flow_triggers_safely) is best-effort.

    One flow's reconcile failure must not roll back the rest of the
    replacement — it is logged and swallowed, same as every other
    flow-save path.
    """
    from langflow.services.triggers import reconciliation as triggers_reconciliation_module

    project = await _create_project(active_user)
    project_id = project["id"]
    live_flows = [
        await _create_flow(
            active_user,
            project_id,
            {
                **_flow_payload(name=f"live-{index}-{uuid4().hex[:8]}", endpoint_name=f"live_endpoint_{index}"),
                "data": {"nodes": [], "edges": [], "marker": f"original-{index}"},
            },
        )
        for index in range(2)
    ]
    request_flows = [
        {
            **_flow_payload(
                flow_id=UUID(live_flow["id"]),
                name=f"requested-{index}-{uuid4().hex[:8]}",
                endpoint_name=f"requested_endpoint_{index}",
            ),
            "data": {"nodes": [], "edges": [], "marker": f"target-{index}"},
        }
        for index, live_flow in enumerate(live_flows)
    ]

    calls = 0
    original_reconcile = triggers_reconciliation_module.reconcile_flow_triggers

    async def fail_on_second_reconcile(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            failure_message = "injected trigger reconciliation failure"
            raise RuntimeError(failure_message)
        return await original_reconcile(*args, **kwargs)

    monkeypatch.setattr(triggers_reconciliation_module, "reconcile_flow_triggers", fail_on_second_reconcile)
    operation_id = str(uuid4())
    response = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{operation_id}",
        json={"description": "editor target", "flows": request_flows},
        headers=logged_in_headers,
    )

    assert response.status_code == 200, response.text
    assert calls == 2
    assert response.json()["project"]["description"] == "editor target"

    async with session_scope() as session:
        stored_project = await session.get(Folder, UUID(project_id))
        stored_flows = list((await session.exec(select(Flow).where(Flow.folder_id == UUID(project_id)))).all())
        assert stored_project.description == "editor target"
        assert {flow.id for flow in stored_flows} == {UUID(f["id"]) for f in live_flows}
        by_id = {str(flow.id): flow for flow in stored_flows}
        for request_flow in request_flows:
            stored_flow = by_id[request_flow["id"]]
            assert stored_flow.name == request_flow["name"]
            assert stored_flow.endpoint_name == request_flow["endpoint_name"]
            assert stored_flow.data == request_flow["data"]

    receipt = await client.get(
        f"api/v1/projects/{project_id}/replacement-operations/{operation_id}", headers=logged_in_headers
    )
    assert receipt.status_code == 200, receipt.text
    assert receipt.json() == response.json()


async def test_replacement_retries_on_deadlock_from_trigger_reconciliation(
    client: AsyncClient, active_user, logged_in_headers, monkeypatch
):
    """A DBAPIError from trigger reconciliation must trigger the whole-transaction retry.

    Unlike a non-database reconciliation failure (best-effort, swallowed —
    see test_replacement_commits_despite_trigger_reconciliation_failure), a real
    lock/deadlock error there must propagate so the replacement is retried from
    a clean body instead of committing with stale trigger rows.
    """
    from langflow.services.triggers import reconciliation as triggers_reconciliation_module

    project = await _create_project(active_user)
    project_id = project["id"]
    flow = await _create_flow(active_user, project_id, _flow_payload(name=f"trigger-deadlock-{uuid4().hex[:8]}"))
    operation_id = str(uuid4())
    url = f"api/v1/projects/{project_id}/replacement-operations/{operation_id}"
    body = {
        "description": "retried after trigger reconciliation deadlock",
        "flows": [
            {
                **_flow_payload(flow_id=UUID(flow["id"]), name=f"retried-{uuid4().hex[:8]}"),
                "data": {"nodes": [], "edges": [], "marker": "target-after-retry"},
            }
        ],
    }

    calls = 0
    original_reconcile = triggers_reconciliation_module.reconcile_flow_triggers

    async def deadlock_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            statement, message = "UPDATE trigger", "simulated trigger reconciliation deadlock"
            raise _deadlock_error(statement, message)
        return await original_reconcile(*args, **kwargs)

    monkeypatch.setattr(triggers_reconciliation_module, "reconcile_flow_triggers", deadlock_once)

    replaced = await client.put(url, json=body, headers=logged_in_headers)

    assert replaced.status_code == 200, replaced.text
    assert calls >= 2, "the first reconcile must have raised and the whole replacement retried"
    assert replaced.json()["flows"][0]["name"] == body["flows"][0]["name"]
    assert replaced.json()["flows"][0]["data"] == body["flows"][0]["data"]

    async with session_scope() as session:
        stored_flow = await session.get(Flow, UUID(flow["id"]))
        assert stored_flow.name == body["flows"][0]["name"]
        assert stored_flow.data == body["flows"][0]["data"]


async def test_replacement_rejects_filesystem_flows_without_mutation(
    client: AsyncClient, active_user, logged_in_headers
):
    project = await _create_project(active_user)
    project_id = project["id"]
    flow = await _create_flow(
        active_user,
        project_id,
        {**_flow_payload(name=f"fs-{uuid4().hex[:8]}"), "fs_path": "flow-files/legacy.json"},
    )

    response = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{uuid4()}",
        json={"description": "must not commit", "flows": []},
        headers=logged_in_headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Atomic replacement does not support filesystem-backed flows"
    assert response.headers.get("x-langflow-error-code") == "replacement_filesystem_flows_unsupported"
    async with session_scope() as session:
        stored_project = await session.get(Folder, UUID(project_id))
        stored_flow = await session.get(Flow, UUID(flow["id"]))
        assert stored_project.description == "original description"
        assert stored_flow.fs_path == "flow-files/legacy.json"


async def test_replacement_receipts_are_pruned_to_the_newest_ten(client: AsyncClient, active_user, logged_in_headers):
    """Receipts beyond the newest _MAX_REPLACEMENT_RECEIPTS_PER_PROJECT are tombstoned, not deleted."""
    project = await _create_project(active_user)
    project_id = project["id"]
    max_receipts = projects_module._MAX_REPLACEMENT_RECEIPTS_PER_PROJECT
    operation_ids = [str(uuid4()) for _ in range(max_receipts + 3)]
    bodies = [{"description": f"replacement {index}", "flows": []} for index in range(len(operation_ids))]
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)

    for index, (operation_id, body) in enumerate(zip(operation_ids, bodies, strict=True)):
        response = await client.put(
            f"api/v1/projects/{project_id}/replacement-operations/{operation_id}",
            json=body,
            headers=logged_in_headers,
        )
        assert response.status_code == 200, response.text
        # Force a strictly increasing created_at per receipt. Two requests can
        # otherwise land in the same clock tick, and the pruning query's
        # (created_at desc, operation_id desc) tie-break then orders same-tick
        # receipts by random UUID rather than request order, making which
        # receipts survive nondeterministic - a pre-existing property of the
        # ranking, not something this test is about.
        async with session_scope() as session:
            receipt = await session.get(ProjectReplacementOperation, (UUID(project_id), UUID(operation_id)))
            receipt.created_at = base_time + timedelta(milliseconds=index)
            session.add(receipt)
            await session.commit()

    tombstoned_ids = operation_ids[: len(operation_ids) - max_receipts]
    surviving_ids = operation_ids[len(operation_ids) - max_receipts :]

    async with session_scope() as session:
        receipts = list(
            (
                await session.exec(
                    select(ProjectReplacementOperation).where(
                        ProjectReplacementOperation.project_id == UUID(project_id)
                    )
                )
            ).all()
        )
        # Every row survives pruning - the row, digest, and owner/workspace are
        # kept; only its result is cleared. See ProjectReplacementOperation.result.
        assert len(receipts) == len(operation_ids)
        by_id = {str(receipt.operation_id): receipt for receipt in receipts}
        assert {op_id for op_id, receipt in by_id.items() if receipt.result is None} == set(tombstoned_ids)
        assert {op_id for op_id, receipt in by_id.items() if receipt.result is not None} == set(surviving_ids)

    # Every tombstoned receipt - including the one right at the retention
    # boundary, the first one pruned - reads as 410, not 404 (the row still
    # exists) and not 200 (its content is gone).
    for operation_id in tombstoned_ids:
        pruned = await client.get(
            f"api/v1/projects/{project_id}/replacement-operations/{operation_id}", headers=logged_in_headers
        )
        assert pruned.status_code == 410, pruned.text
        assert pruned.headers["X-Langflow-Error-Code"] == "replacement_receipt_expired"

    # A surviving receipt is still individually readable.
    kept = await client.get(
        f"api/v1/projects/{project_id}/replacement-operations/{surviving_ids[-1]}", headers=logged_in_headers
    )
    assert kept.status_code == 200, kept.text

    # A PUT retry of a tombstoned operation_id - even with its own original
    # body, so the request digest still matches - must 410, not silently
    # replay and overwrite the project with stale content.
    boundary_operation_id = tombstoned_ids[0]
    boundary_body = bodies[operation_ids.index(boundary_operation_id)]
    retry = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{boundary_operation_id}",
        json=boundary_body,
        headers=logged_in_headers,
    )
    assert retry.status_code == 410, retry.text
    assert retry.headers["X-Langflow-Error-Code"] == "replacement_receipt_expired"

    async with session_scope() as session:
        stored_project = await session.get(Folder, UUID(project_id))
        assert stored_project.description == bodies[-1]["description"]


async def test_project_authorization_denial_leaves_replacement_content_unchanged(
    client: AsyncClient, active_user, logged_in_headers, monkeypatch
):
    from langflow.api.v1 import projects as projects_module

    project = await _create_project(active_user)
    project_id = project["id"]
    flow = await _create_flow(active_user, project_id, _flow_payload(name=f"auth-{uuid4().hex[:8]}"))
    monkeypatch.setattr(
        projects_module,
        "ensure_project_permission",
        AsyncMock(side_effect=HTTPException(status_code=403, detail="denied")),
    )
    operation_id = str(uuid4())

    response = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{operation_id}",
        json={"description": "must not commit", "flows": []},
        headers=logged_in_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"
    async with session_scope() as session:
        stored_project = await session.get(Folder, UUID(project_id))
        stored_flow = await session.get(Flow, UUID(flow["id"]))
        assert stored_project.description == "original description"
        assert stored_flow is not None
    receipt = await client.get(
        f"api/v1/projects/{project_id}/replacement-operations/{operation_id}", headers=logged_in_headers
    )
    assert receipt.status_code == 404


@pytest.mark.parametrize("scenario", ["delete", "write", "create"])
async def test_flow_level_authorization_denial_maps_to_404_and_leaves_content_unchanged(
    client: AsyncClient, active_user, logged_in_headers, monkeypatch, scenario
):
    """A per-flow (not project-level) denial must also 404 and commit nothing.

    Covers all three flow-level checks _replace_project_operation_once makes:
    DELETE (a stale flow dropped from the request), WRITE (an existing flow
    kept but changed), and CREATE (a flow id not already in the project) -
    the same denied-to-404 mapping test_project_authorization_denial_leaves_replacement_content_unchanged
    covers for the project-level check.
    """
    project = await _create_project(active_user)
    project_id = project["id"]

    if scenario in ("delete", "write"):
        flow = await _create_flow(active_user, project_id, _flow_payload(name=f"{scenario}-{uuid4().hex[:8]}"))
    else:
        flow = None

    if scenario == "delete":
        # No requested flows: the project's one existing flow becomes stale.
        body = {"description": "must not commit", "flows": []}
        patched_name = "ensure_flows_permission"
    elif scenario == "write":
        # Same flow id, changed content: goes through the WRITE batch, not CREATE.
        body = {
            "description": "must not commit",
            "flows": [{**_flow_payload(flow_id=UUID(flow["id"]), name=flow["name"]), "description": "changed"}],
        }
        patched_name = "ensure_flows_permission"
    else:
        # An id with no existing row: goes through the single-flow CREATE check.
        body = {
            "description": "must not commit",
            "flows": [_flow_payload(flow_id=uuid4(), name=f"new-{uuid4().hex[:8]}")],
        }
        patched_name = "ensure_flow_permission"

    denial = AsyncMock(side_effect=HTTPException(status_code=403, detail="denied"))
    monkeypatch.setattr(projects_module, patched_name, denial)

    response = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{uuid4()}", json=body, headers=logged_in_headers
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Project not found"
    assert response.headers.get("x-langflow-error-code") == "replacement_project_not_found"
    denial.assert_awaited()

    async with session_scope() as session:
        stored_project = await session.get(Folder, UUID(project_id))
        stored_flows = list((await session.exec(select(Flow).where(Flow.folder_id == UUID(project_id)))).all())
        assert stored_project.description == "original description"
        if scenario == "create":
            assert stored_flows == []
        else:
            assert len(stored_flows) == 1
            assert stored_flows[0].id == UUID(flow["id"])
            assert stored_flows[0].description != "changed"


async def test_replacement_returns_200_despite_post_commit_memory_base_cleanup_failure(
    client: AsyncClient, active_user, logged_in_headers, monkeypatch
):
    """A post-commit Memory Base cleanup failure is best-effort and must not fail the response.

    The replacement is already durable once the transaction commits (see the
    comment above the post-commit block in replace_project_operation) - only
    the external cleanup/cache calls that follow are allowed to fail silently.
    """
    from langflow.services.memory_base import flow_cleanup as flow_cleanup_module
    from langflow.services.memory_base.flow_cleanup import FlowMemoryBaseCleanup

    project = await _create_project(active_user)
    project_id = project["id"]
    stale_flow = await _create_flow(active_user, project_id, _flow_payload(name=f"mb-cleanup-{uuid4().hex[:8]}"))

    async def _fake_cascade_delete_flow(session, target_flow_id, *, memory_base_cleanups):
        # Actually removes the row (mirroring the real cascade) while also
        # recording the Memory Base handle whose finalize is about to fail -
        # without needing a real Memory Base row or KB backend.
        memory_base_cleanups.append(
            FlowMemoryBaseCleanup(
                kb_name="does-not-matter",
                user_id=active_user.id,
                kb_username="activeuser",
                backend_type="chroma",
                backend_config={},
            )
        )
        flow_row = await session.get(Flow, target_flow_id)
        if flow_row is not None:
            await session.delete(flow_row)
        return True

    monkeypatch.setattr(projects_module, "cascade_delete_flow", _fake_cascade_delete_flow)

    async def _raise(*_args, **_kwargs):
        failure_message = "injected memory base cleanup failure"
        raise RuntimeError(failure_message)

    monkeypatch.setattr(flow_cleanup_module, "finalize_flow_memory_base_cleanup", _raise)

    operation_id = str(uuid4())
    response = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{operation_id}",
        json={"description": "post-commit cleanup must not fail this", "flows": []},
        headers=logged_in_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["flows"] == []

    async with session_scope() as session:
        # The commit itself succeeded despite the cleanup failure: the stale
        # flow is gone even though its Memory Base's remote cleanup errored.
        stored_flow = await session.get(Flow, UUID(stale_flow["id"]))
        assert stored_flow is None

    receipt = await client.get(
        f"api/v1/projects/{project_id}/replacement-operations/{operation_id}", headers=logged_in_headers
    )
    assert receipt.status_code == 200, receipt.text
    assert receipt.json() == response.json()


async def test_replacement_by_non_owner_with_literal_mcp_secret_is_rejected(
    client: AsyncClient, active_user, monkeypatch
):
    """A non-owner replacement carrying a literal MCP secret must 409, not stage it.

    MCP credentials are staged as the *project owner's* global variables
    (``stage_mcp_secrets`` in ``_replace_project_operation_once``), so a
    non-owner who can reach an owner's project - only possible via a
    registered cross-user-fetch authorization plugin - must not be able to
    plant a credential there. This exercises that plugin-widened path with an
    allow-everything authorization stub, matching the pattern in
    test_variable.py's ``patch_variable_authz`` and
    test_authz_share_routes.py's ``_StubAuthz``.
    """
    from langflow.services.auth.utils import get_password_hash
    from langflow.services.authorization import guards as authz_guards
    from langflow.services.database.models.user.model import User
    from langflow.services.database.models.variable.model import Variable

    project = await _create_project(active_user)
    project_id = project["id"]

    async with session_scope() as session:
        variables_before = sorted(
            (await session.exec(select(Variable.name).where(Variable.user_id == active_user.id))).all()
        )

    other_username = f"mcp-hijacker-{uuid4().hex[:8]}"
    other_password = "testpassword"  # noqa: S105  # pragma: allowlist secret
    async with session_scope() as session:
        session.add(
            User(
                username=other_username,
                password=get_password_hash(other_password),
                is_active=True,
                is_superuser=False,
            )
        )
        await session.commit()
    login = await client.post("api/v1/login", data={"username": other_username, "password": other_password})
    assert login.status_code == 200, login.text
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    class _AllowAllAuthz:
        async def supports_cross_user_fetch(self) -> bool:
            return True

        async def is_enabled(self) -> bool:
            return True

        async def enforce(self, **_kwargs) -> bool:
            return True

        async def batch_enforce(self, **kwargs) -> list[bool]:
            return [True] * len(kwargs.get("requests", []))

    stub = _AllowAllAuthz()
    monkeypatch.setattr(projects_module, "get_authorization_service", lambda: stub)
    monkeypatch.setattr(authz_guards, "get_authorization_service", lambda: stub)
    monkeypatch.setattr(
        authz_guards,
        "get_settings_service",
        lambda: SimpleNamespace(auth_settings=SimpleNamespace(AUTHZ_ENABLED=True, AUTHZ_AUDIT_ENABLED=False)),
    )

    flow_id = str(uuid4())
    operation_id = str(uuid4())
    flow_payload = {
        "id": flow_id,
        "name": f"mcp-hijack-{uuid4().hex[:8]}",
        "description": "attempted hijack",
        "data": {
            "nodes": [
                {
                    "id": "node-1",
                    "data": {
                        "node": {
                            "template": {
                                "mcp_server": {
                                    "name": "mcp_server",
                                    "type": "mcp",
                                    "value": {
                                        "name": "attacker-mcp",
                                        "config": {
                                            "url": "https://mcp.example.com",
                                            # pragma: allowlist secret
                                            "headers": {"Authorization": "Bearer sk-live-hijack-secret"},
                                        },
                                    },
                                }
                            }
                        }
                    },
                }
            ],
            "edges": [],
        },
    }

    response = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{operation_id}",
        json={"description": project["description"], "flows": [flow_payload]},
        headers=other_headers,
    )

    assert response.status_code == 409, response.text
    assert response.headers["X-Langflow-Error-Code"] == "replacement_mcp_secret_requires_owner"

    async with session_scope() as session:
        variables_after = sorted(
            (await session.exec(select(Variable.name).where(Variable.user_id == active_user.id))).all()
        )
        assert variables_after == variables_before
        assert not any(name.startswith("MCP_") for name in variables_after)
        stored_flow = await session.get(Flow, UUID(flow_id))
        assert stored_flow is None
