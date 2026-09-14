"""Flow edges: duplication, bulk deletion, failure, and the trail's boundaries.

The happy path is covered elsewhere. What is proved here is that the rarer
paths — the ones that copy, that delete many at once, that fail — leave a trail
that says what actually happened.
"""

import asyncio
import uuid

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.services.deps import get_settings_service

SECRET = "sk-never-write-me-down"  # noqa: S105  # pragma: allowlist secret


@pytest.fixture
def audit_on():
    settings = get_settings_service().settings
    original = settings.audit_enabled
    settings.audit_enabled = True
    yield
    settings.audit_enabled = original


def _graph(label: str, *, secret: str = "") -> dict:
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
    }


async def _create(client: AsyncClient, headers, **extra) -> dict:
    body = {"name": f"edge-{uuid.uuid4()}", "data": _graph("gpt-4"), **extra}
    response = await client.post("api/v1/flows/", json=body, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


async def _api_key(client: AsyncClient, headers) -> str:
    """The run endpoint authenticates with an API key, which is how callers reach it."""
    response = await client.post(
        "api/v1/api_key/",
        json={"name": f"run-{uuid.uuid4().hex[:8]}"},
        headers=headers,
    )
    assert response.status_code in {status.HTTP_200_OK, status.HTTP_201_CREATED}, response.text
    return response.json()["api_key"]


async def _trail(client: AsyncClient, headers, flow_id: str) -> list[dict]:
    response = await client.get(f"api/v1/audit/flow/{flow_id}", headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["entries"]


async def test_a_duplicated_flow_is_recorded_against_the_copy_not_the_original(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    """A copy is a new flow, recorded against the copy.

    Attributing it to the original would make the original's history describe an
    act that never touched it.
    """
    original = await _create(client, logged_in_headers)

    copy = await client.post(
        "api/v1/flows/",
        json={"name": f"copy-{uuid.uuid4()}", "data": original["data"]},
        headers=logged_in_headers,
    )
    assert copy.status_code == status.HTTP_201_CREATED, copy.text

    copy_rows = await _trail(client, logged_in_headers, copy.json()["id"])
    original_rows = await _trail(client, logged_in_headers, original["id"])

    assert [e["event"] for e in copy_rows] == ["langflow.audit.flow.create"]
    assert [e["event"] for e in original_rows] == ["langflow.audit.flow.create"]
    assert copy_rows[0]["resource_id"] == copy.json()["id"]


async def test_deleting_many_flows_at_once_records_each_one(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    """A bulk delete is still N deletions to whoever lost them."""
    flows = [await _create(client, logged_in_headers) for _ in range(3)]

    response = await client.request(
        "DELETE",
        "api/v1/flows/",
        json=[flow["id"] for flow in flows],
        headers=logged_in_headers,
    )
    assert response.status_code in {status.HTTP_200_OK, status.HTTP_204_NO_CONTENT}, response.text

    for flow in flows:
        entries = await _trail(client, logged_in_headers, flow["id"])
        deleted = [e for e in entries if e["event"] == "langflow.audit.flow.delete"]
        assert len(deleted) == 1, f"{flow['name']} recorded {len(deleted)} deletions"
        assert deleted[0]["result"] == "succeeded"


async def test_a_rename_is_not_recorded_as_a_graph_change(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    """Nothing about the graph changed, so there is nothing to describe."""
    flow = await _create(client, logged_in_headers)

    response = await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"name": f"renamed-{uuid.uuid4()}"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    entries = await _trail(client, logged_in_headers, flow["id"])
    assert [e for e in entries if e["event"] == "langflow.audit.flow.update"] == []


async def test_concurrent_edits_to_one_flow_each_leave_a_row(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    """Every accepted write is one row — no more, and none lost to the race."""
    flow = await _create(client, logged_in_headers)

    async def edit(label: str):
        return await client.patch(
            f"api/v1/flows/{flow['id']}",
            json={"data": _graph(label)},
            headers=logged_in_headers,
        )

    responses = await asyncio.gather(*(edit(f"model-{i}") for i in range(6)), return_exceptions=True)
    accepted = [r for r in responses if not isinstance(r, Exception) and r.status_code == status.HTTP_200_OK]

    entries = await _trail(client, logged_in_headers, flow["id"])
    updates = [e for e in entries if e["event"] == "langflow.audit.flow.update"]

    assert len(updates) == len(accepted), f"{len(accepted)} writes left {len(updates)} rows"
    assert all(row["result"] == "succeeded" for row in updates)


async def test_a_secret_never_reaches_the_trail_on_any_path(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    flow = await _create(client, logged_in_headers, data=_graph("gpt-4", secret=SECRET))

    await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"data": _graph("gpt-5", secret=f"{SECRET}-rotated")},
        headers=logged_in_headers,
    )

    body = str(await _trail(client, logged_in_headers, flow["id"]))
    assert SECRET not in body
    assert "nodes" not in body


async def test_one_persons_trail_is_not_another_persons(
    client: AsyncClient,
    logged_in_headers_super_user,
    audit_on,  # noqa: ARG001
):
    """A stranger holding the UUID gets the same answer as for one that never existed."""
    admin_headers = logged_in_headers_super_user
    flow = await _create(client, admin_headers)

    stranger = f"stranger-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        "api/v1/users/",
        json={"username": stranger, "password": "strangerpassword"},
        headers=admin_headers,
    )
    if created.status_code != status.HTTP_201_CREATED:
        pytest.skip(f"cannot create a second user here: {created.status_code}")

    # New users land inactive, and an inactive one cannot log in to be refused.
    activated = await client.patch(
        f"api/v1/users/{created.json()['id']}",
        json={"is_active": True},
        headers=admin_headers,
    )
    if activated.status_code != status.HTTP_200_OK:
        pytest.skip(f"cannot activate the second user here: {activated.status_code}")

    token = await client.post(
        "api/v1/login",
        data={"username": stranger, "password": "strangerpassword"},
    )
    assert token.status_code == status.HTTP_200_OK, token.text
    other = {"Authorization": f"Bearer {token.json()['access_token']}"}

    response = await client.get(f"api/v1/audit/flow/{flow['id']}", headers=other)
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text


async def test_restoring_a_version_names_the_version_it_came_from(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    flow = await _create(client, logged_in_headers)

    snapshot = await client.post(
        f"api/v1/flows/{flow['id']}/versions/",
        json={"description": "before the edit"},
        headers=logged_in_headers,
    )
    assert snapshot.status_code == status.HTTP_201_CREATED, snapshot.text
    version_id = snapshot.json()["id"]

    await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"data": _graph("gpt-5")},
        headers=logged_in_headers,
    )

    restored = await client.post(
        f"api/v1/flows/{flow['id']}/versions/{version_id}/activate",
        headers=logged_in_headers,
    )
    assert restored.status_code in {status.HTTP_200_OK, status.HTTP_201_CREATED}, restored.text

    entries = await _trail(client, logged_in_headers, flow["id"])
    rows = [e for e in entries if e["event"] == "langflow.audit.flow.restore"]
    assert len(rows) == 1
    assert rows[0]["result"] == "succeeded"
    assert rows[0]["payload"]["version_id"] == str(version_id)


async def test_running_a_flow_records_the_outcome(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    """A run is an act against the flow, and its outcome is what auditing is for.

    The graph here has no runnable component, so the run fails — the outcome
    that matters most and the one that used to leave no trace.
    """
    flow = await _create(client, logged_in_headers)
    key = await _api_key(client, logged_in_headers)

    response = await client.post(
        f"api/v1/run/{flow['id']}",
        json={"input_value": "hello"},
        headers={"x-api-key": key},
    )
    assert response.status_code >= status.HTTP_400_BAD_REQUEST, response.text

    entries = await _trail(client, logged_in_headers, flow["id"])
    runs = [e for e in entries if e["event"] == "langflow.audit.flow.run"]

    assert len(runs) == 1
    assert runs[0]["family"] == "action"
    assert runs[0]["result"] == "failed"
    assert isinstance(runs[0]["payload"]["duration_ms"], int)
    assert runs[0]["payload"]["error_class"]
    # Never the message: it quotes whatever the flow was given.
    assert "hello" not in str(runs[0])


async def test_a_run_that_fails_without_a_valueerror_is_still_recorded(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    """The branch that used to be the only one audited was ``except ValueError``.

    A tweak the flow refuses raises its own type and is converted to a 422 by a
    different handler, so this run reaches none of the recording that existed
    before. Without a row, an operator filtering for failures sees a healthy
    system.
    """
    flow = await _create(client, logged_in_headers)
    key = await _api_key(client, logged_in_headers)

    response = await client.post(
        f"api/v1/run/{flow['id']}",
        json={"input_value": "hello", "tweaks": {"no-such-component": {"nope": 1}}},
        headers={"x-api-key": key},
    )
    assert response.status_code >= status.HTTP_400_BAD_REQUEST, response.text

    entries = await _trail(client, logged_in_headers, flow["id"])
    runs = [e for e in entries if e["event"] == "langflow.audit.flow.run"]

    assert len(runs) == 1, f"run returned {response.status_code} and left {len(runs)} rows"
    assert runs[0]["result"] == "failed"
    assert runs[0]["payload"]["error_class"]


async def test_moving_a_flow_between_projects_is_recorded(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    """A project is a permission boundary, so a move changes who can see the flow.

    The graph is untouched, which is why it went unrecorded: the update path
    only looked at ``data``. An investigation asking "how did this flow get
    into that project" had nothing to read.
    """
    flow = await _create(client, logged_in_headers)
    project = await client.post(
        "api/v1/projects/",
        json={"name": f"dest-{uuid.uuid4().hex[:8]}", "description": ""},
        headers=logged_in_headers,
    )
    assert project.status_code == status.HTTP_201_CREATED, project.text

    response = await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"folder_id": project.json()["id"]},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    entries = await _trail(client, logged_in_headers, flow["id"])
    moves = [e for e in entries if (e["payload"] or {}).get("reason") == "moved"]

    assert len(moves) == 1
    assert moves[0]["event"] == "langflow.audit.flow.update"
    assert moves[0]["result"] == "succeeded"
    # No graph changed, so the summary is empty and the reason carries the meaning.
    assert moves[0]["payload"]["changes"] == []


async def test_a_rename_beside_a_move_still_records_only_the_move(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    """A rename alone records nothing; a rename riding along with a move must
    not suppress the move, and must not invent a graph change either.
    """
    flow = await _create(client, logged_in_headers)
    project = await client.post(
        "api/v1/projects/",
        json={"name": f"dest-{uuid.uuid4().hex[:8]}", "description": ""},
        headers=logged_in_headers,
    )

    response = await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"name": f"renamed-{uuid.uuid4().hex[:8]}", "folder_id": project.json()["id"]},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    entries = await _trail(client, logged_in_headers, flow["id"])
    updates = [e for e in entries if e["event"] == "langflow.audit.flow.update"]

    assert len(updates) == 1
    assert updates[0]["payload"]["reason"] == "moved"
    assert updates[0]["payload"]["changes"] == []


async def test_a_move_that_rides_along_with_a_graph_edit_records_both(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    """One PATCH can both edit and move. The row has to say so twice over:
    the summary names what changed, the reason says it also changed hands."""
    flow = await _create(client, logged_in_headers)
    project = await client.post(
        "api/v1/projects/",
        json={"name": f"dest-{uuid.uuid4().hex[:8]}", "description": ""},
        headers=logged_in_headers,
    )

    response = await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"data": _graph("gpt-5"), "folder_id": project.json()["id"]},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    entries = await _trail(client, logged_in_headers, flow["id"])
    updates = [e for e in entries if e["event"] == "langflow.audit.flow.update"]

    assert len(updates) == 1, "one request is one row, however many things it touched"
    assert updates[0]["payload"]["reason"] == "moved"
    assert updates[0]["payload"]["changes"] == ["Agent.model_name"]
