"""Regression tests for reading migration graphs from committed Git revisions."""

import shutil
import subprocess

import pytest

from . import test_migration_execution as migration_execution


@pytest.fixture
def migration_repo(tmp_path, monkeypatch):
    git = shutil.which("git")
    if git is None:
        pytest.skip("Git is required to test migration revision discovery")

    def run_git(*args):
        return subprocess.run(  # noqa: S603
            [git, *args], capture_output=True, text=True, check=True, cwd=tmp_path
        ).stdout.strip()

    run_git("init")
    versions = tmp_path / "src/backend/base/langflow/alembic/versions"
    versions.mkdir(parents=True)
    monkeypatch.setattr(migration_execution, "_WORKSPACE_ROOT", tmp_path)

    def commit_migrations(sources):
        for name, source in sources.items():
            (versions / name).write_text(source)
        run_git("add", ".")
        run_git(
            "-c",
            "user.name=Migration Test",
            "-c",
            "user.email=migration@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.hooksPath=/dev/null",
            "commit",
            "-m",
            "Test migrations",
        )
        return run_git("rev-parse", "HEAD")

    return versions, commit_migrations


@pytest.mark.parametrize(
    ("root", "merge", "expected"),
    [
        (
            'revision: str = "aaa111"\ndown_revision: str | None = None\n',
            'revision: str = "ccc333"\ndown_revision: tuple[str, ...] = (\n'
            '    "aaa111",  # first parent\n    "bbb222",  # second parent\n)\n',
            "ccc333",
        ),
        (
            'revision = "aaa111"\ndown_revision = None\n',
            'revision = "ccc333"\ndown_revision = ("aaa111", "bbb222")\n',
            "ccc333",
        ),
        (
            'revision: str = "kb_root"\ndown_revision: str | None = None\n',
            'revision: str = "cp_merge"\ndown_revision = ["kb_root", "bbb222"]\n',
            "cp_merge",
        ),
    ],
    ids=["multiline-merge", "unannotated-assignments", "non-hex-revisions"],
)
def test_head_revision_at_reads_complete_migration_declarations(migration_repo, root, merge, expected):
    _, commit = migration_repo
    ref = commit(
        {
            "root.py": root,
            "other.py": 'revision: str = "bbb222"\ndown_revision: str | None = None\n',
            "merge.py": merge,
        }
    )

    assert migration_execution._head_revision_at(ref) == expected


def test_head_revision_at_reads_committed_source_without_executing_it(migration_repo):
    versions, commit = migration_repo
    ref = commit(
        {
            "root.py": 'revision: str = "aaa111"\ndown_revision = None\n'
            'raise RuntimeError("Migration imports must not run")\n',
        }
    )
    (versions / "root.py").write_text('revision = "bbb222"\ndown_revision = None\n')

    assert migration_execution._head_revision_at(ref) == "aaa111"


def test_head_revision_at_rejects_genuinely_unmerged_heads(migration_repo):
    _, commit = migration_repo
    ref = commit(
        {
            "root.py": 'revision: str = "aaa111"\ndown_revision = None\n',
            "other.py": 'revision: str = "bbb222"\ndown_revision = None\n',
        }
    )

    with pytest.raises(pytest.fail.Exception, match="2 head revisions"):
        migration_execution._head_revision_at(ref)


def test_head_revision_at_returns_none_for_missing_ref(migration_repo):
    _, commit = migration_repo
    commit({"root.py": 'revision: str = "aaa111"\ndown_revision = None\n'})

    assert migration_execution._head_revision_at("missing-ref") is None
