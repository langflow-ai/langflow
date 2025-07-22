from langflow.custom import Component

# Import all input types
from langflow.io import (
    BoolInput,
    DataFrameInput,
    DataInput,
    DictInput,
    DropdownInput,
    FloatInput,
    IntInput,
    MessageInput,
    MessageTextInput,
    MultilineInput,
    MultiselectInput,
    NestedDictInput,
    Output,
    PromptInput,
    StrInput,
    TableInput,
)
from langflow.schema import Data
from pydantic import BaseModel

from lfx.base.tools.component_tool import ComponentToolkit


class AllInputsComponent(Component):
    display_name = "All Inputs Component"
    description = "A component with all input types available in Langflow."
    documentation: str = "http://docs.langflow.org/components/all_inputs"
    icon = "code"
    name = "AllInputsComponent"

    inputs = [
        TableInput(
            name="table_input",
            display_name="Table Input",
            info="Input for table data.",
            value=[],
            tool_mode=True,
            table_schema=[
                {"name": "id", "type": "int"},
                {"name": "name", "type": "str"},
            ],
        ),
        DataInput(name="data_input", display_name="Data Input", info="Input for data objects.", tool_mode=True),
        DataFrameInput(
            name="dataframe_input", display_name="DataFrame Input", info="Input for DataFrame objects.", tool_mode=True
        ),
        PromptInput(name="prompt_input", display_name="Prompt Input", info="Input for prompt data.", tool_mode=True),
        StrInput(name="str_input", display_name="String Input", info="Input for string data.", tool_mode=True),
        MessageInput(
            name="message_input", display_name="Message Input", info="Input for message objects.", tool_mode=True
        ),
        MessageTextInput(
            name="message_text_input", display_name="Message Text Input", info="Input for message text.", tool_mode=True
        ),
        MultilineInput(
            name="multiline_input", display_name="Multiline Input", info="Input for multiline text.", tool_mode=True
        ),
        IntInput(name="int_input", display_name="Integer Input", info="Input for integer values.", tool_mode=True),
        FloatInput(name="float_input", display_name="Float Input", info="Input for float values.", tool_mode=True),
        BoolInput(name="bool_input", display_name="Boolean Input", info="Input for boolean values.", tool_mode=True),
        NestedDictInput(
            name="nested_dict_input",
            display_name="Nested Dictionary Input",
            info="Input for nested dictionary data.",
            tool_mode=True,
            value={"key1": "value1", "key2": "value2"},
        ),
        DictInput(
            name="dict_input",
            display_name="Dictionary Input",
            info="Input for dictionary data.",
            tool_mode=True,
            is_list=True,
            value={"key1": "value1", "key2": "value2"},
        ),
        DropdownInput(
            name="dropdown_input",
            display_name="Dropdown Input",
            info="Input for dropdown selections.",
            tool_mode=True,
            options=["option1", "option2", "option3"],
            value="option1",
        ),
        MultiselectInput(
            name="multiselect_input",
            display_name="Multiselect Input",
            info="Input for multiple selections.",
            tool_mode=True,
            options=["option1", "option2", "option3"],
            value=["option1", "option2"],
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    def build_output(self) -> Data:
        # Example logic to process inputs and produce an output
        data_dict = {
            "table_input": self.table_input,
            "data_input": self.data_input,
            "dataframe_input": self.dataframe_input,
            "prompt_input": self.prompt_input,
            "str_input": self.str_input,
            "message_input": self.message_input,
            "message_text_input": self.message_text_input,
            "multiline_input": self.multiline_input,
            "int_input": self.int_input,
            "float_input": self.float_input,
            "bool_input": self.bool_input,
        }
        data = Data(value=data_dict)
        self.status = data
        return data


def test_component_inputs_toolkit():
    component = AllInputsComponent()
    component_toolkit = ComponentToolkit(component=component)
    component_tool = component_toolkit.get_tools()[0]
    assert component_tool.name == "build_output"
    assert issubclass(component_tool.args_schema, BaseModel)
    properties = component_tool.args_schema.model_json_schema()["properties"]

    # Define expected properties based on the component's inputs
    expected_inputs = {
        "table_input": {"title": "Table Input", "description": "Input for table data."},
        "data_input": {"title": "Data Input", "description": "Input for data objects."},
        "dataframe_input": {"title": "Dataframe Input", "description": "Input for DataFrame objects."},
        "prompt_input": {"title": "Prompt Input", "description": "Input for prompt data."},
        "str_input": {"title": "Str Input", "description": "Input for string data."},
        "message_input": {"title": "Message Input", "description": "Input for message objects."},
        "message_text_input": {"title": "Message Text Input", "description": "Input for message text."},
        "multiline_input": {"title": "Multiline Input", "description": "Input for multiline text."},
        # TODO: to check how the title is generated, Shouldnt it  be the display name?
        "int_input": {"title": "Int Input", "description": "Input for integer values."},
        "float_input": {"title": "Float Input", "description": "Input for float values."},
        "bool_input": {"title": "Bool Input", "description": "Input for boolean values."},
        "nested_dict_input": {"title": "Nested Dict Input", "description": "Input for nested dictionary data."},
        "dict_input": {"title": "Dict Input", "description": "Input for dictionary data."},
        "dropdown_input": {"title": "Dropdown Input", "description": "Input for dropdown selections."},
        "multiselect_input": {"title": "Multiselect Input", "description": "Input for multiple selections."},
    }

    # Iterate and assert each input's properties
    for input_name, expected in expected_inputs.items():
        assert input_name in properties, f"{input_name} is missing in properties."
        assert properties[input_name]["title"] == expected["title"], f"Title mismatch for {input_name}."
        assert properties[input_name]["description"] == expected["description"], (
            f"Description mismatch for {input_name}."
        )
