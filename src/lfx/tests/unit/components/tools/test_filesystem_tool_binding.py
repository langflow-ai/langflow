"""Layer-2 (L2) tool-binding tests for FileSystemToolComponent.

The goal is to ensure that StructuredTool closures captured at ``_get_tools()``
time refuse to operate after the component instance's user_id has changed —
the threat being instance reuse across user sessions.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

import pytest
from lfx.components.files_and_knowledge.filesystem import FileSystemToolComponent

if TYPE_CHECKING:
    from pathlib import Path


def _build_component(
    *,
    monkeypatch: pytest.MonkeyPatch,
    base_dir: Path,
    user_id: str,
) -> FileSystemToolComponent:
    monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(base_dir))
    component = FileSystemToolComponent(root_path="", read_only=False)
    # Tool binding only matters when isolation is active (AUTO_LOGIN=False).
    component._resolve_auto_login = lambda: False  # type: ignore[method-assign]
    component._user_id = user_id
    return component


def _get_tools_sync(component: FileSystemToolComponent) -> list:
    return asyncio.run(component._get_tools())


class TestToolBindingL2:
    """Slice E — captured tools must refuse calls after user_id mutation."""

    def test_should_return_error_when_read_tool_called_after_user_change(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange — build tools while bound to alice, then "swap" identity.
        component = _build_component(monkeypatch=monkeypatch, base_dir=tmp_path / "base", user_id="alice")
        component._write_file("doc.txt", "alice-only")  # owned by alice
        tools = _get_tools_sync(component)
        read_tool = next(t for t in tools if t.name == "read_file")

        # Act — masquerade as bob and try to use the captured tool.
        component._user_id = "bob"
        raw = read_tool.func("doc.txt")

        # Assert — the closure must refuse before invoking the implementation.
        result = json.loads(raw)
        assert "error" in result, f"Expected mismatch error, got: {result}"
        assert "mismatch" in result["error"].lower() or "user" in result["error"].lower()

    @pytest.mark.parametrize(
        ("tool_name", "args"),
        [
            ("read_file", ("doc.txt",)),
            ("write_file", ("new.txt", "x")),
            ("edit_file", ("doc.txt", "alice-only", "bob-was-here")),
            ("glob_search", ("**/*",)),
            ("grep_search", ("alice",)),
        ],
    )
    def test_should_return_error_when_any_tool_called_after_user_change(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        tool_name: str,
        args: tuple,
    ) -> None:
        component = _build_component(monkeypatch=monkeypatch, base_dir=tmp_path / "base", user_id="alice")
        component._write_file("doc.txt", "alice-only")
        tools = _get_tools_sync(component)
        tool = next(t for t in tools if t.name == tool_name)

        component._user_id = "bob"
        raw = tool.func(*args)

        result = json.loads(raw)
        assert "error" in result, f"Tool {tool_name} did not refuse cross-user call: {result}"

    def test_should_allow_tool_call_when_user_id_did_not_change(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Sanity: same user, captured tool keeps working.
        component = _build_component(monkeypatch=monkeypatch, base_dir=tmp_path / "base", user_id="alice")
        component._write_file("doc.txt", "alice-only")
        tools = _get_tools_sync(component)
        read_tool = next(t for t in tools if t.name == "read_file")

        raw = read_tool.func("doc.txt")
        result = json.loads(raw)

        assert result.get("status") == "ok", f"Same-user call broke: {result}"
