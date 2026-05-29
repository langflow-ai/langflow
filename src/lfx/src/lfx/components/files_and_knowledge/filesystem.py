"""Sandboxed filesystem tool component exposing 5 file I/O tools to agents."""

from __future__ import annotations

import contextvars
import json
import os
import re
from pathlib import Path, PureWindowsPath
from typing import TYPE_CHECKING

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from lfx.components.files_and_knowledge._filesystem_isolation import (
    IsolationConfig,
    load_isolation_config,
)
from lfx.components.files_and_knowledge._filesystem_namespace import (
    compute_user_namespace,
    load_or_create_pepper,
)
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, StrInput
from lfx.io import Output
from lfx.schema.data import Data
from lfx.services.deps import get_settings_service

if TYPE_CHECKING:
    from lfx.field_typing import Tool

# Sub-directory under <BASE> used when AUTO_LOGIN=True. Stays parallel to
# users/<hash>/ so flipping AUTO_LOGIN at deploy-time does not mix file trees.
SHARED_NAMESPACE = "shared"


# L2 binding atomicity: the binding check captures `user_id` once at the
# start of every tool invocation; subsequent reads of `_resolve_user_id`
# during the same call (in _validate_root, _validate_path, etc.) read this
# pinned value instead of re-resolving. Without this pin, a concurrent
# mutation of `self._user_id` between the binding check and the path
# resolution would let an attacker write into a foreign user's namespace
# while the check still passed for the original user.
_pinned_user_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_filesystem_pinned_user_id",
    default=None,
)


# Reserved on-disk segments inside every user namespace.
#
# `.lfsig` is the forward hook for an HMAC sidecar tree (L3 in the FS plan).
# `.components` is the storage location for user-generated component code
# (written by a privileged backend helper after Layer-2 code validation;
# read by the registry overlay so build_flow / search_components see the
# user's custom types). Allowing the agent's FS tools to touch either
# directory would either poison a security-critical namespace or let the
# agent plant arbitrary code into its own executable namespace.
#
# Kept as a singular constant for backwards-compat with prior message text
# ("Path component '.lfsig' is reserved") and as a tuple for the actual
# check — both names point at the same casefold set.
RESERVED_SEGMENT = ".lfsig"
RESERVED_SEGMENTS: tuple[str, ...] = (".lfsig", ".components")


def _default_config_dir() -> Path:
    """Pick a sensible config dir when no env var is set.

    Operators set ``LANGFLOW_FS_TOOL_BASE_DIR`` / ``LANGFLOW_FS_TOOL_PEPPER_PATH``
    explicitly in any real deployment; this fallback exists so the OSS desktop
    install just works without any setup.
    """
    return Path.home() / ".langflow" / "fs_tool"


MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
BINARY_SNIFF_BYTES = 8 * 1024
GLOB_RESULT_LIMIT = 100
# Hard upper bound on the number of glob matches collected before truncation.
# Without scanning past `GLOB_RESULT_LIMIT`, the first big branch hit by
# `os.scandir` order fills the cap and entire nested branches are silently
# dropped (BUG-02 / T2-001). The ceiling bounds memory/time on pathological
# trees while leaving headroom to surface diverse branches to the agent.
GLOB_SCAN_CEILING = GLOB_RESULT_LIMIT * 10
GREP_LINE_LIMIT = 250
GREP_OUTPUT_MODES = ("files_with_matches", "content", "count")
# Hard ceiling on user-supplied regex pattern length. Long patterns are a
# common ReDoS vector and have no legitimate need against single text lines.
GREP_PATTERN_MAX_LEN = 1024
# Skip regex matching on lines longer than this — exponential backtracking
# requires non-trivial input length, and oversized lines tend to be data
# blobs (minified JS/JSON) rather than meaningful matches.
GREP_REGEX_LINE_MAX_LEN = 4096
# Cap on total lines scanned per file in regex mode, regardless of matches.
# Bounds the work even for benign-looking patterns on large files.
GREP_REGEX_LINES_PER_FILE = 50_000

# Heuristic ReDoS detector.
#
# Stdlib `re` has no native timeout; we cannot kill a runaway match because
# the engine holds the GIL. Instead we reject patterns whose structure makes
# catastrophic backtracking possible BEFORE compiling them.
#
# The classic ReDoS shape is a nested unbounded quantifier — a parenthesized
# group whose body is itself quantifiable, followed by an outer `+`/`*`/`{n,}`.
# Examples: `(a+)+`, `(a*)*`, `(.*)+`, `(\w+)+`, `(a|aa)+`. We reject any
# group that ends with `)+`/`)*`/`){n,}` AND whose body contains an
# unescaped quantifier (`+`, `*`, `{n,}`) or alternation (`|`).
#
# This is intentionally conservative — it rules out some safe patterns
# (`(ab)+` is fine; `(ab+)+` is not, but our rule rejects both). Users who
# need those patterns can rewrite without the outer quantifier. Trading a
# bit of expressiveness for a hard guarantee that no user pattern can
# DoS the worker.
_REDOS_GROUP = re.compile(
    r"""
    \(                          # outer group open
    (?:                         # body of the group:
        (?:\\.)                 #   - any escaped char (so \+ etc. don't trip us)
        | [^()]                 #   - or any non-paren char
    )*?
    (?:                         # ... that contains at least one of:
        (?<!\\)[+*]             #   unescaped + or *
        | (?<!\\)\{\d+,\d*\}    #   {n,} or {n,m}
        | (?<!\\)\|             #   alternation
    )
    (?:\\.|[^()])*              # ...followed by more body
    \)                          # outer group close
    [+*]                        # outer unbounded quantifier
    """,
    re.VERBOSE,
)


def _looks_like_redos(pattern: str) -> bool:
    """Return True if `pattern` matches a known catastrophic-backtracking shape."""
    return bool(_REDOS_GROUP.search(pattern))


# Windows portability rules (applied on every host OS so flows authored on
# macOS/Linux do not silently break when run on Windows). Pure-string checks.
_WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
)
# Note: ':' is NOT included — drive letters (C:) are valid; bare ':' inside a
# basename will be caught by the OS at write time anyway.
_WINDOWS_FORBIDDEN_CHARS = frozenset('<>"|?*')

# Deny-list: even when a path lies inside `root_path`, refuse access to
# basenames or path components that match well-known credential / secret
# patterns. This is the "default-deny inside an allowed root" pattern from
# Claude Code Sandboxing — it limits the blast radius of a flow author who
# misconfigures `root_path` to cover $HOME or the project root. Pure-string
# checks; runs before any I/O so the agent never observes the file's
# existence, contents, or absence-vs-denied distinction beyond the error
# string itself.
#
# Match semantics (all case-insensitive):
#   * literals — exact basename match (e.g. `.env`, `.netrc`)
#   * prefixes — basename startswith (e.g. `id_rsa`, `id_rsa.pub`, `id_ed25519`)
#   * suffixes — basename endswith (e.g. `cert.pem`, `private.key`)
#   * fragments — any DIRECTORY component equals the fragment (e.g. `.ssh/`,
#     `.aws/config`); the basename itself is not matched against fragments.
_DENY_BASENAME_LITERALS = frozenset({".env", ".netrc", ".pgpass", ".htpasswd", "authorized_keys"})
_DENY_BASENAME_PREFIXES = ("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "credentials")
_DENY_BASENAME_SUFFIXES = (".pem", ".key", ".pfx", ".p12")
_DENY_PATH_FRAGMENTS = frozenset({".ssh", ".aws", ".gnupg", ".docker", ".kube", ".git"})


def _looks_binary(head: bytes) -> bool:
    return b"\x00" in head


def _check_hardlink(candidate: Path) -> str | None:
    """Return an error string when ``candidate`` is a multi-hardlink file.

    Why we refuse multi-hardlink files: an attacker with write access to a
    location outside the sandbox can pre-create an extra hardlink pointing
    at a sandbox path. Subsequent writes through the sandbox name then
    also clobber the external name, defeating the boundary. There is no
    legitimate flow that depends on a multi-link inode inside the
    sandbox, so refusing fails closed.

    Restricted to **regular files**: directories on POSIX always have
    ``st_nlink >= 2`` (`.`, plus one per subdirectory entry), so checking
    them would refuse every nested path. Symlinks fall through to the
    boundary check and the no-follow helpers. Non-existent paths return
    ``None`` — creation is handled by the O_NOFOLLOW write helper.
    """
    try:
        st = os.lstat(candidate)
    except FileNotFoundError:
        return None
    except OSError as exc:
        return f"Cannot stat path: {exc.strerror or exc}"
    import stat as _stat_module

    if _stat_module.S_ISREG(st.st_mode) and st.st_nlink > 1:
        return f"Refusing to operate on multi-hardlink file (nlink={st.st_nlink})"
    return None


def _write_bytes_no_follow(target: Path, data: bytes) -> None:
    """Write ``data`` to ``target`` without following symlinks.

    Uses ``O_NOFOLLOW`` on POSIX so that any symlink at ``target`` —
    including one created by a concurrent process between path
    validation and this open — raises ``ELOOP`` and fails the write
    closed. On Windows the flag is unavailable; we lstat and refuse if
    the target is already a symlink (best-effort against the non-racy
    attacker).

    The file is created with mode 0600 so that, even on shared hosts,
    other users cannot read it without explicit operator action.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    elif target.is_symlink():  # pragma: no cover — Windows-only branch
        msg = f"Refusing to write through symlink: {target}"
        raise PermissionError(msg)
    fd = os.open(str(target), flags, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def _read_bytes_no_follow(target: Path) -> bytes:
    """Read the entire file at ``target`` without following symlinks.

    Same TOCTOU rationale as ``_write_bytes_no_follow``: with
    ``O_NOFOLLOW`` the open fails if a symlink was substituted between
    path validation and this read. Reads up to ``MAX_FILE_SIZE_BYTES``
    in a single syscall — the caller has already enforced the cap via
    ``stat().st_size`` checks.
    """
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    elif target.is_symlink():  # pragma: no cover — Windows-only branch
        msg = f"Refusing to read through symlink: {target}"
        raise PermissionError(msg)
    fd = os.open(str(target), flags)
    try:
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1 << 20)  # 1 MiB per syscall
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def _read_head_no_follow(target: Path, n: int) -> bytes:
    """Read the first ``n`` bytes of ``target`` without following symlinks.

    Used for the binary-content sniff before deciding whether a file is
    safe to surface as text — the same TOCTOU defence applies.
    """
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    elif target.is_symlink():  # pragma: no cover — Windows-only branch
        msg = f"Refusing to read through symlink: {target}"
        raise PermissionError(msg)
    fd = os.open(str(target), flags)
    try:
        return os.read(fd, n)
    finally:
        os.close(fd)


def _check_windows_portability(path: str) -> str | None:
    """Return a human-readable error if the path has Windows-portability issues.

    Why we run this on every host: paths that work on macOS/Linux can silently
    fail on Windows (reserved names, forbidden characters, trailing dot/space
    silently stripped by the OS). The agent should see the same structured
    error regardless of where the flow runs.
    """
    # Use PureWindowsPath to parse separators consistently — it splits on both
    # `/` and `\` and exposes drive markers as components ending in '\'.
    for component in PureWindowsPath(path).parts:
        # Skip root markers ('\\', '/', 'C:\\') and relative markers ('.', '..')
        if component.endswith(("\\", "/")) or component in (".", ".."):
            continue
        # Reserved name (case-insensitive, with or without extension).
        stem = component.split(".", 1)[0].upper()
        if stem in _WINDOWS_RESERVED_NAMES:
            return f"Path component {component!r} is a Windows reserved name"
        # Forbidden characters in basename.
        bad = sorted(set(component) & _WINDOWS_FORBIDDEN_CHARS)
        if bad:
            return f"Path component {component!r} contains forbidden character(s): {bad}"
        # Trailing dot or space — Windows silently strips them.
        if component != component.rstrip(". "):
            return f"Path component {component!r} has trailing dot or space (silently stripped on Windows)"
    return None


class _ReadFileArgs(BaseModel):
    path: str = Field(..., description="Path to the file, relative to the sandbox root.")
    offset: int | None = Field(default=None, description="1-based line number to start reading from.")
    limit: int | None = Field(default=None, description="Maximum number of lines to return.")


class _WriteFileArgs(BaseModel):
    path: str = Field(..., description="Path to the file, relative to the sandbox root.")
    content: str = Field(..., description="Text content to write. Overwrites existing file.")


class _EditFileArgs(BaseModel):
    path: str = Field(..., description="Path to the file, relative to the sandbox root.")
    old_string: str = Field(..., description="Exact string to replace.")
    new_string: str = Field(..., description="Replacement string.")
    replace_all: bool = Field(default=False, description="Replace every occurrence instead of failing on ambiguity.")


class _GlobSearchArgs(BaseModel):
    pattern: str = Field(..., description="Glob pattern, e.g. '**/*.py'.")
    path: str | None = Field(default=None, description="Optional sub-directory to scope the search.")


class _GrepSearchArgs(BaseModel):
    pattern: str = Field(..., description="Pattern to match against file contents (literal substring by default).")
    path: str | None = Field(default=None, description="Optional file or directory to scope the search.")
    glob: str | None = Field(default=None, description="Optional glob filter, e.g. '*.py'.")
    case_insensitive: bool = Field(default=False, description="If true, the pattern is matched case-insensitively.")
    output_mode: str = Field(
        default="files_with_matches",
        description="One of 'files_with_matches', 'content', 'count'.",
    )
    is_regex: bool = Field(
        default=False,
        description=(
            "Treat `pattern` as a Python regex. Disabled by default — when enabled, "
            "patterns are validated against catastrophic-backtracking shapes "
            "(rejecting e.g. `(a+)+` or `(.*)*`) and oversized lines are skipped."
        ),
    )


class FileSystemToolComponent(Component):
    display_name = "File System"
    description = "Sandboxed filesystem access for agents."
    icon = "folder"
    name = "FileSystemTool"

    # Enables the "Tool Mode" toggle on the node header. When ON the framework
    # calls _get_tools() and emits a Toolset output that connects to an Agent's
    # "Tools" handle. When OFF, the JSON metadata output is the only handle.
    add_tool_output = True

    inputs = [
        StrInput(
            name="root_path",
            display_name="Workspace Sub-path",
            required=False,
            value="",
            info=(
                "Sub-folder inside your sandboxed workspace. Leave empty to use the "
                "root of the workspace.\n\n"
                "Resolves under <BASE_DIR>/shared/<sub_path>/ when AUTO_LOGIN=True "
                "(single-user / desktop) or under <BASE_DIR>/users/<your-namespace>/<sub_path>/ "
                "when AUTO_LOGIN=False (multi-user, per-user isolation). "
                "BASE_DIR is operator-controlled via LANGFLOW_FS_TOOL_BASE_DIR."
            ),
        ),
        BoolInput(
            name="read_only",
            display_name="Read Only",
            value=False,
            advanced=True,
            info="If true, write and edit operations are disabled.",
        ),
        # Synthetic hidden input. Exists ONLY to make the "Tool Mode" toggle
        # appear on the node header — see frontend rule in
        # `src/frontend/src/CustomNodes/helpers/parameter-filtering.ts :: isHidden`
        # and the backend gate in `src/lfx/src/lfx/template/utils.py` (toggle
        # visibility = `any(input.tool_mode for input in inputs)`).
        # `show=False` keeps it hidden from the config UI; `tool_mode=True`
        # would otherwise hide a real input in tool mode (see same isHidden
        # rule), so we keep root_path / read_only WITHOUT tool_mode=True so
        # they remain user-editable when the toggle is on. _get_tools() ignores
        # this field — each StructuredTool has its own per-operation schema.
        StrInput(
            name="tool_mode_trigger",
            display_name="",
            show=False,
            tool_mode=True,
            required=False,
        ),
    ]

    outputs = [
        Output(
            display_name="JSON",
            name="metadata",
            method="build_metadata",
            types=["Data"],
        ),
    ]

    def build_metadata(self) -> Data:
        """Return introspective metadata about the sandbox. No file I/O.

        Surfaces the live AUTO_LOGIN-driven layout so flow authors can see
        whether per-user scoping is active and where their files actually land
        without needing to grep env vars.
        """
        registered = ["read_file", "glob_search", "grep_search"]
        if not self.read_only:
            registered.extend(["write_file", "edit_file"])

        auto_login = self._resolve_auto_login()
        user_id = self._resolve_user_id()
        if auto_login:
            mode = "shared"
        elif user_id:
            mode = "isolated"
        else:
            mode = "refused"

        # Best-effort effective_root resolution. We never raise from metadata —
        # if the policy refuses the call (AUTO_LOGIN=False without user_id,
        # unwritable BASE_DIR, etc.) we surface the reason instead of crashing
        # the node preview / Agent build pipeline.
        effective_root: str | None
        resolution_error: str | None = None
        try:
            effective_root = str(self._validate_root())
        except Exception as exc:  # noqa: BLE001 — metadata must never raise
            effective_root = None
            resolution_error = str(exc) or exc.__class__.__name__

        return Data(
            data={
                "root_path": self.root_path,
                "read_only": bool(self.read_only),
                "tools_registered": registered,
                "auto_login": auto_login,
                "mode": mode,
                "effective_root": effective_root,
                "resolution_error": resolution_error,
            }
        )

    async def _get_tools(self) -> list[Tool]:
        """Tool Mode entrypoint. Called by Component.to_toolkit()."""
        # Capture the bound user_id ONCE per build. Each StructuredTool closure
        # below re-checks the live ``self._user_id`` against this value at call
        # time, so a tool issued for user A cannot be invoked after the
        # component has been reused for user B (defense for L2 in the plan).
        bound_user_id = self._resolve_user_id()
        tools: list[Tool] = [
            self._make_read_tool(bound_user_id=bound_user_id),
            self._make_glob_tool(bound_user_id=bound_user_id),
            self._make_grep_tool(bound_user_id=bound_user_id),
        ]
        if not self.read_only:
            tools.append(self._make_write_tool(bound_user_id=bound_user_id))
            tools.append(self._make_edit_tool(bound_user_id=bound_user_id))
        return tools

    def _user_binding_error(self, bound_user_id: str | None) -> dict | None:
        """Return a structured error dict if the live user_id has shifted.

        In shared mode (AUTO_LOGIN=True) user_id is not part of the security
        boundary, so the binding check is a no-op. In isolated mode we compare
        the captured user_id to the live one and refuse if they diverge —
        defends against a worker pool reusing one component instance across
        sessions for different users.
        """
        _, err = self._user_binding_check(bound_user_id)
        return err

    def _user_binding_check(self, bound_user_id: str | None) -> tuple[str | None, dict | None]:
        """Atomic capture of the user_id for the current invocation.

        Returns ``(captured_user_id, error_or_none)``. The captured value is
        the SINGLE read of ``_resolve_user_id`` for this call; downstream
        path-resolution code MUST reuse it (via the ContextVar pin) instead
        of reading again — otherwise a mid-call mutation of ``self._user_id``
        would let a write land in a different user's namespace while this
        check still passed for the original user.
        """
        # When force_isolation is set, every invocation MUST carry the user_id
        # that was captured at binding time — AUTO_LOGIN does not relax the
        # check here, otherwise the per-user root in _validate_root would be
        # reached with the wrong identity.
        if getattr(self, "_force_isolation", False):
            current = self._resolve_user_id()
            if current and current == bound_user_id:
                return current, None
            return None, {
                "error": (
                    "tool/user-id mismatch: this tool was bound to a different user session and cannot be reused"
                ),
            }
        if self._resolve_auto_login():
            return bound_user_id, None
        current = self._resolve_user_id()
        if current == bound_user_id:
            return current, None
        return None, {
            "error": ("tool/user-id mismatch: this tool was bound to a different user session and cannot be reused"),
        }

    def _make_read_tool(self, *, bound_user_id: str | None) -> StructuredTool:
        def _run(path: str, offset: int | None = None, limit: int | None = None) -> str:
            captured, err = self._user_binding_check(bound_user_id)
            if err is not None:
                return json.dumps(err)
            token = _pinned_user_id_var.set(captured)
            try:
                return json.dumps(self._read_file(path, offset=offset, limit=limit))
            finally:
                _pinned_user_id_var.reset(token)

        return StructuredTool.from_function(
            name="read_file",
            description=(
                "Read a text file from the sandboxed workspace. "
                "Returns content prefixed with line numbers plus metadata "
                "(total_lines, start_line, num_lines)."
            ),
            func=_run,
            args_schema=_ReadFileArgs,
            tags=["read_file"],
        )

    def _make_write_tool(self, *, bound_user_id: str | None) -> StructuredTool:
        def _run(path: str, content: str) -> str:
            captured, err = self._user_binding_check(bound_user_id)
            if err is not None:
                return json.dumps(err)
            token = _pinned_user_id_var.set(captured)
            try:
                return json.dumps(self._write_file(path, content))
            finally:
                _pinned_user_id_var.reset(token)

        return StructuredTool.from_function(
            name="write_file",
            description="Create or overwrite a text file inside the sandboxed workspace.",
            func=_run,
            args_schema=_WriteFileArgs,
            tags=["write_file"],
        )

    def _make_edit_tool(self, *, bound_user_id: str | None) -> StructuredTool:
        def _run(path: str, old_string: str, new_string: str, *, replace_all: bool = False) -> str:
            captured, err = self._user_binding_check(bound_user_id)
            if err is not None:
                return json.dumps(err)
            token = _pinned_user_id_var.set(captured)
            try:
                return json.dumps(
                    self._edit_file(path, old_string=old_string, new_string=new_string, replace_all=replace_all)
                )
            finally:
                _pinned_user_id_var.reset(token)

        return StructuredTool.from_function(
            name="edit_file",
            description=(
                "Edit a text file by replacing an exact old_string with new_string. "
                "Fails on ambiguous matches unless replace_all=True."
            ),
            func=_run,
            args_schema=_EditFileArgs,
            tags=["edit_file"],
        )

    def _make_glob_tool(self, *, bound_user_id: str | None) -> StructuredTool:
        def _run(pattern: str, path: str | None = None) -> str:
            captured, err = self._user_binding_check(bound_user_id)
            if err is not None:
                return json.dumps(err)
            token = _pinned_user_id_var.set(captured)
            try:
                return json.dumps(self._glob_search(pattern, path=path))
            finally:
                _pinned_user_id_var.reset(token)

        return StructuredTool.from_function(
            name="glob_search",
            description=(
                "List files matching a glob pattern inside the sandboxed workspace. "
                f"Results are truncated at {GLOB_RESULT_LIMIT} entries."
            ),
            func=_run,
            args_schema=_GlobSearchArgs,
            tags=["glob_search"],
        )

    def _make_grep_tool(self, *, bound_user_id: str | None) -> StructuredTool:
        def _run(
            pattern: str,
            path: str | None = None,
            glob: str | None = None,
            *,
            case_insensitive: bool = False,
            output_mode: str = "files_with_matches",
            is_regex: bool = False,
        ) -> str:
            captured, err = self._user_binding_check(bound_user_id)
            if err is not None:
                return json.dumps(err)
            token = _pinned_user_id_var.set(captured)
            try:
                return json.dumps(
                    self._grep_search(
                        pattern,
                        path=path,
                        glob=glob,
                        case_insensitive=case_insensitive,
                        output_mode=output_mode,
                        is_regex=is_regex,
                    )
                )
            finally:
                _pinned_user_id_var.reset(token)

        return StructuredTool.from_function(
            name="grep_search",
            description=(
                "Search file contents. Default is literal substring match (safe for any pattern); "
                "set is_regex=True to opt into Python regex. Patterns with nested unbounded "
                "quantifiers (e.g. (a+)+) are rejected to prevent catastrophic backtracking. "
                "output_mode: 'files_with_matches' (default), 'content', or 'count'. "
                f"Content mode is capped at {GREP_LINE_LIMIT} lines."
            ),
            func=_run,
            args_schema=_GrepSearchArgs,
            tags=["grep_search"],
        )

    def _resolve_user_id(self) -> str | None:
        """Best-effort lookup of the calling user's id.

        The Component base class populates ``_user_id`` during instantiation,
        and the property cascades to ``self.graph.user_id``. In tests there is
        no graph; in scheduled/anonymous runs there is no user_id at all. We
        treat all of those as "anonymous" — the isolation mode decides what to
        do with that information.

        Why we filter ``"none"`` / ``"null"``: Langflow's ``PlaceholderGraph``
        stringifies a missing user as ``"None"`` rather than the Python
        ``None`` value, so a naive truthiness check would mistake "no user" for
        a real user named "None" and create a spurious shared namespace.

        L2 binding atomicity: when a tool invocation is in progress, the
        pinned ContextVar value takes precedence so every read inside the
        same call sees the user_id captured at the binding check — even if
        ``self._user_id`` is mutated mid-call by a reused component instance.
        """
        pinned = _pinned_user_id_var.get()
        if pinned is not None:
            return pinned
        candidates: list[object | None] = [getattr(self, "_user_id", None)]
        graph = getattr(self, "graph", None)
        if graph is not None:
            candidates.append(getattr(graph, "user_id", None))

        for value in candidates:
            if value is None:
                continue
            cleaned = str(value).strip()
            if not cleaned or cleaned.lower() in {"none", "null"}:
                continue
            return cleaned
        return None

    def _isolation_config(self) -> IsolationConfig:
        """Read the on-disk layout config from the environment on every call.

        Re-read intentionally: tests and live operators tweak env vars between
        runs; caching would create stale-config bugs that are painful to
        diagnose. The cost is a handful of dict lookups per tool call.
        """
        return load_isolation_config(env=os.environ, default_config_dir=_default_config_dir())

    def _resolve_auto_login(self) -> bool:
        """Return AUTO_LOGIN from the live settings service.

        Defaults to True when the settings service is unavailable (tests, very
        early bootstrap) — mirrors the platform-wide default and keeps the
        component usable in lightweight contexts. Tests can override this
        method per-instance to pin the desired mode.
        """
        try:
            settings_service = get_settings_service()
        except Exception:  # noqa: BLE001 — service registry may not be ready
            return True
        if settings_service is None:
            return True
        try:
            return bool(settings_service.auth_settings.AUTO_LOGIN)
        except AttributeError:
            return True

    def _validate_root(self) -> Path:
        """Resolve and authorize the effective sandbox root.

        Dispatch:
          - ``_force_isolation=True``    → <BASE>/users/<hash(user_id)>/<sub_path>
          - AUTO_LOGIN=True              → <BASE>/shared/<sub_path>
          - AUTO_LOGIN=False + user_id   → <BASE>/users/<hash(user_id)>/<sub_path>
          - any mode with no user_id     → PermissionError (caught by callers)

        ``_force_isolation`` exists for callers that carry an authenticated
        user identity and need per-user isolation regardless of the global
        AUTO_LOGIN flag (e.g. the agentic file router + the agent's write
        tools). It defaults to False so other call sites keep their current
        AUTO_LOGIN-driven behavior unchanged.
        """
        config = self._isolation_config()

        if getattr(self, "_force_isolation", False):
            user_id = self._resolve_user_id()
            if not user_id:
                msg = "FileSystemTool requires an authenticated user when _force_isolation is set"
                raise PermissionError(msg)
            return self._isolated_user_root(config=config, user_id=user_id)

        if self._resolve_auto_login():
            return self._shared_root(config=config)

        user_id = self._resolve_user_id()
        if not user_id:
            msg = "FileSystemTool requires an authenticated user when AUTO_LOGIN=False"
            raise PermissionError(msg)
        return self._isolated_user_root(config=config, user_id=user_id)

    def _shared_root(self, *, config: IsolationConfig) -> Path:
        """Materialize ``<base>/shared/<sub_path>`` and verify the boundary.

        Why a fixed ``shared/`` prefix (and not just ``base_dir`` directly):
        keeps the on-disk layout symmetric with isolated mode (``users/<hash>/``)
        so flipping AUTO_LOGIN at deploy time never mixes the two trees.
        """
        shared_root = (config.base_dir / SHARED_NAMESPACE).resolve()
        try:
            shared_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            msg = (
                f"Cannot create shared workspace at {shared_root}: "
                f"{exc.strerror or exc}. "
                f"Check that LANGFLOW_FS_TOOL_BASE_DIR ({config.base_dir}) is writable "
                f"by the Langflow process user."
            )
            raise PermissionError(msg) from exc

        sub_raw = (self.root_path or "").strip()
        sub = sub_raw.lstrip("/\\")
        candidate = (shared_root / sub).resolve() if sub else shared_root
        if not candidate.is_relative_to(shared_root):
            msg = f"sub_path {self.root_path!r} escapes shared workspace"
            raise PermissionError(msg)
        try:
            candidate.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            msg = f"Cannot create sub-path {candidate}: {exc.strerror or exc}"
            raise PermissionError(msg) from exc
        return candidate

    def _isolated_user_root(self, *, config: IsolationConfig, user_id: str) -> Path:
        """Materialize ``<base>/users/<hash(user_id)>/<sub_path>`` and verify the boundary."""
        try:
            pepper = load_or_create_pepper(config.pepper_path)
        except OSError as exc:
            msg = (
                f"Cannot access pepper file at {config.pepper_path}: "
                f"{exc.strerror or exc}. "
                f"Check that LANGFLOW_FS_TOOL_PEPPER_PATH points to a writable location."
            )
            raise PermissionError(msg) from exc
        namespace = compute_user_namespace(user_id, pepper=pepper)
        user_root = (config.base_dir / namespace).resolve()
        try:
            user_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            msg = (
                f"Cannot create user namespace at {user_root}: "
                f"{exc.strerror or exc}. "
                f"Check that LANGFLOW_FS_TOOL_BASE_DIR ({config.base_dir}) is writable "
                f"by the Langflow process user."
            )
            raise PermissionError(msg) from exc

        sub_raw = (self.root_path or "").strip()
        # Strip leading separators so absolute-looking sub_paths are pinned
        # under the user root rather than escaping to the host filesystem.
        sub = sub_raw.lstrip("/\\")
        candidate = (user_root / sub).resolve() if sub else user_root
        if not candidate.is_relative_to(user_root):
            msg = f"sub_path {self.root_path!r} escapes user namespace"
            raise PermissionError(msg)
        try:
            candidate.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            msg = f"Cannot create sub-path {candidate}: {exc.strerror or exc}"
            raise PermissionError(msg) from exc
        return candidate

    def _validate_path(self, path: str) -> Path:
        """Resolve `path` relative to the sandbox root and reject any escape.

        Why raise: internal helper for control flow; each tool operation catches
        PermissionError and translates it into a structured error for the agent.
        """
        if "\x00" in path:
            msg = "Path contains NUL byte"
            raise PermissionError(msg)
        if portability_error := _check_windows_portability(path):
            raise PermissionError(portability_error)
        # Block the reserved segments (`.lfsig` integrity hook, `.components`
        # registered-user-component store). We forbid traversal even by users
        # with valid credentials — agents and humans both — because the
        # privilege model depends on these directories being unreachable from
        # the public tool surface.
        # Compare case-insensitively: APFS and NTFS resolve `.LFSIG` to the
        # same directory as `.lfsig`, so a case-sensitive equality check
        # lets uppercase variants slip past the reservation on those
        # filesystems. `casefold` is the locale-aware lowercase used for
        # caseless string comparison — broader than `.lower()`.
        reserved_folds = {seg.casefold() for seg in RESERVED_SEGMENTS}
        for part in PureWindowsPath(path).parts:
            folded = part.casefold()
            if folded in reserved_folds:
                # Surface the canonical segment name (with leading dot) so
                # error messages stay stable across modes and OSes.
                canonical = next(seg for seg in RESERVED_SEGMENTS if seg.casefold() == folded)
                msg = f"Path component {canonical!r} is reserved"
                raise PermissionError(msg)
        root_resolved = self._validate_root()
        candidate = (root_resolved / path).resolve()
        if not candidate.is_relative_to(root_resolved):
            msg = f"Path escapes workspace boundary: {path}"
            raise PermissionError(msg)
        if hardlink_error := _check_hardlink(candidate):
            raise PermissionError(hardlink_error)
        return candidate

    def _read_file(self, path: str, offset: int | None = None, limit: int | None = None) -> dict:
        try:
            resolved = self._validate_path(path)
        except PermissionError as exc:
            return {"error": str(exc), "path": path}

        if not resolved.exists():
            return {"error": f"File not found: {path}", "path": path}
        if resolved.is_dir():
            return {"error": f"Path is a directory, not a file: {path}", "path": path}

        try:
            size = resolved.stat().st_size
        except OSError as exc:
            return {"error": f"Cannot stat file: {exc.strerror or exc}", "path": path}
        if size > MAX_FILE_SIZE_BYTES:
            return {
                "error": f"File size {size} exceeds limit of {MAX_FILE_SIZE_BYTES} bytes",
                "path": path,
            }

        try:
            head = _read_head_no_follow(resolved, BINARY_SNIFF_BYTES)
        except OSError as exc:
            return {"error": f"Cannot read file: {exc.strerror or exc}", "path": path}
        if _looks_binary(head):
            return {"error": f"Refusing to read binary file: {path}", "path": path}

        try:
            text = _read_bytes_no_follow(resolved).decode("utf-8", errors="replace")
        except OSError as exc:
            return {"error": f"Cannot read file: {exc.strerror or exc}", "path": path}

        lines = text.splitlines()
        total = len(lines)
        start = offset if offset and offset > 0 else 1
        end = total if limit is None else min(total, start - 1 + limit)
        window = lines[start - 1 : end]
        numbered = "\n".join(f"{i:>6}→{line}" for i, line in enumerate(window, start=start))
        return {
            "status": "ok",
            "path": path,
            "content": numbered,
            "total_lines": total,
            "start_line": start,
            "num_lines": len(window),
        }

    def _write_file(self, path: str, content: str) -> dict:
        try:
            resolved = self._validate_path(path)
        except PermissionError as exc:
            return {"error": str(exc), "path": path}

        encoded = content.encode("utf-8")
        if len(encoded) > MAX_FILE_SIZE_BYTES:
            return {
                "error": f"Content size {len(encoded)} exceeds limit of {MAX_FILE_SIZE_BYTES} bytes",
                "path": path,
            }

        if resolved.is_dir():
            return {"error": f"Path is a directory, not a file: {path}", "path": path}
        # Auto-create missing parent directories. `_validate_path` has already
        # confirmed `resolved` lies inside the sandbox root, so every ancestor
        # of `resolved.parent` is also inside the root — `mkdir(parents=True)`
        # cannot escape the sandbox.
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return {"error": f"Cannot create parent directory: {exc.strerror or exc}", "path": path}

        existed = resolved.exists()
        try:
            _write_bytes_no_follow(resolved, encoded)
        except OSError as exc:
            return {"error": f"Cannot write file: {exc.strerror or exc}", "path": path}

        return {
            "status": "updated" if existed else "created",
            "path": path,
            "bytes_written": len(encoded),
        }

    def _edit_file(
        self,
        path: str,
        old_string: str,
        new_string: str,
        *,
        replace_all: bool = False,
    ) -> dict:
        try:
            resolved = self._validate_path(path)
        except PermissionError as exc:
            return {"error": str(exc), "path": path}

        if not resolved.exists():
            return {"error": f"File not found: {path}", "path": path}
        if resolved.is_dir():
            return {"error": f"Path is a directory, not a file: {path}", "path": path}

        # Reject empty old_string outright. With `old_string=""`, str.replace
        # inserts new_string between every character (and at both ends),
        # producing roughly N*len(new_string) extra bytes — a small file plus
        # a large new_string can blow far past MAX_FILE_SIZE_BYTES before the
        # post-construction guard runs. Empty old_string also has no
        # well-defined semantics for "edit this exact match".
        if old_string == "":
            return {"error": "old_string must not be empty", "path": path}

        try:
            current = _read_bytes_no_follow(resolved).decode("utf-8", errors="replace")
        except OSError as exc:
            return {"error": f"Cannot read file: {exc.strerror or exc}", "path": path}

        occurrences = current.count(old_string)
        if occurrences == 0:
            return {"error": f"old_string not found in file: {path}", "path": path}
        if occurrences > 1 and not replace_all:
            return {
                "error": (
                    f"old_string is ambiguous: {occurrences} multiple matches in {path}. "
                    "Pass replace_all=True to replace every occurrence."
                ),
                "path": path,
                "matches": occurrences,
            }

        # Project the encoded size BEFORE building the replacement string.
        # str.replace allocates the full result up front, so a small file
        # with replace_all=True and a large new_string can balloon memory
        # before the post-allocation length check runs. UTF-8 byte counts are
        # exact (no estimation) so the projection is precise.
        old_bytes = len(old_string.encode("utf-8"))
        new_bytes = len(new_string.encode("utf-8"))
        current_bytes = len(current.encode("utf-8"))
        replacements_planned = occurrences if replace_all else 1
        projected_bytes = current_bytes + replacements_planned * (new_bytes - old_bytes)
        if projected_bytes > MAX_FILE_SIZE_BYTES:
            return {
                "error": (
                    f"Resulting content size {projected_bytes} would exceed limit of {MAX_FILE_SIZE_BYTES} bytes"
                ),
                "path": path,
            }

        updated = current.replace(old_string, new_string) if replace_all else current.replace(old_string, new_string, 1)
        encoded = updated.encode("utf-8")
        # Defensive re-check (should be unreachable given the projection above,
        # but keeps the original invariant explicit).
        if len(encoded) > MAX_FILE_SIZE_BYTES:
            return {
                "error": f"Resulting content size {len(encoded)} exceeds limit of {MAX_FILE_SIZE_BYTES} bytes",
                "path": path,
            }

        try:
            _write_bytes_no_follow(resolved, encoded)
        except OSError as exc:
            return {"error": f"Cannot write file: {exc.strerror or exc}", "path": path}

        return {
            "status": "ok",
            "path": path,
            "replacements": occurrences if replace_all else 1,
            "old_string": old_string,
            "new_string": new_string,
        }

    def _glob_search(self, pattern: str, path: str | None = None) -> dict:
        # Empty patterns make ``Path.glob`` raise ``ValueError`` instead of
        # returning an empty match list, which would propagate uncaught and
        # crash the agent. Surface a structured error instead.
        if not pattern or not pattern.strip():
            return {"error": "Pattern must not be empty", "pattern": pattern, "path": path}
        # Reject traversal segments in the pattern itself. Without this guard,
        # ``base.glob("../*")`` walks one directory up; one of the resulting
        # paths (``<base>/../<base_basename>``) resolves back to ``base`` and
        # is surfaced to the agent as ``"."`` — a silent, misleading hit.
        # ``PureWindowsPath`` splits on both ``/`` and ``\`` so the check
        # covers Windows-authored patterns as well.
        if any(part == ".." for part in PureWindowsPath(pattern).parts):
            return {
                "error": "Pattern must not contain '..' (path traversal not allowed)",
                "pattern": pattern,
                "path": path,
            }
        try:
            root_resolved = self._validate_root()
            base = self._validate_path(path) if path else root_resolved
        except PermissionError as exc:
            return {"error": str(exc), "pattern": pattern, "path": path}

        if not base.exists() or not base.is_dir():
            return {"error": f"Base path is not a directory: {path or '.'}", "pattern": pattern}

        # Collect up to GLOB_SCAN_CEILING (>> GLOB_RESULT_LIMIT) so we can
        # surface diverse branches even when one directory dominates the
        # iteration order. See BUG-02 / T2-001.
        collected: list[str] = []
        for match in base.glob(pattern):
            try:
                resolved_match = match.resolve()
            except OSError:
                continue
            if not resolved_match.is_relative_to(root_resolved):
                continue
            collected.append(str(resolved_match.relative_to(root_resolved)))
            if len(collected) >= GLOB_SCAN_CEILING:
                break

        # Sort for cross-filesystem determinism, then truncate to the visible
        # cap. Emit `truncated_branches` so the agent has a non-silent signal:
        # top-level branches under `base` whose files appear in the omitted
        # tail. The agent can narrow with `path=<branch>` to recover them.
        collected.sort()
        truncated = len(collected) > GLOB_RESULT_LIMIT
        if truncated:
            omitted = collected[GLOB_RESULT_LIMIT:]
            matches = collected[:GLOB_RESULT_LIMIT]
            truncated_branches = sorted({Path(p).parts[0] for p in omitted if Path(p).parts})
        else:
            matches = collected
            truncated_branches = []

        return {
            "status": "ok",
            "pattern": pattern,
            "matches": matches,
            "truncated": truncated,
            "truncated_branches": truncated_branches,
        }

    def _grep_search(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
        *,
        case_insensitive: bool = False,
        output_mode: str = "files_with_matches",
        is_regex: bool = False,
    ) -> dict:
        if output_mode not in GREP_OUTPUT_MODES:
            return {
                "error": f"Invalid output_mode '{output_mode}'. Must be one of {GREP_OUTPUT_MODES}",
                "pattern": pattern,
            }

        # Build a per-line matcher. Default is a literal substring check —
        # safe for any user-supplied pattern. Regex is opt-in and is gated by
        # a static heuristic plus per-line/per-file caps. Stdlib `re` cannot
        # be cancelled (it holds the GIL), so prevention is the only viable
        # mitigation: reject pathological patterns at compile time and bound
        # the input we hand to the engine.
        if is_regex:
            if len(pattern) > GREP_PATTERN_MAX_LEN:
                return {
                    "error": (
                        f"Regex pattern exceeds {GREP_PATTERN_MAX_LEN} chars; "
                        "shorten it or use literal mode (is_regex=False)."
                    ),
                    "pattern": pattern,
                }
            if _looks_like_redos(pattern):
                return {
                    "error": (
                        "Regex pattern rejected: nested unbounded quantifier "
                        "(catastrophic-backtracking risk). Rewrite without an "
                        "outer +/* on a group that already contains +, *, {n,}, "
                        "or |, or use literal mode (is_regex=False)."
                    ),
                    "pattern": pattern,
                }
            try:
                flags = re.IGNORECASE if case_insensitive else 0
                regex = re.compile(pattern, flags)
            except re.error as exc:
                return {"error": f"Invalid regex pattern: {exc}", "pattern": pattern}

            def line_matches(line: str) -> bool:
                # Skip regex matching on oversized lines — they are usually
                # data blobs, and a long input is a prerequisite for most
                # practical exponential-backtracking attacks.
                if len(line) > GREP_REGEX_LINE_MAX_LEN:
                    return False
                return regex.search(line) is not None
        else:
            needle = pattern.lower() if case_insensitive else pattern

            def line_matches(line: str) -> bool:
                hay = line.lower() if case_insensitive else line
                return needle in hay

        try:
            root_resolved = self._validate_root()
            base = self._validate_path(path) if path else root_resolved
        except PermissionError as exc:
            return {"error": str(exc), "pattern": pattern, "path": path}

        if not base.exists():
            return {"error": f"Path does not exist: {path or '.'}", "pattern": pattern}

        targets = self._collect_grep_targets(base, glob)
        files_with_matches: list[str] = []
        content_matches: list[dict] = []
        count_matches: list[dict] = []
        line_budget = GREP_LINE_LIMIT
        truncated = False

        for file in targets:
            try:
                resolved_file = file.resolve()
            except OSError:
                continue
            if not resolved_file.is_relative_to(root_resolved):
                continue
            try:
                size = resolved_file.stat().st_size
            except OSError:
                continue
            if size > MAX_FILE_SIZE_BYTES:
                continue
            try:
                with resolved_file.open("rb") as fh:
                    head = fh.read(BINARY_SNIFF_BYTES)
            except OSError:
                continue
            if _looks_binary(head):
                continue
            try:
                text = resolved_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            rel_path = str(resolved_file.relative_to(root_resolved))
            per_file_count = 0
            matched_any = False
            for idx, line in enumerate(text.splitlines(), start=1):
                # Per-file scan cap (regex only — literal scans are O(n)).
                if is_regex and idx > GREP_REGEX_LINES_PER_FILE:
                    break
                if not line_matches(line):
                    continue
                matched_any = True
                per_file_count += 1
                if output_mode == "content":
                    if line_budget <= 0:
                        truncated = True
                        break
                    content_matches.append({"path": rel_path, "line_number": idx, "line": line})
                    line_budget -= 1

            if matched_any:
                files_with_matches.append(rel_path)
                if output_mode == "count":
                    count_matches.append({"path": rel_path, "count": per_file_count})

            if output_mode == "content" and truncated:
                break

        if output_mode == "files_with_matches":
            matches: list = files_with_matches
        elif output_mode == "content":
            matches = content_matches
        else:  # count
            matches = count_matches

        return {
            "status": "ok",
            "pattern": pattern,
            "output_mode": output_mode,
            "matches": matches,
            "truncated": truncated,
        }

    def _collect_grep_targets(self, base: Path, glob: str | None) -> list[Path]:
        if base.is_file():
            return [base]
        all_files = [p for p in base.rglob("*") if p.is_file()]
        if glob:
            return [p for p in all_files if p.match(glob)]
        return all_files
