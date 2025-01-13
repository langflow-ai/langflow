from typing import Protocol

import pandas as pd

from langflow.custom import Component
from langflow.io import DropdownInput, IntInput, MessageTextInput, Output
from langflow.schema.dataframe import DataFrame


class DfOperation(Protocol):
    """Protocol defining the interface for notepad operations.

    All notepad operations must implement this protocol which takes a DataFrame,
    value string and optional position as input and returns a modified DataFrame.
    """

    def __call__(self, notepad: DataFrame, value: str, position: int | None = None) -> DataFrame: ...


def add_value(notepad: DataFrame, value: str, position: int | None = None) -> DataFrame:
    """Add a value to the notepad at the specified position or at the end.

    Args:
        notepad (DataFrame): The current notepad DataFrame
        value (str): The value to add
        position (int | None, optional): Position to insert the value. If None, appends to end.
            Must be between 0 and notepad length inclusive. Defaults to None.

    Returns:
        DataFrame: A new DataFrame with the value added at the specified position or end
    """
    notepad_length = notepad.shape[0]
    if position is not None and 0 <= position <= notepad_length:
        # Insert at specific position
        new_df = pd.concat(
            [notepad.iloc[:position], DataFrame({"value": [value]}), notepad.iloc[position:]]
        ).reset_index(drop=True)
    else:
        # Append at end
        new_df = pd.concat([notepad, DataFrame({"value": [value]})]).reset_index(drop=True)
    return DataFrame(new_df)


def remove_value(notepad: DataFrame, value: str, position: int | None = None) -> DataFrame:
    """Remove a value from the notepad by position or value.

    Args:
        notepad (DataFrame): The current notepad DataFrame
        value (str): The value to remove (if removing by value)
        position (int | None, optional): Position to remove from. If None, removes by value.
            Must be between 0 and notepad length-1 inclusive. Defaults to None.

    Returns:
        DataFrame: A new DataFrame with the specified value removed

    Raises:
        ValueError: If position is not a valid integer or is out of bounds
    """
    notepad_length = notepad.shape[0]

    # If position is provided, validate it's within bounds
    if position is not None:
        if not isinstance(position, int):
            msg = f"Position must be an integer, got {type(position)}"
            raise ValueError(msg)
        if position < 0 or position >= notepad_length:
            msg = f"Position {position} is out of bounds for notepad of length {notepad_length}"
            raise ValueError(msg)
        # Remove at valid position
        return notepad.drop(notepad.index[position]).reset_index(drop=True)

    # Remove by value if it exists
    if notepad_length > 0 and len(notepad[notepad["value"] == value]) > 0:
        return notepad[notepad["value"] != value].reset_index(drop=True)

    return notepad


def edit_value(notepad: DataFrame, value: str, position: int | None = None) -> DataFrame:
    """Edit a value in the notepad at the specified position or the last row.

    Args:
        notepad (DataFrame): The current notepad DataFrame
        value (str): The new value to set
        position (int | None, optional): Position to edit. If None, edits last row.
            Must be between 0 and notepad length-1 inclusive. Defaults to None.

    Returns:
        DataFrame: A new DataFrame with the value edited at the specified position
    """
    notepad_length = notepad.shape[0]
    if notepad_length == 0:
        return notepad

    new_df = notepad.copy()
    if position is not None and 0 <= position < notepad_length:
        # Edit at position
        new_df.loc[new_df.index[position], "value"] = value
    else:
        # Edit last row
        new_df.loc[new_df.index[-1], "value"] = value
    return new_df


NOTEPAD_OPERATIONS: dict[str, DfOperation] = {
    "add": add_value,
    "remove": remove_value,
    "edit": edit_value,
}


class NotepadComponent(Component):
    """A component that stores and manages a list of values in a notepad.

    The notepad is implemented as a DataFrame with a single "value" column.
    Values can be added, removed and edited at specific positions or by value.
    Multiple notepads can be managed using different notepad names.

    Attributes:
        display_name (str): Display name shown in the UI
        description (str): Component description
        icon (str): Icon name for the UI
        inputs (list): List of input parameters
        outputs (list): List of output parameters
    """

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
        MessageTextInput(
            name="notepad_name",
            display_name="Notepad Name",
            info="The name of the notepad. Use this to manage multiple notepads.",
            tool_mode=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Notepad", name="notepad", method="process_and_get_notepad"),
    ]

    def _get_notepad_key(self) -> str:
        """Get the unique key for storing this notepad in context.

        This method generates a unique identifier for storing the notepad data in the component's context.
        If a notepad_name is provided, it will be used directly as the key. Otherwise, it generates a key
        by combining the component's ID with "_notepad" suffix.

        Returns:
            str: The unique key to use for storing/retrieving the notepad data. Either the provided
                 notepad_name or "{component_id}_notepad".
        """
        if self.notepad_name:
            return self.notepad_name
        return f"{self._id}_notepad"

    def _initialize_notepad(self) -> None:
        """Initialize an empty notepad if it doesn't exist.

        Creates an empty DataFrame with a "value" column if the notepad key
        doesn't exist in the component context.
        """
        notepad_key = self._get_notepad_key()
        if notepad_key not in self.ctx:
            empty_df = DataFrame(columns=["value"])
            self.update_ctx({notepad_key: empty_df})

    def _get_current_notepad(self) -> DataFrame:
        """Get the current notepad DataFrame from context.

        Returns:
            DataFrame: A copy of the current notepad DataFrame

        Raises:
            TypeError: If the stored notepad is not a DataFrame
        """
        notepad = self.ctx[self._get_notepad_key()].copy()
        if not isinstance(notepad, DataFrame):
            msg = f"Expected notepad to be a DataFrame, but got {type(notepad)}"
            raise TypeError(msg)
        return notepad

    async def process_and_get_notepad(self) -> DataFrame:
        """Process the notepad operation and return the updated notepad.

        Performs the requested operation (add/remove/edit) on the notepad using the
        provided input value and position.

        Returns:
            DataFrame: The updated notepad after performing the operation

        Raises:
            ValueError: If the operation is invalid or fails
        """
        self._initialize_notepad()
        notepad = self._get_current_notepad()

        operation = self.operation
        value = self.input_value
        position = self.position if isinstance(self.position, int) else None

        try:
            operation_func: DfOperation = NOTEPAD_OPERATIONS[operation]
        except KeyError as exc:
            msg = f"Invalid operation: {operation}"
            raise ValueError(msg) from exc

        try:
            new_df = operation_func(notepad, value, position)
        except Exception as exc:
            msg = f"Error performing operation {operation} on notepad: {exc}"
            raise ValueError(msg) from exc

        if not isinstance(new_df, DataFrame):
            new_df = DataFrame(new_df)

        # Update context with the new DataFrame
        self.update_ctx({self._get_notepad_key(): new_df})

        return new_df
