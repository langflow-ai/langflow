from fastapi import status
from httpx import AsyncClient


def _provider_payload(
    *,
    provider_tenant_id: str | None = "tenant-1",
    provider_key: str | None = "watsonx-orchestrate",
    provider_url: str = "https://example.ibm.com",
    api_key: str = "secret-api-key",
) -> dict:
    payload = {
        "provider_url": provider_url,
        "api_key": api_key,
    }
    if provider_tenant_id is not None:
        payload["provider_tenant_id"] = provider_tenant_id
    if provider_key is not None:
        payload["provider_key"] = provider_key
    return payload


async def test_deployment_provider_account_crud(client: AsyncClient, logged_in_headers):
    create_response = await client.post(
        "api/v1/deployments/providers",
        json=_provider_payload(),
        headers=logged_in_headers,
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    created = create_response.json()
    assert created["provider_tenant_id"] == "tenant-1"
    assert created["provider_key"] == "watsonx-orchestrate"
    assert created["provider_url"] == "https://example.ibm.com"
    assert "api_key" not in created

    list_response = await client.get("api/v1/deployments/providers", headers=logged_in_headers)
    assert list_response.status_code == status.HTTP_200_OK
    listed = list_response.json()["providers"]
    assert any(item["id"] == created["id"] for item in listed)

    get_response = await client.get(f"api/v1/deployments/providers/{created['id']}", headers=logged_in_headers)
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.json()["id"] == created["id"]

    update_response = await client.patch(
        f"api/v1/deployments/providers/{created['id']}",
        json={"provider_url": "https://updated.example.ibm.com"},
        headers=logged_in_headers,
    )
    assert update_response.status_code == status.HTTP_200_OK
    updated = update_response.json()
    assert updated["provider_url"] == "https://updated.example.ibm.com"
    assert "api_key" not in updated

    delete_response = await client.delete(f"api/v1/deployments/providers/{created['id']}", headers=logged_in_headers)
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    not_found_response = await client.get(f"api/v1/deployments/providers/{created['id']}", headers=logged_in_headers)
    assert not_found_response.status_code == status.HTTP_404_NOT_FOUND


async def test_deployment_provider_account_is_user_scoped(
    client: AsyncClient,
    logged_in_headers,
    user_two,
):
    create_response = await client.post(
        "api/v1/deployments/providers",
        json=_provider_payload(provider_tenant_id="tenant-owned-by-user-one"),
        headers=logged_in_headers,
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    created = create_response.json()

    other_user_login = await client.post(
        "api/v1/login",
        data={"username": user_two.username, "password": "hashed_password"},  # pragma: allowlist secret
    )
    assert other_user_login.status_code == status.HTTP_200_OK
    other_user_headers = {"Authorization": f"Bearer {other_user_login.json()['access_token']}"}

    other_user_get = await client.get(f"api/v1/deployments/providers/{created['id']}", headers=other_user_headers)
    assert other_user_get.status_code == status.HTTP_404_NOT_FOUND


async def test_deployment_provider_account_requires_provider_key(
    client: AsyncClient,
    logged_in_headers,
):
    create_response = await client.post(
        "api/v1/deployments/providers",
        json=_provider_payload(
            provider_tenant_id=None,
            provider_key=None,
            provider_url="https://api.dl.watson-orchestrate.ibm.com/instances/20250430-1824-1871-40a1-cbba522cb662",
        ),
        headers=logged_in_headers,
    )
    assert create_response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
