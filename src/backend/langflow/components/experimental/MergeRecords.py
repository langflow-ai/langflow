from langflow import CustomComponent
from langflow.schema import Record


class MergeRecordsComponent(CustomComponent):
    display_name = "Merge Records"
    description = "Merges records."

    field_config = {
        "records": {"display_name": "Records"},
    }

    def build(self, records: list[Record]) -> Record:
        if not records:
            return records
        if len(records) == 1:
            return records[0]
        merged_record = None
        for record in records:
            if merged_record is None:
                merged_record = record
            else:
                merged_record += record
        self.status = merged_record
        return merged_record
