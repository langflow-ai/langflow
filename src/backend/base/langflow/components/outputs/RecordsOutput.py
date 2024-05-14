from langflow.base.io.text import TextComponent
from langflow.schema import Record


class RecordsOutput(TextComponent):
    display_name = "Records Output"
    description = "Display Records as a Table"

    def build(self, input_value: Record) -> Record:
        return input_value
