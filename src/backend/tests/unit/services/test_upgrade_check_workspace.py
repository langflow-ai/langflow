import os
import subprocess
import sys

import pytest
from langflow.services.upgrade_reports.workspace import RUN_FOLDER_PREFIX, _sweep_run_folders, hold_run_folder

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX checkers inherit the directory lock")


def test_sweep_leaves_workspace_until_its_last_checker_exits(tmp_path):
    active = tmp_path / f"{RUN_FOLDER_PREFIX}active"
    active.mkdir()
    (active / "download").touch()

    # The parent and child share the lock. Closing the parent's fd is what happens after a crash.
    with hold_run_folder(active) as fd:
        child = subprocess.Popen(  # noqa: S603
            [sys.executable, "-c", "import sys; sys.stdin.read()"],
            pass_fds=(fd,),
            stdin=subprocess.PIPE,
        )
        _sweep_run_folders(tmp_path)
        assert active.is_dir()

    with child:
        try:
            _sweep_run_folders(tmp_path)
            assert active.is_dir()
        finally:
            child.communicate(timeout=10)

    _sweep_run_folders(tmp_path)
    assert not active.exists()


def test_sweep_ignores_other_folders_and_symlinks(tmp_path):
    legacy = tmp_path / f"{RUN_FOLDER_PREFIX}legacy"
    legacy.mkdir()
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    with hold_run_folder(unrelated):
        link = tmp_path / f"{RUN_FOLDER_PREFIX}link"
        link.symlink_to(unrelated, target_is_directory=True)

    _sweep_run_folders(tmp_path)

    assert unrelated.is_dir()
    assert legacy.is_dir()
    assert link.is_symlink()
