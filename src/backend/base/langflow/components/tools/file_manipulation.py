import ast
import difflib
import fnmatch
import os
import platform
import re
import shutil
from datetime import datetime
from enum import Enum
from typing import Any

from langflow.custom import Component
from langflow.field_typing import Tool
from langflow.io import Output, StrInput


class BackupManager:
    """Simple backup system for file operations."""

    def __init__(self, workspace_folder: str):
        """Initializes the BackupManager with a workspace folder and prepares the backup system.

        Creates a `.backups` directory within the workspace if it does not exist, and sets up internal registries for tracking file backups and undo/redo positions.
        """
        self.workspace_folder = workspace_folder
        self.backup_folder = os.path.join(workspace_folder, ".backups")
        self.backup_registry = {}  # file_path -> [backup_ids]
        self.current_positions = {}  # file_path -> current_position_index

        if not os.path.exists(self.backup_folder):
            os.makedirs(self.backup_folder)

    def backup_file(self, file_path: str) -> str | None:
        """Creates a timestamped backup of the specified file and updates the backup registry.

        If the file does not exist or the backup fails, returns None. On success, returns the backup ID.
        """
        if not os.path.exists(file_path):
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = os.path.basename(file_path)
        backup_id = f"{file_name}_{timestamp}"
        backup_path = os.path.join(self.backup_folder, backup_id)

        try:
            shutil.copy2(file_path, backup_path)

            if file_path not in self.backup_registry:
                self.backup_registry[file_path] = []
                self.current_positions[file_path] = -1

            # If we're not at the end of history, truncate it
            position = self.current_positions[file_path]
            if position != -1:
                self.backup_registry[file_path] = self.backup_registry[file_path][: position + 1]
                self.current_positions[file_path] = -1

            self.backup_registry[file_path].append(backup_id)
            return backup_id

        except Exception:
            return None

    def get_backups(self, file_path: str) -> list[str]:
        """Returns a list of backup IDs for the specified file.

        Args:
            file_path: The path to the file whose backups are requested.

        Returns:
            A list of backup IDs associated with the file, or an empty list if none exist.
        """
        return self.backup_registry.get(file_path, [])

    def get_backup_info(self, file_path: str) -> dict[str, Any]:
        """Returns backup history information for a given file.

        The returned dictionary includes the total number of backups, the current backup position, and booleans indicating whether undo or redo operations are possible.
        """
        if file_path not in self.backup_registry:
            return {"count": 0, "position": -1, "can_undo": False, "can_redo": False}

        backups = self.backup_registry[file_path]
        position = self.current_positions[file_path]

        return {
            "count": len(backups),
            "position": position,
            "can_undo": position < len(backups) - 1 if position != -1 else len(backups) > 0,
            "can_redo": position > 0 if position != -1 else False,
        }

    def restore(self, file_path: str, direction: str = "undo") -> tuple[bool, str | None, str]:
        """Restores a file to a previous ("undo") or newer ("redo") backup version.

        Args:
            file_path: Path to the file to restore.
            direction: "undo" to revert to an earlier backup, "redo" to move to a newer backup.

        Returns:
            A tuple containing a boolean indicating success, the backup ID or "current" if restored to the latest version, and a message describing the result.
        """
        if file_path not in self.backup_registry:
            return False, None, "No backup history for this file"

        backups = self.backup_registry[file_path]
        if not backups:
            return False, None, "No backups available"

        position = self.current_positions[file_path]

        if direction == "undo":
            if position == -1:
                new_position = len(backups) - 1
            elif position > 0:
                new_position = position - 1
            else:
                return False, None, "No earlier version available"

        elif direction == "redo":
            if position == -1:
                return False, None, "No redo operations available. You can only redo after an undo operation."
            if position < len(backups) - 1:
                new_position = position + 1
            else:
                # Already at most recent backup, restore to current version
                self.current_positions[file_path] = -1
                return True, "current", "Restored to current version"
        else:
            return False, None, f"Invalid direction: {direction}"

        backup_id = backups[new_position]
        backup_path = os.path.join(self.backup_folder, backup_id)

        if not os.path.exists(backup_path):
            return False, None, f"Backup file not found: {backup_id}"

        try:
            shutil.copy2(backup_path, file_path)
            self.current_positions[file_path] = new_position
            return True, backup_id, f"Successfully restored {direction} to version {new_position + 1} of {len(backups)}"
        except Exception as e:
            return False, None, f"Failed to restore: {e!s}"


class PathHandler:
    """Handle path operations safely."""

    def __init__(self, workspace_folder: str):
        """Initializes the PathHandler with the specified workspace folder.

        Args:
            workspace_folder: The root directory for all path operations, used to enforce workspace boundaries.
        """
        self.workspace_folder = workspace_folder
        self.platform = platform.system()

    def resolve_path(self, relative_path: str, must_exist: bool = True) -> str:
        """Resolves a relative path to an absolute path within the workspace, enforcing security constraints.

        Args:
            relative_path: The path relative to the workspace folder.
            must_exist: If True, raises an error if the resolved path does not exist.

        Returns:
            The absolute, normalized path within the workspace.

        Raises:
            ValueError: If the path is absolute or outside the workspace.
            FileNotFoundError: If must_exist is True and the path does not exist.
        """
        # Check if absolute
        if os.path.isabs(relative_path):
            msg = f"Path must be relative to workspace: {relative_path}"
            raise ValueError(msg)

        # Normalize path separators for the current platform
        if self.platform == "Windows":
            relative_path = relative_path.replace("/", "\\")
        else:
            relative_path = relative_path.replace("\\", "/")

        # Join with workspace and normalize
        full_path = os.path.normpath(os.path.join(self.workspace_folder, relative_path))

        # Security check: ensure path is within workspace
        if not os.path.abspath(full_path).startswith(os.path.abspath(self.workspace_folder)):
            msg = f"Path must be within workspace: {relative_path}"
            raise ValueError(msg)

        # Check existence if required
        if must_exist and not os.path.exists(full_path):
            msg = f"Path does not exist: {relative_path}"
            raise FileNotFoundError(msg)

        return full_path

    def is_within_workspace(self, path: str) -> bool:
        """Determines whether the given path is located inside the workspace directory.

        Args:
            path: The file or directory path to check.

        Returns:
            True if the path is within the workspace; otherwise, False.
        """
        abs_path = os.path.abspath(path)
        abs_workspace = os.path.abspath(self.workspace_folder)
        return abs_path.startswith(abs_workspace)

    def ensure_directory_exists(self, path: str) -> None:
        """Ensures that the parent directory of the specified path exists, creating it if necessary."""
        directory = os.path.dirname(path)
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)


class FileEditOperation(Enum):
    """Types of file edit operations."""

    REPLACE = "replace"
    INSERT = "insert"
    REMOVE = "remove"
    MOVE = "move"


class FileManipulation(Component):
    display_name = "File Manipulation"
    description = "Efficient file and directory operations with content editing capabilities."
    icon = "file-text"
    name = "FileManipulation"

    inputs = [
        StrInput(
            name="workspace_folder",
            display_name="Workspace Folder",
            info="Base directory for all file operations. All paths will be relative to this folder.",
            required=True,
        ),
    ]

    outputs = [
        Output(name="tools", display_name="Tools", method="build_toolkit"),
    ]

    def __init__(self, *args, **kwargs):
        """Initializes the FileManipulation component and sets up placeholders for backup and path handlers."""
        super().__init__(*args, **kwargs)
        self.backup_manager = None
        self.path_handler = None

    def _get_file_preview(self, file_path: str, line_number: int | None = None, context_lines: int = 5) -> str:
        """Returns a formatted preview of a file's contents with line numbers.

        If a line number is specified, shows lines around that line with context and highlights the target line. If no line number is given, displays the first few lines of the file. Handles empty or missing files and reports errors as messages.
        """
        try:
            resolved_path = self.path_handler.resolve_path(file_path)

            if not os.path.exists(resolved_path):
                return f"File not found: {file_path}"

            # Handle empty files
            if os.path.getsize(resolved_path) == 0:
                return f"File is empty: {file_path}"

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
            preview_length = min(10, len(lines))
            for i, line in enumerate(lines[:preview_length], start=1):
                result += f"{i}: {line}"
            if len(lines) > preview_length:
                result += f"\n... and {len(lines) - preview_length} more lines"
            return result

        except Exception as e:
            return f"Error getting file preview: {e!s}"

    def _edit_file(
        self,
        path: str,
        operation: FileEditOperation,
        search: str | None = None,
        replacement: str | None = None,
        line_number: int | None = None,
        end_line: int | None = None,
        target_line: int | None = None,
        use_regex: bool = False,
        replace_all: bool = False,
        context_before: str | None = None,
        context_after: str | None = None,
        occurrence: int = 1,
        dry_run: bool = False,
    ) -> str:
        """Performs a unified file editing operation such as replace, insert, remove, or move.

        Depending on the specified operation, this method modifies the file at the given path by replacing text, inserting new content at a specific line, removing a range of lines, or moving a block of lines to a new location. It supports dry-run mode, regex-based replacements, occurrence selection, and context constraints. The method ensures the file exists or creates it for insert operations, backs up the file before modification (unless dry run), and returns a message describing the action along with a preview of the affected file region.

        Args:
            path: Relative path to the file to edit.
            operation: The file editing operation to perform (replace, insert, remove, move).
            search: Text or pattern to search for (used in replace).
            replacement: Replacement text (used in replace and insert).
            line_number: Starting line number for insert, remove, or move operations.
            end_line: Ending line number for remove or move operations.
            target_line: Target line number for move operations.
            use_regex: Whether to interpret the search string as a regular expression.
            replace_all: Whether to replace all occurrences (for replace).
            context_before: Required context before the match (for replace).
            context_after: Required context after the match (for replace).
            occurrence: Which occurrence to replace (for replace).
            dry_run: If True, shows the result without modifying the file.

        Returns:
            A message describing the result of the operation and a preview of the affected file region. Returns an error message if the operation fails or is invalid.
        """
        try:
            resolved_path = self.path_handler.resolve_path(path, must_exist=False)

            # Check if file exists and create an empty file if needed
            file_exists = os.path.exists(resolved_path)
            if not file_exists:
                if operation == FileEditOperation.INSERT:
                    # Create parent directories if they don't exist
                    self.path_handler.ensure_directory_exists(resolved_path)
                    # Create empty file for insertion
                    with open(resolved_path, "w", encoding="utf-8") as f:
                        pass
                    file_exists = True
                else:
                    return (
                        f"Error: File doesn't exist: {path}. To create a new file, use insert at line 1 or create_file."
                    )

            # Backup the file if not in dry run mode and file exists
            if not dry_run and file_exists:
                self.backup_manager.backup_file(resolved_path)

            # Read file content if file exists
            content = ""
            lines = []
            if file_exists:
                try:
                    with open(resolved_path, encoding="utf-8") as f:
                        content = f.read()
                        lines = content.splitlines(keepends=True)
                except Exception as e:
                    return f"Error reading file: {e!s}"

            # Execute the requested operation
            if operation == FileEditOperation.REPLACE:
                if not search or replacement is None:
                    return "Error: Search and replacement strings are required for replace operation"

                # Special handling for empty files
                if not content:
                    return f"Error: Cannot replace text in empty file {path}. Use insert_at_line instead."

                new_content, locations = self._replace_content(
                    content,
                    search,
                    replacement,
                    use_regex,
                    replace_all,
                    context_before,
                    context_after,
                    line_number,
                    occurrence,
                )

                if not locations:
                    pattern_type = "Regex pattern" if use_regex else "Text"
                    return f"Error: {pattern_type} not found in {path}"

            elif operation == FileEditOperation.INSERT:
                if replacement is None:
                    return "Error: Replacement text is required for insert operation"

                # Handle insertion in empty or small files
                if line_number is None:
                    line_number = 1

                # Handle case where line number is beyond file length
                if line_number > len(lines) + 1:
                    # For empty files or new files, accept only line 1
                    if len(lines) == 0 and line_number != 1:
                        return "Error: File is empty. For empty files, you can only insert at line 1."
                    # For non-empty files, allow insert at line = len(lines) + 1 (end of file)
                    if line_number > len(lines) + 1:
                        return f"Error: Invalid line number {line_number}. File has {len(lines)} lines. Valid range is 1 to {len(lines) + 1}."

                # Convert to 0-based indexing
                insert_index = max(0, min(line_number - 1, len(lines)))

                # Insert the new text
                if not replacement.endswith("\n"):
                    replacement += "\n"

                if not lines:
                    # Empty file case
                    lines = [replacement]
                else:
                    lines.insert(insert_index, replacement)

                new_content = "".join(lines)

            elif operation == FileEditOperation.REMOVE:
                if line_number is None or end_line is None:
                    return "Error: Start and end line numbers are required for remove operation"

                # Special handling for empty files
                if not lines:
                    return f"Warning: Cannot remove lines from empty file {path}."

                if line_number < 1 or end_line > len(lines) or line_number > end_line:
                    return f"Error: Invalid line range. File has {len(lines)} lines, requested to remove lines {line_number}-{end_line}."

                # Convert to 0-based indexing
                start_idx = line_number - 1
                end_idx = end_line

                # Remove the lines
                lines[start_idx:end_idx]
                lines = lines[:start_idx] + lines[end_idx:]
                new_content = "".join(lines)

            elif operation == FileEditOperation.MOVE:
                if line_number is None or end_line is None or target_line is None:
                    return "Error: Start, end, and target line numbers are required for move operation"

                # Special handling for empty files
                if not lines:
                    return f"Warning: Cannot move lines in empty file {path}."

                if line_number < 1 or end_line > len(lines) or line_number > end_line:
                    return f"Error: Invalid line range. File has {len(lines)} lines, requested to move lines {line_number}-{end_line}."

                if target_line < 1 or target_line > len(lines) + 1:
                    return f"Error: Invalid target line. File has {len(lines)} lines, requested to insert at line {target_line}."

                # Check if target is within the block to move
                if target_line >= line_number and target_line <= end_line + 1:
                    return "Error: Target line is within the block to move. This would result in no change."

                # Convert to 0-based indexing
                start_idx = line_number - 1
                end_idx = end_line
                target_idx = target_line - 1

                # Extract the block to move
                block_lines = lines[start_idx:end_idx]

                # Adjust target position if it's after the block being removed
                adjusted_target = target_idx
                if target_idx > end_idx:
                    adjusted_target -= end_idx - start_idx

                # Build the new content
                new_lines = []
                i = 0
                while i < len(lines):
                    if i == start_idx:
                        # Skip the block being moved
                        i = end_idx
                    elif i == adjusted_target:
                        # Insert the block at the target position
                        new_lines.extend(block_lines)
                        if i < len(lines):
                            new_lines.append(lines[i])
                        i += 1
                    else:
                        if i < len(lines):
                            new_lines.append(lines[i])
                        i += 1

                # Handle case when target is at the end of the file
                if adjusted_target == len(lines):
                    new_lines.extend(block_lines)

                new_content = "".join(new_lines)

            else:
                return f"Error: Unsupported operation: {operation}"

            # Write the changes if not a dry run
            if not dry_run:
                # Ensure parent directory exists
                self.path_handler.ensure_directory_exists(resolved_path)

                with open(resolved_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

            # Generate result message
            action = "Would " if dry_run else ""

            if operation == FileEditOperation.REPLACE:
                replaced_count = len(locations)
                msg = f"{action}replace{'d' if not dry_run else ''} {replaced_count} {'regex match' if use_regex else 'location'}{'es' if replaced_count > 1 else ''} in {path}."
                preview_line = locations[0][2] if locations else None

            elif operation == FileEditOperation.INSERT:
                msg = f"{action}insert{'ed' if not dry_run else ''} text at line {line_number} in {path}."
                preview_line = line_number

            elif operation == FileEditOperation.REMOVE:
                lines_removed = end_line - line_number + 1
                msg = f"{action}remove{'d' if not dry_run else ''} {lines_removed} line{'s' if lines_removed != 1 else ''} ({line_number}-{end_line}) from {path}."
                preview_line = max(1, line_number - 1)

            elif operation == FileEditOperation.MOVE:
                lines_moved = end_line - line_number + 1
                msg = f"{action}move{'d' if not dry_run else ''} {lines_moved} line{'s' if lines_moved != 1 else ''} from {line_number}-{end_line} to line {target_line} in {path}."
                preview_line = (
                    max(1, target_line - 2) if target_line < line_number else max(1, target_line - lines_moved - 2)
                )

            # Get file preview after the change
            file_preview = self._get_file_preview(path, preview_line)
            return f"{msg}\n\nPreview:\n{file_preview}"

        except Exception as e:
            return f"Error editing file: {e!s}"

    def _replace_content(
        self,
        content: str,
        search: str,
        replacement: str,
        use_regex: bool,
        replace_all: bool,
        context_before: str | None,
        context_after: str | None,
        line_number: int | None,
        occurrence: int,
    ) -> tuple[str, list[tuple[int, int, int]]]:
        """Performs targeted find-and-replace operations within the provided content.

        Supports plain text or regular expression search, with options for context-aware matching, line number restriction, occurrence selection, and replacing all matches. Returns the modified content and a list of replaced locations as (start, end, line number) tuples.

        Args:
            content: The text to search and modify.
            search: The string or regex pattern to find.
            replacement: The text to insert in place of each match.
            use_regex: If True, interprets `search` as a regular expression.
            replace_all: If True, replaces all matches; otherwise, only the specified occurrence.
            context_before: Optional string that must precede a match.
            context_after: Optional string that must follow a match.
            line_number: If provided, restricts search to this line.
            occurrence: The 1-based index of the match to replace if not replacing all.

        Returns:
            A tuple containing the modified content and a list of (start, end, line number) for each replacement made.

        Raises:
            ValueError: If an invalid regular expression is provided.
        """
        lines = content.split("\n")
        occurrences = []

        if use_regex:
            # Regex-based search
            try:
                regex = re.compile(search, re.MULTILINE | re.DOTALL)
            except re.error as e:
                # Handle invalid regex pattern
                msg = f"Invalid regex pattern: {e!s}"
                raise ValueError(msg)

            # Handle line number constraint
            if line_number is not None:
                line_idx = line_number - 1
                if 0 <= line_idx < len(lines):
                    line_content = lines[line_idx]
                    for match in regex.finditer(line_content):
                        line_start = sum(len(lines[i]) + 1 for i in range(line_idx))
                        start = line_start + match.start()
                        end = line_start + match.end()
                        occurrences.append((start, end, line_number))
            else:
                for match in regex.finditer(content):
                    start, end = match.span()
                    line_count = content[:start].count("\n") + 1
                    occurrences.append((start, end, line_count))

        # Plain string search
        elif context_before or context_after:
            # Context-aware search

            try:
                if context_before and context_after:
                    pattern_str = f"(?<={re.escape(context_before)})({re.escape(search)})(?={re.escape(context_after)})"
                elif context_before:
                    pattern_str = f"(?<={re.escape(context_before)})({re.escape(search)})"
                elif context_after:
                    pattern_str = f"({re.escape(search)})(?={re.escape(context_after)})"

                pattern = re.compile(pattern_str, re.MULTILINE | re.DOTALL)
                matches = list(pattern.finditer(content))

                for match in matches:
                    start, end = match.span(1)
                    line_count = content[:start].count("\n") + 1
                    occurrences.append((start, end, line_count))
            except re.error:
                # Fall back to regular search if context pattern is invalid
                pass

        elif line_number is not None:
            # Line-constrained search
            line_idx = line_number - 1
            if 0 <= line_idx < len(lines):
                line_content = lines[line_idx]
                start_pos = 0
                while True:
                    pos = line_content.find(search, start_pos)
                    if pos == -1:
                        break
                    line_start = sum(len(lines[i]) + 1 for i in range(line_idx))
                    start = line_start + pos
                    end = start + len(search)
                    occurrences.append((start, end, line_number))
                    start_pos = pos + 1
        else:
            # Full-content search
            start_pos = 0
            while True:
                pos = content.find(search, start_pos)
                if pos == -1:
                    break
                line_count = content[:pos].count("\n") + 1
                occurrences.append((pos, pos + len(search), line_count))
                start_pos = pos + 1

        if not occurrences:
            return content, []

        # Sort occurrences by position
        occurrences.sort()

        # Select which occurrences to replace
        if replace_all:
            to_replace = occurrences
        # Validate occurrence index
        elif occurrence < 1 or occurrence > len(occurrences):
            valid_range = f"1 to {len(occurrences)}"
            msg = f"Invalid occurrence index {occurrence}. Valid range is {valid_range}."
            to_replace = []
        else:
            to_replace = [occurrences[occurrence - 1]]

        if not to_replace:
            return content, []

        # Apply replacements
        new_content = content
        for pos_start, pos_end, _line_num in reversed(to_replace):
            if use_regex:
                match_text = content[pos_start:pos_end]
                try:
                    replaced_text = re.sub(search, replacement, match_text)
                    new_content = new_content[:pos_start] + replaced_text + new_content[pos_end:]
                except Exception:
                    # Skip invalid regex replacements
                    pass
            else:
                new_content = new_content[:pos_start] + replacement + new_content[pos_end:]

        return new_content, to_replace

    def build_toolkit(self) -> Tool:
        """Initializes and returns a suite of file system manipulation and inspection tools.

        This method sets up the backup and path handling infrastructure, then defines and returns a collection of tools for file and directory operations within the workspace. The toolkit includes functions for viewing and editing files, undoing and redoing changes, creating files, listing directories, moving files or directories, searching files and code, generating diff patches, and analyzing Python code structure. Each tool is decorated for integration and provides detailed results or previews, with built-in error handling and workspace boundary enforcement.
        """
        # Initialize components
        self.backup_manager = BackupManager(self.workspace_folder)
        self.path_handler = PathHandler(self.workspace_folder)

        from langchain_core.tools import tool

        @tool
        def view_file(path: str, view_range: list[int] | None = None) -> str:
            """Displays the contents of a file with line numbers.

            If a line range is provided, only those lines are shown; otherwise, the entire file is displayed. Returns an error message if the file does not exist or is empty.

            Args:
                path: Relative path to the file within the workspace.
                view_range: Optional two-element list [start_line, end_line] specifying the range of lines to display (use -1 for end of file).

            Returns:
                A string containing the file contents with line numbers, or an error message if the file is not found or empty.
            """
            try:
                resolved_path = self.path_handler.resolve_path(path)

                # Check if file is empty
                if os.path.getsize(resolved_path) == 0:
                    return f"File is empty: {path}"

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

            except FileNotFoundError:
                return f"Error: File not found: {path}"
            except Exception as e:
                return f"Error viewing file: {e!s}"

        @tool
        def str_replace(
            path: str,
            old_str: str,
            new_str: str,
            use_regex: bool = False,
            replace_all: bool = False,
            context_before: str | None = None,
            context_after: str | None = None,
            line_number: int | None = None,
            occurrence: int = 1,
            *,
            dry_run: bool = False,
        ) -> str:
            """Performs text replacement in a file with advanced pattern matching capabilities.

            Supports plain text or regular expression search, context constraints,
            line restriction, and dry-run preview. Can replace a specific occurrence
            or all matches, with optional context before and after the match to refine
            targeting. Returns a summary of the operation and a preview of the affected
            file region.
            """
            return self._edit_file(
                path=path,
                operation=FileEditOperation.REPLACE,
                search=old_str,
                replacement=new_str,
                use_regex=use_regex,
                replace_all=replace_all,
                context_before=context_before,
                context_after=context_after,
                line_number=line_number,
                occurrence=occurrence,
                dry_run=dry_run,
            )

        @tool
        def insert_at_line(
            path: str,
            line_number: int,
            new_str: str,
            *,
            dry_run: bool = False
        ) -> str:
            """Inserts text at a specified line number in a file.

            Args:
                path: Relative path to the target file within the workspace.
                line_number: 1-based line number at which to insert the text. For empty files, use 1.
                new_str: The text to insert.
                dry_run: If True, displays the changes without modifying the file.

            Returns:
                A message describing the result and a preview of the affected file content.
            """
            return self._edit_file(
                path=path,
                operation=FileEditOperation.INSERT,
                replacement=new_str,
                line_number=line_number,
                dry_run=dry_run,
            )

        @tool
        def remove_lines(
            path: str,
            start_line: int,
            end_line: int,
            *,
            dry_run: bool = False
        ) -> str:
            """Removes a range of lines from a file.

            Args:
                path: Relative path to the file within the workspace.
                start_line: The first line to remove (1-based index).
                end_line: The last line to remove (1-based index).
                dry_run: If True, displays the changes without modifying the file.

            Returns:
                A message describing the result of the operation and a preview of the affected file region.
            """
            return self._edit_file(
                path=path,
                operation=FileEditOperation.REMOVE,
                line_number=start_line,
                end_line=end_line,
                dry_run=dry_run,
            )

        @tool
        def move_code_block(
            path: str,
            start_line: int,
            end_line: int,
            target_line: int,
            *,
            dry_run: bool = False
        ) -> str:
            """Moves a block of lines from one location to another within the same file.

            Args:
                path: Relative path to the file within the workspace.
                start_line: The first line of the block to move (1-based).
                end_line: The last line of the block to move (1-based).
                target_line: The line number where the block should be inserted (1-based).
                dry_run: If True, displays the changes without modifying the file.

            Returns:
                A message describing the result of the move operation, including a preview of the affected file region.
            """
            return self._edit_file(
                path=path,
                operation=FileEditOperation.MOVE,
                line_number=start_line,
                end_line=end_line,
                target_line=target_line,
                dry_run=dry_run,
            )

        @tool
        def undo_edit(path: str) -> str:
            """Undoes the last edit made to a file by restoring it to the previous backup version.

            Args:
                path: Path to the file relative to the workspace.

            Returns:
                A message indicating the result of the undo operation, including a
                preview of the restored file version.
            """
            try:
                resolved_path = self.path_handler.resolve_path(path)
                success, backup_id, message = self.backup_manager.restore(resolved_path, "undo")

                if not success:
                    return f"Note: {message}"

                # Get information about backup history
                info = self.backup_manager.get_backup_info(resolved_path)

                # Get preview
                file_preview = self._get_file_preview(path)

                result = f"Successfully undid changes to {path}.\n"
                if info["position"] >= 0:
                    result += f"Restored to version {info['position'] + 1} of {info['count']}.\n"
                    if info["can_undo"]:
                        result += f"You can undo {info['count'] - info['position'] - 1} more time(s).\n"
                    if info["can_redo"]:
                        result += "You can redo this operation.\n"

                result += f"\nPreview:\n{file_preview}"
            except Exception as e:
                return f"Error undoing edit: {e!s}"
            else:
                return result

        @tool
        def redo_edit(path: str) -> str:
            """Redoes the last undone edit for a file, restoring it to a newer backup version if available.

            Returns a message indicating the result of the redo operation along with
            a preview of the file's current content.
            """
            try:
                resolved_path = self.path_handler.resolve_path(path)
                success, backup_id, message = self.backup_manager.restore(resolved_path, "redo")

                if not success:
                    return f"Note: {message}"

                # Get information about backup history
                info = self.backup_manager.get_backup_info(resolved_path)

                # Get preview
                file_preview = self._get_file_preview(path)

                result = f"Successfully redid changes to {path}.\n"
                if backup_id == "current":
                    result += "Restored to current version.\n"
                    if info["can_undo"]:
                        result += "You can undo this operation.\n"
                elif info["position"] >= 0:
                    result += f"Restored to version {info['position'] + 1} of {info['count']}.\n"
                    if info["can_undo"]:
                        result += "You can undo this operation.\n"
                    if info["can_redo"]:
                        result += f"You can redo {info['position']} more time(s).\n"

                result += f"\nPreview:\n{file_preview}"
            except Exception as e:
                return f"Error redoing edit: {e!s}"
            else:
                return result

        @tool
        def create_file(path: str, file_text: str) -> str:
            """Creates or overwrites a file with the specified content, backing up any existing file.

            If the file already exists, a backup is created before overwriting.
            Returns a message indicating the result and a preview of the file's contents.
            """
            try:
                resolved_path = self.path_handler.resolve_path(path, must_exist=False)

                # Create directories if they don't exist
                from pathlib import Path
                parent_dir = Path(resolved_path).parent
                parent_dir.mkdir(parents=True, exist_ok=True)

                # Check if file exists
                action = "Created"
                if Path(resolved_path).exists():
                    self.backup_manager.backup_file(resolved_path)
                    action = "Updated"

                with Path(resolved_path).open("w", encoding="utf-8") as f:
                    f.write(file_text)

                # Get preview
                file_preview = self._get_file_preview(path)
            except Exception as e:
                return f"Error creating file: {e!s}"
            else:
                return f"Successfully {action} file: {path}\n\nPreview:\n{file_preview}"

        @tool
        def create_directory(directory_path: str) -> str:
            """Creates a new directory in the workspace.

            Args:
                directory_path: Relative path to the directory to create.

            Returns:
                A message indicating the result of the operation.
            """
            try:
                resolved_path = self.path_handler.resolve_path(directory_path, must_exist=False)
                from pathlib import Path
                path_obj = Path(resolved_path)

                # Check if path already exists
                if path_obj.exists():
                    if path_obj.is_dir():
                        return f"Directory already exists: {directory_path}"
                    return f"Error: Path exists but is not a directory: {directory_path}"

                # Create the directory
                path_obj.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                return f"Error creating directory: {e!s}"
            else:
                return f"Successfully created directory: {directory_path}"

        @tool
        def list_directory(directory_path: str = ".") -> str:
            """Returns a detailed listing of files and directories within a specified directory.

            Args:
                directory_path: Relative path to the directory within the workspace
                    (defaults to workspace root).

            Returns:
                A formatted string listing directories and files with type indicators
                and file sizes, or an error message if the path is invalid.
            """
            try:
                resolved_path = self.path_handler.resolve_path(directory_path)
                from pathlib import Path
                path_obj = Path(resolved_path)

                if not path_obj.is_dir():
                    return f"Error: Not a directory: {directory_path}"

                # List directory contents
                entries = list(path_obj.iterdir())
                result = f"Contents of {directory_path}:\n"

                # Add directories first, then files
                dirs = []
                files = []

                # File size constants
                KB_SIZE = 1024
                MB_SIZE = KB_SIZE * 1024

                for entry in entries:
                    if entry.is_dir():
                        dirs.append((entry.name, "directory"))
                    else:
                        # Get file size
                        size = entry.stat().st_size
                        size_str = f"{size} bytes"
                        if size > KB_SIZE:
                            size_str = f"{size / KB_SIZE:.1f} KB"
                        if size > MB_SIZE:
                            size_str = f"{size / MB_SIZE:.1f} MB"
                        files.append((entry.name, "file", size_str))

                # Format and add to result
                for name, type_ in sorted(dirs):
                    result += f"📁 {name}/ ({type_})\n"
                for name, type_, size in sorted(files):
                    result += f"📄 {name} ({type_}, {size})\n"

                if not dirs and not files:
                    result += "Directory is empty."

            except OSError as e:
                return f"Error listing directory: {e!s}"
            else:
                return result

        @tool
        def move_file(source_path: str, destination_path: str) -> str:
            """Moves or renames a file or directory within the workspace, creating backups if applicable.

            Args:
                source_path: Relative path to the source file or directory.
                destination_path: Relative path to the destination location.

            Returns:
                A message indicating the result of the move or rename operation.
            """
            try:
                resolved_source = self.path_handler.resolve_path(source_path)
                resolved_dest = self.path_handler.resolve_path(destination_path, must_exist=False)
                from pathlib import Path

                source_obj = Path(resolved_source)
                dest_obj = Path(resolved_dest)

                # Create backup for the source if it's a file
                if source_obj.is_file():
                    self.backup_manager.backup_file(resolved_source)

                # Create backup for the destination if it exists and is a file
                if dest_obj.is_file() and dest_obj.exists():
                    self.backup_manager.backup_file(resolved_dest)

                # Create destination directory if it doesn't exist
                dest_obj.parent.mkdir(parents=True, exist_ok=True)

                # Move/rename the file or directory
                shutil.move(resolved_source, resolved_dest)

                source_type = "directory" if dest_obj.is_dir() else "file"
            except Exception as e:
                return f"Error moving file: {e!s}"
            else:
                return f"Successfully moved {source_type} from {source_path} to {destination_path}"

        @tool
        def search_files(search_pattern: str, directory_path: str = ".") -> str:
            """Searches for files whose names contain the given pattern, case-insensitively, within a directory.

            Args:
                search_pattern: Substring to match in filenames (case-insensitive).
                directory_path: Directory to search within, relative to the workspace root
                    (default is current directory).

            Returns:
                A formatted string listing all matching file paths, or an error message
                if no matches are found or the directory is invalid.
            """
            try:
                resolved_path = self.path_handler.resolve_path(directory_path)
                from pathlib import Path
                path_obj = Path(resolved_path)

                if not path_obj.is_dir():
                    return f"Error: Not a directory: {directory_path}"

                # Search for matching files
                matches = []
                pattern = f"*{search_pattern}*"

                for root, _dirs, files in os.walk(resolved_path):
                    for name in files:
                        if fnmatch.fnmatch(name.lower(), pattern.lower()):
                            from pathlib import Path
                            rel_path = os.path.relpath(
                                Path(root) / name,
                                self.workspace_folder
                            )
                            matches.append(rel_path)

                if not matches:
                    return f"No files matching '{search_pattern}' found in {directory_path}"

                result = f"Found {len(matches)} file(s) matching '{search_pattern}':\n"
                for match in sorted(matches):
                    result += f"- {match}\n"

            except Exception as e:
                return f"Error searching files: {e!s}"
            else:
                return result

        @tool
        def search_code(search_pattern: str, file_pattern: str = "*", directory_path: str = ".") -> str:
            """Searches for a text pattern within the contents of files in a directory tree.

            Args:
                search_pattern: The text to search for within file contents.
                file_pattern: A glob pattern to filter files by name (e.g., "*.py").
                directory_path: Directory to search in, relative to the workspace root.

            Returns:
                A formatted string listing each match with file path and line number,
                or a message if no matches are found.
            """
            try:
                resolved_path = self.path_handler.resolve_path(directory_path)
                from pathlib import Path
                path_obj = Path(resolved_path)

                if not path_obj.is_dir():
                    return f"Error: Not a directory: {directory_path}"

                # Python-based search
                matches = []

                for root, _dirs, files in os.walk(resolved_path):
                    for name in files:
                        if fnmatch.fnmatch(name, file_pattern):
                            file_path = Path(root) / name
                            try:
                                with file_path.open(encoding="utf-8") as f:
                                    for i, line in enumerate(f, 1):
                                        if search_pattern in line:
                                            rel_path = os.path.relpath(file_path, self.workspace_folder)
                                            matches.append((rel_path, i, line.strip()))
                            except (UnicodeDecodeError, OSError):
                                # Skip files that can't be read as text
                                pass

                if not matches:
                    return f"No matches found for '{search_pattern}' in {directory_path}"

                result = f"Found {len(matches)} match(es) for '{search_pattern}':\n"

                for file_path, line_num, content in matches:
                    result += f"{file_path}:{line_num}: {content}\n"

            except Exception as e:
                return f"Error searching code: {e!s}"
            else:
                return result

        @tool
        def generate_patch(path: str, old_content: str | None = None, new_content: str | None = None) -> str:
            """Generates a unified diff patch between the original and new content of a file.

            If the original content is not provided, it is read from the specified file.
            Returns the unified diff as a string, or a message if there are no differences
            or if an error occurs.
            """
            try:
                resolved_path = self.path_handler.resolve_path(path)
                from pathlib import Path

                # If old_content not provided, read from file
                if old_content is None:
                    with Path(resolved_path).open(encoding="utf-8") as f:
                        old_content = f.read()

                # New content must be provided
                if new_content is None:
                    return "Error: New content must be provided"

                # Generate diff using difflib
                old_lines = old_content.splitlines()
                new_lines = new_content.splitlines()

                diff = difflib.unified_diff(old_lines, new_lines, lineterm="", n=3)

                diff_text = "\n".join(diff)
            except Exception as e:
                return f"Error generating patch: {e!s}"
            else:
                return diff_text if diff_text else "No differences found."

        @tool
        def find_code_structure(path: str, item_type: str = "all") -> str:
            """Analyzes a Python file to identify functions, classes, and methods with their line ranges.

            Args:
                path: Relative path to the file within the workspace.
                item_type: Type of code elements to find
                    ("function", "class", "method", or "all").

            Returns:
                A formatted string listing the names and line ranges of the specified
                code elements, or an error message if the file is not found, empty,
                not a Python file, or contains syntax errors.
            """
            try:
                resolved_path = self.path_handler.resolve_path(path)
                from pathlib import Path
                path_obj = Path(resolved_path)

                # Check file existence first
                if not path_obj.exists():
                    return f"Error: File not found: {path}"

                # Check file size, handle empty files gracefully
                if path_obj.stat().st_size == 0:
                    return f"File {path} is empty."

                # Only supporting Python files for now
                if path_obj.suffix.lower() != ".py":
                    return (
                        f"Note: Code structure analysis is currently only supported for "
                        f"Python (.py) files. File {path} has extension {path_obj.suffix}."
                    )

                # Read file content
                with path_obj.open(encoding="utf-8") as f:
                    content = f.read()

                # Parse the Python code
                try:
                    tree = ast.parse(content)
                except SyntaxError as e:
                    return (
                        f"Error: Could not parse {path} - syntax error at line {e.lineno}, "
                        f"column {e.offset}: {e.msg}"
                    )

                # Helper function to extract line range for a node
                def get_line_range(node):
                    """Returns the start and end line numbers for an AST node.

                    The start line is taken from the node's 'lineno' attribute, and the
                    end line is determined by traversing all child nodes to find the
                    maximum line number present.

                    Args:
                        node: An AST node with a 'lineno' attribute.

                    Returns:
                        A tuple (start_line, end_line) indicating the range of lines
                        spanned by the node.
                    """
                    start_line = getattr(node, "lineno", 0)
                    end_line = start_line

                    # Try to find the last line of the node
                    for child_node in ast.walk(node):
                        if hasattr(child_node, "lineno"):
                            end_line = max(end_line, child_node.lineno)

                    return start_line, end_line

                # Find all matching nodes
                result = f"Code structure for {path}:\n\n"
                has_content = False

                # Functions
                if item_type in ["function", "all"]:
                    functions = [
                        node
                        for node in ast.walk(tree)
                        if isinstance(node, ast.FunctionDef) and not hasattr(node, "parent_class")
                    ]
                    if functions:
                        has_content = True
                        result += "Functions:\n"
                        for func in functions:
                            start, end = get_line_range(func)
                            result += f"- {func.name} (lines {start}-{end})\n"
                        result += "\n"

                # Classes and methods
                if item_type in ["class", "method", "all"]:
                    classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
                    if classes:
                        has_content = True
                        result += "Classes:\n"
                        for cls in classes:
                            start, end = get_line_range(cls)
                            result += f"- {cls.name} (lines {start}-{end})\n"

                            # Show methods if requested
                            if item_type in ["method", "all"]:
                                methods = [
                                    node for node in cls.body if isinstance(node, ast.FunctionDef)
                                ]
                                if methods:
                                    for method in methods:
                                        start, end = get_line_range(method)
                                        result += f"  - {method.name} (lines {start}-{end})\n"
                        result += "\n"

                if not has_content:
                    result += f"No {item_type} items found in {path}."

            except OSError as e:
                return f"Error analyzing code structure: {e!s}"
            else:
                return result

        # Return all tools
        return [
            view_file,
            str_replace,
            insert_at_line,
            remove_lines,
            move_code_block,
            undo_edit,
            redo_edit,
            create_file,
            create_directory,
            list_directory,
            move_file,
            search_files,
            search_code,
            generate_patch,
            find_code_structure,
        ]
