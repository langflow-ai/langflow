r"""Path validator: brace-form home references must be rejected.

PR review #5: the original regex caught ``$HOME`` but not ``${HOME}``,
so ``cat ${HOME}/.ssh/id_rsa`` slipped past path validation. The shell
expands both forms identically, so the validator must too. Same trick
applies to ``${USERPROFILE}``, ``${APPDATA}``, ``${HOMEDRIVE}``, etc.
"""

from __future__ import annotations

import pytest
from lfx.mcp.shell.shell_types import RejectionReason
from lfx.mcp.shell.validation_path import validate_paths


@pytest.mark.parametrize(
    "command",
    [
        "cat ${HOME}/.ssh/id_rsa",
        "cat ${HOME}",
        "ls ${HOME}/.config",
        # Brace form with no path suffix.
        "echo ${HOME}",
        # PowerShell-style brace usage (``${env:HOME}``) — same expansion semantics.
        "cat ${env:HOME}/.ssh/key",
    ],
)
def test_should_reject_brace_form_home_references(command: str, tmp_path):
    result = validate_paths(command, working_directory=str(tmp_path))
    assert not result.is_ok, f"command should have been rejected: {command!r}"
    assert result.reason is RejectionReason.PATH_TRAVERSAL


@pytest.mark.parametrize(
    "var",
    ["USERPROFILE", "APPDATA", "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH"],
)
def test_should_reject_brace_form_windows_env_references(var: str, tmp_path):
    """Reject Windows env-var brace form ``${VAR}`` from bash-on-Windows shells.

    Normally referenced via ``%VAR%`` (cmd.exe) or ``$env:VAR`` (PowerShell),
    but bash on Windows (Git Bash, WSL, MSYS2) uses ``${VAR}`` — the validator
    must recognise it too.
    """
    command = f"cat ${{{var}}}/secret"
    result = validate_paths(command, working_directory=str(tmp_path))
    assert not result.is_ok, f"command should have been rejected: {command!r}"
    assert result.reason is RejectionReason.PATH_TRAVERSAL


def test_should_still_reject_unbraced_home_for_regression(tmp_path):
    """Make sure the brace fix doesn't accidentally regress the unbraced form."""
    result = validate_paths("cat $HOME/.ssh/key", working_directory=str(tmp_path))
    assert not result.is_ok
    assert result.reason is RejectionReason.PATH_TRAVERSAL


def test_should_still_allow_plain_paths_inside_workdir(tmp_path):
    """Sanity: the brace fix must not over-reject normal commands."""
    (tmp_path / "data.txt").write_text("hello")
    result = validate_paths("cat data.txt", working_directory=str(tmp_path))
    assert result.is_ok
