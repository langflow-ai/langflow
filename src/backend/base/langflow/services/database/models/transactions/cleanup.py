"""Periodic cleanup task for transaction logs and vertex builds."""

import asyncio
import contextlib
import threading
from typing import TYPE_CHECKING

from sqlmodel import select, text
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.logging.logger import logger
from langflow.services.database.models.transactions.crud import cleanup_old_transactions_for_flow
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.utils import session_getter
from langflow.services.deps import get_db_service, get_settings_service

if TYPE_CHECKING:
    from uuid import UUID


# Process-level coordination
class _ProcessState:
    """Encapsulates process-level state to avoid global variables."""

    def __init__(self):
        self.lock = threading.Lock()
        self.task_started = False


_process_state = _ProcessState()

# Advisory lock constants for PostgreSQL cross-instance coordination
CLEANUP_LOCK_ID = 42424242  # Arbitrary but consistent lock ID


class TransactionCleanupTask:
    """Periodic task to clean up old transactions and vertex builds with graceful failure handling."""

    def __init__(self, interval_seconds: int = 600):
        self.interval_seconds = interval_seconds
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the periodic cleanup task."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_periodic_cleanup())
        logger.info(f"Started transaction and vertex builds cleanup task (interval: {self.interval_seconds}s)")

    async def stop(self) -> None:
        """Stop the periodic cleanup task."""
        if not self._running:
            return

        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        logger.info("Stopped transaction and vertex builds cleanup task")

    async def _run_periodic_cleanup(self) -> None:
        """Main loop for periodic cleanup."""
        while self._running:
            try:
                await asyncio.sleep(self.interval_seconds)
                if self._running:  # Check again after sleep
                    await self._cleanup_all_flows()
            except asyncio.CancelledError:
                logger.debug("Periodic cleanup cancelled")
            except Exception as e:  # noqa: BLE001
                # Log error but don't stop the task - broad exception handling is intentional
                logger.warning(f"Periodic cleanup encountered error (will retry): {e}")

    def _is_postgresql_database(self, session: AsyncSession) -> bool:
        """Check if we're using a PostgreSQL database by examining the dialect."""
        try:
            # Check the database dialect name from SQLAlchemy engine
            dialect_name = session.get_bind().dialect.name
        except Exception:  # noqa: BLE001
            # Fallback: if we can't determine the dialect, assume it's not PostgreSQL
            return False
        else:
            return dialect_name == "postgresql"

    async def _try_acquire_advisory_lock(self, session: AsyncSession) -> bool:
        """Try to acquire a PostgreSQL advisory lock for cross-instance coordination."""
        try:
            # Check if we're using PostgreSQL by examining the database dialect
            if not self._is_postgresql_database(session):
                # For non-PostgreSQL databases, always allow cleanup
                return True

            # Try to acquire advisory lock (non-blocking)
            result = await session.exec(text(f"SELECT pg_try_advisory_lock({CLEANUP_LOCK_ID})"))
            acquired = result.one()

            if acquired:
                logger.debug("Acquired PostgreSQL advisory lock for cleanup")
            else:
                logger.debug("Could not acquire PostgreSQL advisory lock - another instance is running cleanup")

            return bool(acquired)
        except Exception as e:  # noqa: BLE001
            # If advisory lock fails, fall back to allowing cleanup (better than no cleanup)
            logger.debug(f"Advisory lock attempt failed, proceeding anyway: {e}")
            return True

    async def _release_advisory_lock(self, session: AsyncSession) -> None:
        """Release the PostgreSQL advisory lock."""
        try:
            if self._is_postgresql_database(session):
                await session.exec(text(f"SELECT pg_advisory_unlock({CLEANUP_LOCK_ID})"))
                logger.debug("Released PostgreSQL advisory lock")
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Failed to release advisory lock (not critical): {e}")

    async def _cleanup_all_flows(self) -> None:
        """Clean up transactions and vertex builds for all flows, with graceful failure handling."""
        settings = get_settings_service().settings

        # Try to acquire advisory lock for cross-instance coordination
        async with session_getter(get_db_service()) as session:
            if not await self._try_acquire_advisory_lock(session):
                logger.debug("Skipping cleanup cycle - task is already running")
                return

            try:
                # Clean up transactions if enabled
                if settings.transactions_storage_enabled:
                    await self._cleanup_transactions()

                # Clean up vertex builds if enabled
                if settings.vertex_builds_storage_enabled:
                    await self._cleanup_vertex_builds()
            finally:
                # Always release the lock
                await self._release_advisory_lock(session)

    async def _cleanup_transactions(self) -> None:
        """Clean up transactions with graceful failure handling."""
        try:
            # Get list of flows that have transactions
            async with session_getter(get_db_service()) as session:
                # Set a short timeout for the entire cleanup operation
                timeout_task = asyncio.create_task(self._cleanup_transaction_flows_with_timeout(session))
                try:
                    await asyncio.wait_for(timeout_task, timeout=30.0)  # 30 second timeout
                except asyncio.TimeoutError:
                    logger.debug("Transaction cleanup timed out (likely due to locks), will retry next cycle")
                    timeout_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await timeout_task

        except Exception as e:  # noqa: BLE001
            # Silently handle any database errors (locks, connection issues, etc.) - broad handling is intentional
            await logger.awarning(f"Transaction cleanup failed gracefully: {e}")

    async def _cleanup_vertex_builds(self) -> None:
        """Clean up vertex builds with graceful failure handling."""
        try:
            # Get list of flows that have vertex builds
            async with session_getter(get_db_service()) as session:
                # Set a short timeout for the entire cleanup operation
                timeout_task = asyncio.create_task(self._cleanup_vertex_build_flows_with_timeout(session))
                try:
                    await asyncio.wait_for(timeout_task, timeout=30.0)  # 30 second timeout
                except asyncio.TimeoutError:
                    logger.debug("Vertex builds cleanup timed out (likely due to locks), will retry next cycle")
                    timeout_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await timeout_task

        except Exception as e:  # noqa: BLE001
            # Silently handle any database errors (locks, connection issues, etc.) - broad handling is intentional
            logger.debug(f"Vertex builds cleanup failed gracefully: {e}")

    async def _cleanup_transaction_flows_with_timeout(self, session: AsyncSession) -> None:
        """Clean up transaction flows with timeout handling."""
        # Get unique flow IDs that have transactions
        stmt = select(TransactionTable.flow_id).distinct()
        result = (await session.exec(stmt)).all()
        flow_ids: list[UUID] = list(result)

        if not flow_ids:
            logger.debug("No transactions found for cleanup")
            return

        logger.debug(f"Starting cleanup for {len(flow_ids)} flows")
        cleaned_flows = 0
        total_deleted = 0

        # Clean up each flow individually with error isolation
        for flow_id in flow_ids:
            try:
                # Use a separate session for each flow to isolate lock issues
                async with session_getter(get_db_service()) as flow_session:
                    deleted_count = await cleanup_old_transactions_for_flow(flow_session, flow_id)
                    if deleted_count > 0:
                        total_deleted += deleted_count
                        cleaned_flows += 1

            except Exception as e:  # noqa: BLE001
                # If one flow fails (e.g., locked), continue with others - broad handling is intentional
                logger.debug(f"Cleanup failed for flow {flow_id} (will retry later): {e}")
                continue

        if cleaned_flows > 0:
            logger.info(
                f"Transaction cleanup completed: {total_deleted} transactions removed from {cleaned_flows} flows"
            )
        else:
            logger.debug("Transaction cleanup cycle completed (no transactions removed)")

    async def _cleanup_vertex_build_flows_with_timeout(self, session: AsyncSession) -> None:
        """Clean up vertex build flows with timeout handling."""
        # Import here to avoid circular imports
        from langflow.services.database.models.vertex_builds.crud import cleanup_old_vertex_builds_for_flow
        from langflow.services.database.models.vertex_builds.model import VertexBuildTable

        # Get unique flow IDs that have vertex builds
        stmt = select(VertexBuildTable.flow_id).distinct()
        result = (await session.exec(stmt)).all()
        flow_ids: list[UUID] = list(result)

        if not flow_ids:
            logger.debug("No vertex builds found for cleanup")
            return

        logger.debug(f"Starting vertex builds cleanup for {len(flow_ids)} flows")
        cleaned_flows = 0
        total_deleted = 0

        # Clean up each flow individually with error isolation
        for flow_id in flow_ids:
            try:
                # Use a separate session for each flow to isolate lock issues
                async with session_getter(get_db_service()) as flow_session:
                    deleted_count = await cleanup_old_vertex_builds_for_flow(flow_session, flow_id)
                    if deleted_count > 0:
                        total_deleted += deleted_count
                        cleaned_flows += 1

            except Exception as e:  # noqa: BLE001
                # If one flow fails (e.g., locked), continue with others - broad handling is intentional
                logger.debug(f"Vertex builds cleanup failed for flow {flow_id} (will retry later): {e}")
                continue

        if cleaned_flows > 0:
            logger.info(f"Vertex builds cleanup completed: {total_deleted} builds removed from {cleaned_flows} flows")
        else:
            logger.debug("Vertex builds cleanup cycle completed (no builds removed)")

    async def cleanup_now(self) -> None:
        """Manually trigger cleanup (useful for testing or manual maintenance)."""
        logger.info("Manual cleanup triggered")
        await self._cleanup_all_flows()


# Global instance
_cleanup_task: TransactionCleanupTask | None = None


def get_cleanup_task() -> TransactionCleanupTask:
    """Get or create the global cleanup task instance."""
    global _cleanup_task  # noqa: PLW0603
    if _cleanup_task is None:
        # Check settings for custom interval
        settings = get_settings_service().settings
        interval = getattr(settings, "transaction_cleanup_interval_seconds", 600)  # Default 10 minutes
        _cleanup_task = TransactionCleanupTask(interval_seconds=interval)
    return _cleanup_task


async def start_transaction_cleanup() -> None:
    """Start the global transaction cleanup task (one per process)."""
    # Only start once per process, regardless of how many workers call this
    with _process_state.lock:
        if _process_state.task_started:
            logger.debug("Cleanup task already started in this process")
            return

        if get_settings_service().settings.transactions_storage_enabled:
            await get_cleanup_task().start()
            _process_state.task_started = True
            logger.info("Started process-level transaction cleanup task")


async def stop_transaction_cleanup() -> None:
    """Stop the global transaction cleanup task."""
    if _cleanup_task:
        await _cleanup_task.stop()
