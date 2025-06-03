from typing import TYPE_CHECKING

import anyio
import pytest
from langflow.src.backend.base.langflow.components.tools.file_manipulation import FileManipulation

if TYPE_CHECKING:
    from langflow.field_typing import Tool

# Constants for tests
LARGE_FILE_CONTENT = "line\n" * 15  # More than PREVIEW_LINE_LIMIT
BINARY_FILE_CONTENT = bytes([0x89, 0x50, 0x4E, 0x47])  # PNG header


@pytest.fixture(autouse=True)
async def setup_test_files(tmp_path):
    # Create various test files and directories
    """Asynchronously creates a set of test files and directories in the given temporary path.

    The generated structure includes text files, a large file, a binary file, an empty file, and a nested directory with a file, suitable for comprehensive file manipulation testing.

    Args:
        tmp_path: The base temporary directory path for creating test files and folders.

    Returns:
        The path to the temporary directory containing the created test files and directories.
    """
    await anyio.Path(tmp_path / "test.txt").write_text("hello\nworld\n")
    await anyio.Path(tmp_path / "large.txt").write_text(LARGE_FILE_CONTENT)
    await anyio.Path(tmp_path / "binary.png").write_bytes(BINARY_FILE_CONTENT)
    await anyio.Path(tmp_path / "empty.txt").write_text("")
    await anyio.Path(tmp_path / "nested").mkdir()
    await anyio.Path(tmp_path / "nested/file.txt").write_text("nested content")
    return tmp_path


class TestFileManipulation:
    @pytest.fixture
    def component_class(self):
        """Returns the FileManipulation component class for use in tests."""
        return FileManipulation

    @pytest.fixture
    def default_kwargs(self, tmp_path):
        """Provides default keyword arguments for initializing the component.

        The workspace folder is set to the given temporary path.

        Args:
            tmp_path: Pytest temporary directory fixture.

        Returns:
            A dictionary of default kwargs for component initialization.
        """
        return {"workspace_folder": str(tmp_path)}

    @pytest.mark.asyncio
    async def test_initialization_and_build_toolkit(self, tmp_path, default_kwargs):
        """Tests that the FileManipulation component initializes correctly.

        Its frontend node reflects the provided workspace folder.
        """
        component = self.component_class(**default_kwargs)

        # Act
        frontend_node = component.to_frontend_node()

        # Assert
        assert component.workspace_folder == str(tmp_path)
        assert frontend_node["template"]["workspace_folder"]["value"] == str(tmp_path)

        # Test that it builds a toolkit without errors
        tools = component.build_toolkit()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_build_toolkit(self, component_class, default_kwargs):
        # Arrange
        """Tests that the FileManipulation component builds a toolkit containing all expected tools.

        Asserts that the toolkit is a list of 10 tools with the correct names.
        """
        component = component_class(**default_kwargs)

        # Act
        tools = component.build_toolkit()

        # Assert
        assert isinstance(tools, list)
        assert len(tools) == 10
        tool_names = {tool.name for tool in tools}
        expected_names = {
            "view_file",
            "str_replace",
            "insert_at_line",
            "create_file",
            "undo_edit",
            "create_directory",
            "list_directory",
            "move_file",
            "search_files",
            "search_code",
        }
        assert tool_names == expected_names

    @pytest.mark.asyncio
    async def test_view_file(self, tmp_path):
        """Tests that the 'view_file' tool correctly reads a file and returns its contents with line numbers."""
        file_path = tmp_path / "test.txt"
        await anyio.Path(file_path).write_text("hello\nworld\n")
        component = FileManipulation(workspace_folder=str(tmp_path))
        tools = component.build_toolkit()
        view_file_tool: Tool = next(t for t in tools if t.name == "view_file")
        result = await view_file_tool.ainvoke({"path": "test.txt"})
        assert "1: hello" in result
        assert "2: world" in result

    @pytest.mark.asyncio
    async def test_str_replace_functionality(self, sample_workspace):
        """Tests the 'str_replace' tool for text replacement in files.

        This test verifies that the tool can successfully locate and replace
        text within a file. It asserts that the replacement was successful
        and the file content is updated accordingly.
        """
        file_path = sample_workspace / "replace.txt"
        await anyio.Path(file_path).write_text("foo bar baz\n")
        component = FileManipulation(workspace_folder=str(sample_workspace))
        tools = component.build_toolkit()
        str_replace_tool: Tool = next(t for t in tools if t.name == "str_replace")
        result = await str_replace_tool.ainvoke({"path": "replace.txt", "old_str": "bar", "new_str": "qux"})
        assert "Successfully replaced text" in result
        assert "qux" in await anyio.Path(file_path).read_text()

    @pytest.mark.asyncio
    async def test_undo_edit_functionality(self, sample_workspace):
        """Tests the 'undo_edit' tool functionality.

        This test edits a file using str_replace, then uses the undo_edit
        functionality to restore the file to its original state after an edit.
        It uses the undo_edit tool and verifies that the file content is
        reverted to its original state.
        """
        file_path = sample_workspace / "undo.txt"
        await anyio.Path(file_path).write_text("original\n")
        component = FileManipulation(workspace_folder=str(sample_workspace))
        tools = component.build_toolkit()
        str_replace_tool: Tool = next(t for t in tools if t.name == "str_replace")
        undo_edit_tool: Tool = next(t for t in tools if t.name == "undo_edit")

        # Perform an edit
        await str_replace_tool.ainvoke({"path": "undo.txt", "old_str": "original", "new_str": "modified"})

        # Undo the edit
        result = await undo_edit_tool.ainvoke({"path": "undo.txt"})
        assert "Successfully undid changes" in result
        assert await anyio.Path(file_path).read_text() == "original\n"

    @pytest.mark.asyncio
    async def test_create_directory_functionality(self, sample_workspace):
        """Tests the 'create_directory' tool.

        This test uses the create_directory tool to create a new directory
        in the workspace and verifies that the directory exists in the workspace.
        """
        component = FileManipulation(workspace_folder=str(sample_workspace))
        tools = component.build_toolkit()
        create_directory_tool: Tool = next(t for t in tools if t.name == "create_directory")
        result = await create_directory_tool.ainvoke({"directory_path": "mydir"})
        assert "created directory" in result or "already exists" in result
        assert await anyio.Path(sample_workspace / "mydir").is_dir()

    @pytest.mark.asyncio
    async def test_move_file_functionality(self, sample_workspace):
        """Tests the 'move_file' tool for moving files within the workspace.

        This test moves a file to a new location as the destination, and asserts
        that the source no longer exists and the destination file is present.
        """
        src = sample_workspace / "src.txt"
        await anyio.Path(src).write_text("move me")
        component = FileManipulation(workspace_folder=str(sample_workspace))
        tools = component.build_toolkit()
        move_file_tool: Tool = next(t for t in tools if t.name == "move_file")
        result = await move_file_tool.ainvoke({"source_path": "src.txt", "destination_path": "dest.txt"})
        assert "moved file" in result or "Successfully moved" in result
        assert not await anyio.Path(src).exists()
        assert await anyio.Path(sample_workspace / "dest.txt").exists()

    @pytest.mark.asyncio
    async def test_search_files_functionality(self, sample_workspace):
        """Tests the 'search_files' tool for finding files matching a pattern.

        This test searches for files matching a given pattern in the workspace.
        It uses a specific pattern, and asserts that the expected file is
        present in the results.
        """
        await anyio.Path(sample_workspace / "findme.txt").write_text("x")
        await anyio.Path(sample_workspace / "other.txt").write_text("y")
        component = FileManipulation(workspace_folder=str(sample_workspace))
        tools = component.build_toolkit()
        search_files_tool: Tool = next(t for t in tools if t.name == "search_files")
        result = await search_files_tool.ainvoke({"search_pattern": "findme"})
        assert "findme.txt" in result

    @pytest.mark.asyncio
    async def test_search_code_functionality(self, sample_workspace):
        """Tests the 'search_code' tool for finding code snippets.

        This test searches for code snippets containing a given pattern.
        It uses a specific search pattern and file pattern, and asserts that
        the correct file and code snippet are present in the results.
        """
        await anyio.Path(sample_workspace / "code1.py").write_text("print('hello world')\n")
        await anyio.Path(sample_workspace / "code2.py").write_text("print('goodbye world')\n")
        component = FileManipulation(workspace_folder=str(sample_workspace))
        tools = component.build_toolkit()
        search_code_tool: Tool = next(t for t in tools if t.name == "search_code")
        result = await search_code_tool.ainvoke({"search_pattern": "hello", "file_pattern": "*.py"})
        assert "code1.py" in result
        assert "hello" in result

    @pytest.mark.asyncio
    async def test_view_file_edge_cases(self, tmp_path):
        """Tests edge cases for the 'view_file' tool.

        Including non-existent files, empty files, large files with truncated
        output, specific line ranges, and invalid view ranges.
        """
        component = FileManipulation(workspace_folder=str(tmp_path))
        tools = component.build_toolkit()
        view_file_tool: Tool = next(t for t in tools if t.name == "view_file")

        # Test non-existent file
        result = await view_file_tool.ainvoke({"path": "nonexistent.txt"})
        assert "Error: File not found" in result

        # Test empty file
        result = await view_file_tool.ainvoke({"path": "empty.txt"})
        assert result.strip() == ""

        # Test large file
        result = await view_file_tool.ainvoke({"path": "large.txt"})
        assert "... and" in result  # Should show truncated content

        # Test view range
        result = await view_file_tool.ainvoke({"path": "test.txt", "view_range": [1, 1]})
        assert "1: hello" in result
        assert "2: world" not in result

        # Test invalid view range
        result = await view_file_tool.ainvoke({"path": "test.txt", "view_range": [100, 101]})
        assert "Error: Start line" in result

    @pytest.mark.asyncio
    async def test_str_replace_edge_cases(self, tmp_path):
        """Tests edge cases for the 'str_replace' tool.

        Including non-existent files, missing target text, multiple matches,
        and empty replacement strings.

        This test verifies proper error handling for various edge case conditions
        and that file content is correctly updated when replacing text with an
        empty string.
        """
        component = FileManipulation(workspace_folder=str(tmp_path))
        tools = component.build_toolkit()
        str_replace_tool: Tool = next(t for t in tools if t.name == "str_replace")

        # Test non-existent file
        result = await str_replace_tool.ainvoke({"path": "nonexistent.txt", "old_str": "foo", "new_str": "bar"})
        assert "Error: File not found" in result

        # Test non-existent text
        result = await str_replace_tool.ainvoke({"path": "test.txt", "old_str": "nonexistent", "new_str": "new"})
        assert "Error: Text not found" in result

        # Test multiple matches
        await anyio.Path(tmp_path / "multiple.txt").write_text("test test test")
        result = await str_replace_tool.ainvoke({"path": "multiple.txt", "old_str": "test", "new_str": "new"})
        assert "Error: Multiple matches" in result

        # Test empty replacement
        result = await str_replace_tool.ainvoke({"path": "test.txt", "old_str": "hello", "new_str": ""})
        content = await anyio.Path(tmp_path / "test.txt").read_text()
        assert content == "\nworld\n"

    @pytest.mark.asyncio
    async def test_insert_at_line_edge_cases(self, tmp_path):
        """Tests edge cases for the 'insert_at_line' tool.

        Including invalid line numbers, inserting at the beginning and end of
        a file, and inserting into an empty file. Asserts that appropriate
        success or error messages are returned and that file contents are
        updated as expected.
        """
        component = FileManipulation(workspace_folder=str(tmp_path))
        tools = component.build_toolkit()
        insert_at_line_tool: Tool = next(t for t in tools if t.name == "insert_at_line")

        # Test insert at beginning
        result = await insert_at_line_tool.ainvoke({"path": "test.txt", "insert_line": 1, "new_str": "first"})
        assert "Successfully" in result
        content = await anyio.Path(tmp_path / "test.txt").read_text()
        assert content.startswith("first\n")

        # Test insert beyond file end
        result = await insert_at_line_tool.ainvoke({"path": "test.txt", "insert_line": 100, "new_str": "beyond"})
        assert "Error: Line number" in result

        # Test insert in empty file
        result = await insert_at_line_tool.ainvoke({"path": "empty.txt", "insert_line": 1, "new_str": "content"})
        assert "Successfully" in result
        content = await anyio.Path(tmp_path / "empty.txt").read_text()
        assert "content" in content

    @pytest.mark.asyncio
    async def test_create_file_edge_cases(self, tmp_path):
        """Tests edge cases for the 'create_file' tool.

        Including creating files in non-existent directories, creating files
        with empty content, and overwriting existing files.
        """
        component = FileManipulation(workspace_folder=str(tmp_path))
        tools = component.build_toolkit()
        create_file_tool: Tool = next(t for t in tools if t.name == "create_file")

        # Test create in non-existent directory
        result = await create_file_tool.ainvoke({"path": "newdir/file.txt", "file_text": "content"})
        assert "Successfully" in result
        assert await anyio.Path(tmp_path / "newdir/file.txt").exists()

        # Test create with empty content
        result = await create_file_tool.ainvoke({"path": "empty_new.txt", "file_text": ""})
        assert "Successfully" in result
        assert await anyio.Path(tmp_path / "empty_new.txt").exists()

        # Test overwrite existing file
        result = await create_file_tool.ainvoke({"path": "test.txt", "file_text": "overwritten"})
        assert "Successfully" in result
        content = await anyio.Path(tmp_path / "test.txt").read_text()
        assert content == "overwritten"

    @pytest.mark.asyncio
    async def test_create_directory_edge_cases(self, tmp_path):
        """Tests edge cases for the 'create_directory' tool.

        Including creating nested directories, handling existing directories,
        and attempting to create a directory with the same name as an
        existing file.
        """
        component = FileManipulation(workspace_folder=str(tmp_path))
        tools = component.build_toolkit()
        create_directory_tool: Tool = next(t for t in tools if t.name == "create_directory")

        # Test create nested directories
        result = await create_directory_tool.ainvoke({"directory_path": "a/b/c"})
        assert "Successfully" in result
        assert await anyio.Path(tmp_path / "a/b/c").is_dir()

        # Test create existing directory
        result = await create_directory_tool.ainvoke({"directory_path": "nested"})
        assert "already exists" in result

        # Test create directory with same name as file
        result = await create_directory_tool.ainvoke({"directory_path": "test.txt"})
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_list_directory_edge_cases(self, tmp_path):
        """Tests edge cases for the 'list_directory' tool.

        Including listing non-existent paths, empty directories, and nested
        directories.

        This test verifies that listing an empty directory returns a success
        message with no contents, and listing a nested directory correctly
        includes expected files.
        """
        component = FileManipulation(workspace_folder=str(tmp_path))
        tools = component.build_toolkit()
        list_directory_tool: Tool = next(t for t in tools if t.name == "list_directory")

        # Test list non-existent directory
        result = await list_directory_tool.ainvoke({"directory_path": "nonexistent"})
        assert "Error: Directory not found" in result

        # Test list empty directory
        await anyio.Path(tmp_path / "empty_dir").mkdir()
        result = await list_directory_tool.ainvoke({"directory_path": "empty_dir"})
        assert "Contents of" in result
        assert "directory" not in result.split("\n")[1:]

        # Test list nested directory
        result = await list_directory_tool.ainvoke({"directory_path": "nested"})
        assert "file.txt" in result

    @pytest.mark.asyncio
    async def test_move_file_edge_cases(self, tmp_path):
        """Tests edge cases for the 'move_file' tool.

        Including moving non-existent files, overwriting existing destinations,
        and moving directories.

        This test verifies proper error handling when source files do not exist,
        successful overwriting of an existing destination file, and proper
        movement of directories.
        """
        component = FileManipulation(workspace_folder=str(tmp_path))
        tools = component.build_toolkit()
        move_file_tool: Tool = next(t for t in tools if t.name == "move_file")

        # Test move non-existent file
        result = await move_file_tool.ainvoke({"source_path": "nonexistent.txt", "destination_path": "dest.txt"})
        assert "Error: Source not found" in result

        # Test move to existing destination
        await anyio.Path(tmp_path / "dest.txt").write_text("existing")
        result = await move_file_tool.ainvoke({"source_path": "test.txt", "destination_path": "dest.txt"})
        assert "Successfully" in result
        assert not await anyio.Path(tmp_path / "test.txt").exists()

        # Test move directory
        result = await move_file_tool.ainvoke({"source_path": "nested", "destination_path": "moved_dir"})
        assert "Successfully" in result
        assert await anyio.Path(tmp_path / "moved_dir").is_dir()

    @pytest.mark.asyncio
    async def test_search_files_edge_cases(self, tmp_path):
        """Tests edge cases for the 'search_files' tool.

        Including searching in non-existent directories, with no matches,
        and within nested directories.
        """
        component = FileManipulation(workspace_folder=str(tmp_path))
        tools = component.build_toolkit()
        search_files_tool: Tool = next(t for t in tools if t.name == "search_files")

        # Test search in non-existent directory
        result = await search_files_tool.ainvoke({"search_pattern": "test", "directory_path": "nonexistent"})
        assert "Error: Directory not found" in result

        # Test search with no matches
        result = await search_files_tool.ainvoke({"search_pattern": "nonexistent"})
        assert "No files matching" in result

        # Test search in nested directories
        result = await search_files_tool.ainvoke({"search_pattern": "file"})
        assert "nested/file.txt" in result

    @pytest.mark.asyncio
    async def test_search_code_edge_cases(self, tmp_path):
        """Tests edge cases for the 'search_code' tool.

        Including searching in non-existent directories, handling no matches,
        and ensuring binary files are skipped.
        """
        component = FileManipulation(workspace_folder=str(tmp_path))
        tools = component.build_toolkit()
        search_code_tool: Tool = next(t for t in tools if t.name == "search_code")

        # Create test files
        await anyio.Path(tmp_path / "code1.py").write_text("def test():\n    pass\n")
        await anyio.Path(tmp_path / "code2.py").write_text("# TODO: implement\n")

        # Test search with file pattern
        result = await search_code_tool.ainvoke({"search_pattern": "TODO", "file_pattern": "*.py"})
        assert "code2.py" in result
        assert "code1.py" not in result

        # Test search in non-existent directory
        result = await search_code_tool.ainvoke(
            {
                "search_pattern": "test",
                "file_pattern": "*.*",
                "directory_path": "nonexistent",
            }
        )
        assert "Error: Directory not found" in result

        # Test search with no matches
        result = await search_code_tool.ainvoke({"search_pattern": "nonexistent", "file_pattern": "*.*"})
        assert "No matches found" in result

        # Test search in binary file
        result = await search_code_tool.ainvoke({"search_pattern": "PNG", "file_pattern": "*.png"})
        assert "binary.png" not in result  # Should skip binary files
