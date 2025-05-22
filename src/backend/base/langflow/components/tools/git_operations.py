from langchain_core.tools import tool
import os
import subprocess
from typing import List, Optional

from langflow.custom import Component
from langflow.field_typing import Tool
from langflow.io import StrInput, Output, BoolInput


class GitOperations(Component):
    display_name = "Git Operations"
    description = "Advanced Git operations system for repository management with commit, branch, and clone capabilities"
    icon = "Git"
    name = "GitOperations"
    
    inputs = [
        StrInput(
            name="workspace_folder",
            display_name="Workspace Folder",
            info="Base working directory for all Git operations. All paths will be relative to this folder.",
            required=True,
        ),
        BoolInput(
            name="create_if_missing",
            display_name="Create Workspace If Missing",
            info="Create the workspace folder if it doesn't exist",
            value=True,
        ),
    ]
    
    outputs = [
        Output(name="tools", display_name="Tools", method="build_toolkit"),
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.command_history = []  # Track executed Git commands
    
    def _resolve_path(self, relative_path: str) -> str:
        """Resolve a relative path to absolute path within workspace."""
        if os.path.isabs(relative_path):
            raise ValueError(f"Path must be relative to workspace: {relative_path}")
        full_path = os.path.normpath(os.path.join(self.workspace_folder, relative_path))
        if not full_path.startswith(os.path.abspath(self.workspace_folder)):
            raise ValueError(f"Path must be within workspace: {relative_path}")
        return full_path
    
    def _run_git_command(self, command: List[str], repo_path: str = "") -> str:
        try:
            work_dir = self.workspace_folder
            if repo_path:
                work_dir = self._resolve_path(repo_path)
            if self.create_if_missing and not os.path.exists(self.workspace_folder):
                os.makedirs(self.workspace_folder, exist_ok=True)
            full_command = ["git"] + command
            self.command_history.append(f"git {' '.join(command)}")
            process = subprocess.run(
                full_command,
                cwd=work_dir,
                capture_output=True,
                text=True,
                check=False
            )
            if process.returncode != 0:
                error_message = process.stderr.strip()
                return f"Error executing git command:\n{error_message}"
            output = process.stdout.strip()
            if output:
                return output
            return "Command executed successfully."
        except Exception as e:
            return f"Error executing git command: {str(e)}"
    
    def _is_git_repo(self, repo_path: str = "") -> bool:
        try:
            work_dir = self.workspace_folder
            if repo_path:
                work_dir = self._resolve_path(repo_path)
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=work_dir,
                capture_output=True,
                text=True,
                check=False
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def build_toolkit(self) -> Tool:
        @tool
        def git_init(directory_path: str = ".") -> str:
            repo_path = self._resolve_path(directory_path)
            if not os.path.exists(repo_path):
                os.makedirs(repo_path, exist_ok=True)
            if self._is_git_repo(directory_path):
                return f"Directory is already a Git repository: {directory_path}"
            return self._run_git_command(["init"], directory_path)
        
        @tool
        def git_status(repo_path: str = ".") -> str:
            if not self._is_git_repo(repo_path):
                return f"Error: Not a Git repository: {repo_path}"
            return self._run_git_command(["status"], repo_path)
        
        @tool
        def git_add(paths: List[str] = None, all_files: bool = False, repo_path: str = ".") -> str:
            if not self._is_git_repo(repo_path):
                return f"Error: Not a Git repository: {repo_path}"
            if all_files:
                return self._run_git_command(["add", "."], repo_path)
            elif paths:
                return self._run_git_command(["add"] + paths, repo_path)
            else:
                return "Error: Either specify paths or set all_files=True"
        
        @tool
        def git_commit(message: str, repo_path: str = ".") -> str:
            if not self._is_git_repo(repo_path):
                return f"Error: Not a Git repository: {repo_path}"
            user_email = subprocess.run(
                ["git", "config", "user.email"],
                cwd=self._resolve_path(repo_path),
                capture_output=True,
                text=True,
                check=False
            )
            user_name = subprocess.run(
                ["git", "config", "user.name"],
                cwd=self._resolve_path(repo_path),
                capture_output=True,
                text=True,
                check=False
            )
            if not user_email.stdout.strip():
                self._run_git_command(["config", "user.email", "agent@example.com"], repo_path)
            if not user_name.stdout.strip():
                self._run_git_command(["config", "user.name", "AI Agent"], repo_path)
            return self._run_git_command(["commit", "-m", message], repo_path)
        
        @tool
        def git_clone(repository_url: str, directory_path: Optional[str] = None, depth: Optional[int] = None) -> str:
            command = ["clone"]
            if depth is not None:
                command.extend(["--depth", str(depth)])
            command.append(repository_url)
            if directory_path:
                target_path = self._resolve_path(directory_path)
                command.append(directory_path)
            return self._run_git_command(command)
        
        @tool
        def git_pull(repo_path: str = ".", remote: str = "origin", branch: Optional[str] = None) -> str:
            if not self._is_git_repo(repo_path):
                return f"Error: Not a Git repository: {repo_path}"
            command = ["pull", remote]
            if branch:
                command.append(branch)
            return self._run_git_command(command, repo_path)
        
        @tool
        def git_push(repo_path: str = ".", remote: str = "origin", branch: Optional[str] = None) -> str:
            if not self._is_git_repo(repo_path):
                return f"Error: Not a Git repository: {repo_path}"
            command = ["push", remote]
            if branch:
                command.append(branch)
            return self._run_git_command(command, repo_path)
        
        @tool
        def git_branch(new_branch: Optional[str] = None, list_branches: bool = False, repo_path: str = ".") -> str:
            if not self._is_git_repo(repo_path):
                return f"Error: Not a Git repository: {repo_path}"
            if list_branches:
                return self._run_git_command(["branch"], repo_path)
            elif new_branch:
                return self._run_git_command(["branch", new_branch], repo_path)
            else:
                return "Error: Either specify a new branch name or set list_branches=True"
        
        @tool
        def git_checkout(branch_name: str, repo_path: str = ".", create_branch: bool = False) -> str:
            if not self._is_git_repo(repo_path):
                return f"Error: Not a Git repository: {repo_path}"
            command = ["checkout"]
            if create_branch:
                command.append("-b")
            command.append(branch_name)
            return self._run_git_command(command, repo_path)
        
        @tool
        def git_merge(source_branch: str, repo_path: str = ".", commit_message: Optional[str] = None) -> str:
            if not self._is_git_repo(repo_path):
                return f"Error: Not a Git repository: {repo_path}"
            command = ["merge"]
            if commit_message:
                command.extend(["-m", commit_message])
            command.append(source_branch)
            result = self._run_git_command(command, repo_path)
            if "CONFLICT" in result or "Automatic merge failed" in result:
                return f"Merge conflict detected:\n{result}\nResolve conflicts manually and commit the result."
            return result
        
        @tool
        def git_log(max_count: Optional[int] = None, repo_path: str = ".", pretty_format: str = "oneline") -> str:
            if not self._is_git_repo(repo_path):
                return f"Error: Not a Git repository: {repo_path}"
            command = ["log", f"--pretty={pretty_format}"]
            if max_count is not None:
                command.extend(["-n", str(max_count)])
            return self._run_git_command(command, repo_path)
        
        @tool
        def git_diff(files: List[str] = None, staged: bool = False, repo_path: str = ".") -> str:
            if not self._is_git_repo(repo_path):
                return f"Error: Not a Git repository: {repo_path}"
            command = ["diff"]
            if staged:
                command.append("--staged")
            if files:
                command.extend(files)
            return self._run_git_command(command, repo_path)
        
        @tool
        def git_remote(operation: str = "show", remote_name: Optional[str] = None, 
                       remote_url: Optional[str] = None, repo_path: str = ".") -> str:
            if not self._is_git_repo(repo_path):
                return f"Error: Not a Git repository: {repo_path}"
            if operation == "show":
                command = ["remote", "-v"]
            elif operation == "add":
                if not remote_name or not remote_url:
                    return "Error: Both remote_name and remote_url are required for 'add' operation"
                command = ["remote", "add", remote_name, remote_url]
            elif operation == "remove":
                if not remote_name:
                    return "Error: remote_name is required for 'remove' operation"
                command = ["remote", "remove", remote_name]
            else:
                return f"Error: Unsupported operation: {operation}"
            return self._run_git_command(command, repo_path)
        
        @tool
        def git_reset(file_paths: List[str] = None, mode: str = "mixed", 
                      commit: str = "HEAD", repo_path: str = ".") -> str:
            if not self._is_git_repo(repo_path):
                return f"Error: Not a Git repository: {repo_path}"
            valid_modes = ["soft", "mixed", "hard"]
            if mode not in valid_modes:
                return f"Error: Invalid mode '{mode}'. Must be one of {valid_modes}"
            command = ["reset"]
            if mode != "mixed":
                command.append(f"--{mode}")
            command.append(commit)
            if file_paths:
                command.extend(["--"] + file_paths)
            return self._run_git_command(command, repo_path)
        
        @tool
        def git_config(key: str, value: Optional[str] = None, 
                       global_config: bool = False, repo_path: str = ".") -> str:
            command = ["config"]
            if global_config:
                command.append("--global")
            command.append(key)
            if value is not None:
                command.append(value)
            return self._run_git_command(command, repo_path)
        
        @tool
        def git_command_history() -> str:
            if not self.command_history:
                return "No Git commands have been executed yet."
            history = "\n".join([f"{i+1}. {cmd}" for i, cmd in enumerate(self.command_history)])
            return f"Git Command History:\n{history}"
        
        return [
            git_init,
            git_status,
            git_add,
            git_commit,
            git_clone,
            git_pull,
            git_push,
            git_branch,
            git_checkout,
            git_merge,
            git_log,
            git_diff,
            git_remote,
            git_reset,
            git_config,
            git_command_history
        ]
