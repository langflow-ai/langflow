import os
import subprocess

from langchain_core.tools import tool

from langflow.custom import Component
from langflow.field_typing import Tool
from langflow.io import BoolInput, Output, StrInput


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

    def _run_git_command(self, command: list[str], repo_path: str = "") -> str:
        try:
            work_dir = self.workspace_folder
            if repo_path:
                work_dir = self._resolve_path(repo_path)
            if self.create_if_missing and not os.path.exists(self.workspace_folder):
                os.makedirs(self.workspace_folder, exist_ok=True)
            full_command = ["git"] + command
            self.command_history.append(f"git {' '.join(command)}")
            process = subprocess.run(full_command, cwd=work_dir, capture_output=True, text=True, check=False)
            if process.returncode != 0:
                error_message = process.stderr.strip()
                return f"Error executing git command:\n{error_message}"
            output = process.stdout.strip()
            if output:
                return output
            return "Command executed successfully."
        except Exception as e:
            return f"Error executing git command: {e!s}"

    def _is_git_repo(self, repo_path: str = "") -> bool:
        try:
            work_dir = self.workspace_folder
            if repo_path:
                work_dir = self._resolve_path(repo_path)
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"], cwd=work_dir, capture_output=True, text=True, check=False
            )
            return result.returncode == 0
        except Exception:
            return False

    def build_toolkit(self) -> Tool:
        @tool
        def git_init(directory_path: str = ".") -> str:
            """Initialize a new Git repository.

            Args:
                directory_path: Path to directory relative to workspace (default: workspace root)

            Returns:
                Result of the operation
            """
            repo_path = self._resolve_path(directory_path)
            if not os.path.exists(repo_path):
                os.makedirs(repo_path, exist_ok=True)
            if self._is_git_repo(directory_path):
                return f"Directory is already a Git repository: {directory_path}"
            return self._run_git_command(["init"], directory_path)

        @tool
        def git_status(repo_path: str = ".") -> str:
            """Show the working tree status.

            Args:
                repo_path: Path to repository relative to workspace (default: workspace root)

            Returns:
                Git status output
            """
            if not self._is_git_repo(repo_path):
                return f"Error: Not a Git repository: {repo_path}"
            return self._run_git_command(["status"], repo_path)

        @tool
        def git_add(paths: list[str] = None, all_files: bool = False, repo_path: str = ".") -> str:
            """Add file contents to the index.

            Args:
                paths: List of file paths to add (relative to repo)
                all_files: If True, add all files (equivalent to git add .)
                repo_path: Path to repository relative to workspace (default: workspace root)

            Returns:
                Result of the operation
            """
            if not self._is_git_repo(repo_path):
                return f"Error: Not a Git repository: {repo_path}"
            if all_files:
                return self._run_git_command(["add", "."], repo_path)
            if paths:
                return self._run_git_command(["add"] + paths, repo_path)
            return "Error: Either specify paths or set all_files=True"

        @tool
        def git_commit(message: str, repo_path: str = ".") -> str:
            """Record changes to the repository.

            Args:
                message: Commit message
                repo_path: Path to repository relative to workspace (default: workspace root)

            Returns:
                Result of the operation
            """
            if not self._is_git_repo(repo_path):
                return f"Error: Not a Git repository: {repo_path}"
            user_email = subprocess.run(
                ["git", "config", "user.email"],
                cwd=self._resolve_path(repo_path),
                capture_output=True,
                text=True,
                check=False,
            )
            user_name = subprocess.run(
                ["git", "config", "user.name"],
                cwd=self._resolve_path(repo_path),
                capture_output=True,
                text=True,
                check=False,
            )
            if not user_email.stdout.strip():
                self._run_git_command(["config", "user.email", "agent@example.com"], repo_path)
            if not user_name.stdout.strip():
                self._run_git_command(["config", "user.name", "AI Agent"], repo_path)
            return self._run_git_command(["commit", "-m", message], repo_path)

        @tool
        def git_clone(repository_url: str, directory_path: str | None = None, depth: int | None = None) -> str:
            """Clone a repository into a new directory.

            Args:
                repository_url: URL of the repository to clone
                directory_path: Directory to clone into (relative to workspace)
                depth: Create a shallow clone with the specified depth

            Returns:
                Result of the operation
            """
            command = ["clone"]
            if depth is not None:
                command.extend(["--depth", str(depth)])
            command.append(repository_url)
            if directory_path:
                target_path = self._resolve_path(directory_path)
                command.append(directory_path)
            return self._run_git_command(command)

        @tool
        def git_pull(repo_path: str = ".", remote: str = "origin", branch: str | None = None) -> str:
            """Fetch from and integrate with another repository or a local branch.

            Args:
                repo_path: Path to repository relative to workspace (default: workspace root)
                remote: Remote repository name
                branch: Branch name to pull (default: current branch)

            Returns:
                Result of the operation
            """
            if not self._is_git_repo(repo_path):
                return f"Error: Not a Git repository: {repo_path}"
            command = ["pull", remote]
            if branch:
                command.append(branch)
            return self._run_git_command(command, repo_path)

        @tool
        def git_push(repo_path: str = ".", remote: str = "origin", branch: str | None = None) -> str:
            """Update remote refs along with associated objects.

            Args:
                repo_path: Path to repository relative to workspace (default: workspace root)
                remote: Remote repository name
                branch: Branch name to push (default: current branch)

            Returns:
                Result of the operation
            """
            if not self._is_git_repo(repo_path):
                return f"Error: Not a Git repository: {repo_path}"
            command = ["push", remote]
            if branch:
                command.append(branch)
            return self._run_git_command(command, repo_path)

        @tool
        def git_branch(new_branch: str | None = None, list_branches: bool = False, repo_path: str = ".") -> str:
            """List, create, or delete branches.

            Args:
                new_branch: Create a new branch with this name
                list_branches: List all branches if True
                repo_path: Path to repository relative to workspace (default: workspace root)

            Returns:
                Result of the operation
            """
            if not self._is_git_repo(repo_path):
                return f"Error: Not a Git repository: {repo_path}"
            if list_branches:
                return self._run_git_command(["branch"], repo_path)
            if new_branch:
                return self._run_git_command(["branch", new_branch], repo_path)
            return "Error: Either specify a new branch name or set list_branches=True"

        @tool
        def git_checkout(branch_name: str, repo_path: str = ".", create_branch: bool = False) -> str:
            """Switch branches or restore working tree files.

            Args:
                branch_name: Branch to checkout
                repo_path: Path to repository relative to workspace (default: workspace root)
                create_branch: Create branch if it doesn't exist (-b flag)

            Returns:
                Result of the operation
            """
            if not self._is_git_repo(repo_path):
                return f"Error: Not a Git repository: {repo_path}"
            command = ["checkout"]
            if create_branch:
                command.append("-b")
            command.append(branch_name)
            return self._run_git_command(command, repo_path)

        @tool
        def git_merge(source_branch: str, repo_path: str = ".", commit_message: str | None = None) -> str:
            """Merge a source branch into the current branch.

            Args:
                source_branch: The name of the branch whose changes are to be merged into the current branch
                repo_path: Path to repository relative to workspace (default: workspace root)
                commit_message: If a merge commit is created (not a fast-forward), use this message

            Returns:
                Result of the operation, including information about conflicts if they occur
            """
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
        def git_log(max_count: int | None = None, repo_path: str = ".", pretty_format: str = "oneline") -> str:
            """Show commit logs.

            Args:
                max_count: Limit the number of commits to show
                repo_path: Path to repository relative to workspace (default: workspace root)
                pretty_format: Format for displaying commits (oneline, short, medium, full, etc.)

            Returns:
                Git log output
            """
            if not self._is_git_repo(repo_path):
                return f"Error: Not a Git repository: {repo_path}"
            command = ["log", f"--pretty={pretty_format}"]
            if max_count is not None:
                command.extend(["-n", str(max_count)])
            return self._run_git_command(command, repo_path)

        @tool
        def git_diff(files: list[str] = None, staged: bool = False, repo_path: str = ".") -> str:
            """Show changes between commits, commit and working tree, etc.

            Args:
                files: List of files to show diff for
                staged: Show staged changes only
                repo_path: Path to repository relative to workspace (default: workspace root)

            Returns:
                Git diff output
            """
            if not self._is_git_repo(repo_path):
                return f"Error: Not a Git repository: {repo_path}"
            command = ["diff"]
            if staged:
                command.append("--staged")
            if files:
                command.extend(files)
            return self._run_git_command(command, repo_path)

        @tool
        def git_remote(
            operation: str = "show", remote_name: str | None = None, remote_url: str | None = None, repo_path: str = "."
        ) -> str:
            """Manage set of tracked repositories.

            Args:
                operation: Remote operation (show, add, remove)
                remote_name: Name of the remote
                remote_url: URL for the remote (needed for 'add' operation)
                repo_path: Path to repository relative to workspace (default: workspace root)

            Returns:
                Result of the operation
            """
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
        def git_reset(
            file_paths: list[str] = None, mode: str = "mixed", commit: str = "HEAD", repo_path: str = "."
        ) -> str:
            """Reset current HEAD to the specified state.

            Args:
                file_paths: List of file paths to reset
                mode: Reset mode (soft, mixed, hard)
                commit: Commit to reset to (default: HEAD)
                repo_path: Path to repository relative to workspace (default: workspace root)

            Returns:
                Result of the operation
            """
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
        def git_config(key: str, value: str | None = None, global_config: bool = False, repo_path: str = ".") -> str:
            """Get and set repository or global options.

            Args:
                key: Configuration key
                value: Configuration value (if setting)
                global_config: Use global config if True
                repo_path: Path to repository relative to workspace (default: workspace root)

            Returns:
                Result of the operation
            """
            command = ["config"]
            if global_config:
                command.append("--global")
            command.append(key)
            if value is not None:
                command.append(value)
            return self._run_git_command(command, repo_path)

        @tool
        def git_command_history() -> str:
            """View the history of executed Git commands.

            Returns:
                List of previously executed Git commands
            """
            if not self.command_history:
                return "No Git commands have been executed yet."
            history = "\n".join([f"{i + 1}. {cmd}" for i, cmd in enumerate(self.command_history)])
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
            git_command_history,
        ]
