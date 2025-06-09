from langflow.base.data.utils import IMG_FILE_TYPES, TEXT_FILE_TYPES
from langflow.base.io.chat import ChatComponent
from langflow.inputs.inputs import BoolInput
from langflow.io import (
    DropdownInput,
    FileInput,
    MessageTextInput,
    MultilineInput,
    Output,
)
from langflow.schema.message import Message
from langflow.utils.constants import (
    MESSAGE_SENDER_AI,
    MESSAGE_SENDER_NAME_USER,
    MESSAGE_SENDER_USER,
)


class ChatInput(ChatComponent):
    display_name = "Chat Input"
    description = "Get chat inputs from the Playground."
    icon = "MessagesSquare"
    name = "ChatInput"
    minimized = True

    inputs = [
        MultilineInput(
            name="input_value",
            display_name="Input Text",
            value="",
            info="Message to be passed as input.",
            input_types=[],
        ),
        BoolInput(
            name="should_store_message",
            display_name="Store Messages",
            info="Store the message in the history.",
            value=True,
            advanced=True,
        ),
        DropdownInput(
            name="sender",
            display_name="Sender Type",
            options=[MESSAGE_SENDER_AI, MESSAGE_SENDER_USER],
            value=MESSAGE_SENDER_USER,
            info="Type of sender.",
            advanced=True,
        ),
        MessageTextInput(
            name="sender_name",
            display_name="Sender Name",
            info="Name of the sender.",
            value=MESSAGE_SENDER_NAME_USER,
            advanced=True,
        ),
        MessageTextInput(
            name="session_id",
            display_name="Session ID",
            info="The session ID of the chat. If empty, the current session ID parameter will be used.",
            advanced=True,
        ),
        FileInput(
            name="files",
            display_name="Files",
            file_types=TEXT_FILE_TYPES + IMG_FILE_TYPES,
            info="Files to be sent with the message.",
            advanced=True,
            is_list=True,
            temp_file=True,
        ),
        MessageTextInput(
            name="background_color",
            display_name="Background Color",
            info="The background color of the icon.",
            advanced=True,
        ),
        MessageTextInput(
            name="chat_icon",
            display_name="Icon",
            info="The icon of the message.",
            advanced=True,
        ),
        MessageTextInput(
            name="text_color",
            display_name="Text Color",
            info="The text color of the name",
            advanced=True,
        ),
    ]
    outputs = [
        Output(display_name="Chat Message", name="message", method="message_response"),
    ]

    async def message_response(self) -> Message:
        background_color = self.background_color
        text_color = self.text_color
        icon = self.chat_icon

        message = await Message.create(
            text=self.input_value,
            sender=self.sender,
            sender_name=self.sender_name,
            session_id=self.session_id,
            files=self.files,
            properties={
                "background_color": background_color,
                "text_color": text_color,
                "icon": icon,
            },
        )
        if self.session_id and isinstance(message, Message) and self.should_store_message:
            stored_message = await self.send_message(
                message,
            )
            self.message.value = stored_message
            message = stored_message

        self.status = message
        return message
