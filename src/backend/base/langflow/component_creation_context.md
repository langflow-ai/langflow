# Langflow Component Creation Context & Rules

This file provides in-depth rules, best practices, and references for creating new components (built-in or custom) in Langflow. Use this as a context/reference when developing new components to ensure compatibility, maintainability, and best user experience.

---

## 1. Component Class Structure
- All components must inherit from `Component` (for custom: `from langflow.custom import Component`).
- Use class-level attributes for `display_name`, `description`, `icon`, and `name`.
- Define `inputs` and `outputs` as class-level lists.
- For custom components, the main logic should be in a method referenced by the output (e.g., `build_result`).

---

## 2. Inputs
- Use input field types from `langflow.io`:
  - `MessageTextInput`: For string/text fields (preferred for most text inputs).
  - `DropdownInput`: For selection from a list of options.
  - `BoolInput`: For boolean values.
  - `FileInput`: For file uploads.
  - `IntInput`, `FloatInput`, `MultilineInput`, `DictInput`, etc. for other types.
- Each input must have a unique `name` and a descriptive `display_name`.
- Avoid overlap between input and output names.
- Inputs are accessed as `self.input_name` in your methods.
- For advanced/dynamic fields, see how `update_build_config` is used in components like `CreateDataComponent`.

---

## 3. Outputs
- Use the `Output` class from `langflow.io` for outputs.
- Each output must have:
  - `display_name`: Shown in the UI.
  - `name`: Used for referencing the output.
  - `method`: The method that produces the output (must exist in the class).
- The output method must have a return type annotation (e.g., `def build_result(self) -> str:` or `async def message_response(self) -> Message:`).
- Outputs are registered as a list in the `outputs` class attribute.

---

## 4. Context Usage (`self.ctx`)
- `self.ctx` is a session-scoped dictionary for sharing data between nodes/components in the same flow run.
- Store a value: `self.add_to_ctx("key", value, overwrite=True)`
- Retrieve a value: `value = self.ctx.get("key")`
- Delete a value: `del self.ctx["key"]`
- Use context for passing data between nodes, caching, or session-specific state.

---

## 5. Logging
- Use `self.log(message, name=None)` to log messages from your component.
- For errors, raise exceptions with clear messages (e.g., `raise ValueError("...error...")`).
- You can also use `logger` from `loguru` for advanced logging, but prefer `self.log` for flow-related logs.

---

## 6. Error Handling
- Validate all required inputs in your output method.
- Raise `ValueError` or `TypeError` with clear messages for invalid input or configuration.
- Use try/except blocks for external calls (e.g., database, API) and log errors.

---

## 7. Naming and Metadata
- `display_name`: User-friendly, descriptive name for the component.
- `name`: Unique identifier for the component (used in flows).
- `icon`: String (emoji or icon name) for UI display.
- `description`: Brief explanation of the component's purpose.

---

## 8. Imports
- Import all input/output types from `langflow.io`.
- Import `Component` from `langflow.custom` for custom components.
- For built-in types, see `base/langflow/io/__init__.py` for available fields.

---

## 9. Method Conventions
- Output methods must match the `method` name in the `Output` definition.
- Always annotate the return type of output methods.
- Use `async def` for methods that perform I/O or awaitable operations.
- Use `self.status = ...` to set the component's status for UI/debugging.

---

## 10. Example Template
```python
from langflow.custom import Component
from langflow.io import MessageTextInput, Output

class MyComponent(Component):
    display_name = "My Component"
    description = "Describe what this component does."
    icon = "🔧"
    name = "MyComponent"

    inputs = [
        MessageTextInput(name="input1", display_name="Input 1", required=True),
        MessageTextInput(name="input2", display_name="Input 2"),
    ]
    outputs = [
        Output(display_name="Result", name="result", method="build_result"),
    ]

    def build_result(self) -> str:
        # Access inputs as self.input1, self.input2
        # Access context as self.ctx
        value = self.input1
        self.add_to_ctx("my_key", value, overwrite=True)
        self.log(f"Processing value: {value}")
        return f"Processed: {value}"
```

---

## 11. Advanced Features
- For async operations, use `async def` and `await`.
- For dynamic input fields, override `update_build_config`.
- For stateful or tool components, see advanced examples in the codebase.
- Use `self.get_input(name)` and `self.get_output(name)` for advanced input/output handling.
- Use `self.status` to set the current status/result for UI/debugging.

---

## 12. Common Pitfalls & How to Avoid Them
- **Missing return type annotation**: Always annotate output methods (e.g., `-> str`).
- **Overlapping input/output names**: Ensure all names are unique within the component.
- **Not calling `super().__init__` in custom `__init__`**: Always call the base class constructor.
- **Forgetting to validate required inputs**: Check for required fields in your output method.
- **Not handling exceptions from external services**: Use try/except and log errors.
- **Not using `self.ctx` for session data**: Use context for any data that needs to be shared across nodes in a flow.

---

## 13. References
- See `base/langflow/components/inputs/chat.py` and `base/langflow/components/outputs/chat.py` for real examples.
- See `base/langflow/io/__init__.py` for all available input/output field types.
- See `base/langflow/custom/custom_component/component.py` for advanced features and methods.

---

**Use this file as a reference and checklist when creating new components in Langflow.** 