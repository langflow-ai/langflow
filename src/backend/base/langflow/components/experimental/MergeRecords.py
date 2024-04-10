from langflow.interface.custom.custom_component import CustomComponent
from langflow.schema import Record


class MergeRecordsComponent(CustomComponent):
    display_name = "Merge Records"
    description = "Merges records."
    beta: bool = True

    field_config = {
        "records": {"display_name": "Records"},
    }

    def build(self, records: list[Record]) -> Record:
        if not records:
            return Record()
        if len(records) == 1:
            return records[0]
        merged_record = Record()
        for record in records:
            if merged_record is None:
                merged_record = record
            else:
                merged_record += record
        self.status = merged_record
        return merged_record


if __name__ == "__main__":
    records = [
        Record(data={"key1": "value1"}),
        Record(data={"key2": "value2"}),
    ]
    component = MergeRecordsComponent()
    result = component.build(records)
    print(result)
