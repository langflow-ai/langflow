from langflow.custom import CustomComponent
from langflow.schema import Data


class MergeRecordsComponent(CustomComponent):
    display_name = "Merge Records"
    description = "Merges data."
    beta: bool = True

    field_config = {
        "data": {"display_name": "Records"},
    }

    def build(self, data: list[Data]) -> Data:
        if not data:
            return Data()
        if len(data) == 1:
            return data[0]
        merged_record = Data()
        for value in data:
            if merged_record is None:
                merged_record = value
            else:
                merged_record += value
        self.status = merged_record
        return merged_record


if __name__ == "__main__":
    data = [
        Data(data={"key1": "value1"}),
        Data(data={"key2": "value2"}),
    ]
    component = MergeRecordsComponent()
    result = component.build(data)
    print(result)
