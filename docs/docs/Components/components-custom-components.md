---
title: Custom components
slug: /components-custom-components
---

Custom Components extend Langflow's functionality through Python classes that inherit from `Component`. This enables integration of new features, data manipulation, external services, and specialized tools.

## Overview

In Langflow's node-based environment, each node is a "component" performing discrete functions. Custom Components are Python classes defining:

- **Inputs** — Data or parameters your component requires
- **Outputs** — Data your component provides to downstream nodes
- **Logic** — How you process inputs to produce outputs

## Key Benefits

- **Unlimited Extensibility**: Leverage any Python library in Langflow
- **Reusability**: Save and share components for future projects
- **User-Friendly Configuration**: Automatic UI field generation based on inputs
- **Type-Safe Connections**: Ensure compatible node connections with typed inputs/outputs

## When to Create Custom Components

Create a Custom Component when:

- **Performing Specialized Data Processing**: Converting PDFs to structured data, parsing CSV logs
- **Integrating External Services**: Calling APIs with user-provided credentials
- **Implementing Custom AI Tools**: Creating specialized text-generation functions or chain-of-thought agents
- **Adding Advanced Logic**: Implementing if-else routing, looping, concurrency, or memory management

## Example Scenarios

- **Data Transformations**: Transform or filter a `Data` or `DataFrame` object before passing it to a large language model
- **Conditional Routing**: A router that checks an incoming `Message` and branches the output according to custom logic

# Component Fundamentals

Custom Components in Langflow revolve around:

- The Python class that inherits from `Component`
- Class-level attributes that identify and describe the component
- Input and output lists that determine data flow
- Internal variables for logging and advanced logic

## Class-Level Attributes

Define these attributes to control a Custom Component's appearance and behavior:

```python
class MyCsvReader(Component):
    display_name = "CSV Reader"      # Shown in node header
    description = "Reads CSV files"  # Tooltip text
    icon = "file-text"              # Visual identifier
    name = "CSVReader"              # Unique internal ID
    documentation = "http://docs.example.com/csv_reader"  # Optional
```

### Attribute Details

- **display_name**: User-friendly label in the node header
- **description**: Brief summary shown in tooltips
- **icon**: Visual identifier from Langflow's icon library
- **name**: Unique internal identifier
- **documentation**: Optional link to external docs

## Directory structure requirements

By default, Langflow looks for custom components in the `langflow/components` directory.

If you're creating custom components in a different location using the [LANGFLOW_COMPONENTS_PATH](/environment-variables#LANGFLOW_COMPONENTS_PATH)
`LANGFLOW_COMPONENTS_PATH` environment variable, components must be organized in a specific directory structure to be properly loaded and displayed in the UI:

```
/your/custom/components/path/    # Base directory (set by LANGFLOW_COMPONENTS_PATH)
    └── category_name/          # Required category subfolder (determines menu name)
        └── custom_component.py # Component file
```

Components must be placed inside **category folders**, not directly in the base directory.
The category folder name determines where the component appears in the UI menu.

For example, to add a component to the **Helpers** menu, place it in a `helpers` subfolder:

```
/app/custom_components/          # LANGFLOW_COMPONENTS_PATH
    └── helpers/                 # Shows up as "Helpers" menu
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

## Inputs and Outputs

### Defining Inputs

Specify an inputs list with input definition objects:

```python
from langflow.io import StrInput, DataInput
from langflow.schema import Data

class MyParser(Component):
    inputs = [
        StrInput(name="filename", display_name="Filename", info="Path to file"),
        DataInput(name="config", display_name="Config Data", info="Settings for parsing"),
    ]
```

This creates:
- A text field for "Filename"
- A handle expecting a `Data` object for "Config Data"

### Defining Outputs

Each component must specify an `outputs` list with `Output` objects:

```python
from langflow.template import Output

class MyParser(Component):
    outputs = [
        Output(display_name="Parsed Data", name="parsed_data", method="parse_file"),
        Output(display_name="Stats", name="stats", method="compute_stats"),
    ]
```

Each output includes:
- `display_name`: User-friendly label
- `name`: Internal reference
- `method`: Method to call for output generation

## The Base Component Class

All custom components inherit from `langflow.custom.Component`, which provides:

- **Initialization & Mapping**: Stores inputs/outputs in internal mappings
- **Parameter Handling**: Binds field values to `self.<input_name>`
- **Execution Flow**: Calls output methods via `_build_results`

### Using self.status

`self.status` is a Component attribute used to update intermediate or final results. It's shown in Langflow's UI logs, making it useful for debugging or summarizing.

```python
def parse_file(self) -> Data:
    parsed_result = {"line_count": 100}
    self.status = f"Parsed 100 lines from {self.filename}"
    return Data(data=parsed_result)
```

### Accessing Inputs

Inside any method, you can reference your defined inputs `via self.<input_name>`. For instance

```python
def parse_file(self) -> Data:
    file_path = self.filename  # from StrInput
    # ...
```

## Type Annotations

Use typed return methods:

```python
def parse_file(self) -> Data:
    ...

def process_items(self) -> List[Data]:
    ...
```

Benefits:
- UI color-coding for different types
- Type validation for connections
- Improved code readability

## Example: Hello World with Annotations

```python
from langflow.custom import Component
from langflow.io import StrInput, Output
from langflow.schema import Message

class HelloWorldComponent(Component):
    display_name = "Hello World"
    description = "Example: Accepts a name, returns a greeting."
    icon = "smile"
    name = "HelloWorld"

    inputs = [
        StrInput(name="username", display_name="User Name", info="Who are we greeting?")
    ]
    outputs = [
        Output(name="greeting", display_name="Greeting", method="generate_greeting"),
    ]

    def generate_greeting(self) -> Message:
        user_name = self.username or "Stranger"
        greeting_str = f"Hello, {user_name}!"
        self.status = greeting_str
        return Message(text=greeting_str)
```

## Component Execution Flow

1. Inputs are resolved from preceding nodes or user fields
2. `_build_results` calls each output method
3. Returned values are stored and passed to subsequent nodes
4. Methods are re-run when fields change

## Additional Fields

Besides the mandatory inputs and outputs, you can define other attributes like documentation, beta, or even internal variables.

```python
class MyCustomThing(Component):
    display_name = "CustomThing"
    description = "A demonstration"
    icon = "puzzle"
    name = "MyCustomThing"
    
    # Internal fields
    debug_mode: bool = False
    # ...
```

These don't appear in the UI unless added to `inputs`.

# Component Structure

A Langflow Custom Component is more than just a class with inputs and outputs. This guide covers the internal structure, lifecycle, and common patterns for building robust components.

## Basic Structure

At its simplest, a component:

```python
from langflow.custom import Component
from langflow.template import Output

class MyComponent(Component):
    display_name = "My Component"
    description = "A short summary."
    icon = "sparkles"
    name = "MyComponent"

    inputs = [
        # input definitions
    ]
    outputs = [
        # output objects
    ]

    def some_output_method(self):
        # your logic
        return ...
```

Key points:
- Class name must be unique in your codebase
- `name` field must be unique to avoid UI collisions
- Output methods must match the `method` field in `Output` objects

## Component Lifecycle

Langflow’s component engine manages the lifecycle of a component—how it is initialized, receives inputs, and produces outputs. Understanding this process helps in structuring advanced logic such as iteration or dynamic configuration.

### 1. Instantiation
When a user drags a component onto the canvas:
- Langflow instantiates the component
- Internal structures for inputs/outputs are populated

### 2. Input Assignment
When a user configures inputs:
- Values are assigned to `self.<input_name>`
- Connected outputs from other components are bound

### 3. Validation and Setup
- Base `Component` runs `_validate_inputs` and `_validate_outputs`
- Optional `_pre_run_setup` is called before output generation

### 4. Output Generation
- `run()` or `build_results()` is invoked
- Each output method is called in turn
- Methods can access inputs via `self.<input_name>`

## Input Configuration

### Basic Input Types

```python
# Simple text input
StrInput(
    name="text_prompt",
    display_name="Text Prompt",
    value="Hello world!"
)

# Dropdown selection
DropdownInput(
    name="log_level",
    display_name="Log Level",
    options=["DEBUG", "INFO", "WARNING", "ERROR"],
    value="INFO"
)

# Handle for type-safe connections
HandleInput(
    name="model",
    display_name="Language Model",
    input_types=["LanguageModel"]
)
```

### Input Properties

- `name`: Code reference identifier
- `display_name`: UI label
- `info`: Tooltip text
- `value`: Default value
- `advanced`: Collapse into "Advanced" section
- `is_list`: Accept multiple items
- `tool_mode`: For agent integration
- `real_time_refresh`: Trigger UI updates

## Output Configuration

### Basic Output Structure

```python
outputs = [
    Output(
        display_name="File Contents",
        name="file_contents",
        method="read_file"
    )
]
```

### Output Properties

- `name`: System identifier
- `display_name`: UI label
- `method`: Method to call
- `info`: Additional tooltip

## Associated Methods

Each output method:
- Must match the `method` field in `Output`
- Should return a typed object
- Can access inputs via `self.<input_name>`

Example:
```python
def read_file(self) -> Data:
    path = self.filename
    with open(path, "r") as f:
        content = f.read()
    self.status = f"Read {len(content)} chars from {path}"
    return Data(data={"content": content})
```

## Multiple Outputs

Components can define multiple outputs:

```python
outputs = [
    Output(display_name="Processed Data", name="processed_data", method="process_data"),
    Output(display_name="Debug Info", name="debug_info", method="provide_debug_info")
]
```

Each output can:
- Return different types
- Provide alternative routes
- Include debug information

## Common Patterns

### 1. Pre-run Setup

```python
def _pre_run_setup(self):
    if not hasattr(self, "_initialized"):
        self._initialized = True
        self.iteration = 0
```

### 2. Context Storage

```python
def some_method(self):
    count = self.ctx.get("my_count", 0)
    self.ctx["my_count"] = count + 1
```

### 3. Conditional Routing

```python
def true_output(self) -> Message:
    if self.condition:
        return Message(text="TRUE")
    else:
        self.stop("true_output")
        return Message(text="")
```

## Example: Conditional Router

```python
from langflow.custom import Component
from langflow.io import MessageTextInput, BoolInput, Output
from langflow.schema.message import Message

class ConditionalRouter(Component):
    display_name = "If/Else Router"
    description = "Routes input based on condition"
    icon = "split"
    name = "ConditionalRouter"

    inputs = [
        MessageTextInput(name="input_text", display_name="Input Text"),
        BoolInput(name="check_nonempty", display_name="Check Non-Empty", value=True)
    ]
    outputs = [
        Output(display_name="True", name="true_result", method="true_output"),
        Output(display_name="False", name="false_result", method="false_output")
    ]

    def _pre_run_setup(self):
        if not hasattr(self, "_router_init"):
            self.ctx["true_count"] = 0
            self.ctx["false_count"] = 0
            self._router_init = True

    def true_output(self) -> Message:
        if self.evaluate_condition():
            self.ctx["true_count"] += 1
            self.status = f"True route triggered {self.ctx['true_count']} times"
            return Message(text=f"TRUE: {self.input_text}")
        else:
            self.stop("true_result")
            return Message(text="")

    def false_output(self) -> Message:
        if not self.evaluate_condition():
            self.ctx["false_count"] += 1
            self.status = f"False route triggered {self.ctx['false_count']} times"
            return Message(text=f"FALSE: {self.input_text}")
        else:
            self.stop("false_result")
            return Message(text="")

    def evaluate_condition(self) -> bool:
        if self.check_nonempty:
            return bool(self.input_text.strip())
        return False
```

Key features:
- Uses `_pre_run_setup` for initialization
- Tracks route counts in `self.ctx`
- Uses `self.stop()` to control output flow
- Separates condition evaluation from routing logic

# Inputs and Outputs

Inputs and outputs are the core of any Langflow Custom Component, defining how data flows through the component and how it connects with others. This guide covers the major input types, output patterns, and best practices.

## Input Types

### Basic Input Properties

Inputs in Langflow are typically created using classes from `langflow.io` (e.g., `StrInput`, `DataInput`, `MessageTextInput`, etc.). All input types share a common set of properties:

- **`name`**: Internal variable name, accessed in code via `self.<name>`.
- **`display_name`**: Label shown in the UI.
- **`info`** *(optional)*: Tooltip or short description.
- **`value`** *(optional)*: Default or initial value.
- **`advanced`** *(optional)*: If `True`, places the field in a collapsible "Advanced" section.
- **`required`** *(optional)*: If `True`, the field must be filled in by the user.
- **`is_list`** *(optional)*: Accepts a list of values instead of a single item.
- **`input_types`** *(optional)*: Restricts the allowed connection types (e.g., `["Data"]`, `["LanguageModel"]`).

These properties allow inputs to be customized both functionally and visually within the Langflow interface.

### Input Customization Options

The Input class provides extensive customization options:

#### Basic Configuration
- `field_type`: Type of field (str, int, etc.)
- `required`: Whether the field is mandatory
- `placeholder`: Placeholder text
- `show`: Whether to display the field
- `value`: Default value
- `name`: Internal identifier
- `display_name`: UI label
- `info`: Tooltip text

#### Advanced Features
- `is_list`: Accept multiple values
- `multiline`: Allow multi-line input
- `advanced`: Collapse into "Advanced" section
- `dynamic`: Enable dynamic field behavior
- `real_time_refresh`: Enable real-time updates
- `refresh_button`: Add a refresh button
- `refresh_button_text`: Customize refresh button text

#### File Handling
- `file_types`: List of accepted file types
- `file_path`: Default file path
- `load_from_db`: Load from database

#### Security and Validation
- `password`: Mask input as password
- `input_types`: Restrict connection types
- `range_spec`: Numeric range constraints

#### UI Customization
- `options`: Dropdown options
- `title_case`: Convert display name to title case

Example with multiple options:
```python
from langflow.io import StrInput

class AdvancedComponent(Component):
    inputs = [
        StrInput(
            name="api_key",
            display_name="API Key",
            field_type="str",
            required=True,
            placeholder="Enter your API key",
            password=True,
            info="Your secret API key",
            advanced=True,
            real_time_refresh=True,
            refresh_button=True,
            refresh_button_text="Test Connection"
        ),
        StrInput(
            name="description",
            display_name="Description",
            multiline=True,
            placeholder="Enter a detailed description",
            show=True,
            title_case=False
        )
    ]
```

### Text Inputs

```python
from langflow.io import StrInput, MultilineInput

class MyComponent(Component):
    inputs = [
        StrInput(name="title", display_name="Title", value="Default Title"),
        MultilineInput(name="description", display_name="Description", info="Enter a detailed description.")
    ]
```

### Numeric and Boolean Inputs

```python
from langflow.io import BoolInput, IntInput, FloatInput

class ExampleComponent(Component):
    inputs = [
        BoolInput(name="use_feature", display_name="Use Feature?", value=True),
        IntInput(name="max_attempts", display_name="Max Attempts", value=5),
        FloatInput(name="threshold", display_name="Threshold", value=0.75)
    ]
```

### Selection Inputs

```python
from langflow.io import DropdownInput

class LogComponent(Component):
    inputs = [
        DropdownInput(
            name="log_level",
            display_name="Log Level",
            options=["DEBUG", "INFO", "WARNING", "ERROR"],
            value="INFO"
        )
    ]
```

### Secure Inputs

```python
from langflow.io import SecretStrInput

class APIConnector(Component):
    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Your secret key for external service."
        )
    ]
```

### Data and Message Inputs

```python
from langflow.io import DataInput, MessageInput, MessageTextInput

class Processor(Component):
    inputs = [
        DataInput(name="data_in", display_name="Data In"),
        MessageInput(name="msg_in", display_name="Message In"),
        MessageTextInput(name="text_in", display_name="Text In")
    ]
```

### Handle Inputs

```python
from langflow.io import HandleInput

class LLMComponent(Component):
    inputs = [
        HandleInput(
            name="model",
            display_name="LLM",
            input_types=["LanguageModel"]
        )
    ]
```

## Outputs

### Basic Output Structure

```python
from langflow.template import Output

class MyComponent(Component):
    outputs = [
        Output(
            name="my_output",
            display_name="My Output",
            method="build_output",
            info="A short help text"
        )
    ]
```

### Common Return Types

1. **Message**: Chat message structure
   ```python
   def process_message(self) -> Message:
       return Message(text="Hello, world!")
   ```

2. **Data**: Flexible data container
   ```python
   def process_data(self) -> Data:
       return Data(data={"key": "value"}, text="Optional text")
   ```

3. **DataFrame**: Tabular data
   ```python
   def process_table(self) -> DataFrame:
       return DataFrame({"column": [1, 2, 3]})
   ```

### Multiple Outputs

```python
class Router(Component):
    outputs = [
        Output(name="valid_data", display_name="Valid Data", method="validate_data"),
        Output(name="error_msg", display_name="Error Message", method="error_output")
    ]

    def validate_data(self) -> Data:
        if self.is_valid:
            return Data(data={"status": "valid"})
        self.stop("valid_data")
        return Data()

    def error_output(self) -> Message:
        if not self.is_valid:
            return Message(text="Invalid data")
        self.stop("error_msg")
        return Message()
```

### Status Updates

```python
def process_data(self) -> Data:
    result = self.perform_operation()
    self.status = f"Processed {len(result)} items"
    return Data(data=result)
```

## Example: Data to DataFrame Converter

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

## Best Practices

1. **Type Safety**
   - Use appropriate input types for data validation
   - Add return type annotations for better UI feedback
   - Leverage `input_types` for handle connections

2. **Error Handling**
   - Use `self.stop()` for conditional outputs
   - Set meaningful status messages
   - Validate inputs before processing

3. **UI Considerations**
   - Provide clear display names
   - Add helpful tooltips
   - Use advanced fields for complex options

4. **Performance**
   - Use `is_list` for batch processing
   - Minimize data copying
   - Cache expensive computations

# Typed Annotations

Typed annotations in Langflow components provide visual feedback, type safety, and better code documentation. This guide covers how to use type annotations effectively in your custom components.

## Why Use Typed Annotations?

### Benefits
- **Visual Feedback**: Color-coded node handles based on return types
- **Type Safety**: Prevents incompatible connections between components
- **Documentation**: Makes code more maintainable and self-documenting
- **IDE Support**: Enables better autocomplete and static analysis

## Common Return Types

### Message
Used for chat or conversation contexts:
```python
def produce_message(self) -> Message:
    return Message(text="Hello from typed method!", sender="System")
```

### Data
Flexible container for structured data:
```python
def get_processed_data(self) -> Data:
    processed = {"key1": "value1", "key2": 123}
    return Data(data=processed)
```

### DataFrame
For tabular data operations:
```python
def build_df(self) -> DataFrame:
    pdf = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
    return DataFrame(pdf)
```

### Primitive Types
Basic Python types (use with caution):
```python
def compute_sum(self) -> int:
    return sum(self.numbers)
```

### Collections
Lists and dictionaries (prefer wrapping in Data):
```python
from typing import List

def produce_list(self) -> List[str]:
    return ["Hello", "World"]
```

## Method Signatures

### Single Output
```python
def build_output(self) -> Message:
    user_text = self.user_input
    return Message(text=user_text.upper())
```

### Complex Output
```python
def process_multiple(self) -> Data:
    results = {}
    for item in self.items:
        # Process items
    return Data(data=results, text="All items processed")
```

### DataFrame Output
```python
def transform_df(self) -> DataFrame:
    new_df = self.df.copy()
    new_df["extra_col"] = 42
    return DataFrame(new_df)
```

## Type Consistency

### Input-Output Matching
```python
class MyComponent(Component):
    inputs = [
        DataInput(name="in_data", display_name="In Data")
    ]

    def parse_data(self) -> Data:
        content = self.in_data.data.get("content", "")
        return Data(data={"processed": True})
```

## Example: Complete Component

```python
from langflow.custom import Component
from langflow.io import DataInput, Output
from langflow.schema import Data, Message

class TypedComponent(Component):
    display_name = "Typed Example"
    description = "Demonstrates type annotations"
    icon = "code"
    name = "TypedExample"

    inputs = [
        DataInput(name="input_data", display_name="Input Data")
    ]

    outputs = [
        Output(name="processed", display_name="Processed Data", method="process_data"),
        Output(name="message", display_name="Status Message", method="get_status")
    ]

    def process_data(self) -> Data:
        try:
            result = self.process_input(self.input_data)
            return Data(data=result)
        except Exception as e:
            return Data(data={"error": str(e)})

    def get_status(self) -> Message:
        if hasattr(self, "last_error"):
            return Message(text=f"Error: {self.last_error}")
        return Message(text="Processing complete")

    def process_input(self, data: Data) -> dict:
        # Internal helper with type annotation
        return {"processed": True, "input": data.data}
```

# Dynamic Fields

Dynamic fields enable the display, concealment, or modification of input fields in response to user interactions. This guide outlines the implementation of dynamic behavior within Langflow components.

## Overview

Dynamic fields enable:
- Conditional field visibility
- Real-time UI updates
- Contextual user experience
- Advanced parameter management

## Implementation

### 1. Marking Fields as Dynamic

```python
from langflow.io import DropdownInput, StrInput

class RegexRouter(Component):
    inputs = [
        DropdownInput(
            name="operator",
            display_name="Operator",
            options=["equals", "contains", "regex"],
            value="equals",
            real_time_refresh=True  # Triggers updates
        ),
        StrInput(
            name="regex_pattern",
            display_name="Regex Pattern",
            dynamic=True,  # Can be shown/hidden
            show=False    # Initially hidden
        )
    ]
```

### 2. Implementing update_build_config

```python
def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
    if field_name == "operator":
        if field_value == "regex":
            build_config["regex_pattern"]["show"] = True
        else:
            build_config["regex_pattern"]["show"] = False
    return build_config
```

## Field Controls

### Visibility
```python
build_config["field_name"]["show"] = True/False
```

### Requirements
```python
build_config["field_name"]["required"] = True/False
```

### Advanced Settings
```python
build_config["field_name"]["advanced"] = True/False
```

### Dynamic Options
```python
build_config["dropdown_name"]["options"] = ["New", "Dynamic", "List"]
```

## Complete Example

```python
class ConditionalRouter(Component):
    display_name = "If/Else"
    inputs = [
        DropdownInput(
            name="operator",
            display_name="Operator",
            options=["equals", "not equals", "contains", "starts with", "ends with", "matches regex"],
            value="equals",
            real_time_refresh=True
        ),
        BoolInput(
            name="case_sensitive",
            display_name="Case Sensitive",
            value=False,
            dynamic=True,
            show=True
        )
    ]

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        if field_name == "operator":
            if field_value == "matches regex":
                build_config.pop("case_sensitive", None)
            else:
                if "case_sensitive" not in build_config:
                    for ipt in self.inputs:
                        if ipt.name == "case_sensitive":
                            build_config["case_sensitive"] = ipt.to_dict()
                            break
        return build_config
```

## Real-Time vs. On-Save

- **Real-Time Updates**
  - Triggered by `real_time_refresh=True`
  - Immediate UI feedback
  - Better user experience

- **On-Save Updates**
  - Changes apply after saving
  - More stable but less responsive
  - Suitable for complex updates

## Common Patterns

1. **Conditional Fields**
   ```python
   if condition:
       build_config["field"]["show"] = True
   else:
       build_config["field"]["show"] = False
   ```

2. **Dynamic Options**
   ```python
   build_config["dropdown"]["options"] = new_options
   ```

3. **Field Requirements**
   ```python
   build_config["field"]["required"] = is_required
   ```

4. **Advanced Settings**
   ```python
   build_config["field"]["advanced"] = is_advanced
   ```

# Error Handling and Logging

This guide covers how to handle errors and provide debugging information in Langflow components.

## Error Handling Strategies

### 1. Raising Exceptions

```python
def compute_result(self) -> str:
    if not self.user_input:
        raise ValueError("No input provided.")
    # ...

# Custom exceptions
from langchain_core.tools import ToolException

def call_api(self):
    if resp.status_code != 200:
        raise ToolException(f"API error: {resp.text}")
```

### 2. Returning Error Data

```python
def run_model(self) -> Data:
    try:
        # ...
    except Exception as e:
        return Data(data={"error": str(e)})
```

**Pros:**
- Flow continues without interruption
- Downstream nodes can handle errors
- More control over error presentation

**Cons:**
- Doesn't automatically break the flow
- Requires explicit error checking

## Status Updates

### Using self.status

```python
def parse_data(self) -> Data:
    # ...
    self.status = f"Parsed {len(rows)} rows successfully."
    return Data(data={"rows": rows})
```

**When to Use:**
- Show final success messages
- Display partial progress
- Report error details
- Summarize operations

## Output Control

### Stopping Outputs

```python
def some_output(self) -> Data:
    if <some condition>:
        self.stop("some_output")  # No data flows
        return Data(data={"error": "Condition not met"})
```

**Effects:**
- Prevents downstream execution
- Allows flow to continue on other paths
- Provides graceful degradation

## Logging

### Basic Logging

```python
def process_file(self, file_path: str):
    self.log(f"Processing file {file_path}")
    # ...
```

**Log Display:**
- Appears in node's detail view
- Accessible in debug panel
- Helps diagnose issues

## External API Handling

```python
def call_api(self) -> Data:
    try:
        resp = requests.get(self.api_url)
        resp.raise_for_status()
        result = resp.json()
        self.status = "API call succeeded."
        return Data(data=result)
    except requests.HTTPError as e:
        error_msg = f"API error: {e}"
        self.log(error_msg)
        self.status = error_msg
        return Data(data={"error": error_msg})
```

## Complete Examples

### 1. Conditional Return with Error

```python
def evaluate_expression(self) -> Data:
    expr = self.expression
    if not expr:
        msg = "No expression provided!"
        self.status = msg
        return Data(data={"error": msg})

    try:
        value = eval(expr)
        self.status = f"Evaluation success: {value}"
        return Data(data={"result": value})
    except Exception as e:
        error_msg = f"Invalid expression: {e}"
        self.status = error_msg
        return Data(data={"error": error_msg, "expression": expr})
```

### 2. Branch Control

```python
def route_message(self) -> Message:
    if self.should_route_to_branch():
        return Message(text="Routed to Branch A")
    else:
        self.stop("branch_a")
        return Message(text="Routed to default branch")
```

## Error Handling Patterns

1. **Hard Failures**
   ```python
   raise ValueError("Critical error occurred")
   ```

2. **Graceful Degradation**
   ```python
   return Data(data={"error": "Operation failed", "partial_result": result})
   ```

3. **Status Updates**
   ```python
   self.status = f"Operation completed with {count} items"
   ```

4. **Output Control**
   ```python
   self.stop("output_name")
   return Data(data={"error": "Branch disabled"})
   ```

# Best Practices

Best practices for building maintainable, efficient, and user-friendly Langflow Custom Components:

## 1. Component Design

- **Single Responsibility**: Keep components focused on a single clear purpose.
- **Divide Complex Logic**: Split complex functionality into smaller, reusable components.
- **Chain Components**: Assemble pipelines by connecting simple components together.

> **Example:**
> Instead of:
> ```python
> class DataIngestAndParseAndAnalyze(Component):
>     ...
> ```
> prefer splitting into:
> - `DataIngest`
> - `ParseFields`
> - `Analysis`

## 2. Naming and Metadata

- **Clear Names**: Use descriptive `display_name` and `description`.
- **Icons**: Choose an icon that visually represents the component’s purpose.
- **Documentation**: Link to external documentation if available.

## 3. Type Annotations

- **Always annotate output methods** with proper types like `-> Data`, `-> Message`, or `-> DataFrame`.
- **Benefits**:
  - Better IDE autocomplete and static analysis.
  - UI color-coding for output types.
  - Automatic type validation between components.

> **Example:**
> ```python
> def parse_file(self) -> Data:
>     ...
> ```

## 4. Status Updates

- **Use `self.status`** to provide progress or useful messages in the Langflow UI.
- Update the status field at important stages during execution.

> **Example:**
> ```python
> self.status = f"Processed {len(rows)} rows successfully."
> ```

## 5. Error Handling

- **Validate inputs early** to avoid runtime failures.
- **Use `raise`** for critical errors and **`self.stop()`** to conditionally halt specific outputs.
- **Return structured error information** when graceful degradation is needed.

> **Example:**
> ```python
> return Data(data={"error": "Invalid input"})
> ```

## 6. Dynamic Fields

- **Use sparingly**: Only hide/show fields when it truly improves the UX.
- **Preserve values**: Don't delete field data when hiding it.
- **Real-Time Updates**: Prefer `real_time_refresh=True` for immediate UI feedback.

## 7. Output Control

- **Use `self.stop("output_name")`** inside an output method to prevent that output from propagating if a condition fails.
- Essential for building conditional routers or validators.

## 8. UI/UX Considerations

- **Organize fields**: Separate basic and advanced settings (`advanced=True`).
- **Tooltips (`info`)**: Add helpful descriptions to all non-trivial fields.
- **Simple Layouts**: Keep the interface intuitive and easy to configure.

## 9. Performance Optimization

- **Batch Processing**: Use `is_list=True` on inputs to process multiple elements efficiently.
- **Minimize Copies**: Avoid unnecessary duplication of large datasets.
- **Cache Results**: Cache expensive computations when possible.

## 10. Documentation

- **Docstrings**: Document component classes and important methods.
- **Field Descriptions**: Clearly explain what each input and output does.
- **Usage Examples**: Provide examples when the usage is not obvious.

## 11. Output Methods Best Practices

- **Always annotate output methods** with proper return types (`-> Data`, `-> Message`, `-> DataFrame`).
- **Use wrapper classes** appropriately:
  - `Message` for conversational content.
  - `Data` for structured information.
  - `DataFrame` for tabular datasets.
- **Avoid returning raw primitives** like `str`, `dict`, or `list` directly; wrap them in `Data` whenever possible.
- **Keep output method signatures consistent** within the component.
- **Separate complex output logic** into private helper methods if needed.
- **Document each output properly** using the `info` attribute in the `Output` configuration for clarity.

> **Example:**
> ```python
> def build_output(self) -> Message:
>     user_text = self.user_input
>     return Message(text=user_text.upper())

## Contribute Custom Components to Langflow

See [How to Contribute](/contributing-components) to contribute your custom component to Langflow.
