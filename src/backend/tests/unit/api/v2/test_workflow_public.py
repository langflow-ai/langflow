"""Security tests for ``POST /api/v2/workflows/public``.

Mirrors the v1 ``build_public_tmp`` security suite. Each test pins one of
the mitigations the v2 public endpoint is supposed to inherit from v1:

- access_type == PUBLIC gate (403 for private flows).
- per-visitor virtual_flow_id propagated to the graph builder.
- session id namespaced under the visitor's virtual flow id
  (CVE-2026-33017).
- file-path validation (GHSA-rcjh-r59h-gq37).
- ``data`` / ``tweaks`` rejected by the wire schema (visitors must never
  override the stored flow definition).
- AUTO_LOGIN parity: authenticated_user_id is ignored when AUTO_LOGIN is
  on so the backend's virtual_flow_id matches the frontend's.
- Owner impersonation: the flow runs under the flow owner's user, not
  the visitor's.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from httpx import AsyncClient, codes
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
    import langflow.api.v2.workflow as workflow_module

    async def _fake_generate_flow_events(**kwargs: Any) -> None:
        captured.update(kwargs)
        # Make sure the stream loop's queue terminates cleanly.
        import time

        await kwargs["event_manager"].queue.put((None, None, time.time()))

    monkeypatch.setattr(workflow_module, "generate_flow_events", _fake_generate_flow_events)


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
    """Private flows return 403 before any policy validation runs (info-leak guard)."""
    from tests.unit.build_utils import create_flow

    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    # Note: we deliberately do NOT mark it public.

    _send_unauthenticated(client, "private-test-client")
    response = await client.post(
        "api/v2/workflows/public",
        json={"flow_id": str(flow_id), "input_value": "Hi"},
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == codes.FORBIDDEN


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

    expected_namespace = str(compute_virtual_flow_id(client_id, public_flow_id))
    sent_inputs = captured["inputs"]
    assert sent_inputs is not None
    assert sent_inputs.session == f"{expected_namespace}:{victim_session}"
    assert sent_inputs.session != victim_session


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

    expected_virtual = compute_virtual_flow_id(client_id, public_flow_id)
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
async def test_public_endpoint_runs_as_flow_owner(client: AsyncClient, public_flow_id, monkeypatch):
    """Owner impersonation: ``current_user`` passed to the build is the flow's owner."""
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

    assert captured["current_user"].id == owner_id


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

    def _raise(*_args, **_kwargs):
        raise CustomComponentValidationError(raw_message)

    import langflow.api.v2.workflow_public as workflow_public_module

    monkeypatch.setattr(workflow_public_module, "validate_flow_for_current_settings", _raise)

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
async def test_public_endpoint_surfaces_value_error_as_400(client: AsyncClient, public_flow_id, monkeypatch):
    """Other ``ValueError``s from the gate sequence become 400 with the message preserved.

    Mirrors v1 ``build_public_tmp``'s ``except ValueError -> HTTP 400``.
    Without the wrapper the same path returns a 500 with a stack trace.
    """
    import langflow.api.v2.workflow_public as workflow_public_module

    gate_error_message = "custom gate failure"

    def _raise(*_args, **_kwargs):
        raise ValueError(gate_error_message)

    monkeypatch.setattr(workflow_public_module, "validate_flow_for_current_settings", _raise)

    _send_unauthenticated(client, "value-error-client")
    response = await client.post(
        "api/v2/workflows/public",
        json={"flow_id": str(public_flow_id), "input_value": "Hi"},
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == codes.BAD_REQUEST
    assert response.json().get("detail") == "custom gate failure"
