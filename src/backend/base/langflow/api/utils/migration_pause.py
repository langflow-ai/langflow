"""The write pause that keeps an instance still while its data is copied to a new instance.

The copy runs while this server keeps serving, and a write that lands during it is
lost without a report. While the pause is on, the middleware refuses every request
that could change the instance, and the loops that write without a request skip
their work by asking is_paused().

The pause is a field of the migration record, CONFIG_DIR/migrations/migration.json:

    "pause": {"frozen_at": "<ISO time>", "frozen_by": "<username>"}

It lives outside the database because the database is what moves: a flag stored
there would travel to the new instance, which would then boot refusing writes.
"""

from __future__ import annotations

import json
from pathlib import Path

from lfx.services.settings.feature_flags import FEATURE_FLAGS
from starlette.responses import JSONResponse

from langflow.services.deps import get_settings_service

_READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# What the admin still needs: a session, and the migration steps, which include ending the pause.
_ALLOWED_PATHS = frozenset({"/api/v1/login", "/api/v1/refresh", "/api/v1/logout", "/api/v1/auto_login"})
_ALLOWED_PREFIX = "/api/v1/migration/"

# Which record file was last read, and what it said.
_seen: tuple[str, int, int, int] | None = None
_paused = False


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


class MigrationPauseMiddleware:
    """Refuses, while the pause is on, every request that could change the instance.

    Pure ASGI so that it also sees websocket connections: voice mode writes messages
    over one.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] in {"http", "websocket"} and not _passes_while_paused(scope) and is_paused():
            # On a websocket scope the same response refuses the handshake.
            response = JSONResponse({"detail": "This instance is being migrated."}, status_code=503)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


def _passes_while_paused(scope) -> bool:
    if scope.get("method") in _READ_METHODS:
        return True
    # The path the router matches, which leaves out a configured root path.
    path, root_path = scope["path"], scope.get("root_path", "")
    if root_path and path.startswith(f"{root_path}/"):
        path = path[len(root_path) :]
    return path in _ALLOWED_PATHS or f"{path}/".startswith(_ALLOWED_PREFIX)
