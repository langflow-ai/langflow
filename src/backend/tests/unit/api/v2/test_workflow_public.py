"""Security tests for ``POST /api/v2/workflows/public``.

Mirrors the v1 ``build_public_tmp`` security suite. Each test pins one of
the mitigations the v2 public endpoint is supposed to inherit from v1:

- access_type == PUBLIC compatibility grant (private flows are hidden as 404).
- per-visitor virtual_flow_id propagated to the graph builder.
- session id namespaced under the visitor's virtual flow id
  (CVE-2026-33017).
- file-path validation (GHSA-rcjh-r59h-gq37).
- ``data`` / ``tweaks`` rejected by the wire schema (visitors must never
  override the stored flow definition).
- AUTO_LOGIN parity: authenticated_user_id is ignored when AUTO_LOGIN is
  on so the backend's virtual_flow_id matches the frontend's.
- Anonymous principal isolation: the flow never runs under the owner's user.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
from httpx import AsyncClient, codes
from langflow.services.database.models.auth import AuthzShare, SharePermissionLevel, ShareScope
from langflow.services.database.models.flow.model import Flow
from lfx.services.deps import session_scope
from sqlmodel import select

if TYPE_CHECKING:
    from uuid import UUID


def _stub_generate_flow_events(monkeypatch, captured: dict) -> None:
    """Capture kwargs that would reach ``generate_flow_events`` without running anything.

    The v2 public endpoint reaches ``generate_flow_events`` via
    ``_stream_event_frames``; intercepting at the build entry point lets
    us assert on flow_id translation, session scoping, owner
    impersonation, and source_flow_id propagation without needing the
    full streaming pipeline.
    """
    from langflow.api.v2 import workflow_execution

    async def _fake_generate_flow_events(**kwargs: Any) -> None:
        captured.update(kwargs)
        # Make sure the stream loop's queue terminates cleanly.
        import time

        await kwargs["event_manager"].queue.put((None, None, time.time()))

    monkeypatch.setattr(workflow_execution, "generate_flow_events", _fake_generate_flow_events)


def _send_unauthenticated(client: AsyncClient, client_id: str) -> None:
    """Drop login cookies and set the public ``client_id`` cookie.

    The shared client persists access-token cookies from
    ``logged_in_headers``; clearing them is the only way to land in the
    AUTO_LOGIN=true unauthenticated namespace path the CVE targets.
    """
    client.cookies.clear()
    client.cookies.set("client_id", client_id)


async def _make_flow_public(client: AsyncClient, flow_id: UUID, headers: dict) -> None:
    response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"access_type": "PUBLIC"},
        headers=headers,
    )
    assert response.status_code == codes.OK


async def _read_stream(response) -> None:
    """Drain the SSE response so the generator runs and the stub fires."""
    async for _ in response.aiter_bytes():
        pass


@pytest.fixture
async def public_flow_id(client: AsyncClient, json_memory_chatbot_no_llm, logged_in_headers):
    from tests.unit.build_utils import create_flow

    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    await _make_flow_public(client, flow_id, logged_in_headers)
    return flow_id


@pytest.mark.benchmark
@pytest.mark.security
async def test_public_endpoint_rejects_non_public_flow(
    client: AsyncClient, json_memory_chatbot_no_llm, logged_in_headers
):
    """Private and missing flows share the same privacy-preserving 404 contract."""
    from tests.unit.build_utils import create_flow

    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    # Note: we deliberately do NOT mark it public.

    _send_unauthenticated(client, "private-test-client")
    response = await client.post(
        "api/v2/workflows/public",
        json={"flow_id": str(flow_id), "input_value": "Hi"},
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == codes.NOT_FOUND
    denied_body = response.content

    missing_response = await client.post(
        "api/v2/workflows/public",
        json={"flow_id": str(uuid4()), "input_value": "Hi"},
        headers={"Content-Type": "application/json"},
    )
    assert missing_response.status_code == codes.NOT_FOUND
    assert missing_response.content == denied_body


@pytest.mark.benchmark
@pytest.mark.security
async def test_public_execute_share_grants_direct_link_and_revoke_blocks_next_start(
    client: AsyncClient,
    json_memory_chatbot_no_llm,
    logged_in_headers,
    monkeypatch,
):
    """Canonical PUBLIC shares admit direct execution; deleting the row blocks the next run."""
    from tests.unit.build_utils import create_flow

    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        assert flow is not None
        share = AuthzShare(
            resource_type="flow",
            resource_id=flow_id,
            scope=ShareScope.PUBLIC.value,
            permission_level=SharePermissionLevel.EXECUTE.value,
            created_by=flow.user_id,
        )
        session.add(share)
        await session.commit()
        await session.refresh(share)
        share_id = share.id

    captured: dict = {}
    _stub_generate_flow_events(monkeypatch, captured)
    _send_unauthenticated(client, "public-share-client")
    async with client.stream(
        "POST",
        "api/v2/workflows/public",
        json={"flow_id": str(flow_id), "input_value": "Hi"},
        headers={"Content-Type": "application/json"},
    ) as response:
        assert response.status_code == codes.OK
        await _read_stream(response)

    async with session_scope() as session:
        stored_share = await session.get(AuthzShare, share_id)
        assert stored_share is not None
        await session.delete(stored_share)
        await session.commit()

    response = await client.post(
        "api/v2/workflows/public",
        json={"flow_id": str(flow_id), "input_value": "Hi"},
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == codes.NOT_FOUND


@pytest.mark.benchmark
@pytest.mark.security
async def test_public_endpoint_rejects_data_field(client: AsyncClient, public_flow_id):
    """``data`` is forbidden by the wire schema — visitors cannot override stored flow data."""
    _send_unauthenticated(client, "data-rejection-client")
    response = await client.post(
        "api/v2/workflows/public",
        json={
            "flow_id": str(public_flow_id),
            "input_value": "Hi",
            "data": {"nodes": [], "edges": []},
        },
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == codes.UNPROCESSABLE_ENTITY


@pytest.mark.benchmark
@pytest.mark.security
async def test_public_endpoint_rejects_tweaks_field(client: AsyncClient, public_flow_id):
    """``tweaks`` is forbidden by the wire schema — visitors cannot override component params."""
    _send_unauthenticated(client, "tweaks-rejection-client")
    response = await client.post(
        "api/v2/workflows/public",
        json={
            "flow_id": str(public_flow_id),
            "input_value": "Hi",
            "tweaks": {"node-id": {"input_value": "override"}},
        },
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == codes.UNPROCESSABLE_ENTITY


@pytest.mark.benchmark
@pytest.mark.security
async def test_public_endpoint_rejects_oversized_input_value(client: AsyncClient, public_flow_id):
    """An anonymous caller cannot post an arbitrarily large ``input_value``; the wire schema bounds it at 64 KB."""
    _send_unauthenticated(client, "oversized-input-client")
    response = await client.post(
        "api/v2/workflows/public",
        json={
            "flow_id": str(public_flow_id),
            "input_value": "x" * (64 * 1024 + 1),
        },
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == codes.UNPROCESSABLE_ENTITY


@pytest.mark.benchmark
@pytest.mark.security
async def test_public_endpoint_rejects_oversized_session_id(client: AsyncClient, public_flow_id):
    """``session_id`` is bounded too — it is namespaced and persisted per visitor."""
    _send_unauthenticated(client, "oversized-session-client")
    response = await client.post(
        "api/v2/workflows/public",
        json={
            "flow_id": str(public_flow_id),
            "input_value": "Hi",
            "session_id": "s" * (256 + 1),
        },
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == codes.UNPROCESSABLE_ENTITY


@pytest.mark.benchmark
@pytest.mark.security
async def test_public_endpoint_rejects_non_stream_mode(client: AsyncClient, public_flow_id):
    """``mode`` must be ``stream`` — sync/background widen the public attack surface."""
    _send_unauthenticated(client, "mode-rejection-client")
    response = await client.post(
        "api/v2/workflows/public",
        json={
            "flow_id": str(public_flow_id),
            "input_value": "Hi",
            "mode": "sync",
        },
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == codes.UNPROCESSABLE_ENTITY


@pytest.mark.benchmark
@pytest.mark.security
async def test_public_endpoint_rejects_malicious_files(client: AsyncClient, public_flow_id):
    """Regression for GHSA-rcjh-r59h-gq37 — file paths must be ``{flow_id}/{basename}``."""
    _send_unauthenticated(client, "files-rejection-client")
    response = await client.post(
        "api/v2/workflows/public",
        json={
            "flow_id": str(public_flow_id),
            "input_value": "Hi",
            "files": ["../../../etc/passwd"],
        },
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == codes.BAD_REQUEST


@pytest.mark.benchmark
@pytest.mark.security
async def test_public_endpoint_namespaces_caller_session(client: AsyncClient, public_flow_id, monkeypatch):
    """Caller-supplied ``session_id`` is wrapped under the (client_id, flow_id) namespace.

    Pins CVE-2026-33017 for the v2 public endpoint: an unauthenticated
    visitor must not be able to address a session that lives outside
    their own namespace through a Memory component.
    """
    from langflow.api.utils.flow_utils import compute_virtual_flow_id

    captured: dict = {}
    _stub_generate_flow_events(monkeypatch, captured)

    client_id = "ns-test-client-v2"
    _send_unauthenticated(client, client_id)
    victim_session = str(public_flow_id)

    async with client.stream(
        "POST",
        "api/v2/workflows/public",
        json={
            "flow_id": str(public_flow_id),
            "input_value": "Hi",
            "session_id": victim_session,
        },
        headers={"Content-Type": "application/json"},
    ) as response:
        assert response.status_code == codes.OK
        await _read_stream(response)

    expected_namespace = str(compute_virtual_flow_id(client_id, public_flow_id, principal_type="client"))
    sent_inputs = captured["inputs"]
    assert sent_inputs is not None
    assert sent_inputs.session == f"{expected_namespace}:{victim_session}"
    assert sent_inputs.session != victim_session
    assert captured["run_id"] is not None


@pytest.mark.benchmark
@pytest.mark.security
async def test_public_endpoint_uses_virtual_flow_id_for_storage(client: AsyncClient, public_flow_id, monkeypatch):
    """``generate_flow_events`` is called with ``flow_id=virtual``, ``source_flow_id=real``.

    The graph loads from the real flow id (the DB row) but tags messages
    with the virtual flow id so the popup's ``useGetFlowId``-keyed
    filter actually matches.
    """
    from langflow.api.utils.flow_utils import compute_virtual_flow_id

    captured: dict = {}
    _stub_generate_flow_events(monkeypatch, captured)

    client_id = "virtual-id-test-client"
    _send_unauthenticated(client, client_id)

    async with client.stream(
        "POST",
        "api/v2/workflows/public",
        json={"flow_id": str(public_flow_id), "input_value": "Hi"},
        headers={"Content-Type": "application/json"},
    ) as response:
        assert response.status_code == codes.OK
        await _read_stream(response)

    expected_virtual = compute_virtual_flow_id(client_id, public_flow_id, principal_type="client")
    assert captured["flow_id"] == expected_virtual
    assert captured["source_flow_id"] == public_flow_id


@pytest.mark.benchmark
@pytest.mark.security
async def test_public_endpoint_isolates_disjoint_clients(client: AsyncClient, public_flow_id, monkeypatch):
    """Two client_ids submitting the same session string land in disjoint namespaces."""
    shared_session = "shared-session-name"

    captured: dict = {}
    _stub_generate_flow_events(monkeypatch, captured)

    _send_unauthenticated(client, "iso-client-A")
    async with client.stream(
        "POST",
        "api/v2/workflows/public",
        json={"flow_id": str(public_flow_id), "input_value": "Hi", "session_id": shared_session},
        headers={"Content-Type": "application/json"},
    ) as response:
        assert response.status_code == codes.OK
        await _read_stream(response)
    session_a = captured["inputs"].session

    captured.clear()
    _send_unauthenticated(client, "iso-client-B")
    async with client.stream(
        "POST",
        "api/v2/workflows/public",
        json={"flow_id": str(public_flow_id), "input_value": "Hi", "session_id": shared_session},
        headers={"Content-Type": "application/json"},
    ) as response:
        assert response.status_code == codes.OK
        await _read_stream(response)
    session_b = captured["inputs"].session

    assert session_a != session_b
    assert session_a.endswith(f":{shared_session}")
    assert session_b.endswith(f":{shared_session}")


@pytest.mark.benchmark
@pytest.mark.security
async def test_public_endpoint_runs_as_stable_non_owner_principal(client: AsyncClient, public_flow_id, monkeypatch):
    """Anonymous execution never inherits the owner's dependency principal."""
    captured: dict = {}
    _stub_generate_flow_events(monkeypatch, captured)

    _send_unauthenticated(client, "owner-test-client")
    async with client.stream(
        "POST",
        "api/v2/workflows/public",
        json={"flow_id": str(public_flow_id), "input_value": "Hi"},
        headers={"Content-Type": "application/json"},
    ) as response:
        assert response.status_code == codes.OK
        await _read_stream(response)

    # Look up the flow owner directly to compare.
    async with session_scope() as session:
        flow = (await session.exec(select(Flow).where(Flow.id == public_flow_id))).first()
        assert flow is not None
        owner_id = flow.user_id

    execution_principal = captured["current_user"]
    from langflow.services.authorization.public_access import PUBLIC_ANONYMOUS_ACTOR_ID

    assert execution_principal.id == PUBLIC_ANONYMOUS_ACTOR_ID
    assert execution_principal.id != owner_id
    assert execution_principal.username == "anonymous-public"
    assert execution_principal.is_superuser is False


@pytest.mark.benchmark
@pytest.mark.security
async def test_public_endpoint_reauthorizes_reloaded_flow_after_grant_transition(
    client: AsyncClient,
    public_flow_id,
    monkeypatch,
):
    """The exact DB snapshot detached for streaming must still hold a public grant."""
    import langflow.api.v2.workflow_public as workflow_public_module
    from langflow.api.utils.flow_utils import compute_virtual_flow_id
    from langflow.services.authorization.public_access import public_execution_user
    from langflow.services.database.models.flow.model import AccessTypeEnum

    client_id = "v2-reload-revocation-client"

    async def _admit_first_snapshot_then_revoke(**_kwargs):
        async with session_scope() as session:
            flow = await session.get(Flow, public_flow_id)
            assert flow is not None
            flow.access_type = AccessTypeEnum.PRIVATE
            session.add(flow)
            await session.commit()
        return public_execution_user(), compute_virtual_flow_id(client_id, public_flow_id, principal_type="client")

    captured: dict = {}
    monkeypatch.setattr(
        workflow_public_module,
        "verify_public_flow_and_get_user",
        _admit_first_snapshot_then_revoke,
    )
    _stub_generate_flow_events(monkeypatch, captured)
    _send_unauthenticated(client, client_id)

    response = await client.post(
        "api/v2/workflows/public",
        json={"flow_id": str(public_flow_id), "input_value": "Hi"},
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == codes.NOT_FOUND
    assert response.json() == {"detail": "Flow not found"}
    assert captured == {}


@pytest.mark.benchmark
@pytest.mark.security
async def test_public_endpoint_builds_from_server_sanitized_flow_data(client: AsyncClient, public_flow_id, monkeypatch):
    """Stored component code is replaced and persisted secrets are stripped before an anonymous v2 run."""
    import langflow.api.v2.workflow_public as workflow_public_module

    captured: dict = {}
    _stub_generate_flow_events(monkeypatch, captured)
    prepared = {
        "nodes": [
            {
                "id": "trusted-node",
                "data": {
                    "type": "TrustedComponent",
                    "node": {
                        "template": {
                            "api_key": {
                                "name": "api_key",
                                "password": True,
                                "value": "sk-owner-secret",  # pragma: allowlist secret
                            }
                        }
                    },
                },
            }
        ],
        "edges": [],
    }

    async def _prepare(_flow_data):
        return prepared

    monkeypatch.setattr(workflow_public_module, "prepare_public_flow_build", _prepare)

    _send_unauthenticated(client, "trusted-code-test-client")
    async with client.stream(
        "POST",
        "api/v2/workflows/public",
        json={"flow_id": str(public_flow_id), "input_value": "Hi"},
        headers={"Content-Type": "application/json"},
    ) as response:
        assert response.status_code == codes.OK
        await _read_stream(response)

    assert captured["data"] is not None
    assert captured["data"].nodes[0]["id"] == "trusted-node"
    assert captured["data"].nodes[0]["data"]["node"]["template"]["api_key"]["value"] is None
    assert captured["data"].edges == prepared["edges"]
    assert prepared["nodes"][0]["data"]["node"]["template"]["api_key"]["value"] == "sk-owner-secret"


@pytest.mark.benchmark
@pytest.mark.security
async def test_public_endpoint_sanitizes_before_global_outdated_code_gate(
    client: AsyncClient, public_flow_id, monkeypatch
):
    """Default public builds must reach trusted sanitization even when strict global drift policy is off."""
    import langflow.api.v2.workflow_public as workflow_public_module

    settings = workflow_public_module.get_settings_service().settings
    monkeypatch.setattr(settings, "allow_custom_components", False)
    monkeypatch.setattr(settings, "substitute_outdated_component_code", False)
    monkeypatch.setattr(settings, "allow_public_custom_components", False)

    stale_code = "# deliberately stale client-stored ChatInput source"
    async with session_scope() as session:
        flow = await session.get(Flow, public_flow_id)
        assert flow is not None
        assert flow.data is not None
        updated_data = copy.deepcopy(flow.data)
        chat_input = next(node for node in updated_data["nodes"] if node["data"]["type"] == "ChatInput")
        chat_input["data"]["node"]["template"]["code"]["value"] = stale_code
        flow.data = updated_data
        session.add(flow)
        await session.commit()

    captured: dict = {}
    _stub_generate_flow_events(monkeypatch, captured)

    _send_unauthenticated(client, "outdated-public-code-client")
    async with client.stream(
        "POST",
        "api/v2/workflows/public",
        json={"flow_id": str(public_flow_id), "input_value": "Hi"},
        headers={"Content-Type": "application/json"},
    ) as response:
        assert response.status_code == codes.OK
        await _read_stream(response)

    sanitized_chat_input = next(node for node in captured["data"].nodes if node["data"]["type"] == "ChatInput")
    assert sanitized_chat_input["data"]["node"]["template"]["code"]["value"] != stale_code


@pytest.mark.benchmark
@pytest.mark.security
async def test_public_endpoint_rejects_missing_client_id(client: AsyncClient, public_flow_id):
    """Without a ``client_id`` cookie or authenticated user, the request is rejected."""
    client.cookies.clear()  # no client_id, no auth
    response = await client.post(
        "api/v2/workflows/public",
        json={"flow_id": str(public_flow_id), "input_value": "Hi"},
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == codes.BAD_REQUEST


@pytest.mark.benchmark
@pytest.mark.security
async def test_public_endpoint_sanitizes_component_validation_error(client: AsyncClient, public_flow_id, monkeypatch):
    """``CustomComponentValidationError`` must not leak blocked class names to anonymous visitors.

    Mirrors v1 ``build_public_tmp``: the raw error message embeds the
    disabled component class names, which is enumeration of the owner's
    flow internals through a public surface. Surface a sanitized 400.
    """
    from lfx.utils.flow_validation import CustomComponentValidationError

    raw_message = "Flow build blocked: custom components are not allowed: SecretInternalComponent"

    async def _raise(*_args, **_kwargs):
        raise CustomComponentValidationError(raw_message)

    import langflow.api.v2.workflow_public as workflow_public_module

    monkeypatch.setattr(workflow_public_module, "prepare_public_flow_build", _raise)

    _send_unauthenticated(client, "component-validation-client")
    response = await client.post(
        "api/v2/workflows/public",
        json={"flow_id": str(public_flow_id), "input_value": "Hi"},
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == codes.BAD_REQUEST
    detail = response.json().get("detail", "")
    assert detail == "This flow cannot be executed."
    assert "SecretInternalComponent" not in detail
    assert raw_message not in response.text


@pytest.mark.benchmark
@pytest.mark.security
async def test_public_endpoint_sanitizes_catalog_identity_unavailable_response(
    client: AsyncClient, public_flow_id, monkeypatch
):
    from lfx.utils.flow_validation import (
        PUBLIC_CATALOG_POLICY_UNAVAILABLE_MESSAGE,
        CatalogPolicyIdentityUnavailableError,
    )

    raw_message = "Catalog identities unavailable: internal generation 42"

    def _raise(*_args, **_kwargs):
        raise CatalogPolicyIdentityUnavailableError(raw_message)

    import langflow.api.v2.workflow_public as workflow_public_module

    monkeypatch.setattr(workflow_public_module, "validate_catalog_policy_for_flow", _raise)

    _send_unauthenticated(client, "catalog-identity-unavailable-client")
    response = await client.post(
        "api/v2/workflows/public",
        json={"flow_id": str(public_flow_id), "input_value": "Hi"},
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == codes.SERVICE_UNAVAILABLE
    assert response.json()["detail"] == PUBLIC_CATALOG_POLICY_UNAVAILABLE_MESSAGE
    assert raw_message not in response.text


@pytest.mark.benchmark
@pytest.mark.security
async def test_public_endpoint_rejects_code_execution_components(
    client: AsyncClient, json_memory_chatbot_no_llm, logged_in_headers
):
    """Report H1-3754930: unauthenticated public v2 runs must reject code-execution components.

    Mirrors v1 ``test_build_public_tmp_rejects_code_execution_components``. A public
    flow containing a Python interpreter/REPL would otherwise let any anonymous
    visitor trigger server-side code execution through ``/api/v2/workflows/public``.
    """
    import json

    from tests.unit.build_utils import create_flow

    flow_dict = json.loads(json_memory_chatbot_no_llm)
    flow_dict["data"]["nodes"].append(
        {
            "id": "PythonREPLComponent-pub1",
            "type": "genericNode",
            "position": {"x": 0, "y": 0},
            "data": {
                "id": "PythonREPLComponent-pub1",
                "type": "PythonREPLComponent",
                "display_name": "Python Interpreter",
                "node": {"display_name": "Python Interpreter", "template": {}},
            },
        }
    )
    flow_id = await create_flow(client, json.dumps(flow_dict), logged_in_headers)
    await _make_flow_public(client, flow_id, logged_in_headers)

    _send_unauthenticated(client, "test-code-exec-client")
    response = await client.post(
        "api/v2/workflows/public",
        json={"flow_id": str(flow_id), "input_value": "Hi"},
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == codes.BAD_REQUEST
    assert response.json()["detail"] == "This flow cannot be executed."


@pytest.mark.benchmark
@pytest.mark.security
async def test_public_endpoint_rejects_mcp_stdio_server_config(
    client: AsyncClient, json_memory_chatbot_no_llm, logged_in_headers
):
    """An MCP Tools node configured for the stdio transport must not run anonymously.

    The command it would launch lives in the ``mcp_server`` field VALUE rather than in
    ``code``, so trusted-code substitution leaves it intact; without the public-path
    check an anonymous visitor would make the server spawn that OS process.
    """
    import json

    from tests.unit.build_utils import create_flow

    flow_dict = json.loads(json_memory_chatbot_no_llm)
    flow_dict["data"]["nodes"].append(
        {
            "id": "MCPTools-pub1",
            "type": "genericNode",
            "position": {"x": 0, "y": 0},
            "data": {
                "id": "MCPTools-pub1",
                "type": "MCPTools",
                "node": {
                    "display_name": "MCP Tools",
                    "template": {
                        "mcp_server": {
                            "type": "mcp",
                            "name": "mcp_server",
                            "value": {
                                "name": "local",
                                "config": {"command": "python", "args": ["-m", "some_module"]},
                            },
                        }
                    },
                },
            },
        }
    )
    flow_id = await create_flow(client, json.dumps(flow_dict), logged_in_headers)
    await _make_flow_public(client, flow_id, logged_in_headers)

    _send_unauthenticated(client, "test-mcp-stdio-client")
    response = await client.post(
        "api/v2/workflows/public",
        json={"flow_id": str(flow_id), "input_value": "Hi"},
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == codes.BAD_REQUEST
    assert response.json()["detail"] == "This flow cannot be executed."


@pytest.mark.benchmark
@pytest.mark.security
async def test_public_endpoint_surfaces_value_error_as_400(client: AsyncClient, public_flow_id, monkeypatch):
    """Other gate ``ValueError``s become a sanitized 400."""
    import langflow.api.v2.workflow_public as workflow_public_module

    gate_error_message = "custom gate failure"

    async def _raise(*_args, **_kwargs):
        raise ValueError(gate_error_message)

    monkeypatch.setattr(workflow_public_module, "prepare_public_flow_build", _raise)

    _send_unauthenticated(client, "value-error-client")
    response = await client.post(
        "api/v2/workflows/public",
        json={"flow_id": str(public_flow_id), "input_value": "Hi"},
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == codes.BAD_REQUEST
    assert response.json().get("detail") == "This flow cannot be executed."
    assert gate_error_message not in response.text


@pytest.fixture
def _fresh_limiter():
    """Reset the global limiter singleton so the throttle test starts clean."""
    import langflow.services.rate_limit.service as rate_limit_module

    original = rate_limit_module._limiter
    rate_limit_module._limiter = None
    yield
    rate_limit_module._limiter = original


@pytest.mark.security
@pytest.mark.usefixtures("_fresh_limiter")
def test_public_endpoint_throttles_per_ip(monkeypatch):
    """The unauthenticated public endpoint throttles per client IP.

    Each run has real cost, so an anonymous caller must
    not be able to spin up unbounded runs. With the limit set to 2/min, the third
    request from the same IP is rejected at the throttle (429) before any flow work.
    """
    from fastapi.testclient import TestClient
    from langflow.main import create_app
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "public_flow_rate_limit_per_minute", 2)

    app = create_app()
    sync_client = TestClient(app)
    body = {"flow_id": str(uuid4()), "input_value": "hi"}

    statuses = [sync_client.post("api/v2/workflows/public", json=body).status_code for _ in range(3)]

    # First two pass the throttle (and fail downstream on the nonexistent flow);
    # the third exhausts the 2/min window and is rejected at the throttle.
    assert statuses[2] == codes.TOO_MANY_REQUESTS, statuses
    assert codes.TOO_MANY_REQUESTS not in statuses[:2], statuses
