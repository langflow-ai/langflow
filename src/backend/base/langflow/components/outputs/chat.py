from typing import Any, Generator

from langflow.base.io.chat import ChatComponent
from langflow.inputs.inputs import BoolInput, DropdownInput, HandleInput, MessageTextInput
from langflow.template.field.base import Output
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message
from langflow.schema.properties import Source
from langflow.utils.constants import (
    MESSAGE_SENDER_AI,
    MESSAGE_SENDER_NAME_AI,
    MESSAGE_SENDER_USER,
)

def safe_convert(data: Message | Data | DataFrame | str, clean_data: bool) -> str:
    """Safely convert input data to string."""
    try:
        if isinstance(data, str):
            return data
        if isinstance(data, Message):
            return data.get_text()
        if isinstance(data, Data):
            if data.get_text() is None:
                msg = "Empty Data object"
                raise ValueError(msg)
            return data.get_text()
        if clean_data:
            # Remove empty rows
            data = data.dropna(how="all")
            # Remove empty lines in each cell
            data = data.replace(r"^\s*$", "", regex=True)
            # Replace multiple newlines with a single newline
            data = data.replace(r"\n+", "\n", regex=True)
        return data.to_markdown(index=False)
    except (ValueError, TypeError, AttributeError) as e:
        msg = f"Error converting data: {e!s}"
        raise ValueError(msg) from e
    
def build_source(id_: str | None, display_name: str | None, source: Any | str | None) -> Source:
    source_dict: dict[str, str | None] = {}
    if id_:
        source_dict["id"] = id_
    if display_name:
        source_dict["display_name"] = display_name
    if source is None:
        pass
    elif isinstance(source, str):
        source_dict["source"] = str(source)
    elif hasattr(source, "model_name"):
        # Handle case where source is a ChatOpenAI object
        source_dict["source"] = source.model_name
    elif hasattr(source, "model"):
        source_dict["source"] = str(source.model)

    return Source(**source_dict)

class ChatOutput(ChatComponent):
    display_name = "Chat Output"
    description = "Display a chat message in the Playground."
    icon = "MessagesSquare"
    name = "ChatOutput"
    minimized = True

    inputs = [
        HandleInput(
            name="input_value",
            display_name="Text",
            info="Message to be passed as output.",
            input_types=["Data", "DataFrame", "Message"],
            required=True,
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
        BoolInput(
            name="clean_data",
            display_name="Basic Clean Data",
            value=True,
            info="Whether to clean the data",
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

    input_value: Message | Data | DataFrame | str | list[Message | Data | DataFrame | str] | Generator[Any, None, None] | None

    async def message_response(self) -> Message:
        # Get source properties
        source, icon, display_name, source_id = self.get_properties_from_source_component()
        background_color = self.background_color
        text_color = self.text_color
        if self.chat_icon:
            icon = self.chat_icon

        message = self._validate_input_and_create_message()

        # Set message properties
        message.sender = self.sender
        message.sender_name = self.sender_name
        message.session_id = self.session_id
        message.flow_id = self.graph.flow_id if hasattr(self, "graph") else None
        message.properties.source = build_source(source_id, display_name, source)
        message.properties.icon = icon
        message.properties.background_color = background_color
        message.properties.text_color = text_color

        # Store message if needed
        if self.session_id and self.should_store_message:
            stored_message = await self.send_message(message)
            self.message.value = stored_message
            message = stored_message

        self.status = message
        return message

    def _validate_input_and_create_message(self) -> Message:
        if isinstance(self.input_value, Message):
            # Use existing Message object, update Message properties with safe_convert()
            message = self.input_value
            message.text = safe_convert(self.input_value, self.clean_data)
        elif isinstance(self.input_value, Data | DataFrame | str):
            # Convert Data, DataFrame, str, or list to a Message with safe_convert()
            message = Message(text=safe_convert(self.input_value, self.clean_data))
        elif isinstance(self.input_value, list):
            # Convert list to a Message using safe_convert() on its items and joining with newlines
            message = Message(text="\n".join([safe_convert(item, self.clean_data) for item in self.input_value]))
        elif isinstance(self.input_value, Generator):
            # Generator is found when streaming is enabled, convert to a Message directly
            message = Message(text=self.input_value)
        elif self.input_value is None:
            raise ValueError("Input value cannot be None")
        else:
            raise TypeError(f"Expected Message or Data or DataFrame or str, got {type(self.input_value).__name__}")
        return message
    