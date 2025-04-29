from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from loguru import logger
from sqlmodel import col, delete, select

from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.vertex_builds.model import VertexBuildTable
from langflow.services.deps import get_settings_service, get_storage_service, session_scope

if TYPE_CHECKING:
    from langflow.services.storage.service import StorageService


async def cleanup_orphaned_records() -> None:
    """Clean up all records that reference non-existent flows."""
    from langflow.services.database.models.flow.model import Flow

    async with session_scope() as session:
        # Create a subquery of existing flow IDs
        flow_ids_subquery = select(Flow.id)

        # Tables that have flow_id foreign keys
        tables: list[type[VertexBuildTable | MessageTable | TransactionTable]] = [
            MessageTable,
            VertexBuildTable,
            TransactionTable,
        ]

        for table in tables:
            try:
                # Get distinct orphaned flow IDs from the table
                orphaned_flow_ids = (
                    await session.exec(
                        select(col(table.flow_id).distinct()).where(col(table.flow_id).not_in(flow_ids_subquery))
                    )
                ).all()

                if orphaned_flow_ids:
                    logger.debug(f"Found {len(orphaned_flow_ids)} orphaned flow IDs in {table.__name__}")

                    # Delete all orphaned records in a single query
                    await session.exec(delete(table).where(col(table.flow_id).in_(orphaned_flow_ids)))

                    # Clean up any associated storage files
                    storage_service: StorageService = get_storage_service()
                    for flow_id in orphaned_flow_ids:
                        try:
                            files = await storage_service.list_files(str(flow_id))
                            for file in files:
                                try:
                                    await storage_service.delete_file(str(flow_id), file)
                                except Exception as exc:  # noqa: BLE001
                                    logger.error(f"Failed to delete file {file} for flow {flow_id}: {exc!s}")
                            # Delete the flow directory after all files are deleted
                            flow_dir = storage_service.data_dir / str(flow_id)
                            if await flow_dir.exists():
                                await flow_dir.rmdir()
                        except Exception as exc:  # noqa: BLE001
                            logger.error(f"Failed to list files for flow {flow_id}: {exc!s}")

                    await session.commit()
                    logger.debug(f"Successfully deleted orphaned records from {table.__name__}")

            except Exception as exc:  # noqa: BLE001
                logger.error(f"Error cleaning up orphaned records in {table.__name__}: {exc!s}")
                await session.rollback()


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
        logger.debug("Started database cleanup worker")

    async def stop(self):
        """Stop the cleanup worker gracefully."""
        if self._task is None:
            logger.warning("Cleanup worker is not running")
            return

        logger.debug("Stopping database cleanup worker...")
        self._stop_event.set()
        await self._task
        self._task = None
        logger.debug("Database cleanup worker stopped")

    async def _run(self):
        """Run the cleanup worker until stopped."""
        settings = get_settings_service().settings
        while not self._stop_event.is_set():
            try:
                # Clean up any orphaned records
                await cleanup_orphaned_records()
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


# Create a global instance of the worker
cleanup_worker = CleanupWorker()
