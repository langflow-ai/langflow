"""Memory management functions for lfx package.

This module provides message storage and retrieval functionality adapted for lfx's
service-based architecture. It mirrors the langflow.memory API but works with
lfx's Message model and service interfaces.
"""

from uuid import UUID

from loguru import logger

from lfx.schema.message import Message
from lfx.services.deps import session_scope
from lfx.utils.util import run_until_complete


async def astore_message(
    message: Message,
    flow_id: str | UUID | None = None,
) -> list[Message]:
    """Store a message in the memory.

    Args:
        message (Message): The message to store.
        flow_id (Optional[str | UUID]): The flow ID associated with the message.
            When running from the CustomComponent you can access this using `self.graph.flow_id`.

    Returns:
        List[Message]: A list containing the stored message.

    Raises:
        ValueError: If any of the required parameters (session_id, sender, sender_name) is not provided.
    """
    if not message:
        logger.warning("No message provided.")
        return []

    if not message.session_id or not message.sender or not message.sender_name:
        msg = (
            f"All of session_id, sender, and sender_name must be provided. Session ID: {message.session_id},"
            f" Sender: {message.sender}, Sender Name: {message.sender_name}"
        )
        raise ValueError(msg)

    # Set flow_id if provided
    if flow_id:
        if isinstance(flow_id, str):
            flow_id = UUID(flow_id)
        message.flow_id = str(flow_id)

    # In lfx, we use the service architecture - this is a simplified implementation
    # that doesn't persist to database but maintains the message in memory
    # Real implementation would require a database service
    async with session_scope() as session:
        # Since we're using NoopSession by default, this doesn't actually persist
        # but maintains the same interface as langflow.memory
        try:
            # Generate an ID if not present
            if not hasattr(message, "id") or not message.id:
                try:
                    import nanoid

                    message.id = nanoid.generate()
                except ImportError:
                    # Fallback to uuid if nanoid is not available
                    import uuid

                    message.id = str(uuid.uuid4())

            await session.add(message)
            await session.commit()
            logger.debug(f"Message stored with ID: {message.id}")
        except Exception as e:
            logger.exception(f"Error storing message: {e}")
            await session.rollback()
            raise
        return [message]


def store_message(
    message: Message,
    flow_id: str | UUID | None = None,
) -> list[Message]:
    """DEPRECATED: Stores a message in the memory.

    DEPRECATED: Use `astore_message` instead.

    Args:
        message (Message): The message to store.
        flow_id (Optional[str | UUID]): The flow ID associated with the message.
            When running from the CustomComponent you can access this using `self.graph.flow_id`.

    Returns:
        List[Message]: A list containing the stored message.

    Raises:
        ValueError: If any of the required parameters (session_id, sender, sender_name) is not provided.
    """
    return run_until_complete(astore_message(message, flow_id=flow_id))


async def aupdate_messages(messages: Message | list[Message]) -> list[Message]:
    """Update stored messages.

    Args:
        messages: Message or list of messages to update.

    Returns:
        List[Message]: Updated messages.

    Raises:
        ValueError: If message is not found for update.
    """
    if not isinstance(messages, list):
        messages = [messages]

    async with session_scope() as session:
        updated_messages: list[Message] = []
        for message in messages:
            try:
                # In a real implementation, this would update the database record
                # For now, we just validate the message has an ID and return it
                if not hasattr(message, "id") or not message.id:
                    error_message = f"Message without ID cannot be updated: {message}"
                    logger.warning(error_message)
                    raise ValueError(error_message)

                # Convert flow_id to string if it's a UUID
                if message.flow_id and isinstance(message.flow_id, UUID):
                    message.flow_id = str(message.flow_id)

                await session.add(message)
                await session.commit()
                await session.refresh(message)
                updated_messages.append(message)
                logger.debug(f"Message updated: {message.id}")
            except Exception as e:
                logger.exception(f"Error updating message: {e}")
                await session.rollback()
                msg = f"Failed to update message: {e}"
                logger.error(msg)
                raise ValueError(msg) from e

        return updated_messages


async def delete_message(id_: str) -> None:
    """Delete a message from the memory.

    Args:
        id_ (str): The ID of the message to delete.
    """
    async with session_scope() as session:
        try:
            # In a real implementation, this would delete from database
            # For now, this is a no-op since we're using NoopSession
            await session.delete(id_)
            await session.commit()
            logger.debug(f"Message deleted: {id_}")
        except Exception as e:
            logger.exception(f"Error deleting message: {e}")
            raise


async def aget_messages(
    sender: str | None = None,  # noqa: ARG001
    sender_name: str | None = None,  # noqa: ARG001
    session_id: str | UUID | None = None,  # noqa: ARG001
    order_by: str | None = "timestamp",  # noqa: ARG001
    order: str | None = "DESC",  # noqa: ARG001
    flow_id: UUID | None = None,  # noqa: ARG001
    limit: int | None = None,  # noqa: ARG001
) -> list[Message]:
    """Retrieve messages based on the provided filters.

    Args:
        sender (Optional[str]): The sender of the messages (e.g., "Machine" or "User")
        sender_name (Optional[str]): The name of the sender.
        session_id (Optional[str]): The session ID associated with the messages.
        order_by (Optional[str]): The field to order the messages by. Defaults to "timestamp".
        order (Optional[str]): The order in which to retrieve the messages. Defaults to "DESC".
        flow_id (Optional[UUID]): The flow ID associated with the messages.
        limit (Optional[int]): The maximum number of messages to retrieve.

    Returns:
        List[Message]: A list of Message objects representing the retrieved messages.
    """
    async with session_scope() as session:
        try:
            # In a real implementation, this would query the database
            # For now, return empty list since we're using NoopSession
            result = await session.query()  # This returns [] from NoopSession
            logger.debug(f"Retrieved {len(result)} messages")
        except Exception as e:  # noqa: BLE001
            logger.exception(f"Error retrieving messages: {e}")
            return []
        return result


def get_messages(
    sender: str | None = None,
    sender_name: str | None = None,
    session_id: str | UUID | None = None,
    order_by: str | None = "timestamp",
    order: str | None = "DESC",
    flow_id: UUID | None = None,
    limit: int | None = None,
) -> list[Message]:
    """DEPRECATED - Retrieve messages based on the provided filters.

    DEPRECATED: Use `aget_messages` instead.
    """
    return run_until_complete(aget_messages(sender, sender_name, session_id, order_by, order, flow_id, limit))


async def adelete_messages(session_id: str) -> None:
    """Delete messages from the memory based on the provided session ID.

    Args:
        session_id (str): The session ID associated with the messages to delete.
    """
    async with session_scope() as session:
        try:
            # In a real implementation, this would delete from database
            # For now, this is a no-op since we're using NoopSession
            await session.delete(session_id)
            await session.commit()
            logger.debug(f"Messages deleted for session: {session_id}")
        except Exception as e:
            logger.exception(f"Error deleting messages: {e}")
            raise


def delete_messages(session_id: str) -> None:
    """DEPRECATED - Delete messages based on the provided session ID.

    DEPRECATED: Use `adelete_messages` instead.
    """
    return run_until_complete(adelete_messages(session_id))
