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

## 4. Type Mapping Strategy

### 4.1 Python Type to Langflow Type Mapping

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

## 8. Testing Strategy

### 8.1 Unit Tests for FunctionComponent

```python
# test_function_component.py

def test_function_component_from_simple_function():
    def greet(name: str) -> str:
        return f"Hello, {name}!"

    fc = FunctionComponent(greet)

    assert len(fc.inputs) == 1
    assert fc.inputs[0].name == "name"
    assert fc.inputs[0].input_types == ["Text"]

    assert len(fc.outputs) == 1
    assert fc.outputs[0].name == "result"
    assert "Text" in fc.outputs[0].types


def test_function_component_with_docstring():
    def process(data: str) -> str:
        """Process the data.

        Args:
            data: The input data to process
        """
        return data

    fc = FunctionComponent(process)
    assert fc.inputs[0].info == "The input data to process"


def test_function_component_in_graph():
    def double(x: int) -> int:
        return x * 2

    chat_input = ChatInput(_id="input")
    fc = FunctionComponent(double, _id="double")
    fc.set(x=chat_input.message_response)  # Type mismatch - need to handle

    graph = Graph(chat_input, fc)
    # ... assertions
```

### 8.2 Integration Tests

```python
@pytest.mark.asyncio
async def test_function_component_execution():
    def add(a: int, b: int) -> int:
        return a + b

    fc = FunctionComponent(add)
    fc.set(a=5, b=3)

    graph = Graph(fc, fc)
    results = [r async for r in graph.async_start()]

    # Verify result
    assert results[-2].vertex.custom_component.get_output("result").value == 8
```

---

## 9. Edge Cases to Handle

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

## 12. Summary

The FunctionComponent feature will enable a powerful new workflow where developers can:

1. Write simple Python functions with type hints
2. Connect them directly to existing Langflow components
3. Chain multiple functions together
4. Have inputs/outputs automatically generated from signatures

The implementation requires:
- Creating a new `FunctionComponent` class in `lfx.base.functions`
- Modifying `Component.set()` to detect and wrap plain functions
- Proper type mapping between Python types and Langflow types

This feature maintains backward compatibility while significantly expanding the expressiveness of the programmatic Graph building API.
