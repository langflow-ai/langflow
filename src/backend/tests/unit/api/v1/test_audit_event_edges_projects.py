"""Edge cases the happy-path suites cannot reach.

Atomicity, concurrency, and the boundaries where one person's trail must not
become another's. These are the cases that decide whether the log can be
believed, which is the only thing an audit log is for.
"""

import asyncio
import uuid

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.services.deps import get_settings_service


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
    was_on, was_anon = settings.audit_enabled, settings.audit_anonymize_payload
    settings.audit_enabled, settings.audit_anonymize_payload = True, True
    yield
    settings.audit_enabled, settings.audit_anonymize_payload = was_on, was_anon


def _flow(name: str, *, endpoint: str | None = None) -> dict:
    body = {"name": name, "data": {"nodes": [], "edges": []}}
    if endpoint:
        body["endpoint_name"] = endpoint
    return body


async def _trail(client: AsyncClient, headers, resource: str, resource_id: str) -> list[dict]:
    response = await client.get(f"api/v1/audit/{resource}/{resource_id}", headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["entries"]


async def test_a_project_is_not_left_half_created_when_a_flow_fails(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    """Half a project is worse than none: the caller cannot undo the first step."""
    duplicate = f"clash{uuid.uuid4().hex[:8]}"
    response = await client.post(
        "api/v1/projects/with-flows",
        json={
            "name": f"atomic-{uuid.uuid4()}",
            "description": "",
            # The same endpoint twice: the second insert violates
            # ``unique_flow_endpoint_name``, failing after the project and the
            # first flow already exist.
            "flows": [
                _flow(f"a-{uuid.uuid4()}", endpoint=duplicate),
                _flow(f"b-{uuid.uuid4()}", endpoint=duplicate),
            ],
        },
        headers=logged_in_headers,
    )

    assert response.status_code >= status.HTTP_400_BAD_REQUEST, response.text
    listed = await client.get("api/v1/projects/", headers=logged_in_headers)
    names = [p["name"] for p in listed.json()]
    assert not [n for n in names if n.startswith("atomic-")], "the project survived a failed creation"


async def test_replacing_contents_that_fail_leaves_the_old_contents_alone(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    created = await client.post(
        "api/v1/projects/with-flows",
        json={"name": f"keep-{uuid.uuid4()}", "description": "", "flows": [_flow(f"before-{uuid.uuid4()}")]},
        headers=logged_in_headers,
    )
    assert created.status_code == status.HTTP_201_CREATED, created.text
    project_id = created.json()["id"]

    clash = f"clash{uuid.uuid4().hex[:8]}"
    response = await client.put(
        f"api/v1/projects/{project_id}/flows",
        json={
            "flows": [
                _flow(f"a-{uuid.uuid4()}", endpoint=clash),
                _flow(f"b-{uuid.uuid4()}", endpoint=clash),
            ]
        },
        headers=logged_in_headers,
    )
    assert response.status_code >= status.HTTP_400_BAD_REQUEST, response.text

    listed = await client.get(f"api/v1/flows/?folder_id={project_id}", headers=logged_in_headers)
    remaining = [f["name"] for f in listed.json()]
    assert [n for n in remaining if n.startswith("before-")], "the old contents were destroyed by a failed replace"


async def test_concurrent_creates_each_get_their_own_row(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    """One row per act, under load. A shared counter or a leaked context shows up here."""

    async def create(index: int):
        return await client.post(
            "api/v1/projects/",
            json={"name": f"race-{index}-{uuid.uuid4()}", "description": ""},
            headers=logged_in_headers,
        )

    responses = await asyncio.gather(*(create(i) for i in range(8)))
    created = [r.json() for r in responses if r.status_code == status.HTTP_201_CREATED]
    assert len(created) == 8, [r.status_code for r in responses]

    for project in created:
        entries = await _trail(client, logged_in_headers, "project", project["id"])
        rows = [e for e in entries if e["event"] == "langflow.audit.project.create"]
        assert len(rows) == 1, f"{project['name']} has {len(rows)} rows"
        assert rows[0]["result"] == "succeeded"


async def test_an_aggregate_does_not_silence_a_flow_created_beside_it(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    """The absorb context is per-task, not global.

    If it leaked, an ordinary flow created while an aggregate runs would lose
    its own row — the audit would go quiet for reasons nobody could see.
    """
    solo_name = f"solo-{uuid.uuid4()}"
    aggregate = client.post(
        "api/v1/projects/with-flows",
        json={
            "name": f"aggregate-{uuid.uuid4()}",
            "description": "",
            "flows": [_flow(f"inside-{uuid.uuid4()}") for _ in range(3)],
        },
        headers=logged_in_headers,
    )
    solo = client.post("api/v1/flows/", json=_flow(solo_name), headers=logged_in_headers)
    aggregate_response, solo_response = await asyncio.gather(aggregate, solo)

    assert aggregate_response.status_code == status.HTTP_201_CREATED, aggregate_response.text
    assert solo_response.status_code == status.HTTP_201_CREATED, solo_response.text

    entries = await _trail(client, logged_in_headers, "flow", solo_response.json()["id"])
    assert [e for e in entries if e["event"] == "langflow.audit.flow.create"], (
        "the flow beside the aggregate lost its own row"
    )


async def test_the_flows_inside_an_aggregate_have_no_rows_of_their_own(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    response = await client.post(
        "api/v1/projects/with-flows",
        json={"name": f"quiet-{uuid.uuid4()}", "description": "", "flows": [_flow(f"inside-{uuid.uuid4()}")]},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text

    listed = await client.get(f"api/v1/flows/?folder_id={response.json()['id']}", headers=logged_in_headers)
    inside = listed.json()
    assert len(inside) == 1

    entries = await _trail(client, logged_in_headers, "flow", inside[0]["id"])
    assert entries == [], "a flow absorbed into an aggregate wrote its own row anyway"


async def test_nothing_is_recorded_for_projects_when_the_feature_is_off(
    client: AsyncClient,
    logged_in_headers,
):
    settings = get_settings_service().settings
    original = settings.audit_enabled
    settings.audit_enabled = False
    try:
        response = await client.post(
            "api/v1/projects/",
            json={"name": f"off-{uuid.uuid4()}", "description": ""},
            headers=logged_in_headers,
        )
        assert response.status_code == status.HTTP_201_CREATED, response.text
        project_id = response.json()["id"]
    finally:
        settings.audit_enabled = original

    settings.audit_enabled = False
    try:
        response = await client.get(f"api/v1/audit/project/{project_id}", headers=logged_in_headers)
    finally:
        settings.audit_enabled = original
    # The endpoint says the feature is off rather than serving an empty page,
    # which would read as "nothing happened".
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text

    settings.audit_enabled = True
    try:
        assert await _trail(client, logged_in_headers, "project", project_id) == []
    finally:
        settings.audit_enabled = original


async def test_anonymizing_keeps_the_project_row_and_drops_its_payload(
    client: AsyncClient,
    logged_in_headers,
    anonymized,  # noqa: ARG001
):
    response = await client.post(
        "api/v1/projects/with-flows",
        json={"name": f"anon-{uuid.uuid4()}", "description": "", "flows": [_flow(f"x-{uuid.uuid4()}")]},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text

    entries = await _trail(client, logged_in_headers, "project", response.json()["id"])
    created = [e for e in entries if e["event"] == "langflow.audit.project.create"]

    assert len(created) == 1
    assert created[0]["result"] == "succeeded", "who, what and when must survive anonymizing"
    assert created[0]["payload"] is None


async def test_a_deleted_projects_trail_stays_with_the_person_who_acted(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    response = await client.post(
        "api/v1/projects/",
        json={"name": f"gone-{uuid.uuid4()}", "description": ""},
        headers=logged_in_headers,
    )
    project_id = response.json()["id"]
    assert (await client.delete(f"api/v1/projects/{project_id}", headers=logged_in_headers)).status_code == (
        status.HTTP_204_NO_CONTENT
    )

    entries = await _trail(client, logged_in_headers, "project", project_id)
    assert [e for e in entries if e["event"] == "langflow.audit.project.delete"]


async def test_a_trail_for_a_resource_that_never_existed_is_not_found(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    """A 404 rather than an empty page: the endpoint must not confirm UUIDs."""
    response = await client.get(f"api/v1/audit/project/{uuid.uuid4()}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text


async def test_deleting_a_project_records_the_loss_of_every_flow_inside_it(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    """A project's own row cannot answer "what happened to this flow".

    Deleting a project destroys the flows in it just as surely as a bulk delete
    does, and a bulk delete already writes one row per flow. Without these rows
    each flow's trail ends at its creation, describing a flow that still exists.
    """
    project = await client.post(
        "api/v1/projects/",
        json={"name": f"doomed-{uuid.uuid4().hex[:8]}", "description": ""},
        headers=logged_in_headers,
    )
    project_id = project.json()["id"]
    flows = []
    for i in range(3):
        created = await client.post(
            "api/v1/flows/",
            json={**_flow(f"inside{i}-{uuid.uuid4().hex[:8]}"), "folder_id": project_id},
            headers=logged_in_headers,
        )
        assert created.status_code == status.HTTP_201_CREATED, created.text
        flows.append(created.json()["id"])

    removed = await client.delete(f"api/v1/projects/{project_id}", headers=logged_in_headers)
    assert removed.status_code == status.HTTP_204_NO_CONTENT, removed.text

    for flow_id in flows:
        events = [e["event"] for e in await _trail(client, logged_in_headers, "flow", flow_id)]
        assert "langflow.audit.flow.delete" in events, f"{flow_id} was destroyed with no record of it"

    project_events = [e["event"] for e in await _trail(client, logged_in_headers, "project", project_id)]
    assert "langflow.audit.project.delete" in project_events


async def test_a_refused_replace_still_records_that_it_was_refused(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    """A failure row goes out on a second connection, which needs the write lock.

    The caller's transaction has to let go of it first. A refused replace has
    already deleted the old contents by then, so it is holding that lock — and on
    SQLite a second connection does not wait for it, it fails. The row that went
    missing was the one an investigation starts from.
    """
    project = await client.post(
        "api/v1/projects/with-flows",
        json={
            "name": f"replaced-{uuid.uuid4().hex[:8]}",
            "description": "",
            "flows": [_flow(f"keep-{uuid.uuid4().hex[:8]}")],
        },
        headers=logged_in_headers,
    )
    assert project.status_code == status.HTTP_201_CREATED, project.text
    project_id = project.json()["id"]

    clash = f"clash{uuid.uuid4().hex[:8]}"
    refused = await client.put(
        f"api/v1/projects/{project_id}/flows",
        json={"flows": [_flow(clash, endpoint=clash), _flow(f"{clash}-2", endpoint=clash)]},
        headers=logged_in_headers,
    )
    assert refused.status_code == status.HTTP_409_CONFLICT, refused.text

    entries = await _trail(client, logged_in_headers, "project", project_id)
    replaces = [e for e in entries if e["event"] == "langflow.audit.project.replace"]

    assert len(replaces) == 1
    assert replaces[0]["result"] == "failed"
    assert replaces[0]["family"] == "action", "a refusal on contents is a failed act, not a denial"
