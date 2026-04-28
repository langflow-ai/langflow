"""Defense-in-depth tests against shell glob/brace expansion.

Shell metacharacters like ``{a,b,c}``, ``*``, ``?``, ``[abc]`` expand
**before** the command runs. The static regex never sees the expanded
path, so an unprotected pattern lets ``rm -rf /{etc,var,usr}`` through
even though the actual ``rm`` would wipe ``/etc``, ``/var``, ``/usr``.

We don't try to evaluate the expansion (impossible in general). We
reject any ``rm -rf`` / ``del /S`` / ``rd /S`` / ``Remove-Item -Recurse
-Force`` whose target contains a glob/brace metachar near the root —
that catches all the practical attack shapes while still allowing
``rm -rf ./build/*`` (relative path) and ``rm -rf foo*`` (no leading
slash).
"""

from __future__ import annotations

import pytest
from lfx.mcp.shell.shell_types import RejectionReason
from lfx.mcp.shell.validation_destructive import validate_not_destructive


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf /{etc,var,usr}",
        "rm -rf /{etc,var}",
        "rm -fr /{home,root}",
        "sudo rm -rf /{etc,var,usr}",
    ],
)
def test_should_reject_brace_expansion_at_root(command: str):
    result = validate_not_destructive(command)
    assert result.is_ok is False
    assert result.reason == RejectionReason.DESTRUCTIVE_PATTERN


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf /e?c",
        "rm -rf /etc?",
        "rm -rf /et[c]",
        "rm -rf /[Ee]tc",
        "rm -rf /us*",
        "rm -rf /etc*",
        "rm -rf /v*",
        "rm -rf /W*",
    ],
)
def test_should_reject_glob_in_shallow_root_path(command: str):
    result = validate_not_destructive(command)
    assert result.is_ok is False
    assert result.reason == RejectionReason.DESTRUCTIVE_PATTERN


@pytest.mark.parametrize(
    "command",
    [
        # Specific subdir of cwd — glob is OK because expansion can't
        # reach system roots.
        "rm -rf ./build/*",
        "rm -rf build/*",
        "rm -rf ./dist/?old",
        "rm -rf ./*.log",
        # Filename-only globs without leading slash — fine.
        "rm -rf foo*",
        "rm -rf *.tmp",
        "rm -rf [Bb]uild",
    ],
)
def test_should_allow_globs_in_relative_paths(command: str):
    result = validate_not_destructive(command)
    assert result.is_ok is True


@pytest.mark.parametrize(
    "command",
    [
        # Windows: del /S /Q with glob in shallow drive root.
        "del /S /Q C:\\W*",
        "del /S /Q C:\\Win*",
        "del /S /Q C:\\?indows",
        "del /S /Q C:\\[Ww]indows",
        "rd /S /Q C:\\W*",
        "Remove-Item -Recurse -Force C:\\W*",
        "Remove-Item -Recurse -Force C:\\Win*",
        "Remove-Item -Recurse -Force C:\\[Ww]indows",
    ],
)
def test_should_reject_windows_glob_in_shallow_drive_path(command: str):
    result = validate_not_destructive(command)
    assert result.is_ok is False
    assert result.reason == RejectionReason.DESTRUCTIVE_PATTERN


@pytest.mark.parametrize(
    "command",
    [
        # Relative-path globs are allowed: expansion stays scoped to the
        # current directory, which the path validator already checks
        # lives inside the configured working_directory.
        "Remove-Item -Recurse -Force .\\build\\*",
        "del /S /Q .\\dist\\*.log",
        "rd /S /Q .\\old",
    ],
)
def test_should_allow_windows_globs_in_relative_paths(command: str):
    result = validate_not_destructive(command)
    assert result.is_ok is True
