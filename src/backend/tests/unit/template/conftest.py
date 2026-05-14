"""Conftest for template tests.

Registers an atexit guard that replaces the normal Python shutdown with os._exit()
when torch._C has been loaded.  Any import of langchain/transformers transitively
pulls in torch._C, whose pybind11 Py_AtExit() handler crashes (SIGSEGV / exit 139)
when it runs after the asyncio event loop has already been torn down.  Calling
os._exit() from a Python atexit preempts that C-level handler.

The pytest_sessionfinish hook captures the real exit code so test failures still
propagate correctly (exit 1) instead of being masked by the guard (exit 0).
"""

import atexit
import os
import sys

_exit_code: list[int] = [0]


def pytest_sessionfinish(session, exitstatus: int) -> None:  # noqa: ARG001
    _exit_code[0] = int(exitstatus)


def _torch_guard() -> None:
    if "torch._C" in sys.modules:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(_exit_code[0])


atexit.register(_torch_guard)
