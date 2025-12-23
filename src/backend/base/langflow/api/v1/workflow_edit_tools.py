from __future__ import annotations

import copy
import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import orjson
from lfx.custom.custom_component.component import Component
from lfx.custom.utils import get_component_instance, update_component_build_config
from lfx.graph.graph.base import Graph
from lfx.schema.dotdict import dotdict
from mcp import types

from langflow.api.utils import parse_value
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import session_scope


class WorkflowEditError(ValueError):
    """Raised when a workflow edit operation is invalid or cannot be applied."""


# Constants for field value length limits
MAX_FIELD_VALUE_LENGTH = 200
MAX_FIELD_INFO_LENGTH = 200
MAX_OPTIMIZED_VALUE_LENGTH = 500
MAX_OPTIONS_COUNT = 50


def _json_dumps(obj: Any) -> str:
    return orjson.dumps(obj).decode("utf-8")


def _generate_node_id(component_type: str) -> str:
    """Generate a unique node ID like 'ChatInput-Ab3Cd'."""
    suffix = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(5))
    return f"{component_type}-{suffix}"


def _generate_note_id() -> str:
    """Generate a unique note ID like 'note-Ab3Cd'."""
    suffix = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(5))
    return f"note-{suffix}"


def _require_flow_id(arguments: dict[str, Any]) -> UUID:
    raw = arguments.get("flow_id")
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        msg = "flow_id is required"
        raise WorkflowEditError(msg)
    try:
        return UUID(str(raw))
    except Exception as exc:
        msg = "flow_id must be a valid UUID string"
        raise WorkflowEditError(msg) from exc


def _get_agent_input_preparation_documentation() -> str:
    """Return comprehensive documentation for preparing data for Agent component."""
    return """# Agent Input Preparation Guide

## Overview
The Agent component is a core Langflow component that processes user inputs using LLM and tools.
Properly preparing input data for the Agent is critical for correct operation and message history management.

## Agent Input Requirements

### Input Field: `input_value`
The Agent expects its `input_value` input to be one of two types:

#### Option 1: Message Object (RECOMMENDED)
A `Message` object with the following structure:

```python
from lfx.schema.message import Message

message = await Message.create(
    text="User's question or input",
    sender="User",              # "User" or "Machine"
    sender_name="User",         # Display name (e.g., "John", "Bot")
    session_id="unique_session_id",  # CRITICAL for message history
    context_id="optional_context",   # Additional grouping layer
    files=[],                   # Optional: list of file paths/Image objects
)
```

**Required Fields:**
- `text`: The actual message content (string)
- `sender`: Type of sender - "User" or "Machine"
- `sender_name`: Display name for the sender
- `session_id`: Unique identifier for grouping conversation history

**Optional Fields:**
- `context_id`: Additional layer for separating contexts within same session
- `files`: List of file paths or Image objects for multimodal inputs
- `timestamp`: Auto-generated if not provided
- `flow_id`: Auto-populated by Langflow

#### Option 2: Plain String
A simple string containing the user's message. This is acceptable but does NOT support:
- Automatic message history
- Sender identification
- Session management
- File attachments

**Use plain string ONLY for:**
- Quick testing
- Stateless one-off queries
- Components that don't need conversation history

## Message History Management

### How It Works
Agent automatically retrieves and maintains conversation history using `session_id`:

1. **Automatic Retrieval**: Agent loads last N messages (default: 100) from the same `session_id`
2. **Automatic Storage**: Agent's response is automatically saved with the same `session_id`
3. **Grouping**: Messages with the same `session_id` form one conversation thread
4. **Additional Filtering**: Use `context_id` to create sub-contexts within a session

### Session ID Best Practices

```python
# Web chat: use user-specific session ID
session_id = "web_user_123"

# Telegram bot: use chat-specific session ID
session_id = f"telegram_{chat_id}"

# API integration: use request context
session_id = f"api_{user_id}_{conversation_id}"

# Multi-tenant: include tenant identifier
session_id = f"tenant_{tenant_id}_user_{user_id}"
```

**CRITICAL:** Each unique `session_id` creates a separate conversation history!

## Standard Input Sources

### 1. ChatInput Component (RECOMMENDED for web interfaces)

**Use Case:** Playground, web chat, interactive workflows

```python
# ChatInput automatically provides:
ChatInput.outputs = [
    Output(name="message", method="message_response")  # Returns Message object
]

# What it handles automatically:
# - Creates proper Message object
# - Sets sender="User", sender_name="User"
# - Uses current session_id from Playground
# - Saves message to history (if should_store_message=True)
# - Supports file uploads
```

**Connection:**
```
ChatInput → [message output] → Agent [input_value input]
```

**When to use:**
- ✅ Building chat interfaces
- ✅ Playground testing
- ✅ Need automatic history management
- ✅ Want file upload support

### 2. TextInput Component

**Use Case:** Simple text inputs without history

```python
# TextInput returns plain string
TextInput.outputs = [
    Output(name="text", method="text_response")  # Returns string
]
```

**Connection:**
```
TextInput → [text output] → Agent [input_value input]
```

**When to use:**
- ✅ Stateless queries
- ✅ One-off commands
- ❌ NOT for conversations (no history)

### 3. Custom Data Sources (APIs, Webhooks, External Systems)

**Use Case:** Telegram bots, Slack integrations, custom APIs

When building custom input components, you MUST create a proper Message object:

```python
from lfx.custom import Component
from lfx.io import Output
from lfx.schema.message import Message

class CustomInputComponent(Component):
    display_name = "Custom Input"

    outputs = [
        Output(name="message", method="build_message"),
    ]

    async def build_message(self) -> Message:
        # Extract data from your source (API, webhook, etc.)
        raw_data = self.get_external_data()

        # Create unique session_id for history grouping
        # Example for Telegram: use chat_id
        # Example for Slack: use channel_id + user_id
        session_id = f"source_{raw_data['user_id']}"

        # Create Message object
        message = await Message.create(
            text=raw_data['text'],
            sender="User",
            sender_name=raw_data.get('username', 'User'),
            session_id=session_id,
            context_id=raw_data.get('context', ''),
        )

        return message
```

**CRITICAL Points:**
1. Always return `Message` object, not `Data` or plain dict
2. Use consistent `session_id` format for your data source
3. Set appropriate `sender` and `sender_name`
4. Use `context_id` for additional grouping if needed

## Complete Examples

### Example 1: Simple Chat Agent (ChatInput → Agent → ChatOutput)

```
Workflow:
┌────────────┐     ┌───────────┐     ┌──────────────┐
│ ChatInput  │────▶│   Agent   │────▶│  ChatOutput  │
└────────────┘     └───────────┘     └──────────────┘
   message           input_value         input_value

Components setup:
1. ChatInput:
   - should_store_message: True (saves to history)
   - Uses session_id from Playground automatically

2. Agent:
   - Automatically loads history from session_id
   - Processes input with LLM + tools
   - Saves response to same session_id

3. ChatOutput:
   - Displays response
   - Also saves to history if should_store_message=True
```

### Example 2: Telegram Bot Integration

```python
class TelegramInput(Component):
    display_name = "Telegram Input"

    inputs = [
        DataInput(name="webhook_data", display_name="Webhook Data"),
    ]

    outputs = [
        Output(name="message", method="build_message"),
        Output(name="chat_id", method="get_chat_id"),
    ]

    async def build_message(self) -> Message:
        update = self.webhook_data.data
        message_obj = update.get("message", {})
        chat = message_obj.get("chat", {})
        from_user = message_obj.get("from", {})

        # CRITICAL: Use chat_id as session_id
        # This ensures each Telegram chat has separate history
        session_id = f"telegram_{chat.get('id')}"

        message = await Message.create(
            text=message_obj.get("text", ""),
            sender="User",
            sender_name=from_user.get("first_name", "Telegram User"),
            session_id=session_id,
            context_id="telegram",  # Group all Telegram messages
        )

        return message

    def get_chat_id(self) -> Data:
        # Return chat_id for sending reply
        update = self.webhook_data.data
        chat_id = update.get("message", {}).get("chat", {}).get("id", "")
        return Data(data={"chat_id": chat_id})
```

```
Workflow:
┌──────────────┐     ┌───────────┐     ┌───────────────┐
│ Telegram     │────▶│   Agent   │────▶│ Telegram Send │
│ Input        │     └───────────┘     │ Message       │
└──────────────┘                       └───────────────┘
   message               input_value            ▲
   chat_id ──────────────────────────────────────┘
                                      (for reply)
```

### Example 3: API Integration with Context Separation

```python
class APIInput(Component):
    display_name = "API Input"

    inputs = [
        StrInput(name="user_id", display_name="User ID"),
        StrInput(name="tenant_id", display_name="Tenant ID"),
        MessageTextInput(name="query", display_name="Query"),
    ]

    outputs = [
        Output(name="message", method="build_message"),
    ]

    async def build_message(self) -> Message:
        # Multi-tenant session management
        session_id = f"api_tenant_{self.tenant_id}_user_{self.user_id}"

        # Use context_id for different conversation types
        context_id = "support_chat"  # or "sales_chat", "technical_chat"

        message = await Message.create(
            text=self.query,
            sender="User",
            sender_name=f"User_{self.user_id}",
            session_id=session_id,
            context_id=context_id,
        )

        return message
```

## Common Pitfalls and Solutions

### ❌ WRONG: Passing Data object instead of Message
```python
# This will NOT work properly
def build_output(self) -> Data:
    return Data(data={"text": "Hello"})  # Agent won't get history!
```

### ✅ CORRECT: Create proper Message object
```python
async def build_output(self) -> Message:
    return await Message.create(
        text="Hello",
        sender="User",
        sender_name="User",
        session_id="my_session_123",
    )
```

### ❌ WRONG: Using random session_id
```python
# This creates NEW session every time - no history!
session_id = str(uuid4())  # Different every call
```

### ✅ CORRECT: Use consistent session_id
```python
# Same session_id for same conversation
session_id = f"telegram_{chat_id}"  # Consistent per chat
```

### ❌ WRONG: Not setting sender information
```python
message = Message(text="Hello")  # Missing sender, sender_name, session_id
```

### ✅ CORRECT: Set all required fields
```python
message = await Message.create(
    text="Hello",
    sender="User",
    sender_name="John",
    session_id="session_123",
)
```

## Checklist for Agent Input Preparation

When creating a component that feeds into Agent:

- [ ] Output type is `Message` (not `Data` or string)
- [ ] `text` field contains the actual message content
- [ ] `sender` is set to "User" (for user messages) or "Machine" (for system messages)
- [ ] `sender_name` is set to a meaningful display name
- [ ] `session_id` is consistent for the same conversation
- [ ] `session_id` format is documented and predictable
- [ ] For multiple tenants/users, `session_id` includes identifier
- [ ] Consider using `context_id` for additional grouping
- [ ] Test that message history works correctly across multiple turns

## Advanced: Programmatic Message Creation

If you need to create messages programmatically in Python code:

```python
from lfx.schema.message import Message

# Create user message
user_message = await Message.create(
    text="What's the weather?",
    sender="User",
    sender_name="Alice",
    session_id="session_456",
)

# Create system message
system_message = await Message.create(
    text="System initialized",
    sender="Machine",
    sender_name="System",
    session_id="session_456",
)
```

## Summary

**Golden Rules:**
1. Always use `Message` objects for Agent input (not Data, not plain strings)
2. `session_id` determines conversation history - keep it consistent
3. Use ChatInput for web interfaces - it handles everything automatically
4. For custom sources (Telegram, API, etc.), manually create Message objects
5. Test your `session_id` strategy to ensure history works as expected
"""


def _get_custom_components_documentation() -> str:
    """Return comprehensive documentation for creating custom components."""
    return """# Custom Component Documentation

## Overview
Custom components allow you to add custom Python logic to workflows.
They are Python classes that inherit from `Component`.

## Basic Structure

```python
from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Data, Message

class MyCustomComponent(Component):
    display_name = "My Component"
    description = "Description of what this component does"
    icon = "code"  # Lucide icon name
    name = "MyCustomComponent"

    inputs = [
        MessageTextInput(
            name="input_text",
            display_name="Input Text",
            info="The text to process",
            value="",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="process"),
    ]

    def process(self) -> Message:
        # Access input with self.input_text
        result = self.input_text.upper()
        return Message(text=result)
```

## Available Input Types

Import from `langflow.io`:

1. **StrInput** - Single-line text
2. **MultilineInput** - Multi-line text area
3. **MessageTextInput** - Text that can accept Message connections
4. **IntInput** - Integer values
5. **FloatInput** - Float values
6. **BoolInput** - Boolean toggle
7. **DropdownInput** - Select from options
8. **SecretStrInput** - Hidden password/API key input
9. **DataInput** - Accept Data objects
10. **HandleInput** - Accept specific typed connections

## Input Parameters

- `name`: Internal variable name (access via `self.<name>`)
- `display_name`: UI label
- `info`: Tooltip/description
- `value`: Default value
- `required`: If True, must be filled
- `advanced`: If True, shown in Advanced section
- `is_list`: If True, accepts multiple values
- `input_types`: Restrict connection types, e.g. `["Message"]`
- `tool_mode`: If True, component can be used as a tool

## Output Definition

```python
Output(
    display_name="Output Name",
    name="output_name",
    method="method_name",  # Method that returns the output
    group_outputs=False  # Set to True to enable multiple outputs from one node
)
```

### Group Outputs
When a component has multiple outputs that need to work together, set `group_outputs=True` on ALL outputs:

```python
outputs = [
    Output(display_name="Message", name="message", method="get_message", group_outputs=True),
    Output(display_name="Chat ID", name="chat_id", method="get_chat_id", group_outputs=True),
]
```

This allows the node to have multiple active output connections simultaneously.

## Return Types

- **Message** - For text/chat outputs: `Message(text="Hello")`
- **Data** - For structured data: `Data(data={"key": "value"})`
- **DataFrame** - For tabular data

## Examples

### 1. Text Processor
```python
from langflow.custom import Component
from langflow.io import MessageTextInput, DropdownInput, Output
from langflow.schema import Message

class TextProcessor(Component):
    display_name = "Text Processor"
    description = "Process text with various operations"
    icon = "text"

    inputs = [
        MessageTextInput(name="text", display_name="Text", info="Text to process"),
        DropdownInput(
            name="operation",
            display_name="Operation",
            options=["uppercase", "lowercase", "reverse", "word_count"],
            value="uppercase",
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="process"),
    ]

    def process(self) -> Message:
        text = self.text
        op = self.operation
        if op == "uppercase":
            result = text.upper()
        elif op == "lowercase":
            result = text.lower()
        elif op == "reverse":
            result = text[::-1]
        elif op == "word_count":
            result = str(len(text.split()))
        else:
            result = text
        return Message(text=result)
```

### 2. API Caller
```python
from langflow.custom import Component
from langflow.io import StrInput, SecretStrInput, Output
from langflow.schema import Data
import httpx

class APICaller(Component):
    display_name = "API Caller"
    description = "Call an external API"
    icon = "globe"

    inputs = [
        StrInput(name="url", display_name="URL", info="API endpoint URL"),
        SecretStrInput(name="api_key", display_name="API Key", info="API key for auth"),
    ]

    outputs = [
        Output(display_name="Response", name="response", method="call_api"),
    ]

    def call_api(self) -> Data:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        response = httpx.get(self.url, headers=headers)
        return Data(data=response.json())
```

### 3. Math Calculator
```python
from langflow.custom import Component
from langflow.io import FloatInput, DropdownInput, Output
from langflow.schema import Message

class Calculator(Component):
    display_name = "Calculator"
    description = "Perform math operations"
    icon = "calculator"

    inputs = [
        FloatInput(name="a", display_name="A", value=0),
        FloatInput(name="b", display_name="B", value=0),
        DropdownInput(
            name="operation",
            display_name="Operation",
            options=["add", "subtract", "multiply", "divide"],
            value="add",
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="calculate"),
    ]

    def calculate(self) -> Message:
        a, b = self.a, self.b
        if self.operation == "add":
            result = a + b
        elif self.operation == "subtract":
            result = a - b
        elif self.operation == "multiply":
            result = a * b
        elif self.operation == "divide":
            result = a / b if b != 0 else "Error: Division by zero"
        else:
            result = 0
        return Message(text=str(result))
```

### 4. Data Transformer
```python
from langflow.custom import Component
from langflow.io import DataInput, StrInput, Output
from langflow.schema import Data

class DataTransformer(Component):
    display_name = "Data Transformer"
    description = "Transform Data objects"
    icon = "shuffle"

    inputs = [
        DataInput(name="input_data", display_name="Input Data", is_list=True),
        StrInput(name="key", display_name="Key", info="Key to extract"),
    ]

    outputs = [
        Output(display_name="Extracted", name="extracted", method="transform"),
    ]

    def transform(self) -> Data:
        results = []
        for item in self.input_data:
            if hasattr(item, 'data') and self.key in item.data:
                results.append(item.data[self.key])
        return Data(data={"values": results})
```

### 5. Component with Multiple Outputs
```python
from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Message, Data

class MessageParser(Component):
    display_name = "Message Parser"
    description = "Parse message and extract multiple outputs"
    icon = "split"

    inputs = [
        MessageTextInput(name="message", display_name="Message", info="Message to parse"),
    ]

    outputs = [
        Output(display_name="Text", name="text", method="get_text", group_outputs=True),
        Output(display_name="Length", name="length", method="get_length", group_outputs=True),
        Output(display_name="Metadata", name="metadata", method="get_metadata", group_outputs=True),
    ]

    def get_text(self) -> Message:
        return Message(text=self.message)

    def get_length(self) -> Data:
        return Data(data={"length": len(self.message)})

    def get_metadata(self) -> Data:
        return Data(data={"word_count": len(self.message.split())})
```

## Logging & Status

Use `self.status` to show status in UI:
```python
def process(self) -> Message:
    self.status = "Processing..."
    result = do_something()
    self.status = f"Processed {len(result)} items"
    return Message(text=result)
```

Use `self.log()` for detailed logs:
```python
self.log("Starting process")
self.log({"step": 1, "status": "complete"})
```

## Error Handling

```python
def process(self) -> Data:
    if not self.input_text:
        raise ValueError("Input text is required")
    try:
        result = risky_operation()
        return Data(data={"result": result})
    except Exception as e:
        return Data(data={"error": str(e)})
```

## Tips

1. Always import from `langflow.custom`, `langflow.io`, `langflow.schema`
2. Use `tool_mode=True` on inputs for Agent compatibility
3. Return types should match Output method return annotation
4. Use descriptive display_name and info for clarity
5. Set appropriate icon from Lucide icons (https://lucide.dev/icons)
6. Use `group_outputs=True` on all outputs when component needs multiple simultaneous output connections
"""


def _check_workflow_issues(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Check workflow for common issues and return structured list of problems.

    Checks:
    - Disconnected nodes (no incoming or outgoing edges)
    - Missing required field values
    - Edge type mismatches
    - Empty workflow
    """
    issues: list[dict[str, Any]] = []
    nodes = payload.get("nodes", [])
    edges = payload.get("edges", [])

    if not nodes:
        issues.append(
            {
                "type": "empty_workflow",
                "severity": "warning",
                "message": "Workflow is empty. Add components to build your flow.",
                "suggestion": "Use lf_list_components to see available components.",
            }
        )
        return issues

    node_ids = set()
    note_ids = set()
    for node in nodes:
        node_id = node.get("id", "")
        if node.get("type") == "noteNode":
            note_ids.add(node_id)
        else:
            node_ids.add(node_id)

    sources = {e.get("source") for e in edges}
    targets = {e.get("target") for e in edges}

    for node in nodes:
        if node.get("type") == "noteNode":
            continue

        node_id = node.get("id", "")
        node_data = node.get("data", {})
        display_name = node_data.get("display_name", node_id)
        component_type = node_data.get("type", "")

        is_input_component = component_type.lower() in ["chatinput", "textinput", "fileinput", "webhook"]
        is_output_component = component_type.lower() in ["chatoutput", "textoutput", "fileoutput"]

        has_incoming = node_id in targets
        has_outgoing = node_id in sources

        if not has_incoming and not has_outgoing:
            issues.append(
                {
                    "type": "disconnected_node",
                    "severity": "error",
                    "node_id": node_id,
                    "display_name": display_name,
                    "component_type": component_type,
                    "message": f"Node '{display_name}' ({component_type}) is not connected to any other nodes.",
                    "suggestion": "Connect this node using add_edge or remove it if not needed.",
                }
            )
        elif not has_incoming and not is_input_component:
            issues.append(
                {
                    "type": "no_incoming_connection",
                    "severity": "warning",
                    "node_id": node_id,
                    "display_name": display_name,
                    "component_type": component_type,
                    "message": f"Node '{display_name}' ({component_type}) has no incoming connections.",
                    "suggestion": (
                        "Connect an upstream node to provide input, or verify if this node should receive data."
                    ),
                }
            )
        elif not has_outgoing and not is_output_component:
            node_inner = node_data.get("node", {})
            outputs = node_inner.get("outputs", [])
            if outputs:
                issues.append(
                    {
                        "type": "no_outgoing_connection",
                        "severity": "info",
                        "node_id": node_id,
                        "display_name": display_name,
                        "component_type": component_type,
                        "message": (
                            f"Node '{display_name}' ({component_type}) has outputs but is not connected downstream."
                        ),
                        "suggestion": "Connect this node's output to another node or to an output component.",
                    }
                )

        node_inner = node_data.get("node", {})
        template = node_inner.get("template", {})

        for field_name, field_def in template.items():
            if not isinstance(field_def, dict):
                continue
            if field_name.startswith("_") or field_name == "code":
                continue

            is_required = field_def.get("required", False)
            is_shown = field_def.get("show", True)
            value = field_def.get("value")

            has_edge_connection = any(
                e.get("target") == node_id and _get_target_field_name(e) == field_name for e in edges
            )

            if (
                is_required
                and is_shown
                and not has_edge_connection
                and (value is None or value == "" or (isinstance(value, list) and len(value) == 0))
            ):
                field_display = field_def.get("display_name", field_name)
                issues.append(
                    {
                        "type": "missing_required_field",
                        "severity": "error",
                        "node_id": node_id,
                        "display_name": display_name,
                        "component_type": component_type,
                        "field": field_name,
                        "field_display_name": field_display,
                        "message": f"Required field '{field_display}' on node '{display_name}' is empty.",
                        "suggestion": ("Set a value using set_node_template_value or connect an input to this field."),
                    }
                )

    for edge in edges:
        source_id = edge.get("source", "")
        target_id = edge.get("target", "")

        edge_data = edge.get("data", {})
        source_handle = edge_data.get("sourceHandle", {})
        target_handle = edge_data.get("targetHandle", {})

        source_types = source_handle.get("output_types", []) if isinstance(source_handle, dict) else []
        target_input_types = target_handle.get("inputTypes", []) if isinstance(target_handle, dict) else []

        if source_types and target_input_types:
            compatible = any(st in target_input_types for st in source_types)
            if not compatible:
                source_name = source_handle.get("name", "unknown") if isinstance(source_handle, dict) else "unknown"
                target_field = (
                    target_handle.get("fieldName", "unknown") if isinstance(target_handle, dict) else "unknown"
                )

                source_node = next((n for n in nodes if n.get("id") == source_id), None)
                target_node = next((n for n in nodes if n.get("id") == target_id), None)

                source_display = (
                    source_node.get("data", {}).get("display_name", source_id) if source_node else source_id
                )
                target_display = (
                    target_node.get("data", {}).get("display_name", target_id) if target_node else target_id
                )

                issues.append(
                    {
                        "type": "type_mismatch",
                        "severity": "error",
                        "edge_id": edge.get("id", ""),
                        "source_node": source_id,
                        "target_node": target_id,
                        "source_output": source_name,
                        "target_input": target_field,
                        "source_types": source_types,
                        "target_accepts": target_input_types,
                        "message": (
                            f"Type mismatch: '{source_display}'.{source_name} outputs {source_types} "
                            f"but '{target_display}'.{target_field} accepts {target_input_types}."
                        ),
                        "suggestion": "Remove this edge and use compatible types, or add a converter component.",
                    }
                )

    return issues


def _get_target_field_name(edge: dict[str, Any]) -> str:
    """Extract target field name from edge handle."""
    target_handle = edge.get("targetHandle", "")
    if isinstance(target_handle, str) and target_handle:
        try:
            import json

            handle_str = target_handle.replace("œ", '"')
            handle_data = json.loads(handle_str)
            return handle_data.get("fieldName", "")
        except Exception:  # noqa: BLE001, S110
            # Handle parsing errors silently - fallback to edge data method
            pass

    edge_data = edge.get("data", {})
    target_handle_obj = edge_data.get("targetHandle", {})
    if isinstance(target_handle_obj, dict):
        return target_handle_obj.get("fieldName", "")
    return ""


def _extract_component_info(template: dict[str, Any], component_type: str, category: str) -> dict[str, Any]:
    """Extract detailed component information from template."""
    info: dict[str, Any] = {
        "component_type": component_type,
        "category": category,
        "display_name": template.get("display_name", component_type),
        "description": template.get("description", ""),
        "icon": template.get("icon", ""),
        "inputs": [],
        "outputs": [],
    }

    template_fields = template.get("template", {})
    for field_name, field_def in template_fields.items():
        if not isinstance(field_def, dict):
            continue
        if field_name.startswith("_") or field_name == "code":
            continue

        show = field_def.get("show", True)
        if not show:
            continue

        field_info: dict[str, Any] = {
            "name": field_name,
            "display_name": field_def.get("display_name", field_name),
            "type": field_def.get("type", "str"),
            "required": field_def.get("required", False),
            "advanced": field_def.get("advanced", False),
        }

        if field_def.get("info"):
            field_info["description"] = field_def["info"]

        if field_def.get("value") is not None:
            val = field_def["value"]
            if not isinstance(val, str) or len(val) < MAX_FIELD_VALUE_LENGTH:
                field_info["default"] = val

        if field_def.get("options"):
            field_info["options"] = field_def["options"]

        if field_def.get("input_types"):
            field_info["accepts_connection_types"] = field_def["input_types"]

        if field_def.get("is_list"):
            field_info["is_list"] = True

        info["inputs"].append(field_info)

    outputs = template.get("outputs", [])
    for output in outputs:
        output_info = {
            "name": output.get("name", ""),
            "display_name": output.get("display_name", output.get("name", "")),
            "types": output.get("types", []),
        }
        info["outputs"].append(output_info)

    info["inputs"] = sorted(info["inputs"], key=lambda x: (x.get("advanced", False), x["name"]))

    return info


def _optimize_workflow_payload(payload: dict[str, Any], *, include_code: bool = False) -> dict[str, Any]:
    """Optimize workflow payload by removing unnecessary data for LLM context.

    Args:
        payload: The full workflow payload
        include_code: If True, keep the 'code' field in templates (default: False)

    Returns:
        Optimized payload with minimal necessary data
    """
    if not payload:
        return payload

    optimized = {
        "nodes": [],
        "edges": payload.get("edges", []),
    }

    nodes = payload.get("nodes", [])
    for node in nodes:
        node_data = node.get("data", {})
        node_inner = node_data.get("node", {})
        template = node_inner.get("template", {})

        # Create optimized template with only essential fields
        optimized_template = {}

        # Fields to exclude (they consume too many tokens)
        exclude_fields = {
            "code",  # Source code can be hundreds of lines
            "file_path",
            "fileTypes",
            "load_from_db",
            "title_case",
            "placeholder",
            "password",  # Security field, not needed for structure
            "curl",  # Generated field
            "endpoint",  # Generated field
        }

        # Keep only if explicitly requested
        if include_code:
            exclude_fields.discard("code")

        for field_name, field_value in template.items():
            if field_name.startswith("_") or field_name in exclude_fields:
                continue

            if isinstance(field_value, dict):
                # Keep only essential metadata for each field
                optimized_field = {
                    "type": field_value.get("type"),
                    "display_name": field_value.get("display_name"),
                    "required": field_value.get("required", False),
                    "advanced": field_value.get("advanced", False),
                    "show": field_value.get("show", True),
                }

                # Keep value if not default/empty
                if "value" in field_value:
                    val = field_value["value"]
                    # Don't include large string values or empty values
                    if val and (not isinstance(val, str) or len(val) < MAX_OPTIMIZED_VALUE_LENGTH):
                        optimized_field["value"] = val

                # Keep input/output types for validation
                if "input_types" in field_value:
                    optimized_field["input_types"] = field_value["input_types"]
                if "output_types" in field_value:
                    optimized_field["output_types"] = field_value["output_types"]

                # Keep info if short
                info = field_value.get("info", "")
                if info and len(info) < MAX_FIELD_INFO_LENGTH:
                    optimized_field["info"] = info

                # Keep options for dropdown fields (critical for assistant to set correct values)
                if field_value.get("options"):
                    options = field_value["options"]
                    # Limit options to avoid token bloat
                    if isinstance(options, list) and len(options) <= MAX_OPTIONS_COUNT:
                        optimized_field["options"] = options
                    elif isinstance(options, list):
                        optimized_field["options"] = options[:MAX_OPTIONS_COUNT]
                        optimized_field["options_truncated"] = True

                optimized_template[field_name] = optimized_field
            else:
                optimized_template[field_name] = field_value

        # Create optimized node structure
        optimized_node = {
            "id": node.get("id"),
            "type": node.get("type"),
            "position": node.get("position"),
            "data": {
                "id": node_data.get("id"),
                "type": node_data.get("type"),
                "display_name": node_data.get("display_name"),
                "description": node_inner.get("description", ""),
                "node": {
                    "template": optimized_template,
                    "display_name": node_inner.get("display_name"),
                    "description": node_inner.get("description", ""),
                    "outputs": node_inner.get("outputs", []),
                },
            },
        }

        optimized["nodes"].append(optimized_node)

    return optimized


async def _get_flow_for_user(*, flow_id: UUID, user_id: UUID) -> Flow:
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        if not flow or flow.user_id != user_id:
            msg = "Flow not found"
            raise WorkflowEditError(msg)
        return flow


def validate_flow_payload(payload: dict[str, Any]) -> list[str]:
    """Validate flow payload structure using Graph parsing, returning a list of errors."""
    try:
        Graph.from_payload(payload)
    except Exception as exc:  # noqa: BLE001
        return [str(exc)]
    else:
        return []


def _ensure_list(value: Any, *, name: str) -> list:
    if isinstance(value, list):
        return value
    msg = f"Invalid '{name}': expected list"
    raise WorkflowEditError(msg)


def _ensure_dict(value: Any, *, name: str) -> dict:
    if isinstance(value, dict):
        return value
    msg = f"Invalid '{name}': expected object"
    raise WorkflowEditError(msg)


def _find_node_index(nodes: list[dict[str, Any]], node_id: str) -> int:
    for i, n in enumerate(nodes):
        if str(n.get("id")) == node_id:
            return i
    msg = f"Node '{node_id}' not found"
    raise WorkflowEditError(msg)


def _find_edge_index(edges: list[dict[str, Any]], edge_id: str) -> int:
    for i, e in enumerate(edges):
        if str(e.get("id")) == edge_id:
            return i
    msg = f"Edge '{edge_id}' not found"
    raise WorkflowEditError(msg)


async def _apply_set_node_template_value(
    payload: dict[str, Any],
    *,
    node_id: str,
    field_name: str,
    value: Any,
    create_if_missing: bool,
    user_id: UUID,
) -> None:
    """Set a template field value on a node.

    If the field has `real_time_refresh=True`, this will also call the component's
    `update_build_config` method to handle dynamic field updates (e.g., updating
    input_types when a dropdown value changes).
    """
    nodes = _ensure_list(payload.get("nodes", []), name="nodes")
    idx = _find_node_index(nodes, node_id)
    node = _ensure_dict(nodes[idx], name="node")
    data = _ensure_dict(node.get("data", {}), name="node.data")
    node_inner = _ensure_dict(data.get("node", {}), name="node.data.node")
    template = _ensure_dict(node_inner.get("template", {}), name="node.data.node.template")

    if field_name not in template:
        if not create_if_missing:
            msg = f"Template field '{field_name}' not found on node '{node_id}'"
            raise WorkflowEditError(msg)
        template[field_name] = {"type": "str", "value": None, "show": True}

    field = template[field_name]
    if not isinstance(field, dict):
        msg = f"Template field '{field_name}' is not an object on node '{node_id}'"
        raise WorkflowEditError(msg)

    field["value"] = value

    # If field has real_time_refresh, call update_build_config for dynamic updates
    if field.get("real_time_refresh"):
        await _apply_dynamic_build_config_update(
            template=template,
            field_name=field_name,
            field_value=value,
            user_id=user_id,
        )


async def _apply_dynamic_build_config_update(
    *,
    template: dict[str, Any],
    field_name: str,
    field_value: Any,
    user_id: UUID,
) -> None:
    """Call update_build_config on the component to handle dynamic field updates.

    This is called when a field with `real_time_refresh=True` is modified.
    The component's update_build_config method can modify input_types, add/remove fields, etc.
    """
    # Get the code from template
    code_field = template.get("code", {})
    code = code_field.get("value") if isinstance(code_field, dict) else None

    if not code:
        return

    try:
        component = Component(_code=code)
        cc_instance = get_component_instance(component, user_id=user_id)

        # Set current attributes on the component instance, INCLUDING the new value
        if hasattr(cc_instance, "set_attributes"):
            params = {}
            for key, value_dict in template.items():
                if isinstance(value_dict, dict) and key != "code":
                    val = value_dict.get("value")
                    input_type = str(value_dict.get("_input_type", ""))
                    params[key] = parse_value(val, input_type)
            # Override with the new field value we're setting
            params[field_name] = field_value
            cc_instance.set_attributes(params)

        # Call update_build_config to get updated configuration
        build_config = dotdict(template)
        updated_config = await update_component_build_config(
            cc_instance,
            build_config=build_config,
            field_value=field_value,
            field_name=field_name,
        )
        if updated_config:
            # Replace the template entirely so dynamic add/remove fields are applied correctly.
            template.clear()
            template.update(dict(updated_config))
    except Exception as e:
        msg = f"Dynamic template update failed for '{field_name}': {e}"
        raise WorkflowEditError(msg) from e


def _get_node_by_id(nodes: list[dict[str, Any]], node_id: str) -> dict[str, Any] | None:
    """Find a node by ID in the nodes list."""
    for n in nodes:
        if str(n.get("id")) == node_id:
            return n
    return None


def _find_output_by_name(node: dict[str, Any], output_name: str) -> dict[str, Any] | None:
    """Find an output definition by name in a node's outputs list."""
    node_data = node.get("data", {}).get("node", {})
    outputs = node_data.get("outputs", [])
    for output in outputs:
        if output.get("name") == output_name:
            return output
    return None


def _find_input_by_name(node: dict[str, Any], input_name: str) -> dict[str, Any] | None:
    """Find an input field definition by name in a node's template."""
    node_data = node.get("data", {}).get("node", {})
    template = node_data.get("template", {})
    if input_name in template and isinstance(template[input_name], dict):
        return template[input_name]
    return None


def _build_source_handle(
    source_node: dict[str, Any],
    output_name: str,
) -> dict[str, Any]:
    """Build a proper sourceHandle dictionary from node output info."""
    node_id = source_node.get("id", "")
    node_data = source_node.get("data", {})
    component_type = node_data.get("type", "")

    output = _find_output_by_name(source_node, output_name)
    if output:
        output_types = output.get("types", [])
        return {
            "dataType": component_type,
            "id": node_id,
            "name": output_name,
            "output_types": output_types,
        }
    return {
        "dataType": component_type,
        "id": node_id,
        "name": output_name,
        "output_types": [],
    }


def _build_target_handle(
    target_node: dict[str, Any],
    input_name: str,
) -> dict[str, Any]:
    """Build a proper targetHandle dictionary from node input info."""
    node_id = target_node.get("id", "")

    input_field = _find_input_by_name(target_node, input_name)
    if input_field:
        field_type = input_field.get("type", "str")
        input_types = input_field.get("input_types") or []
        return {
            "fieldName": input_name,
            "id": node_id,
            "inputTypes": input_types,
            "type": field_type,
        }
    return {
        "fieldName": input_name,
        "id": node_id,
        "inputTypes": [],
        "type": "str",
    }


def _handle_to_string(handle: dict[str, Any]) -> str:
    """Convert handle dict to the special string format used by React Flow.

    Uses œ instead of " to avoid JSON escaping issues.
    """
    import json

    json_str = json.dumps(handle, separators=(",", ":"))
    return json_str.replace('"', "œ")


def _normalize_edge(payload: dict[str, Any], edge: dict[str, Any]) -> dict[str, Any]:
    """Normalize edge to proper format for React Flow and Langflow.

    Accepts simplified format:
        {"source": "...", "target": "...", "sourceHandle": "output_name", "targetHandle": "input_name"}

    Converts to full React Flow format with nested data for Langflow validation.
    """
    if "data" in edge and isinstance(edge.get("data"), dict):
        data = edge["data"]
        if isinstance(data.get("sourceHandle"), dict) and isinstance(data.get("targetHandle"), dict):
            if "id" not in edge:
                source_id = edge.get("source", "")
                target_id = edge.get("target", "")
                source_str = _handle_to_string(data["sourceHandle"])
                target_str = _handle_to_string(data["targetHandle"])
                edge["id"] = f"xy-edge__{source_id}{source_str}-{target_id}{target_str}"
                edge["sourceHandle"] = source_str
                edge["targetHandle"] = target_str
            return edge

    source_id = str(edge.get("source", ""))
    target_id = str(edge.get("target", ""))

    source_handle_name = edge.get("sourceHandle", "")
    target_handle_name = edge.get("targetHandle", "")

    if not source_id or not target_id:
        msg = "Edge requires 'source' and 'target' node IDs"
        raise WorkflowEditError(msg)

    nodes = _ensure_list(payload.get("nodes", []), name="nodes")

    source_node = _get_node_by_id(nodes, source_id)
    target_node = _get_node_by_id(nodes, target_id)

    if not source_node:
        msg = f"Source node '{source_id}' not found"
        raise WorkflowEditError(msg)
    if not target_node:
        msg = f"Target node '{target_id}' not found"
        raise WorkflowEditError(msg)

    if not source_handle_name:
        node_data = source_node.get("data", {}).get("node", {})
        outputs = node_data.get("outputs", [])
        source_handle_name = outputs[0].get("name", "output") if outputs else "output"

    if not target_handle_name:
        target_handle_name = "input_value"

    source_handle = _build_source_handle(source_node, source_handle_name)
    target_handle = _build_target_handle(target_node, target_handle_name)

    # IMPORTANT (frontend compatibility):
    # Frontend validates edges against `sourceNode.data.selected_output` and may drop edges
    # that point to a non-selected output on nodes with multiple outputs.
    # Keep `selected_output` aligned with the output we are connecting.
    source_data = source_node.get("data")
    if (
        source_node.get("type") == "genericNode"
        and isinstance(source_data, dict)
        and _find_output_by_name(source_node, source_handle_name) is not None
    ):
        source_data["selected_output"] = source_handle_name

    source_handle_str = _handle_to_string(source_handle)
    target_handle_str = _handle_to_string(target_handle)

    return {
        "id": f"xy-edge__{source_id}{source_handle_str}-{target_id}{target_handle_str}",
        "source": source_id,
        "target": target_id,
        "sourceHandle": source_handle_str,
        "targetHandle": target_handle_str,
        "data": {
            "sourceHandle": source_handle,
            "targetHandle": target_handle,
        },
        "animated": False,
        "className": "",
        "selected": False,
    }


def _apply_add_edge(payload: dict[str, Any], *, edge: dict[str, Any]) -> None:
    """Add an edge to the workflow, normalizing format if needed."""
    edges = _ensure_list(payload.get("edges", []), name="edges")
    normalized_edge = _normalize_edge(payload, edge)
    edges.append(normalized_edge)


def _apply_remove_edge(payload: dict[str, Any], *, edge_id: str) -> None:
    edges = _ensure_list(payload.get("edges", []), name="edges")
    idx = _find_edge_index(edges, edge_id)
    edges.pop(idx)


def _apply_remove_node(payload: dict[str, Any], *, node_id: str) -> None:
    nodes = _ensure_list(payload.get("nodes", []), name="nodes")
    edges = _ensure_list(payload.get("edges", []), name="edges")
    idx = _find_node_index(nodes, node_id)
    nodes.pop(idx)
    payload["edges"] = [e for e in edges if str(e.get("source")) != node_id and str(e.get("target")) != node_id]


async def _get_component_template(component_type: str) -> dict[str, Any] | None:
    """Get the template for a component type from the cached components."""
    from langflow.interface.components import get_and_cache_all_types_dict
    from langflow.services.deps import get_settings_service

    all_types = await get_and_cache_all_types_dict(settings_service=get_settings_service())
    for category_data in all_types.values():
        if component_type in category_data:
            return category_data[component_type]
    return None


def _apply_add_node(
    payload: dict[str, Any],
    *,
    node_id: str,
    component_type: str,
    template: dict[str, Any],
    position: dict[str, float],
) -> None:
    """Add a new node to the workflow payload."""
    nodes = _ensure_list(payload.get("nodes", []), name="nodes")

    node_data = copy.deepcopy(template)
    display_name = node_data.get("display_name", component_type)

    new_node = {
        "id": node_id,
        "type": "genericNode",
        "position": position,
        "data": {
            "id": node_id,
            "display_name": display_name,
            "description": node_data.get("description", ""),
            "type": component_type,
            "node": node_data,
        },
        "width": 320,
        "height": 400,
    }
    nodes.append(new_node)


def _apply_add_note(
    payload: dict[str, Any],
    *,
    note_id: str,
    content: str,
    position: dict[str, float],
    background_color: str = "transparent",
    width: int = 324,
    height: int = 324,
) -> None:
    """Add a new note node to the workflow payload.

    Notes are special UI elements (not components) with type 'noteNode'.
    """
    nodes = _ensure_list(payload.get("nodes", []), name="nodes")

    new_note = {
        "id": note_id,
        "type": "noteNode",
        "position": position,
        "data": {
            "id": note_id,
            "node": {
                "description": content,
                "display_name": "",
                "documentation": "",
                "template": {"backgroundColor": background_color},
            },
            "type": "note",
        },
        "width": width,
        "height": height,
        "style": {"width": width, "height": height},
    }
    nodes.append(new_note)


def _apply_update_note(
    payload: dict[str, Any],
    *,
    note_id: str,
    content: str | None = None,
    background_color: str | None = None,
) -> None:
    """Update an existing note node's content or background color.

    Notes store content in 'description' field, not in template like components.
    """
    nodes = _ensure_list(payload.get("nodes", []), name="nodes")
    idx = _find_node_index(nodes, note_id)
    node = _ensure_dict(nodes[idx], name="node")

    if node.get("type") != "noteNode":
        node_type = node.get("type")
        msg = f"Node '{note_id}' is not a note (type: {node_type})"
        raise WorkflowEditError(msg)

    data = _ensure_dict(node.get("data", {}), name="node.data")
    node_inner = _ensure_dict(data.get("node", {}), name="node.data.node")

    if content is not None:
        node_inner["description"] = content

    if background_color is not None:
        template = node_inner.setdefault("template", {})
        template["backgroundColor"] = background_color


async def apply_workflow_patch(
    payload: dict[str, Any],
    patch: dict[str, Any],
    *,
    user_id: UUID,
) -> dict[str, Any]:
    """Apply a high-level patch to a flow payload.

    Patch format:
      { "ops": [ ... ] }

    Supported ops:
      - {"op":"add_node","component_type":"...","position":{"x":0,"y":0}} - returns generated node_id
      - {"op":"add_note","content":"...","position":{"x":0,"y":0},"background_color":"transparent"} - add a sticky note
      - {"op":"update_note","note_id":"...","content":"...","background_color":"..."} - update note content/color
      - {"op":"set_node_template_value","node_id": "...","field":"...","value": ..., "create_if_missing": false}
      - {"op":"add_edge","edge": { ...edgeObject... }}
      - {"op":"remove_edge","edge_id": "..."}
      - {"op":"remove_node","node_id": "..."}
    """
    patch_obj = _ensure_dict(patch, name="patch")
    ops = _ensure_list(patch_obj.get("ops", []), name="ops")
    new_payload = _ensure_dict(payload, name="payload").copy()
    new_payload.setdefault("nodes", [])
    new_payload.setdefault("edges", [])

    added_node_ids: list[str] = []

    for raw_op in ops:
        op = _ensure_dict(raw_op, name="op")
        kind = op.get("op")
        if kind == "add_node":
            component_type = str(op.get("component_type", ""))
            if not component_type:
                msg = "add_node requires 'component_type'"
                raise WorkflowEditError(msg)
            template = await _get_component_template(component_type)
            if not template:
                msg = f"Unknown component type '{component_type}'"
                raise WorkflowEditError(msg)
            position = op.get("position", {"x": 0, "y": 0})
            node_id = _generate_node_id(component_type)
            _apply_add_node(
                new_payload,
                node_id=node_id,
                component_type=component_type,
                template=template,
                position=position,
            )
            added_node_ids.append(node_id)
        elif kind == "add_note":
            note_content = str(op.get("content", ""))
            position = op.get("position", {"x": 0, "y": 0})
            note_background_color = str(op.get("background_color", "transparent"))
            width = int(op.get("width", 324))
            height = int(op.get("height", 324))
            note_id = _generate_note_id()
            _apply_add_note(
                new_payload,
                note_id=note_id,
                content=note_content,
                position=position,
                background_color=note_background_color,
                width=width,
                height=height,
            )
            added_node_ids.append(note_id)
        elif kind == "update_note":
            note_id = str(op.get("note_id", ""))
            if not note_id:
                msg = "update_note requires 'note_id'"
                raise WorkflowEditError(msg)
            update_content = op.get("content")
            update_background_color = op.get("background_color")
            if update_content is None and update_background_color is None:
                msg = "update_note requires 'content' or 'background_color'"
                raise WorkflowEditError(msg)
            _apply_update_note(
                new_payload,
                note_id=note_id,
                content=str(update_content) if update_content is not None else None,
                background_color=str(update_background_color) if update_background_color is not None else None,
            )
        elif kind == "set_node_template_value":
            await _apply_set_node_template_value(
                new_payload,
                node_id=str(op.get("node_id", "")),
                field_name=str(op.get("field", "")),
                value=op.get("value"),
                create_if_missing=bool(op.get("create_if_missing", False)),
                user_id=user_id,
            )
        elif kind == "add_edge":
            edge = _ensure_dict(op.get("edge"), name="edge")
            _apply_add_edge(new_payload, edge=edge)
        elif kind == "remove_edge":
            _apply_remove_edge(new_payload, edge_id=str(op.get("edge_id", "")))
        elif kind == "remove_node":
            _apply_remove_node(new_payload, node_id=str(op.get("node_id", "")))
        else:
            msg = f"Unsupported op '{kind}'"
            raise WorkflowEditError(msg)

    new_payload["_added_node_ids"] = added_node_ids
    return new_payload


@dataclass(frozen=True)
class WorkflowMcpTool:
    name: str
    description: str
    input_schema: dict[str, Any]

    def to_mcp_tool(self) -> types.Tool:
        return types.Tool(name=self.name, description=self.description, inputSchema=self.input_schema)


WORKFLOW_MCP_TOOLS: list[WorkflowMcpTool] = [
    WorkflowMcpTool(
        name="lf_workflow_get",
        description=(
            "Get a Langflow workflow payload (nodes/edges) by flow_id. "
            "Returns optimized structure without source code to save tokens. "
            "Use lf_get_node_code to inspect specific component implementation if needed."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "flow_id": {"type": "string", "description": "UUID of the flow"},
            },
            "required": ["flow_id"],
        },
    ),
    WorkflowMcpTool(
        name="lf_get_node_code",
        description=(
            "Get source code of a specific node/component by node_id. "
            "Use this to inspect component implementation details when needed. "
            "More efficient than loading all components' code at once."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "flow_id": {"type": "string", "description": "UUID of the flow"},
                "node_id": {
                    "type": "string",
                    "description": "ID of the node to get code for (e.g., 'ChatInput-abc123')",
                },
            },
            "required": ["flow_id", "node_id"],
        },
    ),
    WorkflowMcpTool(
        name="lf_workflow_validate",
        description="Validate a Langflow workflow payload (nodes/edges). Returns errors if invalid.",
        input_schema={
            "type": "object",
            "properties": {"data": {"type": "object", "description": "Flow payload"}},
            "required": ["data"],
        },
    ),
    WorkflowMcpTool(
        name="lf_check_workflow",
        description=(
            "Check workflow for issues: disconnected nodes, missing required fields, "
            "type mismatches in edges, and configuration problems. "
            "Returns structured list of issues with suggestions. "
            "ALWAYS call this AFTER making changes to verify workflow correctness."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "flow_id": {"type": "string", "description": "UUID of the flow"},
            },
            "required": ["flow_id"],
        },
    ),
    WorkflowMcpTool(
        name="lf_workflow_patch",
        description=(
            "Apply a high-level patch to a Langflow workflow stored in DB by flow_id. "
            "Supported ops: "
            "add_node (component_type, position), "
            "add_note (content, position, background_color - for sticky notes), "
            "update_note (note_id, content, background_color - update existing note), "
            "set_node_template_value (node_id, field, value), "
            "add_edge (edge object with source, target, sourceHandle, targetHandle), "
            "remove_edge (edge_id), remove_node (node_id). "
            "Returns added_node_ids for add_node/add_note ops."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "flow_id": {"type": "string", "description": "UUID of the flow"},
                "patch": {
                    "type": "object",
                    "description": "Patch object with {ops:[...]}",
                },
                "validate": {"type": "boolean", "description": "Validate the result payload before saving"},
            },
            "required": ["flow_id", "patch"],
        },
    ),
    WorkflowMcpTool(
        name="lf_list_components",
        description=(
            "List available Langflow component types by category. "
            "Use exact category names: input_output, processing, openai, anthropic, google, "
            "agents, helpers, models, tools, data, logic. "
            "Without category, returns all categories with their components."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Exact category name (e.g. 'input_output', 'openai', 'processing', 'agents')",
                },
            },
            "required": [],
        },
    ),
    WorkflowMcpTool(
        name="lf_get_component_info",
        description=(
            "Get detailed information about a specific component type BEFORE adding it. "
            "Returns: description, all input fields (with types, descriptions, options for dropdowns, defaults), "
            "all outputs (with types), and use case recommendations. "
            "ALWAYS use this to understand a component's capabilities before adding it. "
            "Prefer standard components over custom ones - use this tool to find if existing components "
            "can solve the task."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "component_type": {
                    "type": "string",
                    "description": (
                        "Exact component type name (e.g., 'ChatInput', 'Agent', 'OpenAIModel', 'Prompt Template')"
                    ),
                },
            },
            "required": ["component_type"],
        },
    ),
    WorkflowMcpTool(
        name="lf_node_handles",
        description=(
            "Get available input/output handles for nodes in a flow. "
            "Returns outputs (sourceHandle names) and inputs (targetHandle names) for connecting nodes. "
            "Use this before add_edge to find correct handle names."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "flow_id": {"type": "string", "description": "UUID of the flow"},
                "node_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of node IDs to get handles for. If empty, returns handles for all nodes.",
                },
            },
            "required": ["flow_id"],
        },
    ),
    WorkflowMcpTool(
        name="lf_add_custom_component",
        description=(
            "Add a custom Python component to a workflow. "
            "Use this ONLY when no standard component exists for a specific task. "
            "FIRST use lf_get_component_info to check if standard components can solve the task! "
            "Provide Python code that defines a Component class with inputs and outputs."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "flow_id": {"type": "string", "description": "UUID of the flow"},
                "code": {
                    "type": "string",
                    "description": "Python code defining the custom component class",
                },
                "position": {
                    "type": "object",
                    "description": "Position {x, y} for the node on the canvas",
                    "properties": {
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                    },
                },
            },
            "required": ["flow_id", "code"],
        },
    ),
    WorkflowMcpTool(
        name="lf_get_field_options",
        description=(
            "Get available options for a dropdown field on a node. "
            "Use this for dynamic fields like 'model_name' where options depend on other settings. "
            "For example, model list changes based on the selected provider and API key. "
            "Optionally triggers a refresh to get the latest options from external APIs."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "flow_id": {"type": "string", "description": "UUID of the flow"},
                "node_id": {"type": "string", "description": "ID of the node (e.g., 'Agent-abc123')"},
                "field_name": {"type": "string", "description": "Name of the dropdown field (e.g., 'model_name')"},
                "refresh": {
                    "type": "boolean",
                    "description": "If true, triggers update_build_config to fetch latest options (default: true)",
                },
            },
            "required": ["flow_id", "node_id", "field_name"],
        },
    ),
    WorkflowMcpTool(
        name="lf_documentation",
        description=(
            "Access Langflow documentation. Use this to learn about Langflow concepts, components, "
            "data types, deployment, and best practices. "
            "Actions: "
            "'index' - list all documentation categories and pages; "
            "'search' - search documentation by query (e.g., 'how to create custom component'); "
            "'read' - get full content of a specific documentation page by slug or filename. "
            "ALWAYS use this tool when you need detailed information about Langflow features!"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["index", "search", "read"],
                    "description": (
                        "Action to perform: 'index' for listing, 'search' for finding, 'read' for full content"
                    ),
                },
                "query": {
                    "type": "string",
                    "description": "Search query (for 'search' action) or page identifier (for 'read' action)",
                },
                "category": {
                    "type": "string",
                    "description": "Filter by category (optional, for 'index' action)",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of search results (default: 5, for 'search' action)",
                },
            },
            "required": ["action"],
        },
    ),
]


async def call_workflow_tool(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    user_id: UUID,
) -> list[types.TextContent]:
    if tool_name == "lf_workflow_get":
        flow_id = _require_flow_id(arguments)
        flow = await _get_flow_for_user(flow_id=flow_id, user_id=user_id)
        payload = flow.data or {}

        # Always optimize payload to reduce token usage
        optimized_payload = _optimize_workflow_payload(payload, include_code=False)

        return [types.TextContent(type="text", text=_json_dumps(optimized_payload))]

    if tool_name == "lf_get_node_code":
        flow_id = _require_flow_id(arguments)
        node_id = str(arguments.get("node_id", "")).strip()

        if not node_id:
            # If the caller cannot provide node_id (some providers emit empty tool arguments),
            # return code for all nodes that actually have editable source code.
            flow = await _get_flow_for_user(flow_id=flow_id, user_id=user_id)
            payload = flow.data or {}
            nodes = _ensure_list(payload.get("nodes", []), name="nodes")

            candidates: list[dict[str, Any]] = []
            for node in nodes:
                node_id_candidate = str(node.get("id") or "").strip()
                if not node_id_candidate:
                    continue
                node_data = node.get("data", {}) if isinstance(node.get("data"), dict) else {}
                node_inner = node_data.get("node", {}) if isinstance(node_data.get("node"), dict) else {}
                template = node_inner.get("template", {}) if isinstance(node_inner.get("template"), dict) else {}
                code_field = template.get("code")
                if not isinstance(code_field, dict):
                    continue
                code_value = code_field.get("value", "")
                if not isinstance(code_value, str) or not code_value.strip():
                    continue

                max_chars = 6000
                truncated = len(code_value) > max_chars
                code_out = code_value[:max_chars]

                candidates.append(
                    {
                        "node_id": node_id_candidate,
                        "type": node_data.get("type"),
                        "display_name": node_data.get("display_name"),
                        "description": node_inner.get("description", ""),
                        "has_code": True,
                        "code": code_out,
                        "truncated": truncated,
                        "code_info": {
                            "lines": len(code_value.split("\n")) if code_value else 0,
                            "chars": len(code_value) if code_value else 0,
                        },
                    }
                )

            # Keep payload bounded to avoid huge tool outputs
            max_nodes = 5
            candidates = candidates[:max_nodes]

            result = {
                "node_id": None,
                "has_code": len(candidates) > 0,
                "message": (
                    "node_id was not provided. Returning code for nodes that have editable source code. "
                    "If you need a specific node, call lf_workflow_get and pass node_id explicitly."
                ),
                "candidates": candidates,
            }
            return [types.TextContent(type="text", text=_json_dumps(result))]

        flow = await _get_flow_for_user(flow_id=flow_id, user_id=user_id)
        payload = flow.data or {}
        nodes = _ensure_list(payload.get("nodes", []), name="nodes")

        # Find the node
        target_node = None
        for node in nodes:
            if str(node.get("id")) == node_id:
                target_node = node
                break

        if not target_node:
            msg = f"Node '{node_id}' not found in workflow"
            raise WorkflowEditError(msg)

        # Extract code and metadata
        node_data = target_node.get("data", {})
        node_inner = node_data.get("node", {})
        template = node_inner.get("template", {})
        code_field = template.get("code", {})

        if not isinstance(code_field, dict):
            return [
                types.TextContent(
                    type="text",
                    text=_json_dumps(
                        {
                            "node_id": node_id,
                            "type": node_data.get("type"),
                            "display_name": node_data.get("display_name"),
                            "has_code": False,
                            "message": "This component does not have editable source code (it's a built-in component)",
                        }
                    ),
                )
            ]

        code_value = code_field.get("value", "")

        node_code_result = {
            "node_id": node_id,
            "type": node_data.get("type"),
            "display_name": node_data.get("display_name"),
            "description": node_inner.get("description", ""),
            "has_code": True,
            "code": code_value,
            "code_info": {
                "lines": len(code_value.split("\n")) if code_value else 0,
                "chars": len(code_value) if code_value else 0,
            },
        }

        return [types.TextContent(type="text", text=_json_dumps(node_code_result))]

    if tool_name == "lf_workflow_validate":
        data = _ensure_dict(arguments.get("data"), name="data")
        errors = validate_flow_payload(data)
        validation_result = {"ok": len(errors) == 0, "errors": errors}
        return [types.TextContent(type="text", text=_json_dumps(validation_result))]

    if tool_name == "lf_workflow_patch":
        from sqlalchemy.orm.attributes import flag_modified

        flow_id = _require_flow_id(arguments)
        patch = _ensure_dict(arguments.get("patch"), name="patch")
        validate = bool(arguments.get("validate", True))
        async with session_scope() as session:
            flow = await session.get(Flow, flow_id)
            if not flow or flow.user_id != user_id:
                msg = "Flow not found"
                raise WorkflowEditError(msg)
            current = flow.data or {}
            new_payload = await apply_workflow_patch(current, patch, user_id=user_id)
            added_node_ids = new_payload.pop("_added_node_ids", [])
            if validate:
                errors = validate_flow_payload(new_payload)
                if errors:
                    raise WorkflowEditError("Validation failed: " + "; ".join(errors))
            flow.data = new_payload
            flag_modified(flow, "data")  # Force SQLAlchemy to detect JSON change
            flow.updated_at = datetime.now(timezone.utc)
            session.add(flow)
        patch_result = {"ok": True}
        if added_node_ids:
            patch_result["added_node_ids"] = added_node_ids
        return [types.TextContent(type="text", text=_json_dumps(patch_result))]

    if tool_name == "lf_list_components":
        from langflow.interface.components import get_and_cache_all_types_dict
        from langflow.services.deps import get_settings_service

        category_filter = (arguments.get("category") or "").strip()
        all_types = await get_and_cache_all_types_dict(settings_service=get_settings_service())
        components_result: dict[str, Any] = {}

        if category_filter:
            cat_data = all_types.get(category_filter)
            if cat_data and isinstance(cat_data, dict):
                components_result[category_filter] = list(cat_data.keys())
            else:
                available = [k for k in all_types if isinstance(all_types[k], dict) and all_types[k]]
                components_result["error"] = f"Category '{category_filter}' not found"
                components_result["available_categories"] = available
        else:
            for cat_name, cat_data in all_types.items():
                component_names = list(cat_data.keys()) if isinstance(cat_data, dict) else []
                if component_names:
                    components_result[cat_name] = component_names

        return [types.TextContent(type="text", text=_json_dumps(components_result))]

    if tool_name == "lf_node_handles":
        flow_id = _require_flow_id(arguments)
        node_ids_filter = arguments.get("node_ids", [])
        flow = await _get_flow_for_user(flow_id=flow_id, user_id=user_id)
        payload = flow.data or {}
        nodes = payload.get("nodes", [])

        node_handles_result: dict[str, Any] = {}
        for node in nodes:
            node_id = node.get("id", "")
            if node.get("type") == "noteNode":
                continue
            if node_ids_filter and node_id not in node_ids_filter:
                continue

            node_data = node.get("data", {}).get("node", {})
            outputs = node_data.get("outputs", [])
            template = node_data.get("template", {})

            output_handles = [
                {
                    "name": output.get("name"),
                    "types": output.get("types", []),
                }
                for output in outputs
            ]

            input_handles = []
            for field_name, field_def in template.items():
                if not isinstance(field_def, dict):
                    continue
                if field_name.startswith("_"):
                    continue
                if field_def.get("input_types") or field_def.get("type") in [
                    "LanguageModel",
                    "Message",
                    "Data",
                    "Tool",
                    "Embeddings",
                    "Retriever",
                    "Memory",
                    "str",
                    "int",
                    "float",
                    "bool",
                    "dict",
                    "list",
                    "code",
                    "file",
                    "prompt",
                ]:
                    input_handles.append(
                        {
                            "name": field_name,
                            "type": field_def.get("type"),
                            "input_types": field_def.get("input_types"),
                            "required": field_def.get("required", False),
                        }
                    )

            node_handles_result[node_id] = {
                "display_name": node.get("data", {}).get("display_name", node_id),
                "type": node.get("data", {}).get("type", ""),
                "outputs": output_handles,
                "inputs": input_handles,
            }

        return [types.TextContent(type="text", text=_json_dumps(node_handles_result))]

    if tool_name == "lf_add_custom_component":
        from sqlalchemy.orm.attributes import flag_modified

        from langflow.custom import Component, build_custom_component_template

        flow_id = UUID(str(arguments.get("flow_id")))
        code = str(arguments.get("code", ""))
        position = arguments.get("position", {"x": 400, "y": 400})

        if not code.strip():
            msg = "Custom component code is required"
            raise WorkflowEditError(msg)

        try:
            component = Component(_code=code)
            built_frontend_node, _ = build_custom_component_template(component, user_id=user_id)
        except Exception as exc:
            msg = f"Failed to build custom component: {exc!s}"
            raise WorkflowEditError(msg) from exc

        component_type = built_frontend_node.get("display_name", "CustomComponent")
        node_id = _generate_node_id("Custom")

        async with session_scope() as session:
            flow = await session.get(Flow, flow_id)
            if not flow or flow.user_id != user_id:
                msg = "Flow not found"
                raise WorkflowEditError(msg)

            current = flow.data or {}
            nodes = current.setdefault("nodes", [])
            current.setdefault("edges", [])

            new_node = {
                "id": node_id,
                "type": "genericNode",
                "position": position,
                "data": {
                    "id": node_id,
                    "display_name": component_type,
                    "description": built_frontend_node.get("description", ""),
                    "type": component_type,
                    "node": built_frontend_node,
                },
                "width": 320,
                "height": 400,
            }
            nodes.append(new_node)

            errors = validate_flow_payload(current)
            if errors:
                raise WorkflowEditError("Validation failed: " + "; ".join(errors))

            flow.data = current
            flag_modified(flow, "data")
            flow.updated_at = datetime.now(timezone.utc)
            session.add(flow)

        result = {"ok": True, "added_node_id": node_id, "component_type": component_type}
        return [types.TextContent(type="text", text=_json_dumps(result))]

    if tool_name == "lf_check_workflow":
        flow_id = _require_flow_id(arguments)
        flow = await _get_flow_for_user(flow_id=flow_id, user_id=user_id)
        payload = flow.data or {}

        issues = _check_workflow_issues(payload)
        check_workflow_result = {
            "ok": len(issues) == 0,
            "total_issues": len(issues),
            "issues": issues,
        }
        if not issues:
            check_workflow_result["message"] = "Workflow looks good! All nodes are connected and configured correctly."

        return [types.TextContent(type="text", text=_json_dumps(check_workflow_result))]

    if tool_name == "lf_get_component_info":
        from langflow.interface.components import get_and_cache_all_types_dict
        from langflow.services.deps import get_settings_service

        component_type = (arguments.get("component_type") or "").strip()
        if not component_type:
            msg = (
                "component_type is required (e.g., 'ChatInput', 'Agent', 'QueryRouterModel'). "
                "If you only have a workflow node, call lf_workflow_get and use node.data.type."
            )
            raise WorkflowEditError(msg)

        all_types = await get_and_cache_all_types_dict(settings_service=get_settings_service())

        template = None
        found_category = None
        for cat_name, cat_data in all_types.items():
            if isinstance(cat_data, dict) and component_type in cat_data:
                template = cat_data[component_type]
                found_category = cat_name
                break

        if not template:
            available = []
            for cat_data in all_types.values():
                if isinstance(cat_data, dict):
                    available.extend(list(cat_data.keys()))
            msg = (
                f"Component type '{component_type}' not found. "
                f"Available types include: {', '.join(sorted(available)[:20])}..."
            )
            raise WorkflowEditError(msg)

        component_info = _extract_component_info(template, component_type, found_category or "")
        return [types.TextContent(type="text", text=_json_dumps(component_info))]

    if tool_name == "lf_get_field_options":
        from sqlalchemy.orm.attributes import flag_modified

        flow_id = _require_flow_id(arguments)
        node_id = str(arguments.get("node_id", "")).strip()
        field_name = str(arguments.get("field_name", "")).strip()
        do_refresh = arguments.get("refresh", True)

        if not node_id:
            msg = (
                "node_id is required. "
                "Call lf_workflow_get with the same flow_id, find the target node in 'nodes', "
                "and pass its 'id' as node_id."
            )
            raise WorkflowEditError(msg)
        if not field_name:
            msg = (
                "field_name is required (template field key, e.g., 'model_name'). "
                "Use lf_get_component_info(component_type=...) or inspect the node template via lf_workflow_get."
            )
            raise WorkflowEditError(msg)

        # Fields that trigger dynamic model updates
        model_dynamic_fields = {"api_key", "model", "model_name", "base_url"}

        async with session_scope() as session:
            flow = await session.get(Flow, flow_id)
            if not flow or flow.user_id != user_id:
                msg = "Flow not found"
                raise WorkflowEditError(msg)

            payload = flow.data or {}
            nodes = _ensure_list(payload.get("nodes", []), name="nodes")

            idx = _find_node_index(nodes, node_id)
            node = _ensure_dict(nodes[idx], name="node")
            data = _ensure_dict(node.get("data", {}), name="node.data")
            node_inner = _ensure_dict(data.get("node", {}), name="node.data.node")
            template = _ensure_dict(node_inner.get("template", {}), name="node.data.node.template")

            if field_name not in template:
                available = [k for k in template if not k.startswith("_") and k != "code"]
                msg = f"Field '{field_name}' not found on node '{node_id}'. Available fields: {', '.join(available)}"
                raise WorkflowEditError(msg)

            field = template[field_name]
            if not isinstance(field, dict):
                msg = f"Field '{field_name}' has unexpected format"
                raise WorkflowEditError(msg)

            # Trigger refresh if requested
            # For model_name, we need to trigger via api_key field to fetch from API
            if do_refresh:
                trigger_field = field_name
                trigger_value = field.get("value")

                # For model_name, trigger via api_key to fetch models from provider API
                if field_name == "model_name" and "api_key" in template:
                    trigger_field = "api_key"
                    api_key_field = template.get("api_key", {})
                    trigger_value = api_key_field.get("value", "")

                # Check if this field or related field can trigger dynamic update
                can_refresh = (
                    field.get("real_time_refresh")
                    or field_name in model_dynamic_fields
                    or trigger_field in model_dynamic_fields
                )

                if can_refresh and trigger_value:
                    await _apply_dynamic_build_config_update(
                        template=template,
                        field_name=trigger_field,
                        field_value=trigger_value,
                        user_id=user_id,
                    )
                    # Save the updated template back to DB
                    flow.data = payload
                    flag_modified(flow, "data")
                    flow.updated_at = datetime.now(timezone.utc)
                    session.add(flow)
                    # Re-read the field after refresh
                    field = template.get(field_name, {})

            # Build result with field info
            field_options_result: dict[str, Any] = {
                "node_id": node_id,
                "field_name": field_name,
                "display_name": field.get("display_name", field_name),
                "type": field.get("type"),
                "current_value": field.get("value"),
            }

            # Include options if available
            options = field.get("options")
            if options:
                field_options_result["options"] = options
                field_options_result["options_count"] = len(options) if isinstance(options, list) else 0
            else:
                field_options_result["options"] = []
                field_options_result["options_count"] = 0
                field_options_result["note"] = (
                    "No options available. For dynamic fields like model_name, "
                    "ensure the API key is set and the provider is correctly configured."
                )

            # Include any external options (like "connect_other_models")
            external_options = field.get("external_options")
            if external_options:
                field_options_result["external_options"] = external_options

            return [types.TextContent(type="text", text=_json_dumps(field_options_result))]

    if tool_name == "lf_documentation":
        from langflow.api.v1.documentation import (
            get_category_description,
            get_documentation_index,
            get_documentation_page,
            search_documentation,
        )

        action = str(arguments.get("action", "")).strip().lower()
        if not action:
            msg = "action is required (one of: 'index', 'search', 'read')"
            raise WorkflowEditError(msg)

        if action == "index":
            category_filter = (arguments.get("category") or "").strip().lower()
            full_index = get_documentation_index()

            if category_filter:
                # Filter to specific category
                if category_filter in full_index:
                    result = {
                        "category": category_filter,
                        "description": get_category_description(category_filter),
                        "pages": full_index[category_filter],
                    }
                else:
                    available = list(full_index.keys())
                    msg = (
                        f"Category '{category_filter}' not found. Available categories: {', '.join(sorted(available))}"
                    )
                    raise WorkflowEditError(msg)
            else:
                # Return full index with category descriptions
                result = {
                    "categories": {
                        cat: {
                            "description": get_category_description(cat),
                            "page_count": len(pages),
                            "pages": pages,
                        }
                        for cat, pages in full_index.items()
                    },
                    "total_pages": sum(len(pages) for pages in full_index.values()),
                }

            return [types.TextContent(type="text", text=_json_dumps(result))]

        if action == "search":
            query = (arguments.get("query") or "").strip()
            if not query:
                msg = "query is required for search action"
                raise WorkflowEditError(msg)

            max_results = int(arguments.get("max_results", 5))
            max_results = min(max(1, max_results), 20)  # Clamp between 1 and 20

            results = search_documentation(query, max_results=max_results)

            if not results:
                return [
                    types.TextContent(
                        type="text",
                        text=_json_dumps(
                            {
                                "query": query,
                                "results": [],
                                "message": f"No documentation found for '{query}'. Try different keywords.",
                            }
                        ),
                    )
                ]

            return [
                types.TextContent(
                    type="text",
                    text=_json_dumps(
                        {
                            "query": query,
                            "results_count": len(results),
                            "results": results,
                        }
                    ),
                )
            ]

        if action == "read":
            identifier = (arguments.get("query") or "").strip()
            if not identifier:
                msg = "query (page slug or filename) is required for read action"
                raise WorkflowEditError(msg)

            page = get_documentation_page(identifier)
            if not page:
                msg = (
                    f"Documentation page '{identifier}' not found. "
                    "Use 'index' action to list available pages or 'search' to find by topic."
                )
                raise WorkflowEditError(msg)

            return [types.TextContent(type="text", text=_json_dumps(page))]

        msg = f"Unknown action '{action}'. Use 'index', 'search', or 'read'."
        raise WorkflowEditError(msg)

    msg = f"Unknown workflow tool '{tool_name}'"
    raise WorkflowEditError(msg)
