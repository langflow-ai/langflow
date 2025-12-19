"""Centralized utilities for Message object operations.

This module provides safe access patterns for Message objects, particularly
for accessing the message ID which may not exist if the message hasn't
been stored in the database.

Message ID Semantics:
- Messages only have an ID after being stored in the database
- Messages that are skipped (via Component._should_skip_message) will NOT have an ID
- Always use the utilities in this module to safely access message IDs
- Never access message.id directly without checking if it exists first

Safe Access Patterns:
- Use get_message_id() when ID may or may not exist (returns None if missing)
- Use has_message_id() to check if ID exists before operations that require it
- Use require_message_id() when ID is required (raises ValueError if missing)
"""

from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from lfx.schema.message import Message


def get_message_id(message: "Message") -> str | UUID | None:
    """Safely get the message ID.
    
    This function handles multiple ways the ID might be stored:
    - Direct attribute: message.id
    - Data dict: message.data.get("id")
    - AttributeError: returns None if ID doesn't exist
    
    Args:
        message: The message object
        
    Returns:
        The message ID if it exists, None otherwise.
        
    Note:
        A message only has an ID if it has been stored in the database.
        Messages that are skipped (via _should_skip_message) will not have an ID.
    """
    # Try direct attribute access first (most common case)
    try:
        if hasattr(message, "id") and message.id is not None:
            return message.id
    except (AttributeError, TypeError):
        pass
    
    # Fallback to data dict access (for deserialized messages)
    try:
        if hasattr(message, "data") and isinstance(message.data, dict):
            message_id = message.data.get("id")
            if message_id is not None:
                return message_id
    except (AttributeError, TypeError, KeyError):
        pass
    
    return None


def has_message_id(message: "Message") -> bool:
    """Check if the message has an ID.
    
    Args:
        message: The message object
        
    Returns:
        True if the message has an ID, False otherwise.
        
    Note:
        A message only has an ID if it has been stored in the database.
        Messages that are skipped (via _should_skip_message) will not have an ID.
    """
    return get_message_id(message) is not None


def require_message_id(message: "Message") -> str | UUID:
    """Get the message ID, raising an error if it doesn't exist.
    
    Args:
        message: The message object
        
    Returns:
        The message ID.
        
    Raises:
        ValueError: If the message does not have an ID.
        
    Note:
        Use this function when an ID is required for the operation.
        For optional ID access, use get_message_id() instead.
    """
    message_id = get_message_id(message)
    if message_id is None:
        msg = (
            "Message does not have an ID. Messages only have IDs after being stored in the database. "
            "This typically happens when a component is placed between an agent and chat output, "
            "causing the message to be skipped (via _should_skip_message)."
        )
        raise ValueError(msg)
    return message_id

