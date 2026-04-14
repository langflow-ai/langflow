"""Tests for lfx.mcp.server.validate_flow.

The tool triggers a build and polls /monitor/builds until all components
report back. These tests verify the fast-fail and partial-error-reporting
behaviour so a missing required config doesn't leave callers waiting
the full poll window with no actionable information.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch


def _flow_with_nodes(count: int) -> dict:
    return {
        "id": "flow-1",
        "name": "Test",
        "data": {
            "nodes": [{"id": f"node-{i}"} for i in range(count)],
            "edges": [],
        },
    }


def _build(comp_id: str, *, valid: bool, error: str | None = None) -> dict:
    artifacts = {"error": error} if error is not None else {}
    return {
        "id": f"build-{comp_id}",
        "valid": valid,
        "artifacts": artifacts,
    }


def _patch_validate(*, flow: dict, client: AsyncMock):
    """Patch the dependencies validate_flow reaches out to."""
    from contextlib import contextmanager

    @contextmanager
    def ctx():
        with (
            patch("lfx.mcp.server._get_client", return_value=client),
            patch("lfx.mcp.server._get_flow", new_callable=AsyncMock, return_value=flow),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            yield

    return ctx()


class TestValidateFlow:
    async def test_empty_flow_returns_valid(self) -> None:
        from lfx.mcp.server import validate_flow

        flow = _flow_with_nodes(0)
        client = AsyncMock()

        with _patch_validate(flow=flow, client=client):
            result = await validate_flow("flow-1")

        assert result == {"valid": True, "component_count": 0, "errors": [], "warnings": []}

    async def test_all_components_valid_returns_valid(self) -> None:
        from lfx.mcp.server import validate_flow

        flow = _flow_with_nodes(2)
        client = AsyncMock()
        client.post = AsyncMock(return_value={"job_id": "job-1"})
        client.get = AsyncMock(
            return_value={
                "vertex_builds": {
                    "A-1": [_build("A-1", valid=True)],
                    "B-1": [_build("B-1", valid=True)],
                },
            },
        )

        with _patch_validate(flow=flow, client=client):
            result = await validate_flow("flow-1")

        assert result["valid"] is True
        assert result["component_count"] == 2
        assert result["errors"] == []

    async def test_fails_fast_when_a_component_build_fails(self) -> None:
        """Return immediately when any component reports valid: false.

        Downstream components depend on it and will not run, so polling
        to the timeout yields no new information.
        """
        from lfx.mcp.server import validate_flow

        flow = _flow_with_nodes(3)
        client = AsyncMock()
        client.post = AsyncMock(return_value={"job_id": "job-1"})
        # Monitor reports 1 of 3 builds complete, and that one failed.
        # The other two components will never run because their upstream failed.
        client.get = AsyncMock(
            return_value={
                "vertex_builds": {
                    "A-1": [_build("A-1", valid=False, error="Missing required field: api_key")],
                },
            },
        )

        with _patch_validate(flow=flow, client=client):
            result = await validate_flow("flow-1")

        assert result["valid"] is False
        assert result["errors"] == [{"component_id": "A-1", "error": "Missing required field: api_key"}]
        # Only one GET to /monitor/builds should be needed, not the full 30 polls.
        assert client.get.await_count == 1

    async def test_timeout_includes_errors_from_completed_builds(self) -> None:
        """Surface progress in the timeout response.

        If the build never finishes but some components already completed,
        the timeout response should still report component_count so the
        caller can see how far the build got.
        """
        from lfx.mcp.server import validate_flow

        flow = _flow_with_nodes(5)
        client = AsyncMock()
        client.post = AsyncMock(return_value={"job_id": "job-1"})
        # Only 2 of 5 components complete and all are valid; rest hang.
        client.get = AsyncMock(
            return_value={
                "vertex_builds": {
                    "A-1": [_build("A-1", valid=True)],
                    "B-1": [_build("B-1", valid=True)],
                },
            },
        )

        with _patch_validate(flow=flow, client=client):
            result = await validate_flow("flow-1")

        assert result["valid"] is False
        assert "timed out" in result["error"]
        assert result["component_count"] == 2

    async def test_missing_job_id_short_circuits(self) -> None:
        from lfx.mcp.server import validate_flow

        flow = _flow_with_nodes(1)
        client = AsyncMock()
        client.post = AsyncMock(return_value={})

        with _patch_validate(flow=flow, client=client):
            result = await validate_flow("flow-1")

        assert result == {"valid": False, "error": "Build did not return a job_id"}
