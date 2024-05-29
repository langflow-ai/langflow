from langflow.custom import CustomComponent
from langflow.schema import Record


class RecordsOutput(CustomComponent):
    display_name = "Records Output"
    description = "Display Records as a Table"

    def build(self, input_value: Record) -> Record:
        return input_value
