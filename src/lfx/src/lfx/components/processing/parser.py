from lfx.custom.custom_component.component import Component
from lfx.helpers.data import safe_convert
from lfx.inputs.inputs import BoolInput, HandleInput, MessageTextInput, MultilineInput, TabInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.template.field.base import Output


class ParserComponent(Component):
    display_name = "Parser"
    description = "Extracts text using a template."
    documentation: str = "https://docs.langflow.org/components-processing#parser"
    icon = "braces"

    inputs = [
        HandleInput(
            name="input_data",
            display_name="Data or DataFrame",
            input_types=["DataFrame", "Data"],
            info="Accepts either a DataFrame or a Data object.",
            required=True,
        ),
        TabInput(
            name="mode",
            display_name="Mode",
            options=["Parser", "Stringify"],
            value="Parser",
            info="Convert into raw string instead of using a template.",
            real_time_refresh=True,
        ),
        MultilineInput(
            name="pattern",
            display_name="Template",
            info=(
                "Use variables within curly brackets to extract column values for DataFrames "
                "or key values for Data."
                "For example: `Name: {Name}, Age: {Age}, Country: {Country}`"
            ),
            value="Text: {text}",  # Example default
            dynamic=True,
            show=True,
            required=True,
        ),
        MessageTextInput(
            name="sep",
            display_name="Separator",
            advanced=True,
            value="\n",
            info="String used to separate rows/items.",
        ),
    ]

    outputs = [
        Output(
            display_name="Parsed Text",
            name="parsed_text",
            info="Formatted text output.",
            method="parse_combined_text",
        ),
    ]

    def update_build_config(self, build_config, field_value, field_name=None):
        """Dynamically hide/show `template` and enforce requirement based on `stringify`."""
        if field_name == "mode":
            build_config["pattern"]["show"] = self.mode == "Parser"
            build_config["pattern"]["required"] = self.mode == "Parser"
            if field_value:
                clean_data = BoolInput(
                    name="clean_data",
                    display_name="Clean Data",
                    info=(
                        "Enable to clean the data by removing empty rows and lines "
                        "in each cell of the DataFrame/ Data object."
                    ),
                    value=True,
                    advanced=True,
                    required=False,
                )
                build_config["clean_data"] = clean_data.to_dict()
            else:
                build_config.pop("clean_data", None)

        return build_config

    def _clean_args(self):
        """Prepare arguments based on input type."""
        input_data = self.input_data

        match input_data:
            case list() if all(isinstance(item, Data) for item in input_data):
                msg = "List of Data objects is not supported."
                raise ValueError(msg)
            case DataFrame():
                return input_data, None
            case Data():
                return None, input_data
            case dict() if "data" in input_data:
                try:
                    if "columns" in input_data:  # Likely a DataFrame
                        return DataFrame.from_dict(input_data), None
                    # Likely a Data object
                    return None, Data(**input_data)
                except (TypeError, ValueError, KeyError) as e:
                    msg = f"Invalid structured input provided: {e!s}"
                    raise ValueError(msg) from e
            case _:
                msg = f"Unsupported input type: {type(input_data)}. Expected DataFrame or Data."
                raise ValueError(msg)

    def parse_combined_text(self) -> Message:
        """Parse all rows/items into a single text or convert input to string if `stringify` is enabled."""
        # Early return for stringify option
        if self.mode == "Stringify":
            return self.convert_to_string()

        df, data = self._clean_args()

        lines = []
        if df is not None:
            for _, row in df.iterrows():
                formatted_text = self.pattern.format(**row.to_dict())
                lines.append(formatted_text)
        elif data is not None:
            formatted_text = self.pattern.format(**data.data)
            lines.append(formatted_text)

        combined_text = self.sep.join(lines)
        self.status = combined_text
        return Message(text=combined_text)

    def convert_to_string(self) -> Message:
        """Convert input data to string with proper error handling."""
        result = ""
        if isinstance(self.input_data, list):
            result = "\n".join([safe_convert(item, clean_data=self.clean_data or False) for item in self.input_data])
        else:
            result = safe_convert(self.input_data or False)
        self.log(f"Converted to string with length: {len(result)}")

        message = Message(text=result)
        self.status = message
        return message
