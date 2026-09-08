"""Who changed a flow and what they changed, recorded without costing the save."""

import uuid
from contextlib import contextmanager

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.services.deps import get_settings_service

_AUDIT_SETTINGS = (
    "flow_audit_enabled",
    "flow_audit_session_window_seconds",
    "max_flow_audit_entries_per_flow",
)


@contextmanager
def _audit(*, enabled: bool):
    """Force the trail on or off, and put every audit setting back afterwards.

    Restoring all three matters: tests that shorten the session window or the
    retention ceiling would otherwise leak those values into whatever runs next.
    Forcing the value matters too — a developer with the flag in their .env was
    enough to fail the test that asserts the default.
    """
    settings = get_settings_service().settings
    previous = {name: getattr(settings, name) for name in _AUDIT_SETTINGS}
    settings.flow_audit_enabled = enabled
    try:
        yield settings
    finally:
        for name, value in previous.items():
            setattr(settings, name, value)


@pytest.fixture
def audit_on():
    with _audit(enabled=True) as settings:
        yield settings


@pytest.fixture
def audit_off():
    with _audit(enabled=False) as settings:
        yield settings


def _graph(label: str, value: str = "one", position=(0, 0), *, secret: bool = False) -> dict:
    field = {"display_name": "Input Text", "value": value}
    if secret:
        field["password"] = True
    return {
        "nodes": [
            {
                "id": f"node-{label}",
                "position": {"x": position[0], "y": position[1]},
                "data": {
                    "id": f"node-{label}",
                    "node": {"display_name": "Chat Input", "template": {"input_value": field}},
                },
            }
        ],
        "edges": [],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }


async def _create_flow(client: AsyncClient, headers) -> dict:
    response = await client.post(
        "api/v1/flows/",
        json={"name": f"audit-{uuid.uuid4()}", "data": _graph("a")},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


async def _entries(client: AsyncClient, headers, flow_id: str) -> list[dict]:
    response = await client.get(f"api/v1/flows/{flow_id}/audit/", headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["entries"]


async def test_the_trail_is_off_until_a_deployment_turns_it_on(client: AsyncClient, logged_in_headers, audit_off):  # noqa: ARG001
    """Durable storage nobody asked for is a cost, not a feature."""
    flow = await _create_flow(client, logged_in_headers)

    response = await client.get(f"api/v1/flows/{flow['id']}/audit/", headers=logged_in_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_an_edit_records_who_changed_what(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    flow = await _create_flow(client, logged_in_headers)

    await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"data": _graph("a", "two")},
        headers=logged_in_headers,
    )

    [entry] = await _entries(client, logged_in_headers, flow["id"])
    assert entry["username"]
    assert entry["source"] == "editor"
    [group] = entry["changes"]
    assert group["label"] == "Chat Input"
    assert group["changes"] == [
        {"kind": "field", "field": "input_value", "label": "Input Text", "before": "one", "after": "two"}
    ]


async def test_a_burst_of_edits_is_one_entry_reporting_where_the_value_ended(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    """Typing a word produces one entry, not one per keystroke burst."""
    flow = await _create_flow(client, logged_in_headers)

    for value in ("t", "te", "tes", "test"):
        await client.patch(
            f"api/v1/flows/{flow['id']}",
            json={"data": _graph("a", value)},
            headers=logged_in_headers,
        )

    entries = await _entries(client, logged_in_headers, flow["id"])
    assert len(entries) == 1
    [group] = entries[0]["changes"]
    [change] = group["changes"]
    assert change["before"] == "one"
    assert change["after"] == "test"


async def test_a_value_driven_back_to_where_it_started_leaves_nothing_behind(
    client: AsyncClient,
    logged_in_headers,
    audit_on,  # noqa: ARG001
):
    """An entry claiming a change the flow no longer has would be false."""
    flow = await _create_flow(client, logged_in_headers)

    await client.patch(f"api/v1/flows/{flow['id']}", json={"data": _graph("a", "two")}, headers=logged_in_headers)
    await client.patch(f"api/v1/flows/{flow['id']}", json={"data": _graph("a", "one")}, headers=logged_in_headers)

    assert await _entries(client, logged_in_headers, flow["id"]) == []


async def test_a_secret_is_recorded_as_touched_with_no_value(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    flow = await _create_flow(client, logged_in_headers)
    await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"data": _graph("a", "sk-live-old", secret=True)},
        headers=logged_in_headers,
    )

    await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"data": _graph("a", "sk-live-new", secret=True)},
        headers=logged_in_headers,
    )

    entries = await _entries(client, logged_in_headers, flow["id"])
    assert "sk-live-new" not in str(entries)
    assert "sk-live-old" not in str(entries)
    assert any(change.get("secret") for entry in entries for group in entry["changes"] for change in group["changes"])


async def test_a_rename_records_nothing(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    """It changes no graph, so there is nothing to describe."""
    flow = await _create_flow(client, logged_in_headers)

    await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"name": f"renamed-{uuid.uuid4()}"},
        headers=logged_in_headers,
    )

    assert await _entries(client, logged_in_headers, flow["id"]) == []


async def test_a_no_op_save_records_nothing(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    flow = await _create_flow(client, logged_in_headers)

    await client.patch(f"api/v1/flows/{flow['id']}", json={"data": flow["data"]}, headers=logged_in_headers)

    assert await _entries(client, logged_in_headers, flow["id"]) == []


async def test_an_import_over_a_flow_is_recorded_as_its_own_door(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    """A write from outside the editor is still a write somebody made."""
    import json

    flow = await _create_flow(client, logged_in_headers)
    payload = {"id": flow["id"], "name": flow["name"], "data": _graph("a", "imported"), "is_component": False}

    response = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("flow.json", json.dumps(payload).encode(), "application/json")},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text

    [entry] = await _entries(client, logged_in_headers, flow["id"])
    assert entry["source"] == "import"


async def test_the_trail_chains_onto_the_version_the_flow_carried(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    flow = await _create_flow(client, logged_in_headers)

    response = await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"data": _graph("a", "two")},
        headers=logged_in_headers,
    )

    [entry] = await _entries(client, logged_in_headers, flow["id"])
    assert entry["id"]
    assert response.json()["version_token"] != flow["version_token"]


async def test_the_list_is_paginated_and_filterable(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    flow = await _create_flow(client, logged_in_headers)
    await client.patch(f"api/v1/flows/{flow['id']}", json={"data": _graph("a", "two")}, headers=logged_in_headers)

    response = await client.get(f"api/v1/flows/{flow['id']}/audit/?limit=1", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK

    other_actor = await client.get(f"api/v1/flows/{flow['id']}/audit/?actor={uuid.uuid4()}", headers=logged_in_headers)
    assert other_actor.json()["entries"] == []


async def test_an_unknown_flow_is_refused(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    response = await client.get(f"api/v1/flows/{uuid.uuid4()}/audit/", headers=logged_in_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_a_conflict_overwrite_names_its_own_door(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    flow = await _create_flow(client, logged_in_headers)

    response = await client.post(
        f"api/v1/flows/{flow['id']}/overwrite",
        json={"data": _graph("a", "merged")},
        headers={**logged_in_headers, "If-Match": flow["version_token"]},
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    [entry] = await _entries(client, logged_in_headers, flow["id"])
    assert entry["source"] == "overwrite"


async def test_restoring_a_version_is_recorded_as_a_change(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    """Restoring rewrites the graph like any other write, and someone chose to do it."""
    flow = await _create_flow(client, logged_in_headers)
    snapshot = await client.post(
        f"api/v1/flows/{flow['id']}/versions/", json={"description": "before"}, headers=logged_in_headers
    )
    assert snapshot.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED), snapshot.text
    version_id = snapshot.json()["id"]
    await client.patch(f"api/v1/flows/{flow['id']}", json={"data": _graph("a", "two")}, headers=logged_in_headers)

    response = await client.post(f"api/v1/flows/{flow['id']}/versions/{version_id}/activate", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK, response.text

    sources = {entry["source"] for entry in await _entries(client, logged_in_headers, flow["id"])}
    assert "restore" in sources


async def test_a_pause_longer_than_the_window_starts_a_new_entry(client: AsyncClient, logged_in_headers, audit_on):
    """A session is one sitting; coming back tomorrow is a second one."""
    audit_on.flow_audit_session_window_seconds = 0

    flow = await _create_flow(client, logged_in_headers)
    await client.patch(f"api/v1/flows/{flow['id']}", json={"data": _graph("a", "two")}, headers=logged_in_headers)
    await client.patch(f"api/v1/flows/{flow['id']}", json={"data": _graph("a", "three")}, headers=logged_in_headers)

    assert len(await _entries(client, logged_in_headers, flow["id"])) == 2


async def test_a_failing_recorder_never_costs_the_save(client: AsyncClient, logged_in_headers, audit_on, monkeypatch):  # noqa: ARG001
    """The record is worth less than the work it describes."""

    def explode(*_args, **_kwargs):
        msg = "the diff engine fell over"
        raise RuntimeError(msg)

    monkeypatch.setattr("langflow.services.flow_audit.recorder.diff_graphs", explode)
    flow = await _create_flow(client, logged_in_headers)

    response = await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"data": _graph("a", "two")},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    saved = await client.get(f"api/v1/flows/{flow['id']}", headers=logged_in_headers)
    assert saved.json()["data"]["nodes"][0]["data"]["node"]["template"]["input_value"]["value"] == "two"


async def test_the_trail_never_claims_a_change_the_flow_does_not_have(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    """Concurrent unconditional writes overwrite each other; the entry follows the graph."""
    flow = await _create_flow(client, logged_in_headers)

    await client.patch(f"api/v1/flows/{flow['id']}", json={"data": _graph("a", "first")}, headers=logged_in_headers)
    await client.patch(f"api/v1/flows/{flow['id']}", json={"data": _graph("a", "second")}, headers=logged_in_headers)

    entries = await _entries(client, logged_in_headers, flow["id"])
    server = (await client.get(f"api/v1/flows/{flow['id']}", headers=logged_in_headers)).json()
    ends = {c.get("after") for e in entries for g in e["changes"] for c in g["changes"]}

    assert ends == {server["data"]["nodes"][0]["data"]["node"]["template"]["input_value"]["value"]}


async def test_the_trail_is_capped_per_flow(client: AsyncClient, logged_in_headers, audit_on):
    """Coalescing bounds how fast the trail grows, not how far."""
    audit_on.flow_audit_session_window_seconds = 0
    audit_on.max_flow_audit_entries_per_flow = 3

    flow = await _create_flow(client, logged_in_headers)
    for value in ("two", "three", "four", "five", "six"):
        await client.patch(
            f"api/v1/flows/{flow['id']}",
            json={"data": _graph("a", value)},
            headers=logged_in_headers,
        )

    entries = await _entries(client, logged_in_headers, flow["id"])
    assert len(entries) <= 3

    # The survivors are the newest, and the oldest edit is the one dropped.
    values = {c.get("after") for e in entries for g in e["changes"] for c in g["changes"]}
    assert "six" in values
    assert "two" not in values


async def test_an_entry_carries_the_versions_it_moved_between(client: AsyncClient, logged_in_headers, audit_on):  # noqa: ARG001
    """The pair lines an entry up with the 409 the other person was given."""
    flow = await _create_flow(client, logged_in_headers)

    response = await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"data": _graph("a", "two")},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    [entry] = await _entries(client, logged_in_headers, flow["id"])
    assert entry["from_version_token"] == flow["version_token"]
    assert entry["to_version_token"] == response.json()["version_token"]
    # And neither is a version-history id.
    versions = await client.get(f"api/v1/flows/{flow['id']}/versions/", headers=logged_in_headers)
    version_ids = {v["id"] for v in versions.json().get("entries", [])}
    assert entry["to_version_token"] not in version_ids
