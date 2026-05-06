"""Tests for the PreloadStep gating of default MCP server installation.

Why this exists: in multi-worker (gunicorn) mode, every worker would otherwise
re-run auto_configure_default_mcp_servers for every user, causing wasted writes
and contention. The PreloadStep enum is the master-once / worker-skip mechanism
shared with AGENTIC_MCP and other heavy boot steps.
"""

import pytest
from langflow.preload import (
    PreloadStep,
    _PreloadState,
    is_step_complete,
    mark_step_complete,
)


class TestPreloadStepEnumIncludesDefaultMcpServers:
    def test_should_define_default_mcp_servers_step(self):
        assert PreloadStep.DEFAULT_MCP_SERVERS.value == "default_mcp_servers"


class TestPreloadStateTracksDefaultMcpServers:
    def test_should_default_to_not_configured(self):
        state = _PreloadState()

        assert state.default_mcp_servers_configured is False

    def test_should_clear_flag_on_reset(self):
        state = _PreloadState()
        state.default_mcp_servers_configured = True

        state.reset()

        assert state.default_mcp_servers_configured is False


class TestMarkAndIsStepComplete:
    @pytest.fixture(autouse=True)
    def _reset_module_state(self):
        """Each test gets a clean preload state — module-level _STATE is shared."""
        from langflow.preload import _STATE

        snapshot = {
            "types_cached": _STATE.types_cached,
            "default_mcp_servers_configured": _STATE.default_mcp_servers_configured,
        }
        try:
            yield
        finally:
            _STATE.types_cached = snapshot["types_cached"]
            _STATE.default_mcp_servers_configured = snapshot["default_mcp_servers_configured"]

    def test_should_report_complete_after_mark_when_prereqs_met(self):
        from langflow.preload import _STATE

        _STATE.types_cached = True  # prereq

        mark_step_complete(PreloadStep.DEFAULT_MCP_SERVERS)

        assert is_step_complete(PreloadStep.DEFAULT_MCP_SERVERS) is True

    def test_should_raise_when_marking_complete_without_types_cached_prereq(self):
        from langflow.preload import _STATE

        _STATE.types_cached = False
        _STATE.default_mcp_servers_configured = False

        with pytest.raises(RuntimeError, match="incomplete prerequisites"):
            mark_step_complete(PreloadStep.DEFAULT_MCP_SERVERS)
