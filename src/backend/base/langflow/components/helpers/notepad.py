import pandas as pd

from langflow.custom import Component
from langflow.io import DropdownInput, IntInput, MessageTextInput, Output
from langflow.schema.dataframe import DataFrame


class NotepadComponent(Component):
    display_name = "Notepad"
    description = "A component that stores and manages a list of values."
    icon = "notepad"

    inputs = [
        MessageTextInput(name="input_value", display_name="Input Value", info="The value to be saved", tool_mode=True),
        DropdownInput(
            name="operation",
            display_name="Operation",
            info="The operation to be performed",
            options=["add", "remove", "edit"],
            tool_mode=True,
        ),
        IntInput(
            name="position",
            display_name="Position",
            info="The position where to add, remove or edit the value",
            tool_mode=True,
            advanced=True,
            required=False,
        ),
    ]

    outputs = [
        Output(display_name="Notepad", name="notepad", method="process_and_get_notepad"),
    ]

    async def process_and_get_notepad(self) -> DataFrame:
        # Initialize notepad in context if it doesn't exist
        notepad_key = f"{self._id}_notepad"
        if notepad_key not in self.ctx:
            empty_df = DataFrame(columns=["value"])
            self.update_ctx({notepad_key: empty_df})

        # Get the current notepad DataFrame
        notepad: DataFrame = self.ctx[notepad_key].copy()  # Create a copy to avoid modifying the original
        if not isinstance(notepad, DataFrame):
            msg = f"Expected {notepad_key} to be a DataFrame, but got {type(notepad)}"
            raise TypeError(msg)

        operation = self.operation
        value = self.input_value
        position = self.position if isinstance(self.position, int) else None

        notepad_length = notepad.shape[0]

        # Create a new DataFrame for the operation result
        if operation == "add":
            if position is not None and 0 <= position <= notepad_length:
                # Insert at specific position
                new_df = pd.concat(
                    [notepad.iloc[:position], DataFrame({"value": [value]}), notepad.iloc[position:]]
                ).reset_index(drop=True)
            else:
                # Append at end
                new_df = pd.concat([notepad, DataFrame({"value": [value]})]).reset_index(drop=True)
            new_df = DataFrame(new_df)
        elif operation == "remove":
            if position is not None and 0 <= position < notepad_length:
                # Remove at specific position
                new_df = notepad.drop(notepad.index[position]).reset_index(drop=True)
            elif notepad_length > 0 and len(notepad[notepad["value"] == value]) > 0:
                # Remove by value
                new_df = notepad[notepad["value"] != value].reset_index(drop=True)
            else:
                new_df = notepad

        elif operation == "edit" and notepad_length > 0:
            new_df = notepad.copy()
            if position is not None and 0 <= position < notepad_length:
                # Edit at position
                new_df.loc[new_df.index[position], "value"] = value
            else:
                # Edit last row
                new_df.loc[new_df.index[-1], "value"] = value
        else:
            new_df = notepad

        if not isinstance(new_df, DataFrame):
            new_df = DataFrame(new_df)

        # Update context with the new DataFrame
        self.update_ctx({notepad_key: new_df})

        # Return the DataFrame wrapped in our DataFrame class
        return new_df
