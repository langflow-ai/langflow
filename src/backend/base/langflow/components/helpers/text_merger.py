from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message


class TextMergerComponent(Component):
    display_name = "Text Merger"
    description = "Takes two text inputs and merges them with a newline character"
    icon = "merge"
    name = "TextMerger"

    inputs = [
        MessageTextInput(
            name="first_text",
            display_name="First Text",
            info="Enter the first text to merge",
            value="",
            tool_mode=True,
        ),
        MessageTextInput(
            name="second_text",
            display_name="Second Text", 
            info="Enter the second text to merge",
            value="",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Merged Text",
            name="merged_text", 
            method="merge_texts"
        ),
    ]

    def merge_texts(self) -> Message:
        first = self.first_text or ""
        second = self.second_text or ""
        
        # Merge the two texts with a newline character
        merged_text = f"{first}\n{second}"
        
        self.status = f"Merged two texts: '{first}' and '{second}'"
        return Message(text=merged_text) 