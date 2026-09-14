"""Regression tests for the DbSession dependency's commit ordering.

``injectable_session_scope`` commits in the teardown of a dependency with
yield. FastAPI unwinds a *request*-scoped teardown after the response has
already been sent, so at request scope ``POST /api/v1/flows/`` answered 201
with an id whose row was not committed yet and an immediate read-back could
observe a 404. Declaring the dependency with ``scope="function"`` moves the
teardown ahead of the response send.

These tests pin that ordering and the single-session invariant that goes with
it, so neither a local edit nor a FastAPI upgrade can reintroduce the window
silently.
"""

from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from langflow.api.utils.core import DbSession
from lfx.services.deps import injectable_session_scope
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession


def _http_scope(path: str) -> dict:
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "scheme": "http",
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 1),
        "server": ("testserver", 80),
    }


async def _drive(app: FastAPI, path: str, on_body: list) -> bytes:
    """Call *app* as a raw ASGI app so response sends are observable."""
    body = b""

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        nonlocal body
        if message["type"] == "http.response.body":
            body += message.get("body", b"")
            if not message.get("more_body"):
                on_body.append("response_sent")

    await app(_http_scope(path), receive, send)
    return body


@pytest.mark.usefixtures("client")
async def test_db_session_commits_before_the_response_is_sent(monkeypatch):
    """The auto-commit must land before the client can read the id back."""
    events: list[str] = []
    original_commit = SQLModelAsyncSession.commit

    async def spy_commit(self):
        events.append("commit")
        return await original_commit(self)

    monkeypatch.setattr(SQLModelAsyncSession, "commit", spy_commit)

    app = FastAPI()

    @app.get("/probe")
    async def probe(session: DbSession):  # noqa: ARG001
        return {"ok": True}

    await _drive(app, "/probe", events)

    assert "commit" in events, "the session dependency never committed"
    assert events.index("commit") < events.index("response_sent"), f"commit ran after the response was sent: {events}"


@pytest.mark.usefixtures("client")
async def test_db_session_is_shared_with_nested_session_dependencies():
    """A mixed scope would silently hand the request two distinct sessions.

    FastAPI includes the dependency scope in its cache key, so an
    ``injectable_session_scope`` site that omits ``scope="function"`` (the auth
    chain declares several) stops sharing the handler's session.
    """
    app = FastAPI()

    async def auth_like(db: Annotated[object, Depends(injectable_session_scope, scope="function")]):
        return db

    @app.get("/probe")
    async def probe(session: DbSession, auth_session: Annotated[object, Depends(auth_like)]):
        return {"same": session is auth_session}

    body = await _drive(app, "/probe", [])

    assert b'"same":true' in body.replace(b" ", b""), (
        "the handler and a nested session dependency resolved different sessions"
    )
