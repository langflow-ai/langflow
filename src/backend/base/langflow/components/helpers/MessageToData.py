from langflow.custom import Component
from langflow.io import MessageInput, Output
from langflow.schema import Data
from langflow.schema.message import Message


class MessageToDataComponent(Component):
    display_name = "Message to Data"
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
        try:
            if not isinstance(self.message, Message):
                raise ValueError("Input must be a Message object")

            # Convert Message to Data
            data = Data(data=self.message.data)

            self.status = "Successfully converted Message to Data"
            return data
        except Exception as e:
            error_message = f"Error converting Message to Data: {str(e)}"
            self.status = error_message
            return Data(data={"error": error_message})
