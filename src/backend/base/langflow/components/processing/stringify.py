from langflow.custom import Component
from langflow.io import BoolInput, HandleInput, Output
from langflow.schema import Data, DataFrame, Message


class StringifyComponent(Component):
    display_name = "Stringify"
    description = "Converts Data or DataFrame into a string representation."
    icon = "file-text"  # Matches the idea of text-based output
    name = "Stringify"

    inputs = [
        HandleInput(
            name="input_data",
            display_name="Data or DataFrame",
            input_types=["Data", "DataFrame"],
            info="Accepts either Data or DataFrame",
        ),
        BoolInput(
            name="clean_data",
            display_name="Basic Clean Data",
            value=True,
            info="Whether to clean the data",
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="string_output", display_name="String Output", method="convert_to_string"),
    ]

    def _validate_input(self) -> None:
        """Validate the input data and raise ValueError if invalid."""
        if self.input_data is None:
            msg = "Input data cannot be None"
            raise ValueError(msg)
        if not isinstance(self.input_data, Data | DataFrame):
            msg = f"Expected Data or DataFrame, got {type(self.input_data).__name__}"
            raise TypeError(msg)

    def _safe_convert(self, data: Data | DataFrame) -> str:
        """Safely convert input data to string."""
        try:
            if isinstance(data, Data):
                if data.text is None:
                    msg = "Empty Data object"
                    raise ValueError(msg)
                return data.text
            if isinstance(data, DataFrame):
                if self.clean_data:
                    # Remove empty rows
                    data = data.dropna(how="all")
                    # Remove empty lines in each cell
                    data = data.replace(r"^\s*$", "", regex=True)
                    # Replace multiple newlines with a single newline
                    data = data.replace(r"\n+", "\n", regex=True)
                return data.to_markdown(index=False)
            return str(data)
        except (ValueError, TypeError, AttributeError) as e:
            msg = f"Error converting data: {e!s}"
            raise ValueError(msg) from e

    def convert_to_string(self) -> Message:
        """Convert input data to string with proper error handling."""
        self._validate_input()
        result = self._safe_convert(self.input_data)
        return Message(text=result)
