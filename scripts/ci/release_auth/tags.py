"""Prepare release tags without changing development work."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .constants import AUTH_SOURCE
from .preparation import prepare_release_source


def prepare_release_tag(repo: Path, tag: str, ref: str = "HEAD", *, expected_tag: str | None = None) -> str:
    """Create a release-only commit and tag, preserving branches and the index.

    Tags are immutable by default. To advance a prepared candidate, the caller
    must supply its exact tag object ID, check that no final release was published,
    and push with a lease on that same ID. Only this tool's exact preparation
    transformation can be replaced, and only from a descendant source commit.
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

    def release_tree(commit: str) -> str:
        source = git("show", f"{commit}:{AUTH_SOURCE.as_posix()}")
        blob = git("hash-object", "-w", "--stdin", data=prepare_release_source(source)).decode().strip()
        mode = git("ls-tree", commit, "--", AUTH_SOURCE.as_posix()).decode().split()[0]
        with tempfile.TemporaryDirectory(prefix="langflow-release-index-") as directory:
            env = {**os.environ, "GIT_INDEX_FILE": str(Path(directory) / "index")}
            git("read-tree", commit, env=env)
            git("update-index", "--add", "--cacheinfo", f"{mode},{blob},{AUTH_SOURCE.as_posix()}", env=env)
            return git("write-tree", env=env).decode().strip()

    tree = release_tree(base)
    old_object = "0" * len(base)

    existing = git("for-each-ref", "--format=%(refname)", f"refs/tags/{tag}").decode().splitlines()
    if f"refs/tags/{tag}" in existing:
        old_object = git("rev-parse", f"refs/tags/{tag}").decode().strip()
        if expected_tag is not None and expected_tag != old_object:
            msg = f"Release tag {tag} changed since it was inspected; refresh before retrying"
            raise ValueError(msg)
        commit = git("rev-parse", f"refs/tags/{tag}^{{commit}}").decode().strip()
        existing_tree = git("rev-parse", f"{commit}^{{tree}}").decode().strip()
        parents = git("rev-list", "--parents", "-n", "1", commit).decode().split()[1:]
        if existing_tree == tree and (commit == base or parents == [base]):
            return commit
        if expected_tag is None:
            msg = (
                f"Refusing to move existing release tag {tag}; "
                "choose a new tag or explicitly replace a prepared candidate"
            )
            raise ValueError(msg)
        if (
            len(parents) != 1
            or existing_tree == git("rev-parse", f"{parents[0]}^{{tree}}").decode().strip()
            or existing_tree != release_tree(parents[0])
        ):
            msg = f"Release tag {tag} is not an exact release-auth preparation commit; refusing replacement"
            raise ValueError(msg)
        try:
            git("merge-base", "--is-ancestor", parents[0], base)
        except subprocess.CalledProcessError as exc:
            msg = "Replacement source must descend from the previous candidate's source commit"
            raise ValueError(msg) from exc
    elif expected_tag is not None:
        msg = f"Release tag {tag} no longer exists; refresh before retrying"
        raise ValueError(msg)

    commit = base
    if tree != git("rev-parse", f"{base}^{{tree}}").decode().strip():
        commit = (
            git("commit-tree", tree, "-p", base, "-m", "chore: prepare release authentication defaults")
            .decode()
            .strip()
        )
    # Create the annotated object first, then compare-and-swap the ref. A local
    # concurrent tag update must not be overwritten, just like a remote lease.
    identity = git("var", "GIT_COMMITTER_IDENT").decode().strip()
    annotation = (
        f"object {commit}\ntype commit\ntag {tag}\ntagger {identity}\n\nRelease {tag} with auto-login disabled\n"
    ).encode()
    tag_object = git("mktag", data=annotation).decode().strip()
    git("update-ref", f"refs/tags/{tag}", tag_object, old_object)
    return commit
