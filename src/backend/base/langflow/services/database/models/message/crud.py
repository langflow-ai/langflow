from uuid import UUID

from langflow.services.database.models.message.model import MessageTable, MessageUpdate
from langflow.services.deps import session_scope


def update_message(message_id: UUID | str, message: MessageUpdate | dict):
    if not isinstance(message, MessageUpdate):
        message = MessageUpdate(**message)
    with session_scope() as session:
        db_message = session.get(MessageTable, message_id)
        if not db_message:
            msg = "Message not found"
            raise ValueError(msg)
        message_dict = message.model_dump(exclude_unset=True, exclude_none=True)
        db_message.sqlmodel_update(message_dict)
        session.add(db_message)
        session.commit()
        session.refresh(db_message)
        return db_message
