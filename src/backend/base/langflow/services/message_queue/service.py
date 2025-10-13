"""Message queue service for coordinating cache and batched writes."""

from typing import TYPE_CHECKING

from lfx.log.logger import logger

from langflow.schema.message import Message
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.utils import session_getter
from langflow.services.deps import get_db_service, get_settings_service
from langflow.services.message_queue.cache import MessageCache
from langflow.services.message_queue.queue import MessageWriteQueue
from lfx.services.deps import session_scope

if TYPE_CHECKING:
    from uuid import UUID


class MessageQueueService:
    """Service for managing message history with optional deferred writes.

    Coordinates an in-memory cache for fast reads and a write queue for batched
    database writes, improving performance under load.
    """

    def __init__(self):
        """Initialize the message queue service."""
        settings = get_settings_service().settings
        self.cache = MessageCache(ttl_seconds=settings.message_cache_ttl)
        self.write_queue = MessageWriteQueue(
            max_queue_size=settings.message_queue_max_size,
            batch_size=settings.message_write_batch_size,
            flush_interval=settings.message_flush_interval,
        )
        self._enabled = settings.message_deferred_writes_enabled

        if self._enabled:
            logger.info("Message deferred writes ENABLED - using cache and batching")
        else:
            logger.info("Message deferred writes DISABLED - using immediate writes")

    @property
    def enabled(self) -> bool:
        """Check if deferred writes are enabled."""
        return self._enabled

    async def start(self) -> None:
        """Start background workers if deferred writes are enabled."""
        if self._enabled:
            await self.cache.start()
            await self.write_queue.start()
            logger.info("Message queue service started with deferred writes enabled")
        else:
            logger.debug("Message queue service disabled (using immediate writes)")

    async def stop(self) -> None:
        """Stop background workers and flush pending messages."""
        if self._enabled:
            logger.info("Stopping message queue service and flushing pending messages...")
            await self.write_queue.stop()
            await self.cache.stop()
            logger.info("Message queue service stopped")

    async def add_messages(self, messages: list[MessageTable], session_id: str) -> list[MessageTable]:
        """Add messages with optional deferred writes.

        Args:
            messages: Messages to add
            session_id: Session ID for the messages

        Returns:
            List of message tables (formatted and ready to return)
        """
        import json

        # Deferred mode: cache + queue (non-blocking)
        await self.cache.add_messages(session_id, messages)
        for message in messages:
            await self.write_queue.queue_message(message)

        # Format messages for return (same as immediate mode)
        formatted_messages = []
        for msg in messages:
            msg.properties = json.loads(msg.properties) if isinstance(msg.properties, str) else msg.properties  # type: ignore[arg-type]
            msg.content_blocks = [json.loads(j) if isinstance(j, str) else j for j in msg.content_blocks]  # type: ignore[arg-type]
            msg.category = msg.category or ""
            formatted_messages.append(msg)

        return formatted_messages

    async def get_messages(
        self,
        session_id: str,
        sender: str | None = None,
        sender_name: str | None = None,
        order_by: str | None = "timestamp",
        order: str | None = "DESC",
        flow_id: "UUID | None" = None,
        limit: int | None = None,
    ) -> list[Message]:
        """Get messages from cache or database.

        Args:
            session_id: Session ID to retrieve messages for
            sender: Filter by sender
            sender_name: Filter by sender name
            order_by: Field to order by
            order: Order direction (ASC/DESC)
            flow_id: Filter by flow ID
            limit: Maximum number of messages

        Returns:
            List of messages
        """
        if not self._enabled:
            # Disabled - fall through to database
            return await self._get_from_db(session_id, sender, sender_name, order_by, order, flow_id, limit)

        # Try cache first
        cached = await self.cache.get_messages(session_id)

        if cached is not None and not any([sender, sender_name, flow_id, limit]):
            # Cache hit and no filters - return cached messages
            messages = [await Message.create(**msg.model_dump()) for msg in cached]

            # Apply ordering
            if order_by == "timestamp":
                messages = sorted(messages, key=lambda m: m.timestamp, reverse=(order == "DESC"))

            return messages

        # Cache miss or has filters - get from database
        db_messages = await self._get_from_db(session_id, sender, sender_name, order_by, order, flow_id, limit)

        # If cache hit but had filters, merge results
        if cached is not None:
            # Merge: db messages + cached messages not yet in DB
            db_ids = {msg.id for msg in db_messages}
            cached_messages = [await Message.create(**msg.model_dump()) for msg in cached]
            missing_from_db = [msg for msg in cached_messages if msg.id not in db_ids]

            all_messages = db_messages + missing_from_db

            # Re-sort by timestamp
            all_messages = sorted(all_messages, key=lambda m: m.timestamp, reverse=(order == "DESC"))

            # Apply limit if specified
            if limit:
                all_messages = all_messages[:limit]

            return all_messages

        return db_messages

    async def _get_from_db(
        self,
        session_id: str,
        sender: str | None = None,
        sender_name: str | None = None,
        order_by: str | None = "timestamp",
        order: str | None = "DESC",
        flow_id: "UUID | None" = None,
        limit: int | None = None,
    ) -> list[Message]:
        """Get messages from database.

        Args:
            session_id: Session ID
            sender: Filter by sender
            sender_name: Filter by sender name
            order_by: Field to order by
            order: Order direction
            flow_id: Filter by flow ID
            limit: Maximum number of messages

        Returns:
            List of messages from database
        """
        from langflow.memory import _get_variable_query

        async with session_scope() as session:
            stmt = _get_variable_query(sender, sender_name, session_id, order_by, order, flow_id, limit)
            result = await session.exec(stmt)
            messages = result.all()
            return [await Message.create(**d.model_dump()) for d in messages]

    async def clear_session(self, session_id: str) -> None:
        """Clear cached messages for a session.

        Args:
            session_id: Session ID to clear
        """
        if self._enabled:
            await self.cache.clear_session(session_id)

    def get_stats(self) -> dict:
        """Get service statistics.

        Returns:
            Dictionary with cache and queue stats
        """
        if not self._enabled:
            return {"enabled": False}

        return {
            "enabled": True,
            "cache": self.cache.get_stats(),
            "queue": self.write_queue.get_stats(),
        }
