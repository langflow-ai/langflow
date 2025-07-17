from fastapi import status
from httpx import AsyncClient


async def test_get_starter_projects(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/starter-projects/", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK, response.text
    assert isinstance(result, list), "The result must be a list"
