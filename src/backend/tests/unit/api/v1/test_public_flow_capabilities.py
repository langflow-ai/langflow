"""The direct-link flow payload must carry the anonymous capability set.

``GET /api/v1/flows/public_flow/{id}`` is the only signal the shareable
playground has about a flow it is allowed to open. Before this contract the
page re-derived public access from the legacy ``Flow.access_type`` flag, so a
flow published purely through a canonical ``AuthzShare(scope=public)`` was
authorized by the API and unreachable in the UI. The response now reports the
same decision the authorization layer just made.
"""

from uuid import UUID

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.services.database.models.auth import AuthzShare, SharePermissionLevel, ShareScope
from langflow.services.database.models.flow.model import Flow
from lfx.services.deps import session_scope


def _flow_payload(name: str) -> dict:
    """A minimal chat-shaped flow; access_type is left at its PRIVATE default."""
    return {
        "name": name,
        "description": "capability contract flow",
        "data": {
            "nodes": [
                {
                    "id": "node-1",
                    "type": "genericNode",
                    "position": {"x": 0, "y": 0},
                    "data": {"id": "node-1", "type": "ChatInput", "node": {"template": {}}},
                }
            ],
            "edges": [],
        },
    }


async def _create_flow(client: AsyncClient, logged_in_headers, name: str) -> UUID:
    response = await client.post("api/v1/flows/", json=_flow_payload(name), headers=logged_in_headers)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["access_type"] == "PRIVATE"
    return UUID(response.json()["id"])


async def _add_public_share(flow_id: UUID, permission_level: str) -> None:
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        assert flow is not None
        session.add(
            AuthzShare(
                resource_type="flow",
                resource_id=flow_id,
                scope=ShareScope.PUBLIC.value,
                permission_level=permission_level,
                created_by=flow.user_id,
            )
        )
        await session.commit()


@pytest.mark.parametrize(
    ("permission_level", "expected_can_execute"),
    [
        (SharePermissionLevel.EXECUTE.value, True),
        (SharePermissionLevel.ADMIN.value, True),
        (SharePermissionLevel.READ.value, False),
    ],
)
async def test_canonical_public_share_reports_its_own_level(
    client: AsyncClient, logged_in_headers, permission_level, expected_can_execute
):
    """A PRIVATE flow shared canonically is readable, and the share level bounds execution."""
    flow_id = await _create_flow(client, logged_in_headers, f"canonical-{permission_level}")
    await _add_public_share(flow_id, permission_level)

    client.cookies.clear()
    response = await client.get(f"api/v1/flows/public_flow/{flow_id}")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    # The legacy flag stays PRIVATE — the UI must not be re-deriving access from it.
    assert body["access_type"] == "PRIVATE"
    assert body["public_access"] == {"can_read": True, "can_execute": expected_can_execute}


async def test_legacy_public_flag_still_reports_full_capabilities(client: AsyncClient, logged_in_headers):
    """The documented compatibility grant is unchanged: legacy PUBLIC still runs."""
    flow_id = await _create_flow(client, logged_in_headers, "legacy-public")
    patch_response = await client.patch(
        f"api/v1/flows/{flow_id}", json={"access_type": "PUBLIC"}, headers=logged_in_headers
    )
    assert patch_response.status_code == status.HTTP_200_OK

    client.cookies.clear()
    response = await client.get(f"api/v1/flows/public_flow/{flow_id}")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["public_access"] == {"can_read": True, "can_execute": True}


async def test_read_share_bounds_a_still_public_legacy_flag(client: AsyncClient, logged_in_headers):
    """A canonical read share is authoritative — the legacy flag cannot widen it back to execute."""
    flow_id = await _create_flow(client, logged_in_headers, "read-share-bounds-legacy")
    patch_response = await client.patch(
        f"api/v1/flows/{flow_id}", json={"access_type": "PUBLIC"}, headers=logged_in_headers
    )
    assert patch_response.status_code == status.HTTP_200_OK
    await _add_public_share(flow_id, SharePermissionLevel.READ.value)

    client.cookies.clear()
    response = await client.get(f"api/v1/flows/public_flow/{flow_id}")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["public_access"] == {"can_read": True, "can_execute": False}


async def test_unshared_private_flow_is_still_not_found(client: AsyncClient, logged_in_headers):
    """No grant at all keeps the fail-closed 404 — capabilities never widen access."""
    flow_id = await _create_flow(client, logged_in_headers, "unshared-private")

    client.cookies.clear()
    response = await client.get(f"api/v1/flows/public_flow/{flow_id}")

    assert response.status_code == status.HTTP_404_NOT_FOUND
