from unittest import mock
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient


async def test_add_user(client: AsyncClient):
    basic_case = {
        "username": "string",
        "password": "string"
    }
    response = await client.post("api/v1/users/", json=basic_case)
    result = response.json()

    assert response.status_code == status.HTTP_201_CREATED
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "id" in result, "The result must have an 'id' key"
    assert "is_active" in result, "The result must have an 'is_active' key"
    assert "is_superuser" in result, "The result must have an 'is_superuser' key"
    assert "last_login_at" in result, "The result must have an 'last_login_at' key"
    assert "profile_image" in result, "The result must have an 'profile_image' key"
    assert "store_api_key" in result, "The result must have an 'store_api_key' key"
    assert "updated_at" in result, "The result must have an 'updated_at' key"
    assert "username" in result, "The result must have an 'username' key"


async def test_read_current_user(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/users/whoami", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "id" in result, "The result must have an 'id' key"
    assert "is_active" in result, "The result must have an 'is_active' key"
    assert "is_superuser" in result, "The result must have an 'is_superuser' key"
    assert "last_login_at" in result, "The result must have an 'last_login_at' key"
    assert "profile_image" in result, "The result must have an 'profile_image' key"
    assert "store_api_key" in result, "The result must have an 'store_api_key' key"
    assert "updated_at" in result, "The result must have an 'updated_at' key"
    assert "username" in result, "The result must have an 'username' key"
