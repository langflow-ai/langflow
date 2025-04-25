import asyncio
import fnmatch

import anyio
from langchain_core.tools import tool
from loguru import logger

from langflow.custom import Component
from langflow.field_typing import Tool
from langflow.io import Output, StrInput

# Constants
PREVIEW_LINE_LIMIT = 10
VIEW_RANGE_SIZE = 2
BYTES_IN_KB = 1024
BYTES_IN_MB = BYTES_IN_KB * 1024
MIN_PARTS_LENGTH = 3


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

    async def _resolve_path(self, relative_path: str) -> anyio.Path:
        """Resolve a relative path to an absolute path within the workspace.

        Args:
            relative_path (str): The relative path to resolve.

        Returns:
            anyio.Path: The resolved absolute path.

        Raises:
            ValueError: If the path is absolute or attempts to escape the workspace.
        """
        try:
            workspace_path = anyio.Path(self.workspace_folder)
            path = anyio.Path(relative_path)

            if path.is_absolute():
                msg = f"Absolute paths are not allowed: {relative_path}"
                raise ValueError(msg)

            resolved_path = await (workspace_path / path).resolve()
            workspace_resolved = await workspace_path.resolve()

            try:
                resolved_path.relative_to(workspace_resolved)
            except ValueError as e:
                msg = f"Path attempts to escape workspace: {relative_path}"
                raise ValueError(msg) from e

        except Exception as e:
            msg = f"Invalid path: {relative_path}. Error: {e!s}"
            raise ValueError(msg) from e
        return resolved_path

    async def _backup_file(self, file_path: str) -> None:
        """Create a backup of a file before editing (async)."""
        resolved_path = await self._resolve_path(file_path)
        if resolved_path not in self.file_backups:
            try:
                file_path_obj = anyio.Path(resolved_path)
                if await file_path_obj.exists():
                    async with await file_path_obj.open(encoding="utf-8") as f:
                        self.file_backups[resolved_path] = await f.read()
            except Exception as e:  # noqa: BLE001
                msg = f"Error creating backup for {file_path}: {e!s}"
                logger.error(msg)

    async def _get_file_preview(self, file_path: str, line_number: int | None = None, context_lines: int = 5) -> str:
        """Get a preview of file content with line numbers (async).

        Args:
            file_path: Path to the file relative to workspace.
            line_number: Optional line number to center the preview around.
            context_lines: Number of context lines before and after the line_number.

        Returns:
            A string preview of the file content.
        """
        resolved_path = await self._resolve_path(file_path)

        try:
            file_path_obj = anyio.Path(resolved_path)
            if not await file_path_obj.exists():
                return f"File not found: {file_path}"

            async with await anyio.open_file(resolved_path, mode="r", encoding="utf-8") as f:
                lines = await f.readlines()

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
            for i, line in enumerate(lines[:PREVIEW_LINE_LIMIT], start=1):
                result += f"{i}: {line}"
            if len(lines) > PREVIEW_LINE_LIMIT:
                result += f"\n... and {len(lines) - PREVIEW_LINE_LIMIT} more lines"
        except FileNotFoundError as e:
            logger.error(f"File not found error in _get_file_preview: {e}")
            return f"File not found: {file_path}"
        except PermissionError as e:
            logger.error(f"Permission error in _get_file_preview: {e}")
            return f"Permission denied: {file_path}"
        except OSError as e:
            logger.error(f"IO error in _get_file_preview: {e}")
            return f"Error reading file: {e}"
        except ValueError as e:
            logger.error(f"Value error in _get_file_preview: {e}")
            return f"Invalid value: {e}"
        except RuntimeError as e:
            logger.error(f"System error in _get_file_preview: {e}")
            return f"System error: {e}"
        return result

    def build_toolkit(self) -> Tool:
        """Build and return file system tools."""

        @tool
        async def view_file(path: str, view_range: list[int] | None = None) -> str:
            """View file contents with line numbers.

            Use this to examine the contents of a file before making any changes.

            Args:
                path: Path to the file relative to workspace
                view_range: Optional [start_line, end_line] to view specific lines (use -1 for end of file)

            Returns:
                File contents with line numbers
            """
            try:
                resolved_path = await self._resolve_path(path)
                file_path = anyio.Path(resolved_path)
                if not await file_path.exists():
                    return f"Error: File not found: {path}"

                async with await anyio.open_file(resolved_path, encoding="utf-8") as f:
                    lines = await f.readlines()

                # If view_range is provided, show only those lines
                if view_range and len(view_range) == VIEW_RANGE_SIZE:
                    start = max(0, view_range[0] - 1)
                    end = len(lines) if view_range[1] == -1 else min(len(lines), view_range[1])
                    if start >= len(lines):
                        return f"Error: Start line {view_range[0]} exceeds file length ({len(lines)})"
                    result = ""
                    for i, line in enumerate(lines[start:end], start=start + 1):
                        result += f"{i}: {line}"
                    return result

                # Otherwise show the whole file with line numbers
                result = ""
                for i, line in enumerate(lines, start=1):
                    result += f"{i}: {line}"
            except (FileNotFoundError, PermissionError) as e:
                logger.error(f"File access error in view_file: {e}")
                return f"Error: {e!s}"
            except ValueError as e:
                logger.error(f"Value error in view_file: {e}")
                return f"Error: {e!s}"
            except OSError as e:
                logger.error(f"IO error in view_file: {e}")
                return f"Error: {e!s}"
            return result

        # --- Replace a string in a file (only if exactly one match) ---
        @tool
        async def str_replace(path: str, old_str: str, new_str: str) -> str:
            """Replace text in a file. The old_str must match EXACTLY with text to replace.

            Args:
                path: Path to the file relative to workspace
                old_str: Exact text to be replaced (must match exactly with whitespace and indentation)
                new_str: New text to replace with

            Returns:
                Result of the operation with preview of changed content
            """
            try:
                resolved_path = await self._resolve_path(path)
                file_path = anyio.Path(resolved_path)
                if not await file_path.exists():
                    return f"Error: File not found: {path}"

                # Create backup
                await self._backup_file(path)

                async with await anyio.open_file(resolved_path, encoding="utf-8") as f:
                    content = await f.read()

                # Count occurrences
                count = content.count(old_str)
                if count == 0:
                    return f"Error: Text not found in {path}"
                if count > 1:
                    return f"Error: Multiple matches ({count}) found in {path}. Please use more specific text to match."

                match_pos = content.find(old_str)
                # Find the line number of the match
                upto = content[:match_pos]
                match_line = upto.count("\n") + 1

                # Replace the text
                new_content = content.replace(old_str, new_str, 1)
                async with await anyio.open_file(resolved_path, "w", encoding="utf-8") as f:
                    await f.write(new_content)

                # Get preview
                file_preview = await self._get_file_preview(path, match_line)

            except (FileNotFoundError, PermissionError) as e:
                logger.error(f"File access error in str_replace: {e}")
                return f"Error: {e!s}"
            except ValueError as e:
                logger.error(f"Value error in str_replace: {e}")
                return f"Error: {e!s}"
            except OSError as e:
                logger.error(f"IO error in str_replace: {e}")
                return f"Error: {e!s}"
            return f"Successfully replaced text at exactly one location in {path}.\n\nPreview:\n{file_preview}"

        # --- Insert text at a specific line ---
        @tool
        async def insert_at_line(path: str, insert_line: int, new_str: str) -> str:
            """Insert text at a specific line number in a file.

            Args:
                path: Path to the file relative to workspace
                insert_line: Line number where to insert text (1-based)
                new_str: Text to insert

            Returns:
                Result of the operation with preview of changed content
            """
            try:
                resolved_path = await self._resolve_path(path)
                file_path = anyio.Path(resolved_path)
                if not await file_path.exists():
                    return f"Error: File not found: {path}"

                # Create backup
                await self._backup_file(path)

                async with await anyio.open_file(resolved_path, encoding="utf-8") as f:
                    lines = await f.readlines()

                insert_index = max(0, min(len(lines), insert_line - 1))

                # If insert_line is beyond file length, add newlines
                if insert_index > len(lines):
                    return f"Error: Line number {insert_line} exceeds file length ({len(lines)})"

                # Insert the new text
                if not new_str.endswith("\n"):
                    new_str += "\n"
                lines.insert(insert_index, new_str)

                async with await anyio.open_file(resolved_path, "w", encoding="utf-8") as f:
                    await f.writelines(lines)

                file_preview = await self._get_file_preview(path, insert_line)

            except (FileNotFoundError, PermissionError) as e:
                logger.error(f"File access error in insert_at_line: {e}")
                return f"Error: {e!s}"
            except ValueError as e:
                logger.error(f"Value error in insert_at_line: {e}")
                return f"Error: {e!s}"
            except OSError as e:
                logger.error(f"IO error in insert_at_line: {e}")
                return f"Error: {e!s}"
            return f"Successfully inserted text at line {insert_line} in {path}.\n\nPreview:\n{file_preview}"

        @tool
        async def undo_edit(path: str) -> str:
            """Undo the last edit made to a file.

            Args:
                path: Path to the file relative to workspace

            Returns:
                Result of the operation
            """
            try:
                resolved_path = await self._resolve_path(path)
                anyio.Path(resolved_path)

                if resolved_path not in self.file_backups:
                    return f"Error: No backup found for {path}"

                backup_content = self.file_backups[resolved_path]
                async with await anyio.open_file(resolved_path, "w", encoding="utf-8") as f:
                    await f.write(backup_content)

                # Remove the backup
                del self.file_backups[resolved_path]

                # Get preview
                file_preview = await self._get_file_preview(path)

            except (FileNotFoundError, PermissionError) as e:
                logger.error(f"File access error in undo_edit: {e}")
                return f"Error: {e!s}"
            except ValueError as e:
                logger.error(f"Value error in undo_edit: {e}")
                return f"Error: {e!s}"
            except OSError as e:
                logger.error(f"IO error in undo_edit: {e}")
                return f"Error: {e!s}"
            except KeyError as e:
                logger.error(f"Backup not found in undo_edit: {e}")
                return f"Error: No backup found for {path}"
            return f"Successfully restored {path} to previous state.\n\nPreview:\n{file_preview}"

        # --- Create a new file (or overwrite) ---
        @tool
        async def create_file(path: str, file_text: str) -> str:
            """Create a new file with content.

            Args:
                path: Path to the file relative to workspace
                file_text: Text content to write to the file

            Returns:
                Result of the operation with preview
            """
            try:
                resolved_path = await self._resolve_path(path)
                file_path = anyio.Path(resolved_path)
                dir_path = file_path.parent

                # Create directories if they don't exist
                await dir_path.mkdir(parents=True, exist_ok=True)

                # Check if file exists
                if await file_path.exists():
                    # Backup if file exists
                    await self._backup_file(path)
                    action = "Updated"
                else:
                    action = "Created"

                async with await anyio.open_file(resolved_path, "w", encoding="utf-8") as f:
                    await f.write(file_text)

                # Get preview
                file_preview = await self._get_file_preview(path)

            except (FileNotFoundError, PermissionError) as e:
                logger.error(f"File access error in create_file: {e}")
                return f"Error: {e!s}"
            except ValueError as e:
                logger.error(f"Value error in create_file: {e}")
                return f"Error: {e!s}"
            except OSError as e:
                logger.error(f"IO error in create_file: {e}")
                return f"Error: {e!s}"
            return f"Successfully {action} file: {path}\n\nPreview:\n{file_preview}"

        # --- Create a new directory ---
        @tool
        async def create_directory(directory_path: str) -> str:
            """Create a new directory or ensure it exists.

            Args:
                directory_path: Path to the directory relative to workspace

            Returns:
                Result of the operation
            """
            try:
                resolved_path = await self._resolve_path(directory_path)
                dir_path = anyio.Path(resolved_path)

                # Check if directory already exists
                if await dir_path.exists():
                    if await dir_path.is_dir():
                        return f"Directory already exists: {directory_path}"
                    return f"Error: Path exists but is not a directory: {directory_path}"

                # Create directory
                await dir_path.mkdir(parents=True, exist_ok=True)
            except (FileNotFoundError, PermissionError) as e:
                logger.error(f"File access error in create_directory: {e}")
                return f"Error: {e!s}"
            except ValueError as e:
                logger.error(f"Value error in create_directory: {e}")
                return f"Error: {e!s}"
            except OSError as e:
                logger.error(f"IO error in create_directory: {e}")
                return f"Error: {e!s}"
            return f"Successfully created directory: {directory_path}"

        # --- List directory contents ---
        @tool
        async def list_directory(directory_path: str = ".") -> str:
            """Get detailed listing of files and directories.

            Args:
                directory_path: Path to the directory relative to workspace (default: workspace root)

            Returns:
                Listing of files and directories with details
            """
            try:
                resolved_path = await self._resolve_path(directory_path)
                dir_path = anyio.Path(resolved_path)

                if not await dir_path.exists():
                    return f"Error: Directory not found: {directory_path}"

                if not await dir_path.is_dir():
                    return f"Error: Path is not a directory: {directory_path}"

                # list directory contents
                entries = [entry async for entry in dir_path.iterdir()]

                result = f"Contents of {directory_path}:\n"

                # Add directories first, then files
                dirs = []
                files = []

                for entry in entries:
                    if await entry.is_dir():
                        dirs.append(entry.name)
                    else:
                        stat = await entry.stat()
                        size = stat.st_size
                        if size > BYTES_IN_MB:
                            size_str = f"{size / BYTES_IN_MB:.1f} MB"
                        elif size > BYTES_IN_KB:
                            size_str = f"{size / BYTES_IN_KB:.1f} KB"
                        else:
                            size_str = f"{size} bytes"
                        files.append((entry.name, size_str))

                for name in sorted(dirs):
                    result += f"📁 {name}/ (directory)\n"
                for name, size in sorted(files):
                    result += f"📄 {name} (file, {size})\n"

            except (FileNotFoundError, PermissionError) as e:
                logger.error(f"File access error in list_directory: {e}")
                return f"Error: {e!s}"
            except ValueError as e:
                logger.error(f"Value error in list_directory: {e}")
                return f"Error: {e!s}"
            except OSError as e:
                logger.error(f"IO error in list_directory: {e}")
                return f"Error: {e!s}"
            return result

        # --- Move or rename files/directories ---
        @tool
        async def move_file(source_path: str, destination_path: str) -> str:
            """Move or rename files and directories.

            Args:
                source_path: Path to the source file/directory relative to workspace
                destination_path: Path to the destination relative to workspace

            Returns:
                Result of the operation
            """
            try:
                resolved_source = await self._resolve_path(source_path)
                resolved_dest = await self._resolve_path(destination_path)

                source_path_obj = anyio.Path(resolved_source)
                dest_path_obj = anyio.Path(resolved_dest)

                if not await source_path_obj.exists():
                    return f"Error: Source not found: {source_path}"

                await dest_path_obj.parent.mkdir(parents=True, exist_ok=True)
                await source_path_obj.rename(dest_path_obj)

                is_dir = await dest_path_obj.is_dir()
                source_type = "directory" if is_dir else "file"
            except (FileNotFoundError, PermissionError) as e:
                logger.error(f"File access error in move_file: {e}")
                return f"Error: {e!s}"
            except ValueError as e:
                logger.error(f"Value error in move_file: {e}")
                return f"Error: {e!s}"
            except OSError as e:
                logger.error(f"IO error in move_file: {e}")
                return f"Error: {e!s}"
            return f"Successfully moved {source_type} from {source_path} to {destination_path}"

        # --- Search for files by name (case-insensitive substring) ---
        @tool
        async def search_files(search_pattern: str, directory_path: str = ".") -> str:
            """Find files by name using case-insensitive substring matching.

            Args:
                search_pattern: Pattern to search for in filenames
                directory_path: Path to the directory to search in (default: workspace root)

            Returns:
                list of matching files
            """
            try:
                resolved_path = await self._resolve_path(directory_path)
                dir_path = anyio.Path(resolved_path)
                if not await dir_path.exists():
                    return f"Error: Directory not found: {directory_path}"
                if not await dir_path.is_dir():
                    return f"Error: Path is not a directory: {directory_path}"

                pattern = f"*{search_pattern}*"

                async def walk_dir(current_dir, relative_to):
                    result = []
                    async for entry in current_dir.iterdir():
                        if await entry.is_dir():
                            result.extend(await walk_dir(entry, relative_to))
                        elif fnmatch.fnmatch(entry.name.lower(), pattern.lower()):
                            rel_path = str(entry.relative_to(relative_to))
                            result.append(rel_path)
                    return result

                workspace_path = anyio.Path(self.workspace_folder)
                matches = await walk_dir(dir_path, workspace_path)

                if not matches:
                    return f"No files matching '{search_pattern}' found in {directory_path}"

                result = f"Found {len(matches)} file(s) matching '{search_pattern}':\n"
                for match in sorted(matches):
                    result += f"- {match}\n"
            except (FileNotFoundError, PermissionError) as e:
                logger.error(f"File access error in search_files: {e}")
                return f"Error: {e!s}"
            except ValueError as e:
                logger.error(f"Value error in search_files: {e}")
                return f"Error: {e!s}"
            except OSError as e:
                logger.error(f"IO error in search_files: {e}")
                return f"Error: {e!s}"
            return result

        # --- Search for code/text patterns in files ---
        @tool
        async def search_code(search_pattern: str, file_pattern: str = "*", directory_path: str = ".") -> str:
            """Search for text/code patterns within file contents using ripgrep or grep.

            Args:
                search_pattern: Text pattern to search for in file contents
                file_pattern: Filter for file types (e.g., "*.py" for Python files)
                directory_path: Path to the directory to search in (default: workspace root)

            Returns:
                Search results with file locations and line numbers
            """
            try:
                resolved_path = await self._resolve_path(directory_path)
                dir_path = anyio.Path(resolved_path)

                if not await dir_path.exists():
                    return f"Error: Directory not found: {directory_path}"

                # Try to use ripgrep if available
                use_ripgrep = False
                try:
                    # Check if ripgrep is available
                    process = await asyncio.create_subprocess_exec(
                        "rg", "--version", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    await process.communicate()
                    if process.returncode == 0:
                        use_ripgrep = True
                except (OSError, FileNotFoundError):
                    # Ripgrep not available, will use Python fallback
                    pass

                if use_ripgrep:
                    # Use ripgrep for searching
                    cmd = [
                        "rg",
                        "--line-number",
                        "--no-heading",
                        "--glob",
                        file_pattern,
                        search_pattern,
                        str(resolved_path),
                    ]
                    process = await asyncio.create_subprocess_exec(
                        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()
                    if process.returncode is not None and process.returncode > 1:
                        return f"Error executing ripgrep: {stderr.decode('utf-8')}"
                    if not stdout.strip():
                        return f"No matches found for '{search_pattern}' in {directory_path}"

                    lines = stdout.decode("utf-8").strip().split("\n")
                    result = f"Found matches for '{search_pattern}':\n"
                    for line in lines:
                        if line.strip():
                            parts = line.split(":", 2)
                            if len(parts) >= MIN_PARTS_LENGTH:
                                file_path = str(anyio.Path(parts[0]).relative_to(self.workspace_folder))
                                line_num = parts[1]
                                content = parts[2]
                                result += f"{file_path}:{line_num}: {content}\n"
                    return result

                # Fallback: Python-based search
                matches = []

                async def walk_and_search(current_dir, pattern):
                    result = []
                    async for entry in current_dir.iterdir():
                        if await entry.is_dir():
                            result.extend(await walk_and_search(entry, pattern))
                        elif fnmatch.fnmatch(entry.name, pattern):
                            try:
                                # Try to read first few bytes to check if it's a text file
                                async with await anyio.open_file(str(entry), "rb") as f:
                                    content = await f.read(1024)
                                    if b"\x00" in content:  # Skip binary files
                                        continue
                                    try:
                                        content.decode("utf-8")
                                    except UnicodeDecodeError:
                                        continue

                                async with await anyio.open_file(str(entry), encoding="utf-8") as f:
                                    lines = await f.readlines()
                                for i, line in enumerate(lines, 1):
                                    if search_pattern in line:
                                        rel_path = str(entry.relative_to(self.workspace_folder))
                                        result.append((rel_path, i, line.strip()))
                            except (OSError, FileNotFoundError, PermissionError) as e:
                                logger.warning(f"Error reading file {entry}: {e}")
                                continue
                    return result

                matches = await walk_and_search(dir_path, file_pattern)
                if not matches:
                    return f"No matches found for '{search_pattern}' in {directory_path}"

                result = f"Found {len(matches)} match(es) for '{search_pattern}':\n"
                for file_path, line_num, content in matches:
                    result += f"{file_path}:{line_num}: {content}\n"
            except (FileNotFoundError, PermissionError) as e:
                logger.error(f"File access error in search_code: {e}")
                return f"Error: {e!s}"
            except ValueError as e:
                logger.error(f"Value error in search_code: {e}")
                return f"Error: {e!s}"
            except OSError as e:
                logger.error(f"IO error in search_code: {e}")
                return f"Error: {e!s}"
            return result

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
