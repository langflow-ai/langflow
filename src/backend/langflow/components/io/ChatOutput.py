from typing import Optional, Text
from langflow.api.v1.schemas import ChatMessage
from langflow.services.getters import get_chat_service
from langflow import CustomComponent
from anyio.from_thread import start_blocking_portal
from loguru import logger
from langflow.field_typing import Text


class ChatOutput(CustomComponent):
    display_name = "Chat Output"
    description = "Used to send a message to the chat."

    field_config = {
        "code": {
            "show": False,
        }
    }

    def build_config(self):
        return {"message": {"input_types": ["Text"]}}

    def build(self, message: Optional[Text], is_ai: bool = False) -> Text:
        if not message:
            return ""
        try:
            chat_manager = get_chat_service()
            chat_message = ChatMessage(message=message, is_bot=is_ai)
            # send_message is a coroutine
            # run in a thread safe manner
            with start_blocking_portal() as portal:
                portal.call(chat_manager.send_message, chat_message)
            chat_manager.chat_history.add_message(
                chat_manager.cache_manager.current_client_id, chat_message
            )
        except Exception as exc:
            logger.exception(exc)
            logger.debug(f"Error sending message to chat: {exc}")
        self.repr_value = message
        return message
