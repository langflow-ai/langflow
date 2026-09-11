"""The cases the happy path never reaches.

Two of these exist because the first pass shipped a defect: the reader fetched a
flow by id alone, so anyone holding a UUID could read someone else's history,
and the anonymize switch was a documented setting that did nothing.
"""

import uuid
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.services.deps import get_settings_service, session_scope

SECRET = "sk-edge-case-secret"  # noqa: S105  # pragma: allowlist secret


@pytest.fixture
def audit_on():
    settings = get_settings_service().settings
    original = settings.audit_enabled
    settings.audit_enabled = True
    yield
    settings.audit_enabled = original


@pytest.fixture
def anonymized():
    settings = get_settings_service().settings
    before = settings.audit_enabled, settings.audit_anonymize_payload
    settings.audit_enabled, settings.audit_anonymize_payload = True, True
    yield
    settings.audit_enabled, settings.audit_anonymize_payload = before


def _graph(label: str, secret: str = "") -> dict:
    return {
        "nodes": [
            {
                "id": "agent-1",
                "position": {"x": 0, "y": 0},
                "data": {
                    "node": {
                        "display_name": "Agent",
                        "template": {
                            "_type": "Component",
                            "model_name": {"value": label},
                            "api_key": {"value": secret, "password": True},
                        },
                    }
                },
            }
        ],
        "edges": [],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }


async def _create_flow(client: AsyncClient, headers) -> dict:
    response = await client.post(
        "api/v1/flows/",
        json={"name": f"edge-{uuid.uuid4()}", "data": _graph("v0")},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


async def _second_user_headers(client: AsyncClient, username: str) -> dict[str, str]:
    from langflow.services.auth.utils import get_password_hash
    from langflow.services.database.models.user.model import User

    login_data = {"username": username, "password": "testpassword"}  # pragma: allowlist secret
    async with session_scope() as session:
        session.add(
            User(
                id=uuid4(),
                username=username,
                password=get_password_hash(login_data["password"]),
                is_active=True,
                is_superuser=False,
            )
        )
        await session.commit()
    login = await client.post("api/v1/login", data=login_data)
    assert login.status_code == status.HTTP_200_OK
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def test_a_stranger_cannot_read_someone_elses_history(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    """The reader must be owner-scoped: the OSS pass-through allows every permission check."""
    flow = await _create_flow(client, logged_in_headers)
    stranger = await _second_user_headers(client, f"stranger-{uuid.uuid4().hex[:8]}")

    response = await client.get(f"api/v1/audit/flow/{flow['id']}", headers=stranger)

    assert response.status_code == status.HTTP_404_NOT_FOUND, "a stranger must not read another user's trail"


async def test_the_owner_still_reads_their_own_history(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    flow = await _create_flow(client, logged_in_headers)

    response = await client.get(f"api/v1/audit/flow/{flow['id']}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["total"] >= 1


async def test_a_flow_that_does_not_exist_is_not_distinguishable(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    """A 404 either way, so the endpoint cannot be used to probe which UUIDs exist."""
    response = await client.get(f"api/v1/audit/flow/{uuid4()}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_anonymizing_keeps_who_what_and_when_but_drops_the_payload(
    client: AsyncClient,
    logged_in_headers,
    anonymized,  # noqa: ARG001
):
    flow = await _create_flow(client, logged_in_headers)
    await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"data": _graph("gpt-5")},
        headers=logged_in_headers,
    )

    entries = (await client.get(f"api/v1/audit/flow/{flow['id']}", headers=logged_in_headers)).json()["entries"]
    updated = [e for e in entries if e["event"] == "langflow.audit.flow.updated"]

    assert len(updated) == 1, "the row is still written"
    assert updated[0]["payload"] is None, "but it carries nothing"
    assert updated[0]["user_id"] and updated[0]["created_at"], "who and when survive"


async def test_a_plain_api_client_that_sends_no_precondition_is_still_recorded(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    """Writes that arrive through any path must still be audited."""
    flow = await _create_flow(client, logged_in_headers)

    for i in range(5):
        response = await client.patch(
            f"api/v1/flows/{flow['id']}",
            json={"data": _graph(f"no-precondition-{i}")},
            headers=logged_in_headers,
        )
        assert response.status_code == status.HTTP_200_OK, response.text

    entries = (await client.get(f"api/v1/audit/flow/{flow['id']}", headers=logged_in_headers)).json()["entries"]
    updated = [e for e in entries if e["event"] == "langflow.audit.flow.updated"]
    denied = [e for e in entries if e["event"] == "langflow.audit.flow.save.denied"]

    assert len(updated) == 5, "every unconditional write is recorded"
    assert denied == [], "an unconditional write is never refused, so nothing is denied"


async def test_a_deleted_flow_keeps_its_history(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    """resource_id has no foreign key precisely so the trail outlives the resource."""
    from langflow.services.database.models.audit_log.model import AuditLog
    from sqlmodel import col, select

    flow = await _create_flow(client, logged_in_headers)
    response = await client.delete(f"api/v1/flows/{flow['id']}", headers=logged_in_headers)
    assert response.status_code in (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT), response.text

    async with session_scope() as session:
        rows = (await session.exec(select(AuditLog).where(col(AuditLog.resource_id) == uuid.UUID(flow["id"])))).all()

    events = {row.event for row in rows}
    assert "langflow.audit.flow.created" in events, "the trail survives the flow"
    assert "langflow.audit.flow.deleted" in events, "and records the deletion"


async def test_a_large_flow_does_not_produce_a_large_row(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    """The row is bounded by what was touched, not by how big the flow is."""
    big = {
        "nodes": [
            {
                "id": f"n{i}",
                "position": {"x": i, "y": 0},
                "data": {"node": {"display_name": f"C{i}", "template": {"value": {"value": "x" * 500}}}},
            }
            for i in range(200)
        ],
        "edges": [],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }
    flow = await _create_flow(client, logged_in_headers)
    response = await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"data": big},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    entries = (await client.get(f"api/v1/audit/flow/{flow['id']}", headers=logged_in_headers)).json()["entries"]
    updated = next(e for e in entries if e["event"] == "langflow.audit.flow.updated")

    assert len(updated["payload"]["changes"]) == 50, "the list is capped"
    assert updated["payload"]["changes_total"] == 201, "but the true total is reported"
    assert len(str(updated["payload"])) < 2000, "the row stays small next to a 200-component flow"


async def test_the_page_is_capped_but_the_total_is_not(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    """A busy flow outgrows one page, and a reader counting the page would undercount."""
    flow = await _create_flow(client, logged_in_headers)
    writes = 12

    for i in range(writes):
        response = await client.patch(
            f"api/v1/flows/{flow['id']}",
            json={"data": _graph(f"page-{i}")},
            headers=logged_in_headers,
        )
        assert response.status_code == status.HTTP_200_OK, response.text

    page = (await client.get(f"api/v1/audit/flow/{flow['id']}?limit=5", headers=logged_in_headers)).json()

    assert len(page["entries"]) == 5, "the page honours the limit"
    assert page["total"] == writes + 1, "the total counts every row, including the creation"

    second = (await client.get(f"api/v1/audit/flow/{flow['id']}?limit=5&offset=5", headers=logged_in_headers)).json()
    assert {e["id"] for e in page["entries"]} & {e["id"] for e in second["entries"]} == set(), "pages do not overlap"


async def test_the_page_size_cannot_be_raised_without_limit(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    flow = await _create_flow(client, logged_in_headers)

    response = await client.get(f"api/v1/audit/flow/{flow['id']}?limit=5000", headers=logged_in_headers)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
