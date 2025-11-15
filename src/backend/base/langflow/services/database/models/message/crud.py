"""DEPRECATED - Message CRUD operations.

Use langflow.services.database.crud.message_crud instead.
This module is kept for backward compatibility only.
"""

from uuid import UUID

from lfx.utils.async_helpers import run_until_complete

from langflow.services.database.models.message.model import MessageUpdate
from langflow.services.deps import session_scope


async def _update_message(message_id: UUID | str, message: MessageUpdate | dict):
    """DEPRECATED - Use message_crud.update() instead."""
    from langflow.services.database.crud import message_crud

    if not isinstance(message, MessageUpdate):
        message = MessageUpdate(**message)
    async with session_scope() as session:
        db_message = await message_crud.get(session, message_id)
        if not db_message:
            msg = "Message not found"
            raise ValueError(msg)
        return await message_crud.update(session, db_obj=db_message, obj_in=message)


def update_message(message_id: UUID | str, message: MessageUpdate | dict):
    """DEPRECATED - Kept for backward compatibility. Do not use."""
    return run_until_complete(_update_message(message_id, message))
