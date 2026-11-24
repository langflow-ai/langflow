"""Regression test for issue #9505.

When the caller supplies a ``user_id`` separate from the authenticated user
(e.g. via the ``/api/v1/run/{flow_id}`` request body), it must reach the
tracing layer untouched. The auth user_id remains the source of truth for
authentication and authorization and for ``trace.userId``; the caller-supplied
label is forwarded as ``tracing_user_id`` so providers can surface it
separately (e.g. in trace metadata).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from lfx.graph import Graph


@pytest.mark.asyncio
async def test_initialize_run_forwards_both_user_id_and_tracing_user_id():
    """Auth ``user_id`` and ``tracing_user_id`` must be passed as distinct kwargs.

    Graph just forwards both fields untouched; how the override surfaces (e.g.
    LangFuseTracer stamps it into trace metadata) is the provider's concern.
    """
    graph = Graph(flow_id="11111111-1111-1111-1111-111111111111", flow_name="t", user_id="auth-user")
    graph.tracing_user_id = "test123"
    graph.session_id = "session-abc"
    graph.set_run_id(uuid.uuid4())

    fake_service = AsyncMock()
    fake_service.start_tracers = AsyncMock()
    graph._tracing_service = fake_service
    graph._tracing_service_initialized = True

    await graph.initialize_run()

    fake_service.start_tracers.assert_awaited_once()
    kwargs = fake_service.start_tracers.await_args.kwargs
    assert kwargs["user_id"] == "auth-user"
    assert kwargs["tracing_user_id"] == "test123"
    assert kwargs["session_id"] == "session-abc"


@pytest.mark.asyncio
async def test_initialize_run_passes_none_tracing_user_id_when_no_override():
    """Without an override, ``tracing_user_id`` is None and only ``user_id`` reaches the tracers."""
    graph = Graph(flow_id="22222222-2222-2222-2222-222222222222", flow_name="t", user_id="auth-user")
    graph.session_id = "s"
    graph.set_run_id(uuid.uuid4())

    fake_service = AsyncMock()
    fake_service.start_tracers = AsyncMock()
    graph._tracing_service = fake_service
    graph._tracing_service_initialized = True

    await graph.initialize_run()

    kwargs = fake_service.start_tracers.await_args.kwargs
    assert kwargs["user_id"] == "auth-user"
    assert kwargs["tracing_user_id"] is None


def test_tracing_user_id_default_is_none():
    """Defaults must not change for existing call sites."""
    graph = Graph(flow_id="33333333-3333-3333-3333-333333333333", flow_name="t", user_id="auth-user")
    assert graph.tracing_user_id is None
    assert graph.user_id == "auth-user"
