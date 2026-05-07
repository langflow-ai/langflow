"""Registry of default MCP servers auto-installed for every Langflow user on startup.

Why this lives in its own module: the orchestrator (``default_servers.py``)
must stay agnostic to which servers exist. To register a new default server,
append a single entry to ``DEFAULT_MCP_SERVERS`` — no changes to the
orchestrator are required.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lfx.services.settings.base import Settings

# Sub-directory under ``settings.config_dir`` that the in-tree shell-execution
# MCP server uses as its sandbox. The orchestrator creates this directory
# (mkdir -p) before persisting the spec because the server's own startup
# validation refuses to boot when the dir is missing.
SHELL_SANDBOX_DIRNAME = "mcp-shell-workdir"


@dataclass(frozen=True)
class DefaultMcpServerConfig:
    """Launch configuration for a single default MCP server.

    ``env_factory`` is called at orchestration time with the live
    :class:`Settings` instance. This lets entries inject deployment-specific
    paths (e.g. the langflow ``config_dir``) without hardcoding them at
    module-import time. The default factory returns an empty dict for
    servers that need no env injection.
    """

    command: str
    args: tuple[str, ...]
    env_factory: Callable[[Settings], dict[str, str]] = field(default=lambda _settings: {})


@dataclass(frozen=True)
class DefaultMcpServerSpec:
    """An entry in the default MCP servers registry. Keyed by server name."""

    description: str
    config: DefaultMcpServerConfig
    # Optional per-server startup timeout (seconds). When set, surfaces in the
    # persisted payload as ``metadata.startup_timeout_seconds`` and overrides
    # the global ``mcp_server_timeout`` for THIS server only. Useful for
    # servers whose first run is legitimately slow (e.g. ``npx -y`` packages
    # that download on first launch). The in-tree shell server doesn't need
    # one — it boots in <1s on every supported platform.
    startup_timeout_seconds: int | None = None


def _shell_execution_env(settings: Settings) -> dict[str, str]:
    """Compose the env required by ``lfx.mcp.shell``.

    The shell server's :func:`_read_working_dir` refuses to boot without
    ``LANGFLOW_SHELL_WORKING_DIR`` (PR review #1: no Path.cwd fallback). We
    point it at a per-deployment subdirectory of the langflow ``config_dir``
    so each install gets a stable, isolated sandbox without the operator
    having to set the env var manually.

    The directory is created lazily by the orchestrator before the spec is
    persisted (the server's startup validation is fail-fast on missing dirs).
    """
    sandbox = Path(settings.config_dir) / SHELL_SANDBOX_DIRNAME
    return {"LANGFLOW_SHELL_WORKING_DIR": str(sandbox)}


# In-tree shell-execution server. Why we ship our own (not DesktopCommander or
# any other npm/pypi package): every external package we tried introduced
# cross-platform fragility — npm postinstall scripts blocked by Windows
# antivirus, registry HTTP roundtrips on ``@latest`` tags, ripgrep download
# failures behind corporate proxies, etc. ``lfx.mcp.shell`` runs in the same
# Python interpreter that's already running Langflow, so if Langflow boots,
# the shell server boots.
_SHELL_EXECUTION_CONFIG = DefaultMcpServerConfig(
    command="python",
    args=("-m", "lfx.mcp.shell"),
    env_factory=_shell_execution_env,
)


DEFAULT_MCP_SERVERS: dict[str, DefaultMcpServerSpec] = {
    "shell-execution": DefaultMcpServerSpec(
        description=(
            "Cross-platform shell execution (in-tree lfx.mcp.shell) — Python-based, "
            "no npm/uvx dependency, sandboxed to a per-deployment working directory."
        ),
        config=_SHELL_EXECUTION_CONFIG,
    ),
}
