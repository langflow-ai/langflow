"""Create immutable release tags without changing development work."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .constants import AUTH_SOURCE
from .preparation import prepare_release_source


def prepare_release_tag(repo: Path, tag: str, ref: str = "HEAD") -> str:
    """Create a release-only commit and tag, preserving branches and the index.

    The caller must push the returned tag explicitly. Existing tags are never
    moved; a retry is accepted only when the tag already names this release tree
    at the requested source commit or its single-parent release commit.
    """
    git_executable = shutil.which("git")
    if git_executable is None:
        msg = "Git is required to prepare a release tag"
        raise RuntimeError(msg)

    def git(*args: str, data: bytes | None = None, env: dict[str, str] | None = None) -> bytes:
        # Fixed Git subcommands; refs are validated and never passed to a shell.
        return subprocess.run(  # noqa: S603
            [git_executable, "-C", str(repo), *args], input=data, env=env, check=True, capture_output=True
        ).stdout

    if tag.startswith("-"):
        msg = "Release tag must not start with '-'"
        raise ValueError(msg)
    git("check-ref-format", f"refs/tags/{tag}")
    base = git("rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}").decode().strip()
    source = git("show", f"{base}:{AUTH_SOURCE.as_posix()}")
    prepared = prepare_release_source(source)
    blob = git("hash-object", "-w", "--stdin", data=prepared).decode().strip()
    mode = git("ls-tree", base, "--", AUTH_SOURCE.as_posix()).decode().split()[0]
    with tempfile.TemporaryDirectory(prefix="langflow-release-index-") as directory:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(directory) / "index")}
        git("read-tree", base, env=env)
        git("update-index", "--add", "--cacheinfo", f"{mode},{blob},{AUTH_SOURCE.as_posix()}", env=env)
        tree = git("write-tree", env=env).decode().strip()

    existing = git("for-each-ref", "--format=%(refname)", f"refs/tags/{tag}").decode().splitlines()
    if f"refs/tags/{tag}" in existing:
        commit = git("rev-parse", f"refs/tags/{tag}^{{commit}}").decode().strip()
        existing_tree = git("rev-parse", f"{commit}^{{tree}}").decode().strip()
        parents = git("rev-list", "--parents", "-n", "1", commit).decode().split()[1:]
        if existing_tree == tree and (commit == base or parents == [base]):
            return commit
        msg = f"Refusing to move existing release tag {tag}; choose a new tag or the matching source ref"
        raise ValueError(msg)

    commit = base
    if prepared != source:
        commit = (
            git("commit-tree", tree, "-p", base, "-m", "chore: prepare release authentication defaults")
            .decode()
            .strip()
        )
    git("tag", "--annotate", "--message", f"Release {tag} with auto-login disabled", "--", tag, commit)
    return commit
