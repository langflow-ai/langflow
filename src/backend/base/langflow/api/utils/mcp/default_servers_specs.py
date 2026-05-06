"""Registry of default MCP servers auto-installed for every Langflow user on startup.

Why this lives in its own module: the orchestrator (default_servers.py) MUST stay agnostic
to which servers exist. To register a new default server, append a single entry to
DEFAULT_MCP_SERVERS — no changes to the orchestrator are required.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DefaultMcpServerConfig:
    """Launch configuration for a single default MCP server.

    Cross-platform — the chosen providers run identically on macOS/Linux/Windows.
    If a future server requires per-OS variation, extend this dataclass then.
    """

    command: str
    args: tuple[str, ...]
    env: dict[str, str]


@dataclass(frozen=True)
class DefaultMcpServerSpec:
    """An entry in the default MCP servers registry. Keyed by server name."""

    description: str
    config: DefaultMcpServerConfig
    # Optional per-server startup timeout (seconds). When set, surfaces in the
    # persisted payload as ``metadata.startup_timeout_seconds`` and overrides
    # the global ``mcp_server_timeout`` for THIS server only.
    # Use this for servers whose first run is legitimately slow (e.g. ``npx -y``
    # downloading a large package on first launch).
    startup_timeout_seconds: int | None = None


# Cross-platform shell-execution config.
# Why DesktopCommander instead of tumf/mcp-shell-server: the previous provider
# imports `pwd` at module load and crashes on Windows. DesktopCommander uses Node
# `child_process.spawn` and runs identically on macOS/Linux/Windows. The launch
# command requires `-y` to skip npx's interactive prompt; this is allowed by
# MCPServerConfig.validate_yes_flag_pattern via the package-pinned allowlist
# ALLOWED_NPX_YES_PACKAGES (see api/v2/schemas.py).
_SHELL_EXECUTION_CONFIG = DefaultMcpServerConfig(
    command="npx",
    args=("-y", "@wonderwhy-er/desktop-commander@latest"),
    env={},
)


DEFAULT_MCP_SERVERS: dict[str, DefaultMcpServerSpec] = {
    "shell-execution": DefaultMcpServerSpec(
        description=("Cross-platform shell execution + filesystem control (wonderwhy-er/desktop-commander)."),
        config=_SHELL_EXECUTION_CONFIG,
        # First run of `npx -y @wonderwhy-er/desktop-commander@latest` can take
        # 30-90s while npm downloads the package + dependencies (Tiptap, sharp,
        # etc.). 60s comfortably covers that without raising the global default.
        startup_timeout_seconds=60,
    ),
}
