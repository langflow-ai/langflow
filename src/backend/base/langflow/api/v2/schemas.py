"""Pydantic schemas for v2 API endpoints."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from langflow.logging import logger

# SECURITY: Allowlist of approved MCP stdio commands
# Following Flowise best practice: https://github.com/FlowiseAI/Flowise/blob/main/packages/components/nodes/tools/MCP/CustomMCP/CustomMCP.ts#L166
ALLOWED_MCP_COMMANDS = frozenset(
    {
        "node",
        "python",
        "python3",
        "npx",
        "uvx",
        "docker",
    }
)

# SECURITY: Shell metacharacters that enable command injection
DANGEROUS_SHELL_CHARS = frozenset({";", "|", "&", "$", "`", "<", ">", "(", ")", "\n", "\r"})

# SECURITY: Keywords that enable code execution or package installation
DANGEROUS_KEYWORDS = frozenset(
    {
        "-c",
        "-e",
        "-y",
        "--yes",
        "pip",
        "install",
        "npm",
        "yarn",
        "pnpm",
        "eval",
        "exec",
    }
)

# SECURITY: Environment variables that enable code injection via approved commands.
# Grouped by attack category. All comparisons are case-insensitive.
DANGEROUS_ENV_VARS = frozenset(
    {
        # -- Shared-object / dylib injection (arbitrary native code execution) --
        "ld_preload",
        "ld_library_path",
        "ld_audit",
        "dyld_insert_libraries",
        "dyld_library_path",
        # -- glibc iconv module injection (loads arbitrary .so via iconv) --
        "gconv_path",
        # -- Command resolution override (redirects which binary bash executes) --
        "path",
        # -- Shell startup-script injection (bash executes these before the command) --
        "bash_env",
        "env",
        "bash_func_",  # Shellshock-style function export prefix
        # -- Shell word-splitting / globbing manipulation --
        "ifs",
        "cdpath",
        # -- Node.js code injection --
        "node_options",
        "node_extra_ca_certs",
        # -- Python code injection --
        "pythonstartup",
        "pythonpath",
        # -- Home / config directory redirection (loads attacker-controlled configs) --
        "home",
        "xdg_config_home",
        "xdg_data_home",
        # -- Temp directory redirection --
        "tmpdir",
        "tmp",
        "temp",
        # -- DNS / network manipulation --
        "hostaliases",
        "localdomain",
        "res_options",
        # -- Locale / getconf injection (can load arbitrary .so on some glibc) --
        "getconf_dir",
    }
)

# SECURITY: Docker-specific arguments that break container isolation
DOCKER_DANGEROUS_ARGS = frozenset({"--privileged", "--cap-add"})
DOCKER_DANGEROUS_ARG_PREFIXES = ("--net=", "--network=", "--pid=", "--cap-add=", "--privileged=")


class MCPServerConfig(BaseModel):
    """Pydantic model for MCP server configuration."""

    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    headers: dict[str, str] | None = None
    url: str | None = None

    model_config = ConfigDict(extra="allow")

    @field_validator("command")
    @classmethod
    def validate_command(cls, v: str | None) -> str | None:
        """Validate MCP command against allowlist to prevent command injection.

        This prevents attackers from executing arbitrary commands via the MCP stdio interface.
        Only approved MCP server executables are allowed.

        Args:
            v: The command string to validate

        Returns:
            The validated command string

        Raises:
            ValueError: If the command is not in the allowlist
        """
        if v is None:
            return None

        base_command = _extract_base_command(v)

        if base_command not in ALLOWED_MCP_COMMANDS:
            allowed_list = ", ".join(sorted(ALLOWED_MCP_COMMANDS))
            msg = f"Command '{base_command}' is not allowed for security reasons. Allowed commands: {allowed_list}"
            logger.warning("MCP command rejected: '{}' (full_path='{}')", base_command, v)
            raise ValueError(msg)

        return v

    @field_validator("args")
    @classmethod
    def validate_args(cls, v: list[str] | None) -> list[str] | None:
        """Validate MCP command arguments to prevent shell injection and code execution.

        Blocks shell metacharacters and dangerous flags that could be used for
        command injection, code execution, or package installation attacks.

        Args:
            v: The list of arguments to validate

        Returns:
            The validated arguments list

        Raises:
            ValueError: If any argument contains dangerous patterns
        """
        if v is None:
            return None

        for arg in v:
            for char in DANGEROUS_SHELL_CHARS:
                if char in arg:
                    msg = f"Argument contains dangerous shell metacharacter '{char}': {arg}"
                    logger.warning("MCP argument rejected - shell metacharacter '{}' in arg", char)
                    raise ValueError(msg)

        for arg in v:
            if arg.lower() in DANGEROUS_KEYWORDS:
                msg = f"Argument '{arg}' is not allowed for security reasons"
                logger.warning("MCP argument rejected - dangerous keyword: '{}'", arg)
                raise ValueError(msg)

        return v

    @field_validator("env")
    @classmethod
    def validate_env(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        """Validate environment variables to prevent code injection via approved commands.

        Blocks environment variables that can force approved commands (node, python, etc.)
        to load and execute attacker-controlled code (e.g. LD_PRELOAD, NODE_OPTIONS, PATH).

        Args:
            v: The environment variable dict to validate

        Returns:
            The validated environment dict

        Raises:
            ValueError: If any env var name is in the blocklist
        """
        if v is None:
            return None

        for key in v:
            lower_key = key.lower()
            if lower_key in DANGEROUS_ENV_VARS or lower_key.startswith("bash_func_"):
                msg = f"Environment variable '{key}' is not allowed for security reasons"
                logger.warning("MCP env var rejected: '{}'", key)
                raise ValueError(msg)

        return v

    @model_validator(mode="after")
    def validate_docker_args(self) -> "MCPServerConfig":
        """Block Docker-specific arguments that break container isolation.

        Only applies when the command resolves to ``docker``. Prevents
        ``--privileged``, host-namespace sharing, and capability escalation.

        Returns:
            The validated config

        Raises:
            ValueError: If a dangerous Docker argument is detected
        """
        if not self.command or not self.args:
            return self

        base_command = _extract_base_command(self.command)
        if base_command != "docker":
            return self

        for arg in self.args:
            if arg in DOCKER_DANGEROUS_ARGS or arg.startswith(DOCKER_DANGEROUS_ARG_PREFIXES):
                msg = f"Docker argument '{arg}' is not allowed for security reasons"
                logger.warning("MCP Docker argument rejected: '{}'", arg)
                raise ValueError(msg)

        return self


def _extract_base_command(command: str) -> str:
    r"""Extract the base command name from a possibly fully-qualified path.

    Handles Unix paths (``/usr/bin/node``), Windows paths
    (``C:\\Program Files\\nodejs\\node.exe``), and bare names (``node``).

    Also handles commands with arguments (e.g., "uvx mcp-server-fetch" or
    "npx @scope/package") by extracting only the first token before any
    whitespace, unless it's an actual file path.
    """
    # Check if this looks like an actual file path (not an npm scoped package)
    # File paths either:
    # - Start with / (Unix absolute)
    # - Start with ./ or ../ (relative)
    # - Contain \ (Windows)
    # - Match drive letter pattern like C:\ (Windows absolute)
    drive_letter_len = 3
    is_file_path = (
        command.startswith(("/", "./", "../"))
        or "\\" in command
        or (len(command) >= drive_letter_len and command[1:3] == ":\\")  # Windows drive letter
    )

    command_only = command.split()[0] if not is_file_path and command.strip() else command

    normalized_path = command_only.replace("\\", "/")
    base_command = Path(normalized_path).name

    if base_command.lower().endswith(".exe"):
        base_command = base_command[:-4]

    return base_command
