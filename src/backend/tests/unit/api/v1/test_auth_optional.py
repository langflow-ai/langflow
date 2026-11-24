"""Tests for get_current_user_optional dependency.

This dependency is used by build_public_tmp to optionally resolve an
authenticated user from HttpOnly cookies, Bearer tokens, or API keys.
Returns None for unauthenticated requests instead of raising.
"""

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.usefixtures("active_user")
async def test_optional_auth_returns_user_with_valid_bearer(client: AsyncClient, logged_in_headers):
    """Valid Bearer token should resolve the user before the missing-flow check."""
    # We test indirectly via build_public_tmp: if auth resolves,
    # the endpoint proceeds (may fail on flow validation, but NOT on auth)
    fake_flow_id = "00000000-0000-0000-0000-000000000099"
    response = await client.post(
        f"api/v1/build_public_tmp/{fake_flow_id}/flow",
        headers=logged_in_headers,
        json={"inputs": None},
    )
    # Auth resolved, so the endpoint reaches the non-leaking public-flow lookup
    # instead of rejecting the request for a missing anonymous client id.
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_optional_auth_returns_none_without_credentials(
    client: AsyncClient,
):
    """No credentials should still allow the endpoint to proceed (anonymous mode)."""
    fake_flow_id = "00000000-0000-0000-0000-000000000099"
    response = await client.post(
        f"api/v1/build_public_tmp/{fake_flow_id}/flow",
        json={"inputs": None},
    )
    # Without auth AND without client_id cookie → 400 (no client_id)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "client_id" in response.json().get("detail", "").lower()


async def test_optional_auth_returns_none_with_invalid_token(
    client: AsyncClient,
):
    """Invalid Bearer token should not block the request — falls back to anonymous."""
    fake_flow_id = "00000000-0000-0000-0000-000000000099"
    response = await client.post(
        f"api/v1/build_public_tmp/{fake_flow_id}/flow",
        headers={"Authorization": "Bearer invalid-expired-token"},
        json={"inputs": None},
    )
    # Invalid token → get_current_user_optional returns None → anonymous mode
    # Without client_id cookie → 400 (no client_id)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "client_id" in response.json().get("detail", "").lower()


async def test_optional_auth_returns_none_with_invalid_api_key(
    client: AsyncClient,
):
    """Invalid API key should not block the request — falls back to anonymous."""
    fake_flow_id = "00000000-0000-0000-0000-000000000099"
    response = await client.post(
        f"api/v1/build_public_tmp/{fake_flow_id}/flow",
        headers={"x-api-key": "invalid-api-key"},
        json={"inputs": None},
    )
    # Invalid API key → get_current_user_optional returns None → anonymous mode
    # Without client_id cookie → 400 (no client_id)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "client_id" in response.json().get("detail", "").lower()
