"""Shared helpers for flow collaboration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import aiofiles
from lfx.log.logger import logger

from langflow.api.v1.flows_helpers import _get_safe_flow_path

if TYPE_CHECKING:
    from uuid import UUID

    from anyio import Path
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.flow.model import Flow
    from langflow.services.storage.service import StorageService


@dataclass(frozen=True)
class FlowFilesystemSnapshot:
    path: Path | None
    existed: bool
    contents: bytes | None = None

    def __post_init__(self) -> None:
        if self.path is None and self.existed:
            msg = "Flow filesystem snapshot cannot exist without a path"
            raise ValueError(msg)
        if self.existed and self.contents is None:
            msg = "Existing flow filesystem snapshot is missing contents"
            raise ValueError(msg)


async def snapshot_flow_filesystem(
    flow: Flow,
    owner_user_id: UUID,
    storage_service: StorageService,
) -> FlowFilesystemSnapshot:
    if not flow.fs_path:
        return FlowFilesystemSnapshot(path=None, existed=False)

    path = _get_safe_flow_path(flow.fs_path, owner_user_id, storage_service)
    if not await path.exists():
        return FlowFilesystemSnapshot(path=path, existed=False)

    async with aiofiles.open(str(path), "rb") as file:
        contents = await file.read()
    return FlowFilesystemSnapshot(path=path, existed=True, contents=contents)


async def restore_flow_filesystem(snapshot: FlowFilesystemSnapshot) -> None:
    if snapshot.path is None:
        return

    if snapshot.existed:
        await snapshot.path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(str(snapshot.path), "wb") as file:
            await file.write(snapshot.contents)
        return

    if await snapshot.path.exists():
        await snapshot.path.unlink()


async def rollback_and_restore_flow_filesystem(
    session: AsyncSession,
    snapshot: FlowFilesystemSnapshot,
) -> None:
    try:
        await session.rollback()
    except Exception as exc:  # noqa: BLE001
        await logger.aexception(
            "Failed to roll back flow operation transaction before filesystem restore: %s",
            exc,
        )
    try:
        await restore_flow_filesystem(snapshot)
    except Exception as restore_exc:  # noqa: BLE001
        await logger.aexception(
            "Failed to restore flow filesystem mirror; "
            "filesystem mirror may be out of sync with the database flow row: %s",
            restore_exc,
        )
