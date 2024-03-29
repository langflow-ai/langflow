from langflow.interface.custom.custom_component import CustomComponent
from langflow.schema import Record


class CreateRecordComponent(CustomComponent):
    display_name = "Create Record"
    description = "A component to create a record."
    beta: bool = True

    def build_config(self):
        return {
            "data": {
                "display_name": "Data",
                "info": "Data to contruct the record.",
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
