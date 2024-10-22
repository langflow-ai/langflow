import pytest
from fastapi import status
from httpx import AsyncClient


async def test_post_validate_code(client: AsyncClient):
    good_code = """
from pprint import pprint
var = {"a": 1, "b": 2}
pprint(var)
    """
    response = await client.post("api/v1/validate/code", json={"code": good_code})
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "imports" in result.keys(), "The result must have an 'imports' key"
    assert "function" in result.keys(), "The result must have a 'function' key"
