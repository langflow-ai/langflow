from langflow.custom import CustomComponent
from langflow.schema import Data


class UpdateDataComponent(CustomComponent):
    display_name = "Update Data"
    description = "Update Data with text-based key/value pairs, similar to updating a Python dictionary."
    name = "UpdateData"

    def build_config(self):
        return {
            "data": {
                "display_name": "Data",
                "info": "The record to update.",
            },
            "new_data": {
                "display_name": "New Data",
                "info": "The new data to update the record with.",
                "input_types": ["Text"],
            },
        }

    def build(
        self,
        data: Data,
        new_data: dict,
    ) -> Data:
        """
        Updates a record with new data.

        Args:
            record (Data): The record to update.
            new_data (dict): The new data to update the record with.

        Returns:
            Data: The updated record.
        """
        data.data.update(new_data)
        self.status = data
        return data
