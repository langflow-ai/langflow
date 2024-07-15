from langflow.custom import CustomComponent
from langflow.schema import Data


class MergeDataComponent(CustomComponent):
    display_name = "Merge Data"
    description = "Combines multiple data sources into a single unified Data object."
    beta: bool = True
    name = "MergeData"

    field_config = {
        "data": {"display_name": "Data"},
    }

    def build(self, data: list[Data]) -> Data:
        if not data:
            return Data()
        if len(data) == 1:
            return data[0]
        merged_data = Data()
        for value in data:
            if merged_data is None:
                merged_data = value
            else:
                merged_data += value
        self.status = merged_data
        return merged_data
