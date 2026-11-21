"""Protect legacy credential-bearing files from restricted API keys."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import HTTPException

from langflow.services.auth.context import current_auth_is_restricted_api_key
from langflow.services.authorization.audit import audit_decision

if TYPE_CHECKING:
    from collections.abc import Iterable
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


def is_mcp_credential_file(name: str) -> bool:
    stem = Path(name).stem.casefold()
    return stem == "_mcp_servers" or stem.startswith("_mcp_servers_")


async def ensure_mcp_credential_file_access(
    *,
    user_id: UUID,
    names: Iterable[str],
    session: AsyncSession | None = None,
) -> None:
    if not current_auth_is_restricted_api_key() or not any(is_mcp_credential_file(name) for name in names):
        return
    # Call before any mutation. A durable audit must not wait for another
    # connection while the candidate-file lookup holds the only pool slot.
    if session is not None:
        await session.rollback()
    await audit_decision(
        user_id=user_id,
        action="credential:access",
        obj="credential:*",
        result="deny",
        details={"reason": "restricted_api_key_mcp_credential_file"},
    )
    raise HTTPException(status_code=404, detail="File not found")
