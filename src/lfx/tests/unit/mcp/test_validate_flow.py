"""Tests for lfx.mcp.server.validate_flow.

The tool streams the build inline (event_delivery=direct) and aggregates
per-vertex results from `end_vertex` events. These tests verify the
fast-fail and partial-error-reporting behaviour so a missing required
config doesn't leave callers waiting with no actionable information.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


def _flow_with_nodes(count: int) -> dict:
    return {
        "id": "flow-1",
        "name": "Test",
        "data": {
            "nodes": [{"id": f"node-{i}"} for i in range(count)],
            "edges": [],
        },
    }


def _end_vertex_event(vertex_id: str, *, valid: bool, error_message: str | None = None) -> dict:
    outputs: dict = {}
    if not valid and error_message is not None:
        outputs = {"output": {"message": {"errorMessage": error_message, "stackTrace": ""}, "type": "error"}}
    return {
        "event": "end_vertex",
        "data": {
            "build_data": {
                "id": vertex_id,
                "valid": valid,
                "params": error_message if not valid else "",
                "data": {"outputs": outputs},
            },
        },
    }


def _end_event() -> dict:
    return {"event": "end", "data": {"build_duration": 0.1}}


def _stream_client(events: list[dict]) -> MagicMock:
    """Build a client mock whose stream_post yields the given events."""

    async def _stream(*_args, **_kwargs):
        for event in events:
            yield event

    client = MagicMock()
    client.stream_post = _stream
    return client


def _patch_validate(*, flow: dict, client: MagicMock):
    """Patch the dependencies validate_flow reaches out to."""
    from contextlib import contextmanager

    @contextmanager
    def ctx():
        with (
            patch("lfx.mcp.server._get_client", return_value=client),
            patch("lfx.mcp.server._get_flow", new_callable=AsyncMock, return_value=flow),
        ):
            yield

    return ctx()


class TestValidateFlow:
    async def test_empty_flow_returns_valid(self) -> None:
        from lfx.mcp.server import validate_flow

        flow = _flow_with_nodes(0)
        client = _stream_client([])

        with _patch_validate(flow=flow, client=client):
            result = await validate_flow("flow-1")

        assert result == {"valid": True, "component_count": 0, "errors": [], "warnings": []}

    async def test_all_components_valid_returns_valid(self) -> None:
        from lfx.mcp.server import validate_flow

        flow = _flow_with_nodes(2)
        events = [
            _end_vertex_event("A-1", valid=True),
            _end_vertex_event("B-1", valid=True),
            _end_event(),
        ]
        client = _stream_client(events)

        with _patch_validate(flow=flow, client=client):
            result = await validate_flow("flow-1")

        assert result["valid"] is True
        assert result["component_count"] == 2
        assert result["errors"] == []

    async def test_fails_fast_when_a_component_build_fails(self) -> None:
        """Return immediately when any component reports valid: false.

        Downstream components depend on it and will not run, so consuming
        the remainder of the stream yields no new information.
        """
        from lfx.mcp.server import validate_flow

        flow = _flow_with_nodes(3)
        # A fails; B and C would never fire end_vertex in reality. We include
        # trailing events to verify the iterator stops early.
        trailing_marker = MagicMock()
        events = [
            _end_vertex_event("A-1", valid=False, error_message="Missing required field: api_key"),
            trailing_marker,
        ]
        client = _stream_client(events)

        with _patch_validate(flow=flow, client=client):
            result = await validate_flow("flow-1")

        assert result["valid"] is False
        assert result["errors"] == [{"component_id": "A-1", "error": "Missing required field: api_key"}]
        assert result["component_count"] == 1

    async def test_top_level_error_event_returns_failure(self) -> None:
        """If the build itself fails before any vertex runs, return that error."""
        from lfx.mcp.server import validate_flow

        flow = _flow_with_nodes(2)
        events = [
            {"event": "error", "data": {"exception": "Graph has a cycle"}},
        ]
        client = _stream_client(events)

        with _patch_validate(flow=flow, client=client):
            result = await validate_flow("flow-1")

        assert result["valid"] is False
        assert result["errors"] == [{"component_id": "flow", "error": "Graph has a cycle"}]
        assert result["component_count"] == 0

    async def test_build_request_failure_is_surfaced(self) -> None:
        """Network / HTTP failure during the streaming build is reported."""
        from lfx.mcp.server import validate_flow

        flow = _flow_with_nodes(1)

        async def _stream(*_args, **_kwargs):
            msg = "POST /build/flow-1/flow failed (500)"
            raise RuntimeError(msg)
            yield  # pragma: no cover - unreachable, makes this an async generator

        client = MagicMock()
        client.stream_post = _stream

        with _patch_validate(flow=flow, client=client):
            result = await validate_flow("flow-1")

        assert result["valid"] is False
        assert "Build request failed" in result["error"]
        assert result["component_count"] == 0
