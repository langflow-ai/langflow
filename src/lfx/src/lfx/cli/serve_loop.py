"""Event loop selection for ``lfx serve``.

uvicorn's default (``auto``) picks uvloop whenever uvloop is importable. uvloop ships with
``uvicorn[standard]``, so that is what ``lfx serve`` runs on today and what it
keeps running on unless asked otherwise.

``LFX_EVENT_LOOP=zuvloop`` opts into zuvloop instead: a libuv event loop written
in Zig. It needs Python 3.14+ and is not an lfx dependency, so install it
alongside lfx (``pip install zuvloop``).

When zuvloop is asked for but unusable - not installed, or an older uvicorn
whose loop registry predates the factory contract - the server logs a warning
and serves on the default loop. The event loop is a performance choice, so a
missing one degrades the server's throughput, never its ability to boot.
"""

from __future__ import annotations

import os

from lfx.log.logger import logger

EVENT_LOOP_ENV = "LFX_EVENT_LOOP"

AUTO_LOOP = "auto"
ZUVLOOP = "zuvloop"


def resolve_loop() -> str:
    """Return the uvicorn loop name or import path to serve with.

    Always returns a loop choice uvicorn can resolve, falling back to ``auto``
    whenever the requested loop cannot be used.
    """
    requested = os.environ.get(EVENT_LOOP_ENV, "").strip().lower()
    if not requested or requested == AUTO_LOOP:
        return AUTO_LOOP

    if requested != ZUVLOOP:
        logger.warning(
            f"{EVENT_LOOP_ENV}={requested!r} is not a loop lfx knows about "
            f"(expected {ZUVLOOP!r} or {AUTO_LOOP!r}); serving on the default loop."
        )
        return AUTO_LOOP

    try:
        from uvicorn.config import LOOP_FACTORIES  # noqa: F401
    except ImportError:
        logger.warning(
            f"{EVENT_LOOP_ENV}={ZUVLOOP} needs uvicorn>=0.36, whose loop registry takes a loop "
            "factory; this environment has an older uvicorn. Serving on the default loop."
        )
        return AUTO_LOOP

    try:
        import zuvloop  # noqa: F401
    except ImportError:
        logger.warning(
            f"{EVENT_LOOP_ENV}={ZUVLOOP} was set but zuvloop is not importable. It needs "
            "Python 3.14+ and does not ship with lfx, so install it alongside lfx "
            "('pip install zuvloop'). Serving on the default loop."
        )
        return AUTO_LOOP

    logger.info(f"Serving on the zuvloop event loop ({EVENT_LOOP_ENV}={ZUVLOOP}).")
    # Spawned workers start with a fresh registry, so pass an importable constructor.
    return "zuvloop:new_event_loop"
