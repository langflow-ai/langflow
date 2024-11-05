import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.skip(reason="Temporarily disabled: This is currently broken")
async def test_retrieve_vertices_order(client: AsyncClient):
    flow_id = "123e4567-e89b-12d3-a456-426614174000"
    basic_case = {"nodes": [{}], "edges": [{}], "viewport": {}}

    response = await client.post(f"api/v1/build/{flow_id}/vertices", json=basic_case)

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.skip(reason="Temporarily disabled: This is currently broken")
async def test_build_flow(client: AsyncClient, logged_in_headers):
    flow_id = "123e4567-e89b-12d3-a456-426614174000"

    response = await client.post(f"api/v1/build/{flow_id}/flow", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.skip(reason="Temporarily disabled: This is currently broken")
async def test_build_vertex(client: AsyncClient, logged_in_headers):
    flow_id = "123e4567-e89b-12d3-a456-426614174000"
    vertex_id = "123"

    response = await client.post(f"api/v1/build/{flow_id}/vertices/{vertex_id}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.skip(reason="Temporarily disabled: This is currently broken")
async def test_build_vertex_stream(client: AsyncClient):
    flow_id = "123e4567-e89b-12d3-a456-426614174000"
    vertex_id = "123"

    response = await client.post(f"api/v1/build/{flow_id}/{vertex_id}/stream")

    assert response.status_code == status.HTTP_200_OK
