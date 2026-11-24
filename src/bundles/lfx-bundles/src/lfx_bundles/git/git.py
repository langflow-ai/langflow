import ntpath
import os
import re
import stat
import tempfile
from contextlib import ExitStack, asynccontextmanager
from fnmatch import fnmatch
from pathlib import Path

import anyio
from langchain_community.document_loaders.git import GitLoader
from langchain_core.documents import Document
from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, MessageTextInput, Output
from lfx.schema.data import Data
from lfx.utils.file_path_security import enforce_local_file_access
from lfx.utils.ssrf_protection import validate_git_repository_url

_IS_WINDOWS = os.name == "nt"


def _require_secure_path_opens() -> None:
    if _IS_WINDOWS:
        return
    if not (hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY") and os.open in os.supports_dir_fd):
        msg = "Secure Git working-tree reads are not supported on this platform."
        raise NotImplementedError(msg)


def _windows_path_is_within_root(file_path: str, repository_root: str) -> bool:
    def normalize(path: str) -> str:
        if path.startswith("\\\\?\\UNC\\"):
            path = "\\\\" + path[8:]
        elif path.startswith("\\\\?\\"):
            path = path[4:]
        return ntpath.normcase(ntpath.normpath(path))

    normalized_root = normalize(repository_root)
    try:
        return ntpath.commonpath([normalized_root, normalize(file_path)]) == normalized_root
    except ValueError:
        return False


def _get_windows_final_path(handle: int) -> str:
    import ctypes
    from ctypes import wintypes

    get_final_path = ctypes.WinDLL("kernel32", use_last_error=True).GetFinalPathNameByHandleW
    get_final_path.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
    get_final_path.restype = wintypes.DWORD
    buffer = ctypes.create_unicode_buffer(32768)
    length = get_final_path(handle, buffer, len(buffer), 0)
    if length == 0 or length >= len(buffer):
        msg = "Could not validate the Git working-tree file handle."
        raise PermissionError(msg)
    return buffer.value


def _read_file_bytes_windows(file_path: Path, *, repository_root: Path, limit: int = -1) -> bytes:
    import msvcrt

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    with os.fdopen(os.open(file_path, flags), "rb") as file:
        handle_path = _get_windows_final_path(msvcrt.get_osfhandle(file.fileno()))
        if not _windows_path_is_within_root(handle_path, str(repository_root)):
            msg = "Git working-tree file handle resolved outside the repository."
            raise PermissionError(msg)
        if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
            msg = "Git working-tree paths must refer to regular files."
            raise PermissionError(msg)
        return file.read(limit)


def _read_file_bytes_posix(file_path: Path, *, repository_root: Path, limit: int = -1) -> bytes:
    _require_secure_path_opens()
    file_path.relative_to(repository_root)
    # Pin every directory from the filesystem root. O_NOFOLLOW on only the
    # final file leaves parent-directory swaps able to redirect the read.
    with ExitStack() as stack:
        directory_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY
        directory_fd = os.open(file_path.anchor, directory_flags)
        stack.callback(os.close, directory_fd)
        for part in file_path.parts[1:-1]:
            directory_fd = os.open(part, directory_flags, dir_fd=directory_fd)
            stack.callback(os.close, directory_fd)
        file_fd = os.open(file_path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
        with os.fdopen(file_fd, "rb") as file:
            if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
                msg = "Git working-tree paths must refer to regular files."
                raise PermissionError(msg)
            return file.read(limit)


def _read_file_bytes(file_path: str, *, repository_root: Path | None = None, limit: int = -1) -> bytes:
    if repository_root is None:
        with Path(file_path).open("rb") as file:
            return file.read(limit)
    path = Path(file_path).absolute()
    if ".." in path.parts:
        msg = "Parent traversal is not permitted in Git working-tree paths."
        raise PermissionError(msg)
    path.relative_to(repository_root)
    read_file = _read_file_bytes_windows if _IS_WINDOWS else _read_file_bytes_posix
    return read_file(path, repository_root=repository_root, limit=limit)


_GIT_SYMLINK_MODE = 0o120000


class _RepositoryGitLoader(GitLoader):
    """Read working-tree files without following symlinks swapped in after filtering."""

    def lazy_load(self):
        from git import Blob, Repo

        _require_secure_path_opens()
        if not Path(self.repo_path).exists() and self.clone_url is None:
            msg = f"Path {self.repo_path} does not exist"
            raise ValueError(msg)
        if self.clone_url:
            if Path(self.repo_path, ".git").is_dir():
                repo = Repo(self.repo_path)
                if repo.remotes.origin.url != self.clone_url:
                    msg = "A different repository is already cloned at this path."
                    raise ValueError(msg)
            else:
                repo = Repo.clone_from(self.clone_url, self.repo_path)
            repo.git.checkout(self.branch)
        else:
            repo = Repo(self.repo_path)
            repo.git.checkout(self.branch)

        for item in repo.tree().traverse():
            if not isinstance(item, Blob) or item.mode == _GIT_SYMLINK_MODE:
                continue

            file_path = str(Path(self.repo_path) / item.path)
            if repo.ignored([file_path]):
                continue
            if self.file_filter and not self.file_filter(file_path):
                continue

            rel_file_path = os.path.relpath(file_path, self.repo_path)
            try:
                content = _read_file_bytes(file_path, repository_root=Path(self.repo_path))
                try:
                    text_content = content.decode("utf-8")
                except UnicodeDecodeError:
                    continue

                metadata = {
                    "source": rel_file_path,
                    "file_path": rel_file_path,
                    "file_name": item.name,
                    "file_type": Path(item.name).suffix,
                }
                yield Document(page_content=text_content, metadata=metadata)
            except Exception as e:  # noqa: BLE001
                print(f"Error reading file {file_path}: {e}")  # noqa: T201


class GitLoaderComponent(Component):
    display_name = "Git"
    description = (
        "Load and filter documents from a local or remote Git repository. "
        "Use a local repo path or clone from a remote URL."
    )
    trace_type = "tool"
    icon = "GitLoader"

    inputs = [
        DropdownInput(
            name="repo_source",
            display_name="Repository Source",
            options=["Local", "Remote"],
            required=True,
            info="Select whether to use a local repo path or clone from a remote URL.",
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="repo_path",
            display_name="Local Repository Path",
            required=False,
            info="The local path to the existing Git repository (used if 'Local' is selected).",
            dynamic=True,
            show=False,
        ),
        MessageTextInput(
            name="clone_url",
            display_name="Clone URL",
            required=False,
            info="The URL of the Git repository to clone (used if 'Clone' is selected).",
            dynamic=True,
            show=False,
        ),
        MessageTextInput(
            name="branch",
            display_name="Branch",
            required=False,
            value="main",
            info="The branch to load files from. Defaults to 'main'.",
        ),
        MessageTextInput(
            name="file_filter",
            display_name="File Filter",
            required=False,
            advanced=True,
            info=(
                "Patterns to filter files. For example:\n"
                "Include only .py files: '*.py'\n"
                "Exclude .py files: '!*.py'\n"
                "Multiple patterns can be separated by commas."
            ),
        ),
        MessageTextInput(
            name="content_filter",
            display_name="Content Filter",
            required=False,
            advanced=True,
            info="A regex pattern to filter files based on their content.",
        ),
    ]

    outputs = [
        Output(name="data", display_name="JSON", method="load_documents"),
    ]

    @staticmethod
    def is_binary(file_path: str | Path, *, repository_root: Path | None = None) -> bool:
        """Check if a file is binary by looking for null bytes."""
        try:
            return b"\x00" in _read_file_bytes(str(file_path), repository_root=repository_root, limit=1024)
        except Exception:  # noqa: BLE001
            return True

    @staticmethod
    def check_file_patterns(file_path: str | Path, patterns: str) -> bool:
        """Check if a file matches the given patterns.

        Args:
            file_path: Path to the file to check
            patterns: Comma-separated list of glob patterns

        Returns:
            bool: True if file should be included, False if excluded
        """
        # Handle empty or whitespace-only patterns
        if not patterns or patterns.isspace():
            return True

        path_str = str(file_path)
        file_name = Path(path_str).name
        pattern_list: list[str] = [pattern.strip() for pattern in patterns.split(",") if pattern.strip()]

        # If no valid patterns after stripping, treat as include all
        if not pattern_list:
            return True

        # Process exclusion patterns first
        for pattern in pattern_list:
            if pattern.startswith("!"):
                # For exclusions, match against both full path and filename
                exclude_pattern = pattern[1:]
                if fnmatch(path_str, exclude_pattern) or fnmatch(file_name, exclude_pattern):
                    return False

        # Then check inclusion patterns
        include_patterns = [p for p in pattern_list if not p.startswith("!")]
        # If no include patterns, treat as include all
        if not include_patterns:
            return True

        # For inclusions, match against both full path and filename
        return any(fnmatch(path_str, pattern) or fnmatch(file_name, pattern) for pattern in include_patterns)

    @staticmethod
    def check_content_pattern(file_path: str | Path, pattern: str, *, repository_root: Path | None = None) -> bool:
        """Check if file content matches the given regex pattern.

        Args:
            file_path: Path to the file to check
            pattern: Regex pattern to match against content
            repository_root: Canonical repository root for confined working-tree reads

        Returns:
            bool: True if content matches, False otherwise
        """
        try:
            # Check if file is binary
            content = _read_file_bytes(str(file_path), repository_root=repository_root)
            if b"\x00" in content[:1024]:
                return False

            # Try to compile the regex pattern first
            try:
                # Use the MULTILINE flag to better handle text content
                content_regex = re.compile(pattern, re.MULTILINE)
                # Test the pattern with a simple string to catch syntax errors
                test_str = "test\nstring"
                if not content_regex.search(test_str):
                    # Pattern is valid but doesn't match test string
                    pass
            except (re.error, TypeError, ValueError):
                return False

            # If not binary and regex is valid, check content
            file_content = content.decode("utf-8")
            return bool(content_regex.search(file_content))
        except (OSError, UnicodeDecodeError):
            return False

    def build_combined_filter(
        self,
        file_filter_patterns: str | None = None,
        content_filter_pattern: str | None = None,
        repo_path: str | Path | None = None,
    ):
        """Build a combined filter function from file and content patterns.

        Args:
            file_filter_patterns: Comma-separated glob patterns
            content_filter_pattern: Regex pattern for content
            repo_path: Repository directory that files must remain inside

        Returns:
            callable: Filter function that takes a file path and returns bool
        """
        repository_root = Path(repo_path).resolve() if repo_path is not None else None

        def combined_filter(file_path: str) -> bool:
            try:
                path = Path(file_path)
                if path.is_symlink():
                    return False
                if repository_root is not None:
                    path.resolve().relative_to(repository_root)

                # Check if file exists and is readable
                if not path.exists():
                    return False

                # Check if file is binary
                if self.is_binary(path, repository_root=repository_root):
                    return False

                # Apply file pattern filters
                if file_filter_patterns and not self.check_file_patterns(path, file_filter_patterns):
                    return False

                # Apply content filter
                return not (
                    content_filter_pattern
                    and not self.check_content_pattern(path, content_filter_pattern, repository_root=repository_root)
                )
            except Exception:  # noqa: BLE001
                return False

        return combined_filter

    @asynccontextmanager
    async def temp_clone_dir(self):
        """Context manager for handling temporary clone directory."""
        temp_dir = None
        try:
            temp_dir = tempfile.mkdtemp(prefix="langflow_clone_")
            yield temp_dir
        finally:
            if temp_dir:
                await anyio.Path(temp_dir).rmdir()

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        # Hide fields by default
        build_config["repo_path"]["show"] = False
        build_config["clone_url"]["show"] = False

        if field_name == "repo_source":
            if field_value == "Local":
                build_config["repo_path"]["show"] = True
                build_config["repo_path"]["required"] = True
                build_config["clone_url"]["required"] = False
            elif field_value == "Remote":
                build_config["clone_url"]["show"] = True
                build_config["clone_url"]["required"] = True
                build_config["repo_path"]["required"] = False

        return build_config

    async def build_gitloader(self) -> GitLoader:
        file_filter_patterns = getattr(self, "file_filter", None)
        content_filter_pattern = getattr(self, "content_filter", None)

        repo_source = getattr(self, "repo_source", None)
        if repo_source == "Local":
            # repo_path is tenant-controlled and its file contents are read back: confine to the
            # storage dir when LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS is enabled (multi-tenant).
            repo_path = str(enforce_local_file_access(self.repo_path).resolve())
            clone_url = None
        else:
            # Clone source. The URL is tenant-controlled: block ext::/fd:: remote helpers
            # (RCE), file:// / local paths (arbitrary file read), and SSRF-blocked hosts.
            clone_url = self.clone_url
            validate_git_repository_url(clone_url)
            async with self.temp_clone_dir() as temp_dir:
                repo_path = str(Path(temp_dir).resolve())

        combined_filter = self.build_combined_filter(file_filter_patterns, content_filter_pattern, repo_path)

        # Only pass branch if it's explicitly set
        branch = getattr(self, "branch", None)
        if not branch:
            branch = None

        return _RepositoryGitLoader(
            repo_path=repo_path,
            clone_url=clone_url if repo_source == "Remote" else None,
            branch=branch,
            file_filter=combined_filter,
        )

    async def load_documents(self) -> list[Data]:
        gitloader = await self.build_gitloader()
        data = [Data.from_document(doc) async for doc in gitloader.alazy_load()]
        self.status = data
        return data
