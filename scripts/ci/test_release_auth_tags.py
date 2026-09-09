"""Integration coverage for immutable release tags and development-state preservation."""

from __future__ import annotations

import io
import subprocess
import zipfile
from typing import TYPE_CHECKING

import pytest

from scripts.ci.release_auth.constants import AUTH_SOURCE
from scripts.ci.release_auth.preparation import prepare_release_auth
from scripts.ci.release_auth.tags import prepare_release_tag
from scripts.ci.release_auth.validation import verify_release_source
from scripts.ci.release_auth_fixtures import run_git

if TYPE_CHECKING:
    from pathlib import Path

pytest_plugins = ("scripts.ci.release_auth_fixtures",)


def test_release_tag_archives_disable_auto_login_without_changing_development(source_repo: Path) -> None:
    base = run_git(source_repo, "rev-parse", "HEAD").decode().strip()
    source = (source_repo / AUTH_SOURCE).read_bytes()
    (source_repo / "staged.txt").write_text("Unrelated staged work")
    run_git(source_repo, "add", "--", "staged.txt")
    (source_repo / AUTH_SOURCE).write_bytes(source + b"\n# Uncommitted development work\n")
    status = run_git(source_repo, "status", "--porcelain")
    index = run_git(source_repo, "diff", "--cached")

    release = prepare_release_tag(source_repo, "v1.13.0")

    assert release != base
    assert run_git(source_repo, "rev-parse", "HEAD").decode().strip() == base
    assert run_git(source_repo, "branch", "--show-current").strip() == b"development"
    assert run_git(source_repo, "status", "--porcelain") == status
    assert run_git(source_repo, "diff", "--cached") == index
    assert (source_repo / AUTH_SOURCE).read_bytes() == source + b"\n# Uncommitted development work\n"
    assert run_git(source_repo, "diff", "--name-only", base, release).decode().splitlines() == [AUTH_SOURCE.as_posix()]
    assert prepare_release_tag(source_repo, "v1.13.0") == release

    archive_bytes = run_git(source_repo, "archive", "--format=zip", "v1.13.0")
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        tagged_source = archive.read(AUTH_SOURCE.as_posix())
    assert b"AUTO_LOGIN: bool = Field(\n        default=False," in tagged_source
    assert b"Uncommitted development work" not in tagged_source


@pytest.mark.parametrize("tag", ["v1.13.0", "lfx-v1.13.0"])
def test_release_tag_refuses_to_move_an_existing_unprepared_tag(source_repo: Path, tag: str) -> None:
    run_git(source_repo, "tag", tag)
    original = run_git(source_repo, "rev-parse", f"refs/tags/{tag}")

    with pytest.raises(ValueError, match="Refusing to move existing release tag"):
        prepare_release_tag(source_repo, tag)

    assert run_git(source_repo, "rev-parse", f"refs/tags/{tag}") == original


def test_release_tag_refuses_to_reuse_a_tag_from_another_source_commit(source_repo: Path) -> None:
    release = prepare_release_tag(source_repo, "v1.13.0")
    run_git(source_repo, "commit", "--allow-empty", "-m", "New source changes")

    with pytest.raises(ValueError, match="Refusing to move existing release tag"):
        prepare_release_tag(source_repo, "v1.13.0")

    assert run_git(source_repo, "rev-parse", "refs/tags/v1.13.0^{commit}").decode().strip() == release


def test_tagging_an_already_prepared_release_does_not_add_another_commit(source_repo: Path) -> None:
    prepare_release_auth(source_repo / AUTH_SOURCE)
    run_git(source_repo, "add", "--", AUTH_SOURCE.as_posix())
    run_git(source_repo, "commit", "-m", "Prepared release")
    base = run_git(source_repo, "rev-parse", "HEAD").decode().strip()

    assert prepare_release_tag(source_repo, "v1.13.0") == base
    assert prepare_release_tag(source_repo, "v1.13.0") == base
    verify_release_source(source_repo / AUTH_SOURCE)


@pytest.mark.parametrize("tag", ["-invalid", "", "v1..13", "v1.13.0; touch sentinel"])
def test_should_preserve_repository_when_tag_is_invalid(source_repo: Path, tag: str) -> None:
    head = run_git(source_repo, "rev-parse", "HEAD")
    status = run_git(source_repo, "status", "--porcelain")

    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        prepare_release_tag(source_repo, tag)

    assert run_git(source_repo, "rev-parse", "HEAD") == head
    assert run_git(source_repo, "status", "--porcelain") == status
    assert run_git(source_repo, "tag", "--list") == b""


def test_should_report_missing_git_when_git_is_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))

    with pytest.raises(RuntimeError, match="Git is required"):
        prepare_release_tag(tmp_path, "v1.13.0")
