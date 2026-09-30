from uuid import uuid4

import pytest
from httpx import AsyncClient
from langflow.services.auth.utils import get_auth_service
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.database.models.vertex_builds.crud import log_vertex_build
from langflow.services.database.models.vertex_builds.model import VertexBuildBase
from langflow.services.deps import session_scope


@pytest.fixture
async def other_active_user(client):  # noqa: ARG001
    username = f"other-monitor-user-{uuid4().hex[:8]}"
    async with session_scope() as session:
        user = User(
            username=username,
            password=get_auth_service().get_password_hash("testpassword"),
            is_active=True,
            is_superuser=False,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        user = UserRead.model_validate(user, from_attributes=True)

    yield user

    async with session_scope() as session:
        db_user = await session.get(User, user.id)
        if db_user:
            await session.delete(db_user)


@pytest.fixture
async def other_logged_in_headers(client: AsyncClient, other_active_user):
    login_data = {"username": other_active_user.username, "password": "testpassword"}
    response = await client.post("api/v1/login", data=login_data)
    assert response.status_code == 200
    tokens = response.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
async def cross_user_monitor_data(active_user, other_active_user):
    async with session_scope() as session:
        owned_flow = Flow(name=f"owned-flow-{uuid4().hex[:8]}", user_id=active_user.id, data={"nodes": [], "edges": []})
        foreign_flow = Flow(
            name=f"foreign-flow-{uuid4().hex[:8]}",
            user_id=other_active_user.id,
            data={"nodes": [], "edges": []},
        )
        session.add(owned_flow)
        session.add(foreign_flow)
        await session.flush()

        owned_tx = TransactionTable(
            vertex_id="owned-vertex",
            inputs={"in": "owned"},
            outputs={"out": "owned"},
            status="success",
            flow_id=owned_flow.id,
        )
        foreign_tx = TransactionTable(
            vertex_id="foreign-vertex",
            inputs={"in": "foreign"},
            outputs={"out": "foreign"},
            status="success",
            flow_id=foreign_flow.id,
        )
        session.add(owned_tx)
        session.add(foreign_tx)

        await log_vertex_build(
            session,
            VertexBuildBase(
                id="owned-vertex",
                flow_id=owned_flow.id,
                valid=True,
                params="{}",
                data={"kind": "owned"},
                artifacts={},
            ),
        )
        await log_vertex_build(
            session,
            VertexBuildBase(
                id="foreign-vertex",
                flow_id=foreign_flow.id,
                valid=True,
                params="{}",
                data={"kind": "foreign"},
                artifacts={},
            ),
        )

        await session.flush()

        return {
            "owned_flow_id": str(owned_flow.id),
            "foreign_flow_id": str(foreign_flow.id),
        }


@pytest.mark.api_key_required
async def test_get_monitor_builds_does_not_return_other_users_data(
    client: AsyncClient,
    logged_in_headers,
    other_logged_in_headers,
    cross_user_monitor_data,
):
    own_response = await client.get(
        "api/v1/monitor/builds",
        params={"flow_id": cross_user_monitor_data["owned_flow_id"]},
        headers=logged_in_headers,
    )
    assert own_response.status_code == 200, own_response.text
    assert own_response.json()["vertex_builds"]

    foreign_response = await client.get(
        "api/v1/monitor/builds",
        params={"flow_id": cross_user_monitor_data["foreign_flow_id"]},
        headers=logged_in_headers,
    )
    assert foreign_response.status_code == 200, foreign_response.text
    assert foreign_response.json() == {"vertex_builds": {}}

    owner_response = await client.get(
        "api/v1/monitor/builds",
        params={"flow_id": cross_user_monitor_data["foreign_flow_id"]},
        headers=other_logged_in_headers,
    )
    assert owner_response.status_code == 200, owner_response.text
    assert owner_response.json()["vertex_builds"]


@pytest.mark.api_key_required
async def test_delete_monitor_builds_cannot_delete_other_users_data(
    client: AsyncClient,
    logged_in_headers,
    other_logged_in_headers,
    cross_user_monitor_data,
):
    delete_response = await client.delete(
        "api/v1/monitor/builds",
        params={"flow_id": cross_user_monitor_data["foreign_flow_id"]},
        headers=logged_in_headers,
    )
    assert delete_response.status_code == 204, delete_response.text

    owner_response = await client.get(
        "api/v1/monitor/builds",
        params={"flow_id": cross_user_monitor_data["foreign_flow_id"]},
        headers=other_logged_in_headers,
    )
    assert owner_response.status_code == 200, owner_response.text
    assert owner_response.json()["vertex_builds"]


@pytest.mark.api_key_required
async def test_get_monitor_transactions_does_not_return_other_users_data(
    client: AsyncClient,
    logged_in_headers,
    other_logged_in_headers,
    cross_user_monitor_data,
):
    own_response = await client.get(
        "api/v1/monitor/transactions",
        params={"flow_id": cross_user_monitor_data["owned_flow_id"]},
        headers=logged_in_headers,
    )
    assert own_response.status_code == 200, own_response.text
    assert len(own_response.json()["items"]) == 1

    foreign_response = await client.get(
        "api/v1/monitor/transactions",
        params={"flow_id": cross_user_monitor_data["foreign_flow_id"]},
        headers=logged_in_headers,
    )
    assert foreign_response.status_code == 200, foreign_response.text
    assert foreign_response.json()["items"] == []
    assert foreign_response.json()["total"] == 0

    owner_response = await client.get(
        "api/v1/monitor/transactions",
        params={"flow_id": cross_user_monitor_data["foreign_flow_id"]},
        headers=other_logged_in_headers,
    )
    assert owner_response.status_code == 200, owner_response.text
    assert len(owner_response.json()["items"]) == 1
