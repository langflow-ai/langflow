"""CLI wrapper for the run command."""

import json
from functools import partial
from pathlib import Path

import typer
from asyncer import syncify

# Cold-start benchmark hook. No-op when LFX_BENCHMARK_CHECKPOINTS is unset.
# See src/lfx/src/lfx/_bench.py for the checkpoint / dump contract.
from lfx._bench import _ENABLED as _BENCH_ENABLED
from lfx._bench import checkpoint, dump
from lfx.run.base import RunError, run_flow

checkpoint("after-imports")

# Benchmark landmark trigger. The `lfx run` path does NOT transitively import
# `lfx.services.initialize` during normal flow loading, so its module-level
# `initialize_services()` (and the landmark checkpoint that follows it) would never fire.
# Gated on the benchmark env var so production runs pay ZERO import cost; under measurement
# this triggers the module body and therefore records `after-initialize-services`.
# The landmarks themselves live at their true call sites in `lfx/services/initialize.py`
# and `lfx/load/load.py`.
if _BENCH_ENABLED:
    import lfx.services.initialize  # noqa: F401

# Verbosity level constants
VERBOSITY_DETAILED = 2
VERBOSITY_FULL = 3


def _register_torch_exit_guard() -> list[int]:
    """Register a Python atexit that calls os._exit() if torch's C extension loaded.

    WHY THIS EXISTS
    ---------------
    Any non-trivial langchain import (langchain_core.language_models,
    langchain_classic.agents, etc.) transitively imports ``transformers``, which
    imports ``torch._C`` — a pybind11 C extension.  Loading ``torch._C``
    registers a cleanup handler via ``Py_AtExit()``.  When torch is first imported
    *inside* a running asyncio event loop, that C-level handler later runs after
    interpreter state it references has already been freed, producing SIGSEGV
    (exit 139).  On ``release-1.10.0`` torch was imported at process startup
    (before asyncio) via eager top-level imports and shutdown was orderly.  The
    cold-start work moved those imports inside the event loop, inadvertently
    introducing the crash.

    HOW THIS FIXES IT
    -----------------
    Python atexit functions run *before* C-level ``Py_AtExit()`` handlers in
    CPython's shutdown sequence.  Calling ``os._exit()`` from a Python atexit
    terminates the process before the dangerous C teardown runs.

    The returned list ``[exit_code]`` lets the caller update the intended exit
    code before the atexit fires, ensuring error exits are not masked as success.
    The guard is keyed on ``torch._C`` (the C extension that registers the
    pybind11 handler) rather than ``torch``, which CPython may clear earlier.
    """
    import atexit
    import os
    import sys

    code: list[int] = [0]

    def _guard() -> None:
        if "torch._C" in sys.modules:
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(code[0])

    atexit.register(_guard)
    return code


def _check_langchain_version_compatibility(error_message: str) -> str | None:
    """Check if error is due to langchain-core version incompatibility.

    Returns a helpful error message if incompatibility is detected, None otherwise.
    """
    # Check for the specific error that occurs with langchain-core 1.x
    # The langchain_core.memory module was removed in langchain-core 1.x
    if "langchain_core.memory" in error_message or "No module named 'langchain_core.memory'" in error_message:
        try:
            import langchain_core

            version = getattr(langchain_core, "__version__", "unknown")
        except ImportError:
            version = "unknown"

        return (
            f"ERROR: Incompatible langchain-core version (v{version}).\n\n"
            "The 'langchain_core.memory' module was removed in langchain-core 1.x.\n"
            "lfx requires langchain-core < 1.0.0.\n\n"
            "This usually happens when langchain-openai >= 1.0.0 is installed,\n"
            "which pulls in langchain-core >= 1.0.0.\n\n"
            "FIX: Reinstall with compatible versions:\n\n"
            "  uv pip install 'langchain-core>=0.3.0,<1.0.0' \\\n"
            "                 'langchain-openai>=0.3.0,<1.0.0' \\\n"
            "                 'langchain-community>=0.3.0,<1.0.0'\n\n"
            "Or with pip:\n\n"
            "  pip install 'langchain-core>=0.3.0,<1.0.0' \\\n"
            "              'langchain-openai>=0.3.0,<1.0.0' \\\n"
            "              'langchain-community>=0.3.0,<1.0.0'"
        )
    return None


@partial(syncify, raise_sync_error=False)
async def run(
    script_path: Path | None = typer.Argument(  # noqa: B008
        None, help="Path to the Python script (.py) or JSON flow (.json) containing a graph"
    ),
    input_value: str | None = typer.Argument(None, help="Input value to pass to the graph"),
    input_value_option: str | None = typer.Option(
        None,
        "--input-value",
        help="Input value to pass to the graph (alternative to positional argument)",
    ),
    output_format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Output format: json, text, message, or result",
    ),
    flow_json: str | None = typer.Option(
        None,
        "--flow-json",
        help=("Inline JSON flow content as a string (alternative to script_path)"),
    ),
    *,
    stdin: bool | None = typer.Option(
        default=False,
        flag_value="--stdin",
        show_default=True,
        help="Read JSON flow content from stdin (alternative to script_path)",
    ),
    check_variables: bool = typer.Option(
        default=True,
        show_default=True,
        help="Check global variables for environment compatibility",
    ),
    verbose: bool = typer.Option(
        False,  # noqa: FBT003
        "-v",
        "--verbose",
        help="Show basic progress information",
    ),
    verbose_detailed: bool = typer.Option(
        False,  # noqa: FBT003
        "-vv",
        help="Show detailed progress and debug information",
    ),
    verbose_full: bool = typer.Option(
        False,  # noqa: FBT003
        "-vvv",
        help="Show full debugging output including component logs",
    ),
    timing: bool = typer.Option(
        default=False,
        show_default=True,
        help="Include detailed timing information in output",
    ),
    session_id: str | None = typer.Option(
        None,
        "--session-id",
        help=(
            "Session ID to attach to the run. Agent and Memory Components will use this to track conversation history."
        ),
    ),
) -> None:
    """Execute a Langflow graph script or JSON flow and return the result.

    This command analyzes and executes either a Python script containing a Langflow graph,
    a JSON flow file, inline JSON, or JSON from stdin, returning the result in the specified format.
    By default, output is minimal for use in containers and serverless environments.

    Args:
        script_path: Path to the Python script (.py) or JSON flow (.json) containing a graph
        input_value: Input value to pass to the graph (positional argument)
        input_value_option: Input value to pass to the graph (alternative option)
        verbose: Show diagnostic output and execution details
        verbose_detailed: Show detailed progress and debug information (-vv)
        verbose_full: Show full debugging output including component logs (-vvv)
        output_format: Format for output (json, text, message, or result)
        flow_json: Inline JSON flow content as a string
        stdin: Read JSON flow content from stdin
        check_variables: Check global variables for environment compatibility
        timing: Include detailed timing information in output
        session_id: Optional session ID; auto-generated if not supplied
    """
    # Determine verbosity for output formatting
    verbosity = 3 if verbose_full else (2 if verbose_detailed else (1 if verbose else 0))

    _torch_exit_code = _register_torch_exit_guard()

    try:
        checkpoint("before-run-flow")
        result = await run_flow(
            script_path=script_path,
            input_value=input_value,
            input_value_option=input_value_option,
            output_format=output_format,
            flow_json=flow_json,
            stdin=bool(stdin),
            check_variables=check_variables,
            verbose=verbose,
            verbose_detailed=verbose_detailed,
            verbose_full=verbose_full,
            timing=timing,
            global_variables=None,
            session_id=session_id,
        )
        checkpoint("after-run-flow")

        # Output based on format
        if output_format in {"text", "message", "result"}:
            typer.echo(result.get("output", ""))
        else:
            indent = 2 if verbosity > 0 else None
            typer.echo(json.dumps(result, indent=indent))
        dump()

    except RunError as e:
        error_response = {
            "success": False,
            "type": "error",
        }
        if e.original_exception:
            error_response["exception_type"] = type(e.original_exception).__name__
            error_response["exception_message"] = str(e.original_exception)
        else:
            error_response["exception_message"] = str(e)
        typer.echo(json.dumps(error_response))
        dump()
        _torch_exit_code[0] = 1
        raise typer.Exit(1) from e

    except BaseException as exc:
        # Catch-all for anything that escapes the RunError handler: unhandled
        # asyncio errors, KeyboardInterrupt, etc.  Re-raise immediately so
        # normal error handling is unaffected; the only purpose here is to
        # ensure the atexit guard uses the correct exit code before it fires.
        #
        # typer.Exit inherits from RuntimeError (not SystemExit), so it must
        # be checked before the unconditional else-branch to avoid masking a
        # clean typer.Exit(0) as exit code 1.
        if isinstance(exc, SystemExit):
            code = exc.code
            _torch_exit_code[0] = code if isinstance(code, int) else (0 if code is None else 1)
        elif isinstance(exc, typer.Exit):
            _torch_exit_code[0] = int(exc.exit_code) if exc.exit_code is not None else 0
        elif isinstance(exc, KeyboardInterrupt):
            _torch_exit_code[0] = 130
        else:
            _torch_exit_code[0] = 1
        raise
