"""Unit tests for FileSystemToolComponent (sandboxed filesystem agent tool)."""

import json
from pathlib import Path

import pytest
from lfx.components.tools.filesystem import FileSystemToolComponent


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """Pre-populated sandbox directory used by filesystem-tool tests."""
    (tmp_path / "hello.txt").write_text("line1\nline2\nline3\n", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "deep.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
    (tmp_path / "binary.bin").write_bytes(b"\x00\x01\x02\x03BIN\x00")
    return tmp_path


@pytest.fixture
def component(sandbox: Path) -> FileSystemToolComponent:
    return FileSystemToolComponent(root_path=str(sandbox), read_only=False)


class TestComponentSkeleton:
    """Slice 1 — component boots with required configuration inputs."""

    def test_should_expose_required_inputs_when_instantiated(self, component: FileSystemToolComponent) -> None:
        input_names = {inp.name for inp in component.inputs}
        assert {"root_path", "read_only"}.issubset(input_names)

    def test_should_have_display_metadata(self) -> None:
        assert FileSystemToolComponent.display_name == "File System"
        assert FileSystemToolComponent.icon == "folder"
        assert FileSystemToolComponent.name == "FileSystemTool"


class TestValidatePath:
    """Slices 2-6 — every operation MUST resolve paths through _validate_path."""

    def test_should_return_resolved_path_when_path_is_inside_sandbox(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        resolved = component._validate_path("hello.txt")
        assert resolved == (sandbox / "hello.txt").resolve()

    def test_should_return_resolved_path_when_path_is_nested(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        resolved = component._validate_path("nested/deep.py")
        assert resolved == (sandbox / "nested" / "deep.py").resolve()

    def test_should_reject_when_path_escapes_via_dotdot(self, component: FileSystemToolComponent) -> None:
        with pytest.raises(PermissionError):
            component._validate_path("../outside.txt")

    def test_should_reject_when_path_is_absolute_outside_root(self, component: FileSystemToolComponent) -> None:
        with pytest.raises(PermissionError):
            component._validate_path("/etc/passwd")

    def test_should_reject_when_symlink_points_outside_root(
        self, component: FileSystemToolComponent, sandbox: Path, tmp_path: Path
    ) -> None:
        outside = tmp_path.parent / f"{tmp_path.name}-outside-secret.txt"
        outside.write_text("secret", encoding="utf-8")
        symlink = sandbox / "escape_link"
        symlink.symlink_to(outside)
        with pytest.raises(PermissionError):
            component._validate_path("escape_link")

    def test_should_reject_path_containing_null_byte(self, component: FileSystemToolComponent) -> None:
        with pytest.raises(PermissionError):
            component._validate_path("hello\x00.txt")


class TestWindowsPortability:
    """Slice 26 — proactively reject paths that would fail on Windows.

    These checks are pure-string and equally valid on every host OS, so flows
    authored on macOS/Linux do not silently break when run on Windows.
    """

    @pytest.mark.parametrize("name", ["CON", "PRN", "AUX", "NUL", "COM1", "COM9", "LPT1", "LPT9"])
    def test_should_reject_basename_that_is_a_windows_reserved_name(
        self, component: FileSystemToolComponent, name: str
    ) -> None:
        result = component._read_file(name)
        assert "error" in result
        assert "reserved" in result["error"].lower()

    def test_should_reject_reserved_name_with_extension(self, component: FileSystemToolComponent) -> None:
        # CON.txt is just as reserved as bare CON on Windows.
        result = component._read_file("CON.txt")
        assert "error" in result
        assert "reserved" in result["error"].lower()

    def test_should_reject_reserved_name_in_nested_path(self, component: FileSystemToolComponent) -> None:
        result = component._read_file("nested/PRN.json")
        assert "error" in result
        assert "reserved" in result["error"].lower()

    def test_should_be_case_insensitive_for_reserved_names(self, component: FileSystemToolComponent) -> None:
        # Lowercase "con" is treated identically by Windows.
        result = component._read_file("con.log")
        assert "error" in result
        assert "reserved" in result["error"].lower()

    def test_should_accept_reserved_name_as_substring(self, component: FileSystemToolComponent, sandbox: Path) -> None:
        # MyCon.txt is NOT reserved — only the exact stem CON is.
        (sandbox / "MyCon.txt").write_text("data", encoding="utf-8")
        result = component._read_file("MyCon.txt")
        assert "error" not in result, f"Unexpected error: {result.get('error')}"

    @pytest.mark.parametrize("char", ["<", ">", '"', "|", "?", "*"])
    def test_should_reject_path_with_forbidden_windows_character(
        self, component: FileSystemToolComponent, char: str
    ) -> None:
        result = component._read_file(f"bad{char}name.txt")
        assert "error" in result
        assert "forbidden" in result["error"].lower()

    def test_should_reject_path_with_trailing_dot(self, component: FileSystemToolComponent) -> None:
        # Windows silently strips trailing "." — ambiguous and bug-prone.
        result = component._write_file("badname.", "x")
        assert "error" in result
        assert "trailing" in result["error"].lower()

    def test_should_reject_path_with_trailing_space(self, component: FileSystemToolComponent) -> None:
        result = component._write_file("badname ", "x")
        assert "error" in result
        assert "trailing" in result["error"].lower()

    def test_should_not_trigger_on_dotdot_relative_marker(self, component: FileSystemToolComponent) -> None:
        # `..` IS a path component but it is the parent-dir marker, not a
        # filename with a trailing dot. It should pass the portability check
        # and be caught only by the sandbox-boundary check downstream.
        result = component._read_file("../outside.txt")
        assert "error" in result
        assert "trailing" not in result["error"].lower()
        assert "boundary" in result["error"].lower() or "escape" in result["error"].lower()

    def test_should_not_trigger_on_single_dot(self, component: FileSystemToolComponent, sandbox: Path) -> None:
        # `./hello.txt` is just `hello.txt`. Should not trigger trailing-dot
        # rule, and should resolve to the existing file.
        assert (sandbox / "hello.txt").exists()
        result = component._read_file("./hello.txt")
        assert result.get("status") == "ok", f"Got: {result}"


class TestReadFile:
    """Slices 7-9 — read_file returns content with metadata + adversarial cases."""

    def test_should_return_content_with_metadata(self, component: FileSystemToolComponent) -> None:
        result = component._read_file("hello.txt")
        assert result["status"] == "ok"
        assert result["total_lines"] == 3
        assert result["start_line"] == 1
        assert result["num_lines"] == 3
        assert "line1" in result["content"]
        assert "line2" in result["content"]
        assert "line3" in result["content"]

    def test_should_prefix_lines_with_line_numbers(self, component: FileSystemToolComponent) -> None:
        result = component._read_file("hello.txt")
        assert "1" in result["content"].splitlines()[0]
        assert "line1" in result["content"].splitlines()[0]

    def test_should_respect_offset_and_limit_window(self, component: FileSystemToolComponent) -> None:
        result = component._read_file("hello.txt", offset=2, limit=1)
        assert result["status"] == "ok"
        assert result["start_line"] == 2
        assert result["num_lines"] == 1
        assert result["total_lines"] == 3
        assert "line2" in result["content"]
        assert "line1" not in result["content"]
        assert "line3" not in result["content"]

    def test_should_reject_binary_file_on_read(self, component: FileSystemToolComponent) -> None:
        result = component._read_file("binary.bin")
        assert "error" in result
        assert "binary" in result["error"].lower()

    def test_should_reject_read_when_file_exceeds_size_limit(
        self, component: FileSystemToolComponent, sandbox: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from lfx.components.tools import filesystem as fs_mod

        (sandbox / "big.txt").write_text("x" * 128, encoding="utf-8")
        monkeypatch.setattr(fs_mod, "MAX_FILE_SIZE_BYTES", 64)
        result = component._read_file("big.txt")
        assert "error" in result
        assert "size" in result["error"].lower() or "limit" in result["error"].lower()

    def test_should_return_structured_error_when_file_does_not_exist(self, component: FileSystemToolComponent) -> None:
        result = component._read_file("does_not_exist.txt")
        assert "error" in result
        assert "not found" in result["error"].lower() or "no such" in result["error"].lower()

    def test_should_return_structured_error_when_path_is_a_directory(self, component: FileSystemToolComponent) -> None:
        result = component._read_file("nested")
        assert "error" in result
        assert "directory" in result["error"].lower()

    def test_should_return_structured_error_when_path_escapes_sandbox(self, component: FileSystemToolComponent) -> None:
        result = component._read_file("../outside.txt")
        assert "error" in result
        assert "escape" in result["error"].lower() or "boundary" in result["error"].lower()


class TestWriteFile:
    """Slices 10-12 — write_file creates/updates with size + OS error guards."""

    def test_should_create_new_file(self, component: FileSystemToolComponent, sandbox: Path) -> None:
        result = component._write_file("new.txt", "hello world")
        assert result["status"] == "created"
        assert (sandbox / "new.txt").read_text(encoding="utf-8") == "hello world"

    def test_should_overwrite_existing_file(self, component: FileSystemToolComponent, sandbox: Path) -> None:
        result = component._write_file("hello.txt", "replaced")
        assert result["status"] == "updated"
        assert (sandbox / "hello.txt").read_text(encoding="utf-8") == "replaced"

    def test_should_reject_write_when_content_exceeds_size_limit(
        self, component: FileSystemToolComponent, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from lfx.components.tools import filesystem as fs_mod

        monkeypatch.setattr(fs_mod, "MAX_FILE_SIZE_BYTES", 8)
        result = component._write_file("too_big.txt", "this content exceeds eight bytes")
        assert "error" in result
        assert "size" in result["error"].lower() or "limit" in result["error"].lower()

    def test_should_return_structured_error_when_parent_directory_missing(
        self, component: FileSystemToolComponent
    ) -> None:
        result = component._write_file("missing_dir/new.txt", "x")
        assert "error" in result
        assert "directory" in result["error"].lower() or "parent" in result["error"].lower()

    def test_should_return_structured_error_when_path_escapes_sandbox(self, component: FileSystemToolComponent) -> None:
        result = component._write_file("../escape.txt", "x")
        assert "error" in result
        assert "escape" in result["error"].lower() or "boundary" in result["error"].lower()

    def test_should_return_structured_error_when_target_is_a_directory(
        self, component: FileSystemToolComponent
    ) -> None:
        result = component._write_file("nested", "x")
        assert "error" in result
        assert "directory" in result["error"].lower()


class TestEditFile:
    """Slices 13-15 — edit_file uses exact string match (not line numbers)."""

    def test_should_replace_single_occurrence(self, component: FileSystemToolComponent, sandbox: Path) -> None:
        result = component._edit_file("hello.txt", old_string="line2", new_string="LINE_TWO")
        assert result["status"] == "ok"
        assert result["replacements"] == 1
        assert (sandbox / "hello.txt").read_text(encoding="utf-8") == "line1\nLINE_TWO\nline3\n"

    def test_should_replace_all_when_replace_all_true(self, component: FileSystemToolComponent, sandbox: Path) -> None:
        (sandbox / "repeat.txt").write_text("foo\nfoo\nfoo\n", encoding="utf-8")
        result = component._edit_file("repeat.txt", old_string="foo", new_string="bar", replace_all=True)
        assert result["status"] == "ok"
        assert result["replacements"] == 3
        assert (sandbox / "repeat.txt").read_text(encoding="utf-8") == "bar\nbar\nbar\n"

    def test_should_reject_edit_when_old_string_not_found(self, component: FileSystemToolComponent) -> None:
        result = component._edit_file("hello.txt", old_string="absent", new_string="whatever")
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_should_reject_edit_when_old_string_matches_multiple_times_and_replace_all_false(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        (sandbox / "repeat.txt").write_text("foo\nfoo\n", encoding="utf-8")
        result = component._edit_file("repeat.txt", old_string="foo", new_string="bar")
        assert "error" in result
        assert "multiple" in result["error"].lower() or "ambiguous" in result["error"].lower()

    def test_should_return_structured_error_when_file_does_not_exist(self, component: FileSystemToolComponent) -> None:
        result = component._edit_file("missing.txt", old_string="x", new_string="y")
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_should_return_structured_error_when_path_escapes(self, component: FileSystemToolComponent) -> None:
        result = component._edit_file("../escape.txt", old_string="x", new_string="y")
        assert "error" in result
        assert "escape" in result["error"].lower() or "boundary" in result["error"].lower()


class TestGlobSearch:
    """Slices 16-17 — glob_search lists matching paths with truncation flag."""

    def test_should_list_paths_matching_pattern(self, component: FileSystemToolComponent) -> None:
        result = component._glob_search("**/*.py")
        assert result["status"] == "ok"
        assert result["truncated"] is False
        assert any(p.endswith("deep.py") for p in result["matches"])

    def test_should_return_empty_list_when_no_matches(self, component: FileSystemToolComponent) -> None:
        result = component._glob_search("**/*.nonexistent")
        assert result["status"] == "ok"
        assert result["matches"] == []
        assert result["truncated"] is False

    def test_should_truncate_glob_results_at_one_hundred_and_set_flag(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        bulk = sandbox / "bulk"
        bulk.mkdir()
        for i in range(150):
            (bulk / f"f{i:03d}.log").write_text("x", encoding="utf-8")
        result = component._glob_search("bulk/*.log")
        assert result["status"] == "ok"
        assert result["truncated"] is True
        assert len(result["matches"]) == 100

    def test_should_scope_glob_to_path_argument(self, component: FileSystemToolComponent, sandbox: Path) -> None:
        (sandbox / "nested" / "only_here.md").write_text("x", encoding="utf-8")
        (sandbox / "top.md").write_text("x", encoding="utf-8")
        result = component._glob_search("*.md", path="nested")
        assert result["status"] == "ok"
        assert any("only_here.md" in p for p in result["matches"])
        assert not any("top.md" in p for p in result["matches"])

    def test_should_return_structured_error_when_scope_path_escapes(self, component: FileSystemToolComponent) -> None:
        result = component._glob_search("*.txt", path="../")
        assert "error" in result


class TestGrepSearch:
    """Slices 18-21 — grep_search supports files_with_matches | content | count."""

    @pytest.fixture(autouse=True)
    def _populate(self, sandbox: Path) -> None:
        (sandbox / "a.txt").write_text("alpha\nfoo bar\nbeta\n", encoding="utf-8")
        (sandbox / "b.txt").write_text("FOO bar\nbaz\n", encoding="utf-8")
        (sandbox / "nested" / "c.md").write_text("foo only here\n", encoding="utf-8")

    def test_should_return_files_with_matches_by_default(self, component: FileSystemToolComponent) -> None:
        result = component._grep_search(r"foo")
        assert result["status"] == "ok"
        assert result["output_mode"] == "files_with_matches"
        files = result["matches"]
        assert any(f.endswith("a.txt") for f in files)
        assert any(f.endswith("c.md") for f in files)
        assert not any(f.endswith("b.txt") for f in files)  # FOO is uppercase, default is case-sensitive

    def test_should_return_content_with_line_numbers_in_content_mode(self, component: FileSystemToolComponent) -> None:
        result = component._grep_search(r"foo", output_mode="content")
        assert result["status"] == "ok"
        assert result["output_mode"] == "content"
        lines = result["matches"]
        assert any("foo bar" in entry["line"] and entry["line_number"] == 2 for entry in lines)

    def test_should_return_count_per_file_in_count_mode(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        (sandbox / "many.txt").write_text("foo\nfoo\nbar\nfoo\n", encoding="utf-8")
        result = component._grep_search(r"foo", output_mode="count")
        assert result["status"] == "ok"
        assert result["output_mode"] == "count"
        counts = {entry["path"]: entry["count"] for entry in result["matches"]}
        assert any(p.endswith("many.txt") and c == 3 for p, c in counts.items())

    def test_should_apply_glob_filter_to_grep(self, component: FileSystemToolComponent) -> None:
        result = component._grep_search(r"foo", glob="*.md")
        files = result["matches"]
        assert any(f.endswith("c.md") for f in files)
        assert not any(f.endswith(".txt") for f in files)

    def test_should_honor_case_insensitive_flag(self, component: FileSystemToolComponent) -> None:
        result = component._grep_search(r"foo", case_insensitive=True)
        files = result["matches"]
        assert any(f.endswith("a.txt") for f in files)
        assert any(f.endswith("b.txt") for f in files)

    def test_should_truncate_grep_output_at_default_line_limit(
        self, component: FileSystemToolComponent, sandbox: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from lfx.components.tools import filesystem as fs_mod

        monkeypatch.setattr(fs_mod, "GREP_LINE_LIMIT", 5)
        big = "foo\n" * 20
        (sandbox / "big.txt").write_text(big, encoding="utf-8")
        result = component._grep_search(r"foo", output_mode="content", path="big.txt")
        assert result["status"] == "ok"
        assert result["truncated"] is True
        assert len(result["matches"]) == 5

    def test_should_scope_grep_to_single_file_path(self, component: FileSystemToolComponent) -> None:
        result = component._grep_search(r"foo", path="a.txt", output_mode="content")
        assert result["status"] == "ok"
        assert all("a.txt" in entry["path"] for entry in result["matches"])

    def test_should_return_structured_error_for_invalid_regex(self, component: FileSystemToolComponent) -> None:
        # Regex compilation only happens in opt-in regex mode; in literal
        # mode, an unbalanced bracket is just a substring (no error).
        result = component._grep_search(r"[invalid", is_regex=True)
        assert "error" in result
        assert "regex" in result["error"].lower() or "pattern" in result["error"].lower()

    def test_should_return_structured_error_when_scope_path_escapes(self, component: FileSystemToolComponent) -> None:
        result = component._grep_search(r"foo", path="../")
        assert "error" in result


class TestGetTools:
    """Slices 22-23 — tool registration respects read_only flag (modern Tool Mode pattern)."""

    async def test_should_register_all_five_tools_when_read_only_false(
        self, component: FileSystemToolComponent
    ) -> None:
        tools = await component._get_tools()
        names = {tool.name for tool in tools}
        assert names == {"read_file", "write_file", "edit_file", "glob_search", "grep_search"}

    async def test_should_not_register_write_and_edit_tools_in_read_only_mode(self, sandbox: Path) -> None:
        component = FileSystemToolComponent(root_path=str(sandbox), read_only=True)
        tools = await component._get_tools()
        names = {tool.name for tool in tools}
        assert names == {"read_file", "glob_search", "grep_search"}
        assert "write_file" not in names
        assert "edit_file" not in names

    async def test_registered_read_tool_invokes_read_file(self, component: FileSystemToolComponent) -> None:
        tools = {tool.name: tool for tool in await component._get_tools()}
        output = tools["read_file"].invoke({"path": "hello.txt"})
        assert "line1" in str(output)

    async def test_every_tool_must_have_non_empty_tags(self, component: FileSystemToolComponent) -> None:
        # The framework's update_tools_metadata flow (component_tool.py:343)
        # gates on `isinstance(tool, StructuredTool|BaseTool) AND tool.tags`.
        # A tool without tags falls through to a misleading TypeError that
        # claims a wrong type. Every tool MUST carry at least one tag matching
        # its name so the metadata-merge step can identify it.
        for tool in await component._get_tools():
            assert tool.tags, f"Tool {tool.name!r} is missing tags"
            assert tool.tags[0] == tool.name, f"Tool {tool.name!r} first tag ({tool.tags[0]!r}) must match name"


class TestToolModeToggle:
    """Slice 25 — modern UI contract: Tool Mode toggle is exposed in the UI."""

    def test_should_set_add_tool_output_flag_at_class_level(self) -> None:
        # Defensive runtime flag — read by Component._handle_tool_mode.
        assert getattr(FileSystemToolComponent, "add_tool_output", False) is True

    def test_should_have_at_least_one_input_with_tool_mode_true(self, component: FileSystemToolComponent) -> None:
        # The frontend toggle visibility is gated by `any(input.tool_mode)` in
        # lfx.template.utils — without this, the "Tool Mode" header toggle does
        # not render even if add_tool_output is True.
        assert any(getattr(inp, "tool_mode", False) for inp in component.inputs)

    def test_should_keep_root_path_visible_in_tool_mode(self, component: FileSystemToolComponent) -> None:
        # Frontend rule (parameter-filtering.ts :: isHidden): an input with
        # tool_mode=True is hidden when the Tool Mode toggle is ON. The
        # root_path field is component-level configuration and MUST remain
        # user-editable in both modes — guard against accidentally setting
        # tool_mode=True on it.
        root_path_input = next(inp for inp in component.inputs if inp.name == "root_path")
        assert getattr(root_path_input, "tool_mode", False) is False

    def test_should_use_a_dedicated_hidden_synthetic_input_as_toggle_trigger(
        self, component: FileSystemToolComponent
    ) -> None:
        # The trigger must be hidden (show=False) so it does not pollute the
        # config UI. Pattern follows FileComponent.file_path_str.
        triggers = [
            inp for inp in component.inputs if getattr(inp, "tool_mode", False) and not getattr(inp, "show", True)
        ]
        assert len(triggers) >= 1, "Expected at least one hidden input with tool_mode=True"


class TestBuildMetadata:
    """Slice 24 — build_metadata returns introspective metadata (no I/O)."""

    def test_should_return_sandbox_metadata_as_data(self, component: FileSystemToolComponent) -> None:
        result = component.build_metadata()
        assert result.data["root_path"] == component.root_path
        assert result.data["read_only"] is False
        assert set(result.data["tools_registered"]) == {
            "read_file",
            "write_file",
            "edit_file",
            "glob_search",
            "grep_search",
        }

    def test_should_reflect_read_only_in_tools_registered(self, sandbox: Path) -> None:
        component = FileSystemToolComponent(root_path=str(sandbox), read_only=True)
        result = component.build_metadata()
        assert result.data["read_only"] is True
        assert set(result.data["tools_registered"]) == {"read_file", "glob_search", "grep_search"}


class TestRootPathAllowlist:
    """Slice 27 — root_path is server-controlled via env-var allowlist.

    A flow author should not be able to escape the operator's intent by
    pointing root_path at `/`, an app config directory, or any other
    sensitive server location. When `LANGFLOW_FS_TOOL_ALLOWED_ROOTS` is set,
    every operation must reject root_path values that don't resolve under
    one of the allowlisted paths.
    """

    def test_should_reject_root_outside_allowlist(
        self, sandbox: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Allowlist names a different directory than the requested root.
        allowed = tmp_path / "workspace"
        allowed.mkdir()
        monkeypatch.setenv("LANGFLOW_FS_TOOL_ALLOWED_ROOTS", str(allowed))
        component = FileSystemToolComponent(root_path=str(sandbox), read_only=False)

        result = component._read_file("hello.txt")
        assert "error" in result
        assert "allowlist" in result["error"].lower() or "not allowed" in result["error"].lower()

    def test_should_accept_root_inside_allowlist(self, sandbox: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Allowlist names the parent of sandbox.
        monkeypatch.setenv("LANGFLOW_FS_TOOL_ALLOWED_ROOTS", str(sandbox.parent))
        component = FileSystemToolComponent(root_path=str(sandbox), read_only=False)

        result = component._read_file("hello.txt")
        assert result.get("status") == "ok", f"Got: {result}"

    def test_should_accept_root_exactly_equal_to_allowlist_entry(
        self, sandbox: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LANGFLOW_FS_TOOL_ALLOWED_ROOTS", str(sandbox))
        component = FileSystemToolComponent(root_path=str(sandbox), read_only=False)

        result = component._read_file("hello.txt")
        assert result.get("status") == "ok", f"Got: {result}"

    def test_should_support_multiple_paths_separated_by_os_pathsep(
        self, sandbox: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import os

        other = tmp_path / "other"
        other.mkdir()
        monkeypatch.setenv("LANGFLOW_FS_TOOL_ALLOWED_ROOTS", os.pathsep.join([str(other), str(sandbox.parent)]))
        component = FileSystemToolComponent(root_path=str(sandbox), read_only=False)

        result = component._read_file("hello.txt")
        assert result.get("status") == "ok", f"Got: {result}"

    def test_should_reject_root_when_running_in_astra_cloud(
        self, sandbox: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Defense in depth: even without an allowlist, a hosted/cloud env
        # MUST refuse free-form filesystem access from a flow author.
        monkeypatch.setenv("ASTRA_CLOUD_DISABLE_COMPONENT", "true")
        monkeypatch.delenv("LANGFLOW_FS_TOOL_ALLOWED_ROOTS", raising=False)
        component = FileSystemToolComponent(root_path=str(sandbox), read_only=False)

        result = component._read_file("hello.txt")
        assert "error" in result
        assert "cloud" in result["error"].lower() or "disabled" in result["error"].lower()

    def test_glob_search_should_honor_allowlist(
        self, sandbox: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        allowed = tmp_path / "workspace"
        allowed.mkdir()
        monkeypatch.setenv("LANGFLOW_FS_TOOL_ALLOWED_ROOTS", str(allowed))
        component = FileSystemToolComponent(root_path=str(sandbox), read_only=False)

        result = component._glob_search("**/*.py")
        assert "error" in result

    def test_grep_search_should_honor_allowlist(
        self, sandbox: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        allowed = tmp_path / "workspace"
        allowed.mkdir()
        monkeypatch.setenv("LANGFLOW_FS_TOOL_ALLOWED_ROOTS", str(allowed))
        component = FileSystemToolComponent(root_path=str(sandbox), read_only=False)

        result = component._grep_search(r"foo")
        assert "error" in result

    def test_write_and_edit_should_honor_allowlist(
        self, sandbox: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        allowed = tmp_path / "workspace"
        allowed.mkdir()
        monkeypatch.setenv("LANGFLOW_FS_TOOL_ALLOWED_ROOTS", str(allowed))
        component = FileSystemToolComponent(root_path=str(sandbox), read_only=False)

        write_result = component._write_file("new.txt", "data")
        assert "error" in write_result
        edit_result = component._edit_file("hello.txt", old_string="line2", new_string="X")
        assert "error" in edit_result


class TestGrepSearchReDoSGuard:
    """Slice 28 — grep_search must not be DoS-able by a malicious regex.

    The default mode is literal substring match. Regex mode is opt-in via
    `is_regex=True` and runs each match under a hard timeout so a
    catastrophic-backtracking pattern cannot pin a worker thread.
    """

    @pytest.fixture(autouse=True)
    def _populate(self, sandbox: Path) -> None:
        # File whose contents would trigger catastrophic backtracking on the
        # naive `^(a+)+$` pattern under stdlib `re`.
        (sandbox / "redos.txt").write_text("a" * 60 + "X\n", encoding="utf-8")
        (sandbox / "lit.txt").write_text("hello world\nfoo.bar\nbaz\n", encoding="utf-8")

    def test_default_mode_should_treat_pattern_as_literal_substring(self, component: FileSystemToolComponent) -> None:
        # `.` is a regex metachar but in literal mode it must match only a dot.
        result = component._grep_search("foo.bar", path="lit.txt", output_mode="content")
        assert result["status"] == "ok"
        assert any("foo.bar" in entry["line"] for entry in result["matches"])

    def test_default_literal_mode_should_not_match_regex_metachars(self, component: FileSystemToolComponent) -> None:
        # `h.llo` would match "hello" as a regex; in literal mode it must NOT.
        result = component._grep_search("h.llo", path="lit.txt", output_mode="content")
        assert result["status"] == "ok"
        assert result["matches"] == []

    def test_regex_mode_should_be_opt_in_and_compile_pattern(self, component: FileSystemToolComponent) -> None:
        result = component._grep_search("h.llo", path="lit.txt", output_mode="content", is_regex=True)
        assert result["status"] == "ok"
        assert any("hello" in entry["line"] for entry in result["matches"])

    def test_regex_mode_must_terminate_under_timeout_for_catastrophic_pattern(
        self, component: FileSystemToolComponent
    ) -> None:
        import time

        # Stdlib `re` with `^(a+)+$` against 60 'a's followed by 'X' triggers
        # exponential backtracking — without a timeout this hangs the worker.
        # With our guard, it must return promptly with a structured error.
        start = time.monotonic()
        result = component._grep_search(r"^(a+)+$", path="redos.txt", is_regex=True)
        elapsed = time.monotonic() - start
        assert elapsed < 5.0, f"grep_search did not terminate promptly (took {elapsed:.1f}s)"
        # Either the pattern was rejected up front, or the per-match timeout fired.
        assert "error" in result or result.get("truncated") is True or result.get("matches") == []


class TestEditFileSizeProjection:
    """Slice 29 — edit_file rejects empty old_string and projects size up front.

    With `old_string=""`, Python's `str.replace` inserts new_string between
    every character (and at both ends), producing roughly N*len(new_string)
    extra bytes. A small file plus a large new_string can blow far past
    MAX_FILE_SIZE_BYTES before the existing post-construction guard runs.
    """

    def test_should_reject_empty_old_string(self, component: FileSystemToolComponent, sandbox: Path) -> None:
        # The reviewer-flagged DoS vector: with old_string="", str.replace
        # inserts new_string between every character. The pre-fix code did
        # not reject empty old_string outright — it fell through to
        # current.count("") == len(file)+1, then to the "ambiguous matches"
        # error path. That error message is misleading AND only blocks the
        # path coincidentally; with replace_all=True the unbounded
        # allocation would proceed. The fix MUST reject empty old_string
        # explicitly with a message that says "empty", not "ambiguous".
        result = component._edit_file("hello.txt", old_string="", new_string="X")
        assert "error" in result
        assert "empty" in result["error"].lower(), (
            f"Expected 'empty' in error to distinguish from old 'ambiguous' rejection path. Got: {result['error']!r}"
        )
        # File on disk must NOT have been modified.
        assert (sandbox / "hello.txt").read_text(encoding="utf-8") == "line1\nline2\nline3\n"

    def test_should_reject_empty_old_string_even_with_replace_all(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        # The pre-fix code's "ambiguous" guard fired on empty old_string only
        # because `replace_all=False`. With `replace_all=True`, the
        # ambiguity check was bypassed and `current.replace("", "X" * N)`
        # would balloon the file to N*(len+1)+len bytes BEFORE the
        # post-allocation size check. The fix MUST reject empty old_string
        # regardless of replace_all.
        result = component._edit_file("hello.txt", old_string="", new_string="X", replace_all=True)
        assert "error" in result
        assert "empty" in result["error"].lower(), f"Got: {result['error']!r}"
        # File on disk must NOT have been modified.
        assert (sandbox / "hello.txt").read_text(encoding="utf-8") == "line1\nline2\nline3\n"

    def test_should_still_allow_legitimate_replacements_within_limit(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        # Sanity: a normal in-bounds edit still works after the new guard.
        result = component._edit_file("hello.txt", old_string="line2", new_string="LINE_TWO")
        assert result["status"] == "ok"
        assert (sandbox / "hello.txt").read_text(encoding="utf-8") == "line1\nLINE_TWO\nline3\n"


class TestEditFileIdempotency:
    """Slice 30 — re-running the same edit must not re-modify the file.

    Idempotence here is "second run is a structured no-op": the first call
    succeeds, the second call returns a structured "not found" error (because
    old_string is gone after the first replacement), and the on-disk content
    is identical before and after the second call.
    """

    def test_should_be_idempotent_when_same_edit_runs_twice(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        first = component._edit_file("hello.txt", old_string="line2", new_string="LINE_TWO")
        assert first["status"] == "ok"
        assert first["replacements"] == 1
        post_first = (sandbox / "hello.txt").read_text(encoding="utf-8")
        assert post_first == "line1\nLINE_TWO\nline3\n"

        second = component._edit_file("hello.txt", old_string="line2", new_string="LINE_TWO")
        assert "error" in second, f"Expected structured error on re-run, got: {second}"
        assert "not found" in second["error"].lower()

        # Disk state must be byte-identical to the post-first state — proves
        # the second call did not re-apply the edit nor corrupt the file.
        assert (sandbox / "hello.txt").read_text(encoding="utf-8") == post_first

    def test_should_be_idempotent_when_replace_all_runs_twice(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        # Replace_all variant: a second run with no remaining matches must
        # still return "not found" rather than silently succeeding.
        (sandbox / "repeat.txt").write_text("foo\nfoo\nfoo\n", encoding="utf-8")
        first = component._edit_file("repeat.txt", old_string="foo", new_string="bar", replace_all=True)
        assert first["status"] == "ok"
        assert first["replacements"] == 3
        post_first = (sandbox / "repeat.txt").read_text(encoding="utf-8")
        assert post_first == "bar\nbar\nbar\n"

        second = component._edit_file("repeat.txt", old_string="foo", new_string="bar", replace_all=True)
        assert "error" in second
        assert "not found" in second["error"].lower()
        assert (sandbox / "repeat.txt").read_text(encoding="utf-8") == post_first


class TestGlobNestedDirectories:
    """Slice 31 — glob_search descends through multiple nested directory levels.

    Cross-platform: uses forward-slash glob patterns (Path.glob normalizes)
    and Path API for tree creation.
    """

    def test_should_find_file_in_deeply_nested_directory(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        deep = sandbox / "a" / "b" / "c" / "d"
        deep.mkdir(parents=True)
        (deep / "leaf.py").write_text("x = 1\n", encoding="utf-8")
        result = component._glob_search("**/*.py")
        assert result["status"] == "ok"
        assert any(p.endswith("leaf.py") for p in result["matches"])

    def test_should_find_files_across_multiple_nested_branches(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        for branch in ("alpha/inner", "beta/inner", "gamma/inner"):
            target = sandbox / Path(branch)
            target.mkdir(parents=True)
            (target / "leaf.py").write_text("x = 1\n", encoding="utf-8")
        result = component._glob_search("**/*.py")
        assert result["status"] == "ok"
        leaf_matches = [p for p in result["matches"] if p.endswith("leaf.py")]
        # Three new branches must all be reachable via `**` traversal.
        assert len(leaf_matches) >= 3, f"Expected >=3 leaf.py matches across branches, got: {leaf_matches}"

    def test_should_scope_nested_glob_to_subdirectory(self, component: FileSystemToolComponent, sandbox: Path) -> None:
        # Confirms that descending traversal also respects the `path` scope —
        # i.e., **/*.py inside `nested/` should not see siblings outside it.
        deep = sandbox / "nested" / "deeper" / "deepest"
        deep.mkdir(parents=True)
        (deep / "scoped.py").write_text("x = 1\n", encoding="utf-8")
        (sandbox / "outside.py").write_text("x = 1\n", encoding="utf-8")
        result = component._glob_search("**/*.py", path="nested")
        assert result["status"] == "ok"
        assert any(p.endswith("scoped.py") for p in result["matches"])
        assert not any(p.endswith("outside.py") for p in result["matches"])


class TestSandboxStructuredErrorAtPublicLevel:
    """Slice 32 — sandbox violations surface as structured errors via public methods.

    The agent never sees a raised PermissionError; it always sees a
    JSON-serializable dict with an `error` key. This locks in the contract
    for all three escape forms (`..` traversal, symlink-out, absolute-path-out).
    Cross-platform: uses tmp_path.parent for "absolute path outside root"
    instead of POSIX-only paths like /etc/passwd.
    """

    def test_read_file_should_return_structured_error_for_absolute_path_outside_root(
        self, component: FileSystemToolComponent, tmp_path: Path
    ) -> None:
        outside_abs = str(tmp_path.parent)
        result = component._read_file(outside_abs)
        assert "error" in result
        assert "escape" in result["error"].lower() or "boundary" in result["error"].lower()

    def test_read_file_should_return_structured_error_for_symlink_escaping_root(
        self, component: FileSystemToolComponent, sandbox: Path, tmp_path: Path
    ) -> None:
        outside = tmp_path.parent / f"{tmp_path.name}-public-escape.txt"
        outside.write_text("secret", encoding="utf-8")
        symlink = sandbox / "escape_link_public"
        try:
            symlink.symlink_to(outside)
        except (OSError, NotImplementedError) as exc:
            # Windows without Developer Mode rejects unprivileged symlinks.
            # In that case the test premise can't be set up; skip rather than
            # fail spuriously, since the production guard is the same.
            pytest.skip(f"Symlink creation unsupported in this environment: {exc}")
        result = component._read_file("escape_link_public")
        assert "error" in result
        assert "escape" in result["error"].lower() or "boundary" in result["error"].lower()

    def test_write_file_should_return_structured_error_for_absolute_path_outside_root(
        self, component: FileSystemToolComponent, tmp_path: Path
    ) -> None:
        outside_abs = str(tmp_path.parent / "should_not_be_created.txt")
        result = component._write_file(outside_abs, "x")
        assert "error" in result
        assert "escape" in result["error"].lower() or "boundary" in result["error"].lower()
        # And the side effect MUST NOT have happened.
        assert not (tmp_path.parent / "should_not_be_created.txt").exists()

    def test_edit_file_should_return_structured_error_for_absolute_path_outside_root(
        self, component: FileSystemToolComponent, tmp_path: Path
    ) -> None:
        outside_abs = str(tmp_path.parent)
        result = component._edit_file(outside_abs, old_string="x", new_string="y")
        assert "error" in result
        assert "escape" in result["error"].lower() or "boundary" in result["error"].lower()

    def test_glob_search_should_return_structured_error_for_absolute_scope_outside_root(
        self, component: FileSystemToolComponent, tmp_path: Path
    ) -> None:
        result = component._glob_search("*.txt", path=str(tmp_path.parent))
        assert "error" in result
        assert "escape" in result["error"].lower() or "boundary" in result["error"].lower()

    def test_grep_search_should_return_structured_error_for_absolute_scope_outside_root(
        self, component: FileSystemToolComponent, tmp_path: Path
    ) -> None:
        result = component._grep_search("foo", path=str(tmp_path.parent))
        assert "error" in result
        assert "escape" in result["error"].lower() or "boundary" in result["error"].lower()


class TestStructuredToolErrorEnvelope:
    """Slice 33 — StructuredTool wrappers serialize errors as JSON envelopes.

    The Tool Mode contract: the agent invokes a StructuredTool and receives a
    string. That string MUST be JSON-decodable into a dict whose `error` key
    explains the failure — never an unhandled Python exception that surfaces
    as a tool-call crash to the agent loop.
    """

    async def test_read_tool_wrapper_should_return_json_error_for_dotdot_escape(
        self, component: FileSystemToolComponent
    ) -> None:
        tools = {tool.name: tool for tool in await component._get_tools()}
        output = tools["read_file"].invoke({"path": "../escape.txt"})
        payload = json.loads(output)
        assert "error" in payload

    async def test_glob_tool_wrapper_should_return_json_error_for_dotdot_scope(
        self, component: FileSystemToolComponent
    ) -> None:
        tools = {tool.name: tool for tool in await component._get_tools()}
        output = tools["glob_search"].invoke({"pattern": "*.txt", "path": "../"})
        payload = json.loads(output)
        assert "error" in payload

    async def test_grep_tool_wrapper_should_return_json_error_for_dotdot_scope(
        self, component: FileSystemToolComponent
    ) -> None:
        tools = {tool.name: tool for tool in await component._get_tools()}
        output = tools["grep_search"].invoke({"pattern": "foo", "path": "../"})
        payload = json.loads(output)
        assert "error" in payload

    async def test_write_tool_wrapper_should_return_json_error_for_dotdot_escape(
        self, component: FileSystemToolComponent
    ) -> None:
        tools = {tool.name: tool for tool in await component._get_tools()}
        output = tools["write_file"].invoke({"path": "../escape.txt", "content": "x"})
        payload = json.loads(output)
        assert "error" in payload

    async def test_edit_tool_wrapper_should_return_json_error_for_dotdot_escape(
        self, component: FileSystemToolComponent
    ) -> None:
        tools = {tool.name: tool for tool in await component._get_tools()}
        output = tools["edit_file"].invoke(
            {"path": "../escape.txt", "old_string": "x", "new_string": "y"},
        )
        payload = json.loads(output)
        assert "error" in payload


class TestBug02GlobTruncationDropsNestedSilently:
    """BUG-02 (T2-001) — `glob_search` silently drops nested results when truncated.

    Scenario from the report: a flat sibling directory with 100+ matches fills
    the result cap entirely, and files in nested subdirectories are silently
    omitted with no signal beyond `truncated: True`. The agent has no way to
    learn which branches went unrepresented.

    Fix contract: when truncation occurs, the response must enumerate the
    top-level branches under the search base whose matches were not surfaced,
    so the agent can narrow with a `path=` argument and recover them.
    """

    def test_should_signal_truncated_branches_when_flat_dir_fills_cap_and_nested_branch_is_dropped(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        # Arrange — exactly the bug-report scenario.
        flat = sandbox / "flat"
        flat.mkdir()
        for i in range(110):
            (flat / f"f{i:03d}.txt").write_text("x", encoding="utf-8")
        deep = sandbox / "deep" / "deeper" / "deepest"
        deep.mkdir(parents=True)
        (deep / "must_find_me.txt").write_text("important", encoding="utf-8")

        # Act
        result = component._glob_search("**/*.txt")

        # Assert — agent must NOT silently lose the nested branch.
        assert result["status"] == "ok"
        assert result["truncated"] is True
        # The nested branch must be discoverable from the response: either
        # `must_find_me.txt` is in matches, or `deep` is named in the
        # truncation signal so the agent knows where to look.
        nested_in_matches = any("must_find_me.txt" in p for p in result["matches"])
        truncated_branches = result.get("truncated_branches", [])
        deep_in_signal = "deep" in truncated_branches
        assert nested_in_matches or deep_in_signal, (
            "When truncation drops a whole branch, the response MUST surface "
            "either the file itself or the branch name. "
            f"matches sample={result['matches'][:3]}, "
            f"truncated_branches={truncated_branches}"
        )

    def test_should_emit_truncated_branches_field_when_truncated_is_true(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        # Stricter: the structured-error contract for truncation is that
        # `truncated_branches` exists alongside `truncated: True`.
        flat = sandbox / "flat"
        flat.mkdir()
        for i in range(110):
            (flat / f"f{i:03d}.txt").write_text("x", encoding="utf-8")
        deep = sandbox / "deep"
        deep.mkdir()
        (deep / "leaf.txt").write_text("y", encoding="utf-8")

        result = component._glob_search("**/*.txt")
        assert result["truncated"] is True
        assert "truncated_branches" in result, (
            "When truncated=True the response MUST include `truncated_branches` "
            f"so the agent has a non-silent signal. Got keys: {list(result.keys())}"
        )
        # Sorted, deterministic, top-level relative paths under the search base.
        assert isinstance(result["truncated_branches"], list)
        assert result["truncated_branches"] == sorted(result["truncated_branches"])

    def test_should_have_empty_truncated_branches_when_not_truncated(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        # Sanity: small result set must not falsely report truncated branches.
        (sandbox / "a.txt").write_text("x", encoding="utf-8")
        (sandbox / "b.txt").write_text("y", encoding="utf-8")
        result = component._glob_search("*.txt")
        assert result["truncated"] is False
        assert result.get("truncated_branches", []) == []


class TestBug03EmptyRootPathSilentlyDefaultsToCwd:
    """BUG-03 (UI-022) — empty `root_path` silently resolves to the process CWD.

    Scenario: when an agent invokes the tool via Tool Mode, the UI's
    `required=True` constraint on `root_path` is bypassed (each StructuredTool
    has its own per-operation args schema; `root_path` is component-level
    config). With an empty/None/whitespace value, `Path("").resolve()` returns
    the CWD — in a container that's typically `/app/`. The tool then accepts
    every operation against the CWD as if it were a legitimate sandbox.

    Fix contract: the public methods MUST return a structured error mentioning
    `root_path` before any I/O, regardless of whether root_path is "", None,
    or whitespace-only.
    """

    def test_should_return_structured_error_when_root_path_is_empty_string(self) -> None:
        component = FileSystemToolComponent(root_path="", read_only=False)
        result = component._read_file("anything.txt")
        assert "error" in result, f"Expected structured error, got: {result}"
        assert "root_path" in result["error"].lower()
        assert "required" in result["error"].lower() or "empty" in result["error"].lower()

    def test_should_return_structured_error_when_root_path_is_whitespace_only(self) -> None:
        component = FileSystemToolComponent(root_path="   ", read_only=False)
        result = component._read_file("anything.txt")
        assert "error" in result, f"Expected structured error, got: {result}"
        assert "root_path" in result["error"].lower()

    def test_should_return_structured_error_when_root_path_is_none(self) -> None:
        # The current code raises TypeError on None — must also be converted
        # into a structured error envelope (no raise from the public methods).
        component = FileSystemToolComponent(root_path=None, read_only=False)
        result = component._read_file("anything.txt")
        assert "error" in result, f"Expected structured error, got: {result}"
        assert "root_path" in result["error"].lower()

    def test_should_not_read_files_from_cwd_when_root_path_is_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The actual security implication of the bug: the agent MUST NOT be
        # able to read files from the process working directory just because
        # root_path was left blank. Set CWD to a place with a known file,
        # then verify _read_file does NOT read it.
        monkeypatch.chdir(tmp_path)
        marker = tmp_path / "should_never_be_readable_via_empty_root.txt"
        marker.write_text("compromised", encoding="utf-8")

        component = FileSystemToolComponent(root_path="", read_only=False)
        result = component._read_file(marker.name)

        assert "error" in result, (
            f"Empty root_path must NEVER read from CWD. Got: {result}. "
            "This is the sandbox-escape-via-misconfig path from the bug report."
        )
        assert result.get("status") != "ok"

    def test_glob_search_should_return_structured_error_when_root_path_is_empty(self) -> None:
        component = FileSystemToolComponent(root_path="", read_only=False)
        result = component._glob_search("**/*.txt")
        assert "error" in result
        assert "root_path" in result["error"].lower()

    def test_grep_search_should_return_structured_error_when_root_path_is_empty(self) -> None:
        component = FileSystemToolComponent(root_path="", read_only=False)
        result = component._grep_search("foo")
        assert "error" in result
        assert "root_path" in result["error"].lower()

    def test_write_file_should_return_structured_error_when_root_path_is_empty(self) -> None:
        component = FileSystemToolComponent(root_path="", read_only=False)
        result = component._write_file("anything.txt", "x")
        assert "error" in result
        assert "root_path" in result["error"].lower()

    def test_edit_file_should_return_structured_error_when_root_path_is_empty(self) -> None:
        component = FileSystemToolComponent(root_path="", read_only=False)
        result = component._edit_file("anything.txt", old_string="x", new_string="y")
        assert "error" in result
        assert "root_path" in result["error"].lower()


class TestDenyListSensitivePaths:
    """Slice 34 — basenames and path fragments matching credential patterns are rejected.

    Even when root_path covers a sensitive directory (a flow-author misconfig
    such as setting root_path to $HOME), the agent must not be able to
    read/write files like .env, id_rsa*, *.pem, *.key, credentials*, or any
    file under .ssh/, .aws/, .gnupg/, .docker/, .kube/, .git/. This is the
    "default-deny inside an allowed root" pattern from Claude Code Sandboxing
    and OWASP LLM06 (Excessive Agency).
    """

    def test_should_reject_read_when_basename_is_dotenv(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        (sandbox / ".env").write_text("SECRET=x\n", encoding="utf-8")
        result = component._read_file(".env")
        assert "error" in result
        assert "denied" in result["error"].lower() or "sensitive" in result["error"].lower()

    def test_should_reject_read_when_basename_starts_with_id_rsa(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        (sandbox / "id_rsa").write_text("private", encoding="utf-8")
        result = component._read_file("id_rsa")
        assert "error" in result
        assert "denied" in result["error"].lower() or "sensitive" in result["error"].lower()

    def test_should_reject_read_when_basename_is_id_rsa_pub(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        (sandbox / "id_rsa.pub").write_text("public", encoding="utf-8")
        result = component._read_file("id_rsa.pub")
        assert "error" in result

    def test_should_reject_read_when_basename_is_id_ed25519(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        (sandbox / "id_ed25519").write_text("private", encoding="utf-8")
        result = component._read_file("id_ed25519")
        assert "error" in result

    def test_should_reject_read_when_extension_is_pem(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        (sandbox / "cert.pem").write_text("-----BEGIN", encoding="utf-8")
        result = component._read_file("cert.pem")
        assert "error" in result

    def test_should_reject_read_when_extension_is_key(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        (sandbox / "private.key").write_text("-----BEGIN", encoding="utf-8")
        result = component._read_file("private.key")
        assert "error" in result

    def test_should_reject_read_when_basename_starts_with_credentials(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        (sandbox / "credentials.json").write_text("{}", encoding="utf-8")
        result = component._read_file("credentials.json")
        assert "error" in result

    def test_should_reject_path_under_dot_ssh_directory(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        ssh_dir = sandbox / ".ssh"
        ssh_dir.mkdir()
        (ssh_dir / "known_hosts").write_text("...", encoding="utf-8")
        result = component._read_file(".ssh/known_hosts")
        assert "error" in result

    def test_should_reject_path_under_dot_aws_directory(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        aws_dir = sandbox / ".aws"
        aws_dir.mkdir()
        (aws_dir / "config").write_text("...", encoding="utf-8")
        result = component._read_file(".aws/config")
        assert "error" in result

    def test_should_reject_path_under_dot_git_directory(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        git_dir = sandbox / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("[remote]", encoding="utf-8")
        result = component._read_file(".git/config")
        assert "error" in result

    def test_should_reject_writing_to_denied_basename(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        result = component._write_file(".env", "SECRET=x\n")
        assert "error" in result
        # Side effect must NOT have happened.
        assert not (sandbox / ".env").exists()

    def test_should_reject_writing_under_denied_directory_fragment(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        (sandbox / ".ssh").mkdir()
        result = component._write_file(".ssh/authorized_keys", "ssh-rsa AAAA...")
        assert "error" in result
        assert not (sandbox / ".ssh" / "authorized_keys").exists()

    def test_should_reject_editing_denied_basename(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        # Even if the file pre-exists, edits are rejected on denied paths.
        (sandbox / ".env").write_text("OLD=1\n", encoding="utf-8")
        result = component._edit_file(".env", old_string="OLD=1", new_string="NEW=2")
        assert "error" in result
        # Disk content must remain unchanged.
        assert (sandbox / ".env").read_text(encoding="utf-8") == "OLD=1\n"

    def test_should_allow_normal_path_with_dot_in_name(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        # A file named config.json must NOT be rejected — only specific
        # credential patterns are denied. Sanity-check that the deny-list
        # is not over-broad.
        (sandbox / "config.json").write_text('{"a":1}', encoding="utf-8")
        result = component._read_file("config.json")
        assert result.get("status") == "ok", f"Got: {result}"

    def test_should_allow_basename_that_only_contains_env_as_substring(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        # `myenv.txt` is NOT `.env` — must NOT be denied.
        (sandbox / "myenv.txt").write_text("not a secret", encoding="utf-8")
        result = component._read_file("myenv.txt")
        assert result.get("status") == "ok", f"Got: {result}"

    def test_should_be_case_insensitive_for_denied_basenames(
        self, component: FileSystemToolComponent, sandbox: Path
    ) -> None:
        # Case-folded check matches Windows semantics and prevents trivial
        # bypass via casing. ID_RSA must be denied like id_rsa.
        (sandbox / "ID_RSA").write_text("private", encoding="utf-8")
        result = component._read_file("ID_RSA")
        assert "error" in result


class TestHardlinkRejection:
    """Slice 35 — files with st_nlink > 1 are rejected.

    A hardlink inside the sandbox pointing to a file outside (e.g. /etc/shadow)
    bypasses Path.resolve() + is_relative_to() because hardlinks share an
    inode but the path string stays inside the sandbox. The fix: stat the
    resolved target and refuse if its link count is greater than 1. This is
    fail-closed — a legitimate file with multiple links is rare in agent
    workspaces, and the security gain (closing the hardlink-escape class
    documented in GHSA-34x7-hfp2-rc4v) outweighs the rare false positive.
    """

    def _make_hardlink(self, source: Path, dest: Path) -> bool:
        """Try to create a hardlink; return False if the FS does not allow it."""
        import os as _os

        try:
            _os.link(source, dest)
        except (OSError, NotImplementedError):
            return False
        return True

    def test_should_reject_read_when_target_has_multiple_hardlinks(
        self, component: FileSystemToolComponent, sandbox: Path, tmp_path: Path
    ) -> None:
        outside = tmp_path.parent / f"{tmp_path.name}-hardlink-secret.txt"
        outside.write_text("secret content", encoding="utf-8")
        if not self._make_hardlink(outside, sandbox / "linked.txt"):
            pytest.skip("Hardlink creation unsupported in this environment")
        result = component._read_file("linked.txt")
        assert "error" in result
        assert "hardlink" in result["error"].lower() or "link count" in result["error"].lower()

    def test_should_reject_write_when_target_has_multiple_hardlinks(
        self, component: FileSystemToolComponent, sandbox: Path, tmp_path: Path
    ) -> None:
        # Pre-create a hardlink inside the sandbox; agent-driven write must
        # not modify the linked outside file.
        outside = tmp_path.parent / f"{tmp_path.name}-hardlink-target.txt"
        outside.write_text("original", encoding="utf-8")
        if not self._make_hardlink(outside, sandbox / "linked.txt"):
            pytest.skip("Hardlink creation unsupported in this environment")
        result = component._write_file("linked.txt", "evil")
        assert "error" in result
        # Outside file must remain untouched.
        assert outside.read_text(encoding="utf-8") == "original"

    def test_should_reject_edit_when_target_has_multiple_hardlinks(
        self, component: FileSystemToolComponent, sandbox: Path, tmp_path: Path
    ) -> None:
        outside = tmp_path.parent / f"{tmp_path.name}-hardlink-edit.txt"
        outside.write_text("OLD\n", encoding="utf-8")
        if not self._make_hardlink(outside, sandbox / "linked.txt"):
            pytest.skip("Hardlink creation unsupported in this environment")
        result = component._edit_file("linked.txt", old_string="OLD", new_string="NEW")
        assert "error" in result
        assert outside.read_text(encoding="utf-8") == "OLD\n"

    def test_should_allow_regular_file_with_single_link(
        self, component: FileSystemToolComponent
    ) -> None:
        # Sanity: hello.txt has st_nlink == 1, must still work.
        result = component._read_file("hello.txt")
        assert result.get("status") == "ok", f"Got: {result}"

    def test_should_allow_writing_a_brand_new_file(
        self, component: FileSystemToolComponent
    ) -> None:
        # New-file writes must NOT trigger the hardlink check (nothing to stat).
        result = component._write_file("brand_new.txt", "data")
        assert result.get("status") == "created", f"Got: {result}"


class TestOpenNoFollowTOCTOU:
    """Slice 36 — opens use O_NOFOLLOW to close the post-validate TOCTOU window.

    A symlink injected between validate and open cannot redirect the I/O
    outside the sandbox. `Path.resolve()` runs at validate time. Between then and the actual
    `open()` syscall there is a window in which an external attacker (or a
    second concurrent agent) can replace the resolved file with a symlink
    pointing anywhere on the host. Without O_NOFOLLOW the open silently
    follows the symlink. With O_NOFOLLOW the kernel returns ELOOP and the
    operation fails closed.

    To test deterministically we monkeypatch `_validate_path` to perform
    the TOCTOU swap in-band: the wrapper calls the real validator, then
    replaces the resolved file with a symlink pointing OUTSIDE the sandbox
    before returning. Without O_NOFOLLOW the test would observe the
    outside file's contents leak into the read result; with O_NOFOLLOW the
    open returns a structured error.
    """

    def _make_symlink(self, link: Path, target: Path) -> bool:
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            return False
        return True

    def test_read_should_refuse_when_resolved_target_is_swapped_to_symlink(
        self,
        component: FileSystemToolComponent,
        sandbox: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        outside = tmp_path.parent / f"{tmp_path.name}-toctou-leaked.txt"
        outside.write_text("SECRET-LEAKED", encoding="utf-8")
        target = sandbox / "innocent.txt"
        target.write_text("real content", encoding="utf-8")

        original = type(component)._validate_path

        def racing_validate(self_: FileSystemToolComponent, path: str) -> Path:
            result = original(self_, path)
            if path == "innocent.txt":
                target.unlink()
                if not self._make_symlink(target, outside):
                    pytest.skip("Symlink creation unsupported in this environment")
            return result

        monkeypatch.setattr(type(component), "_validate_path", racing_validate)

        result = component._read_file("innocent.txt")
        assert "error" in result, f"O_NOFOLLOW must refuse symlink at open; got: {result}"
        # Outside file content must NOT leak into the structured result.
        assert "SECRET-LEAKED" not in str(result)

    def test_write_should_refuse_when_resolved_target_is_swapped_to_symlink(
        self,
        component: FileSystemToolComponent,
        sandbox: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        outside = tmp_path.parent / f"{tmp_path.name}-toctou-write-target.txt"
        outside.write_text("ORIGINAL_OUTSIDE", encoding="utf-8")
        target = sandbox / "to_overwrite.txt"
        target.write_text("inside content", encoding="utf-8")

        original = type(component)._validate_path

        def racing_validate(self_: FileSystemToolComponent, path: str) -> Path:
            result = original(self_, path)
            if path == "to_overwrite.txt":
                target.unlink()
                if not self._make_symlink(target, outside):
                    pytest.skip("Symlink creation unsupported in this environment")
            return result

        monkeypatch.setattr(type(component), "_validate_path", racing_validate)

        result = component._write_file("to_overwrite.txt", "EVIL_PAYLOAD")
        assert "error" in result, f"O_NOFOLLOW must refuse symlink at open; got: {result}"
        # The outside file MUST be unchanged — no write through the symlink.
        assert outside.read_text(encoding="utf-8") == "ORIGINAL_OUTSIDE"

    def test_edit_should_refuse_when_resolved_target_is_swapped_to_symlink(
        self,
        component: FileSystemToolComponent,
        sandbox: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        outside = tmp_path.parent / f"{tmp_path.name}-toctou-edit-target.txt"
        outside.write_text("OUTSIDE_BEFORE\n", encoding="utf-8")
        target = sandbox / "to_edit.txt"
        target.write_text("OUTSIDE_BEFORE\n", encoding="utf-8")

        original = type(component)._validate_path

        def racing_validate(self_: FileSystemToolComponent, path: str) -> Path:
            result = original(self_, path)
            if path == "to_edit.txt":
                target.unlink()
                if not self._make_symlink(target, outside):
                    pytest.skip("Symlink creation unsupported in this environment")
            return result

        monkeypatch.setattr(type(component), "_validate_path", racing_validate)

        result = component._edit_file("to_edit.txt", old_string="OUTSIDE_BEFORE", new_string="EVIL_AFTER")
        assert "error" in result, f"O_NOFOLLOW must refuse symlink at open; got: {result}"
        # The outside file MUST be unchanged — neither read-modified nor written-through.
        assert outside.read_text(encoding="utf-8") == "OUTSIDE_BEFORE\n"

    def test_read_should_still_succeed_for_normal_regular_file(
        self, component: FileSystemToolComponent
    ) -> None:
        # Sanity: O_NOFOLLOW is a no-op for normal regular files.
        result = component._read_file("hello.txt")
        assert result.get("status") == "ok", f"Got: {result}"
