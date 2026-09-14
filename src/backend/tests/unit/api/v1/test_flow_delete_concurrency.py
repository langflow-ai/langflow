"""Only the request that removes a flow or version should report success."""

import asyncio
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.api.v1 import flows
from langflow.services.database.models.flow_version import crud as version_crud


async def test_delete_flow_returns_not_found_when_final_delete_matches_no_row(
    client: AsyncClient, logged_in_headers, monkeypatch
):
    """A zero-row delete must return 404 even when the retry read found the flow."""
    response = await client.post(
        "api/v1/flows/",
        json={"name": f"delete-zero-rows-{uuid4()}", "data": {}},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    flow_id = response.json()["id"]

    async def matched_no_row(_session, _target_flow_id):
        # PostgreSQL can wait for a competing delete and then match zero rows
        # without the lock error that drives SQLite through a retry read.
        return False

    monkeypatch.setattr(flows, "cascade_delete_flow", matched_no_row)

    response = await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Flow not found"}


@pytest.mark.parametrize("concurrent_deletions", [0, 1, 2])
async def test_bulk_delete_counts_only_rows_it_removes(
    client: AsyncClient, logged_in_headers, monkeypatch, concurrent_deletions
):
    """Rows removed after the initial bulk query must not inflate the count."""
    flow_ids = []
    for _ in range(2):
        response = await client.post(
            "api/v1/flows/",
            json={"name": f"bulk-delete-zero-rows-{uuid4()}", "data": {}},
            headers=logged_in_headers,
        )
        assert response.status_code == status.HTTP_201_CREATED
        flow_ids.append(response.json()["id"])
    removed_by_competitor = set(flow_ids[:concurrent_deletions])
    original_delete = flows.cascade_delete_flow
    attempted_ids = []

    async def delete_after_competing_requests(session, target_flow_id):
        attempted_ids.append(str(target_flow_id))
        if str(target_flow_id) in removed_by_competitor:
            return False
        return await original_delete(session, target_flow_id)

    monkeypatch.setattr(flows, "cascade_delete_flow", delete_after_competing_requests)

    response = await client.request("DELETE", "api/v1/flows/", json=flow_ids, headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"deleted": len(flow_ids) - concurrent_deletions}
    assert sorted(attempted_ids) == sorted(flow_ids)


def _request_barrier(parties: int):
    ready = asyncio.Event()
    arrivals = 0

    async def wait():
        nonlocal arrivals
        arrivals += 1
        if arrivals == parties:
            ready.set()
        await asyncio.wait_for(ready.wait(), timeout=10)

    return wait


async def test_concurrent_flow_deletes_report_one_success(client: AsyncClient, logged_in_headers, monkeypatch):
    response = await client.post(
        "api/v1/flows/",
        json={"name": f"concurrent-delete-{uuid4()}", "data": {"nodes": [], "edges": []}},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    flow_id = response.json()["id"]
    wait_for_requests = _request_barrier(4)
    original_read = flows._read_flow

    async def read_before_competing_deletes(*args, **kwargs):
        flow = await original_read(*args, **kwargs)
        # Synchronize the initial reads; retries must read the committed result.
        await wait_for_requests()
        return flow

    monkeypatch.setattr(flows, "_read_flow", read_before_competing_deletes)
    responses = await asyncio.gather(
        *(client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers) for _ in range(4))
    )

    assert sorted(response.status_code for response in responses) == [200, 404, 404, 404]
    for response in responses:
        if response.status_code == status.HTTP_200_OK:
            assert response.json() == {"message": "Flow deleted successfully"}
        else:
            assert response.json() == {"detail": "Flow not found"}
    assert (await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)).status_code == 404


async def test_concurrent_version_deletes_report_one_success(client: AsyncClient, logged_in_headers, monkeypatch):
    response = await client.post(
        "api/v1/flows/",
        json={"name": f"concurrent-version-delete-{uuid4()}", "data": {"nodes": [], "edges": []}},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    flow_id = response.json()["id"]
    response = await client.post(f"api/v1/flows/{flow_id}/versions/", json={}, headers=logged_in_headers)
    assert response.status_code == status.HTTP_201_CREATED
    version_id = response.json()["id"]
    wait_for_requests = _request_barrier(4)
    original_lock = version_crud.lock_flow_version_entry

    async def lock_after_competing_requests_arrive(*args, **kwargs):
        # All requests must reach deletion before one acquires the database lock.
        await wait_for_requests()
        return await original_lock(*args, **kwargs)

    monkeypatch.setattr(version_crud, "lock_flow_version_entry", lock_after_competing_requests_arrive)
    responses = await asyncio.gather(
        *(client.delete(f"api/v1/flows/{flow_id}/versions/{version_id}", headers=logged_in_headers) for _ in range(4))
    )

    assert sorted(response.status_code for response in responses) == [204, 404, 404, 404]
    for response in responses:
        if response.status_code == status.HTTP_404_NOT_FOUND:
            assert response.json() == {"detail": f"Version entry {version_id} not found"}
    response = await client.get(f"api/v1/flows/{flow_id}/versions/", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["entries"] == []
    assert (await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)).status_code == 200
