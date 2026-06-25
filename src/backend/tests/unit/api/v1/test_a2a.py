"""Integration tests for the F2 A2A agent-card discovery endpoint.

The route is public and gated behind LANGFLOW_A2A_ENABLED (default off). These
tests drive the real endpoint against the test DB: flows and folders are created
directly via session_scope, the server flag is toggled on the live settings
object, and the served card is revalidated against the a2a-sdk model.
"""

import uuid
from pathlib import Path

import langflow
import orjson
import pytest
from a2a.compat.v0_3 import types as a2a_types
from httpx import AsyncClient
from langflow.helpers.flow import json_schema_from_flow
from langflow.services.database.models import Folder
from langflow.services.database.models.flow.model import Flow, FlowType
from langflow.services.deps import session_scope
from lfx.services.deps import get_settings_service

_STARTERS = Path(langflow.__file__).parent / "initial_setup" / "starter_projects"


def _card_url(flow_id) -> str:
    return f"api/v1/a2a/{flow_id}/.well-known/agent-card.json"


async def _create_flow(
    user_id,
    *,
    data,
    flow_type=FlowType.AGENT,
    a2a_enabled=True,
    folder_id=None,
    overrides=None,
):
    async with session_scope() as session:
        flow = Flow(
            name=f"a2a-flow-{uuid.uuid4().hex[:8]}",
            data=data,
            user_id=user_id,
            flow_type=flow_type,
            a2a_enabled=a2a_enabled,
            folder_id=folder_id,
            a2a_card_overrides=overrides,
        )
        session.add(flow)
        await session.commit()
        await session.refresh(flow)
        return flow.id


async def _create_folder(user_id, *, auth_settings):
    async with session_scope() as session:
        folder = Folder(
            name=f"a2a-folder-{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            auth_settings=auth_settings,
        )
        session.add(folder)
        await session.commit()
        await session.refresh(folder)
        return folder.id


@pytest.fixture
def a2a_flag_on(client):  # noqa: ARG001 - client ensures settings are built first
    """Turn the server A2A flag on for the duration of a test, then restore."""
    settings = get_settings_service().settings
    original = settings.a2a_enabled
    settings.a2a_enabled = True
    yield
    settings.a2a_enabled = original


@pytest.fixture
def flow_data():
    """Real, current-format agent flow data (has an input node for the skill schema)."""
    return orjson.loads((_STARTERS / "Simple Agent.json").read_bytes())["data"]


@pytest.mark.usefixtures("a2a_flag_on")
async def test_get_agent_card_returns_valid_card(client: AsyncClient, active_user, flow_data):
    """An agent-typed, a2a_enabled flow serves a spec-valid card carrying the flow schema."""
    flow_id = await _create_flow(active_user.id, data=flow_data)

    response = await client.get(_card_url(flow_id))

    assert response.status_code == 200
    body = response.json()
    assert body["url"].endswith(f"/api/v1/a2a/{flow_id}/jsonrpc")
    assert body["protocolVersion"] == "0.3.0"
    assert body["preferredTransport"] == "JSONRPC"

    # The card (minus the non-model inputSchema key) revalidates against the SDK model.
    skill = {k: v for k, v in body["skills"][0].items() if k != "inputSchema"}
    a2a_types.AgentCard.model_validate({**body, "skills": [skill]})

    input_schema = body["skills"][0]["inputSchema"]
    assert input_schema["type"] == "object"
    assert input_schema["properties"]["session_id"]["type"] == "string"

    # The published schema matches what json_schema_from_flow computes directly.
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        assert input_schema == json_schema_from_flow(flow)


@pytest.mark.usefixtures("a2a_flag_on")
async def test_capabilities_advertised_false(client: AsyncClient, active_user, flow_data):
    """Streaming and pushNotifications must be present and explicitly false."""
    flow_id = await _create_flow(active_user.id, data=flow_data)

    body = (await client.get(_card_url(flow_id))).json()

    assert body["capabilities"] == {"streaming": False, "pushNotifications": False}


@pytest.mark.usefixtures("a2a_flag_on")
async def test_workflow_flow_returns_404(client: AsyncClient, active_user, flow_data):
    """A workflow-typed flow is not an agent, so the card 404s even with a2a_enabled."""
    flow_id = await _create_flow(active_user.id, data=flow_data, flow_type=FlowType.WORKFLOW)

    response = await client.get(_card_url(flow_id))

    assert response.status_code == 404


@pytest.mark.usefixtures("a2a_flag_on")
async def test_agent_flow_a2a_disabled_returns_404(client: AsyncClient, active_user, flow_data):
    """An agent flow with a2a_enabled=False 404s."""
    flow_id = await _create_flow(active_user.id, data=flow_data, a2a_enabled=False)

    response = await client.get(_card_url(flow_id))

    assert response.status_code == 404


@pytest.mark.usefixtures("a2a_flag_on")
async def test_agent_flow_a2a_none_returns_404(client: AsyncClient, active_user, flow_data):
    """An agent flow with a2a_enabled=None 404s (covers the bool|None branch)."""
    flow_id = await _create_flow(active_user.id, data=flow_data, a2a_enabled=None)

    response = await client.get(_card_url(flow_id))

    assert response.status_code == 404


@pytest.mark.usefixtures("a2a_flag_on")
async def test_missing_flow_returns_404(client: AsyncClient):
    """A random flow id 404s."""
    response = await client.get(_card_url(uuid.uuid4()))

    assert response.status_code == 404


async def test_flag_off_returns_404(client: AsyncClient, active_user, flow_data):
    """A valid agent+enabled flow 404s when the server flag is off (no a2a_flag_on)."""
    flow_id = await _create_flow(active_user.id, data=flow_data)

    response = await client.get(_card_url(flow_id))

    assert response.status_code == 404


@pytest.mark.usefixtures("a2a_flag_on")
async def test_card_overrides_merged(client: AsyncClient, active_user, flow_data):
    """a2a_card_overrides override the editable bits of the card."""
    overrides = {"name": "Custom Agent", "description": "Custom desc", "version": "9.9.9", "tags": ["x", "y"]}
    flow_id = await _create_flow(active_user.id, data=flow_data, overrides=overrides)

    body = (await client.get(_card_url(flow_id))).json()

    assert body["name"] == "Custom Agent"
    assert body["description"] == "Custom desc"
    assert body["version"] == "9.9.9"
    assert body["skills"][0]["name"] == "Custom Agent"
    assert body["skills"][0]["tags"] == ["x", "y"]


@pytest.mark.usefixtures("a2a_flag_on")
async def test_defaults_when_no_overrides(client: AsyncClient, active_user, flow_data):
    """Without overrides the card falls back to the flow name and the langflow version."""
    from langflow.utils.version import get_version_info

    flow_id = await _create_flow(active_user.id, data=flow_data)

    body = (await client.get(_card_url(flow_id))).json()

    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        assert body["name"] == flow.name
    assert body["version"] == get_version_info()["version"]
    assert body["skills"][0]["tags"] == ["langflow"]


@pytest.mark.usefixtures("a2a_flag_on")
async def test_security_schemes_apikey(client: AsyncClient, active_user, flow_data):
    """A folder with apikey auth reflects an x-api-key security scheme onto the card."""
    folder_id = await _create_folder(active_user.id, auth_settings={"auth_type": "apikey"})
    flow_id = await _create_flow(active_user.id, data=flow_data, folder_id=folder_id)

    body = (await client.get(_card_url(flow_id))).json()

    assert body["securitySchemes"] == {
        "apiKey": {
            "type": "apiKey",
            "in": "header",
            "name": "x-api-key",
            "description": "API key passed in the x-api-key header.",
        }
    }
    assert body["security"] == [{"apiKey": []}]


@pytest.mark.usefixtures("a2a_flag_on")
async def test_no_security_for_oauth_folder(client: AsyncClient, active_user, flow_data):
    """OAuth is out of F2 scope, so no security is advertised."""
    folder_id = await _create_folder(active_user.id, auth_settings={"auth_type": "oauth"})
    flow_id = await _create_flow(active_user.id, data=flow_data, folder_id=folder_id)

    body = (await client.get(_card_url(flow_id))).json()

    assert "securitySchemes" not in body
    assert "security" not in body


@pytest.mark.usefixtures("a2a_flag_on")
async def test_no_security_for_folderless_flow(client: AsyncClient, active_user, flow_data):
    """A flow without a folder advertises no security."""
    flow_id = await _create_flow(active_user.id, data=flow_data, folder_id=None)

    body = (await client.get(_card_url(flow_id))).json()

    assert "securitySchemes" not in body
    assert "security" not in body


@pytest.mark.usefixtures("a2a_flag_on")
async def test_unbuildable_flow_serves_empty_input_schema(client: AsyncClient, active_user):
    """An agent flow with empty/unbuildable data serves a valid card with an empty input schema, not a 500."""
    flow_id = await _create_flow(active_user.id, data={})

    response = await client.get(_card_url(flow_id))

    assert response.status_code == 200
    body = response.json()
    assert body["skills"][0]["inputSchema"] == {"type": "object", "properties": {}, "required": []}


@pytest.mark.usefixtures("a2a_flag_on")
async def test_malformed_overrides_fall_back_to_defaults(client: AsyncClient, active_user, flow_data):
    """Wrong-typed override values are ignored (no 500); the card falls back to defaults."""
    from langflow.utils.version import get_version_info

    overrides = {"name": 123, "version": 9, "tags": "billing", "examples": [1, 2]}
    flow_id = await _create_flow(active_user.id, data=flow_data, overrides=overrides)

    response = await client.get(_card_url(flow_id))

    assert response.status_code == 200
    body = response.json()
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        assert body["name"] == flow.name
    assert body["version"] == get_version_info()["version"]
    assert body["skills"][0]["tags"] == ["langflow"]
    assert "examples" not in body["skills"][0]
