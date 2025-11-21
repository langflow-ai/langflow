from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message


class IfElseComponent(Component):
    display_name = "If Else Message"
    description = (
        "Outputs whichever of the two message inputs is not empty. "
        "If both have values, raises an error."
    )
    icon = "split"
    name = "IfElseMessage"

    inputs = [
        MessageTextInput(
            name="input_a",
            display_name="Input A",
            info="The first message input.",
        ),
        MessageTextInput(
            name="input_b",
            display_name="Input B",
            info="The second message input.",
        ),
    ]

    outputs = [
        Output(
            display_name="Selected Message",
            name="selected_message",
            method="select_message",
        ),
    ]

    def select_message(self) -> Message:
        # Normalize and strip whitespace
        val_a = str(self.input_a).strip() if self.input_a is not None else ""
        val_b = str(self.input_b).strip() if self.input_b is not None else ""

        # Validate conditions
        if val_a and val_b:
            error_msg = "Both inputs have values. Only one input should be provided."
            self.status = error_msg
            raise ValueError(error_msg)
        elif val_a:
            selected = val_a
            self.status = "Selected Input A"
        elif val_b:
            selected = val_b
            self.status = "Selected Input B"
        else:
            error_msg = "Both inputs are empty. Provide at least one input."
            self.status = error_msg
            raise ValueError(error_msg)

        return Message(text=selected)
