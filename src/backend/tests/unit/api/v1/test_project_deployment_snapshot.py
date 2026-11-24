from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, Response, status
from langflow.api.v1 import projects
from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User
from langflow.services.deployment_artifacts import (
    EmptyProjectArtifactError,
    ProjectArtifactError,
    ProjectArtifactLimitError,
    ProjectArtifactNotFoundError,
)
from langflow.services.deps import session_scope
from langflow.services.variable.constants import CREDENTIAL_TYPE

if TYPE_CHECKING:
    from httpx import AsyncClient


def _flow_payload(project_id: str, *, endpoint_name: str) -> dict:
    """Build a flow exercising every field shape recently flagged in review.

    A load_from_db secret, a connection ref, an already-empty password field, a
    component ``code`` string with a ``#`` comment mentioning "password", and
    an MCP server whose config is already secret-free - exactly the shapes
    CodeRabbit/ogabrielluiz/HzaRashid flagged as being scrubbed or rejected
    incorrectly.
    """
    return {
        "name": "Triage",
        "description": "Route a request",
        "endpoint_name": endpoint_name,
        "folder_id": project_id,
        "is_component": False,
        "data": {
            "nodes": [
                {
                    "id": "node-1",
                    "data": {
                        "node": {
                            "template": {
                                "api_key": {
                                    "name": "api_key",
                                    "password": True,
                                    "load_from_db": True,
                                    "value": "MY_DEPLOY_API_KEY",
                                },
                                "connection": {
                                    "name": "connection",
                                    "type": "connection_ref",
                                    "provider": "google_workspace",
                                    "value": "google_workspace/work",
                                    "required_scopes": ["calendar.readonly"],
                                },
                                "code": {
                                    "name": "code",
                                    "type": "code",
                                    "value": (
                                        "# Enable global variable mode: single-line with password masking\n"
                                        "class Demo:\n    pass\n"
                                    ),
                                },
                                "mcp_server": {
                                    "name": "mcp_server",
                                    "type": "mcp",
                                    "value": {
                                        "name": "demo-mcp",
                                        "config": {
                                            "url": "https://mcp.example.com",
                                            "headers": {"Authorization": "MCP_DEMO_MCP_AUTHORIZATION_ABCD1234"},
                                        },
                                    },
                                },
                                "extra_secret": {
                                    "name": "extra_secret",
                                    "password": True,
                                    "value": "",
                                },
                            }
                        }
                    },
                }
            ],
            "edges": [],
        },
    }


async def _create_project(client: AsyncClient, headers: dict, *, name: str) -> str:
    response = await client.post(
        "api/v1/projects/",
        json={"name": name, "description": "", "flows_list": [], "components_list": []},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["id"]


async def _second_user_headers(client: AsyncClient, *, username: str) -> dict:
    async with session_scope() as session:
        other_user = User(
            username=username,
            password=get_password_hash("testpassword"),
            is_active=True,
            is_superuser=False,
        )
        session.add(other_user)
        await session.commit()

    login_data = {"username": username, "password": "testpassword"}  # pragma: allowlist secret
    response = await client.post("api/v1/login", data=login_data)
    assert response.status_code == status.HTTP_200_OK
    tokens = response.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.mark.asyncio
async def test_deployment_snapshot_owner_gets_full_snapshot(client: AsyncClient, logged_in_headers) -> None:
    """The owner's snapshot must carry the identity, secrets-safe fields the CP needs to rebuild a deploy."""
    # The snapshot only keeps a load_from_db reference that names one of the
    # owner's real global variables (LE-2717 review: a name-shaped literal
    # behind a stale load_from_db flag must not survive capture) - create it
    # so the api_key field below is a legitimate reference, not a false one.
    variable_resp = await client.post(
        "api/v1/variables/",
        json={"name": "MY_DEPLOY_API_KEY", "value": "does-not-matter", "type": CREDENTIAL_TYPE, "default_fields": []},
        headers=logged_in_headers,
    )
    assert variable_resp.status_code == status.HTTP_201_CREATED, variable_resp.text
    # Same requirement for the MCP config's header reference below: a bare
    # MCP_* value is only kept once it names one of the owner's real global
    # variables (LE-2717 review: _mcp_config_is_clean must not accept any
    # MCP_*-shaped value without checking it against known_variable_names).
    mcp_variable_resp = await client.post(
        "api/v1/variables/",
        json={
            "name": "MCP_DEMO_MCP_AUTHORIZATION_ABCD1234",
            "value": "does-not-matter",
            "type": CREDENTIAL_TYPE,
            "default_fields": [],
        },
        headers=logged_in_headers,
    )
    assert mcp_variable_resp.status_code == status.HTTP_201_CREATED, mcp_variable_resp.text

    project_id = await _create_project(client, logged_in_headers, name="support-automation")
    flow_payload = _flow_payload(project_id, endpoint_name=f"triage-{uuid4().hex[:8]}")
    flow_resp = await client.post("api/v1/flows/", json=flow_payload, headers=logged_in_headers)
    assert flow_resp.status_code == status.HTTP_201_CREATED, flow_resp.text
    flow_id = flow_resp.json()["id"]

    response = await client.get(f"api/v1/projects/{project_id}/deployment-snapshot", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.headers["cache-control"] == "no-store"
    body = response.json()

    assert body["project"]["id"] == project_id
    assert body["project"]["name"] == "support-automation"

    assert len(body["flows"]) == 1
    flow = body["flows"][0]
    assert flow["id"] == flow_id
    assert flow["name"] == "Triage"
    assert flow["endpoint_name"] == flow_payload["endpoint_name"]
    assert flow["description"] == "Route a request"

    template = flow["data"]["nodes"][0]["data"]["node"]["template"]
    # load_from_db secret: kept as the variable NAME, never the literal, and
    # surfaced in required_variables so the deploy target can provision it.
    assert template["api_key"]["value"] == "MY_DEPLOY_API_KEY"
    assert body["required_variables"] == ["MY_DEPLOY_API_KEY"]
    # connection_ref: kept and normalized, and rolled up into required_connections.
    assert template["connection"]["value"] == "google_workspace/work"
    assert body["required_connections"] == [
        {"provider": "google_workspace", "name": "work", "scopes": ["calendar.readonly"]}
    ]
    # A `#` comment mentioning "password" in component code must survive untouched
    # (regression for the _contains_url_credentials false positive).
    assert "password masking" in template["code"]["value"]
    # An MCP config that was already secret-free at save time is kept, not
    # collapsed down to {"name": ...}.
    assert template["mcp_server"]["value"] == {
        "name": "demo-mcp",
        "config": {
            "url": "https://mcp.example.com",
            "headers": {"Authorization": "MCP_DEMO_MCP_AUTHORIZATION_ABCD1234"},
        },
    }
    # An already-empty password field must not trip the strict-capture guard.
    assert template["extra_secret"]["value"] == ""


@pytest.mark.asyncio
async def test_deployment_snapshot_round_trips_exposure_fields_through_replacement(
    client: AsyncClient, logged_in_headers
) -> None:
    """A rollback (PUT only applies sent fields) or restore-after-delete must not drift them.

    Captures a snapshot with non-default values for every FlowCreate exposure/
    presentation field the snapshot now carries, mutates the persisted flow
    away from those values (as a delete+restore or a partial rollback would
    leave it), replays the snapshot's own flows through PUT
    /replacement-operations, and checks a second snapshot matches the first.
    """
    project_id = await _create_project(client, logged_in_headers, name="exposure-fields")
    flow_payload = {
        "name": "Exposure",
        "description": "Carries every exposure field",
        "endpoint_name": f"exposure-{uuid4().hex[:8]}",
        "folder_id": project_id,
        "data": {"nodes": [], "edges": []},
        "is_component": True,
        "locked": True,
        "mcp_enabled": True,
        "action_name": "custom_action",
        "action_description": "A custom action description",
        "access_type": "PUBLIC",
        "flow_type": "agent",
        "a2a_enabled": True,
        "a2a_card_overrides": {"skillDescription": "custom skill"},
        "tags": ["alpha", "beta"],
        "icon": "bot",
        "icon_bg_color": "#123456",
        "gradient": "3",
    }
    flow_resp = await client.post("api/v1/flows/", json=flow_payload, headers=logged_in_headers)
    assert flow_resp.status_code == status.HTTP_201_CREATED, flow_resp.text
    flow_id = flow_resp.json()["id"]

    first = await client.get(f"api/v1/projects/{project_id}/deployment-snapshot", headers=logged_in_headers)
    assert first.status_code == status.HTTP_200_OK, first.text
    first_body = first.json()
    snapshot_flow = first_body["flows"][0]
    for field, expected in flow_payload.items():
        if field in ("folder_id", "endpoint_name", "name", "description", "data"):
            continue
        assert snapshot_flow[field] == expected, field

    # Directly mutate the persisted flow away from the captured values - what
    # a delete+restore or a partial rollback would otherwise leave behind.
    # The flow is unlocked here too, since a locked flow's content is
    # immutable except for an identical-content request (see
    # ensure_flow_update_allowed); replaying the snapshot's own locked=True
    # value below is then a legitimate re-lock, not a locked-content edit.
    async with session_scope() as session:
        stored_flow = await session.get(Flow, UUID(flow_id))
        stored_flow.is_component = False
        stored_flow.locked = False
        stored_flow.mcp_enabled = False
        stored_flow.action_name = None
        stored_flow.action_description = None
        stored_flow.access_type = "PRIVATE"
        stored_flow.flow_type = "workflow"
        stored_flow.a2a_enabled = False
        stored_flow.a2a_card_overrides = None
        stored_flow.tags = []
        stored_flow.icon = None
        stored_flow.icon_bg_color = None
        stored_flow.gradient = None
        session.add(stored_flow)
        await session.commit()

    drifted = await client.get(f"api/v1/projects/{project_id}/deployment-snapshot", headers=logged_in_headers)
    assert drifted.status_code == status.HTTP_200_OK, drifted.text
    assert drifted.json()["flows"][0]["access_type"] == "PRIVATE"
    assert drifted.json()["flows"][0]["flow_type"] == "workflow"
    assert drifted.json()["flows"][0]["locked"] is False

    restore = await client.put(
        f"api/v1/projects/{project_id}/replacement-operations/{uuid4()}",
        json={"description": first_body["project"]["description"], "flows": first_body["flows"]},
        headers=logged_in_headers,
    )
    assert restore.status_code == status.HTTP_200_OK, restore.text

    second = await client.get(f"api/v1/projects/{project_id}/deployment-snapshot", headers=logged_in_headers)
    assert second.status_code == status.HTTP_200_OK, second.text
    assert second.json() == first_body


@pytest.mark.asyncio
async def test_deployment_snapshot_another_user_gets_404(client: AsyncClient, logged_in_headers) -> None:
    """A project the caller does not own must read as not-found, not forbidden."""
    project_id = await _create_project(client, logged_in_headers, name="owner-only-project")
    other_headers = await _second_user_headers(client, username=f"other_snapshot_user_{uuid4().hex[:8]}")

    response = await client.get(f"api/v1/projects/{project_id}/deployment-snapshot", headers=other_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Project not found"


@pytest.mark.asyncio
async def test_deployment_snapshot_refuses_unsafe_literal_secret(client: AsyncClient, logged_in_headers) -> None:
    """A real, non-referenced secret must fail the capture closed rather than leak."""
    project_id = await _create_project(client, logged_in_headers, name="unsafe-secret-project")
    secret = "literal-secret-must-not-escape"  # noqa: S105  # pragma: allowlist secret
    flow_payload = {
        "name": "Has Raw Secret",
        "folder_id": project_id,
        "is_component": False,
        "data": {
            "nodes": [
                {
                    "id": "node-1",
                    "data": {
                        "node": {
                            "template": {
                                "password": {"name": "password", "password": True, "value": secret},
                            }
                        }
                    },
                }
            ],
            "edges": [],
        },
    }
    flow_resp = await client.post("api/v1/flows/", json=flow_payload, headers=logged_in_headers)
    assert flow_resp.status_code == status.HTTP_201_CREATED, flow_resp.text

    response = await client.get(f"api/v1/projects/{project_id}/deployment-snapshot", headers=logged_in_headers)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["detail"] == "Project snapshot could not be captured safely"
    assert secret not in response.text


@pytest.mark.asyncio
async def test_deployment_snapshot_refuses_load_from_db_naming_unknown_variable(
    client: AsyncClient, logged_in_headers
) -> None:
    """A load_from_db value that does not name one of the owner's real variables must fail closed.

    A stale ``load_from_db`` flag left on a field that actually holds a literal
    secret is shaped exactly like a legitimate variable-name reference. Without
    checking the name against the owner's real variables, that literal would be
    captured (and required_variables would advertise a variable that does not
    exist) instead of failing the capture.
    """
    project_id = await _create_project(client, logged_in_headers, name="unknown-variable-project")
    secret = "looks-like-a-var-name-but-is-a-secret"  # noqa: S105  # pragma: allowlist secret
    flow_payload = {
        "name": "Stale Load From DB Flag",
        "folder_id": project_id,
        "is_component": False,
        "data": {
            "nodes": [
                {
                    "id": "node-1",
                    "data": {
                        "node": {
                            "template": {
                                "api_key": {
                                    "name": "api_key",
                                    "password": True,
                                    "load_from_db": True,
                                    "value": secret,
                                },
                            }
                        }
                    },
                }
            ],
            "edges": [],
        },
    }
    flow_resp = await client.post("api/v1/flows/", json=flow_payload, headers=logged_in_headers)
    assert flow_resp.status_code == status.HTTP_201_CREATED, flow_resp.text

    response = await client.get(f"api/v1/projects/{project_id}/deployment-snapshot", headers=logged_in_headers)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["detail"] == "Project snapshot could not be captured safely"
    assert secret not in response.text


@pytest.mark.asyncio
async def test_deployment_snapshot_load_from_db_naming_known_variable_is_captured(
    client: AsyncClient, logged_in_headers
) -> None:
    """A load_from_db value naming a real owner variable is kept and listed as required."""
    variable_resp = await client.post(
        "api/v1/variables/",
        json={
            "name": "KNOWN_DEPLOY_VARIABLE",
            "value": "does-not-matter",
            "type": CREDENTIAL_TYPE,
            "default_fields": [],
        },
        headers=logged_in_headers,
    )
    assert variable_resp.status_code == status.HTTP_201_CREATED, variable_resp.text

    project_id = await _create_project(client, logged_in_headers, name="known-variable-project")
    flow_payload = {
        "name": "Known Load From DB Reference",
        "folder_id": project_id,
        "is_component": False,
        "data": {
            "nodes": [
                {
                    "id": "node-1",
                    "data": {
                        "node": {
                            "template": {
                                "api_key": {
                                    "name": "api_key",
                                    "password": True,
                                    "load_from_db": True,
                                    "value": "KNOWN_DEPLOY_VARIABLE",
                                },
                            }
                        }
                    },
                }
            ],
            "edges": [],
        },
    }
    flow_resp = await client.post("api/v1/flows/", json=flow_payload, headers=logged_in_headers)
    assert flow_resp.status_code == status.HTTP_201_CREATED, flow_resp.text

    response = await client.get(f"api/v1/projects/{project_id}/deployment-snapshot", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK, response.text
    body = response.json()
    assert body["required_variables"] == ["KNOWN_DEPLOY_VARIABLE"]
    template = body["flows"][0]["data"]["nodes"][0]["data"]["node"]["template"]
    assert template["api_key"]["value"] == "KNOWN_DEPLOY_VARIABLE"


def _mcp_flow_payload(project_id: str, *, reference: str) -> dict:
    return {
        "name": "MCP Header Reference",
        "folder_id": project_id,
        "is_component": False,
        "data": {
            "nodes": [
                {
                    "id": "node-1",
                    "data": {
                        "node": {
                            "template": {
                                "mcp_server": {
                                    "name": "mcp_server",
                                    "type": "mcp",
                                    "value": {
                                        "name": "demo-mcp",
                                        "config": {
                                            "url": "https://mcp.example.com",
                                            "headers": {"Authorization": reference},
                                        },
                                    },
                                },
                            }
                        }
                    },
                }
            ],
            "edges": [],
        },
    }


@pytest.mark.asyncio
async def test_deployment_snapshot_refuses_mcp_config_naming_unknown_variable(
    client: AsyncClient, logged_in_headers
) -> None:
    """An MCP header value that does not name one of the owner's real variables must fail closed.

    ``_mcp_config_is_clean`` used to accept any ``MCP_*``-shaped header value as
    provably clean without checking it against the owner's real global
    variables, letting a literal secret that merely looks like one of these
    generated reference names escape a strict snapshot (LE-2717 review).
    """
    project_id = await _create_project(client, logged_in_headers, name="mcp-unknown-variable-project")
    flow_payload = _mcp_flow_payload(project_id, reference="MCP_RAW_LITERAL_SECRET")
    flow_resp = await client.post("api/v1/flows/", json=flow_payload, headers=logged_in_headers)
    assert flow_resp.status_code == status.HTTP_201_CREATED, flow_resp.text

    response = await client.get(f"api/v1/projects/{project_id}/deployment-snapshot", headers=logged_in_headers)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["detail"] == "Project snapshot could not be captured safely"
    assert "MCP_RAW_LITERAL_SECRET" not in response.text


@pytest.mark.asyncio
async def test_deployment_snapshot_mcp_config_naming_known_variable_is_captured(
    client: AsyncClient, logged_in_headers
) -> None:
    """The same MCP header reference is kept once it names a real owner variable."""
    variable_resp = await client.post(
        "api/v1/variables/",
        json={
            "name": "MCP_KNOWN_DEPLOY_VARIABLE",
            "value": "does-not-matter",
            "type": CREDENTIAL_TYPE,
            "default_fields": [],
        },
        headers=logged_in_headers,
    )
    assert variable_resp.status_code == status.HTTP_201_CREATED, variable_resp.text

    project_id = await _create_project(client, logged_in_headers, name="mcp-known-variable-project")
    flow_payload = _mcp_flow_payload(project_id, reference="MCP_KNOWN_DEPLOY_VARIABLE")
    flow_resp = await client.post("api/v1/flows/", json=flow_payload, headers=logged_in_headers)
    assert flow_resp.status_code == status.HTTP_201_CREATED, flow_resp.text

    response = await client.get(f"api/v1/projects/{project_id}/deployment-snapshot", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK, response.text
    template = response.json()["flows"][0]["data"]["nodes"][0]["data"]["node"]["template"]
    assert template["mcp_server"]["value"] == {
        "name": "demo-mcp",
        "config": {
            "url": "https://mcp.example.com",
            "headers": {"Authorization": "MCP_KNOWN_DEPLOY_VARIABLE"},
        },
    }


@pytest.mark.asyncio
async def test_snapshot_route_masks_auth_denial_and_does_not_expose_capture_details() -> None:
    session = AsyncMock()
    response = Response()
    secret = "literal-secret-must-not-escape"  # noqa: S105  # pragma: allowlist secret

    with (
        patch.object(projects, "_begin_deployment_snapshot_transaction", new_callable=AsyncMock),
        patch.object(
            projects,
            "build_project_deployment_snapshot",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=secret),
        ),
        pytest.raises(HTTPException) as raised,
    ):
        await projects.read_project_deployment_snapshot(
            session=session,
            project_id=uuid4(),
            current_user=SimpleNamespace(id=uuid4()),
            response=response,
        )

    assert raised.value.status_code == status.HTTP_404_NOT_FOUND
    assert raised.value.detail == "Project not found"
    assert secret not in str(raised.value.detail)
    assert raised.value.headers.get("X-Langflow-Error-Code") == "snapshot_project_not_found"
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_snapshot_route_masks_generic_capture_error_detail() -> None:
    session = AsyncMock()
    response = Response()
    secret = "literal-secret-must-not-escape"  # noqa: S105  # pragma: allowlist secret

    with (
        patch.object(projects, "_begin_deployment_snapshot_transaction", new_callable=AsyncMock),
        patch.object(
            projects,
            "build_project_deployment_snapshot",
            new_callable=AsyncMock,
            side_effect=ProjectArtifactError(secret),
        ),
        pytest.raises(HTTPException) as raised,
    ):
        await projects.read_project_deployment_snapshot(
            session=session,
            project_id=uuid4(),
            current_user=SimpleNamespace(id=uuid4()),
            response=response,
        )

    assert raised.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert raised.value.detail == "Project snapshot could not be captured safely"
    assert secret not in str(raised.value.detail)
    assert raised.value.headers.get("X-Langflow-Error-Code") == "snapshot_unsafe"
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "expected_status", "expected_code"),
    [
        (ProjectArtifactLimitError("snapshot too large"), status.HTTP_413_CONTENT_TOO_LARGE, "snapshot_too_large"),
        (ProjectArtifactNotFoundError("Project not found"), status.HTTP_404_NOT_FOUND, "snapshot_project_not_found"),
        (EmptyProjectArtifactError("project has no flows"), status.HTTP_422_UNPROCESSABLE_CONTENT, "snapshot_empty"),
    ],
)
async def test_snapshot_route_maps_bounded_capture_failures(failure, expected_status, expected_code) -> None:
    session = AsyncMock()
    response = Response()

    with (
        patch.object(projects, "_begin_deployment_snapshot_transaction", new_callable=AsyncMock),
        patch.object(projects, "build_project_deployment_snapshot", new_callable=AsyncMock, side_effect=failure),
        pytest.raises(HTTPException) as raised,
    ):
        await projects.read_project_deployment_snapshot(
            session=session,
            project_id=uuid4(),
            current_user=SimpleNamespace(id=uuid4()),
            response=response,
        )

    assert raised.value.status_code == expected_status
    assert raised.value.headers.get("X-Langflow-Error-Code") == expected_code
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_snapshot_transaction_starts_before_first_sqlite_read() -> None:
    session = MagicMock()
    session.execute = AsyncMock()
    session.rollback = AsyncMock()
    session.begin = AsyncMock()
    session.in_transaction.return_value = False
    session.get_bind.return_value = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

    await projects._begin_deployment_snapshot_transaction(session)

    session.execute.assert_awaited_once()
    assert str(session.execute.await_args.args[0]) == "BEGIN"


@pytest.mark.asyncio
async def test_snapshot_transaction_uses_repeatable_read_only_postgres() -> None:
    session = MagicMock()
    session.execute = AsyncMock()
    session.rollback = AsyncMock()
    session.begin = AsyncMock()
    session.in_transaction.return_value = False
    session.get_bind.return_value = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    await projects._begin_deployment_snapshot_transaction(session)

    session.execute.assert_awaited_once()
    assert str(session.execute.await_args.args[0]) == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
