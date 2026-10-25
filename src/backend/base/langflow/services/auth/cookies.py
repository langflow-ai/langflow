"""Keep native authentication cookies separate for each configured URL prefix."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

if TYPE_CHECKING:
    from starlette.requests import HTTPConnection


def auth_cookie_name(name: str, connection: HTTPConnection) -> str:
    """Match the frontend cookie names without trusting forwarded root paths."""
    app = connection.scope.get("app")
    prefix = app.root_path.strip().rstrip("/") if app is not None else ""
    return f"{name}_{quote(prefix, safe='')}" if prefix else name
