import os
import shutil
import platform
import re
import fnmatch
import tempfile
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from enum import Enum
import ast
import difflib

from langflow.custom import Component
from langflow.field_typing import Tool
from langflow.io import StrInput, Output


class BackupManager:
    """Simple backup system for file operations."""
    
    def __init__(self, workspace_folder: str):
        self.workspace_folder = workspace_folder
        self.backup_folder = os.path.join(workspace_folder, ".backups")
        self.backup_registry = {}  # file_path -> [backup_ids]
        self.current_positions = {}  # file_path -> current_position_index
        
        if not os.path.exists(self.backup_folder):
            os.makedirs(self.backup_folder)
    
    def backup_file(self, file_path: str) -> Optional[str]:
        """Create a backup of a file before modifying it."""
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
                self.backup_registry[file_path] = self.backup_registry[file_path][:position+1]
                self.current_positions[file_path] = -1
                
            self.backup_registry[file_path].append(backup_id)
            return backup_id
            
        except Exception as e:
            return None
    
    def get_backups(self, file_path: str) -> List[str]:
        """Get list of backups for a file."""
        return self.backup_registry.get(file_path, [])
    
    def get_backup_info(self, file_path: str) -> Dict[str, Any]:
        """Get information about backup history."""
        if file_path not in self.backup_registry:
            return {
                "count": 0, 
                "position": -1, 
                "can_undo": False, 
                "can_redo": False
            }
            
        backups = self.backup_registry[file_path]
        position = self.current_positions[file_path]
        
        return {
            "count": len(backups),
            "position": position,
            "can_undo": position < len(backups) - 1 if position != -1 else len(backups) > 0,
            "can_redo": position > 0 if position != -1 else False
        }
    
    def restore(self, file_path: str, direction: str = "undo") -> Tuple[bool, Optional[str], str]:
        """Restore a file to a previous or newer version."""
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
            elif position < len(backups) - 1:
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
            return True, backup_id, f"Successfully restored {direction} to version {new_position+1} of {len(backups)}"
        except Exception as e:
            return False, None, f"Failed to restore: {str(e)}"


class PathHandler:
    """Handle path operations safely."""
    
    def __init__(self, workspace_folder: str):
        self.workspace_folder = workspace_folder
        self.platform = platform.system()
    
    def resolve_path(self, relative_path: str, must_exist: bool = True) -> str:
        """Resolve a path relative to the workspace and check security constraints."""
        # Check if absolute
        if os.path.isabs(relative_path):
            raise ValueError(f"Path must be relative to workspace: {relative_path}")
            
        # Normalize path separators for the current platform
        if self.platform == "Windows":
            relative_path = relative_path.replace('/', '\\')
        else:
            relative_path = relative_path.replace('\\', '/')
            
        # Join with workspace and normalize
        full_path = os.path.normpath(os.path.join(self.workspace_folder, relative_path))
        
        # Security check: ensure path is within workspace
        if not os.path.abspath(full_path).startswith(os.path.abspath(self.workspace_folder)):
            raise ValueError(f"Path must be within workspace: {relative_path}")
            
        # Check existence if required
        if must_exist and not os.path.exists(full_path):
            raise FileNotFoundError(f"Path does not exist: {relative_path}")
            
        return full_path
        
    def is_within_workspace(self, path: str) -> bool:
        """Check if a path is within the workspace."""
        abs_path = os.path.abspath(path)
        abs_workspace = os.path.abspath(self.workspace_folder)
        return abs_path.startswith(abs_workspace)
    
    def ensure_directory_exists(self, path: str) -> None:
        """Ensure that the directory for the given path exists."""
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
        super().__init__(*args, **kwargs)
        self.backup_manager = None
        self.path_handler = None
        
    def _get_file_preview(self, file_path: str, line_number: Optional[int] = None, context_lines: int = 5) -> str:
        """Get a preview of file content with line numbers."""
        try:
            resolved_path = self.path_handler.resolve_path(file_path)
            
            if not os.path.exists(resolved_path):
                return f"File not found: {file_path}"
                
            # Handle empty files
            if os.path.getsize(resolved_path) == 0:
                return f"File is empty: {file_path}"
            
            with open(resolved_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # If specific line is provided, show context around it
            if line_number is not None:
                start = max(0, line_number - context_lines - 1)
                end = min(len(lines), line_number + context_lines)
                preview_lines = lines[start:end]
                result = ""
                for i, line in enumerate(preview_lines, start=start+1):
                    prefix = ">>> " if i == line_number else "    "
                    result += f"{prefix}{i}: {line}"
                return result
            
            # Otherwise show first few lines
            result = ""
            preview_length = min(10, len(lines))
            for i, line in enumerate(lines[:preview_length], start=1):
                result += f"{i}: {line}"
            if len(lines) > preview_length:
                result += f"\n... and {len(lines)-preview_length} more lines"
            return result
            
        except Exception as e:
            return f"Error getting file preview: {str(e)}"
    
    def _edit_file(
        self, 
        path: str, 
        operation: FileEditOperation,
        search: Optional[str] = None,
        replacement: Optional[str] = None,
        line_number: Optional[int] = None,
        end_line: Optional[int] = None,
        target_line: Optional[int] = None,
        use_regex: bool = False,
        replace_all: bool = False,
        context_before: Optional[str] = None,
        context_after: Optional[str] = None,
        occurrence: int = 1,
        dry_run: bool = False
    ) -> str:
        """Unified method for file editing operations."""
        try:
            resolved_path = self.path_handler.resolve_path(path, must_exist=False)
            
            # Check if file exists and create an empty file if needed
            file_exists = os.path.exists(resolved_path)
            if not file_exists:
                if operation == FileEditOperation.INSERT:
                    # Create parent directories if they don't exist
                    self.path_handler.ensure_directory_exists(resolved_path)
                    # Create empty file for insertion
                    with open(resolved_path, 'w', encoding='utf-8') as f:
                        pass
                    file_exists = True
                else:
                    return f"Error: File doesn't exist: {path}. To create a new file, use insert at line 1 or create_file."
            
            # Backup the file if not in dry run mode and file exists
            if not dry_run and file_exists:
                backup_id = self.backup_manager.backup_file(resolved_path)
            
            # Read file content if file exists
            content = ""
            lines = []
            if file_exists:
                try:
                    with open(resolved_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = content.splitlines(keepends=True)
                except Exception as e:
                    return f"Error reading file: {str(e)}"
            
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
                    occurrence
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
                        return f"Error: File is empty. For empty files, you can only insert at line 1."
                    # For non-empty files, allow insert at line = len(lines) + 1 (end of file)
                    elif line_number > len(lines) + 1:
                        return f"Error: Invalid line number {line_number}. File has {len(lines)} lines. Valid range is 1 to {len(lines) + 1}."
                
                # Convert to 0-based indexing
                insert_index = max(0, min(line_number - 1, len(lines)))
                
                # Insert the new text
                if not replacement.endswith('\n'):
                    replacement += '\n'
                    
                if not lines:
                    # Empty file case
                    lines = [replacement]
                else:
                    lines.insert(insert_index, replacement)
                    
                new_content = ''.join(lines)
                
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
                removed_lines = lines[start_idx:end_idx]
                lines = lines[:start_idx] + lines[end_idx:]
                new_content = ''.join(lines)
                
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
                    adjusted_target -= (end_idx - start_idx)
                
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
                    
                new_content = ''.join(new_lines)
            
            else:
                return f"Error: Unsupported operation: {operation}"
            
            # Write the changes if not a dry run
            if not dry_run:
                # Ensure parent directory exists
                self.path_handler.ensure_directory_exists(resolved_path)
                
                with open(resolved_path, 'w', encoding='utf-8') as f:
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
                preview_line = max(1, target_line - 2) if target_line < line_number else max(1, target_line - lines_moved - 2)
            
            # Get file preview after the change
            file_preview = self._get_file_preview(path, preview_line)
            return f"{msg}\n\nPreview:\n{file_preview}"
            
        except Exception as e:
            return f"Error editing file: {str(e)}"
    
    def _replace_content(
        self, 
        content: str, 
        search: str, 
        replacement: str, 
        use_regex: bool, 
        replace_all: bool, 
        context_before: Optional[str], 
        context_after: Optional[str], 
        line_number: Optional[int], 
        occurrence: int
    ) -> Tuple[str, List[Tuple[int, int, int]]]:
        """Find and replace content with various targeting options."""
        lines = content.split('\n')
        occurrences = []
        
        if use_regex:
            # Regex-based search
            try:
                regex = re.compile(search, re.MULTILINE | re.DOTALL)
            except re.error as e:
                # Handle invalid regex pattern
                msg = f"Invalid regex pattern: {str(e)}"
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
                    line_count = content[:start].count('\n') + 1
                    occurrences.append((start, end, line_count))
                    
        else:
            # Plain string search
            if context_before or context_after:
                # Context-aware search
                import re
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
                        line_count = content[:start].count('\n') + 1
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
                    line_count = content[:pos].count('\n') + 1
                    occurrences.append((pos, pos + len(search), line_count))
                    start_pos = pos + 1
        
        if not occurrences:
            return content, []
            
        # Sort occurrences by position
        occurrences.sort()
        
        # Select which occurrences to replace
        if replace_all:
            to_replace = occurrences
        else:
            # Validate occurrence index
            if occurrence < 1 or occurrence > len(occurrences):
                valid_range = f"1 to {len(occurrences)}"
                msg = f"Invalid occurrence index {occurrence}. Valid range is {valid_range}."
                to_replace = []
            else:
                to_replace = [occurrences[occurrence-1]]
        
        if not to_replace:
            return content, []
            
        # Apply replacements
        new_content = content
        for pos_start, pos_end, line_num in reversed(to_replace):
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
        """Build and return file system tools."""
        # Initialize components
        self.backup_manager = BackupManager(self.workspace_folder)
        self.path_handler = PathHandler(self.workspace_folder)
        
        from langchain_core.tools import tool
        
        @tool
        def view_file(path: str, view_range: Optional[List[int]] = None) -> str:
            """View file contents with line numbers.
            
            Args:
                path: Path to the file relative to workspace
                view_range: Optional [start_line, end_line] to view specific lines (use -1 for end of file)
                
            Returns:
                File contents with line numbers
            """
            try:
                resolved_path = self.path_handler.resolve_path(path)
                
                # Check if file is empty
                if os.path.getsize(resolved_path) == 0:
                    return f"File is empty: {path}"
                
                with open(resolved_path, 'r', encoding='utf-8') as f:
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
                return f"Error viewing file: {str(e)}"
        
        @tool
        def edit_text(
            path: str, 
            old_str: str, 
            new_str: str, 
            use_regex: bool = False,
            replace_all: bool = False,
            context_before: Optional[str] = None,
            context_after: Optional[str] = None,
            line_number: Optional[int] = None,
            occurrence: int = 1,
            dry_run: bool = False
        ) -> str:
            """Replace text in a file with enhanced targeting options.
            
            Args:
                path: Path to the file relative to workspace
                old_str: Text or regex pattern to search for
                new_str: Text to replace with
                use_regex: Whether to interpret old_str as a regular expression
                replace_all: If True, replace all occurrences
                context_before: Text that must appear before the replacement
                context_after: Text that must appear after the replacement
                line_number: Line number to narrow search
                occurrence: Which occurrence to replace (1-based, ignored if replace_all=True)
                dry_run: If True, only show what would change without making changes
                
            Returns:
                Result of the operation with preview of changed content
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
                dry_run=dry_run
            )
        
        @tool
        def insert_at_line(path: str, line_number: int, new_str: str, dry_run: bool = False) -> str:
            """Insert text at a specific line number in a file.
            
            Args:
                path: Path to the file relative to workspace
                line_number: Line number where to insert text (1-based). For empty files, use line 1.
                new_str: Text to insert
                dry_run: If True, only show what would change without making changes
                
            Returns:
                Result of the operation with preview of changed content
            """
            return self._edit_file(
                path=path,
                operation=FileEditOperation.INSERT,
                replacement=new_str,
                line_number=line_number,
                dry_run=dry_run
            )
        
        @tool
        def remove_lines(path: str, start_line: int, end_line: int, dry_run: bool = False) -> str:
            """Remove a range of lines from a file.
            
            Args:
                path: Path to the file relative to workspace
                start_line: First line to remove (1-based)
                end_line: Last line to remove (1-based)
                dry_run: If True, only show what would change without making changes
                
            Returns:
                Result of the operation with preview
            """
            return self._edit_file(
                path=path,
                operation=FileEditOperation.REMOVE,
                line_number=start_line,
                end_line=end_line,
                dry_run=dry_run
            )
        
        @tool
        def move_code_block(path: str, start_line: int, end_line: int, target_line: int, dry_run: bool = False) -> str:
            """Move a block of code from one location to another in the same file.
            
            Args:
                path: Path to the file relative to workspace
                start_line: First line of block to move (1-based)
                end_line: Last line of block to move (1-based)
                target_line: Line number where to insert the block (1-based)
                dry_run: If True, only show what would change without making changes
                
            Returns:
                Result of the operation with preview
            """
            return self._edit_file(
                path=path,
                operation=FileEditOperation.MOVE,
                line_number=start_line,
                end_line=end_line,
                target_line=target_line,
                dry_run=dry_run
            )
        
        @tool
        def undo_edit(path: str) -> str:
            """Undo the last edit made to a file.
            
            Args:
                path: Path to the file relative to workspace
                
            Returns:
                Result of the operation with preview of the previous version
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
                    result += f"Restored to version {info['position']+1} of {info['count']}.\n"
                    if info["can_undo"]:
                        result += f"You can undo {info['count'] - info['position'] - 1} more time(s).\n"
                    if info["can_redo"]:
                        result += "You can redo this operation.\n"
                
                result += f"\nPreview:\n{file_preview}"
                return result
                
            except Exception as e:
                return f"Error undoing edit: {str(e)}"
        
        @tool
        def redo_edit(path: str) -> str:
            """Redo a previously undone edit to a file.
            
            Args:
                path: Path to the file relative to workspace
                
            Returns:
                Result of the operation with preview of the newer version
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
                    result += f"Restored to version {info['position']+1} of {info['count']}.\n"
                    if info["can_undo"]:
                        result += "You can undo this operation.\n"
                    if info["can_redo"]:
                        result += f"You can redo {info['position']} more time(s).\n"
                
                result += f"\nPreview:\n{file_preview}"
                return result
                
            except Exception as e:
                return f"Error redoing edit: {str(e)}"
        
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
                resolved_path = self.path_handler.resolve_path(path, must_exist=False)
                
                # Create directories if they don't exist
                os.makedirs(os.path.dirname(os.path.abspath(resolved_path)), exist_ok=True)
                
                # Check if file exists
                action = "Created"
                if os.path.exists(resolved_path):
                    self.backup_manager.backup_file(resolved_path)
                    action = "Updated"
                
                with open(resolved_path, 'w', encoding='utf-8') as f:
                    f.write(file_text)
                
                # Get preview
                file_preview = self._get_file_preview(path)
                return f"Successfully {action} file: {path}\n\nPreview:\n{file_preview}"
                
            except Exception as e:
                return f"Error creating file: {str(e)}"
        
        @tool
        def list_directory(directory_path: str = ".") -> str:
            """Get detailed listing of files and directories.
            
            Args:
                directory_path: Path to the directory relative to workspace (default: workspace root)
                
            Returns:
                Listing of files and directories with details
            """
            try:
                resolved_path = self.path_handler.resolve_path(directory_path)
                
                if not os.path.isdir(resolved_path):
                    return f"Error: Not a directory: {directory_path}"
                
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
                            size_str = f"{size/1024:.1f} KB"
                        if size > 1024*1024:
                            size_str = f"{size/(1024*1024):.1f} MB"
                        files.append((entry, "file", size_str))
                
                # Format and add to result
                for name, type_ in sorted(dirs):
                    result += f"📁 {name}/ ({type_})\n"
                for name, type_, size in sorted(files):
                    result += f"📄 {name} ({type_}, {size})\n"
                
                if not dirs and not files:
                    result += "Directory is empty."
                
                return result
                
            except Exception as e:
                return f"Error listing directory: {str(e)}"
        
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
                resolved_source = self.path_handler.resolve_path(source_path)
                resolved_dest = self.path_handler.resolve_path(destination_path, must_exist=False)
                
                # Create backup for the source if it's a file
                if os.path.isfile(resolved_source):
                    self.backup_manager.backup_file(resolved_source)
                
                # Create backup for the destination if it exists and is a file
                if os.path.isfile(resolved_dest) and os.path.exists(resolved_dest):
                    self.backup_manager.backup_file(resolved_dest)
                
                # Create destination directory if it doesn't exist
                dest_dir = os.path.dirname(resolved_dest)
                os.makedirs(dest_dir, exist_ok=True)
                
                # Move/rename the file or directory
                shutil.move(resolved_source, resolved_dest)
                
                source_type = "directory" if os.path.isdir(resolved_dest) else "file"
                return f"Successfully moved {source_type} from {source_path} to {destination_path}"
                
            except Exception as e:
                return f"Error moving file: {str(e)}"
        
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
                resolved_path = self.path_handler.resolve_path(directory_path)
                
                if not os.path.isdir(resolved_path):
                    return f"Error: Not a directory: {directory_path}"
                
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
                return f"Error searching files: {str(e)}"
        
        @tool
        def search_code(search_pattern: str, file_pattern: str = "*", directory_path: str = ".") -> str:
            """Search for text/code patterns within file contents.
            
            Args:
                search_pattern: Text pattern to search for in file contents
                file_pattern: Filter for file types (e.g., "*.py" for Python files)
                directory_path: Path to the directory to search in (default: workspace root)
                
            Returns:
                Search results with file locations and line numbers
            """
            try:
                resolved_path = self.path_handler.resolve_path(directory_path)
                
                if not os.path.isdir(resolved_path):
                    return f"Error: Not a directory: {directory_path}"
                
                # Python-based search
                matches = []
                
                for root, dirs, files in os.walk(resolved_path):
                    for name in files:
                        if fnmatch.fnmatch(name, file_pattern):
                            file_path = os.path.join(root, name)
                            try:
                                with open(file_path, 'r', encoding='utf-8') as f:
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
                return f"Error searching code: {str(e)}"
        
        @tool
        def generate_patch(path: str, old_content: Optional[str] = None, new_content: Optional[str] = None) -> str:
            """Generate a unified diff patch from old and new content.
            
            Args:
                path: Path to the target file
                old_content: Original content (if None, reads from file)
                new_content: New content
                
            Returns:
                A unified diff patch
            """
            try:
                resolved_path = self.path_handler.resolve_path(path)
                
                # If old_content not provided, read from file
                if old_content is None:
                    with open(resolved_path, 'r', encoding='utf-8') as f:
                        old_content = f.read()
                
                # New content must be provided
                if new_content is None:
                    return "Error: New content must be provided"
                
                # Generate diff using difflib
                old_lines = old_content.splitlines()
                new_lines = new_content.splitlines()
                
                diff = difflib.unified_diff(
                    old_lines, 
                    new_lines,
                    lineterm='',
                    n=3
                )
                
                diff_text = '\n'.join(diff)
                return diff_text if diff_text else "No differences found."
                
            except Exception as e:
                return f"Error generating patch: {str(e)}"
        
        @tool
        def find_code_structure(path: str, item_type: str = "all") -> str:
            """Analyze a file to find code structure elements like functions, classes, methods.
            
            Args:
                path: Path to the file relative to workspace
                item_type: Type of items to find ("function", "class", "method", "all")
                
            Returns:
                Structured information about code elements with line ranges
            """
            try:
                resolved_path = self.path_handler.resolve_path(path)
                
                # Check file existence first
                if not os.path.exists(resolved_path):
                    return f"Error: File not found: {path}"
                
                # Check file size, handle empty files gracefully
                if os.path.getsize(resolved_path) == 0:
                    return f"File {path} is empty."
                
                # Only supporting Python files for now
                file_ext = os.path.splitext(resolved_path)[1].lower()
                if file_ext != '.py':
                    return f"Note: Code structure analysis is currently only supported for Python (.py) files. File {path} has extension {file_ext}."
                
                # Read file content
                with open(resolved_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Parse the Python code
                try:
                    tree = ast.parse(content)
                except SyntaxError as e:
                    return f"Error: Could not parse {path} - syntax error at line {e.lineno}, column {e.offset}: {e.msg}"
                
                # Helper function to extract line range for a node
                def get_line_range(node):
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
                    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and not hasattr(node, "parent_class")]
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
                            cls_start, cls_end = get_line_range(cls)
                            result += f"- {cls.name} (lines {cls_start}-{cls_end})\n"
                            
                            if item_type in ["method", "all"]:
                                methods = [node for node in ast.walk(cls) if isinstance(node, ast.FunctionDef)]
                                for method in methods:
                                    method.parent_class = cls.name  # Mark as a method
                                    method_start, method_end = get_line_range(method)
                                    result += f"  - {method.name} (lines {method_start}-{method_end})\n"
                        result += "\n"
                
                # Check if we found anything
                if not has_content:
                    result += f"No {item_type} items found in {path}."
                
                return result
                
            except Exception as e:
                return f"Error analyzing code structure: {str(e)}"
        
        # Return all tools
        return [
            view_file,
            edit_text,
            insert_at_line,
            remove_lines,
            move_code_block,
            undo_edit,
            redo_edit,
            create_file,
            list_directory,
            move_file,
            search_files,
            search_code,
            generate_patch,
            find_code_structure
        ]
