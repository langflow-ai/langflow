"""Resolve the FileSystem sandbox root for the Langflow Assistant.

The shipped LangflowAssistant flow embeds a FileSystemTool whose `root_path`
must be a non-empty, OS-appropriate directory at runtime. Hardcoding any
value (developer's home, /tmp, etc.) breaks portability across macOS, Linux,
Windows and Docker, so the path is resolved here.

This is a transitional shim that goes away once PR #13031
(per-user FileSystemTool isolation) lands. It is forward-compatible with
that PR's contract:

    Env var:  LANGFLOW_FS_TOOL_BASE_DIR  (same name PR #13031 uses)
    Default:  ~/.langflow/fs_tool/fs_sandbox  (same default PR #13031 uses)

Resolution order:
    1. If the isolation module from PR #13031 is importable, return None —
       the FileSystemTool now self-resolves a per-user namespace and any
       injected root_path would be misinterpreted as a relative sub_path.
    2. LANGFLOW_FS_TOOL_BASE_DIR env var (after expanduser + strip), if set.
    3. ~/.langflow/fs_tool/fs_sandbox.

The directory is created (idempotently) before the path is returned so the
component never sees a non-existent root.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

BASE_DIR_ENV = "LANGFLOW_FS_TOOL_BASE_DIR"
# Sub-path under the user's home, mirrored from PR #13031's default.
DEFAULT_BASE_SUBPATH = Path(".langflow") / "fs_tool" / "fs_sandbox"
# When this module exists in the runtime, PR #13031's per-user isolation
# is active and the FileSystemTool resolves its own sandbox.
ISOLATION_MODULE = "lfx.components.tools._filesystem_isolation"


def _isolation_module_present() -> bool:
    """Return True when PR #13031's isolation module is importable.

    Uses ``find_spec`` (no side effects) so we can detect the new component
    contract without forcing imports on processes that don't need it.
    """
    return importlib.util.find_spec(ISOLATION_MODULE) is not None


def resolve_assistant_fs_root() -> Path | None:
    """Return the resolved sandbox root path, or None when injection is unneeded.

    Returns None when PR #13031's isolation module is present — in that case
    the FileSystemTool component derives its own per-user namespace and
    injecting a value into ``root_path`` would corrupt that resolution.

    Otherwise returns an absolute path to a writable directory (creating it
    if missing). The mkdir is idempotent and intentional — callers downstream
    require the path to exist.
    """
    if _isolation_module_present():
        return None

    raw = os.environ.get(BASE_DIR_ENV, "").strip()
    candidate = Path(raw).expanduser() if raw else Path.home() / DEFAULT_BASE_SUBPATH

    resolved = candidate.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved
