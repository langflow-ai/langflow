from langflow.custom import Component
from langflow.io import HandleInput, NestedDictInput, Output, StrInput
from langflow.schema import Data


class AddMetadataComponent(Component):
    display_name = "Add Metadata"
    description = "Adds Metadata Dictionary to inputs"
    icon = "merge"
    name = "AddMetadata"

    inputs = [
        HandleInput(
            name="input_value",
            display_name="Input",
            info="Object(s) to which Metadata should be added",
            required=False,
            input_types=["Message", "Data"],
            is_list=True,
        ),
        StrInput(
            name="text_in",
            display_name="User Text",
            info="Text input; value will be in 'text' attribute of Data object. Empty text entries are ignored.",
            required=False,
        ),
        NestedDictInput(
            name="metadata",
            display_name="Metadata",
            info="Metadata to add to each object",
            input_types=["Data"],
            required=True,
        ),
    ]

    outputs = [
        Output(
            name="data",
            display_name="Data",
            info="List of Input objects each with added Metadata",
            method="process_output",
        ),
    ]

    def _as_clean_dict(self, obj):
        """Convert a Data object or a standard dictionary to a standard dictionary."""
        if isinstance(obj, dict):
            as_dict = obj
        elif isinstance(obj, Data):
            as_dict = obj.data
        else:
            raise TypeError("Expected a Data object or a dictionary.")

        return {k: v for k, v in (as_dict or {}).items() if k and k.strip()}

    def process_output(self) -> list[Data]:
        # Ensure metadata is a dictionary, filtering out any empty keys
        metadata = self._as_clean_dict(self.metadata)

        # Convert text_in to a Data object if it exists, and initialize our list of Data objects
        data_objects = [Data(text=self.text_in)] if self.text_in else []

        # Append existing Data objects from input_value, if any
        if self.input_value:
            data_objects.extend(self.input_value)

        # Update each Data object with the new metadata, preserving existing fields
        for data in data_objects:
            data.data.update(metadata)

        # Set the status for tracking/debugging purposes
        self.status = data_objects
        return data_objects
