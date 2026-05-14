import atexit
import os
import sys

import pytest

# Guard against pybind11 SIGSEGV on process exit when torch has been loaded.
# Integration tests pull in langchain → transformers → torch._C; the C-level
# Py_AtExit() handler then crashes (exit 139) after asyncio teardown. Calling
# os._exit() from a Python atexit preempts that handler. pytest_sessionfinish
# captures the real exit code so failures still propagate correctly.
_exit_code: list[int] = [0]


def pytest_sessionfinish(session, exitstatus: int) -> None:  # noqa: ARG001
    _exit_code[0] = int(exitstatus)


def _torch_guard() -> None:
    if "torch._C" in sys.modules:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(_exit_code[0])


atexit.register(_torch_guard)


@pytest.fixture(autouse=True)
def _start_app(client):
    pass


def pytest_configure(config):
    config.addinivalue_line("markers", "no_leaks: detect asyncio task leaks, thread leaks, and event loop blocking")
