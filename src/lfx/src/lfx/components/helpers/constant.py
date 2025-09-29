from typing import Any

from pandas import DataFrame as PandasDataFrame

from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import (
    AuthInput,
    BoolInput,
    CodeInput,
    DataFrameInput,
    DataInput,
    DictInput,
    DropdownInput,
    FileInput,
    FloatInput,
    HandleInput,
    IntInput,
    LinkInput,
    McpInput,
    MessageInput,
    MessageTextInput,
    MultilineInput,
    MultilineSecretInput,
    MultiselectInput,
    NestedDictInput,
    PromptInput,
    QueryInput,
    SecretStrInput,
    SliderInput,
    SortableListInput,
    StrInput,
    TabInput,
    TableInput,
    ToolsInput,
)
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.dotdict import dotdict
from lfx.schema.message import Message
from lfx.template.field.base import Output


class ConstantComponent(Component):
    display_name = "Constant"
    description = "A configurable constant component that can output different data types based on the selected input type."
    icon = "bookmark"
    name = "Constant"

    inputs = [
        DropdownInput(
            name="input_type",
            display_name="Input Type",
            options=[
                "StrInput",
                "MessageTextInput",
                "MessageInput",
                "MultilineInput",
                "MultilineSecretInput",
                "SecretStrInput",
                "PromptInput",
                "CodeInput",
                "IntInput",
                "FloatInput",
                "SliderInput",
                "BoolInput",
                "DropdownInput",
                "MultiselectInput",
                "TabInput",
                "DictInput",
                "NestedDictInput",
                "TableInput",
                "DataInput",
                "DataFrameInput",
                "FileInput",
                "LinkInput",
                "HandleInput",
                "ToolsInput",
                "AuthInput",
                "QueryInput",
                "McpInput",
                "SortableListInput",
            ],
            info="Choose the type of input field to display",
            value="StrInput",
            real_time_refresh=True,
        )
    ]

    outputs = [
        Output(display_name="Message", name="message_output", method="get_message_output"),
        Output(display_name="Data", name="data_output", method="get_data_output"),
        Output(display_name="DataFrame", name="dataframe_output", method="get_dataframe_output"),
    ]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "input_type":
            # Remove any existing dynamic input
            keys_to_remove = [key for key in build_config.keys() if key not in ["input_type", "_type", "code"]]
            for key in keys_to_remove:
                build_config.pop(key, None)

            # Create the appropriate input based on selection
            input_configs = {
                "StrInput": StrInput(
                    name="value",
                    display_name="Text Value",
                    info="Enter a text value",
                ),
                "MessageTextInput": MessageTextInput(
                    name="value",
                    display_name="Message Text",
                    info="Enter message text",
                ),
                "MessageInput": MessageInput(
                    name="value",
                    display_name="Message",
                    info="Enter a message",
                ),
                "MultilineInput": MultilineInput(
                    name="value",
                    display_name="Multiline Text",
                    info="Enter multiline text",
                ),
                "MultilineSecretInput": MultilineSecretInput(
                    name="value",
                    display_name="Multiline Secret",
                    info="Enter multiline secret text",
                ),
                "SecretStrInput": SecretStrInput(
                    name="value",
                    display_name="Secret",
                    info="Enter a secret value",
                ),
                "PromptInput": PromptInput(
                    name="value",
                    display_name="Prompt",
                    info="Enter a prompt",
                ),
                "CodeInput": CodeInput(
                    name="value",
                    display_name="Code",
                    info="Enter code",
                ),
                "IntInput": IntInput(
                    name="value",
                    display_name="Integer",
                    info="Enter an integer value",
                    value=0,
                ),
                "FloatInput": FloatInput(
                    name="value",
                    display_name="Float",
                    info="Enter a float value",
                    value=0.0,
                ),
                "SliderInput": SliderInput(
                    name="value",
                    display_name="Slider",
                    info="Set slider value",
                    range_spec=RangeSpec(min=0, max=100, step=1),
                    value=50,
                ),
                "BoolInput": BoolInput(
                    name="value",
                    display_name="Boolean",
                    info="Set boolean value",
                    value=False,
                ),
                "DropdownInput": DropdownInput(
                    name="value",
                    display_name="Dropdown Selection",
                    info="Select from dropdown",
                    options=["Option 1", "Option 2", "Option 3"],
                    value="Option 1",
                ),
                "MultiselectInput": MultiselectInput(
                    name="value",
                    display_name="Multiselect",
                    info="Select multiple options",
                    options=["Option 1", "Option 2", "Option 3"],
                    value=[],
                ),
                "TabInput": TabInput(
                    name="value",
                    display_name="Tab Selection",
                    info="Select tab",
                    options=["Tab 1", "Tab 2", "Tab 3"],
                    value="Tab 1",
                ),
                "DictInput": DictInput(
                    name="value",
                    display_name="Dictionary",
                    info="Enter dictionary data",
                    value={},
                ),
                "NestedDictInput": NestedDictInput(
                    name="value",
                    display_name="Nested Dictionary",
                    info="Enter nested dictionary data",
                    value={},
                ),
                "TableInput": TableInput(
                    name="value",
                    display_name="Table",
                    info="Enter table data",
                    value=[],
                ),
                "DataInput": DataInput(
                    name="value",
                    display_name="Data Object",
                    info="Connect a Data object",
                ),
                "DataFrameInput": DataFrameInput(
                    name="value",
                    display_name="DataFrame",
                    info="Connect a DataFrame",
                ),
                "FileInput": FileInput(
                    name="value",
                    display_name="File",
                    info="Select a file",
                ),
                "LinkInput": LinkInput(
                    name="value",
                    display_name="Link",
                    info="Enter a URL or link",
                ),
                "HandleInput": HandleInput(
                    name="value",
                    display_name="Handle",
                    info="Connect a handle",
                ),
                "ToolsInput": ToolsInput(
                    name="value",
                    display_name="Tools",
                    info="Configure tools",
                    value=[],
                ),
                "AuthInput": AuthInput(
                    name="value",
                    display_name="Authentication",
                    info="Configure authentication",
                ),
                "QueryInput": QueryInput(
                    name="value",
                    display_name="Query",
                    info="Enter search query",
                ),
                "McpInput": McpInput(
                    name="value",
                    display_name="MCP",
                    info="Configure MCP input",
                    value={},
                ),
                "SortableListInput": SortableListInput(
                    name="value",
                    display_name="Sortable List",
                    info="Configure sortable list",
                    value=[],
                ),
            }

            if field_value in input_configs:
                input_config = input_configs[field_value]
                build_config["value"] = input_config.to_dict()

        return build_config

    def get_message_output(self) -> Message:
        """Convert the input value to a Message object."""
        value = getattr(self, "value", None)
        
        if isinstance(value, Message):
            return value
        elif isinstance(value, Data):
            return Message(text=value.get_text())
        elif isinstance(value, (str, int, float, bool)):
            return Message(text=str(value))
        elif isinstance(value, dict):
            return Message(text=str(value))
        elif isinstance(value, list):
            if len(value) > 0 and isinstance(value[0], str):
                return Message(text=", ".join(value))
            else:
                return Message(text=str(value))
        elif isinstance(value, PandasDataFrame):
            return Message(text=value.to_string())
        else:
            return Message(text=str(value) if value is not None else "")

    def get_data_output(self) -> Data:
        """Convert the input value to a Data object."""
        value = getattr(self, "value", None)
        
        if isinstance(value, Data):
            return value
        elif isinstance(value, Message):
            return Data(text=value.text)
        elif isinstance(value, (str, int, float, bool)):
            return Data(text=str(value), data={"value": value})
        elif isinstance(value, dict):
            return Data(data=value, text=str(value))
        elif isinstance(value, list):
            if len(value) > 0:
                if isinstance(value[0], dict):
                    # List of dictionaries - create a composite data object
                    return Data(data={"items": value}, text=f"List with {len(value)} items")
                elif isinstance(value[0], str):
                    return Data(text=", ".join(value), data={"items": value})
                else:
                    return Data(text=str(value), data={"items": value})
            else:
                return Data(text="Empty list", data={"items": []})
        elif isinstance(value, PandasDataFrame):
            return Data(data={"dataframe": value.to_dict()}, text=f"DataFrame with {len(value)} rows")
        else:
            return Data(text=str(value) if value is not None else "", data={"value": value})

    def get_dataframe_output(self) -> DataFrame:
        """Convert the input value to a DataFrame object."""
        value = getattr(self, "value", None)
        
        if isinstance(value, PandasDataFrame):
            return DataFrame(value)
        elif isinstance(value, list):
            if len(value) > 0:
                if isinstance(value[0], dict):
                    # List of dictionaries can be converted to DataFrame
                    df = PandasDataFrame(value)
                    return DataFrame(df)
                elif isinstance(value[0], Data):
                    # List of Data objects
                    data_list = [data.data for data in value]
                    df = PandasDataFrame(data_list)
                    return DataFrame(df)
                else:
                    # Simple list - create single column DataFrame
                    df = PandasDataFrame({"value": value})
                    return DataFrame(df)
            else:
                # Empty list
                df = PandasDataFrame()
                return DataFrame(df)
        elif isinstance(value, dict):
            # Single dictionary - create DataFrame with one row
            df = PandasDataFrame([value])
            return DataFrame(df)
        elif isinstance(value, Data):
            # Single Data object
            df = PandasDataFrame([value.data])
            return DataFrame(df)
        elif isinstance(value, (str, int, float, bool)):
            # Single value - create DataFrame with one column and one row
            df = PandasDataFrame({"value": [value]})
            return DataFrame(df)
        else:
            # Default case - create empty DataFrame
            df = PandasDataFrame()
            return DataFrame(df)