import jq

from langflow.custom import Component
from langflow.io import DataInput, Output, StrInput
from langflow.schema import Data, DataFrame


class JQComponent(Component):
    display_name = "JQ Data Processor"
    description = "Run JQ transformations against data"
    documentation: str = "https://jqlang.org/"
    icon = "braces"
    name = "JQ Data Processor"

    inputs = [
        StrInput(name="jq", display_name="JQ input", info="The JQ to evaluate", value=".", tool_mode=True),
        DataInput(
            name="input_json",
            display_name="Input JSON",
            info="The json to pass through JQ",
            value="{}",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Output Data Object", name="output_object", method="build_output_object"),
        Output(display_name="Output DataFrame Array", name="output_array", method="build_output_array"),
        Output(display_name="Output String", name="output_string", method="build_output_string"),
    ]

    # Helper methods for data operations
    def get_data_dict(self) -> dict:
        """Extract data dictionary from Data object."""
        data = (
            self.input_json[0] if isinstance(self.input_json, list) and len(self.input_json) == 1 else self.input_json
        )
        return data.model_dump()

    def get_normalized_data(self) -> dict:
        """Get normalized data dictionary, handling the 'data' key if present."""
        data_dict = self.get_data_dict()
        return data_dict.get("data", data_dict)

    def build_output_string(self) -> str:
        query_result = jq.compile(self.jq).input_value(self.get_normalized_data())
        result = query_result.first()
        self.log(result)
        return result

    def build_output_array(self) -> DataFrame:
        query_result = jq.compile(self.jq).input_value(self.get_normalized_data())
        result = query_result.first()
        self.log(result)
        return DataFrame([Data(data=x) for x in result])

    def build_output_object(self) -> Data:
        query_result = jq.compile(self.jq).input_value(self.get_normalized_data())
        result = query_result.first()
        output = Data(data=result)
        self.log(result)
        return output
