"""Only the request that removes a flow or version should report success."""

import asyncio
from uuid import uuid4

from fastapi import status
from httpx import AsyncClient
from langflow.api.v1 import flows
from langflow.services.database.models.flow_version import crud as version_crud


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
    original_check = version_crud.has_deployment_attachments

    async def check_before_competing_deletes(*args, **kwargs):
        attached = await original_check(*args, **kwargs)
        await wait_for_requests()
        return attached

    monkeypatch.setattr(version_crud, "has_deployment_attachments", check_before_competing_deletes)
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
