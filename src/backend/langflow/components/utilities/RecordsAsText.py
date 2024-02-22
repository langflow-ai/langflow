from langflow import CustomComponent
from langflow.field_typing import Text
from langflow.schema import Record


class RecordsAsTextComponent(CustomComponent):
    display_name = "Records to Text"
    description = "Converts Records a list of Records to text using a template."

    def build_config(self):
        return {
            "records": {
                "display_name": "Records",
                "info": "The records to convert to text.",
            },
            "template": {
                "display_name": "Template",
                "info": "The template to use for formatting the records. It must contain the keys {text} and {data}.",
            },
        }

    def build(
        self,
        records: list[Record],
        template: str = "Text: {text}\nData: {data}",
    ) -> Text:
        if isinstance(records, Record):
            records = [records]

        formated_records = [
            template.format(text=record.text, **record.data) for record in records
        ]
        result_string = "\n".join(formated_records)
        self.status = result_string
        return result_string
