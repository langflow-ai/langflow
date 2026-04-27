"""Unit tests for FileSystemToolComponent (sandboxed filesystem agent tool)."""

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
