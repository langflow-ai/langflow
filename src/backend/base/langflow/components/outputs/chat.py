from typing import Any

from langflow.base.io.chat import ChatComponent
from langflow.inputs import BoolInput
from langflow.inputs.inputs import HandleInput
from langflow.io import DropdownInput, MessageTextInput, Output
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message
from langflow.schema.properties import Source
from langflow.utils.constants import (
    MESSAGE_SENDER_AI,
    MESSAGE_SENDER_NAME_AI,
    MESSAGE_SENDER_USER,
)


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

    def _build_source(self, id_: str | None, display_name: str | None, source: str | None) -> Source:
        source_dict = {}
        if id_:
            source_dict["id"] = id_
        if display_name:
            source_dict["display_name"] = display_name
        if source:
            # Handle case where source is a ChatOpenAI object
            if hasattr(source, "model_name"):
                source_dict["source"] = source.model_name
            elif hasattr(source, "model"):
                source_dict["source"] = str(source.model)
            else:
                source_dict["source"] = str(source)
        return Source(**source_dict)

    async def message_response(self) -> Message:
        # First convert the input to string if needed
        text = self.convert_to_string()

        # Get source properties
        source, icon, display_name, source_id = self.get_properties_from_source_component()
        background_color = self.background_color
        text_color = self.text_color
        if self.chat_icon:
            icon = self.chat_icon

        # Create or use existing Message object
        if isinstance(self.input_value, Message):
            message = self.input_value
            # Update message properties
            message.text = text
        else:
            message = Message(text=text)

        # Set message properties
        message.sender = self.sender
        message.sender_name = self.sender_name
        message.session_id = self.session_id
        message.flow_id = self.graph.flow_id if hasattr(self, "graph") else None
        message.properties.source = self._build_source(source_id, display_name, source)
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

    def _validate_input(self) -> None:
        """Validate the input data and raise ValueError if invalid."""
        if self.input_value is None:
            msg = "Input data cannot be None"
            raise ValueError(msg)
        if not isinstance(self.input_value, Data | DataFrame | Message | str | list):
            msg = f"Expected Data or DataFrame or Message or str, got {type(self.input_value).__name__}"
            raise TypeError(msg)

    def _safe_convert(self, data: Any) -> str:
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
            if isinstance(data, DataFrame):
                if self.clean_data:
                    # Remove empty rows
                    data = data.dropna(how="all")
                    # Remove empty lines in each cell
                    data = data.replace(r"^\s*$", "", regex=True)
                    # Replace multiple newlines with a single newline
                    data = data.replace(r"\n+", "\n", regex=True)
                return data.to_markdown(index=False)
            return str(data)
        except (ValueError, TypeError, AttributeError) as e:
            msg = f"Error converting data: {e!s}"
            raise ValueError(msg) from e

    def convert_to_string(self) -> str:
        """Convert input data to string with proper error handling."""
        self._validate_input()
        if isinstance(self.input_value, list):
            return "\n".join([self._safe_convert(item) for item in self.input_value])
        return self._safe_convert(self.input_value)
