from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from .deps import get_db_service

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


async def get_no_org_session() -> AsyncGenerator[AsyncSession, None]:
    """Retrieve a database session without organisation scoping."""
    async with get_db_service(use_organisation=False).with_session() as session:
        yield session


DbNoOrgSession = Annotated[AsyncSession, Depends(get_no_org_session)]
