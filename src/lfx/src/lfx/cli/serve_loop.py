"""Event loop selection for ``lfx serve``.

uvicorn resolves its loop through a registry in ``uvicorn.config``, and its
default (``auto``) picks uvloop whenever uvloop is importable. uvloop ships with
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
from typing import TYPE_CHECKING

from lfx.log.logger import logger

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Callable

EVENT_LOOP_ENV = "LFX_EVENT_LOOP"

AUTO_LOOP = "auto"
ZUVLOOP = "zuvloop"


def zuvloop_loop_factory(*, use_subprocess: bool = False) -> Callable[[], asyncio.AbstractEventLoop]:  # noqa: ARG001
    """Return zuvloop's loop constructor.

    Mirrors ``uvicorn.loops.uvloop.uvloop_loop_factory``, including the unused
    ``use_subprocess`` argument that uvicorn passes - by keyword - to every loop
    factory.
    """
    import zuvloop

    return zuvloop.new_event_loop


def resolve_loop() -> str:
    """Return the uvicorn ``loop`` name to serve with, registering zuvloop if requested.

    Always returns a loop name uvicorn can resolve, falling back to ``auto``
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
        from uvicorn.config import LOOP_FACTORIES
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

    LOOP_FACTORIES[ZUVLOOP] = "lfx.cli.serve_loop:zuvloop_loop_factory"
    logger.info(f"Serving on the zuvloop event loop ({EVENT_LOOP_ENV}={ZUVLOOP}).")
    return ZUVLOOP
