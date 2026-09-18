"""Safe recipient-directory response schemas."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class AuthorizationRecipientRead(BaseModel):
    id: UUID
    kind: Literal["user", "team"]
    display_name: str
    avatar: str | None = None


class AuthorizationRecipientPage(BaseModel):
    items: list[AuthorizationRecipientRead]
    has_more: bool
    next_offset: int | None = None


__all__ = ["AuthorizationRecipientPage", "AuthorizationRecipientRead"]
