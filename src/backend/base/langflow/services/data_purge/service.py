"""Data purge service for periodic removal of old data from vertex_build, message, and transaction tables."""

import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from langflow.logging.logger import logger
from langflow.services.base import Service
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.vertex_builds.model import VertexBuildTable
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.deps import get_settings_service
from sqlmodel import delete, select
from sqlmodel.ext.asyncio.session import AsyncSession


def parse_time_interval(interval_str: str) -> Optional[timedelta]:
    """
    Parse time interval string (e.g., '2h', '30m', '1d') to timedelta.
    
    Args:
        interval_str: Time interval string (e.g., '2h', '30m', '1d', '7d')
    
    Returns:
        timedelta object or None if parsing fails
    
    Examples:
        '1m' -> timedelta(minutes=1)
        '2h' -> timedelta(hours=2)  
        '1d' -> timedelta(days=1)
        '7d' -> timedelta(days=7)
    """
    if not interval_str or not isinstance(interval_str, str):
        return None
    
    # Match pattern like '1m', '2h', '30m', '1d' etc.
    pattern = r'^(\d+)([mhd])$'
    match = re.match(pattern, interval_str.strip().lower())
    
    if not match:
        return None
    
    value, unit = match.groups()
    value = int(value)
    
    if unit == 'm':
        return timedelta(minutes=value)
    elif unit == 'h':
        return timedelta(hours=value)
    elif unit == 'd':
        return timedelta(days=value)
    
    return None


class DataPurgeService(Service):
    """Service for periodic purge of old data from vertex_build, message, and transaction tables."""
    
    name = "data_purge_service"
    
    def __init__(self, database_service, settings_service):
        super().__init__()
        self.database_service = database_service
        self.settings_service = settings_service
        self.cleanup_task: Optional[asyncio.Task] = None
        self.cleanup_interval: Optional[timedelta] = None
        self._initialized = False
        
    async def initialize_service(self) -> None:
        """Initialize the cleanup service."""
        try:
            settings = self.settings_service.settings
            cleanup_interval_str = getattr(settings, 'data_purge_interval', None)
            
            logger.info(f"Data purge service starting - found setting: {cleanup_interval_str}")
            
            if cleanup_interval_str:
                self.cleanup_interval = parse_time_interval(cleanup_interval_str)
                if self.cleanup_interval:
                    logger.info(f"Data purge service initialized with interval: {cleanup_interval_str} ({self.cleanup_interval})")
                    await self.start_periodic_cleanup()
                    logger.info("Data purge periodic task started successfully")
                else:
                    logger.warning(f"Invalid purge interval format: {cleanup_interval_str}. Expected format: '1m', '2h', '1d', etc.")
            else:
                logger.info("Data purge service disabled (LANGFLOW_DATA_PURGE_INTERVAL not set)")
        except Exception as e:
            logger.error(f"Error initializing data purge service: {e}", exc_info=True)
    
    async def setup(self) -> None:
        """Setup the service - called automatically by the service manager."""
        if not self._initialized:
            await self.initialize_service()
            self._initialized = True
    
    async def start_periodic_cleanup(self) -> None:
        """Start the periodic cleanup task."""
        if self.cleanup_task is not None:
            self.cleanup_task.cancel()
        
        if self.cleanup_interval:
            self.cleanup_task = asyncio.create_task(self._periodic_cleanup_loop())
    
    async def stop_periodic_cleanup(self) -> None:
        """Stop the periodic cleanup task."""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            self.cleanup_task = None
    
    async def _periodic_cleanup_loop(self) -> None:
        """Main loop for periodic cleanup."""
        while True:
            try:
                if self.cleanup_interval:
                    await self.purge_old_data()
                    # Wait for the cleanup interval before next cleanup
                    await asyncio.sleep(self.cleanup_interval.total_seconds())
                else:
                    break
            except asyncio.CancelledError:
                logger.info("Data purge task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in data purge loop: {e}")
                # Wait a bit before retrying on error
                await asyncio.sleep(60)
    
    async def purge_old_data(self) -> int:
        """
        Remove all data from vertex_build, message, and transaction tables.
        
        Returns:
            Total number of records deleted
        """
        try:
            logger.info("Starting data purge operation...")
            total_deleted = 0
            
            async with self.database_service.with_session() as session:
                # Delete all vertex builds
                vertex_delete_stmt = delete(VertexBuildTable)
                vertex_result = await session.exec(vertex_delete_stmt)
                vertex_deleted = vertex_result.rowcount or 0
                total_deleted += vertex_deleted
                
                # Delete all messages
                message_delete_stmt = delete(MessageTable)
                message_result = await session.exec(message_delete_stmt)
                message_deleted = message_result.rowcount or 0
                total_deleted += message_deleted
                
                # Delete all transactions
                transaction_delete_stmt = delete(TransactionTable)
                transaction_result = await session.exec(transaction_delete_stmt)
                transaction_deleted = transaction_result.rowcount or 0
                total_deleted += transaction_deleted
                
                await session.commit()
                
                if total_deleted > 0:
                    logger.info(f"Successfully purged {total_deleted} records - VertexBuilds: {vertex_deleted}, Messages: {message_deleted}, Transactions: {transaction_deleted}")
                else:
                    logger.info("No data found to purge")
                
                return total_deleted
                
        except Exception as e:
            logger.error(f"Error purging data: {e}", exc_info=True)
            return 0
    
    async def teardown_service(self) -> None:
        """Cleanup service on shutdown."""
        await self.stop_periodic_cleanup()