from lfx.custom.custom_component.component import Component
from lfx.io import MessageInput, Output
from lfx.schema.data import Data
from langflow.schema.message import Message
from loguru import logger


class MessageToDataComponent(Component):
    display_name = "Message to Data"
    category: str = "helpers"
    description = "Convert a Message object to a Data object"
    icon = "message-square-share"
    beta = True
    name = "MessagetoData"

    inputs = [
        MessageInput(
            name="message",
            display_name="Message",
            info="The Message object to convert to a Data object",
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="convert_message_to_data"),
    ]

    def convert_message_to_data(self) -> Data:
        if isinstance(self.message, Message):
            # Convert Message to Data
            return Data(data=self.message.data)

        msg = "Error converting Message to Data: Input must be a Message object"
        logger.opt(exception=True).debug(msg)
        self.status = msg
        return Data(data={"error": msg})
