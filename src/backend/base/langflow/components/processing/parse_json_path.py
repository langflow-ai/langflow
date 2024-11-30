from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Data
from jsonpath_ng import parse


class JSONPathComponent(Component):
    display_name = "JSON Path"
    description = "JSONPath Component enables dynamic querying of JSON data using JSONPath expressions."
    icon = "braces"
    name = "JSONPathComponent"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="JSON TEXT",
            info="This is a JSONPath component Input",
            value='',
            tool_mode=True,
        ),
        MessageTextInput(
            name="jsonpath_query",
            display_name="JSONPath Query",
            info="Provide a JSONPath query to extract data from the input JSON.",
            value="$",  # Default JSONPath
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    def build_output(self) -> Data:
        # Parse the input JSON
        try:
            import json
            json_data = json.loads(self.input_value)

            # Apply the JSONPath query
            jsonpath_expr = parse(self.jsonpath_query)
            results = [match.value for match in jsonpath_expr.find(json_data)]

            # Return the results as Data
            data = Data(text=results)
            self.status = data
            return data
        except Exception as e:
            # Handle any errors and provide feedback
            return Data(error=f"Error: {str(e)}")
