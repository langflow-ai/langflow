"""Tests for the behavioral fixes in fix/mcp-server-bugs.

Covers:
- _set_client invalidates shared registry on client change
- login() session isolation (only closes contextvar client)
- create_flow_from_spec raises on validation failure
- validate_flow filters builds by job_id
- update_flow_from_spec rollback on failure
"""

import copy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_client(**overrides):
    client = AsyncMock()
    client.post_event = AsyncMock()
    client.get = AsyncMock(return_value={})
    client.patch = AsyncMock(return_value={})
    client.post = AsyncMock(return_value={})
    client.close = AsyncMock()
    client.login = AsyncMock()
    client.server_url = "http://localhost:7860"
    for k, v in overrides.items():
        setattr(client, k, v)
    return client


def _mock_flow(flow_id="flow-123", nodes=None, edges=None):
    return {
        "id": flow_id,
        "name": "Test Flow",
        "data": {
            "nodes": nodes or [],
            "edges": edges or [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        },
    }


MOCK_REGISTRY = {
    "ChatInput": {
        "display_name": "Chat Input",
        "template": {},
        "output_types": ["Message"],
        "outputs": [{"name": "message", "types": ["Message"]}],
    },
}


# ---------------------------------------------------------------------------
# _set_client: invalidates shared registry when client changes
# ---------------------------------------------------------------------------


class TestSetClientRegistryInvalidation:
    def test_invalidates_registry_on_new_client(self):
        import lfx.mcp.server as srv

        old_client = MagicMock()
        new_client = MagicMock()

        srv._shared_client = old_client
        srv._shared_registry = {"some": "registry"}

        srv._set_client(new_client)

        assert srv._shared_registry is None
        assert srv._shared_client is new_client

    def test_preserves_registry_when_same_client(self):
        import lfx.mcp.server as srv

        client = MagicMock()
        registry = {"some": "registry"}

        srv._shared_client = client
        srv._shared_registry = registry

        srv._set_client(client)

        assert srv._shared_registry is registry
        assert srv._shared_client is client


# ---------------------------------------------------------------------------
# login(): session isolation -- only closes the contextvar client
# ---------------------------------------------------------------------------


class TestLoginSessionIsolation:
    async def test_login_closes_only_session_client(self):
        """login() should close the contextvar client, not the shared one."""
        import lfx.mcp.server as srv

        session_client = _make_mock_client()
        shared_client = _make_mock_client()

        # Set up: session has its own client, shared has a different one
        srv._client_var.set(session_client)
        srv._shared_client = shared_client

        with patch.object(srv, "LangflowClient", return_value=_make_mock_client()):
            await srv.login("user", "pass", "http://localhost:7860")

        session_client.close.assert_called_once()
        shared_client.close.assert_not_called()

    async def test_login_no_close_when_no_session_client(self):
        """login() should not close anything when no contextvar client exists."""
        import lfx.mcp.server as srv

        shared_client = _make_mock_client()

        srv._client_var.set(None)
        srv._shared_client = shared_client

        new_client = _make_mock_client()
        with patch.object(srv, "LangflowClient", return_value=new_client):
            await srv.login("user", "pass", "http://localhost:7860")

        shared_client.close.assert_not_called()

    async def test_login_clears_session_registry_not_shared(self):
        """login() should clear _registry_var but leave _shared_registry alone."""
        import lfx.mcp.server as srv

        srv._client_var.set(None)
        srv._shared_client = _make_mock_client()
        srv._shared_registry = {"cached": "registry"}
        srv._registry_var.set({"session": "registry"})

        new_client = _make_mock_client()
        with patch.object(srv, "LangflowClient", return_value=new_client):
            await srv.login("user", "pass", "http://localhost:7860")

        assert srv._registry_var.get() is None
        # _shared_registry may be invalidated by _set_client if client changes,
        # but login itself should not explicitly clear it


# ---------------------------------------------------------------------------
# create_flow_from_spec: raises RuntimeError when validation fails
# ---------------------------------------------------------------------------


class TestCreateFlowFromSpecValidation:
    async def test_raises_on_validation_failure(self):
        from lfx.mcp.server import create_flow_from_spec

        parsed = {
            "name": "T",
            "description": "",
            "nodes": [{"id": "A", "type": "ChatInput"}],
            "edges": [],
            "config": {},
        }
        created = {"id": "flow-new", "name": "T", "description": ""}
        mock_client = _make_mock_client()
        validation_result = {
            "valid": False,
            "errors": [{"component_id": "X-1", "error": "Missing API key"}],
        }

        with (
            patch("lfx.mcp.server._get_client", return_value=mock_client),
            patch("lfx.mcp.server._get_registry", new_callable=AsyncMock, return_value=MOCK_REGISTRY),
            patch("lfx.mcp.server.parse_flow_spec", return_value=parsed),
            patch("lfx.mcp.server.validate_spec_references"),
            patch("lfx.mcp.server.create_flow", new_callable=AsyncMock, return_value=created),
            patch("lfx.mcp.server.add_component", new_callable=AsyncMock, return_value={"id": "X-1"}),
            patch("lfx.mcp.server.validate_flow", new_callable=AsyncMock, return_value=validation_result),
            patch("lfx.mcp.server.delete_flow", new_callable=AsyncMock),
            pytest.raises(RuntimeError, match=r"Flow validation failed.*Missing API key"),
        ):
            await create_flow_from_spec("nodes:\n  A: ChatInput")

    async def test_skips_validation_when_disabled(self):
        from lfx.mcp.server import create_flow_from_spec

        parsed = {
            "name": "T",
            "description": "",
            "nodes": [{"id": "A", "type": "ChatInput"}],
            "edges": [],
            "config": {},
        }
        created = {"id": "flow-new", "name": "T", "description": ""}
        mock_client = _make_mock_client()

        with (
            patch("lfx.mcp.server._get_client", return_value=mock_client),
            patch("lfx.mcp.server._get_registry", new_callable=AsyncMock, return_value=MOCK_REGISTRY),
            patch("lfx.mcp.server.parse_flow_spec", return_value=parsed),
            patch("lfx.mcp.server.validate_spec_references"),
            patch("lfx.mcp.server.create_flow", new_callable=AsyncMock, return_value=created),
            patch("lfx.mcp.server.add_component", new_callable=AsyncMock, return_value={"id": "X-1"}),
            patch("lfx.mcp.server.validate_flow", new_callable=AsyncMock) as mock_validate,
            patch("lfx.mcp.server.get_flow_info", new_callable=AsyncMock, return_value={"id": "flow-new"}),
        ):
            await create_flow_from_spec("nodes:\n  A: ChatInput", validate=False)

        mock_validate.assert_not_called()


# ---------------------------------------------------------------------------
# validate_flow: filters builds by job_id
# ---------------------------------------------------------------------------


class TestValidateFlowJobIdFiltering:
    async def test_filters_by_job_id(self):
        import asyncio

        from lfx.mcp.server import validate_flow

        mock_client = _make_mock_client()
        flow = _mock_flow(nodes=[{"data": {"id": "comp-1"}}])

        mock_client.post.return_value = {"job_id": "job-current"}

        # Simulate monitor returning builds from both old and current job
        monitor_response = {
            "vertex_builds": {
                "comp-1": [
                    {"build_id": "job-old", "valid": True, "artifacts": {}},
                    {"build_id": "job-current", "valid": True, "artifacts": {}},
                ],
            }
        }
        mock_client.get.return_value = monitor_response

        with (
            patch("lfx.mcp.server._get_client", return_value=mock_client),
            patch("lfx.mcp.server._get_flow", new_callable=AsyncMock, return_value=flow),
            patch.object(asyncio, "sleep", new_callable=AsyncMock),
        ):
            result = await validate_flow("flow-123")

        assert result["valid"] is True
        assert result["component_count"] == 1

    async def test_ignores_stale_builds(self):
        import asyncio

        from lfx.mcp.server import validate_flow

        mock_client = _make_mock_client()
        flow = _mock_flow(nodes=[{"data": {"id": "comp-1"}}])

        mock_client.post.return_value = {"job_id": "job-current"}

        # Monitor only has builds from old job, none matching current
        monitor_response = {
            "vertex_builds": {
                "comp-1": [
                    {"build_id": "job-old", "valid": True, "artifacts": {}},
                ],
            }
        }
        mock_client.get.return_value = monitor_response

        with (
            patch("lfx.mcp.server._get_client", return_value=mock_client),
            patch("lfx.mcp.server._get_flow", new_callable=AsyncMock, return_value=flow),
            patch.object(asyncio, "sleep", new_callable=AsyncMock),
            patch("lfx.mcp.server.logger") as mock_logger,
        ):
            mock_logger.awarning = AsyncMock()
            result = await validate_flow("flow-123")

        assert result["valid"] is False
        assert "timed out" in result["errors"][0]["error"].lower()

    async def test_no_job_id_returns_error(self):
        from lfx.mcp.server import validate_flow

        mock_client = _make_mock_client()
        flow = _mock_flow(nodes=[{"data": {"id": "comp-1"}}])
        mock_client.post.return_value = {}  # No job_id

        with (
            patch("lfx.mcp.server._get_client", return_value=mock_client),
            patch("lfx.mcp.server._get_flow", new_callable=AsyncMock, return_value=flow),
        ):
            result = await validate_flow("flow-123")

        assert result["valid"] is False
        assert result["errors"][0]["error"] == "Build did not return a job_id"

    async def test_errors_list_format_on_component_failure(self):
        import asyncio

        from lfx.mcp.server import validate_flow

        mock_client = _make_mock_client()
        flow = _mock_flow(nodes=[{"data": {"id": "comp-1"}}])

        mock_client.post.return_value = {"job_id": "job-1"}

        monitor_response = {
            "vertex_builds": {
                "comp-1": [
                    {
                        "build_id": "job-1",
                        "valid": False,
                        "artifacts": {"error": "Component X failed"},
                    },
                ],
            }
        }
        mock_client.get.return_value = monitor_response

        with (
            patch("lfx.mcp.server._get_client", return_value=mock_client),
            patch("lfx.mcp.server._get_flow", new_callable=AsyncMock, return_value=flow),
            patch.object(asyncio, "sleep", new_callable=AsyncMock),
        ):
            result = await validate_flow("flow-123")

        assert result["valid"] is False
        assert len(result["errors"]) == 1
        assert result["errors"][0]["component_id"] == "comp-1"
        assert result["errors"][0]["error"] == "Component X failed"


# ---------------------------------------------------------------------------
# update_flow_from_spec: rollback on failure
# ---------------------------------------------------------------------------


class TestUpdateFlowFromSpecRollback:
    async def test_restores_original_data_on_failure(self):
        from lfx.mcp.server import update_flow_from_spec

        mock_client = _make_mock_client()
        original_nodes = [{"id": "n1", "data": {"id": "orig-comp"}}]
        flow = _mock_flow(flow_id="flow-123", nodes=original_nodes)
        original_data = copy.deepcopy(flow["data"])

        parsed = {
            "name": "T",
            "description": "",
            "nodes": [{"id": "A", "type": "ChatInput"}],
            "edges": [],
            "config": {},
        }

        with (
            patch("lfx.mcp.server._get_client", return_value=mock_client),
            patch("lfx.mcp.server._get_flow", new_callable=AsyncMock, return_value=flow),
            patch("lfx.mcp.server._get_registry", new_callable=AsyncMock, return_value=MOCK_REGISTRY),
            patch("lfx.mcp.server.parse_flow_spec", return_value=parsed),
            patch("lfx.mcp.server.validate_spec_references"),
            patch("lfx.mcp.server.add_component", new_callable=AsyncMock, side_effect=RuntimeError("Server error")),
            pytest.raises(RuntimeError, match="Server error"),
        ):
            await update_flow_from_spec("flow-123", "nodes:\n  A: ChatInput")

        # Verify rollback: the last patch call should restore original_data
        patch_calls = mock_client.patch.call_args_list
        last_patch = patch_calls[-1]
        assert last_patch[1]["json_data"]["data"] == original_data

    async def test_emits_settle_event_on_rollback(self):
        from lfx.mcp.server import update_flow_from_spec

        mock_client = _make_mock_client()
        flow = _mock_flow(flow_id="flow-123", nodes=[{"id": "n1", "data": {"id": "orig-comp"}}])

        parsed = {
            "name": "T",
            "description": "",
            "nodes": [{"id": "A", "type": "ChatInput"}],
            "edges": [],
            "config": {},
        }

        with (
            patch("lfx.mcp.server._get_client", return_value=mock_client),
            patch("lfx.mcp.server._get_flow", new_callable=AsyncMock, return_value=flow),
            patch("lfx.mcp.server._get_registry", new_callable=AsyncMock, return_value=MOCK_REGISTRY),
            patch("lfx.mcp.server.parse_flow_spec", return_value=parsed),
            patch("lfx.mcp.server.validate_spec_references"),
            patch("lfx.mcp.server.add_component", new_callable=AsyncMock, side_effect=RuntimeError("fail")),
            pytest.raises(RuntimeError, match="fail"),
        ):
            await update_flow_from_spec("flow-123", "nodes:\n  A: ChatInput")

        # Should have emitted flow_settled before restoring
        mock_client.post_event.assert_called_once()
        args = mock_client.post_event.call_args[0]
        assert args[0] == "flow-123"
        assert args[1] == "flow_settled"

    async def test_success_does_not_rollback(self):
        from lfx.mcp.server import update_flow_from_spec

        mock_client = _make_mock_client()
        flow = _mock_flow(flow_id="flow-123")

        parsed = {
            "name": "Updated",
            "description": "",
            "nodes": [{"id": "A", "type": "ChatInput"}],
            "edges": [],
            "config": {},
        }

        with (
            patch("lfx.mcp.server._get_client", return_value=mock_client),
            patch("lfx.mcp.server._get_flow", new_callable=AsyncMock, return_value=flow),
            patch("lfx.mcp.server._get_registry", new_callable=AsyncMock, return_value=MOCK_REGISTRY),
            patch("lfx.mcp.server.parse_flow_spec", return_value=parsed),
            patch("lfx.mcp.server.validate_spec_references"),
            patch("lfx.mcp.server.add_component", new_callable=AsyncMock, return_value={"id": "X-1"}),
            patch("lfx.mcp.server._create_prompt_template_vars", new_callable=AsyncMock),
            patch("lfx.mcp.server.get_flow_info", new_callable=AsyncMock, return_value={"id": "flow-123"}),
        ):
            result = await update_flow_from_spec("flow-123", "nodes:\n  A: ChatInput")

        assert result["id"] == "flow-123"
        assert result["node_id_map"] == {"A": "X-1"}
        # Only 2 patch calls: initial clear + no rollback
        # First patch clears nodes/edges, no second rollback patch
        patch_calls = [c for c in mock_client.patch.call_args_list if "data" in (c[1].get("json_data") or {})]
        assert len(patch_calls) == 1  # Only the initial clear
