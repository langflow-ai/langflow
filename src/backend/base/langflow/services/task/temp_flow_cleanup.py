from __future__ import annotations

import asyncio
import contextlib
import datetime
import uuid
from typing import TYPE_CHECKING

from loguru import logger
from sqlmodel import select

from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.vertex_builds.model import VertexBuildTable
from langflow.services.deps import get_settings_service, get_storage_service, session_scope

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.flow.model import Flow


class CleanupWorker:
    def __init__(self) -> None:
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def start(self):
        """Start the cleanup worker."""
        if self._task is not None:
            logger.warning("Cleanup worker is already running")
            return

        self._task = asyncio.create_task(self._run())
        logger.info("Started public flow cleanup worker")

    async def stop(self):
        """Stop the cleanup worker gracefully."""
        if self._task is None:
            logger.warning("Cleanup worker is not running")
            return

        logger.info("Stopping public flow cleanup worker...")
        self._stop_event.set()
        await self._task
        self._task = None
        logger.info("Public flow cleanup worker stopped")

    async def _run(self):
        """Run the cleanup worker until stopped."""
        from langflow.services.database.models.flow.model import AccessTypeEnum, Flow

        settings = get_settings_service().settings
        while not self._stop_event.is_set():
            # Only run if there are public flows
            async with session_scope() as session:
                public_flows = (await session.exec(select(Flow).where(Flow.access_type == AccessTypeEnum.PUBLIC))).all()
                if public_flows:
                    try:
                        await cleanup_expired_public_flows(public_flows, session)
                    except Exception as exc:  # noqa: BLE001
                        logger.error(f"Error in cleanup worker: {exc!s}")

            try:
                # Create a task for the timeout
                sleep_task = asyncio.create_task(asyncio.sleep(settings.public_flow_cleanup_interval))
                # Create a task for the stop event
                stop_task = asyncio.create_task(self._stop_event.wait())

                # Wait for either the timeout or the stop event
                done, pending = await asyncio.wait([sleep_task, stop_task], return_when=asyncio.FIRST_COMPLETED)

                # Cancel any pending tasks
                for task in pending:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

                # If the stop event completed, break the loop
                if stop_task in done:
                    break

            except Exception as exc:  # noqa: BLE001
                logger.error(f"Error in cleanup worker sleep: {exc!s}")
                # Sleep a minimum amount in case of errors
                await asyncio.sleep(60)


def get_public_flow_id(original_flow_id: uuid.UUID) -> uuid.UUID:
    """Generate the UUID5 for a public flow based on its original ID."""
    new_id = f"publish_{original_flow_id}"
    return uuid.uuid5(uuid.NAMESPACE_DNS, new_id)


async def cleanup_public_flow_data(flow_id: uuid.UUID, session: AsyncSession) -> None:
    """Clean up all data related to a public flow."""
    try:
        # Delete all related data in a single transaction
        tables = [MessageTable, VertexBuildTable, TransactionTable]
        for table in tables:
            items = (await session.exec(select(table).where(table.flow_id == flow_id))).all()
            for item in items:
                await session.delete(item)

        await session.commit()
        logger.info(f"Successfully cleaned up public flow {flow_id}")
    except Exception as exc:
        logger.error(f"Error cleaning up public flow {flow_id}: {exc!s}")
        await session.rollback()
        raise


async def cleanup_expired_public_flows(public_flows: list[Flow], session: AsyncSession) -> None:
    """Clean up all expired public flows."""
    from langflow.services.database.models.flow.model import AccessTypeEnum, Flow

    settings = get_settings_service().settings
    expiration_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        seconds=settings.public_flow_expiration
    )

    # Find all public flows that have expired
    public_flows = (
        await session.exec(
            select(Flow).where(
                Flow.access_type == AccessTypeEnum.PUBLIC,
                Flow.updated_at < expiration_time,
            )
        )
    ).all()

    storage_service = get_storage_service()
    for flow in public_flows:
        public_flow_id = get_public_flow_id(flow.id)

        # Clean up database records
        try:
            await cleanup_public_flow_data(public_flow_id, session)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Failed to clean up flow {flow.id}: {exc!s}")
            continue

        # Clean up storage files
        try:
            files = await storage_service.list_files(str(public_flow_id))
            for file in files:
                try:
                    await storage_service.delete_file(str(public_flow_id), file)
                except Exception as exc:  # noqa: BLE001
                    logger.error(f"Failed to delete file {file} for flow {public_flow_id}: {exc!s}")
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Failed to list files for flow {public_flow_id}: {exc!s}")


# Create a global instance of the worker
cleanup_worker = CleanupWorker()
