"""Make process stdout/stderr tolerate characters their console codec cannot encode."""

import contextlib
import sys
from typing import Any


def _reconfigure(stream: Any) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    with contextlib.suppress(Exception):
        reconfigure(errors="backslashreplace")


def make_streams_resilient() -> None:
    """Escape unencodable characters on write instead of raising.

    Windows consoles default to a legacy code page (cp1252) whose codec raises
    UnicodeEncodeError on the box-drawing glyphs structlog's ConsoleRenderer
    emits when formatting a traceback. That second exception is raised inside
    the logging call itself, so it masks the original error and aborts the
    request that logged it. ``errors="backslashreplace"`` keeps the stream
    encoding but escapes anything the code page can't represent, so logging
    never crashes the caller. The underlying streams are reconfigured too
    because colorama wraps those same objects, regardless of wrap order.
    """
    for stream in (sys.stdout, sys.stderr, sys.__stdout__, sys.__stderr__):
        _reconfigure(stream)
