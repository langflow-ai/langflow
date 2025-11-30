# FunctionComponent Feature Research & Implementation Plan

## Executive Summary

This document outlines the research findings and implementation plan for enabling arbitrary Python functions to be used as Langflow Components. The goal is to allow developers to connect functions directly to components and other functions within a graph, with the system automatically generating inputs/outputs from the function signature.

---

## 1. Current Architecture Overview

### 1.1 How Graphs Are Built

Graphs in Langflow are built by connecting Component instances using the `set()` method or by programmatically adding components and edges:

**Pattern 1: Using `set()` for connections**
```python
chat_input = ChatInput(_id="chat_input")
chat_output = ChatOutput(_id="chat_output")
chat_output.set(input_value=chat_input.message_response)
graph = Graph(chat_input, chat_output)
```

**Pattern 2: Manual edge creation**
```python
graph = Graph()
input_id = graph.add_component(ChatInput())
output_id = graph.add_component(ChatOutput())
graph.add_component_edge(input_id, ("message", "input_value"), output_id)
```

### 1.2 The Component.set() Method

**Location:** `src/lfx/src/lfx/custom/custom_component/component.py:412-426`

```python
def set(self, **kwargs):
    """Connects the component to other components or sets parameters."""
    for key, value in kwargs.items():
        self._process_connection_or_parameters(key, value)
    return self
```

**The `_process_connection_or_parameter()` method (lines 754-775) handles three cases:**

1. **Component Instance** (`isinstance(value, Component)`):
   - Calls `_find_matching_output_method()` to find the output that matches the input type
   - Returns the bound method of that output

2. **Callable from Component** (`callable(value) and self._inherits_from_component(value)`):
   - Validates it's a proper output method
   - Creates an edge via `_connect_to_component()`

3. **Other Values**:
   - Sets as parameter via `_set_parameter_or_attribute()`

**Key insight:** The system does NOT currently handle plain Python functions (non-Component callables).

### 1.3 How Edges Are Created

When components are connected via `set()`, the `_add_edge()` method (lines 866-886) creates edge data:

```python
def _add_edge(self, component, key, output, input_) -> None:
    self._edges.append({
        "source": component._id,
        "target": self._id,
        "data": {
            "sourceHandle": {
                "dataType": component.name or component.__class__.__name__,
                "id": component._id,
                "name": output.name,
                "output_types": output.types,
            },
            "targetHandle": {
                "fieldName": key,
                "id": self._id,
                "inputTypes": input_.input_types,
                "type": input_.field_type,
            },
        },
    })
```

### 1.4 Graph Component Processing

**Location:** `src/lfx/src/lfx/graph/graph/base.py:269-290`

The `add_component()` method:
1. Generates/uses component ID
2. Calls `component.to_frontend_node()` to serialize the component
3. Creates a Vertex from the frontend node
4. Adds edges from `component.get_edges()`
5. **Recursively** adds connected components from `component.get_components()`

This recursive behavior is crucial - it means that if a FunctionComponent is connected, it will automatically be discovered and added to the graph.

### 1.5 Type Extraction System

**Location:** `src/lfx/src/lfx/type_extraction/type_extraction.py`

The system extracts types from method signatures using:
- `get_type_hints()` from `typing` module
- `post_process_type()` to handle generics, unions, lists

**Location:** `src/lfx/src/lfx/custom/custom_component/component.py:987-993`

```python
def _get_method_return_type(self, method_name: str) -> list[str]:
    method = getattr(self, method_name)
    return_type = get_type_hints(method).get("return")
    if return_type is None:
        return []
    extracted_return_types = self._extract_return_type(return_type)
    return [format_type(extracted_return_type) for extracted_return_type in extracted_return_types]
```

### 1.6 Input/Output System

**Input Definition** (`src/lfx/src/lfx/template/field/base.py:34-174`):
- `input_types: list[str]` - Types this input accepts for connections
- `field_type: str` - The field type (str, int, etc.)
- `info: str` - Description shown in UI
- `name: str` - Unique identifier
- `display_name: str` - Human-readable name

**Output Definition** (`src/lfx/src/lfx/template/field/base.py:176-261`):
- `types: list[str]` - Output types for connection matching
- `method: str` - Name of method that produces this output
- `name: str` - Unique identifier

**Type Matching:** Edges are valid when `output.types` intersects with `input.input_types`.

---

## 2. The lfx.base Module Structure

**Location:** `src/lfx/src/lfx/base/`

The module contains 26+ specialized base classes organized by component type:

| Directory | Base Class | Trace Type |
|-----------|------------|------------|
| `models/` | `LCModelComponent` | `"llm"` |
| `agents/` | `LCAgentComponent` | `"agent"` |
| `chains/` | `LCChainComponent` | `"chain"` |
| `tools/` | `LCToolComponent` | `"tool"` |
| `memory/` | `LCChatMemoryComponent` | `"chat_memory"` |
| `embeddings/` | `LCEmbeddingsComponent` | - |
| `vectorstores/` | `LCVectorStoreComponent` | - |
| `io/` | `ChatComponent`, `TextComponent` | - |

**Recommendation:** Create `src/lfx/src/lfx/base/functions/` for `FunctionComponent`.

---

## 3. Implementation Plan

### 3.1 Create the FunctionComponent Class

**Location:** `src/lfx/src/lfx/base/functions/function_component.py`

```python
from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, get_type_hints

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, StrInput, IntInput, FloatInput, BoolInput
from lfx.template.field.base import Input, Output
from lfx.type_extraction import post_process_type


# Mapping from Python types to Langflow Input classes
TYPE_TO_INPUT_MAP = {
    str: StrInput,
    int: IntInput,
    float: FloatInput,
    bool: BoolInput,
    # Add more as needed
}

# Mapping from Python types to type strings for input_types
TYPE_TO_TYPE_STRING = {
    str: "Text",
    int: "int",
    float: "float",
    bool: "bool",
    # Message, Data, etc. would map to their respective types
}


class FunctionComponent(Component):
    """A component that wraps an arbitrary Python function.

    This component dynamically generates inputs and outputs based on
    the function's signature and type annotations.
    """

    trace_type = "function"

    def __init__(
        self,
        func: Callable,
        _id: str | None = None,
        **kwargs
    ):
        self._wrapped_function = func
        self._func_name = func.__name__

        # Extract function metadata
        self._signature = inspect.signature(func)
        self._type_hints = get_type_hints(func) if func else {}
        self._docstring = inspect.getdoc(func) or ""
        self._param_docs = self._parse_docstring_params()

        # Build inputs/outputs before parent init
        inputs = self._build_inputs_from_signature()
        outputs = self._build_outputs_from_signature()

        # Set display name from function name
        display_name = self._func_name.replace("_", " ").title()

        super().__init__(
            _id=_id,
            inputs=inputs,
            outputs=outputs,
            display_name=display_name,
            description=self._docstring.split("\n")[0] if self._docstring else None,
            **kwargs
        )

    def _parse_docstring_params(self) -> dict[str, str]:
        """Parse parameter descriptions from docstring (Google/Numpy style)."""
        param_docs = {}
        if not self._docstring:
            return param_docs

        # Simple parsing for common docstring formats
        lines = self._docstring.split("\n")
        in_args_section = False
        current_param = None

        for line in lines:
            stripped = line.strip()

            # Detect Args/Parameters section
            if stripped.lower() in ("args:", "arguments:", "parameters:"):
                in_args_section = True
                continue

            # Detect end of Args section
            if in_args_section and stripped and not stripped.startswith(" ") and ":" in stripped:
                if any(stripped.lower().startswith(s) for s in ("returns:", "raises:", "yields:", "examples:")):
                    in_args_section = False
                    continue

            if in_args_section:
                # Parse "param_name: description" or "param_name (type): description"
                if ":" in stripped and not stripped.startswith(" "):
                    parts = stripped.split(":", 1)
                    param_part = parts[0].strip()
                    # Handle "param_name (type)" format
                    if "(" in param_part:
                        param_part = param_part.split("(")[0].strip()
                    current_param = param_part
                    param_docs[current_param] = parts[1].strip() if len(parts) > 1 else ""
                elif current_param and stripped:
                    # Continuation of previous param description
                    param_docs[current_param] += " " + stripped

        return param_docs

    def _build_inputs_from_signature(self) -> list:
        """Build Langflow inputs from function signature."""
        inputs = []

        for param_name, param in self._signature.parameters.items():
            # Skip self, cls, *args, **kwargs
            if param_name in ("self", "cls"):
                continue
            if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                continue

            # Get type annotation
            param_type = self._type_hints.get(param_name, str)

            # Get description from docstring
            info = self._param_docs.get(param_name, "")

            # Determine if required (no default value)
            required = param.default is inspect.Parameter.empty

            # Get default value
            default = None if param.default is inspect.Parameter.empty else param.default

            # Create appropriate input type
            input_class = TYPE_TO_INPUT_MAP.get(param_type, MessageTextInput)
            input_types = self._get_input_types_for_param(param_type)

            input_field = input_class(
                name=param_name,
                display_name=param_name.replace("_", " ").title(),
                info=info,
                required=required,
                value=default,
                input_types=input_types,
            )
            inputs.append(input_field)

        return inputs

    def _get_input_types_for_param(self, param_type) -> list[str]:
        """Get the input_types list for a parameter based on its type."""
        type_string = TYPE_TO_TYPE_STRING.get(param_type)
        if type_string:
            return [type_string]

        # Handle typing generics
        if hasattr(param_type, "__origin__"):
            # e.g., List[str], Optional[int]
            pass

        # Default to Text for unknown types
        return ["Text"]

    def _build_outputs_from_signature(self) -> list[Output]:
        """Build Langflow outputs from function return type."""
        return_type = self._type_hints.get("return")

        # Create output with inferred types
        output = Output(
            display_name="Result",
            name="result",
            method="invoke_function",
        )

        if return_type:
            processed_types = post_process_type(return_type)
            type_names = [self._format_type_name(t) for t in processed_types]
            output.add_types(type_names)
        else:
            output.add_types(["Any"])

        return [output]

    def _format_type_name(self, type_obj) -> str:
        """Format a type object to a string name."""
        if isinstance(type_obj, str):
            return type_obj
        if hasattr(type_obj, "__name__"):
            return type_obj.__name__
        return str(type_obj)

    async def invoke_function(self) -> Any:
        """Execute the wrapped function with the input values."""
        # Gather input values
        kwargs = {}
        for param_name in self._signature.parameters:
            if param_name in ("self", "cls"):
                continue
            param = self._signature.parameters[param_name]
            if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                continue

            # Get value from inputs
            if param_name in self._inputs:
                value = self._inputs[param_name].value
                # Handle connected values
                if hasattr(value, "text"):  # Message
                    value = value.text
                kwargs[param_name] = value

        # Call the function
        result = self._wrapped_function(**kwargs)

        # Handle async functions
        if inspect.iscoroutine(result):
            result = await result

        return result
```

### 3.2 Create Factory Function

**Location:** `src/lfx/src/lfx/base/functions/__init__.py`

```python
from lfx.base.functions.function_component import FunctionComponent


def from_function(func, **kwargs):
    """Create a FunctionComponent from a Python function.

    Args:
        func: The Python function to wrap
        **kwargs: Additional arguments passed to FunctionComponent

    Returns:
        FunctionComponent: A component wrapping the function
    """
    return FunctionComponent(func, **kwargs)


__all__ = ["FunctionComponent", "from_function"]
```

### 3.3 Modify Component.set() to Handle Functions

**Location:** `src/lfx/src/lfx/custom/custom_component/component.py`

Modify `_process_connection_or_parameter()` (around line 754):

```python
def _process_connection_or_parameter(self, key, value) -> None:
    # Special handling for Loop components
    if self._is_loop_connection(key, value):
        self._process_loop_connection(key, value)
        return

    input_ = self._get_or_create_input(key)

    # NEW: Handle plain functions (not Component methods)
    if callable(value) and not self._inherits_from_component(value) and not isinstance(value, Component):
        # Check if it's a regular function (not a builtin, class, etc.)
        if inspect.isfunction(value) or inspect.ismethod(value):
            # Wrap in FunctionComponent
            from lfx.base.functions import FunctionComponent
            value = FunctionComponent(value)
            # Find matching output and get the method
            value = self._find_matching_output_method(key, value)

    # Existing logic...
    if isinstance(value, Component):
        value = self._find_matching_output_method(key, value)
    if callable(value) and self._inherits_from_component(value):
        try:
            self._method_is_valid_output(value)
        except ValueError as e:
            msg = f"Method {value.__name__} is not a valid output of {value.__self__.__class__.__name__}"
            raise ValueError(msg) from e
        self._connect_to_component(key, value, input_)
    else:
        self._set_parameter_or_attribute(key, value)
```

### 3.4 Alternative: Decorator Approach

For a cleaner API, we could also provide a decorator:

```python
from lfx.base.functions import component

@component
def add_numbers(a: int, b: int) -> int:
    """Add two numbers together.

    Args:
        a: First number
        b: Second number

    Returns:
        The sum of a and b
    """
    return a + b

# Usage
chat_input = ChatInput()
result = add_numbers.set(a=chat_input.message_response)
graph = Graph(chat_input, result)
```

### 3.5 Update Module Exports

**Location:** `src/lfx/src/lfx/base/__init__.py`

```python
from lfx.base.functions import FunctionComponent, from_function

__all__ = [
    # ... existing exports
    "FunctionComponent",
    "from_function",
]
```

---

## 4. Input Attributes from BaseInputMixin

**Location:** `src/lfx/src/lfx/inputs/input_mixin.py:55-137`

The `BaseInputMixin` class defines all attributes available for inputs. When creating a `FunctionComponent`, we can extract many of these from the function signature and docstring.

### 4.1 Core Attributes (Extractable from Signature)

| Attribute | Type | Default | How to Extract from Function |
|-----------|------|---------|------------------------------|
| `name` | `str` | required | Parameter name |
| `required` | `bool` | `False` | `param.default is inspect.Parameter.empty` |
| `value` | `Any` | `""` | `param.default` if not empty |
| `field_type` | `FieldTypes` | `TEXT` | Map from type annotation |
| `input_types` | `list[str]` | `None` | Map from type annotation for handle connections |
| `is_list` | `bool` | `False` | Check if type is `list[X]` or `Sequence[X]` |
| `display_name` | `str` | `None` | Format param name: `my_param` → `"My Param"` |
| `info` | `str` | `""` | Parse from docstring Args section |

### 4.2 Additional Attributes (Extractable from Annotations/Docstring)

| Attribute | Type | Default | Extraction Strategy |
|-----------|------|---------|---------------------|
| `placeholder` | `str` | `""` | Could parse from docstring (e.g., "e.g., ..." pattern) |
| `advanced` | `bool` | `False` | Custom annotation: `Annotated[str, Advanced()]` |
| `show` | `bool` | `True` | Custom annotation: `Annotated[str, Hidden()]` |
| `range_spec` | `RangeSpec` | `None` | `Annotated[int, Range(min=0, max=100, step=1)]` |
| `options` | `list[str]` | `None` | `Literal["opt1", "opt2", "opt3"]` type |
| `multiline` | `bool` | `False` | Custom annotation: `Annotated[str, Multiline()]` |

### 4.3 FieldTypes Enum (for field_type mapping)

**Location:** `src/lfx/src/lfx/inputs/input_mixin.py:18-39`

```python
class FieldTypes(str, Enum):
    TEXT = "str"
    INTEGER = "int"
    PASSWORD = "str"
    FLOAT = "float"
    BOOLEAN = "bool"
    DICT = "dict"
    NESTED_DICT = "NestedDict"
    FILE = "file"
    CODE = "code"
    OTHER = "other"
    # ... more types
```

### 4.4 Available Input Classes

**Location:** `src/lfx/src/lfx/inputs/inputs.py`

| Input Class | field_type | input_types | Use Case |
|------------|------------|-------------|----------|
| `StrInput` | `TEXT` | - | Plain strings |
| `MessageTextInput` | `TEXT` | `["Message"]` | Text that can receive Message connections |
| `MessageInput` | `TEXT` | `["Message"]` | Receives Message objects directly |
| `IntInput` | `INTEGER` | - | Integer values (includes RangeMixin) |
| `FloatInput` | `FLOAT` | - | Float values (includes RangeMixin) |
| `BoolInput` | `BOOLEAN` | - | Boolean values |
| `DataInput` | `OTHER` | `["Data"]` | Data objects |
| `HandleInput` | `OTHER` | configurable | Generic handle for any type |
| `DropdownInput` | `TEXT` | - | Dropdown with options |
| `MultilineInput` | `TEXT` | `["Message"]` | Multiline text (includes AIMixin) |
| `SecretStrInput` | `PASSWORD` | - | Sensitive strings |
| `FileInput` | `FILE` | - | File uploads |
| `DictInput` | `DICT` | - | Dictionary values |
| `NestedDictInput` | `NESTED_DICT` | - | Nested dictionaries |

### 4.5 Useful Mixins for FunctionComponent

| Mixin | Attributes | Use Case |
|-------|------------|----------|
| `ListableInputMixin` | `is_list`, `list_add_label` | `list[X]` type annotations |
| `RangeMixin` | `range_spec` | Int/float ranges via `Annotated` |
| `DropDownMixin` | `options`, `combobox` | `Literal` types |
| `MultilineMixin` | `multiline=True` | Long text inputs |
| `FileMixin` | `file_path`, `file_types` | File parameters |
| `DatabaseLoadMixin` | `load_from_db` | Credentials/secrets |

### 4.6 Implementation: Mapping Function Signature to Inputs

```python
import inspect
from typing import get_type_hints, get_origin, get_args, Literal, Annotated

def build_input_from_parameter(
    param: inspect.Parameter,
    type_hint: type | None,
    docstring_info: str | None = None
) -> InputTypes:
    """Build a Langflow Input from a function parameter."""

    # 1. Determine if required
    required = param.default is inspect.Parameter.empty

    # 2. Get default value
    default = None if required else param.default

    # 3. Check for list type
    is_list = False
    inner_type = type_hint
    if get_origin(type_hint) in (list, List, Sequence):
        is_list = True
        args = get_args(type_hint)
        inner_type = args[0] if args else str

    # 4. Check for Literal (dropdown options)
    options = None
    if get_origin(inner_type) is Literal:
        options = list(get_args(inner_type))
        inner_type = str

    # 5. Check for Annotated (custom metadata)
    range_spec = None
    advanced = False
    multiline = False
    if get_origin(inner_type) is Annotated:
        args = get_args(inner_type)
        inner_type = args[0]
        for meta in args[1:]:
            if isinstance(meta, RangeSpec):
                range_spec = meta
            elif isinstance(meta, Advanced):
                advanced = True
            elif isinstance(meta, Multiline):
                multiline = True

    # 6. Map type to Input class
    input_class = TYPE_TO_INPUT_CLASS.get(inner_type, MessageTextInput)

    # 7. Build input
    return input_class(
        name=param.name,
        display_name=param.name.replace("_", " ").title(),
        required=required,
        value=default,
        is_list=is_list,
        info=docstring_info or "",
        advanced=advanced,
        options=options,
        range_spec=range_spec,
        # input_types set by input_class default
    )
```

---

## 5. Type Mapping Strategy

### 5.1 Python Type to Langflow Type Mapping

| Python Type | Langflow Input Class | input_types |
|-------------|---------------------|-------------|
| `str` | `StrInput` / `MessageTextInput` | `["Text"]` |
| `int` | `IntInput` | `["int"]` |
| `float` | `FloatInput` | `["float"]` |
| `bool` | `BoolInput` | `["bool"]` |
| `list[str]` | `StrInput(is_list=True)` | `["Text"]` |
| `Message` | `MessageInput` | `["Message"]` |
| `Data` | `DataInput` | `["Data"]` |
| `Any` | `MessageTextInput` | `["Text", "Message", "Data"]` |

### 4.2 Return Type to Output Type Mapping

| Python Return Type | output.types |
|-------------------|--------------|
| `str` | `["Text"]` |
| `int` | `["int"]` |
| `Message` | `["Message"]` |
| `Data` | `["Data"]` |
| `list[str]` | `["Text"]` (with is_list) |
| `None` | `["Any"]` |

---

## 5. Connection Flow

When a function is passed to `set()`:

```
component.set(param=my_function)
          │
          ▼
_process_connection_or_parameter()
          │
          ├─► Detect: callable but not Component method
          │
          ▼
    Create FunctionComponent(my_function)
          │
          ├─► Introspect signature → Create inputs
          ├─► Introspect return type → Create output
          ├─► Parse docstring → Add info to inputs
          │
          ▼
    _find_matching_output_method()
          │
          ├─► Match output.types with input.input_types
          │
          ▼
    _connect_to_component()
          │
          ├─► Add FunctionComponent to self._components
          ├─► Create edge data
          │
          ▼
    Component now connected to FunctionComponent
```

When Graph is built:

```
Graph(start, end)
      │
      ▼
add_component(start)
      │
      ├─► to_frontend_node() → serialize
      ├─► Create Vertex
      ├─► Add edges from component._edges
      │
      ├─► get_components() → [FunctionComponent, ...]
      │         │
      │         ▼
      │   add_component(FunctionComponent)  ◄── Recursive!
      │         │
      │         ├─► to_frontend_node()
      │         ├─► Create Vertex
      │         └─► Add edges
      │
      ▼
add_component(end)
      ...
```

---

## 6. Example Usage

### 6.1 Basic Function as Component

```python
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph

def process_message(text: str) -> str:
    """Process the input message.

    Args:
        text: The input text to process

    Returns:
        Processed text in uppercase
    """
    return text.upper()

# Create components
chat_input = ChatInput(_id="input")
chat_output = ChatOutput(_id="output")

# Connect function - automatically wrapped in FunctionComponent
chat_output.set(input_value=process_message)
process_message.set(text=chat_input.message_response)  # Hmm, this won't work...

# Better API with explicit wrapping
from lfx.base.functions import from_function

processor = from_function(process_message, _id="processor")
processor.set(text=chat_input.message_response)
chat_output.set(input_value=processor.result)

graph = Graph(chat_input, chat_output)
```

### 6.2 Function Chaining

```python
from lfx.base.functions import from_function

def step1(input_text: str) -> str:
    return input_text.strip()

def step2(text: str) -> str:
    return text.lower()

def step3(text: str) -> str:
    return f"Processed: {text}"

# Create function components
s1 = from_function(step1, _id="step1")
s2 = from_function(step2, _id="step2")
s3 = from_function(step3, _id="step3")

# Chain them
s1.set(input_text=chat_input.message_response)
s2.set(text=s1.result)
s3.set(text=s2.result)
chat_output.set(input_value=s3.result)

graph = Graph(chat_input, chat_output)
```

### 6.3 Async Functions

```python
async def fetch_data(url: str) -> str:
    """Fetch data from URL."""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()

fetcher = from_function(fetch_data, _id="fetcher")
fetcher.set(url=url_input.text_response)
```

---

## 7. Key Files to Modify

| File | Changes |
|------|---------|
| `src/lfx/src/lfx/base/functions/__init__.py` | **NEW** - Create module with exports |
| `src/lfx/src/lfx/base/functions/function_component.py` | **NEW** - FunctionComponent class |
| `src/lfx/src/lfx/custom/custom_component/component.py` | Modify `_process_connection_or_parameter()` |
| `src/lfx/src/lfx/base/__init__.py` | Add exports for new module |

---

## 8. Comprehensive Test Plan

### 8.1 Unit Tests: FunctionComponent Creation

**File:** `src/lfx/tests/unit/base/functions/test_function_component.py`

```python
import pytest
from typing import Literal, Annotated, Optional
from lfx.base.functions import FunctionComponent, from_function
from lfx.field_typing.range_spec import RangeSpec


class TestFunctionComponentCreation:
    """Tests for FunctionComponent instantiation and signature introspection."""

    def test_simple_function_single_param(self):
        """Function with one typed parameter creates one input."""
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        fc = FunctionComponent(greet)

        assert len(fc.inputs) == 1
        assert fc.inputs[0].name == "name"
        assert fc.inputs[0].display_name == "Name"
        assert fc.inputs[0].required is True  # No default
        assert fc.inputs[0].value is None
        assert "Text" in fc.inputs[0].input_types or "Message" in fc.inputs[0].input_types

    def test_function_multiple_params(self):
        """Function with multiple parameters creates multiple inputs."""
        def calculate(a: int, b: int, c: float = 1.0) -> float:
            return (a + b) * c

        fc = FunctionComponent(calculate)

        assert len(fc.inputs) == 3
        assert fc.inputs[0].name == "a"
        assert fc.inputs[0].required is True
        assert fc.inputs[1].name == "b"
        assert fc.inputs[1].required is True
        assert fc.inputs[2].name == "c"
        assert fc.inputs[2].required is False
        assert fc.inputs[2].value == 1.0

    def test_function_with_default_values(self):
        """Default values are captured in input.value."""
        def configure(
            name: str = "default",
            count: int = 10,
            enabled: bool = True
        ) -> str:
            return f"{name}: {count}, {enabled}"

        fc = FunctionComponent(configure)

        assert fc.inputs[0].value == "default"
        assert fc.inputs[1].value == 10
        assert fc.inputs[2].value is True
        assert all(inp.required is False for inp in fc.inputs)

    def test_function_without_type_hints(self):
        """Untyped parameters default to str/Text."""
        def process(data):
            return str(data)

        fc = FunctionComponent(process)

        assert len(fc.inputs) == 1
        assert fc.inputs[0].name == "data"
        # Should default to text-compatible type

    def test_function_with_list_type(self):
        """list[X] type creates is_list=True input."""
        def process_items(items: list[str]) -> str:
            return ", ".join(items)

        fc = FunctionComponent(process_items)

        assert fc.inputs[0].is_list is True

    def test_function_with_literal_type(self):
        """Literal type creates dropdown with options."""
        def set_mode(mode: Literal["fast", "slow", "balanced"]) -> str:
            return mode

        fc = FunctionComponent(set_mode)

        assert fc.inputs[0].options == ["fast", "slow", "balanced"]

    def test_function_with_optional_type(self):
        """Optional[X] is handled correctly."""
        def maybe_process(data: Optional[str] = None) -> str:
            return data or "empty"

        fc = FunctionComponent(maybe_process)

        assert fc.inputs[0].required is False
        assert fc.inputs[0].value is None

    def test_skips_self_and_cls(self):
        """self and cls parameters are skipped."""
        class MyClass:
            def method(self, data: str) -> str:
                return data

        fc = FunctionComponent(MyClass().method)
        # Should only have 'data', not 'self'
        assert len(fc.inputs) == 1
        assert fc.inputs[0].name == "data"

    def test_skips_args_kwargs(self):
        """*args and **kwargs are skipped."""
        def flexible(required: str, *args, **kwargs) -> str:
            return required

        fc = FunctionComponent(flexible)

        assert len(fc.inputs) == 1
        assert fc.inputs[0].name == "required"


class TestFunctionComponentDocstring:
    """Tests for docstring parsing."""

    def test_google_style_docstring(self):
        """Google-style docstrings are parsed for parameter info."""
        def process(data: str, count: int) -> str:
            """Process the data multiple times.

            Args:
                data: The input data to process
                count: Number of times to process

            Returns:
                Processed result
            """
            return data * count

        fc = FunctionComponent(process)

        assert fc.inputs[0].info == "The input data to process"
        assert fc.inputs[1].info == "Number of times to process"
        assert fc.description == "Process the data multiple times."

    def test_numpy_style_docstring(self):
        """Numpy-style docstrings are parsed."""
        def analyze(values: list[float]) -> float:
            """Analyze numerical values.

            Parameters
            ----------
            values : list[float]
                The values to analyze

            Returns
            -------
            float
                The analysis result
            """
            return sum(values) / len(values)

        fc = FunctionComponent(analyze)
        # Should extract parameter description

    def test_no_docstring(self):
        """Functions without docstrings have empty info."""
        def simple(x: int) -> int:
            return x * 2

        fc = FunctionComponent(simple)

        assert fc.inputs[0].info == ""
        assert fc.description is None or fc.description == ""


class TestFunctionComponentOutput:
    """Tests for output generation from return types."""

    def test_simple_return_type(self):
        """Simple return types create appropriate output."""
        def get_text() -> str:
            return "hello"

        fc = FunctionComponent(get_text)

        assert len(fc.outputs) == 1
        assert fc.outputs[0].name == "result"
        assert fc.outputs[0].method == "invoke_function"
        assert "str" in fc.outputs[0].types or "Text" in fc.outputs[0].types

    def test_no_return_type(self):
        """Functions without return type get Any output."""
        def mystery():
            return 42

        fc = FunctionComponent(mystery)

        assert "Any" in fc.outputs[0].types

    def test_none_return_type(self):
        """Functions returning None are handled."""
        def side_effect(data: str) -> None:
            print(data)

        fc = FunctionComponent(side_effect)
        # Should still have an output, possibly with None/Any type

    def test_union_return_type(self):
        """Union return types create multiple output types."""
        from typing import Union

        def maybe_int(x: str) -> Union[int, None]:
            try:
                return int(x)
            except ValueError:
                return None

        fc = FunctionComponent(maybe_int)
        # Should have both int and None in types


class TestFunctionComponentNaming:
    """Tests for component naming and display."""

    def test_display_name_from_function_name(self):
        """Display name is derived from function name."""
        def process_user_input(data: str) -> str:
            return data

        fc = FunctionComponent(process_user_input)

        assert fc.display_name == "Process User Input"

    def test_custom_id(self):
        """Custom _id is respected."""
        def simple(x: str) -> str:
            return x

        fc = FunctionComponent(simple, _id="my_custom_id")

        assert fc._id == "my_custom_id"

    def test_auto_generated_id(self):
        """ID is auto-generated if not provided."""
        def simple(x: str) -> str:
            return x

        fc = FunctionComponent(simple)

        assert fc._id is not None
        assert len(fc._id) > 0


### 8.2 Unit Tests: Component Connection

```python
class TestFunctionComponentConnection:
    """Tests for connecting FunctionComponents to other components."""

    def test_connect_to_chat_input(self):
        """FunctionComponent can receive from ChatInput."""
        from lfx.components.input_output import ChatInput

        def process(text: str) -> str:
            return text.upper()

        chat_input = ChatInput(_id="input")
        fc = from_function(process, _id="processor")
        fc.set(text=chat_input.message_response)

        assert len(fc._components) == 1
        assert fc._components[0] == chat_input
        assert len(fc._edges) == 1

    def test_connect_to_another_function(self):
        """FunctionComponents can chain together."""
        def step1(x: str) -> str:
            return x.strip()

        def step2(y: str) -> str:
            return y.lower()

        fc1 = from_function(step1, _id="step1")
        fc2 = from_function(step2, _id="step2")

        fc1.set(x="  hello  ")
        fc2.set(y=fc1.result)

        assert len(fc2._components) == 1
        assert len(fc2._edges) == 1

    def test_type_mismatch_error(self):
        """Mismatched types raise clear error."""
        from lfx.components.input_output import ChatInput

        def needs_int(x: int) -> int:
            return x * 2

        chat_input = ChatInput(_id="input")
        fc = from_function(needs_int, _id="processor")

        # ChatInput outputs Message, but function needs int
        # Should raise ValueError with helpful message
        with pytest.raises(ValueError, match="no matching output"):
            fc.set(x=chat_input.message_response)

    def test_multiple_inputs_partial_connection(self):
        """Can connect some inputs and set others as values."""
        from lfx.components.input_output import ChatInput

        def combine(prefix: str, text: str, suffix: str = "!") -> str:
            return f"{prefix}{text}{suffix}"

        chat_input = ChatInput(_id="input")
        fc = from_function(combine, _id="combiner")

        fc.set(
            prefix="Hello, ",
            text=chat_input.message_response,
            suffix="!!!"
        )

        assert len(fc._edges) == 1  # Only text is connected
        assert fc._parameters.get("prefix") == "Hello, "
        assert fc._parameters.get("suffix") == "!!!"
```

### 8.3 Integration Tests: Graph Execution

```python
class TestFunctionComponentExecution:
    """Tests for executing graphs with FunctionComponents."""

    @pytest.mark.asyncio
    async def test_simple_execution(self):
        """FunctionComponent executes and produces output."""
        def double(x: int) -> int:
            return x * 2

        fc = from_function(double, _id="doubler")
        fc.set(x=5)

        graph = Graph(fc, fc)
        results = [r async for r in graph.async_start()]

        # Find result
        result_vertex = next(
            r for r in results
            if hasattr(r, "vertex") and r.vertex.id == "doubler"
        )
        assert result_vertex.vertex.custom_component._outputs_map["result"].value == 10

    @pytest.mark.asyncio
    async def test_chained_execution(self):
        """Multiple FunctionComponents execute in order."""
        def add_one(x: int) -> int:
            return x + 1

        def multiply_two(x: int) -> int:
            return x * 2

        fc1 = from_function(add_one, _id="add")
        fc2 = from_function(multiply_two, _id="mult")

        fc1.set(x=5)
        fc2.set(x=fc1.result)

        graph = Graph(fc1, fc2)
        results = [r async for r in graph.async_start()]

        # (5 + 1) * 2 = 12
        # Verify final result

    @pytest.mark.asyncio
    async def test_async_function_execution(self):
        """Async functions are awaited properly."""
        async def async_process(data: str) -> str:
            import asyncio
            await asyncio.sleep(0.01)
            return data.upper()

        fc = from_function(async_process, _id="async_proc")
        fc.set(data="hello")

        graph = Graph(fc, fc)
        results = [r async for r in graph.async_start()]

        # Should complete without error

    @pytest.mark.asyncio
    async def test_function_with_exception(self):
        """Exceptions in functions are handled gracefully."""
        def risky(x: int) -> int:
            if x < 0:
                raise ValueError("x must be non-negative")
            return x

        fc = from_function(risky, _id="risky")
        fc.set(x=-1)

        graph = Graph(fc, fc)

        with pytest.raises(ValueError, match="x must be non-negative"):
            results = [r async for r in graph.async_start()]

    @pytest.mark.asyncio
    async def test_with_chat_input_output(self):
        """Full flow with ChatInput -> Function -> ChatOutput."""
        from lfx.components.input_output import ChatInput, ChatOutput

        def process(text: str) -> str:
            return f"Processed: {text}"

        chat_input = ChatInput(_id="input")
        fc = from_function(process, _id="processor")
        chat_output = ChatOutput(_id="output")

        fc.set(text=chat_input.message_response)
        chat_output.set(input_value=fc.result)

        graph = Graph(chat_input, chat_output)

        # Execute with input
        results = [r async for r in graph.async_start(
            inputs=[{"input_value": "Hello"}]
        )]

        assert any("Processed: Hello" in str(r) for r in results)
```

### 8.4 Serialization Tests

```python
class TestFunctionComponentSerialization:
    """Tests for graph.dump() with FunctionComponents."""

    def test_to_frontend_node(self):
        """FunctionComponent serializes to valid frontend node."""
        def simple(x: str) -> str:
            return x

        fc = from_function(simple, _id="simple")
        node = fc.to_frontend_node()

        assert "data" in node
        assert "id" in node["data"]
        assert node["data"]["id"] == "simple"
        assert "node" in node["data"]
        assert "template" in node["data"]["node"]

    def test_graph_dump_includes_functions(self):
        """Graph.dump() includes FunctionComponent data."""
        from lfx.components.input_output import ChatInput, ChatOutput

        def process(text: str) -> str:
            return text

        chat_input = ChatInput(_id="input")
        fc = from_function(process, _id="processor")
        chat_output = ChatOutput(_id="output")

        fc.set(text=chat_input.message_response)
        chat_output.set(input_value=fc.result)

        graph = Graph(chat_input, chat_output)
        dump = graph.dump()

        node_ids = [n["id"] for n in dump["data"]["nodes"]]
        assert "processor" in node_ids

    def test_edges_serialized_correctly(self):
        """Edges between components are correctly serialized."""
        from lfx.components.input_output import ChatInput

        def process(text: str) -> str:
            return text

        chat_input = ChatInput(_id="input")
        fc = from_function(process, _id="processor")
        fc.set(text=chat_input.message_response)

        graph = Graph(chat_input, fc)
        dump = graph.dump()

        edges = dump["data"]["edges"]
        assert len(edges) >= 1

        # Find edge from input to processor
        edge = next(e for e in edges if e["target"] == "processor")
        assert edge["source"] == "input"
```

### 8.5 Edge Case Tests

```python
class TestFunctionComponentEdgeCases:
    """Tests for edge cases and error handling."""

    def test_lambda_function(self):
        """Lambda functions can be wrapped (limited introspection)."""
        square = lambda x: x * 2

        fc = FunctionComponent(square)

        # Lambda has limited introspection
        assert len(fc.inputs) >= 1

    def test_builtin_function_raises(self):
        """Built-in functions raise appropriate error."""
        with pytest.raises((TypeError, ValueError)):
            fc = FunctionComponent(len)

    def test_class_as_function_raises(self):
        """Classes are not valid functions."""
        class MyClass:
            pass

        with pytest.raises((TypeError, ValueError)):
            fc = FunctionComponent(MyClass)

    def test_generator_function(self):
        """Generator functions are handled (future enhancement)."""
        def gen(n: int):
            for i in range(n):
                yield i

        # Should either work or raise clear error
        fc = FunctionComponent(gen)

    def test_function_with_complex_defaults(self):
        """Functions with mutable defaults are handled."""
        def with_list(items: list[str] = None) -> str:
            items = items or []
            return ",".join(items)

        fc = FunctionComponent(with_list)
        assert fc.inputs[0].value is None  # Not []

    def test_deeply_nested_types(self):
        """Complex nested types are handled gracefully."""
        from typing import Dict, List, Optional

        def complex_fn(
            data: Optional[Dict[str, List[int]]] = None
        ) -> Dict[str, int]:
            return {}

        fc = FunctionComponent(complex_fn)
        # Should not crash, may default to generic types
```

---

## 9. Developer Experience (DX) Considerations

### 9.1 API Design Decisions

**Issue: The implicit wrapping API doesn't work well**

The document shows this pattern that WON'T work:
```python
chat_output.set(input_value=process_message)
process_message.set(text=chat_input.message_response)  # ❌ Won't work!
```

This fails because `process_message` is still a plain function - it hasn't been wrapped yet.

**Recommended API Patterns:**

```python
# Pattern 1: Explicit wrapping (RECOMMENDED)
from lfx.base.functions import from_function

processor = from_function(process_message, _id="processor")
processor.set(text=chat_input.message_response)
chat_output.set(input_value=processor.result)

# Pattern 2: Decorator at definition time
from lfx.base.functions import component

@component
def process_message(text: str) -> str:
    return text.upper()

# Now process_message IS a FunctionComponent
process_message.set(text=chat_input.message_response)
chat_output.set(input_value=process_message.result)

# Pattern 3: Inline lambda-like (concise but less readable)
fc = from_function(lambda x: x.upper(), _id="upper")
```

### 9.2 Type Coercion Strategy

**Problem:** A function expects `str` but receives `Message`.

**Options:**

1. **Automatic Coercion** (Recommended for DX):
   ```python
   # In invoke_function():
   value = self._inputs[param_name].value
   if isinstance(value, Message) and expected_type is str:
       value = value.text
   ```

2. **Explicit Coercion Required**:
   - User must handle conversion in function
   - Clearer but more verbose

3. **Hybrid Approach**:
   - Auto-coerce for common cases (Message→str, Data→dict)
   - Require explicit for complex cases

**Recommendation:** Implement automatic coercion for:
- `Message` → `str` (via `.text`)
- `Data` → `dict` (via `.data`)
- `str` → `Message` (via `Message(text=x)`)

### 9.3 Error Messages

**Bad Error Message:**
```
ValueError: No matching output found
```

**Good Error Message:**
```
ValueError: Cannot connect 'ChatInput.message_response' (outputs: ['Message'])
to 'processor.x' (accepts: ['int']).

Consider:
  - Changing the parameter type to 'str' or 'Message'
  - Adding a type conversion function between components
  - Using fc.set(x=chat_input.message_response.text) for explicit conversion
```

### 9.4 Accessing Output Methods

**How `fc.result` works:**

The `FunctionComponent` needs to expose output methods as attributes:

```python
class FunctionComponent(Component):
    @property
    def result(self):
        """Access the result output method for chaining."""
        return self.invoke_function
```

This allows the chaining pattern:
```python
fc2.set(input=fc1.result)  # fc1.result returns the bound method
```

### 9.5 Debugging Support

**Tracing:**
```python
# In invoke_function():
logger.debug(f"FunctionComponent '{self._id}' invoking {self._func_name}")
logger.debug(f"  Inputs: {kwargs}")
result = self._wrapped_function(**kwargs)
logger.debug(f"  Output: {result}")
```

**Vertex Display:**
```python
# Custom display in UI/logs
@property
def trace_name(self) -> str:
    return f"Function: {self._func_name} ({self._id})"
```

### 9.6 IDE Support

For good autocomplete:

```python
from lfx.base.functions import from_function

# Type hint the return value
def from_function(
    func: Callable[..., T],
    _id: str | None = None,
    **kwargs
) -> FunctionComponent:
    """Create a FunctionComponent from a Python function.

    Example:
        >>> def greet(name: str) -> str:
        ...     return f"Hello, {name}!"
        >>> fc = from_function(greet, _id="greeter")
        >>> fc.set(name="World")
        >>> fc.result  # Returns the invoke_function method
    """
    return FunctionComponent(func, _id=_id, **kwargs)
```

---

## 10. Identified Gaps & Open Issues

### 10.1 Critical Issues to Resolve

| Issue | Description | Proposed Solution |
|-------|-------------|-------------------|
| **Output accessor** | How does `fc.result` work? | Property that returns `self.invoke_function` |
| **Type coercion** | Message→str automatic? | Yes, auto-coerce common types |
| **Serialization** | Can graph with functions be saved/loaded? | Need `to_frontend_node()` impl |
| **Code persistence** | Function code not serialized | Store source via `inspect.getsource()` |
| **Rehydration** | Can't reload FunctionComponent from dump | Need special handling or limitation |

### 10.2 Context & Dependencies

**Problem:** How do functions access Langflow services?

```python
def fetch_from_storage(path: str) -> str:
    # How to access storage service?
    pass
```

**Options:**

1. **Inject via special parameters:**
   ```python
   from lfx.base.functions import Context

   def fetch_from_storage(path: str, ctx: Context) -> str:
       return ctx.storage.read(path)
   ```

2. **Global/thread-local context:**
   ```python
   from lfx.base.functions import get_context

   def fetch_from_storage(path: str) -> str:
       ctx = get_context()
       return ctx.storage.read(path)
   ```

3. **Closure capture (current pattern):**
   ```python
   storage = get_storage_service()

   def fetch_from_storage(path: str) -> str:
       return storage.read(path)  # Captured
   ```

### 10.3 Multiple Outputs

**Future Enhancement:** Support tuple/dict returns as multiple outputs.

```python
def split_data(text: str) -> tuple[str, int]:
    """Split and analyze.

    Returns:
        (processed_text, word_count)
    """
    words = text.split()
    return " ".join(words), len(words)

# Could generate two outputs: 'processed_text' and 'word_count'
fc = from_function(split_data, _id="splitter")
other.set(text=fc.processed_text, count=fc.word_count)
```

### 10.4 Stateful Functions

**Question:** Should FunctionComponents support state?

```python
def counter(increment: int = 1) -> int:
    # Where does state live?
    counter.count = getattr(counter, 'count', 0) + increment
    return counter.count
```

**Recommendation:** Keep functions stateless. State should be managed via:
- Graph context (`graph.context`)
- Dedicated state components
- External services

---

## 11. Edge Cases to Handle

1. **Functions with `*args` / `**kwargs`** - Skip these parameters
2. **Functions with no type hints** - Default to `str` / `Text`
3. **Functions with complex types** (`Union`, `Optional`, generics) - Parse appropriately
4. **Async functions** - Detect and handle with `await`
5. **Functions that return `None`** - Create output with type `["Any"]`
6. **Class methods** - May need special handling for `self`
7. **Lambda functions** - Limited introspection, may need fallbacks
8. **Built-in functions** - Cannot be wrapped (no signature)

---

## 10. Future Enhancements

1. **@component Decorator**: Sugar for creating FunctionComponents
2. **Multiple Outputs**: Support functions that return tuples/dicts as multiple outputs
3. **Validation**: Add input validation based on type hints
4. **Caching**: Support for caching function results
5. **Error Handling**: Proper error propagation from function execution
6. **UI Integration**: Custom icons/styling for FunctionComponents
7. **Streaming**: Support for generator functions that yield values

---

## 11. Open Questions

1. **Type Coercion**: Should we automatically convert `Message.text` when a function expects `str`?
2. **Naming**: Should function components have auto-generated IDs or require explicit IDs?
3. **Display**: How should function components appear in the UI? Custom icon/color?
4. **Error Messages**: What happens when a function raises an exception?
5. **State**: Should function components support stateful operations?

---

## 12. Decorator API Design

### 12.1 Overview

The `@component` decorator transforms a plain Python function into a `FunctionComponent` at decoration time. This provides the cleanest developer experience for defining function-based components.

### 12.2 Basic Decorator Usage

```python
from lfx.base.functions import component

@component
def process_text(text: str) -> str:
    """Process input text.

    Args:
        text: The input text to process

    Returns:
        Processed text in uppercase
    """
    return text.upper()

# process_text is now a FunctionComponent instance
process_text.set(text=chat_input.message_response)
chat_output.set(input_value=process_text.result)
```

### 12.3 Decorator Parameters

The decorator should support the following parameters for maximum flexibility:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `display_name` | `str \| None` | `None` | Override auto-generated display name |
| `description` | `str \| None` | `None` | Override description from docstring |
| `icon` | `str \| None` | `None` | Icon name for UI display |
| `category` | `str` | `"Functions"` | Category for component browser |
| `output_name` | `str` | `"result"` | Name of the output |
| `output_display_name` | `str` | `"Result"` | Display name of the output |
| `output_types` | `list[str] \| None` | `None` | Override inferred output types |
| `trace_type` | `str` | `"function"` | Trace type for telemetry |
| `_id` | `str \| None` | `None` | Explicit component ID |

### 12.4 Decorator Implementation

```python
from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar, overload

P = ParamSpec("P")
T = TypeVar("T")


@overload
def component(func: Callable[P, T]) -> FunctionComponent: ...

@overload
def component(
    *,
    display_name: str | None = None,
    description: str | None = None,
    icon: str | None = None,
    category: str = "Functions",
    output_name: str = "result",
    output_display_name: str = "Result",
    output_types: list[str] | None = None,
    trace_type: str = "function",
    _id: str | None = None,
) -> Callable[[Callable[P, T]], FunctionComponent]: ...


def component(
    func: Callable[P, T] | None = None,
    *,
    display_name: str | None = None,
    description: str | None = None,
    icon: str | None = None,
    category: str = "Functions",
    output_name: str = "result",
    output_display_name: str = "Result",
    output_types: list[str] | None = None,
    trace_type: str = "function",
    _id: str | None = None,
) -> FunctionComponent | Callable[[Callable[P, T]], FunctionComponent]:
    """Decorator to transform a Python function into a FunctionComponent.

    Can be used with or without arguments:

        @component
        def my_func(x: str) -> str:
            return x.upper()

        @component(display_name="My Custom Name")
        def my_func(x: str) -> str:
            return x.upper()

    Args:
        func: The function to wrap (when used without parentheses)
        display_name: Override the auto-generated display name
        description: Override the docstring description
        icon: Icon name for UI display
        category: Category for component browser
        output_name: Name of the output field
        output_display_name: Display name of the output field
        output_types: Override inferred output types
        trace_type: Trace type for telemetry
        _id: Explicit component ID

    Returns:
        FunctionComponent or decorator function
    """
    def decorator(fn: Callable[P, T]) -> FunctionComponent:
        # Capture source code at decoration time
        try:
            source_code = inspect.getsource(fn)
        except (OSError, TypeError):
            # Fallback for dynamically defined functions
            source_code = None

        # Create the FunctionComponent
        fc = FunctionComponent(
            func=fn,
            _id=_id,
            display_name=display_name,
            description=description,
            icon=icon,
            category=category,
            output_name=output_name,
            output_display_name=output_display_name,
            output_types=output_types,
            trace_type=trace_type,
            _source_code=source_code,  # Store for persistence
        )

        # Preserve function metadata
        functools.update_wrapper(fc, fn)

        return fc

    # Handle both @component and @component(...) syntax
    if func is not None:
        return decorator(func)
    return decorator
```

### 12.5 Input Parameter Customization via Annotated

For fine-grained control over input fields, use `typing.Annotated`:

```python
from typing import Annotated, Literal
from lfx.base.functions import component, InputConfig
from lfx.field_typing.range_spec import RangeSpec

@component
def configure(
    # Basic string with placeholder
    name: Annotated[str, InputConfig(placeholder="Enter name")] = "",

    # Integer with range slider
    count: Annotated[int, RangeSpec(min=1, max=100, step=1)] = 10,

    # Dropdown from Literal
    mode: Literal["fast", "slow", "balanced"] = "balanced",

    # Advanced parameter (hidden by default)
    debug: Annotated[bool, InputConfig(advanced=True)] = False,

    # Multiline text
    prompt: Annotated[str, InputConfig(multiline=True)] = "",

    # Secret input
    api_key: Annotated[str, InputConfig(password=True)] = "",
) -> str:
    """Configure the system."""
    return f"{name}: {mode}"
```

### 12.6 InputConfig Class

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass
class InputConfig:
    """Configuration for a function parameter input field.

    Use with typing.Annotated to customize input behavior.
    """
    display_name: str | None = None
    info: str | None = None
    placeholder: str | None = None
    advanced: bool = False
    multiline: bool = False
    password: bool = False
    show: bool = True
    required: bool | None = None  # None = infer from default
    input_types: list[str] | None = None
    # For dropdown
    options: list[str] | None = None
    combobox: bool = False
```

### 12.7 Examples

**Example 1: Simple decorated function**
```python
@component
def greet(name: str = "World") -> str:
    """Generate a greeting message.

    Args:
        name: The name to greet
    """
    return f"Hello, {name}!"
```

**Example 2: With customization**
```python
@component(
    display_name="Text Processor",
    icon="TextIcon",
    category="Text Processing",
)
def process_text(
    text: str,
    uppercase: bool = False,
    repeat: Annotated[int, RangeSpec(min=1, max=10)] = 1,
) -> str:
    """Process and transform text.

    Args:
        text: Input text to process
        uppercase: Convert to uppercase
        repeat: Number of times to repeat
    """
    result = text.upper() if uppercase else text
    return result * repeat
```

**Example 3: Async function**
```python
@component(output_types=["Data"])
async def fetch_data(url: str) -> Data:
    """Fetch data from a URL.

    Args:
        url: The URL to fetch
    """
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            content = await response.text()
            return Data(data={"url": url, "content": content})
```

---

## 13. Persistence & Serialization

### 13.1 Current Flow for Components

The existing persistence flow works as follows:

1. **Serialization (`to_frontend_node`):**
   - Component's `to_frontend_node()` method creates a frontend node
   - `set_class_code()` uses `inspect.getsource(module)` to get source code
   - Source code is stored in a "code" field in the template

   **Location:** `src/lfx/src/lfx/custom/custom_component/component.py:998-1027`
   ```python
   def to_frontend_node(self):
       # ... create frontend_node ...
       if not self._code:
           self.set_class_code()
       code_field = Input(
           dynamic=True,
           required=True,
           value=self._code,  # Source code stored here
           name="code",
           field_type="code",
           # ...
       )
       frontend_node.template.add_field(code_field)
   ```

2. **Deserialization (`instantiate_class`):**
   - `instantiate_class()` extracts "code" from vertex params
   - Calls `eval_custom_component_code(code)` to evaluate
   - `extract_class_name()` finds the Component subclass
   - `create_class()` compiles and returns the class

   **Location:** `src/lfx/src/lfx/interface/initialize/loading.py:28-54`
   ```python
   async def instantiate_class(...):
       custom_params = get_params(vertex.params)
       code = custom_params.pop("code")
       class_object = eval_custom_component_code(code)
       custom_component = class_object(...)
   ```

### 13.2 FunctionComponent Persistence Strategy

For `FunctionComponent`, we need to:

1. **At Creation Time:** Capture the function source via `inspect.getsource(func)`
2. **At Serialization:** Store the function source in the "code" field
3. **At Deserialization:** Detect function-based code and reconstruct

#### 13.2.1 Source Code Capture

```python
class FunctionComponent(Component):
    def __init__(
        self,
        func: Callable,
        _source_code: str | None = None,
        **kwargs
    ):
        self._wrapped_function = func

        # Capture source code
        if _source_code:
            self._function_source = _source_code
        else:
            try:
                self._function_source = inspect.getsource(func)
            except (OSError, TypeError):
                # Fallback: store a stub that will fail on reload
                self._function_source = self._generate_stub_code()

        # ... rest of init ...

    def _generate_stub_code(self) -> str:
        """Generate stub code for functions without source."""
        return f'''
# WARNING: Original function source could not be captured.
# This component cannot be reloaded from JSON.
def {self._func_name}(*args, **kwargs):
    raise RuntimeError(
        "This FunctionComponent was created from a dynamically defined "
        "function and cannot be reloaded. Define the function in a module "
        "or use the @component decorator."
    )
'''
```

#### 13.2.2 Modified set_class_code for Functions

```python
def set_class_code(self) -> None:
    if self._code:
        return

    # For FunctionComponent, use function source + wrapper class
    if hasattr(self, '_function_source'):
        # Generate a complete module that includes the function
        # and wraps it in a FunctionComponent
        self._code = self._generate_persistable_code()
        return

    # Existing logic for regular components...
    try:
        module = inspect.getmodule(self.__class__)
        if module is None:
            msg = "Could not find module for class"
            raise ValueError(msg)
        class_code = inspect.getsource(module)
        self._code = class_code
    except (OSError, TypeError) as e:
        msg = f"Could not find source code for {self.__class__.__name__}"
        raise ValueError(msg) from e

def _generate_persistable_code(self) -> str:
    """Generate code that can be persisted and reloaded."""
    return f'''
from lfx.base.functions import FunctionComponent

{self._function_source}

# Metadata for reconstruction
_FUNCTION_NAME = "{self._func_name}"
_COMPONENT_CONFIG = {{
    "display_name": {repr(self.display_name)},
    "description": {repr(self.description)},
    "_id": {repr(self._id)},
}}
'''
```

### 13.3 Modified Evaluation Functions

#### 13.3.1 Updated `eval_custom_component_code`

**Location:** `src/lfx/src/lfx/custom/eval.py`

```python
from lfx.custom import validate

def eval_custom_component_code(code: str) -> type["CustomComponent"]:
    """Evaluate custom component code.

    Handles both class-based components and function-based components.
    """
    # Try to detect if this is a FunctionComponent
    if _is_function_component_code(code):
        return _eval_function_component_code(code)

    # Existing class-based logic
    class_name = validate.extract_class_name(code)
    return validate.create_class(code, class_name)


def _is_function_component_code(code: str) -> bool:
    """Check if code represents a FunctionComponent."""
    return "_FUNCTION_NAME" in code and "FunctionComponent" in code


def _eval_function_component_code(code: str) -> type["FunctionComponent"]:
    """Evaluate function component code and return the class."""
    from lfx.base.functions import FunctionComponent

    # Execute the code to get the function and config
    namespace = {}
    exec(code, namespace)

    func_name = namespace.get("_FUNCTION_NAME")
    config = namespace.get("_COMPONENT_CONFIG", {})
    func = namespace.get(func_name)

    if func is None:
        msg = f"Function '{func_name}' not found in code"
        raise ValueError(msg)

    # Create a factory that returns a configured FunctionComponent
    def create_component(**kwargs):
        merged = {**config, **kwargs}
        return FunctionComponent(func=func, **merged)

    # Return something that acts like a class
    class FunctionComponentFactory:
        def __init__(self, **kwargs):
            self._instance = create_component(**kwargs)

        def __getattr__(self, name):
            return getattr(self._instance, name)

    return FunctionComponentFactory
```

#### 13.3.2 Updated `extract_class_name`

**Location:** `src/lfx/src/lfx/custom/validate.py`

Add support for detecting function-based components:

```python
def extract_class_name(code: str) -> str:
    """Extract the name of the first Component subclass found in the code.

    Also handles FunctionComponent patterns.
    """
    try:
        module = ast.parse(code)

        # First, check for FunctionComponent pattern
        for node in module.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "_FUNCTION_NAME":
                        # This is a FunctionComponent - return the function name
                        if isinstance(node.value, ast.Constant):
                            return f"FunctionComponent:{node.value.value}"

        # Fall back to class-based detection
        for node in module.body:
            if not isinstance(node, ast.ClassDef):
                continue
            for base in node.bases:
                if isinstance(base, ast.Name) and any(
                    pattern in base.id for pattern in ["Component", "LC"]
                ):
                    return node.name

        msg = f"No Component subclass found in code. Code snippet: {code[:100]}"
        raise TypeError(msg)
    except SyntaxError as e:
        msg = f"Invalid Python code: {e!s}"
        raise ValueError(msg) from e
```

### 13.4 Alternative: Hybrid Approach

Instead of generating wrapper code, store function metadata separately:

```python
# In to_frontend_node(), add function-specific fields:

def to_frontend_node(self):
    frontend_node = super().to_frontend_node()

    if hasattr(self, '_function_source'):
        # Add function-specific metadata
        frontend_node.template.add_field(Input(
            name="_function_source",
            value=self._function_source,
            field_type="code",
            advanced=True,
            show=False,
        ))
        frontend_node.template.add_field(Input(
            name="_function_name",
            value=self._func_name,
            field_type="str",
            advanced=True,
            show=False,
        ))
        frontend_node.template.add_field(Input(
            name="_is_function_component",
            value=True,
            field_type="bool",
            advanced=True,
            show=False,
        ))

    return frontend_node
```

Then in `instantiate_class`:

```python
async def instantiate_class(...):
    custom_params = get_params(vertex.params)

    # Check if this is a FunctionComponent
    if custom_params.get("_is_function_component"):
        func_source = custom_params.pop("_function_source")
        func_name = custom_params.pop("_function_name")
        custom_params.pop("_is_function_component")

        # Evaluate the function
        namespace = {}
        exec(func_source, namespace)
        func = namespace[func_name]

        from lfx.base.functions import FunctionComponent
        return FunctionComponent(func=func, **custom_params)

    # Existing class-based logic
    code = custom_params.pop("code")
    class_object = eval_custom_component_code(code)
    # ...
```

### 13.5 Limitations & Edge Cases

| Scenario | Behavior | Recommendation |
|----------|----------|----------------|
| Lambda functions | `inspect.getsource()` fails | Use named functions |
| REPL-defined functions | Source not available | Save to file first |
| Closures with captured vars | Variables not serialized | Avoid closures or inject at runtime |
| Functions with side effects | Re-execution may differ | Keep functions pure |
| Functions importing local modules | Imports may fail on reload | Use absolute imports |

### 13.6 Decorator with Source Capture

The `@component` decorator captures source at decoration time:

```python
@component
def my_func(x: str) -> str:
    return x

# my_func._function_source contains the source code
# This is captured at decoration time, even in REPL
```

This works because `inspect.getsource()` is called while the decorator is being executed, at which point the function definition is still accessible.

---

## 14. UI Workflow: CustomComponent Code Editing

### 14.1 Current UI Flow for Component Code Editing

When a user edits code in a CustomComponent in the Langflow UI:

```
User edits code in CustomComponent
            │
            ▼
Frontend calls POST /api/v1/custom_component/update
            │
            ▼
endpoints.py: custom_component_update()
  └─► Component(_code=code_request.code)
            │
            ▼
build_custom_component_template()
  └─► get_component_instance()
            │
            ▼
eval_custom_component_code(code)
  ├─► extract_class_name(code)  # Find Component subclass
  └─► create_class(code, class_name)  # Compile and return class
            │
            ▼
Frontend node returned with inputs/outputs
```

### 14.2 Key Files and Functions

| File | Function | Purpose |
|------|----------|---------|
| `src/backend/base/langflow/api/v1/endpoints.py:865-884` | `custom_component()` | Handle new custom component |
| `src/backend/base/langflow/api/v1/endpoints.py:887-953` | `custom_component_update()` | Handle code updates |
| `src/lfx/src/lfx/custom/utils.py:540-577` | `build_custom_component_template()` | Build frontend node from component |
| `src/lfx/src/lfx/custom/utils.py:300-320` | `get_component_instance()` | Evaluate code and get instance |
| `src/lfx/src/lfx/custom/eval.py:9-12` | `eval_custom_component_code()` | Main code evaluation entry point |
| `src/lfx/src/lfx/custom/validate.py:495-523` | `extract_class_name()` | Find Component subclass in code |
| `src/lfx/src/lfx/custom/validate.py:241-286` | `create_class()` | Compile code and return class |

### 14.3 Required Changes for FunctionComponent UI Support

For users to write function code directly in the UI CustomComponent, we need:

#### 14.3.1 Update `eval_custom_component_code`

```python
# src/lfx/src/lfx/custom/eval.py

def eval_custom_component_code(code: str) -> type["CustomComponent"]:
    """Evaluate custom component code.

    Handles both class-based components and function-based components.
    """
    # Check if this is pure function code (no Component class)
    if _is_pure_function_code(code):
        return _create_function_component_from_code(code)

    # Check if this is serialized FunctionComponent code
    if _is_function_component_code(code):
        return _eval_function_component_code(code)

    # Existing class-based logic
    class_name = validate.extract_class_name(code)
    return validate.create_class(code, class_name)


def _is_pure_function_code(code: str) -> bool:
    """Check if code is a pure function definition (no Component class)."""
    try:
        tree = ast.parse(code)
        has_function = False
        has_component_class = False

        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                has_function = True
            elif isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name) and any(
                        pattern in base.id for pattern in ["Component", "LC"]
                    ):
                        has_component_class = True

        return has_function and not has_component_class
    except SyntaxError:
        return False


def _create_function_component_from_code(code: str) -> type:
    """Create a FunctionComponent class from pure function code."""
    from lfx.base.functions import FunctionComponent

    # Execute code to get the function
    namespace = {}
    exec(code, namespace)

    # Find the first function defined in the code
    func = None
    func_name = None
    tree = ast.parse(code)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            func_name = node.name
            func = namespace.get(func_name)
            break

    if func is None:
        msg = "No function found in code"
        raise ValueError(msg)

    # Create a factory class that behaves like a Component class
    class FunctionComponentWrapper(FunctionComponent):
        def __init__(self, **kwargs):
            super().__init__(func=func, _source_code=code, **kwargs)

    FunctionComponentWrapper.__name__ = f"FunctionComponent_{func_name}"
    return FunctionComponentWrapper
```

#### 14.3.2 Update `extract_class_name` for Function Detection

```python
# src/lfx/src/lfx/custom/validate.py

def extract_class_name(code: str) -> str:
    """Extract the name of the first Component subclass found in the code.

    Also handles FunctionComponent patterns and pure functions.
    """
    try:
        module = ast.parse(code)

        # First, check for FunctionComponent serialization pattern
        for node in module.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "_FUNCTION_NAME":
                        if isinstance(node.value, ast.Constant):
                            return f"FunctionComponent:{node.value.value}"

        # Check for Component subclass
        for node in module.body:
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name) and any(
                        pattern in base.id for pattern in ["Component", "LC"]
                    ):
                        return node.name

        # Check for pure function definition (no Component class)
        for node in module.body:
            if isinstance(node, ast.FunctionDef):
                return f"Function:{node.name}"

        msg = f"No Component subclass or function found in code. Code snippet: {code[:100]}"
        raise TypeError(msg)
    except SyntaxError as e:
        msg = f"Invalid Python code: {e!s}"
        raise ValueError(msg) from e
```

#### 14.3.3 Update `get_component_instance`

```python
# src/lfx/src/lfx/custom/utils.py

def get_component_instance(custom_component: CustomComponent | Component, user_id: str | UUID | None = None):
    """Returns an instance of a custom component, evaluating its code if necessary."""
    code = custom_component._code
    if not isinstance(code, str):
        error = "Code is None" if code is None else "Invalid code type"
        msg = f"Invalid type conversion: {error}. Please check your code and try again."
        logger.error(msg)
        raise HTTPException(status_code=400, detail={"error": msg})

    try:
        custom_class = eval_custom_component_code(code)
    except Exception as exc:
        # ... existing error handling ...

    # Instantiate the class (works for both Component and FunctionComponent)
    try:
        custom_instance = custom_class(_user_id=user_id, _code=code)
    except TypeError:
        # FunctionComponent might have different constructor signature
        custom_instance = custom_class(_code=code)

    return custom_instance
```

### 14.4 UI Code Example for Users

With these changes, users can write code like this in the UI:

**Option 1: Pure function (simplest)**
```python
def process_text(text: str) -> str:
    """Process input text.

    Args:
        text: The input text to process
    """
    return text.upper()
```

**Option 2: Using @component decorator**
```python
from lfx.base.functions import component

@component(
    display_name="Text Processor",
    category="Text Processing",
)
def process_text(text: str) -> str:
    """Process input text.

    Args:
        text: The input text to process
    """
    return text.upper()
```

**Option 3: Explicit FunctionComponent (most control)**
```python
from lfx.base.functions import FunctionComponent

def process_text(text: str) -> str:
    """Process input text."""
    return text.upper()

# Create component with explicit configuration
component = FunctionComponent(
    func=process_text,
    display_name="Text Processor",
)
```

### 14.5 Validation Flow

The existing `/validate/code` endpoint should also be updated:

```python
# src/backend/base/langflow/api/v1/validate.py

@router.post("/code", status_code=200)
async def post_validate_code(code: Code, _current_user: CurrentActiveUser) -> CodeValidationResponse:
    try:
        errors = validate_code(code.code)

        # Add function-specific validation
        if _is_pure_function_code(code.code):
            func_errors = validate_function_code(code.code)
            errors["function"]["errors"].extend(func_errors)

        return CodeValidationResponse(
            imports=errors.get("imports", {}),
            function=errors.get("function", {}),
        )
    except Exception as e:
        logger.debug("Error validating code", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
```

---

## 15. Summary

The FunctionComponent feature will enable a powerful new workflow where developers can:

1. Write simple Python functions with type hints
2. Connect them directly to existing Langflow components
3. Chain multiple functions together
4. Have inputs/outputs automatically generated from signatures
5. Use the `@component` decorator for the cleanest syntax
6. Persist and reload function-based graphs

### 15.1 Implementation Requirements

| Area | Changes Required |
|------|------------------|
| **New Files** | `src/lfx/src/lfx/base/functions/function_component.py` - FunctionComponent class |
| | `src/lfx/src/lfx/base/functions/__init__.py` - Module exports with `component` decorator, `InputConfig` class |
| **Modified Files** | `src/lfx/src/lfx/custom/custom_component/component.py` - Add function handling in `_process_connection_or_parameter()` |
| | `src/lfx/src/lfx/custom/eval.py` - Add `_is_pure_function_code()`, `_is_function_component_code()`, `_eval_function_component_code()`, `_create_function_component_from_code()` |
| | `src/lfx/src/lfx/custom/validate.py` - Update `extract_class_name()` for function detection |
| | `src/lfx/src/lfx/custom/utils.py` - Update `get_component_instance()` for FunctionComponent |
| | `src/lfx/src/lfx/interface/initialize/loading.py` - Handle FunctionComponent in `instantiate_class()` |
| | `src/lfx/src/lfx/base/__init__.py` - Export new module |
| | `src/backend/base/langflow/api/v1/validate.py` - Add function validation support |

### 15.2 Key Design Decisions

1. **Decorator API**: The `@component` decorator provides the cleanest DX and captures source code at decoration time
2. **Annotated Types**: Use `typing.Annotated` with `InputConfig` for fine-grained input customization
3. **Persistence**: Store function source in "code" field with `_FUNCTION_NAME` marker for detection
4. **Type Coercion**: Automatically convert `Message→str` and `Data→dict` for seamless connections
5. **Error Messages**: Provide clear, actionable error messages for type mismatches
6. **UI Support**: Users can write pure functions in CustomComponent code editor

### 15.3 Implementation Phases

**Phase 1: Core FunctionComponent**
- Create `FunctionComponent` class with signature introspection
- Implement `from_function()` factory function
- Add type mapping for common Python types

**Phase 2: Decorator & Customization**
- Implement `@component` decorator with parameters
- Create `InputConfig` class for `Annotated` customization
- Add docstring parsing for parameter descriptions

**Phase 3: Persistence**
- Implement source code capture via `inspect.getsource()`
- Modify `to_frontend_node()` for function serialization
- Update evaluation functions for deserialization

**Phase 4: Integration**
- Modify `Component.set()` to auto-wrap plain functions
- Add comprehensive test suite
- Document API and provide examples

This feature maintains backward compatibility while significantly expanding the expressiveness of the programmatic Graph building API.
