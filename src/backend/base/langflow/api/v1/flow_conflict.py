"""Optimistic concurrency for flow writes.

Every write that changes a flow's graph rotates ``Flow.version_token``. A client
sends the token it last read in an ``If-Match`` header; when that token no longer
matches, the write is refused with ``409`` instead of overwriting whoever wrote
in between.

The header is optional by design. Without it a request behaves exactly as it did
before preconditions existed, which is what keeps every existing API client and
every pre-upgrade row working unchanged.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import BaseModel
from sqlmodel import select, update

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

FLOW_VERSION_CONFLICT_CODE = "flow_version_conflict"

UNKNOWN_AUTHOR = "Someone"


def parse_if_match(raw: str | None) -> UUID | None:
    """Return the token carried by an ``If-Match`` header, or None when absent.

    Quotes and the weak-validator prefix are accepted so a client using a standard
    HTTP ETag library interoperates. A malformed value is rejected rather than
    ignored: treating it as absent would silently downgrade the request to an
    unconditional write, which is the failure this whole mechanism exists to stop.
    """
    if raw is None:
        return None
    token = raw.strip()
    if token.startswith("W/"):
        token = token[2:].strip()
    token = token.strip('"')
    if not token:
        return None
    try:
        return UUID(token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid If-Match header: expected a version token") from exc


async def resolve_author_name(session: AsyncSession, user_id: UUID | None) -> str | None:
    """Resolve a user id to the name shown to people.

    ``User.username`` is the only human-readable identity in the schema, so it is
    what the interface shows. A deleted author resolves to None and is rendered as
    an unknown author rather than a blank or a crash.
    """
    if user_id is None:
        return None
    result = await session.exec(select(User.username).where(User.id == user_id))
    return result.first()


def build_conflict_detail(
    *,
    flow_id: UUID,
    expected: UUID | None,
    current: UUID | None,
    author_id: UUID | None,
    author_name: str | None,
    modified_at: Any = None,
) -> dict[str, Any]:
    """Build the body of a 409 so the client can name the other person."""
    return {
        "code": FLOW_VERSION_CONFLICT_CODE,
        "message": "This flow was changed by someone else after you loaded it.",
        "flow_id": str(flow_id),
        "expected_version_token": str(expected) if expected else None,
        "current_version_token": str(current) if current else None,
        "modified_by": {
            "id": str(author_id) if author_id else None,
            "username": author_name,
        },
        "modified_at": modified_at.isoformat() if modified_at is not None else None,
    }


async def ensure_version_precondition(
    session: AsyncSession,
    db_flow: Flow,
    expected: UUID | None,
) -> None:
    """Refuse the write when *expected* is not the flow's current token.

    A NULL token on the row means it was last written before this mechanism
    existed. There is nothing to compare against, so the write proceeds — a
    legacy row must not become unsaveable just because the client learned to
    send a precondition.
    """
    if expected is None or db_flow.version_token is None:
        return
    if db_flow.version_token == expected:
        return

    author_name = await resolve_author_name(session, db_flow.last_modified_by)
    raise HTTPException(
        status_code=409,
        detail=build_conflict_detail(
            flow_id=db_flow.id,
            expected=expected,
            current=db_flow.version_token,
            author_id=db_flow.last_modified_by,
            author_name=author_name,
            modified_at=db_flow.updated_at,
        ),
    )


class FlowVersionState(BaseModel):
    """Just enough to tell whether an open editor is looking at a stale flow.

    Deliberately its own endpoint rather than fields on ``FlowRead``: the author's
    name needs a lookup, and putting that on the shared read model would run it
    once per row on every list endpoint.
    """

    version_token: UUID | None
    last_modified_by: UUID | None
    last_modified_by_username: str | None
    updated_at: datetime | None


async def build_version_state(session: AsyncSession, db_flow: Flow) -> FlowVersionState:
    return FlowVersionState(
        version_token=db_flow.version_token,
        last_modified_by=db_flow.last_modified_by,
        last_modified_by_username=await resolve_author_name(session, db_flow.last_modified_by),
        updated_at=db_flow.updated_at,
    )


async def claim_version_token(
    session: AsyncSession,
    db_flow: Flow,
    expected: UUID | None,
) -> UUID | None:
    """Take the right to write, atomically, and return the token that was claimed.

    Comparing in Python after a ``SELECT ... FOR UPDATE`` is not enough: SQLite
    ignores ``FOR UPDATE`` entirely, so concurrent writers all read the same token,
    all pass the comparison, and all write — six simultaneous saves were accepted
    where one should have been, which is precisely the lost update this exists to
    stop. A single conditional UPDATE is indivisible on every backend: only the
    writer that moves the row off *expected* proceeds.

    Returns the newly claimed token, or None when there was nothing to claim
    (no precondition sent, or a legacy row that has no token to compare).
    """
    if expected is None or db_flow.version_token is None:
        return None

    claimed = uuid4()
    result = await session.exec(
        update(Flow)
        .where(Flow.id == db_flow.id, Flow.version_token == expected)
        .values(version_token=claimed)
    )
    if result.rowcount == 0:
        # No rollback here: rowcount 0 means nothing was written, and rolling back
        # expires the caller's ORM objects — a later attribute access then raised
        # MissingGreenlet and a loser got an opaque 500 instead of its conflict.
        refreshed = (await session.exec(select(Flow).where(Flow.id == db_flow.id))).first()
        current = refreshed.version_token if refreshed else None
        author_id = refreshed.last_modified_by if refreshed else None
        raise HTTPException(
            status_code=409,
            detail=build_conflict_detail(
                flow_id=db_flow.id,
                expected=expected,
                current=current,
                author_id=author_id,
                author_name=await resolve_author_name(session, author_id),
                modified_at=refreshed.updated_at if refreshed else None,
            ),
        )
    return claimed
