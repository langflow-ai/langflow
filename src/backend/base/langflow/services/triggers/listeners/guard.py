"""The assertion that keeps the listener process and the API process apart.

Both prior trigger attempts hosted provider connections inside the API process,
and ``decisions/process-model.md`` makes not repeating that a decision rather
than a convention. A convention is a comment; this is a process-local flag that
:func:`langflow.main.create_app` refuses to build an app against.

It is deliberately *not* an environment variable. A child process spawned from
the API inherits the environment, so an env flag would describe the parent as
well as the child; a module global is set exactly once, by the code path that
actually becomes a listener.
"""

from __future__ import annotations

_IS_LISTENER_PROCESS = False


def mark_listener_process() -> None:
    """Declare this process a listener. Idempotent, and never reversed."""
    global _IS_LISTENER_PROCESS  # noqa: PLW0603 - one process-wide fact, set at boot
    _IS_LISTENER_PROCESS = True


def is_listener_process() -> bool:
    """True once :func:`mark_listener_process` has run in this process."""
    return _IS_LISTENER_PROCESS


def assert_no_http_app() -> None:
    """Fail the listener boot if a FastAPI app already exists in this process.

    Called after the flag is set, so the two checks are complementary: this one
    catches "an app was built before we became a listener", and ``create_app``'s
    own guard catches "something tried to build one afterwards".
    """
    import sys

    module = sys.modules.get("langflow.main")
    if module is None:
        return
    app = getattr(module, "app", None)
    if app is not None:
        msg = (
            "A FastAPI application already exists in this process; the listener process "
            "must not host the API. Run 'langflow listeners' as its own process."
        )
        raise RuntimeError(msg)
