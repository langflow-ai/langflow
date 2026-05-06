"""Registry of default MCP servers auto-installed for every Langflow user on startup.

Why this lives in its own module: the orchestrator (default_servers.py) MUST stay agnostic
to which servers exist. To register a new default server, append a single entry to
DEFAULT_MCP_SERVERS — no changes to the orchestrator are required.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DefaultMcpServerConfig:
    """Per-OS configuration for a single default MCP server."""

    command: str
    args: tuple[str, ...]
    env: dict[str, str]


@dataclass(frozen=True)
class DefaultMcpServerSpec:
    """An entry in the default MCP servers registry. Keyed by server name."""

    description: str
    unix: DefaultMcpServerConfig
    windows: DefaultMcpServerConfig


UNIX_SHELL_ALLOWED_COMMANDS = "ls,cat,pwd,grep,wc,find,echo,head,tail,date,whoami,uname,which,df,ps"
WINDOWS_SHELL_ALLOWED_COMMANDS = "dir,type,echo,where,whoami,hostname,findstr,systeminfo,ver"


DEFAULT_MCP_SERVERS: dict[str, DefaultMcpServerSpec] = {
    "shell-execution": DefaultMcpServerSpec(
        description=("Secure shell execution server (tumf/mcp-shell-server) — whitelisted commands only."),
        unix=DefaultMcpServerConfig(
            command="uvx",
            args=("mcp-shell-server",),
            env={"ALLOW_COMMANDS": UNIX_SHELL_ALLOWED_COMMANDS},
        ),
        windows=DefaultMcpServerConfig(
            command="cmd",
            args=("/c", "uvx", "mcp-shell-server"),
            env={"ALLOW_COMMANDS": WINDOWS_SHELL_ALLOWED_COMMANDS},
        ),
    ),
}
