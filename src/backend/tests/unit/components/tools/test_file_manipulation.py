import asyncio
import fnmatch
import anyio
import pytest
from langchain_core.tools import tool
from loguru import logger
from langflow.custom import Component
from langflow.field_typing import Tool
from langflow.io import Output, StrInput
from langflow.src.backend.base.langflow.components.tools.file_manipulation import FileManipulation

# Constants for tests
LARGE_FILE_CONTENT = "line\n" * 15  # More than PREVIEW_LINE_LIMIT
BINARY_FILE_CONTENT = bytes([0x89, 0x50, 0x4E, 0x47])  # PNG header

@pytest.fixture(autouse=True)
async def setup_test_files(tmp_path):
    # Create various test files and directories
    """
    Asynchronously creates a set of test files and directories in the given temporary path.
    
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
        """
        Returns the FileManipulation component class for use in tests.
        """
        return FileManipulation

    @pytest.fixture
    def default_kwargs(self, tmp_path):
        """
        Provides default keyword arguments for initializing the component with the workspace folder set to the given temporary path.
        
        Args:
            tmp_path: Temporary directory path used as the workspace folder.
        
        Returns:
            A dictionary with the workspace folder path.
        """
        return {"workspace_folder": str(tmp_path)}

    def test_component_initialization(self, component_class, default_kwargs):
        # Arrange
        """
        Tests that the FileManipulation component initializes correctly and its frontend node reflects the provided workspace folder.
        """
        component = component_class(**default_kwargs)

        # Act
        frontend_node = component.to_frontend_node()

        # Assert
        node_data = frontend_node["data"]["node"]
        assert node_data["template"]["workspace_folder"]["value"] == default_kwargs["workspace_folder"]

    def test_build_toolkit(self, component_class, default_kwargs):
        # Arrange
        """
        Tests that the FileManipulation component builds a toolkit containing all expected tools.
        
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
        """
        Tests that the 'view_file' tool correctly reads a file and returns its contents with line numbers.
        """
        file_path = tmp_path / "test.txt"
        await anyio.Path(file_path).write_text("hello\nworld\n")
        component = FileManipulation(workspace_folder=str(tmp_path))
        tools = component.build_toolkit()
        view_file_tool: Tool = next(t for t in tools if t.name == "view_file")
        result = await view_file_tool.ainvoke({"path": "test.txt"})
        assert "1: hello" in result
        assert "2: world" in result

    @pytest.mark.asyncio
    async def test_str_replace(self, tmp_path):
        """
        Tests that the 'str_replace' tool correctly replaces a substring in a file.
        
        Creates a file, performs a string replacement using the tool, and asserts that the replacement was successful and the file content is updated accordingly.
        """
        file_path = tmp_path / "replace.txt"
        await anyio.Path(file_path).write_text("foo bar baz\n")
        component = FileManipulation(workspace_folder=str(tmp_path))
        tools = component.build_toolkit()
        str_replace_tool: Tool = next(t for t in tools if t.name == "str_replace")
        result = await str_replace_tool.ainvoke({"path": "replace.txt", "old_str": "bar", "new_str": "qux"})
        assert "Successfully replaced text" in result
        assert "qux" in await anyio.Path(file_path).read_text()

    @pytest.mark.asyncio
    async def test_insert_at_line(self, tmp_path):
        """
        Tests inserting a string at a specified line in a file using the 'insert_at_line' tool.
        
        Creates a file, inserts a new string at the given line, and verifies that the insertion
        was successful and the file content was updated accordingly.
        """
        file_path = tmp_path / "insert.txt"
        await anyio.Path(file_path).write_text("line1\nline2\n")
        component = FileManipulation(workspace_folder=str(tmp_path))
        tools = component.build_toolkit()
        insert_at_line_tool: Tool = next(t for t in tools if t.name == "insert_at_line")
        result = await insert_at_line_tool.ainvoke({"path": "insert.txt", "insert_line": 2, "new_str": "inserted"})
        assert "Successfully inserted text" in result
        content = await anyio.Path(file_path).read_text()
        assert "inserted" in content

    @pytest.mark.asyncio
    async def test_undo_edit(self, tmp_path):
        """
        Tests that the undo_edit tool restores a file to its previous state after an edit.
        
        Creates a file, performs a string replacement, then invokes the undo_edit tool and verifies that the file content is reverted to its original state.
        """
        file_path = tmp_path / "undo.txt"
        await anyio.Path(file_path).write_text("original\n")
        component = FileManipulation(workspace_folder=str(tmp_path))
        tools = component.build_toolkit()
        str_replace_tool: Tool = next(t for t in tools if t.name == "str_replace")
        undo_edit_tool: Tool = next(t for t in tools if t.name == "undo_edit")
        await str_replace_tool.ainvoke({"path": "undo.txt", "old_str": "original", "new_str": "changed"})
        result = await undo_edit_tool.ainvoke({"path": "undo.txt"})
        assert "restored" in result or "Successfully restored" in result
        assert await anyio.Path(file_path).read_text() == "original\n"

    @pytest.mark.asyncio
    async def test_create_file(self, tmp_path):
        """
        Tests creating or updating a file with specified content in the workspace.
        
        Asserts that the file is created or updated successfully and that its contents match the provided text.
        """
        component = FileManipulation(workspace_folder=str(tmp_path))
        tools = component.build_toolkit()
        create_file_tool: Tool = next(t for t in tools if t.name == "create_file")
        result = await create_file_tool.ainvoke({"path": "newfile.txt", "file_text": "abc\ndef"})
        assert "Created file" in result or "Updated file" in result or "Successfully" in result
        assert await anyio.Path(tmp_path / "newfile.txt").read_text() == "abc\ndef"

    @pytest.mark.asyncio
    async def test_create_directory(self, tmp_path):
        """
        Tests creating a new directory using the create_directory tool.
        
        Asserts that the tool reports successful creation or existence of the directory and verifies that the directory exists in the workspace.
        """
        component = FileManipulation(workspace_folder=str(tmp_path))
        tools = component.build_toolkit()
        create_directory_tool: Tool = next(t for t in tools if t.name == "create_directory")
        result = await create_directory_tool.ainvoke({"directory_path": "mydir"})
        assert "created directory" in result or "already exists" in result
        assert await anyio.Path(tmp_path / "mydir").is_dir()

    @pytest.mark.asyncio
    async def test_list_directory(self, tmp_path):
        """
        Tests that the list_directory tool returns all files and subdirectories in the specified directory.
        """
        await anyio.Path(tmp_path / "a.txt").write_text("a")
        await anyio.Path(tmp_path / "b.txt").write_text("b")
        await anyio.Path(tmp_path / "subdir").mkdir()
        component = FileManipulation(workspace_folder=str(tmp_path))
        tools = component.build_toolkit()
        list_directory_tool: Tool = next(t for t in tools if t.name == "list_directory")
        result = await list_directory_tool.ainvoke({"directory_path": "."})
        assert "a.txt" in result
        assert "b.txt" in result
        assert "subdir" in result

    @pytest.mark.asyncio
    async def test_move_file(self, tmp_path):
        """
        Tests moving a file from a source to a destination within the workspace.
        
        Creates a source file, invokes the move file tool to move it to a new destination, and asserts that the source no longer exists and the destination file is present.
        """
        src = tmp_path / "src.txt"
        await anyio.Path(src).write_text("move me")
        component = FileManipulation(workspace_folder=str(tmp_path))
        tools = component.build_toolkit()
        move_file_tool: Tool = next(t for t in tools if t.name == "move_file")
        result = await move_file_tool.ainvoke({"source_path": "src.txt", "destination_path": "dest.txt"})
        assert "moved file" in result or "Successfully moved" in result
        assert not await anyio.Path(src).exists()
        assert await anyio.Path(tmp_path / "dest.txt").exists()

    @pytest.mark.asyncio
    async def test_search_files(self, tmp_path):
        """
        Tests that the 'search_files' tool correctly finds files matching a given pattern in the workspace.
        
        Creates test files, invokes the search tool with a specific pattern, and asserts that the expected file is present in the results.
        """
        await anyio.Path(tmp_path / "findme.txt").write_text("x")
        await anyio.Path(tmp_path / "other.txt").write_text("y")
        component = FileManipulation(workspace_folder=str(tmp_path))
        tools = component.build_toolkit()
        search_files_tool: Tool = next(t for t in tools if t.name == "search_files")
        result = await search_files_tool.ainvoke({"search_pattern": "findme"})
        assert "findme.txt" in result

    @pytest.mark.asyncio
    async def test_search_code(self, tmp_path):
        """
        Tests that the 'search_code' tool finds code matching a pattern in files matching a given pattern.
        
        Creates Python files with known content, invokes the search tool with a search pattern and file pattern, and asserts that the correct file and code snippet are present in the results.
        """
        await anyio.Path(tmp_path / "code1.py").write_text("print('hello world')\n")
        await anyio.Path(tmp_path / "code2.py").write_text("print('goodbye world')\n")
        component = FileManipulation(workspace_folder=str(tmp_path))
        tools = component.build_toolkit()
        search_code_tool: Tool = next(t for t in tools if t.name == "search_code")
        result = await search_code_tool.ainvoke({"search_pattern": "hello", "file_pattern": "*.py"})
        assert "code1.py" in result
        assert "hello world" in result

    @pytest.mark.asyncio
    async def test_view_file_edge_cases(self, tmp_path):
        """
        Tests edge cases for the 'view_file' tool, including non-existent files, empty files,
        large files with truncated output, specific line ranges, and invalid view ranges.
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
        """
        Tests edge cases for the string replacement tool, including handling of non-existent files, missing target text, multiple matches, and empty replacement strings.
        
        Verifies that appropriate error messages are returned for invalid operations and that file content is correctly updated when replacing text with an empty string.
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
        """
        Tests edge cases for inserting a string at a specific line in a file.
        
        Verifies correct behavior when inserting at the beginning of a file, attempting to insert beyond the end of a file, and inserting into an empty file. Asserts that appropriate success or error messages are returned and that file contents are updated as expected.
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
        """
        Tests edge cases for the 'create_file' tool, including creating files in non-existent directories, creating files with empty content, and overwriting existing files.
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
        """
        Tests edge cases for the create_directory tool, including creating nested directories, handling existing directories, and attempting to create a directory with the same name as an existing file.
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
        """
        Tests edge cases for listing directory contents, including non-existent, empty, and nested directories.
        
        Verifies that listing a non-existent directory returns an error, listing an empty directory returns a success message with no contents, and listing a nested directory correctly includes expected files.
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
        """
        Tests edge cases for the move_file tool, including moving non-existent files, overwriting existing destinations, and moving directories.
        
        Verifies correct error handling when the source file does not exist, successful overwriting of an existing destination file, and proper movement of directories.
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
        """
        Tests edge cases for the 'search_files' tool, including searching in non-existent directories, with no matches, and within nested directories.
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
        """
        Tests edge cases for the 'search_code' tool, including file pattern filtering, searching in non-existent directories, handling no matches, and ensuring binary files are skipped.
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
