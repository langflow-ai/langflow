from langflow.base.io.chat import ChatComponent
from langflow.inputs import BoolInput
from langflow.io import DropdownInput, MessageInput, MessageTextInput, Output
from langflow.schema.message import Message
from langflow.schema.properties import Source
from langflow.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_NAME_AI, MESSAGE_SENDER_USER


class ChatOutput(ChatComponent):
    display_name = "Chat Output"
    description = "Display a chat message in the Playground."
    icon = "MessagesSquare"
    name = "ChatOutput"

    inputs = [
        MessageInput(
            name="input_value",
            display_name="Text",
            info="Message to be passed as output.",
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
            value=MESSAGE_SENDER_AI,
            advanced=True,
            info="Type of sender.",
        ),
        MessageTextInput(
            name="sender_name",
            display_name="Sender Name",
            info="Name of the sender.",
            value=MESSAGE_SENDER_NAME_AI,
            advanced=True,
        ),
        MessageTextInput(
            name="session_id",
            display_name="Session ID",
            info="The session ID of the chat. If empty, the current session ID parameter will be used.",
            advanced=True,
        ),
        MessageTextInput(
            name="data_template",
            display_name="Data Template",
            value="{text}",
            advanced=True,
            info="Template to convert Data to Text. If left empty, it will be dynamically set to the Data's text key.",
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
        Output(
            display_name="Message",
            name="message",
            method="message_response",
        ),
    ]

    def _build_source(self, _id: str | None, display_name: str | None, source: str | None) -> Source:
        source_dict = {}
        if _id:
            source_dict["id"] = _id
        if display_name:
            source_dict["display_name"] = display_name
        if source:
            source_dict["source"] = source
        return Source(**source_dict)

    def message_response(self) -> Message:
        _source, _icon, _display_name, _source_id = self.get_properties_from_source_component()
        _background_color = self.background_color
        _text_color = self.text_color
        if self.chat_icon:
            _icon = self.chat_icon
        message = self.input_value if isinstance(self.input_value, Message) else Message(text=self.input_value)
        message.sender = self.sender
        message.sender_name = self.sender_name
        message.session_id = self.session_id
        message.flow_id = self.graph.flow_id if hasattr(self, "graph") else None
        message.properties.source = self._build_source(_source_id, _display_name, _source)
        message.properties.icon = _icon
        message.properties.background_color = _background_color
        message.properties.text_color = _text_color
        if self.session_id and isinstance(message, Message) and self.should_store_message:
            stored_message = self.send_message(
                message,
            )
            self.message.value = stored_message
            message = stored_message

        self.status = message
        return message
