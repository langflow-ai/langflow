from langflow import CustomComponent
from langflow.schema import Record


class ExtractKeyFromRecordComponent(CustomComponent):
    display_name = "Extract Key From Record"
    description = "Extracts a key from a record."
    beta: bool = True

    field_config = {
        "record": {"display_name": "Record"},
    }

    def build(self, record: Record, key: str, silent_error: bool = True) -> dict:
        data = getattr(record, key)
        self.status = data
        return data
