"""Sanity checks on the DEFAULT_MCP_SERVERS registry itself.

These keep the registry honest: every entry must (1) name a command on the
``ALLOWED_MCP_COMMANDS`` allowlist, (2) survive ``MCPServerConfig`` validation
when its env_factory is run with realistic settings, and (3) name the canonical
server slot ``shell-execution`` (the UI label users see — renaming it without
a migration would orphan every existing user's persisted entry).
"""

from __future__ import annotations

from types import SimpleNamespace

from langflow.api.utils.mcp.default_servers_specs import DEFAULT_MCP_SERVERS
from langflow.api.v2.schemas import ALLOWED_MCP_COMMANDS, MCPServerConfig


class TestRegistryShape:
    def test_should_register_shell_execution_slot(self):
        """Pin the user-facing slot name as part of the data contract.

        Existing persisted entries are keyed by it; the PR thread on the
        DesktopCommander pivot decided to keep the name even when the
        underlying provider changes.
        """
        assert "shell-execution" in DEFAULT_MCP_SERVERS

    def test_shell_execution_uses_in_tree_python_module(self):
        """Why python -m lfx.mcp.shell, not npm/uvx.

        Every external package we tried introduced cross-platform fragility
        (see PR #12919 docs). The in-tree server boots from the same Python
        that's already running Langflow, so if Langflow boots, the shell
        server boots.
        """
        spec = DEFAULT_MCP_SERVERS["shell-execution"]
        assert spec.config.command == "python"
        assert spec.config.args == ("-m", "lfx.mcp.shell")


class TestRegistryEntriesSurviveValidation:
    def test_every_entry_passes_mcp_server_config_validation(self, tmp_path):
        """Every entry must build a payload that ``MCPServerConfig`` accepts.

        Otherwise the orchestrator would crash at startup. We use a realistic
        ``config_dir`` (tmp_path) so env_factory paths resolve.
        """
        fake_settings = SimpleNamespace(config_dir=str(tmp_path))
        for name, spec in DEFAULT_MCP_SERVERS.items():
            payload = {
                "command": spec.config.command,
                "args": list(spec.config.args),
                "env": dict(spec.config.env_factory(fake_settings)),
                "metadata": {
                    "description": spec.description,
                    "auto_configured": True,
                    "langflow_internal": True,
                },
            }
            MCPServerConfig.model_validate(payload)  # raises if invalid
            assert spec.config.command in ALLOWED_MCP_COMMANDS, (
                f"registry entry {name!r} uses command {spec.config.command!r} "
                f"which is not in ALLOWED_MCP_COMMANDS — would fail validation"
            )
