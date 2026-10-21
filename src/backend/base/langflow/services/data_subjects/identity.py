"""End-user identity rules for erasure: validation and the keys used to find their rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lfx.memory.flow_context import derive_message_owner_uuid
from lfx.services.authorization.base import PUBLIC_ANONYMOUS_ACTOR_ID
from lfx.utils.util_strings import escape_like_pattern
from lfx.workflow.end_user_identity import ANONYMOUS_SESSION_PREFIX, SCOPE_SEPARATOR
from sqlmodel import select

from langflow.services.data_subjects.errors import InvalidEndUserIdError
from langflow.services.database.models.user.model import User

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

MAX_END_USER_ID_LENGTH = 255
ANONYMOUS_PREFIX = ANONYMOUS_SESSION_PREFIX.removesuffix(SCOPE_SEPARATOR)


@dataclass(frozen=True)
class EndUserKeys:
    """Every key under which Langflow stores one end user's data."""

    raw_id: str
    message_owner_id: UUID
    session_prefix: str

    @property
    def session_like_pattern(self) -> str:
        return f"{escape_like_pattern(self.session_prefix)}%"


def normalize_end_user_id(raw: str | None) -> str:
    """Return the id exactly as the serving plane stores it, or raise."""
    value = (raw or "").strip()
    if not value:
        msg = "end_user_id is required"
        raise InvalidEndUserIdError(msg)
    if len(value) > MAX_END_USER_ID_LENGTH:
        msg = f"end_user_id must be at most {MAX_END_USER_ID_LENGTH} characters"
        raise InvalidEndUserIdError(msg)
    if SCOPE_SEPARATOR in value:
        msg = f"end_user_id must not contain '{SCOPE_SEPARATOR}': its sessions cannot be told apart"
        raise InvalidEndUserIdError(msg)
    if value == ANONYMOUS_PREFIX:
        msg = "end_user_id must not be the anonymous session namespace"
        raise InvalidEndUserIdError(msg)
    return value


def end_user_keys(raw: str) -> EndUserKeys:
    value = normalize_end_user_id(raw)
    return EndUserKeys(
        raw_id=value,
        message_owner_id=derive_message_owner_uuid(value),
        session_prefix=f"{value}{SCOPE_SEPARATOR}",
    )


async def ensure_not_an_account(session: AsyncSession, keys: EndUserKeys) -> None:
    """Refuse an end-user id whose message owner collides with a real account or the public principal."""
    if keys.message_owner_id == PUBLIC_ANONYMOUS_ACTOR_ID:
        msg = "end_user_id resolves to the shared public principal"
        raise InvalidEndUserIdError(msg)
    collision = (await session.exec(select(User.id).where(User.id == keys.message_owner_id))).first()
    if collision is not None:
        msg = "end_user_id resolves to an existing account id; erase that account as a builder instead"
        raise InvalidEndUserIdError(msg)
