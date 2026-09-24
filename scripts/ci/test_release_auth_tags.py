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


def test_prepared_candidates_can_advance_without_changing_development(source_repo: Path) -> None:
    tag = "v1.13.0"
    first = prepare_release_tag(source_repo, tag)
    for label in ("RC2 fix", "Final fix"):
        expected = run_git(source_repo, "rev-parse", f"refs/tags/{tag}").decode().strip()
        (source_repo / "fix.txt").write_text(label)
        run_git(source_repo, "add", "fix.txt")
        run_git(source_repo, "commit", "-m", label)
        head = run_git(source_repo, "rev-parse", "HEAD")
        (source_repo / "unrelated.txt").write_text("staged work")
        run_git(source_repo, "add", "unrelated.txt")
        status = run_git(source_repo, "status", "--porcelain")

        prepared = prepare_release_tag(source_repo, tag, expected_tag=expected)

        assert prepared != first
        assert run_git(source_repo, "rev-parse", "HEAD") == head
        assert run_git(source_repo, "status", "--porcelain") == status
        assert run_git(source_repo, "show", f"{tag}:fix.txt").decode() == label
        assert b"default=False" in run_git(source_repo, "show", f"{tag}:{AUTH_SOURCE.as_posix()}")
        assert b"default=True" in (source_repo / AUTH_SOURCE).read_bytes()
        assert prepare_release_tag(source_repo, tag) == prepared


@pytest.mark.parametrize("change", ["unprepared", "extra_auth_change", "extra_file", "stale_tag", "unrelated_source"])
def test_candidate_replacement_rejects_unrecognized_or_stale_state(source_repo: Path, change: str) -> None:
    tag = "v1.13.0"
    original_base = run_git(source_repo, "rev-parse", "HEAD").decode().strip()
    if change == "unprepared":
        run_git(source_repo, "tag", tag)
    else:
        prepared = prepare_release_tag(source_repo, tag)
        if change in {"extra_auth_change", "extra_file"}:
            run_git(source_repo, "checkout", "--detach", prepared)
            target = source_repo / (AUTH_SOURCE if change == "extra_auth_change" else "extra.txt")
            target.write_bytes(target.read_bytes() + b"\n# Additional change\n" if target.exists() else b"extra")
            run_git(source_repo, "add", "--all")
            run_git(source_repo, "commit", "--amend", "--no-edit")
            run_git(source_repo, "tag", "--force", tag)
            run_git(source_repo, "checkout", "development")
    expected = run_git(source_repo, "rev-parse", f"refs/tags/{tag}").decode().strip()
    if change == "stale_tag":
        expected = original_base
    if change == "unrelated_source":
        run_git(source_repo, "checkout", "--orphan", "unrelated")
        run_git(source_repo, "commit", "-m", "Unrelated source")
    else:
        run_git(source_repo, "commit", "--allow-empty", "-m", "New source")
    original_tag = run_git(source_repo, "rev-parse", f"refs/tags/{tag}")

    with pytest.raises(ValueError, match=r"not an exact|changed since|must descend"):
        prepare_release_tag(source_repo, tag, expected_tag=expected)

    assert run_git(source_repo, "rev-parse", f"refs/tags/{tag}") == original_tag


def test_remote_candidate_update_uses_a_lease(source_repo: Path, tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    run_git(source_repo, "init", "--bare", str(remote))
    run_git(source_repo, "remote", "add", "origin", str(remote))
    tag_ref = "refs/tags/v1.13.0"
    prepare_release_tag(source_repo, "v1.13.0")
    expected = run_git(source_repo, "rev-parse", tag_ref).decode().strip()
    run_git(source_repo, "push", "origin", tag_ref)
    run_git(source_repo, "commit", "--allow-empty", "-m", "RC2")
    prepare_release_tag(source_repo, "v1.13.0", expected_tag=expected)
    run_git(source_repo, "push", f"--force-with-lease={tag_ref}:{expected}", "origin", tag_ref)
    current = run_git(remote, "rev-parse", tag_ref)

    # A stale retry cannot overwrite a candidate that another run has advanced.
    run_git(source_repo, "commit", "--allow-empty", "-m", "Final")
    prepare_release_tag(source_repo, "v1.13.0", expected_tag=current.decode().strip())
    with pytest.raises(subprocess.CalledProcessError):
        run_git(source_repo, "push", f"--force-with-lease={tag_ref}:{expected}", "origin", tag_ref)
    assert run_git(remote, "rev-parse", tag_ref) == current


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
