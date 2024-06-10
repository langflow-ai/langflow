from langflow.custom import CustomComponent
from langflow.schema import Record


class RecordOutput(CustomComponent):
    display_name = "Records Output"
    description = "Display Records as a Table"

    def build_config(self):
        return {
            "input_value": {
                "display_name": "Records",
                "input_types": ["Record"],
                "info": "Record or Record list to be passed as input.",
            },
        }

    def build(self, input_value: Record) -> Record:
        self.status = input_value
        return input_value
