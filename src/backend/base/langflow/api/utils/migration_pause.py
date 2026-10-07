"""The write pause that keeps an instance still while its data is copied to a new instance.

The copy runs while this server keeps serving, and a write that lands during it is
lost without a report. While the pause is on, the middleware refuses every request
that could change the instance, and the loops that write without a request skip
their work by asking is_paused().

The pause is a field of the migration record, CONFIG_DIR/migrations/migration.json:

    "pause": {"frozen_at": "<ISO time>", "frozen_by": "<username>"}

It lives outside the database because the database is what moves: a flag stored
there would travel to the new instance, which would then boot refusing writes.

A pause counts only once every change that was let in before it has ended. Each such
change holds a place, writing(), from before it asks about the pause until it is over,
and the pause waits in drained() until no place is held. Places are kept in this
worker and, for the other workers, held as a shared lock on CONFIG_DIR/migrations/pause.lock,
which the kernel lets go of when a process dies.

Each place says what holds it, so that a pause that gives up waiting can tell the admin
what is still under way: under_way().
"""

from __future__ import annotations

import asyncio
import contextlib
import itertools
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lfx.services.settings.feature_flags import FEATURE_FLAGS
from starlette.responses import JSONResponse

from langflow.services.deps import get_settings_service

try:
    import fcntl
except ImportError:  # Windows
    # ponytail: without flock only this worker's changes are counted, so a pause there can begin
    # while another worker still writes. Use msvcrt.locking if Langflow runs several workers on Windows.
    fcntl = None

if TYPE_CHECKING:
    from collections.abc import Iterator

_READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# What the admin still needs: a session, and the migration steps, which include ending the pause.
_ALLOWED_PATHS = frozenset({"/api/v1/login", "/api/v1/refresh", "/api/v1/logout", "/api/v1/auto_login"})
_ALLOWED_PREFIX = "/api/v1/migration/"

# Which record file was last read, and what it said.
_seen: tuple[str, int, int, int] | None = None
_paused = False
# The changes this worker let in that have not ended: each place, with what holds it and since when.
_held: dict[int, dict[str, Any]] = {}
_places = itertools.count()
# Seconds between two looks at whether every change has ended.
_DRAIN_POLL = 0.05


def is_paused() -> bool:
    """Whether the pause is on.

    Every worker process asks on each request, so the answer costs one stat: the
    record is read again only when the file was replaced or changed. A missing record
    means not paused. A record that cannot be read or parsed means paused, because a
    damaged record must not lift a pause that was on.
    """
    global _seen, _paused  # noqa: PLW0603
    if not FEATURE_FLAGS.instance_migration:
        return False
    path = Path(get_settings_service().settings.config_dir) / "migrations" / "migration.json"
    try:
        # ponytail: a blocking stat on the event loop, microseconds on a local disk. Move it to a
        # thread if CONFIG_DIR ever sits on a slow network mount.
        stat = path.stat()
        # The record is replaced by rename, so the inode changes even when the time and size do not.
        seen = (str(path), stat.st_ino, stat.st_mtime_ns, stat.st_size)
        if seen != _seen:
            pause = json.loads(path.read_bytes()).get("pause") or {}
            _seen, _paused = seen, bool(pause.get("frozen_at"))
    except FileNotFoundError:
        _seen = None
        return False
    except (OSError, ValueError, AttributeError):
        _seen = None
        return True
    return _paused


# A request holds a place, and so does each pass of a loop that writes with no request around it: the
# trigger listeners, the flow sync from disk, the trigger dispatcher, the audit cleanup and the telemetry
# writer. The background executor holds none: what it starts is a job, and the pause looks for those.
@contextlib.contextmanager
def writing(
    kind: str = "loop", *, method: str | None = None, path: str | None = None, name: str | None = None
) -> Iterator[bool]:
    """Hold a place among the changes a pause waits for, and say whether this one may go ahead.

    The place is taken before the pause is asked about. A pause that is written just after
    finds the place held and waits for the change. One that was written just before is seen
    here, and the change does not go ahead. Asking first would leave a gap between the two.

    The arguments say what holds the place: a "request" by its method and path, a "websocket"
    by its path, a "loop" by its name. They are what under_way() tells.

    With the feature off there is no pause to wait, so no place is taken and no lock.
    """
    if not FEATURE_FLAGS.instance_migration:
        yield True
        return
    held = next(_places)
    _held[held] = {"kind": kind, "method": method, "path": path, "name": name, "since": time.time()}
    place = None
    try:
        let_in = True
        if fcntl:
            try:
                place = _lock(fcntl.LOCK_SH)
            except BlockingIOError:
                # A pause holds the lock for itself, the instant it checks that nothing is going.
                let_in = False
            except OSError:
                # No lock to share in a CONFIG_DIR this process cannot use. A pause cannot take it
                # either and is refused, so no change has to be stopped for it.
                pass
        yield let_in and not is_paused()
    finally:
        if place is not None:
            os.close(place)
        del _held[held]


async def drained(seconds: float) -> bool:
    """Wait until no change is still going, in any worker. False when the time is up and one still is."""
    deadline = time.monotonic() + seconds
    # Other processes hold the lock, so there is no event to wait on.
    while not _still():
        if time.monotonic() >= deadline:
            return False
        await asyncio.sleep(_DRAIN_POLL)
    return True


def under_way() -> dict[str, Any]:
    """What a pause is still waiting for, to tell the admin when it gives up.

    "changes" are the places this worker holds, the oldest first, each with what holds it and
    since when. "elsewhere" says that another worker holds one. It shows only once this worker
    holds none: the lock says that a place is held and never whose.
    """
    changes = [
        {**change, "since": datetime.fromtimestamp(change["since"], timezone.utc).isoformat()}
        for change in sorted(_held.values(), key=lambda change: change["since"])
    ]
    # ponytail: a change in another worker is not named. Give each place a file of its own that says
    # what holds it, in place of the one shared lock, if admins of several workers need the names.
    return {"changes": changes, "elsewhere": not changes and not _still()}


def _still() -> bool:
    if _held:
        return False
    if fcntl is None:
        return True
    try:
        # Taken only when no worker holds a place, and let go at once.
        os.close(_lock(fcntl.LOCK_EX))
    except BlockingIOError:
        return False
    return True


def _lock(mode: int) -> int:
    """Take the lock that workers share, without waiting. BlockingIOError when another holder is in the way."""
    path = Path(get_settings_service().settings.config_dir) / "migrations" / "pause.lock"
    # ponytail: flock needs a CONFIG_DIR that every worker shares, and over NFS it is one lock per
    # process, which is why this worker's own changes are counted as well.
    try:
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    except FileNotFoundError:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, mode | fcntl.LOCK_NB)
    except OSError:
        os.close(descriptor)
        raise
    return descriptor


class MigrationPauseMiddleware:
    """Refuses, while the pause is on, every request that could change the instance.

    Pure ASGI so that it also sees websocket connections: voice mode writes messages
    over one.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] not in {"http", "websocket"} or _passes_while_paused(scope):
            await self.app(scope, receive, send)
            return
        # Held for the whole of the request, its upload and its response included.
        kind = "request" if scope["type"] == "http" else "websocket"
        with writing(kind, method=scope.get("method"), path=_path(scope)) as let_in:
            if let_in:
                await self.app(scope, receive, send)
                return
        # On a websocket scope the same response refuses the handshake.
        response = JSONResponse({"detail": "This instance is being migrated."}, status_code=503)
        await response(scope, receive, send)


def _passes_while_paused(scope) -> bool:
    if scope.get("method") in _READ_METHODS:
        return True
    path = _path(scope)
    return path in _ALLOWED_PATHS or f"{path}/".startswith(_ALLOWED_PREFIX)


def _path(scope) -> str:
    """The path the router matches, which leaves out a configured root path. Never the query: it can hold a key."""
    path, root_path = scope["path"], scope.get("root_path", "")
    if root_path and path.startswith(f"{root_path}/"):
        path = path[len(root_path) :]
    return path
