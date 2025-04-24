import fnmatch
import os
import shutil
import subprocess

from langchain_core.tools import tool

from langflow.custom import Component
from langflow.field_typing import Tool
from langflow.io import Output, StrInput


class FileManipulation(Component):
    display_name = "File Manipulation"
    description = "Advanced system for precise file and directory operations with comprehensive content editing"
    icon = "File"
    name = "FileManipulation"

    inputs = [
        StrInput(
            name="workspace_folder",
            display_name="Workspace Folder",
            info="Base working directory for all file operations. All paths will be relative to this folder.",
            required=True,
        ),
    ]

    outputs = [
        Output(name="tools", display_name="Tools", method="build_toolkit"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_backups = {}  # For undo functionality

    def _resolve_path(self, relative_path: str) -> str:
        """Resolve a relative path to absolute path within workspace."""
        # Make sure the path is relative (doesn't start with / or drive letter)
        if os.path.isabs(relative_path):
            raise ValueError(f"Path must be relative to workspace: {relative_path}")

        # Join with workspace folder and normalize
        full_path = os.path.normpath(os.path.join(self.workspace_folder, relative_path))

        # Security check - make sure result is still within workspace
        if not full_path.startswith(os.path.abspath(self.workspace_folder)):
            raise ValueError(f"Path must be within workspace: {relative_path}")

        return full_path

    def _backup_file(self, file_path: str) -> None:
        """Create a backup of a file before editing."""
        resolved_path = self._resolve_path(file_path)
        if resolved_path not in self.file_backups:
            try:
                if os.path.exists(resolved_path):
                    with open(resolved_path, encoding="utf-8") as f:
                        self.file_backups[resolved_path] = f.read()
            except Exception:
                pass

    def _get_file_preview(self, file_path: str, line_number: int | None = None, context_lines: int = 5) -> str:
        """Get a preview of file content with line numbers."""
        resolved_path = self._resolve_path(file_path)

        try:
            if not os.path.exists(resolved_path):
                return f"File not found: {file_path}"

            with open(resolved_path, encoding="utf-8") as f:
                lines = f.readlines()

            # If specific line is provided, show context around it
            if line_number is not None:
                start = max(0, line_number - context_lines - 1)
                end = min(len(lines), line_number + context_lines)
                preview_lines = lines[start:end]
                result = ""
                for i, line in enumerate(preview_lines, start=start + 1):
                    prefix = ">>> " if i == line_number else "    "
                    result += f"{prefix}{i}: {line}"
                return result

            # Otherwise show first few lines
            result = ""
            for i, line in enumerate(lines[:10], start=1):
                result += f"{i}: {line}"
            if len(lines) > 10:
                result += f"\n... and {len(lines) - 10} more lines"
            return result

        except Exception as e:
            return f"Error getting file preview: {e!s}"

    def build_toolkit(self) -> Tool:
        """Build and return file system tools."""

        @tool
        def view_file(path: str, view_range: list[int] = None) -> str:
            """View file contents with line numbers.

            Use this to examine the contents of a file before making any changes.

            Args:
                path: Path to the file relative to workspace
                view_range: Optional [start_line, end_line] to view specific lines (use -1 for end of file)

            Returns:
                File contents with line numbers
            """
            try:
                resolved_path = self._resolve_path(path)

                if not os.path.exists(resolved_path):
                    return f"Error: File not found: {path}"

                with open(resolved_path, encoding="utf-8") as f:
                    lines = f.readlines()

                # Process view range if provided
                if view_range and len(view_range) == 2:
                    start = max(0, view_range[0] - 1)  # Convert to 0-indexed
                    end = len(lines) if view_range[1] == -1 else view_range[1]
                    lines = lines[start:end]

                    # Add line numbers
                    result = ""
                    for i, line in enumerate(lines):
                        line_num = view_range[0] + i
                        result += f"{line_num}: {line}"

                    return result

                # Otherwise show the whole file with line numbers
                result = ""
                for i, line in enumerate(lines, start=1):
                    result += f"{i}: {line}"

                return result

            except Exception as e:
                return f"Error viewing file: {e!s}"

        @tool
        def str_replace(path: str, old_str: str, new_str: str) -> str:
            """Replace text in a file. The old_str must match EXACTLY with text to replace.

            Args:
                path: Path to the file relative to workspace
                old_str: Exact text to be replaced (must match exactly with whitespace and indentation)
                new_str: New text to replace with

            Returns:
                Result of the operation with preview of changed content
            """
            try:
                resolved_path = self._resolve_path(path)

                if not os.path.exists(resolved_path):
                    return f"Error: File not found: {path}"

                # Create backup
                self._backup_file(path)

                with open(resolved_path, encoding="utf-8") as f:
                    content = f.read()

                # Count occurrences
                count = content.count(old_str)
                if count == 0:
                    return f"Error: Text not found in {path}"
                if count > 1:
                    return f"Error: Multiple matches ({count}) found in {path}. Please use more specific text to match."

                # Find the line number for preview
                lines = content.split("\n")
                line_count = 0
                char_count = 0
                match_line = 0

                for line_num, line in enumerate(lines):
                    char_count += len(line) + 1  # +1 for newline
                    match_pos = content.find(old_str)
                    if match_pos < char_count:
                        match_line = line_num + 1
                        break

                # Replace the text
                new_content = content.replace(old_str, new_str, 1)
                with open(resolved_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

                # Get preview
                file_preview = self._get_file_preview(path, match_line)

                return f"Successfully replaced text at exactly one location in {path}.\n\nPreview:\n{file_preview}"

            except Exception as e:
                return f"Error replacing text: {e!s}"

        @tool
        def insert_at_line(path: str, insert_line: int, new_str: str) -> str:
            """Insert text at a specific line number in a file.

            Args:
                path: Path to the file relative to workspace
                insert_line: Line number where to insert text (1-based)
                new_str: Text to insert

            Returns:
                Result of the operation with preview of changed content
            """
            try:
                resolved_path = self._resolve_path(path)

                if not os.path.exists(resolved_path):
                    return f"Error: File not found: {path}"

                # Create backup
                self._backup_file(path)

                with open(resolved_path, encoding="utf-8") as f:
                    lines = f.readlines()

                # Convert to 0-based indexing
                insert_index = max(0, min(len(lines), insert_line - 1))

                # If insert_line is beyond file length, add newlines
                if insert_index > len(lines):
                    return f"Error: Line number {insert_line} exceeds file length ({len(lines)})"

                # Insert the new text
                if not new_str.endswith("\n"):
                    new_str += "\n"
                lines.insert(insert_index, new_str)

                with open(resolved_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)

                # Get preview
                file_preview = self._get_file_preview(path, insert_line)

                return f"Successfully inserted text at line {insert_line} in {path}.\n\nPreview:\n{file_preview}"

            except Exception as e:
                return f"Error inserting text: {e!s}"

        @tool
        def undo_edit(path: str) -> str:
            """Undo the last edit made to a file.

            Args:
                path: Path to the file relative to workspace

            Returns:
                Result of the operation
            """
            try:
                resolved_path = self._resolve_path(path)

                if resolved_path not in self.file_backups:
                    return f"Error: No backup found for {path}"

                backup_content = self.file_backups[resolved_path]
                with open(resolved_path, "w", encoding="utf-8") as f:
                    f.write(backup_content)

                # Remove the backup
                del self.file_backups[resolved_path]

                # Get preview
                file_preview = self._get_file_preview(path)

                return f"Successfully restored {path} to previous state.\n\nPreview:\n{file_preview}"

            except Exception as e:
                return f"Error undoing edit: {e!s}"

        @tool
        def create_file(path: str, file_text: str) -> str:
            """Create a new file with content.

            Args:
                path: Path to the file relative to workspace
                file_text: Text content to write to the file

            Returns:
                Result of the operation with preview
            """
            try:
                resolved_path = self._resolve_path(path)

                # Create directories if they don't exist
                os.makedirs(os.path.dirname(os.path.abspath(resolved_path)), exist_ok=True)

                # Check if file exists
                if os.path.exists(resolved_path):
                    # Backup if file exists
                    self._backup_file(path)
                    action = "Updated"
                else:
                    action = "Created"

                with open(resolved_path, "w", encoding="utf-8") as f:
                    f.write(file_text)

                # Get preview
                file_preview = self._get_file_preview(path)

                return f"Successfully {action} file: {path}\n\nPreview:\n{file_preview}"

            except Exception as e:
                return f"Error creating file: {e!s}"

        @tool
        def create_directory(directory_path: str) -> str:
            """Create a new directory or ensure it exists.

            Args:
                directory_path: Path to the directory relative to workspace

            Returns:
                Result of the operation
            """
            try:
                resolved_path = self._resolve_path(directory_path)

                # Check if directory already exists
                if os.path.exists(resolved_path):
                    if os.path.isdir(resolved_path):
                        return f"Directory already exists: {directory_path}"
                    return f"Error: Path exists but is not a directory: {directory_path}"

                # Create directory
                os.makedirs(resolved_path, exist_ok=True)
                return f"Successfully created directory: {directory_path}"

            except Exception as e:
                return f"Error creating directory: {e!s}"

        @tool
        def list_directory(directory_path: str = ".") -> str:
            """Get detailed listing of files and directories.

            Args:
                directory_path: Path to the directory relative to workspace (default: workspace root)

            Returns:
                Listing of files and directories with details
            """
            try:
                resolved_path = self._resolve_path(directory_path)

                if not os.path.exists(resolved_path):
                    return f"Error: Directory not found: {directory_path}"

                if not os.path.isdir(resolved_path):
                    return f"Error: Path is not a directory: {directory_path}"

                # List directory contents
                entries = os.listdir(resolved_path)
                result = f"Contents of {directory_path}:\n"

                # Add directories first, then files
                dirs = []
                files = []

                for entry in entries:
                    entry_path = os.path.join(resolved_path, entry)
                    if os.path.isdir(entry_path):
                        dirs.append((entry, "directory"))
                    else:
                        # Get file size
                        size = os.path.getsize(entry_path)
                        size_str = f"{size} bytes"
                        if size > 1024:
                            size_str = f"{size / 1024:.1f} KB"
                        if size > 1024 * 1024:
                            size_str = f"{size / (1024 * 1024):.1f} MB"

                        files.append((entry, "file", size_str))

                # Format and add to result
                for name, type_ in sorted(dirs):
                    result += f"📁 {name}/ ({type_})\n"

                for name, type_, size in sorted(files):
                    result += f"📄 {name} ({type_}, {size})\n"

                return result

            except Exception as e:
                return f"Error listing directory: {e!s}"

        @tool
        def move_file(source_path: str, destination_path: str) -> str:
            """Move or rename files and directories.

            Args:
                source_path: Path to the source file/directory relative to workspace
                destination_path: Path to the destination relative to workspace

            Returns:
                Result of the operation
            """
            try:
                resolved_source = self._resolve_path(source_path)
                resolved_dest = self._resolve_path(destination_path)

                if not os.path.exists(resolved_source):
                    return f"Error: Source not found: {source_path}"

                # Create destination directory if it doesn't exist
                dest_dir = os.path.dirname(resolved_dest)
                os.makedirs(dest_dir, exist_ok=True)

                # Move/rename the file or directory
                shutil.move(resolved_source, resolved_dest)

                source_type = "directory" if os.path.isdir(resolved_dest) else "file"
                return f"Successfully moved {source_type} from {source_path} to {destination_path}"

            except Exception as e:
                return f"Error moving file: {e!s}"

        @tool
        def search_files(search_pattern: str, directory_path: str = ".") -> str:
            """Find files by name using case-insensitive substring matching.

            Args:
                search_pattern: Pattern to search for in filenames
                directory_path: Path to the directory to search in (default: workspace root)

            Returns:
                List of matching files
            """
            try:
                resolved_path = self._resolve_path(directory_path)

                if not os.path.exists(resolved_path):
                    return f"Error: Directory not found: {directory_path}"

                if not os.path.isdir(resolved_path):
                    return f"Error: Path is not a directory: {directory_path}"

                # Search for matching files
                matches = []
                pattern = f"*{search_pattern}*"

                for root, dirs, files in os.walk(resolved_path):
                    for name in files:
                        if fnmatch.fnmatch(name.lower(), pattern.lower()):
                            rel_path = os.path.relpath(os.path.join(root, name), self.workspace_folder)
                            matches.append(rel_path)

                if not matches:
                    return f"No files matching '{search_pattern}' found in {directory_path}"

                result = f"Found {len(matches)} file(s) matching '{search_pattern}':\n"
                for match in sorted(matches):
                    result += f"- {match}\n"

                return result

            except Exception as e:
                return f"Error searching files: {e!s}"

        @tool
        def search_code(search_pattern: str, file_pattern: str = "*", directory_path: str = ".") -> str:
            """Search for text/code patterns within file contents using ripgrep or grep.

            Args:
                search_pattern: Text pattern to search for in file contents
                file_pattern: Filter for file types (e.g., "*.py" for Python files)
                directory_path: Path to the directory to search in (default: workspace root)

            Returns:
                Search results with file locations and line numbers
            """
            try:
                resolved_path = self._resolve_path(directory_path)

                if not os.path.exists(resolved_path):
                    return f"Error: Directory not found: {directory_path}"

                # Decide whether to use ripgrep or fallback to Python search
                use_ripgrep = False
                try:
                    # Check if ripgrep is available
                    subprocess.run(["rg", "--version"], capture_output=True, check=True)
                    use_ripgrep = True
                except (subprocess.SubprocessError, FileNotFoundError):
                    # Ripgrep not available, will use Python fallback
                    pass

                if use_ripgrep:
                    # Use ripgrep for searching
                    cmd = ["rg", "--line-number", "--no-heading", "--glob", file_pattern, search_pattern, resolved_path]
                    process = subprocess.run(cmd, capture_output=True, text=True, check=False)

                    if process.returncode > 1:  # rg returns 1 if no matches, 0 if matches
                        return f"Error executing ripgrep: {process.stderr}"

                    if not process.stdout.strip():
                        return f"No matches found for '{search_pattern}' in {directory_path}"

                    # Format the results for readability
                    lines = process.stdout.strip().split("\n")
                    result = f"Found matches for '{search_pattern}':\n"

                    for line in lines:
                        if line.strip():
                            parts = line.split(":", 2)
                            if len(parts) >= 3:
                                file_path = os.path.relpath(parts[0], self.workspace_folder)
                                line_num = parts[1]
                                content = parts[2]
                                result += f"{file_path}:{line_num}: {content}\n"

                    return result

                # Fallback: Python-based search
                matches = []

                for root, dirs, files in os.walk(resolved_path):
                    for name in files:
                        if fnmatch.fnmatch(name, file_pattern):
                            file_path = os.path.join(root, name)
                            try:
                                with open(file_path, encoding="utf-8") as f:
                                    for i, line in enumerate(f, 1):
                                        if search_pattern in line:
                                            rel_path = os.path.relpath(file_path, self.workspace_folder)
                                            matches.append((rel_path, i, line.strip()))
                            except:
                                # Skip files that can't be read as text
                                pass

                if not matches:
                    return f"No matches found for '{search_pattern}' in {directory_path}"

                result = f"Found {len(matches)} match(es) for '{search_pattern}':\n"
                for file_path, line_num, content in matches:
                    result += f"{file_path}:{line_num}: {content}\n"

                return result

            except Exception as e:
                return f"Error searching code: {e!s}"

        # Return the list of tools
        return [
            view_file,
            str_replace,
            insert_at_line,
            create_file,
            undo_edit,
            create_directory,
            list_directory,
            move_file,
            search_files,
            search_code,
        ]
