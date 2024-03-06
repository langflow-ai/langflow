from typing import Optional

from langflow import CustomComponent
from langflow.field_typing import Text
from langflow.schema import Record


class TextToRecordComponent(CustomComponent):
    display_name = "Text to Record"
    description = "Converts text to a Record."

    def build_config(self):
        return {
            "text": {
                "display_name": "Text",
                "info": "The text to convert to a record.",
            },
            "data": {
                "display_name": "Data",
                "info": "The optional data to include in the record.",
            },
        }

    def build(
        self,
        text: Text,
        data: Optional[dict] = {},
    ) -> Record:
        record = Record(text=text, data=data)
        self.status = record
        return record
