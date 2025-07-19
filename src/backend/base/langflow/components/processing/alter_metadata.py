from lfx.custom.custom_component.component import Component

from langflow.inputs.inputs import MessageTextInput
from langflow.io import HandleInput, NestedDictInput, Output, StrInput
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame


class AlterMetadataComponent(Component):
    display_name = "Alter Metadata"
    description = "Adds/Removes Metadata Dictionary on inputs"
    icon = "merge"
    name = "AlterMetadata"
    legacy = True

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
        MessageTextInput(
            name="remove_fields",
            display_name="Fields to Remove",
            info="Metadata Fields to Remove",
            required=False,
            is_list=True,
        ),
    ]

    outputs = [
        Output(
            name="data",
            display_name="Data",
            info="List of Input objects each with added Metadata",
            method="process_output",
        ),
        Output(
            display_name="DataFrame",
            name="dataframe",
            info="Data objects as a DataFrame, with metadata as columns",
            method="as_dataframe",
        ),
    ]

    def _as_clean_dict(self, obj):
        """Convert a Data object or a standard dictionary to a standard dictionary."""
        if isinstance(obj, dict):
            as_dict = obj
        elif isinstance(obj, Data):
            as_dict = obj.data
        else:
            msg = f"Expected a Data object or a dictionary but got {type(obj)}."
            raise TypeError(msg)

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

        # Handle removal of fields specified in remove_fields
        if self.remove_fields:
            fields_to_remove = {field.strip() for field in self.remove_fields if field.strip()}

            # Remove specified fields from each Data object's metadata
            for data in data_objects:
                data.data = {k: v for k, v in data.data.items() if k not in fields_to_remove}

        # Set the status for tracking/debugging purposes
        self.status = data_objects
        return data_objects

    def as_dataframe(self) -> DataFrame:
        """Convert the processed data objects into a DataFrame.

        Returns:
            DataFrame: A DataFrame where each row corresponds to a Data object,
                    with metadata fields as columns.
        """
        data_list = self.process_output()
        return DataFrame(data_list)
