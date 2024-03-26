from langflow.interface.custom.custom_component import CustomComponent
from langflow.schema import Record


class TextToRecordComponent(CustomComponent):
    display_name = "Text to Record"
    description = "A component to create a record from Text."
    beta: bool = True

    def build_config(self):
        return {
            "data": {
                "display_name": "Data",
                "info": "The data to convert to a record.",
                "input_types": ["Text"],
            }
        }

    def build(
        self,
        data: dict,
    ) -> Record:
        return_record = Record(data=data)
        self.status = return_record
        return return_record
