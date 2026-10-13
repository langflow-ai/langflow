"""A saved flow must not carry an MCP credential in ``flow.data``.

``flow.data`` is an unencrypted JSON column that travels through export, share and
version history. ``cleanMcpConfig`` scrubbed it on those three paths only, never on
save, so registering a project as an MCP server left the auto-minted key sitting in
plaintext in every flow that used it.

Scrubbing is forward-only: the secret moves into the ``mcp_server`` row, which is
encrypted at rest and which ``resolve_mcp_config`` already prefers at runtime, so a
scrubbed flow keeps running unchanged. Flows saved before this are left alone.
"""

import uuid

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.api.utils.mcp.flow_secrets import variable_name_for
from langflow.api.v2.mcp import get_server
from langflow.services.auth.mcp_encryption import MCP_CONFIG_VALUE_MASK, encrypt_mcp_config
from langflow.services.database.models import MCPServer
from langflow.services.deps import get_variable_service, session_scope

SECRET = "sk-mcp-should-never-persist"  # noqa: S105  # pragma: allowlist secret


def _flow_payload(server_name: str, config: dict) -> dict:
    return {
        "name": f"mcp-secret-flow-{uuid.uuid4().hex[:8]}",
        "description": "flow carrying an MCP server config",
        "data": {
            "nodes": [
                {
                    "id": "MCPTools-abc12",
                    "type": "genericNode",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "id": "MCPTools-abc12",
                        "type": "MCPTools",
                        "node": {
                            "template": {
                                "mcp_server": {
                                    "type": "mcp",
                                    "name": "mcp_server",
                                    "value": {"name": server_name, "config": config},
                                }
                            }
                        },
                    },
                }
            ],
            "edges": [],
        },
    }


async def _saved_flow(client: AsyncClient, headers, server_name: str, config: dict) -> tuple[dict, str]:
    response = await client.post("api/v1/flows/", json=_flow_payload(server_name, config), headers=headers)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json(), response.text


def _stored_config(flow: dict) -> dict:
    node = flow["data"]["nodes"][0]
    return node["data"]["node"]["template"]["mcp_server"]["value"]["config"]


async def test_should_not_persist_header_secret_on_create(client: AsyncClient, logged_in_headers):
    server_name = f"billing-{uuid.uuid4().hex[:6]}"
    config = {
        "url": "https://serving.internal/mcp",
        "headers": {"x-api-key": SECRET},
    }

    flow, raw = await _saved_flow(client, logged_in_headers, server_name, config)

    assert SECRET not in raw
    assert _stored_config(flow)["headers"] == {"x-api-key": variable_name_for(server_name, "x-api-key")}


async def test_should_keep_non_secret_config_intact(client: AsyncClient, logged_in_headers):
    """Blanking the credential must not cost the flow its target."""
    server_name = f"billing-{uuid.uuid4().hex[:6]}"
    config = {
        "url": "https://serving.internal/mcp",
        "mode": "Streamable_HTTP",
        "headers": {"x-api-key": SECRET},
    }

    flow, _ = await _saved_flow(client, logged_in_headers, server_name, config)

    stored = _stored_config(flow)
    assert stored["url"] == "https://serving.internal/mcp"
    assert stored["mode"] == "Streamable_HTTP"


async def test_should_move_the_secret_into_the_mcp_server_row(client: AsyncClient, logged_in_headers, active_user):
    """Dropping the value without storing it would break the next run."""
    server_name = f"billing-{uuid.uuid4().hex[:6]}"
    config = {"url": "https://serving.internal/mcp", "headers": {"x-api-key": SECRET}}

    await _saved_flow(client, logged_in_headers, server_name, config)

    response = await client.get(f"api/v2/mcp/servers/{server_name}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    stored = response.json()

    assert SECRET not in response.text
    assert stored["headers"]["x-api-key"] == MCP_CONFIG_VALUE_MASK
    async with session_scope() as session:
        runtime = await get_server(server_name, active_user, session, None, None)
        assert runtime["headers"]["x-api-key"] == SECRET, "the secret must survive somewhere the runtime can reach"


async def test_should_scrub_env_secrets_on_a_stdio_config(client: AsyncClient, logged_in_headers):
    server_name = f"local-{uuid.uuid4().hex[:6]}"
    config = {"command": "uvx", "args": ["some-server"], "env": {"API_TOKEN": SECRET}}

    flow, raw = await _saved_flow(client, logged_in_headers, server_name, config)

    assert SECRET not in raw
    assert _stored_config(flow)["env"] == {"API_TOKEN": variable_name_for(server_name, "API_TOKEN")}


async def test_should_scrub_a_secret_hidden_in_proxy_args(client: AsyncClient, logged_in_headers):
    """Auto-install bakes the minted key into ``--headers x-api-key <key>``."""
    server_name = f"proxy-{uuid.uuid4().hex[:6]}"
    config = {
        "command": "uvx",
        "args": ["mcp-proxy", "--headers", "x-api-key", SECRET, "https://serving.internal/mcp"],
    }

    _, raw = await _saved_flow(client, logged_in_headers, server_name, config)

    assert SECRET not in raw


async def test_should_scrub_on_update_too(client: AsyncClient, logged_in_headers):
    """A flow saved clean can still have a credential pasted into it later."""
    server_name = f"billing-{uuid.uuid4().hex[:6]}"
    flow, _ = await _saved_flow(client, logged_in_headers, server_name, {"url": "https://serving.internal/mcp"})

    payload = _flow_payload(server_name, {"url": "https://serving.internal/mcp", "headers": {"x-api-key": SECRET}})
    response = await client.patch(
        f"api/v1/flows/{flow['id']}", json={"data": payload["data"]}, headers=logged_in_headers
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert SECRET not in response.text


async def test_should_leave_a_static_config_untouched(client: AsyncClient, logged_in_headers):
    """No secret means no rewrite and no row written."""
    server_name = f"static-{uuid.uuid4().hex[:6]}"
    config = {"url": "https://serving.internal/mcp", "mode": "Streamable_HTTP"}

    flow, _ = await _saved_flow(client, logged_in_headers, server_name, config)

    assert _stored_config(flow) == config


async def test_should_keep_the_credential_across_a_lock_retry(
    client: AsyncClient, logged_in_headers, active_user, monkeypatch
):
    """A retried PATCH must not leave the flow pointing at a variable that was never created.

    ``run_with_lock_retry`` rolls the session back between attempts, which discards the
    staged variable and ``mcp_server`` rows, while the in-place rewrite of ``flow.data``
    survives in memory. Re-extracting on attempt 2 would find only the reference attempt 1
    wrote and stage nothing, committing a flow that cannot authenticate.
    """
    from langflow.api.v1 import flows as flows_module
    from langflow.services.database.models.folder.model import Folder

    server_name = f"retry-{uuid.uuid4().hex[:6]}"
    project_payload = {"description": "", "flows_list": [], "components_list": []}
    source = await client.post(
        "api/v1/projects/",
        json={**project_payload, "name": f"retry-src-{uuid.uuid4()}"},
        headers=logged_in_headers,
    )
    destination = await client.post(
        "api/v1/projects/",
        json={**project_payload, "name": f"retry-dst-{uuid.uuid4()}"},
        headers=logged_in_headers,
    )
    assert source.status_code == status.HTTP_201_CREATED
    assert destination.status_code == status.HTTP_201_CREATED

    base = await client.post(
        "api/v1/flows/",
        json={"name": f"retry-base-{uuid.uuid4().hex[:8]}", "data": {}, "folder_id": source.json()["id"]},
        headers=logged_in_headers,
    )
    assert base.status_code == status.HTTP_201_CREATED, base.text
    flow_id = base.json()["id"]

    original_read_flow = flows_module._read_flow
    attempts = {"count": 0}

    async def read_flow_with_competing_commit(*args, **kwargs):
        db_flow = await original_read_flow(*args, **kwargs)
        attempts["count"] += 1
        if attempts["count"] == 1:
            async with session_scope() as competing_session:
                competing_session.add(Folder(name=f"competing-{uuid.uuid4()}", user_id=None))
        return db_flow

    monkeypatch.setattr(flows_module, "_read_flow", read_flow_with_competing_commit)

    payload = _flow_payload(server_name, {"url": "https://serving.internal/mcp", "headers": {"x-api-key": SECRET}})
    # The folder move is what makes the write contend, and contention is what forces the
    # retry this test exists to exercise.
    response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"data": payload["data"], "folder_id": destination.json()["id"]},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert attempts["count"] >= 2, "the PATCH did not retry, so this never exercised the rollback"
    assert SECRET not in response.text

    reference = _stored_config(response.json())["headers"]["x-api-key"]
    variables = await client.get("api/v1/variables/", headers=logged_in_headers)
    assert reference in [item["name"] for item in variables.json()], "the retry left a dangling reference"

    server = await client.get(f"api/v2/mcp/servers/{server_name}", headers=logged_in_headers)
    assert server.status_code == status.HTTP_200_OK, server.text
    assert SECRET not in server.text
    assert server.json()["headers"]["x-api-key"] == MCP_CONFIG_VALUE_MASK
    async with session_scope() as session:
        runtime = await get_server(server_name, active_user, session, None, None)
        assert runtime["headers"]["x-api-key"] == SECRET


async def test_should_apply_a_rotated_credential(client: AsyncClient, logged_in_headers, active_user):
    """Typing a new key into the node must actually change what the runtime sends.

    The variable name does not depend on the value, an existing variable and an existing
    ``mcp_server`` row were both left alone, and the row wins at runtime — so every edit
    after the first was dropped on the floor and the old credential kept being used. A
    rotation that silently does nothing is worse than one that fails.
    """
    server_name = f"rotate-{uuid.uuid4().hex[:6]}"
    rotated = "sk-rotated-and-must-be-used"

    flow, _ = await _saved_flow(
        client,
        logged_in_headers,
        server_name,
        {"url": "https://serving.internal/mcp", "headers": {"x-api-key": SECRET}},
    )

    payload = _flow_payload(server_name, {"url": "https://serving.internal/mcp", "headers": {"x-api-key": rotated}})
    response = await client.patch(
        f"api/v1/flows/{flow['id']}", json={"data": payload["data"]}, headers=logged_in_headers
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    assert rotated not in response.text

    server = await client.get(f"api/v2/mcp/servers/{server_name}", headers=logged_in_headers)
    assert server.status_code == status.HTTP_200_OK, server.text
    assert rotated not in server.text
    assert server.json()["headers"]["x-api-key"] == MCP_CONFIG_VALUE_MASK
    async with session_scope() as session:
        runtime = await get_server(server_name, active_user, session, None, None)
        assert runtime["headers"]["x-api-key"] == rotated, "the rotation was silently discarded"


async def test_should_preserve_masked_credentials_when_saving_a_flow(
    client: AsyncClient, logged_in_headers, active_user
):
    """Saving management masks must preserve current server and global-variable credentials."""
    server_name = f"masked-{uuid.uuid4().hex[:6]}"
    config = {
        "url": "https://serving.internal/mcp",
        "headers": {"x-api-key": SECRET},
        "env": {"API_TOKEN": "test-env-credential"},
    }
    flow, _ = await _saved_flow(client, logged_in_headers, server_name, config)
    editor = await client.get(f"api/v2/mcp/servers/{server_name}", headers=logged_in_headers)
    assert editor.status_code == status.HTTP_200_OK, editor.text
    masked_config = editor.json()
    rotated = "test-current-server-credential"
    updated = await client.patch(
        f"api/v2/mcp/servers/{server_name}",
        json={"headers": {"x-api-key": rotated}},
        headers=logged_in_headers,
    )
    assert updated.status_code == status.HTTP_200_OK, updated.text
    masked_config["headers"]["X-New-Token"] = "test-added-credential"
    payload = _flow_payload(server_name, masked_config)
    response = await client.patch(
        f"api/v1/flows/{flow['id']}", json={"data": payload["data"]}, headers=logged_in_headers
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    assert rotated not in response.text
    assert "test-env-credential" not in response.text
    assert "test-added-credential" not in response.text
    async with session_scope() as session:
        runtime = await get_server(server_name, active_user, session, None, None)
        assert runtime["headers"] == {"x-api-key": rotated, "X-New-Token": "test-added-credential"}
        assert runtime["env"] == config["env"]
        for key, expected in {
            "x-api-key": rotated,
            "API_TOKEN": "test-env-credential",
            "X-New-Token": "test-added-credential",
        }.items():
            actual = await get_variable_service().get_variable(
                user_id=active_user.id, name=variable_name_for(server_name, key), field="", session=session
            )
            assert actual.get_secret_value() == expected, "the flow must retain usable global variables"


@pytest.mark.parametrize(
    "config",
    [
        {"url": "https://serving.internal/mcp", "headers": {"x-api-key": MCP_CONFIG_VALUE_MASK}},
        {"command": "uvx", "args": ["mcp-proxy", "--headers", "x-api-key", MCP_CONFIG_VALUE_MASK]},
        {"url": "https://serving.internal/mcp", "headers": {"Content-Type": MCP_CONFIG_VALUE_MASK}},
    ],
    ids=["header-map", "header-argument", "allowlisted-header"],
)
async def test_should_reject_unresolved_flow_credential_masks(
    client: AsyncClient, logged_in_headers, active_user, config
):
    """An imported management mask cannot become a new server or global-variable credential."""
    server_name = f"unresolved-{uuid.uuid4().hex[:6]}"
    response = await client.post("api/v1/flows/", json=_flow_payload(server_name, config), headers=logged_in_headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    async with session_scope() as session:
        assert await get_server(server_name, active_user, session, None, None) is None
        names = await get_variable_service().list_variables(active_user.id, session)
        assert variable_name_for(server_name, "x-api-key") not in names
        assert variable_name_for(server_name, "Content-Type") not in names


async def test_should_not_resolve_flow_masks_from_another_users_server(
    client: AsyncClient, logged_in_headers, active_user, user_two
):
    """Another owner's server cannot supply secrets for a masked flow import."""
    server_name = f"other-owner-{uuid.uuid4().hex[:6]}"
    config = {"url": "https://serving.internal/mcp", "headers": {"x-api-key": SECRET}}
    async with session_scope() as session:
        session.add(MCPServer(user_id=user_two.id, name=server_name, config=encrypt_mcp_config(config)))
    masked_config = {**config, "headers": {"x-api-key": MCP_CONFIG_VALUE_MASK}}
    response = await client.post(
        "api/v1/flows/", json=_flow_payload(server_name, masked_config), headers=logged_in_headers
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    assert SECRET not in response.text
    async with session_scope() as session:
        assert await get_server(server_name, active_user, session, None, None) is None
        assert await get_server(server_name, user_two, session, None, None) == config
        names = await get_variable_service().list_variables(active_user.id, session)
        assert variable_name_for(server_name, "x-api-key") not in names


@pytest.mark.parametrize("reference_kind", ["placeholder", "generated"])
async def test_should_preserve_masked_variable_references_when_saving_a_flow(
    client: AsyncClient, logged_in_headers, active_user, reference_kind
):
    """A masked editor roundtrip must retain references and follow later variable rotation."""
    server_name = f"reference-{uuid.uuid4().hex[:6]}"
    variable_name = f"MCP_TOKEN_{uuid.uuid4().hex[:6]}"
    reference = f"{{{{{variable_name}}}}}" if reference_kind == "placeholder" else variable_name
    sibling_name = f"MCP_OTHER_{uuid.uuid4().hex[:6]}"
    sibling_reference = f"{{{{{sibling_name}}}}}" if reference_kind == "placeholder" else sibling_name
    config = {
        "url": "https://serving.internal/mcp",
        "headers": {"x-api-key": reference},
        "env": {"API_TOKEN": reference},
    }
    async with session_scope() as session:
        session.add(MCPServer(user_id=active_user.id, name=server_name, config=encrypt_mcp_config(config)))
        await get_variable_service().create_variable(
            user_id=active_user.id, name=variable_name, value=SECRET, session=session
        )
        await get_variable_service().create_variable(
            user_id=active_user.id, name=sibling_name, value="test-sibling-credential", session=session
        )
    flow, _ = await _saved_flow(client, logged_in_headers, server_name, config)
    editor = await client.get(f"api/v2/mcp/servers/{server_name}", headers=logged_in_headers)
    assert editor.status_code == status.HTTP_200_OK, editor.text
    assert editor.json()["headers"]["x-api-key"] == MCP_CONFIG_VALUE_MASK
    payload = _flow_payload(server_name, editor.json())
    sibling_config = {
        **config,
        "headers": {"x-api-key": sibling_reference},
        "env": {"API_TOKEN": sibling_reference},
    }
    sibling_node = _flow_payload(server_name, sibling_config)["data"]["nodes"][0]
    sibling_node["id"] = sibling_node["data"]["id"] = "MCPTools-explicit"
    payload["data"]["nodes"].append(sibling_node)
    response = await client.patch(
        f"api/v1/flows/{flow['id']}", json={"data": payload["data"]}, headers=logged_in_headers
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    assert SECRET not in response.text
    assert _stored_config(response.json())["headers"] == config["headers"]
    assert _stored_config(response.json())["env"] == config["env"]
    saved_sibling = response.json()["data"]["nodes"][1]
    assert saved_sibling["data"]["node"]["template"]["mcp_server"]["value"]["config"] == sibling_config
    async with session_scope() as session:
        runtime = await get_server(server_name, active_user, session, None, None)
        assert runtime == config
        names = await get_variable_service().list_variables(active_user.id, session)
        assert variable_name_for(server_name, "x-api-key") not in names
        assert variable_name_for(server_name, "API_TOKEN") not in names
        sibling_value = await get_variable_service().get_variable(
            user_id=active_user.id, name=sibling_name, field="", session=session
        )
        assert sibling_value.get_secret_value() == "test-sibling-credential"
        rotated = "test-rotated-reference-credential"
        await get_variable_service().update_variable(
            user_id=active_user.id, name=variable_name, value=rotated, session=session
        )
    from lfx.base.mcp.util import _resolve_global_variables_in_headers

    assert _resolve_global_variables_in_headers(runtime["headers"], {variable_name: rotated}) == {"x-api-key": rotated}
    assert _resolve_global_variables_in_headers(runtime["env"], {variable_name: rotated}) == {"API_TOKEN": rotated}


async def test_should_keep_a_masked_allowlisted_header_out_of_the_flow_response(
    client: AsyncClient, logged_in_headers, active_user
):
    """A management mask must stay confidential regardless of the header's name."""
    server_name = f"allowlisted-{uuid.uuid4().hex[:6]}"
    config = {"url": "https://serving.internal/mcp", "headers": {"Content-Type": SECRET}}
    async with session_scope() as session:
        session.add(MCPServer(user_id=active_user.id, name=server_name, config=encrypt_mcp_config(config)))
    editor = await client.get(f"api/v2/mcp/servers/{server_name}", headers=logged_in_headers)
    assert editor.status_code == status.HTTP_200_OK, editor.text
    assert editor.json()["headers"]["Content-Type"] == MCP_CONFIG_VALUE_MASK
    response = await client.post(
        "api/v1/flows/", json=_flow_payload(server_name, editor.json()), headers=logged_in_headers
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert SECRET not in response.text
    alias = variable_name_for(server_name, "Content-Type")
    assert _stored_config(response.json())["headers"] == {"Content-Type": alias}
    async with session_scope() as session:
        assert await get_server(server_name, active_user, session, None, None) == config
        credential = await get_variable_service().get_variable(
            user_id=active_user.id, name=alias, field="", session=session
        )
        assert credential.get_secret_value() == SECRET
