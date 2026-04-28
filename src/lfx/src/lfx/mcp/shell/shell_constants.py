"""Constants for the shell MCP server.

Default configuration values, env var names, and pattern tables consumed
by classification and destructive-pattern stages. All values here are
data only — no logic.
"""

from __future__ import annotations

# ---- Env var names -----------------------------------------------------------

ENV_WORKING_DIR = "LANGFLOW_SHELL_WORKING_DIR"
ENV_MODE = "LANGFLOW_SHELL_MODE"
ENV_MAX_TIMEOUT = "LANGFLOW_SHELL_MAX_TIMEOUT"
ENV_MAX_OUTPUT_BYTES = "LANGFLOW_SHELL_MAX_OUTPUT_BYTES"
ENV_MAX_COMMAND_LENGTH = "LANGFLOW_SHELL_MAX_COMMAND_LENGTH"

# ---- Defaults ----------------------------------------------------------------

DEFAULT_MAX_TIMEOUT_SECONDS = 120
DEFAULT_MAX_OUTPUT_BYTES = 16 * 1024
DEFAULT_MAX_COMMAND_LENGTH = 4 * 1024

# ---- Truncation marker -------------------------------------------------------

TRUNCATION_MARKER_TEMPLATE = "\n[... truncated {dropped} bytes]"

# ---- Subcommand splitting ----------------------------------------------------
# Operators that chain commands at shell level. The validation pipeline
# splits the input on these (outside of quoted regions) and validates
# each subcommand independently — otherwise ``ls; rm -rf /`` could slip
# past Stage 2.
SUBCOMMAND_SEPARATORS = (";", "&&", "||", "|", "&")

# ---- Environment allow-list for the spawned subprocess -----------------------
# We strip the parent process env down to this minimal set so secrets
# such as LANGFLOW_API_KEY do not leak into commands the agent runs.

SUBPROCESS_ENV_ALLOWLIST_POSIX = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TZ",
    "TERM",
    "USER",
    "LOGNAME",
    "PWD",
    "SHELL",
)

# Windows depends on a different set of variables for basic shell + binary
# resolution. ``ComSpec`` points at cmd.exe; ``PATHEXT`` controls which
# extensions count as executables; ``SystemRoot``/``WINDIR`` are needed by
# system DLLs; ``USERPROFILE``/``APPDATA``/``LOCALAPPDATA`` replace HOME.
SUBPROCESS_ENV_ALLOWLIST_WINDOWS = (
    "PATH",
    "PATHEXT",
    "ComSpec",
    "SystemRoot",
    "WINDIR",
    "SystemDrive",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "HOMEDRIVE",
    "HOMEPATH",
    "TEMP",
    "TMP",
    "USERNAME",
    "USERDOMAIN",
    "COMPUTERNAME",
    "OS",
    "PROCESSOR_ARCHITECTURE",
    "NUMBER_OF_PROCESSORS",
)


def current_env_allowlist() -> tuple[str, ...]:
    """Return the env allowlist for the current platform."""
    import os as _os

    return SUBPROCESS_ENV_ALLOWLIST_WINDOWS if _os.name == "nt" else SUBPROCESS_ENV_ALLOWLIST_POSIX
