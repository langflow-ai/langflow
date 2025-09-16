from lfx.custom.custom_component.component import Component
from lfx.io import MessageInput, Output
from lfx.log.logger import logger
from lfx.schema.data import Data


class MessageToDataComponent(Component):
    display_name = "Message to Data"
    description = "Convert a Message object to a Data object"
    icon = "message-square-share"
    beta = True
    name = "MessagetoData"
    legacy = True
    replacement = ["processing.TypeConverterComponent"]

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
        # Check for Message by checking if it has the expected attributes instead of isinstance
        if hasattr(self.message, "data") and hasattr(self.message, "text") and hasattr(self.message, "get_text"):
            # Convert Message to Data - this works for both langflow.Message and lfx.Message
            return Data(data=self.message.data)

        msg = "Error converting Message to Data: Input must be a Message object"
        logger.debug(msg, exc_info=True)
        self.status = msg
        return Data(data={"error": msg})
