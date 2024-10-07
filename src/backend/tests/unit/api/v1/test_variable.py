from unittest import mock
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
from httpx import AsyncClient


@pytest.fixture
async def body():
    return {
        "name": "test_variable",
        "value": "test_value",
        "type": "test_type",
        "default_fields": ["test_field"],
    }


async def test_create_variable(client: AsyncClient, body, active_user, logged_in_headers):
    response = await client.post("api/v1/variables/", json=body, headers=logged_in_headers)
    result = response.json()

    assert status.HTTP_201_CREATED == response.status_code
    assert body["name"] == result["name"]
    assert body["type"] == result["type"]
    assert body["default_fields"] == result["default_fields"]
    assert "id" in result.keys()
    assert body["value"] != result["value"]


async def test_create_variable__variable_name_already_exists(client: AsyncClient, body, active_user, logged_in_headers):
    await client.post("api/v1/variables/", json=body, headers=logged_in_headers)

    response = await client.post("api/v1/variables/", json=body, headers=logged_in_headers)
    result = response.json()

    assert status.HTTP_400_BAD_REQUEST == response.status_code
    assert "Variable name already exists" in result["detail"]


async def test_create_variable__variable_name_and_value_cannot_be_empty(
    client: AsyncClient, body, active_user, logged_in_headers
):
    body["name"] = ""
    body["value"] = ""

    response = await client.post("api/v1/variables/", json=body, headers=logged_in_headers)
    result = response.json()

    assert status.HTTP_400_BAD_REQUEST == response.status_code
    assert "Variable name and value cannot be empty" in result["detail"]


async def test_create_variable__variable_name_cannot_be_empty(
    client: AsyncClient, body, active_user, logged_in_headers
):
    body["name"] = ""

    response = await client.post("api/v1/variables/", json=body, headers=logged_in_headers)
    result = response.json()

    assert status.HTTP_400_BAD_REQUEST == response.status_code
    assert "Variable name cannot be empty" in result["detail"]


async def test_create_variable__variable_value_cannot_be_empty(
    client: AsyncClient, body, active_user, logged_in_headers
):
    body["value"] = ""

    response = await client.post("api/v1/variables/", json=body, headers=logged_in_headers)
    result = response.json()

    assert status.HTTP_400_BAD_REQUEST == response.status_code
    assert "Variable value cannot be empty" in result["detail"]


async def test_create_variable__HTTPException(client: AsyncClient, body, active_user, logged_in_headers):
    status_code = 418
    generic_message = "I'm a teapot"

    with mock.patch("langflow.services.auth.utils.encrypt_api_key") as m:
        m.side_effect = HTTPException(status_code=status_code, detail=generic_message)
        response = await client.post("api/v1/variables/", json=body, headers=logged_in_headers)
        result = response.json()

        assert status.HTTP_418_IM_A_TEAPOT == response.status_code
        assert generic_message in result["detail"]


async def test_create_variable__Exception(client: AsyncClient, body, active_user, logged_in_headers):
    generic_message = "Generic error message"

    with mock.patch("langflow.services.auth.utils.encrypt_api_key") as m:
        m.side_effect = Exception(generic_message)
        response = await client.post("api/v1/variables/", json=body, headers=logged_in_headers)
        result = response.json()

        assert status.HTTP_500_INTERNAL_SERVER_ERROR == response.status_code
        assert generic_message in result["detail"]


async def test_read_variables(client: AsyncClient, body, active_user, logged_in_headers):
    names = ["test_variable1", "test_variable2", "test_variable3"]
    for name in names:
        body["name"] = name
        await client.post("api/v1/variables/", json=body, headers=logged_in_headers)

    response = await client.get("api/v1/variables/", headers=logged_in_headers)
    result = response.json()

    assert status.HTTP_200_OK == response.status_code
    assert all(name in [r["name"] for r in result] for name in names)


async def test_read_variables__empty(client: AsyncClient, active_user, logged_in_headers):
    all_variables = await client.get("api/v1/variables/", headers=logged_in_headers)
    all_variables = all_variables.json()
    for variable in all_variables:
        await client.delete(f"api/v1/variables/{variable.get('id')}", headers=logged_in_headers)

    response = await client.get("api/v1/variables/", headers=logged_in_headers)
    result = response.json()

    assert status.HTTP_200_OK == response.status_code
    assert [] == result


async def test_read_variables__(client: AsyncClient, active_user, logged_in_headers):
    generic_message = "Generic error message"

    with pytest.raises(Exception) as exc:
        with mock.patch("sqlmodel.Session.exec") as m:
            m.side_effect = Exception(generic_message)

            response = await client.get("api/v1/variables/", headers=logged_in_headers)
            result = response.json()

            assert status.HTTP_500_INTERNAL_SERVER_ERROR == response.status_code
            assert generic_message in result["detail"]

    assert generic_message in str(exc.value)


async def test_update_variable(client: AsyncClient, body, active_user, logged_in_headers):
    saved = await client.post("api/v1/variables/", json=body, headers=logged_in_headers)
    saved = saved.json()
    body["id"] = saved.get("id")
    body["name"] = "new_name"
    body["value"] = "new_value"
    body["type"] = "new_type"
    body["default_fields"] = ["new_field"]

    response = await client.patch(f"api/v1/variables/{saved.get('id')}", json=body, headers=logged_in_headers)
    result = response.json()

    assert status.HTTP_200_OK == response.status_code
    assert saved["id"] == result["id"]
    assert saved["name"] != result["name"]
    assert saved["default_fields"] != result["default_fields"]


async def test_update_variable__Exception(client: AsyncClient, body, active_user, logged_in_headers):
    wrong_id = uuid4()
    body["id"] = str(wrong_id)

    response = await client.patch(f"api/v1/variables/{wrong_id}", json=body, headers=logged_in_headers)
    result = response.json()

    assert status.HTTP_404_NOT_FOUND == response.status_code
    assert "Variable not found" in result["detail"]


async def test_delete_variable(client: AsyncClient, body, active_user, logged_in_headers):
    response = await client.post("api/v1/variables/", json=body, headers=logged_in_headers)
    saved = response.json()
    response = await client.delete(f"api/v1/variables/{saved.get('id')}", headers=logged_in_headers)

    assert status.HTTP_204_NO_CONTENT == response.status_code


async def test_delete_variable__Exception(client: AsyncClient, active_user, logged_in_headers):
    wrong_id = uuid4()

    response = await client.delete(f"api/v1/variables/{wrong_id}", headers=logged_in_headers)

    assert status.HTTP_500_INTERNAL_SERVER_ERROR == response.status_code
