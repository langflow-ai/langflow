"""Message queue service for batched message writes."""

from langflow.services.message_queue.service import MessageQueueService

__all__ = ["MessageQueueService", "get_message_queue_service"]

_message_queue_service: MessageQueueService | None = None


def get_message_queue_service() -> MessageQueueService:
    """Get the global message queue service instance."""
    global _message_queue_service  # noqa: PLW0603
    if _message_queue_service is None:
        _message_queue_service = MessageQueueService()
    return _message_queue_service
