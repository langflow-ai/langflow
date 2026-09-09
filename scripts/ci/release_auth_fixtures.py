"""Reusable fixtures for isolated release-authentication integration tests."""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from scripts.ci.release_auth.constants import AUTH_SOURCE, WHEEL_AUTH_PATH


def run_git(repo: Path, *args: str) -> bytes:
    """Run Git only inside the temporary repository supplied by a test."""
    git = shutil.which("git")
    if git is None:
        pytest.fail("Git is required for release-tag integration tests")
    # Arguments are supplied by tests; no command is interpreted by a shell.
    return subprocess.run([git, "-C", str(repo), *args], check=True, capture_output=True).stdout  # noqa: S603


@pytest.fixture
def development_auth_source() -> bytes:
    """Provide development source even when tests run from an official tag."""
    return (
        (Path(__file__).resolve().parents[2] / AUTH_SOURCE)
        .read_bytes()
        .replace(
            b"AUTO_LOGIN: bool = Field(\n        default=False,", b"AUTO_LOGIN: bool = Field(\n        default=True,"
        )
    )


@pytest.fixture
def source_repo(tmp_path: Path, development_auth_source: bytes) -> Path:
    """Create a disposable repository without touching the developer's index."""
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "--initial-branch=development")
    run_git(repo, "config", "user.name", "Release Test")
    run_git(repo, "config", "user.email", "release-test@example.invalid")
    run_git(repo, "config", "commit.gpgsign", "false")
    run_git(repo, "config", "tag.gpgsign", "false")
    auth = repo / AUTH_SOURCE
    auth.parent.mkdir(parents=True)
    auth.write_bytes(development_auth_source)
    run_git(repo, "add", "--", AUTH_SOURCE.as_posix())
    run_git(repo, "commit", "-m", "Source development")
    return repo


@pytest.fixture
def wheel_files(tmp_path: Path) -> dict[bool, Path]:
    """Provide wheels with independently declared development/release defaults."""
    wheels = {}
    for is_release in (False, True):
        path = tmp_path / f"lfx-{'release' if is_release else 'development'}.whl"
        source = f"class AuthSettings:\n    AUTO_LOGIN: bool = Field(default={not is_release})\n"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(WHEEL_AUTH_PATH, source)
        wheels[is_release] = path
    return wheels
