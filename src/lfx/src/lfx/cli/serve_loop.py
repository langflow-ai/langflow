"""Event loop selection for ``lfx serve``.

uvicorn's default (``auto``) picks uvloop whenever uvloop is importable. uvloop ships
with ``uvicorn[standard]``, so that is what every uvicorn-backed serve path runs on
today, and what it keeps running on unless asked otherwise. ``--use-sync-workers`` is
the exception: it serves through the WSGI bridge, which builds its own stdlib loop and
never sees this setting.

``LFX_EVENT_LOOP=zuvloop`` opts into zuvloop instead: a libuv event loop written in
Zig. It needs Python 3.14+ and is not an lfx dependency, so install it alongside lfx
(``pip install zuvloop``).

The loop is handed to uvicorn as the import string ``zuvloop:new_event_loop``, not as
the bare name ``zuvloop``. uvicorn only grew a built-in ``zuvloop`` entry in its loop
registry in 0.54, and lfx pins ``uvicorn[standard]>=0.36``, so the bare name fails on
the older versions the pin still allows. The import string resolves to the same factory
on every supported version, since uvicorn imports a ``<module>:<attribute>`` loop value
and uses the result directly. Raising the pin to 0.54 would let this module drop the
string and pass ``loop="zuvloop"``.

When zuvloop is asked for but unusable, the server logs a warning and serves on the
default loop. The event loop is a performance choice, so a missing one degrades the
server's throughput, never its ability to boot.
"""

from __future__ import annotations

import os

from lfx.log.logger import logger

EVENT_LOOP_ENV = "LFX_EVENT_LOOP"

AUTO_LOOP = "auto"
ZUVLOOP = "zuvloop"

# What uvicorn is given for the zuvloop case. See the module docstring for why this is
# an import string rather than the bare loop name.
ZUVLOOP_LOOP_FACTORY = "zuvloop:new_event_loop"

# partition, not split, so a malformed constant degrades to the default loop through
# the hasattr check below instead of raising while this module is imported.
_ZUVLOOP_FACTORY_ATTR = ZUVLOOP_LOOP_FACTORY.partition(":")[2]


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
        import zuvloop
    except ImportError:
        logger.warning(
            f"{EVENT_LOOP_ENV}={ZUVLOOP} was set but zuvloop is not importable. It needs "
            "Python 3.14+ and does not ship with lfx, so install it alongside lfx "
            "('pip install zuvloop'). Serving on the default loop."
        )
        return AUTO_LOOP

    # uvicorn exits the process when an import-string loop value does not resolve, so
    # check the attribute here instead of letting a renamed one take the server down.
    if not hasattr(zuvloop, _ZUVLOOP_FACTORY_ATTR):
        logger.warning(
            f"{EVENT_LOOP_ENV}={ZUVLOOP} was set but the installed zuvloop has no "
            f"{_ZUVLOOP_FACTORY_ATTR!r}, so uvicorn cannot build a loop from it. "
            "Serving on the default loop."
        )
        return AUTO_LOOP

    logger.info(f"Serving on the zuvloop event loop ({EVENT_LOOP_ENV}={ZUVLOOP}).")
    return ZUVLOOP_LOOP_FACTORY
