"""A deployment policy must be consulted wherever an API key is minted.

Keys are not only minted by ``POST /api/v1/api_key/``. Project MCP
registration mints one implicitly, on a path where the caller never asked for a
key and never learns one was created, so a policy attached to the public route
alone leaves that door open. These tests pin the check at the one function all
of those paths go through.
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from langflow.services.database.models.api_key.crud import create_api_key
from langflow.services.database.models.api_key.model import ApiKeyCreate
from langflow.services.database.models.api_key.policy import (
    ApiKeyIssuanceDeniedError,
    check_api_key_issuance,
    get_api_key_issuance_policy,
    set_api_key_issuance_policy,
)


@pytest.fixture(autouse=True)
def _restore_policy():
    """A policy is process-wide; never let one leak into another test."""
    previous = get_api_key_issuance_policy()
    yield
    set_api_key_issuance_policy(previous)


async def test_no_policy_means_no_restriction():
    """Stock Langflow has no sign-in policy and must be unaffected."""
    set_api_key_issuance_policy(None)

    await check_api_key_issuance(AsyncMock(), uuid4())


async def test_the_policy_sees_the_session_and_the_owner():
    """A policy decides per account, so it needs to be told which one."""
    policy = AsyncMock()
    set_api_key_issuance_policy(policy)
    session, user_id = AsyncMock(), uuid4()

    await check_api_key_issuance(session, user_id)

    policy.assert_awaited_once_with(session, user_id)


async def test_a_refusal_is_a_permission_error():
    """Callers that already map PermissionError to 403 keep working unchanged."""
    assert issubclass(ApiKeyIssuanceDeniedError, PermissionError)


async def test_create_api_key_asks_the_policy_before_staging_anything(client, logged_in_headers):  # noqa: ARG001
    """A refusal must leave the caller's transaction exactly as it found it."""
    denied = AsyncMock(side_effect=ApiKeyIssuanceDeniedError("no sign-in source"))
    set_api_key_issuance_policy(denied)
    session = AsyncMock()

    with pytest.raises(ApiKeyIssuanceDeniedError):
        await create_api_key(session, ApiKeyCreate(name="refused"), uuid4())

    session.add.assert_not_called()
    session.flush.assert_not_awaited()


async def test_the_public_route_answers_a_refusal_with_403(client, logged_in_headers):
    """The route already maps PermissionError to 403; the refusal reuses it."""
    set_api_key_issuance_policy(AsyncMock(side_effect=ApiKeyIssuanceDeniedError("no sign-in source")))

    response = await client.post("api/v1/api_key/", json={"name": "refused"}, headers=logged_in_headers)

    assert response.status_code == 403
    assert "no sign-in source" in response.json()["detail"]


async def test_a_refusal_is_not_swallowed_as_a_registration_failure():
    """The MCP helper drops transient failures; a refusal is a decision.

    Returning False here would report a project as registered while its server
    was never configured, or leave a project on its old auth with nothing said.
    """
    from langflow.api.v1.projects_mcp_helpers import register_mcp_servers_for_project

    set_api_key_issuance_policy(AsyncMock(side_effect=ApiKeyIssuanceDeniedError("no sign-in source")))
    project = type("Project", (), {"id": uuid4(), "name": "Denied"})()

    with (
        patch("langflow.api.v1.projects_mcp_helpers.get_storage_service", lambda: None),
        patch("langflow.api.v1.projects_mcp_helpers.get_settings_service", lambda: None),
        patch(
            "langflow.api.v1.projects_mcp_helpers.get_project_streamable_http_url",
            AsyncMock(return_value="http://localhost:7860/api/v1/mcp/project/x/streamable"),
        ),
        patch(
            "langflow.api.v1.projects_mcp_helpers.validate_mcp_server_for_project",
            AsyncMock(
                return_value=type(
                    "Result",
                    (),
                    {
                        "has_conflict": False,
                        "conflict_message": None,
                        "should_skip": False,
                        "existing_config": None,
                        "server_name": "denied",
                    },
                )()
            ),
        ),
        pytest.raises(ApiKeyIssuanceDeniedError),
    ):
        await register_mcp_servers_for_project(
            project,
            {"auth_type": "apikey"},
            type("User", (), {"id": uuid4()})(),
            AsyncMock(),
        )
