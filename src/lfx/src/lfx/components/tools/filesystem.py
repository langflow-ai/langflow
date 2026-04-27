"""Sandboxed filesystem tool component exposing 5 file I/O tools to agents."""

from __future__ import annotations

import json
import re
from pathlib import Path, PureWindowsPath
from typing import TYPE_CHECKING

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, StrInput
from lfx.io import Output
from lfx.schema.data import Data

if TYPE_CHECKING:
    from lfx.field_typing import Tool

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
BINARY_SNIFF_BYTES = 8 * 1024
GLOB_RESULT_LIMIT = 100
GREP_LINE_LIMIT = 250
GREP_OUTPUT_MODES = ("files_with_matches", "content", "count")

# Windows portability rules (applied on every host OS so flows authored on
# macOS/Linux do not silently break when run on Windows). Pure-string checks.
_WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
)
# Note: ':' is NOT included — drive letters (C:) are valid; bare ':' inside a
# basename will be caught by the OS at write time anyway.
_WINDOWS_FORBIDDEN_CHARS = frozenset('<>"|?*')


def _looks_binary(head: bytes) -> bool:
    return b"\x00" in head


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
    pattern: str = Field(..., description="Regular expression to match against file contents.")
    path: str | None = Field(default=None, description="Optional file or directory to scope the search.")
    glob: str | None = Field(default=None, description="Optional glob filter, e.g. '*.py'.")
    case_insensitive: bool = Field(default=False, description="If true, the regex is matched case-insensitively.")
    output_mode: str = Field(
        default="files_with_matches",
        description="One of 'files_with_matches', 'content', 'count'.",
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
            display_name="Root Path",
            required=True,
            info="Base directory. All operations are sandboxed to this path.",
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
        """Return introspective metadata about the sandbox. No file I/O."""
        registered = ["read_file", "glob_search", "grep_search"]
        if not self.read_only:
            registered.extend(["write_file", "edit_file"])
        return Data(
            data={
                "root_path": self.root_path,
                "read_only": bool(self.read_only),
                "tools_registered": registered,
            }
        )

    async def _get_tools(self) -> list[Tool]:
        """Tool Mode entrypoint. Called by Component.to_toolkit()."""
        tools: list[Tool] = [
            self._make_read_tool(),
            self._make_glob_tool(),
            self._make_grep_tool(),
        ]
        if not self.read_only:
            tools.append(self._make_write_tool())
            tools.append(self._make_edit_tool())
        return tools

    def _make_read_tool(self) -> StructuredTool:
        def _run(path: str, offset: int | None = None, limit: int | None = None) -> str:
            return json.dumps(self._read_file(path, offset=offset, limit=limit))

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

    def _make_write_tool(self) -> StructuredTool:
        def _run(path: str, content: str) -> str:
            return json.dumps(self._write_file(path, content))

        return StructuredTool.from_function(
            name="write_file",
            description="Create or overwrite a text file inside the sandboxed workspace.",
            func=_run,
            args_schema=_WriteFileArgs,
            tags=["write_file"],
        )

    def _make_edit_tool(self) -> StructuredTool:
        def _run(path: str, old_string: str, new_string: str, *, replace_all: bool = False) -> str:
            return json.dumps(
                self._edit_file(path, old_string=old_string, new_string=new_string, replace_all=replace_all)
            )

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

    def _make_glob_tool(self) -> StructuredTool:
        def _run(pattern: str, path: str | None = None) -> str:
            return json.dumps(self._glob_search(pattern, path=path))

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

    def _make_grep_tool(self) -> StructuredTool:
        def _run(
            pattern: str,
            path: str | None = None,
            glob: str | None = None,
            *,
            case_insensitive: bool = False,
            output_mode: str = "files_with_matches",
        ) -> str:
            return json.dumps(
                self._grep_search(
                    pattern,
                    path=path,
                    glob=glob,
                    case_insensitive=case_insensitive,
                    output_mode=output_mode,
                )
            )

        return StructuredTool.from_function(
            name="grep_search",
            description=(
                "Search file contents with a regular expression. "
                "output_mode: 'files_with_matches' (default), 'content', or 'count'. "
                f"Content mode is capped at {GREP_LINE_LIMIT} lines."
            ),
            func=_run,
            args_schema=_GrepSearchArgs,
            tags=["grep_search"],
        )

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
        root_resolved = Path(self.root_path).resolve()
        candidate = (root_resolved / path).resolve()
        if not candidate.is_relative_to(root_resolved):
            msg = f"Path escapes workspace boundary: {path}"
            raise PermissionError(msg)
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
            with resolved.open("rb") as fh:
                head = fh.read(BINARY_SNIFF_BYTES)
        except OSError as exc:
            return {"error": f"Cannot read file: {exc.strerror or exc}", "path": path}
        if _looks_binary(head):
            return {"error": f"Refusing to read binary file: {path}", "path": path}

        try:
            text = resolved.read_text(encoding="utf-8", errors="replace")
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
        if not resolved.parent.exists():
            return {"error": f"Parent directory does not exist: {path}", "path": path}

        existed = resolved.exists()
        try:
            resolved.write_bytes(encoded)
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

        try:
            current = resolved.read_text(encoding="utf-8", errors="replace")
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

        updated = current.replace(old_string, new_string) if replace_all else current.replace(old_string, new_string, 1)
        encoded = updated.encode("utf-8")
        if len(encoded) > MAX_FILE_SIZE_BYTES:
            return {
                "error": f"Resulting content size {len(encoded)} exceeds limit of {MAX_FILE_SIZE_BYTES} bytes",
                "path": path,
            }

        try:
            resolved.write_bytes(encoded)
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
        try:
            base = self._validate_path(path) if path else Path(self.root_path).resolve()
        except PermissionError as exc:
            return {"error": str(exc), "pattern": pattern, "path": path}

        if not base.exists() or not base.is_dir():
            return {"error": f"Base path is not a directory: {path or '.'}", "pattern": pattern}

        root_resolved = Path(self.root_path).resolve()
        matches: list[str] = []
        truncated = False
        for match in base.glob(pattern):
            try:
                resolved_match = match.resolve()
            except OSError:
                continue
            if not resolved_match.is_relative_to(root_resolved):
                continue
            matches.append(str(resolved_match.relative_to(root_resolved)))
            if len(matches) >= GLOB_RESULT_LIMIT:
                truncated = True
                break

        return {
            "status": "ok",
            "pattern": pattern,
            "matches": matches,
            "truncated": truncated,
        }

    def _grep_search(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
        *,
        case_insensitive: bool = False,
        output_mode: str = "files_with_matches",
    ) -> dict:
        if output_mode not in GREP_OUTPUT_MODES:
            return {
                "error": f"Invalid output_mode '{output_mode}'. Must be one of {GREP_OUTPUT_MODES}",
                "pattern": pattern,
            }
        try:
            flags = re.IGNORECASE if case_insensitive else 0
            regex = re.compile(pattern, flags)
        except re.error as exc:
            return {"error": f"Invalid regex pattern: {exc}", "pattern": pattern}

        try:
            base = self._validate_path(path) if path else Path(self.root_path).resolve()
        except PermissionError as exc:
            return {"error": str(exc), "pattern": pattern, "path": path}

        if not base.exists():
            return {"error": f"Path does not exist: {path or '.'}", "pattern": pattern}

        root_resolved = Path(self.root_path).resolve()
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
                if not regex.search(line):
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
