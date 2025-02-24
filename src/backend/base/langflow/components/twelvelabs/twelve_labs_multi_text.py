from langflow.custom import Component
from langflow.io import MessageTextInput, Output, StrInput
from langflow.schema import Data


class TwelveLabsMultiTextInput(Component):
    display_name = "Twelve Labs Multi Text Input"
    description = "Component to input multiple text entries for embedding."
    icon = "text"
    name = "TwelveLabsMultiTextInput"

    inputs = [
        StrInput(
            name="texts",
            display_name="Text Inputs",
            is_list=True,
            placeholder="Enter text...",
            list_add_label="Add Text",
        )
    ]

    outputs = [
        Output(display_name="Data", name="data", method="process_texts"),
    ]

    def process_texts(self) -> list[Data]:
        """Process the input texts and return them as Data objects."""
        if not self.texts:
            return []
            
        texts = [text.strip() for text in self.texts if text.strip()]
        data = [Data(text=text) for text in texts]
        self.status = data
        return data
