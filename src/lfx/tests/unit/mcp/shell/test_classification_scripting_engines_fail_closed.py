"""Fail-closed classification for scripting engines.

PR review #4: ``awk`` and ``sed`` are scripting engines with script-level
shell-exec primitives:

  * ``awk 'BEGIN{system("...")}'``
  * ``sed 'e <cmd>'``

Once the script is inside a single-quoted token, the path validator can't
see what's in it, so the embedded command runs unfiltered. The same applies
to ``perl``, ``tcl``, ``lua``, ``osascript``, ``xargs``.

Fix: classify the whole family as UNKNOWN so the pipeline fail-closes
unless the operator explicitly enables them. UNKNOWN intent is rejected
by the pipeline; an opt-in flag would be future work.
"""

from __future__ import annotations

import pytest
from lfx.mcp.shell.classification import classify_command
from lfx.mcp.shell.shell_types import CommandIntent


@pytest.mark.parametrize(
    "command",
    [
        # awk script-exec primitive: BEGIN{system("...")}
        "awk 'BEGIN{system(\"id\")}'",
        # awk also supports getline pipe and printf to pipe — same risk surface.
        "awk '{print | \"sh\"}'",
        # plain awk ALSO classified UNKNOWN (fail-closed default; can't tell
        # statically whether the script body contains exec primitives).
        "awk '{print $1}' file.txt",
    ],
)
def test_should_classify_awk_as_unknown(command: str):
    assert classify_command(command) == CommandIntent.UNKNOWN


@pytest.mark.parametrize(
    "command",
    [
        # sed e command: 'e <cmd>' — runs cmd through shell.
        "sed 'e id' file",
        # sed in-place edits with arbitrary substitution — also fail-closed
        # because the substitution body could embed shell metacharacters that
        # downstream pipelines re-interpret.
        "sed -i 's/foo/bar/' file",
        "sed 's/x/y/g' file",
    ],
)
def test_should_classify_sed_as_unknown(command: str):
    assert classify_command(command) == CommandIntent.UNKNOWN


@pytest.mark.parametrize(
    "engine",
    ["perl", "tcl", "tclsh", "lua", "luajit", "osascript", "xargs", "ruby", "node", "deno", "bun", "php"],
)
def test_should_classify_scripting_engines_as_unknown(engine: str):
    """Each engine has shell-exec primitives in its script language."""
    assert classify_command(f"{engine} -e 'something'") == CommandIntent.UNKNOWN
    assert classify_command(f"{engine} script.txt") == CommandIntent.UNKNOWN


def test_xargs_explicit_subcommand_invocation_classified_as_unknown():
    """Xargs -I{} sh -c '...' is the canonical bypass.

    The shell command lives inside a single-quoted argv slot that the path
    validator can't introspect.
    """
    assert classify_command("xargs -I{} sh -c 'rm -rf /'") == CommandIntent.UNKNOWN
    # And the simpler form — same reasoning.
    assert classify_command("xargs rm") == CommandIntent.UNKNOWN
