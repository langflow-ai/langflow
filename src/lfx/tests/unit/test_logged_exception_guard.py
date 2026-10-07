"""The guard that keeps caught exception text out of log messages.

Exercised through the script's real entry point, including its exit code, because that is
what pre-commit and CI actually run. A unit test against the internal helpers would pass
while the command-line path was broken.

The accept cases matter as much as the reject ones. A guard that flags
``logger.error(f"failed for flow {flow_id}")`` gets turned off, and then it protects
nothing.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "lint" / "check_logged_exception_text.py"


def run_guard(source: str, tmp_path: Path):
    """Write source to a file, run the guard over it, return (exit code, output)."""
    target = tmp_path / "sample.py"
    target.write_text(textwrap.dedent(source), encoding="utf-8")
    completed = subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), str(target)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return completed.returncode, completed.stdout + completed.stderr


def test_the_script_exists_where_pre_commit_expects_it():
    """Asserted first: every case below shells out to this path."""
    assert SCRIPT.is_file(), SCRIPT


ACCEPTED = {
    "exc_info keyword": """
        try:
            work()
        except ValueError as e:
            logger.error("work failed", exc_info=e)
    """,
    "type name only": """
        try:
            work()
        except ValueError as e:
            logger.error(f"work failed: {type(e).__name__}")
    """,
    "an unrelated variable in an f-string": """
        try:
            work()
        except ValueError as e:
            logger.error(f"work failed for flow {flow_id}", exc_info=e)
    """,
    "no exception binding at all": """
        try:
            work()
        except ValueError:
            logger.error("work failed")
    """,
    "a message with no interpolation": """
        try:
            work()
        except ValueError as e:
            logger.warning("could not convert the message")
            raise RuntimeError from e
    """,
    "re-raising, which keeps the exception in the traceback rather than the log": """
        try:
            work()
        except ValueError as e:
            logger.debug("retrying")
            raise
    """,
}

REJECTED = {
    "f-string": """
        try:
            work()
        except ValueError as e:
            logger.error(f"work failed: {e}")
    """,
    # The four below are the ones ruff's G004 does not catch, which is why this exists.
    "structlog async variant": """
        try:
            work()
        except ValueError as e:
            await logger.aerror(f"work failed: {e}")
    """,
    "the lazy form G004 itself recommends": """
        try:
            work()
        except ValueError as e:
            logger.error("work failed: %s", e)
    """,
    "str() concatenation": """
        try:
            work()
        except ValueError as e:
            logger.error("work failed: " + str(e))
    """,
    "str.format": """
        try:
            work()
        except ValueError as e:
            logger.error("work failed: {}".format(e))
    """,
    "the exception as the sole argument": """
        try:
            work()
        except ValueError as e:
            logger.exception(e)
    """,
    "hidden in a structured field": """
        try:
            work()
        except ValueError as exc:
            logger.info("work.failed", extra={"reason": str(exc)})
    """,
    "the type is not enough when the message rides along with it": """
        try:
            work()
        except ValueError as e:
            logger.error(f"{type(e).__name__}: {e}")
    """,
    "an exception-shaped keyword is still a rendered field": """
        try:
            work()
        except ValueError as e:
            logger.error("work failed", error=str(e))
    """,
    "and so is a differently named one": """
        try:
            work()
        except ValueError as e:
            logger.error("work failed", exception=f"{e}")
    """,
    "conversion flags do not launder it": """
        try:
            work()
        except ValueError as e:
            logger.debug(f"work failed: {e!s}")
    """,
    "inside a nested function in the handler": """
        try:
            work()
        except ValueError as e:
            logger.warning(f"failed: {e}")
            cleanup()
    """,
}


@pytest.mark.parametrize("source", ACCEPTED.values(), ids=list(ACCEPTED))
def test_accepted_forms_pass(source, tmp_path):
    code, output = run_guard(source, tmp_path)

    assert code == 0, output


@pytest.mark.parametrize("source", REJECTED.values(), ids=list(REJECTED))
def test_rejected_forms_fail(source, tmp_path):
    code, output = run_guard(source, tmp_path)

    assert code == 1, f"guard did not flag this:\n{source}"
    assert "sample.py" in output, output


def test_the_report_names_the_line_and_says_how_to_fix_it(tmp_path):
    """A guard whose output does not say what to do gets suppressed rather than obeyed."""
    code, output = run_guard(
        """
        try:
            work()
        except ValueError as e:
            logger.error(f"work failed: {e}")
        """,
        tmp_path,
    )

    assert code == 1
    assert "sample.py:5" in output, output
    assert "exc_info" in output, output
    assert "type(exc).__name__" in output, output


def test_the_flow_execution_path_is_clean(tmp_path):  # noqa: ARG001
    """The gate itself: the scoped roots stay at zero, with no baseline file to drift."""
    completed = subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_a_nested_rebinding_is_reported_once(tmp_path):
    """``ast.walk`` cannot prune, so the naive version reported this twice.

    The inner handler rebinds ``e`` and owns its body. Counting matters: a guard that
    double-reports trains people to skim its output.
    """
    code, output = run_guard(
        """
        try:
            work()
        except ValueError as e:
            try:
                cleanup()
            except KeyError as e:
                logger.error(f"cleanup failed: {e}")
        """,
        tmp_path,
    )

    assert code == 1, output
    assert output.count("sample.py:8") == 1, output


def test_an_unrelated_nested_handler_does_not_hide_the_outer_binding(tmp_path):
    """Pruning is by name. A nested handler binding something else must not shield a leak."""
    code, output = run_guard(
        """
        try:
            work()
        except ValueError as e:
            try:
                cleanup()
            except KeyError as other:
                logger.error(f"cleanup failed: {e}")
        """,
        tmp_path,
    )

    assert code == 1, output
