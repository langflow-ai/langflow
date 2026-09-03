"""The half of multi-edit safety that cannot fail open.

Every case here maps to a defect found while building the feature: a save that
overwrote somebody, a rename that stole the writer's turn, a run that manufactured
a conflict, a client that set its own token. Deleting any one of these lets the
lost-update hole reopen with nothing in CI to notice.
"""

import uuid

from fastapi import status
from httpx import AsyncClient


def _graph(label: str) -> dict:
    return {
        "nodes": [{"id": f"n-{label}", "data": {"label": label}, "position": {"x": 0, "y": 0}}],
        "edges": [],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }


async def _create_flow(client: AsyncClient, headers, **overrides) -> dict:
    payload = {"name": f"conflict-{uuid.uuid4()}", "data": _graph("base"), **overrides}
    response = await client.post("api/v1/flows/", json=payload, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


async def test_new_flow_is_protected_from_creation(client: AsyncClient, logged_in_headers):
    """A flow with no token cannot be guarded, so the very first concurrent edit would be lost."""
    flow = await _create_flow(client, logged_in_headers)

    assert flow["version_token"] is not None


async def test_graph_change_rotates_the_token(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)

    response = await client.patch(
        f"api/v1/flows/{flow['id']}", json={"data": _graph("changed")}, headers=logged_in_headers
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["version_token"] != flow["version_token"]


async def test_rename_does_not_rotate_the_token(client: AsyncClient, logged_in_headers):
    """Only a graph change takes the writer's turn; otherwise every open editor conflicts on a rename."""
    flow = await _create_flow(client, logged_in_headers)

    response = await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"name": f"renamed-{uuid.uuid4()}"},
        headers={**logged_in_headers, "If-Match": flow["version_token"]},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["version_token"] == flow["version_token"]


async def test_no_op_graph_save_does_not_rotate_the_token(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)

    response = await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"data": flow["data"]},
        headers={**logged_in_headers, "If-Match": flow["version_token"]},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["version_token"] == flow["version_token"]


async def test_fresh_token_is_accepted(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)

    response = await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"data": _graph("second")},
        headers={**logged_in_headers, "If-Match": flow["version_token"]},
    )

    assert response.status_code == status.HTTP_200_OK


async def test_stale_token_is_refused_with_context(client: AsyncClient, logged_in_headers):
    """The refusal has to name the other writer, or the dialog has nothing to say."""
    flow = await _create_flow(client, logged_in_headers)
    first = await client.patch(
        f"api/v1/flows/{flow['id']}", json={"data": _graph("theirs")}, headers=logged_in_headers
    )
    rotated = first.json()["version_token"]

    response = await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"data": _graph("mine")},
        headers={**logged_in_headers, "If-Match": flow["version_token"]},
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    detail = response.json()["detail"]
    assert detail["code"] == "flow_version_conflict"
    assert detail["expected_version_token"] == flow["version_token"]
    assert detail["current_version_token"] == rotated
    assert detail["modified_by"]["username"]
    assert detail["modified_at"]


async def test_omitting_the_header_keeps_todays_behaviour(client: AsyncClient, logged_in_headers):
    """The compatibility guarantee: every existing API client keeps working unchanged."""
    flow = await _create_flow(client, logged_in_headers)
    await client.patch(f"api/v1/flows/{flow['id']}", json={"data": _graph("theirs")}, headers=logged_in_headers)

    response = await client.patch(
        f"api/v1/flows/{flow['id']}", json={"data": _graph("unconditional")}, headers=logged_in_headers
    )

    assert response.status_code == status.HTTP_200_OK


async def test_malformed_header_is_rejected_not_ignored(client: AsyncClient, logged_in_headers):
    """Treating a bad header as absent would silently downgrade the write to unconditional."""
    flow = await _create_flow(client, logged_in_headers)

    response = await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"data": _graph("x")},
        headers={**logged_in_headers, "If-Match": "not-a-uuid"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_client_cannot_set_its_own_token(client: AsyncClient, logged_in_headers):
    """A caller that could choose its own token could always defeat the precondition."""
    flow = await _create_flow(client, logged_in_headers)
    forged = "11111111-1111-1111-1111-111111111111"

    response = await client.patch(
        f"api/v1/flows/{flow['id']}",
        json={"data": _graph("y"), "version_token": forged},
        headers={**logged_in_headers, "If-Match": flow["version_token"]},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["version_token"] != forged


async def test_version_state_reports_the_current_version_and_author(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)

    response = await client.get(f"api/v1/flows/{flow['id']}/version-state", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["version_token"] == flow["version_token"]
    assert body["last_modified_by_username"]


async def test_fork_is_inert(client: AsyncClient, logged_in_headers):
    """A copy that inherited exposure would stand up a second live listener nobody asked for."""
    source = await _create_flow(
        client,
        logged_in_headers,
        endpoint_name=f"exposed-{uuid.uuid4().hex[:8]}",
        mcp_enabled=True,
        access_type="PUBLIC",
    )

    response = await client.post(
        f"api/v1/flows/{source['id']}/fork", json={"data": _graph("merged")}, headers=logged_in_headers
    )

    assert response.status_code == status.HTTP_201_CREATED, response.text
    fork = response.json()
    assert fork["id"] != source["id"]
    assert not fork["endpoint_name"]
    assert not fork["mcp_enabled"]
    assert not fork["locked"]
    assert not fork["webhook"]
    assert fork["access_type"] == "PRIVATE"
    assert fork["data"]["nodes"][0]["id"] == "n-merged"


async def test_fork_never_collides_on_the_name(client: AsyncClient, logged_in_headers):
    """Duplicating is the conflict dialog's only exit, so it must not fail on a repeat."""
    source = await _create_flow(client, logged_in_headers)

    first = await client.post(f"api/v1/flows/{source['id']}/fork", json={}, headers=logged_in_headers)
    second = await client.post(f"api/v1/flows/{source['id']}/fork", json={}, headers=logged_in_headers)

    assert first.status_code == status.HTTP_201_CREATED
    assert second.status_code == status.HTTP_201_CREATED
    assert first.json()["name"] != second.json()["name"]


async def test_fork_leaves_the_source_untouched(client: AsyncClient, logged_in_headers):
    source = await _create_flow(client, logged_in_headers)

    await client.post(f"api/v1/flows/{source['id']}/fork", json={"data": _graph("merged")}, headers=logged_in_headers)

    after = await client.get(f"api/v1/flows/{source['id']}", headers=logged_in_headers)
    assert after.json()["data"]["nodes"][0]["id"] == "n-base"
    assert after.json()["version_token"] == source["version_token"]


async def test_only_one_of_many_simultaneous_writers_wins(client: AsyncClient, logged_in_headers):
    """The precondition has to be atomic, not a compare followed by a write.

    Comparing in Python after ``SELECT ... FOR UPDATE`` looked correct and was not:
    SQLite ignores ``FOR UPDATE``, so every concurrent writer read the same token,
    every comparison passed, and six simultaneous saves were all accepted — the
    lost update this feature exists to prevent, reproduced in full.
    """
    import asyncio

    flow = await _create_flow(client, logged_in_headers)
    headers = {**logged_in_headers, "If-Match": flow["version_token"]}

    responses = await asyncio.gather(
        *(
            client.patch(f"api/v1/flows/{flow['id']}", json={"data": _graph(f"racer-{i}")}, headers=headers)
            for i in range(6)
        )
    )

    codes = [response.status_code for response in responses]
    assert codes.count(status.HTTP_200_OK) == 1, codes
    assert codes.count(status.HTTP_409_CONFLICT) == 5, codes


async def test_a_refused_racer_is_told_who_won(client: AsyncClient, logged_in_headers):
    """A loser needs the author, or the dialog cannot name the person it is protecting."""
    import asyncio

    flow = await _create_flow(client, logged_in_headers)
    headers = {**logged_in_headers, "If-Match": flow["version_token"]}

    responses = await asyncio.gather(
        *(
            client.patch(f"api/v1/flows/{flow['id']}", json={"data": _graph(f"racer-{i}")}, headers=headers)
            for i in range(4)
        )
    )

    refused = [r for r in responses if r.status_code == status.HTTP_409_CONFLICT]
    assert refused
    for response in refused:
        detail = response.json()["detail"]
        assert detail["code"] == "flow_version_conflict"
        assert detail["modified_by"]["username"]
        assert detail["current_version_token"] != flow["version_token"]


async def test_overwrite_replaces_the_flow_with_the_merged_graph(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    theirs = await client.patch(
        f"api/v1/flows/{flow['id']}", json={"data": _graph("theirs")}, headers=logged_in_headers
    )
    reviewed = theirs.json()["version_token"]

    response = await client.post(
        f"api/v1/flows/{flow['id']}/overwrite",
        json={"data": _graph("merged")},
        headers={**logged_in_headers, "If-Match": reviewed},
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["data"]["nodes"][0]["id"] == "n-merged"
    assert response.json()["version_token"] != reviewed


async def test_overwrite_keeps_the_replaced_version_in_history(client: AsyncClient, logged_in_headers):
    """The archive is what makes overwriting safe to offer at all."""
    flow = await _create_flow(client, logged_in_headers)
    theirs = await client.patch(
        f"api/v1/flows/{flow['id']}", json={"data": _graph("theirs")}, headers=logged_in_headers
    )

    await client.post(
        f"api/v1/flows/{flow['id']}/overwrite",
        json={"data": _graph("merged")},
        headers={**logged_in_headers, "If-Match": theirs.json()["version_token"]},
    )

    versions = await client.get(f"api/v1/flows/{flow['id']}/versions/", headers=logged_in_headers)
    entries = versions.json()["entries"]
    assert entries, "the replaced version must be recoverable"
    archived = await client.get(
        f"api/v1/flows/{flow['id']}/versions/{entries[0]['id']}", headers=logged_in_headers
    )
    assert archived.json()["data"]["nodes"][0]["id"] == "n-theirs"


async def test_overwrite_is_still_refused_when_the_flow_moved_again(client: AsyncClient, logged_in_headers):
    """Overwrite means "replace what I reviewed", not "write unconditionally".

    A fourth writer landing while the dialog is open must not be discarded, which
    is the same lost update the precondition exists to stop.
    """
    flow = await _create_flow(client, logged_in_headers)
    reviewed = flow["version_token"]
    await client.patch(f"api/v1/flows/{flow['id']}", json={"data": _graph("moved-again")}, headers=logged_in_headers)

    response = await client.post(
        f"api/v1/flows/{flow['id']}/overwrite",
        json={"data": _graph("merged")},
        headers={**logged_in_headers, "If-Match": reviewed},
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"]["code"] == "flow_version_conflict"


async def test_a_refused_overwrite_archives_nothing(client: AsyncClient, logged_in_headers):
    """Snapshot and write share one transaction, so a refusal leaves no orphan version."""
    flow = await _create_flow(client, logged_in_headers)
    reviewed = flow["version_token"]
    await client.patch(f"api/v1/flows/{flow['id']}", json={"data": _graph("moved-again")}, headers=logged_in_headers)

    await client.post(
        f"api/v1/flows/{flow['id']}/overwrite",
        json={"data": _graph("merged")},
        headers={**logged_in_headers, "If-Match": reviewed},
    )

    versions = await client.get(f"api/v1/flows/{flow['id']}/versions/", headers=logged_in_headers)
    assert versions.json()["entries"] == []


async def test_version_history_names_the_author(client: AsyncClient, logged_in_headers):
    flow = await _create_flow(client, logged_in_headers)
    await client.post(f"api/v1/flows/{flow['id']}/versions/", json={"description": "snap"}, headers=logged_in_headers)

    versions = await client.get(f"api/v1/flows/{flow['id']}/versions/", headers=logged_in_headers)

    assert versions.json()["entries"][0]["username"]


async def test_a_failed_archive_does_not_take_the_writers_turn(client: AsyncClient, logged_in_headers, monkeypatch):
    """Claiming the token is only worth anything if the write that follows happens.

    The claim runs before the archive so a stale caller is refused before any row
    is written. That leaves a window the other way: if archiving fails, the token
    has already moved, and the caller's own next save would be refused for a write
    that never landed.
    """
    from langflow.api.v1 import flow_conflict_routes
    from langflow.services.database.models.flow_version.exceptions import FlowVersionError

    flow = await _create_flow(client, logged_in_headers)
    reviewed = flow["version_token"]

    async def explode(*args, **kwargs):
        msg = "archive unavailable"
        raise FlowVersionError(msg)

    monkeypatch.setattr(flow_conflict_routes, "create_flow_version_entry", explode)

    response = await client.post(
        f"api/v1/flows/{flow['id']}/overwrite",
        json={"data": _graph("merged")},
        headers={**logged_in_headers, "If-Match": reviewed},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    state = await client.get(f"api/v1/flows/{flow['id']}/version-state", headers=logged_in_headers)
    assert state.json()["version_token"] == reviewed, "a write that never happened must not consume the token"
