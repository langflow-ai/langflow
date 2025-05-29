---
title: Create custom Python components
slug: /components-custom-components
---

Custom components extend Langflow's functionality through Python classes that inherit from `Component`. This enables integration of new features, data manipulation, external services, and specialized tools.

In Langflow's node-based environment, each node is a "component" that performs discrete functions. Custom components are Python classes which define:

* **Inputs** — Data or parameters your component requires.
* **Outputs** — Data your component provides to downstream nodes.
* **Logic** — How you process inputs to produce outputs.

The benefits of creating custom components include unlimited extensibility, reusability, automatic UI field generation based on inputs, and type-safe connections between nodes.

Create custom components for performing specialized tasks, calling APIs, or adding advanced logic.

Custom components in Langflow are built upon:

* The Python class that inherits from `Component`.
* Class-level attributes that identify and describe the component.
* Input and output lists that determine data flow.
* Internal variables for logging and advanced logic.

## Class-level attributes

Define these attributes to control a custom component's appearance and behavior:

```python
class MyCsvReader(Component):
    display_name = "CSV Reader"      # Shown in node header
    description = "Reads CSV files"  # Tooltip text
    icon = "file-text"              # Visual identifier
    name = "CSVReader"              # Unique internal ID
    documentation = "http://docs.example.com/csv_reader"  # Optional
```

* **display_name**: A user-friendly label in the node header.
* **description**: A brief summary shown in tooltips.
* **icon**: A visual identifier from Langflow's icon library.
* **name**: A unique internal identifier.
* **documentation**: An optional link to external docs.

### Structure of a custom component

A **Langflow custom component** goes beyond a simple class with inputs and outputs. It includes an internal structure with optional lifecycle steps, output generation, front-end interaction, and logic organization.

A basic component:

* Inherits from `langflow.custom.Component`.
* Declares metadata like `display_name`, `description`, `icon`, and more.
* Defines `inputs` and `outputs` lists.
* Implements methods matching output specifications.

A minimal custom component skeleton contains the following:

```python
from langflow.custom import Component
from langflow.template import Output

class MyComponent(Component):
    display_name = "My Component"
    description = "A short summary."
    icon = "sparkles"
    name = "MyComponent"

    inputs = []
    outputs = []

    def some_output_method(self):
        return ...
```
### Internal Lifecycle and Execution Flow

Langflow's engine manages:

* **Instantiation**:  A component is created and internal structures are initialized.
* **Assigning Inputs**: Values from the UI or connections are assigned to component fields.
* **Validation and Setup**: Optional hooks like `_pre_run_setup`.
* **Outputs Generation**: `run()` or `build_results()` triggers output methods.

**Optional Hooks**:

* `initialize_data` or `_pre_run_setup` can run setup logic before the component's main execution.
* `__call__`, `run()`, or `_run()` can be overridden to customize how the component is called or to define custom execution logic.

### Inputs and outputs 

Custom component inputs are defined with properties like:

* `name`, `display_name`
* Optional: `info`, `value`, `advanced`, `is_list`, `tool_mode`, `real_time_refresh`

For example:

* `StrInput`: simple text input.
* `DropdownInput`: selectable options.
* `HandleInput`: specialized connections.

Custom component `Output` properties define:

* `name`, `display_name`, `method`
* Optional: `info`

For more information, see [Custom component inputs and outputs](/components-custom-components#custom-component-inputs-and-outputs).

### Associated Methods

Each output is linked to a method:

* The output method name must match the method name.
* The method typically returns objects like Message, Data, or DataFrame.
* The method can use inputs with `self.<input_name>`.

For example:

```python
Output(
    display_name="File Contents",
    name="file_contents",
    method="read_file"
)
#...
def read_file(self) -> Data:
    path = self.filename
    with open(path, "r") as f:
        content = f.read()
    self.status = f"Read {len(content)} chars from {path}"
    return Data(data={"content": content})
```

### Components with multiple outputs

A component can define multiple outputs.
Each output can have a different corresponding method.
For example:

```python
outputs = [
    Output(display_name="Processed Data", name="processed_data", method="process_data"),
    Output(display_name="Debug Info", name="debug_info", method="provide_debug_info"),
]
```

### Common internal patterns

#### `_pre_run_setup()`

To initialize a custom component with counters set:

```python
def _pre_run_setup(self):
    if not hasattr(self, "_initialized"):
        self._initialized = True
        self.iteration = 0
```

#### Override `run` or `_run`
You can override `async def _run(self): ...` to define custom execution logic, although the default behavior from the base class usually covers most cases.

#### Store data in `self.ctx`
Use `self.ctx` as a shared storage for data or counters across the component's execution flow:

```python
def some_method(self):
    count = self.ctx.get("my_count", 0)
    self.ctx["my_count"] = count + 1
```

## Directory structure requirements

By default, Langflow looks for custom components in the `langflow/components` directory.

If you're creating custom components in a different location using the [LANGFLOW_COMPONENTS_PATH](/environment-variables#LANGFLOW_COMPONENTS_PATH) environment variable, components must be organized in a specific directory structure to be properly loaded and displayed in the UI:

```
/your/custom/components/path/    # Base directory set by LANGFLOW_COMPONENTS_PATH
    └── category_name/          # Required category subfolder that determines menu name
        └── custom_component.py # Component file
```

Components must be placed inside **category folders**, not directly in the base directory.
The category folder name determines where the component appears in the UI menu.

For example, to add a component to the **Helpers** menu, place it in a `helpers` subfolder:

```
/app/custom_components/          # LANGFLOW_COMPONENTS_PATH
    └── helpers/                 # Displayed within the "Helpers" menu
        └── custom_component.py  # Your component
```

You can have **multiple category folders** to organize components into different menus:
```
/app/custom_components/
    ├── helpers/
    │   └── helper_component.py
    └── tools/
        └── tool_component.py
```

This folder structure is required for Langflow to properly discover and load your custom components. Components placed directly in the base directory will not be loaded.

```
/app/custom_components/          # LANGFLOW_COMPONENTS_PATH
    └── custom_component.py      # Won't be loaded - missing category folder!
```

## Custom component inputs and outputs

Inputs and outputs define how data flows through the component, how it appears in the UI, and how connections to other components are validated.

### Inputs

Inputs are defined in a class-level `inputs` list. When Langflow loads the component, it uses this list to render fields and handles in the UI. Users or other components provide values or connections to fill these inputs.

An input is usually an instance of a class from `langflow.io` (such as `StrInput`, `DataInput`, or `MessageTextInput`). The most common constructor parameters are:

* **`name`**: The internal variable name, accessed via `self.<name>`.
* **`display_name`**: The label shown to users in the UI.
* **`info`** *(optional)*: A tooltip or short description.
* **`value`** *(optional)*: The default value.
* **`advanced`** *(optional)*: If `True`, moves the field into the "Advanced" section.
* **`required`** *(optional)*: If `True`, forces the user to provide a value.
* **`is_list`** *(optional)*: If `True`, allows multiple values.
* **`input_types`** *(optional)*: Restricts allowed connection types (e.g., `["Data"]`, `["LanguageModel"]`).

Here are the most commonly used input classes and their typical usage.

**Text Inputs**: For simple text entries.
* **`StrInput`** creates a single-line text field.
* **`MultilineInput`** creates a multi-line text area.

**Numeric and Boolean Inputs**: Ensures users can only enter valid numeric or boolean data.
* **`BoolInput`**, **`IntInput`**, and **`FloatInput`** provide fields for boolean, integer, and float values, ensuring type consistency.

**Dropdowns**: For selecting from predefined options, useful for modes or levels.
* **`DropdownInput`**

**Secrets**: A specialized input for sensitive data, ensuring input is hidden in the UI.
* **`SecretStrInput`** for API keys and passwords.

**Specialized Data Inputs**: Ensures type-checking and color-coded connections in the UI.
* **`DataInput`** expects a `Data` object (typically with `.data` and optional `.text`).
* **`MessageInput`** expects a `Message` object, used in chat or agent-based flows.
* **`MessageTextInput`** simplifies access to the `.text` field of a `Message`.

**Handle-Based Inputs**: Used to connect outputs of specific types, ensuring correct pipeline connections.
- **`HandleInput`**

**File Uploads**: Allows users to upload files directly through the UI or receive file paths from other components.
- **`FileInput`**

**Lists**: Set `is_list=True` to accept multiple values, ideal for batch or grouped operations.

This example defines three inputs: a text field (`StrInput`), a boolean toggle (`BoolInput`), and a dropdown selection (`DropdownInput`).

```python
from langflow.io import StrInput, BoolInput, DropdownInput

inputs = [
    StrInput(name="title", display_name="Title"),
    BoolInput(name="enabled", display_name="Enabled", value=True),
    DropdownInput(name="mode", display_name="Mode", options=["Fast", "Safe", "Experimental"], value="Safe")
]
```

### Outputs

Outputs are defined in a class-level `outputs` list. When Langflow renders a component, each output becomes a connector point in the UI. When you connect something to an output, Langflow automatically calls the corresponding method and passes the returned object to the next component.

An output is usually an instance of `Output` from `langflow.io`, with common parameters:

* **`name`**: The internal variable name.
* **`display_name`**: The label shown in the UI.
* **`method`**: The name of the method called to produce the output.
* **`info`** *(optional)*: Help text shown on hover.

The method must exist in the class, and it is recommended to annotate its return type for better type checking.
You can also set a `self.status` message inside the method to show progress or logs.

**Common Return Types**:
- **`Message`**: Structured chat messages.
- **`Data`**: Flexible object with `.data` and optional `.text`.
- **`DataFrame`**: Pandas-based tables (`langflow.schema.DataFrame`).
- **Primitive types**: `str`, `int`, `bool` (not recommended if you need type/color consistency).

In this example, the `DataToDataFrame` component defines its output using the outputs list. The `df_out` output is linked to the `build_df` method, so when connected in the UI, Langflow calls this method and passes its returned DataFrame to the next node. This demonstrates how each output maps to a method that generates the actual output data.

```python
from langflow.custom import Component
from langflow.io import DataInput, Output
from langflow.schema import Data, DataFrame

class DataToDataFrame(Component):
    display_name = "Data to DataFrame"
    description = "Convert multiple Data objects into a DataFrame"
    icon = "table"
    name = "DataToDataFrame"

    inputs = [
        DataInput(
            name="items",
            display_name="Data Items",
            info="List of Data objects to convert",
            is_list=True
        )
    ]

    outputs = [
        Output(
            name="df_out",
            display_name="DataFrame Output",
            method="build_df"
        )
    ]

    def build_df(self) -> DataFrame:
        rows = []
        for item in self.items:
            row_dict = item.data.copy() if item.data else {}
            row_dict["text"] = item.get_text() or ""
            rows.append(row_dict)

        df = DataFrame(rows)
        self.status = f"Built DataFrame with {len(rows)} rows."
        return df
```


### Tool mode

You can configure a Custom Component to work as a **Tool** by setting the parameter `tool_mode=True`. This allows the component to be used in Langflow's Tool Mode workflows, such as by Agent components.

Langflow currently supports the following input types for Tool Mode:

* `DataInput`
* `DataFrameInput`
* `PromptInput`
* `MessageTextInput`
* `MultilineInput`
* `DropdownInput`

```python
inputs = [
    MessageTextInput(
        name="message",
        display_name="Mensage",
        info="Enter the message that will be processed directly by the tool",
        tool_mode=True,
    ),
]
```

## Typed annotations

In Langflow, **typed annotations** allow Langflow to visually guide users and maintain flow consistency.

Typed annotations provide:

* **Color-coding**: Outputs like `-> Data` or `-> Message` get distinct colors.
* **Validation**: Langflow blocks incompatible connections automatically.
* **Readability**: Developers can quickly understand data flow.
* **Development tools**: Better code suggestions and error checking in your code editor.

### Common Return Types

**`Message`**

For chat-style outputs.

```python
def produce_message(self) -> Message:
    return Message(text="Hello! from typed method!", sender="System")
```
In the UI, connects only to Message-compatible inputs.

**`Data`**

For structured data like dicts or partial texts.
```python
def get_processed_data(self) -> Data:
    processed = {"key1": "value1", "key2": 123}
    return Data(data=processed)
```

In the UI, connects only with DataInput.

**`DataFrame`**

For tabular data

```python
def build_df(self) -> DataFrame:
    pdf = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
    return DataFrame(pdf)

```

In the UI, connects only to DataFrameInput.

**Primitive Types (`str`, `int`, `bool`)**

Returning primitives is allowed but wrapping in Data or Message is recommended for better UI consistency.

```python
def compute_sum(self) -> int:
    return sum(self.numbers)
```

### Tips for typed annotations

When using typed annotations, consider the following best practices:

* **Always Annotate Outputs**: Specify return types like `-> Data`, `-> Message`, or `-> DataFrame` to enable proper UI color-coding and validation.
* **Wrap Raw Data**: Use `Data`, `Message`, or `DataFrame` wrappers instead of returning plain structures.
* **Use Primitives Carefully**: Direct `str` or `int` returns are fine for simple flows, but wrapping improves flexibility.
* **Annotate Helpers Too**: Even if internal, typing improves maintainability and clarity.
* **Handle Edge Cases**: Prefer returning structured `Data` with error fields when needed.
* **Stay Consistent**: Use the same types across your components to make flows predictable and easier to build.


## Enable dynamic fields

In **Langflow**, dynamic fields allow inputs to change or appear based on user interactions. You can make an input dynamic by setting `dynamic=True`.
Optionally, setting `real_time_refresh=True` triggers the `update_build_config` method to adjust the input's visibility or properties in real time, creating a contextual UI that only displays relevant fields based on the user's choices.

In this example, the operator field triggers updates via `real_time_refresh=True`.
The `regex_pattern` field is initially hidden and controlled via `dynamic=True`.

```python
from langflow.io import DropdownInput, StrInput

class RegexRouter(Component):
    display_name = "Regex Router"
    description = "Demonstrates dynamic fields for regex input."

    inputs = [
        DropdownInput(
            name="operator",
            display_name="Operator",
            options=["equals", "contains", "regex"],
            value="equals",
            real_time_refresh=True,
        ),
        StrInput(
            name="regex_pattern",
            display_name="Regex Pattern",
            info="Used if operator='regex'",
            dynamic=True,
            show=False,
        ),
    ]
```

### Implement `update_build_config`

When a field with `real_time_refresh=True` is modified, Langflow calls the `update_build_config` method, passing the updated field name, value, and the component's configuration to dynamically adjust the visibility or properties of other fields based on user input.

This example will show or hide the `regex_pattern` field when the user selects a different operator.

```python
def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
    if field_name == "operator":
        if field_value == "regex":
            build_config["regex_pattern"]["show"] = True
        else:
            build_config["regex_pattern"]["show"] = False
    return build_config
```

### Additional Dynamic Field Controls

You can also modify other properties within `update_build_config`, such as:
* `required`: Set `build_config["some_field"]["required"] = True/False`

* `advanced`: Set `build_config["some_field"]["advanced"] = True`

* `options`: Modify dynamic dropdown options.

### Tips for Managing Dynamic Fields

When working with dynamic fields, consider the following best practices to ensure a smooth user experience:

* **Minimize field changes**: Hide only fields that are truly irrelevant to avoid confusing users.
* **Test behavior**: Ensure that adding or removing fields doesn't accidentally erase user input.
* **Preserve data**: Use `build_config["some_field"]["show"] = False` to hide fields without losing their values.
* **Clarify logic**: Add `info` notes to explain why fields appear or disappear based on conditions.
* **Keep it manageable**: If the dynamic logic becomes too complex, consider breaking it into smaller components, unless it serves a clear purpose in a single node.


## Error handling and logging

In Langflow, robust error handling ensures that your components behave predictably, even when unexpected situations occur, such as invalid inputs, external API failures, or internal logic errors.

### Error handling techniques

* **Raise Exceptions**:
  If a critical error occurs, you can raise standard Python exceptions such as `ValueError`, or specialized exceptions like `ToolException`. Langflow will automatically catch these and display appropriate error messages in the UI, helping users quickly identify what went wrong.
  ```python
  def compute_result(self) -> str:
      if not self.user_input:
          raise ValueError("No input provided.")
      # ...
  ```
* **Return Structured Error Data**:
  Instead of stopping a flow abruptly, you can return a Data object containing an "error" field. This approach allows the flow to continue operating and enables downstream components to detect and handle the error gracefully.
  ```python
  def run_model(self) -> Data:
    try:
        # ...
    except Exception as e:
        return Data(data={"error": str(e)})
  ```

### Improve debugging and flow management

* **Use `self.status`**:
  Each component has a status field where you can store short messages about the execution result—such as success summaries, partial progress, or error notifications. These appear directly in the UI, making troubleshooting easier for users.
  ```python
  def parse_data(self) -> Data:
  # ...
  self.status = f"Parsed {len(rows)} rows successfully."
  return Data(data={"rows": rows})
  ```
* **Stop specific outputs with `self.stop(...)`**:
  You can halt individual output paths when certain conditions fail, without affecting the entire component. This is especially useful when working with components that have multiple output branches.
  ```python
  def some_output(self) -> Data:
  if <some condition>:
      self.stop("some_output")  # Tells Langflow no data flows
      return Data(data={"error": "Condition not met"})
  ```

* **Log events**:
  You can log key execution details inside components. Logs are displayed in the "Logs" or "Events" section of the component's detail view and can be accessed later through the flow's debug panel or exported files, providing a clear trace of the component's behavior for easier debugging.
  ```python
  def process_file(self, file_path: str):
  self.log(f"Processing file {file_path}")
  # ...
  ```

### Tips for error handling and logging

To build more reliable components, consider the following best practices:

* **Validate inputs early**: Catch missing or invalid inputs at the start to prevent broken logic.
* **Summarize with `self.status`**: Use short success or error summaries to help users understand results quickly.
* **Keep logs concise**: Focus on meaningful messages to avoid cluttering the UI.
* **Return structured errors**: When appropriate, return `Data(data={"error": ...})` instead of raising exceptions to allow downstream handling.
* **Stop outputs selectively**: Only halt specific outputs with `self.stop(...)` if necessary, to preserve correct flow behavior elsewhere.

## Contribute custom components to Langflow

See [How to Contribute](/contributing-components) to contribute your custom component to Langflow.

