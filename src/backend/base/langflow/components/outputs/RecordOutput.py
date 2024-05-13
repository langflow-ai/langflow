from langflow.base.io.text import TextComponent
from langflow.schema import Record


class RecordOutput(TextComponent):
    display_name = "Record Output"
    description = "Display record"

    def build(self, input_value: Record) -> Record:
        return input_value
