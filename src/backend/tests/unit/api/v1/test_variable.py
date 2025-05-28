from unittest import mock
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
from httpx import AsyncClient
from langflow.services.variable.constants import CREDENTIAL_TYPE, GENERIC_TYPE


@pytest.fixture
def generic_variable():
    return {
        "name": "test_generic_variable",
        "value": "test_generic_value",
        "type": GENERIC_TYPE,
        "default_fields": ["test_field"],
    }


@pytest.fixture
def credential_variable():
    return {
        "name": "test_credential_variable",
        "value": "test_credential_value",
        "type": CREDENTIAL_TYPE,
        "default_fields": ["test_field"],
    }


@pytest.mark.usefixtures("active_user")
async def test_create_variable(client: AsyncClient, generic_variable, logged_in_headers):
    response = await client.post("api/v1/variables/", json=generic_variable, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_201_CREATED
    assert generic_variable["name"] == result["name"]
    assert generic_variable["type"] == result["type"]
    assert generic_variable["default_fields"] == result["default_fields"]
    assert "id" in result
    assert generic_variable["value"] != result["value"]  # Value should be encrypted


@pytest.mark.usefixtures("active_user")
async def test_create_variable__variable_name_already_exists(client: AsyncClient, generic_variable, logged_in_headers):
    await client.post("api/v1/variables/", json=generic_variable, headers=logged_in_headers)

    response = await client.post("api/v1/variables/", json=generic_variable, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Variable name already exists" in result["detail"]


@pytest.mark.usefixtures("active_user")
async def test_create_variable__variable_name_and_value_cannot_be_empty(
    client: AsyncClient, generic_variable, logged_in_headers
):
    generic_variable["name"] = ""
    generic_variable["value"] = ""

    response = await client.post("api/v1/variables/", json=generic_variable, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Variable name and value cannot be empty" in result["detail"]


@pytest.mark.usefixtures("active_user")
async def test_create_variable__variable_name_cannot_be_empty(client: AsyncClient, generic_variable, logged_in_headers):
    generic_variable["name"] = ""

    response = await client.post("api/v1/variables/", json=generic_variable, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Variable name cannot be empty" in result["detail"]


@pytest.mark.usefixtures("active_user")
async def test_create_variable__variable_value_cannot_be_empty(
    client: AsyncClient, generic_variable, logged_in_headers
):
    generic_variable["value"] = ""

    response = await client.post("api/v1/variables/", json=generic_variable, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Variable value cannot be empty" in result["detail"]


@pytest.mark.usefixtures("active_user")
async def test_create_variable__httpexception(client: AsyncClient, generic_variable, logged_in_headers):
    status_code = 418
    generic_message = "I'm a teapot"

    with mock.patch("langflow.services.auth.utils.encrypt_api_key") as m:
        m.side_effect = HTTPException(status_code=status_code, detail=generic_message)
        response = await client.post("api/v1/variables/", json=generic_variable, headers=logged_in_headers)
        result = response.json()

        assert response.status_code == status.HTTP_418_IM_A_TEAPOT
        assert generic_message in result["detail"]


@pytest.mark.usefixtures("active_user")
async def test_create_variable__exception(client: AsyncClient, generic_variable, logged_in_headers):
    generic_message = "Generic error message"

    with mock.patch("langflow.services.auth.utils.encrypt_api_key") as m:
        m.side_effect = Exception(generic_message)
        response = await client.post("api/v1/variables/", json=generic_variable, headers=logged_in_headers)
        result = response.json()

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert generic_message in result["detail"]


@pytest.mark.usefixtures("active_user")
async def test_read_variables(client: AsyncClient, generic_variable, credential_variable, logged_in_headers):
    # Create a generic variable
    create_response = await client.post("api/v1/variables/", json=generic_variable, headers=logged_in_headers)
    assert create_response.status_code == status.HTTP_201_CREATED

    # Create a credential variable
    create_response = await client.post("api/v1/variables/", json=credential_variable, headers=logged_in_headers)
    assert create_response.status_code == status.HTTP_201_CREATED

    response = await client.get("api/v1/variables/", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK

    # Check both variables exist
    assert generic_variable["name"] in [r["name"] for r in result]
    assert credential_variable["name"] in [r["name"] for r in result]

    # Assert that credentials are not decrypted and generic are decrypted
    credential_vars = [r for r in result if r["type"] == CREDENTIAL_TYPE]
    generic_vars = [r for r in result if r["type"] == GENERIC_TYPE]

    # Credential variables should remain encrypted (value should be different)
    assert all(c["value"] != credential_variable["value"] for c in credential_vars)

    # Generic variables should be decrypted (value should match original)
    assert all(g["value"] == generic_variable["value"] for g in generic_vars)


@pytest.mark.usefixtures("active_user")
async def test_read_variables__empty(client: AsyncClient, logged_in_headers):
    all_variables = await client.get("api/v1/variables/", headers=logged_in_headers)
    all_variables = all_variables.json()
    for variable in all_variables:
        await client.delete(f"api/v1/variables/{variable.get('id')}", headers=logged_in_headers)

    response = await client.get("api/v1/variables/", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert result == []


@pytest.mark.usefixtures("active_user")
async def test_read_variables__(client: AsyncClient, logged_in_headers):
    generic_message = "Generic error message"

    with mock.patch("sqlmodel.Session.exec") as m:
        m.side_effect = Exception(generic_message)
        with pytest.raises(Exception, match=generic_message):
            await client.get("api/v1/variables/", headers=logged_in_headers)


@pytest.mark.usefixtures("active_user")
async def test_update_variable(client: AsyncClient, generic_variable, logged_in_headers):
    saved = await client.post("api/v1/variables/", json=generic_variable, headers=logged_in_headers)
    saved = saved.json()
    generic_variable["id"] = saved.get("id")
    generic_variable["name"] = "new_name"
    generic_variable["value"] = "new_value"
    generic_variable["type"] = GENERIC_TYPE  # Ensure we keep it as GENERIC_TYPE
    generic_variable["default_fields"] = ["new_field"]

    response = await client.patch(
        f"api/v1/variables/{saved.get('id')}", json=generic_variable, headers=logged_in_headers
    )
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert saved["id"] == result["id"]
    assert saved["name"] != result["name"]
    assert saved["default_fields"] != result["default_fields"]


@pytest.mark.usefixtures("active_user")
async def test_update_variable__exception(client: AsyncClient, generic_variable, logged_in_headers):
    wrong_id = uuid4()
    generic_variable["id"] = str(wrong_id)

    response = await client.patch(f"api/v1/variables/{wrong_id}", json=generic_variable, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "Variable not found" in result["detail"]


@pytest.mark.usefixtures("active_user")
async def test_delete_variable(client: AsyncClient, generic_variable, logged_in_headers):
    response = await client.post("api/v1/variables/", json=generic_variable, headers=logged_in_headers)
    saved = response.json()
    response = await client.delete(f"api/v1/variables/{saved.get('id')}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.usefixtures("active_user")
async def test_delete_variable__exception(client: AsyncClient, logged_in_headers):
    wrong_id = uuid4()

    response = await client.delete(f"api/v1/variables/{wrong_id}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
