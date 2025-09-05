from uuid import UUID

from lfx.utils.async_helpers import run_until_complete

from langflow.services.database.models.message.model import MessageTable, MessageUpdate
from langflow.services.deps import session_scope


async def _update_message(message_id: UUID | str, message: MessageUpdate | dict):
    if not isinstance(message, MessageUpdate):
        message = MessageUpdate(**message)
    async with session_scope() as session:
        db_message = await session.get(MessageTable, message_id)
        if not db_message:
            msg = "Message not found"
            raise ValueError(msg)
        message_dict = message.model_dump(exclude_unset=True, exclude_none=True)
        db_message.sqlmodel_update(message_dict)
        session.add(db_message)
        await session.commit()
        await session.refresh(db_message)
        return db_message


def update_message(message_id: UUID | str, message: MessageUpdate | dict):
    """DEPRECATED - Kept for backward compatibility. Do not use."""
    return run_until_complete(_update_message(message_id, message))
