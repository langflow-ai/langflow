from typing import Optional

from langflow.field_typing import Text
from langflow.interface.custom.custom_component import CustomComponent
from langflow.schema import Record
from langflow.utils.util import unescape_string


class SplitTextComponent(CustomComponent):
    display_name: str = "Split Text"
    description: str = "Split text into chunks of a specified length."

    def build_config(self):
        return {
            "inputs": {
                "display_name": "Inputs",
                "info": "Texts to split.",
                "input_types": ["Record", "Text"],
            },
            "separator": {
                "display_name": "Separator",
                "info": 'The character to split on. Defaults to " ".',
            },
            "truncate_size": {
                "display_name": "Truncate Size",
                "info": "The maximum length (in number of characters) of each chunk to keep. Defaults to 0 (no truncation).",
            },
        }

    def build(
        self,
        inputs: list[Text],
        separator: str = " ",
        truncate_size: Optional[int] = 0,
    ) -> list[Record]:
        separator = unescape_string(separator)

        outputs = []
        for text in inputs:
            chunks = text.split(separator)

            if truncate_size:
                chunks = [chunk[:truncate_size] for chunk in chunks]

            for chunk in chunks:
                outputs.append(Record(text=chunk, data={"parent": text}))

        self.status = outputs
        return outputs
