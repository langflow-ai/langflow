from langflow.custom import CustomComponent
from langflow.field_typing import Text
from langflow.helpers.record import data_to_text
from langflow.schema import Data


class RecordsToTextComponent(CustomComponent):
    display_name = "Records To Text"
    description = "Convert Records into plain text following a specified template."

    def build_config(self):
        return {
            "data": {
                "display_name": "Records",
                "info": "The data to convert to text.",
            },
            "template": {
                "display_name": "Template",
                "info": "The template to use for formatting the data. It can contain the keys {text}, {data} or any other key in the Data.",
                "multiline": True,
            },
        }

    def build(
        self,
        data: list[Data],
        template: str = "Text: {text}\nData: {data}",
    ) -> Text:
        if not data:
            return ""
        if isinstance(data, Data):
            data = [data]

        result_string = data_to_text(template, data)
        self.status = result_string
        return result_string
