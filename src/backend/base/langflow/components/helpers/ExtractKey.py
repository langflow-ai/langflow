from typing import List, Union
from langflow.custom import Component
from langflow.io import DataInput, StrInput, Output
from langflow.schema import Data

class ExtractDataKeyComponent(Component):
    display_name = "Extract Key"
    description = "Extract a specific key from a Data object or a list of Data objects and return the extracted value(s) as Data object(s)."
    icon = "key"
    beta = True
    name = "ExtractaKey"

    inputs = [
        DataInput(
            name="data_input",
            display_name="Data Input",
            info="The Data object or list of Data objects to extract the key from.",
        ),
        StrInput(
            name="key",
            display_name="Key to Extract",
            info="The key in the Data object(s) to extract.",
        ),
    ]

    outputs = [
        Output(display_name="Extracted Data", name="extracted_data", method="extract_key"),
    ]

    def extract_key(self) -> Union[Data, List[Data]]:
        key = self.key

        if isinstance(self.data_input, list):
            result = []
            for item in self.data_input:
                if isinstance(item, Data) and key in item.data:
                    extracted_value = item.data[key]
                    result.append(Data(data={key: extracted_value}))
            self.status = result
            return result
        elif isinstance(self.data_input, Data):
            if key in self.data_input.data:
                extracted_value = self.data_input.data[key]
                result = Data(data={key: extracted_value})
                self.status = result
                return result
            else:
                self.status = f"Key '{key}' not found in Data object."
                return Data(data={"error": f"Key '{key}' not found in Data object."})
        else:
            self.status = "Invalid input. Expected Data object or list of Data objects."
            return Data(data={"error": "Invalid input. Expected Data object or list of Data objects."})
