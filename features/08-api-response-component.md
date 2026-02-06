# Feature 8: API Response Component

## Summary

Adds two new I/O components for API-oriented workflows:

1. **APIResponseComponent** (`APIResponse`): Provides clean, stateless API responses with minimal JSON structure. Accepts Data, DataFrame, or Message inputs and wraps them in a standardized output envelope with metadata (flow_id, timestamp, duration, status).

2. **JSONInputComponent** (`JSONInput`): Receives and destructures HTTP request JSON payloads into individual outputs (Method, Headers, Body, Query Params, Path Params, URL). Supports both manual JSON input for testing and runtime injection via `set_request_data()`.

The components are registered as `InterfaceComponentTypes` in the graph schema, making them recognized as input/output components by the flow execution engine.

## Dependencies

- `fastapi.encoders` (for `jsonable_encoder` in APIResponseComponent)
- `lfx.base.io.text.TextComponent` base class
- Existing `lfx.schema` types (Data, DataFrame, Message)

## Implementation Notes

- `TextOutputComponent` was removed from the `input_output` module exports (replaced by `APIResponseComponent`).
- Both components are added to `InterfaceComponentTypes` enum and the `INPUT_COMPONENTS` / `OUTPUT_COMPONENTS` lists in `graph/schema.py`.
- `APIResponseComponent` is marked as `beta = True`.
- `JSONInputComponent` has a `set_request_data()` method for API endpoint integration, allowing the actual HTTP request data to be injected at runtime.

---

## File Diffs

### `src/lfx/src/lfx/components/input_output/api_response.py` (new)

```diff
diff --git a/src/lfx/src/lfx/components/input_output/api_response.py b/src/lfx/src/lfx/components/input_output/api_response.py
new file mode 100644
index 0000000000..df608146e9
--- /dev/null
+++ b/src/lfx/src/lfx/components/input_output/api_response.py
@@ -0,0 +1,72 @@
+from fastapi.encoders import jsonable_encoder
+
+from lfx.base.io.text import TextComponent
+from lfx.io import HandleInput, Output
+from lfx.schema.data import Data
+from lfx.schema.dataframe import DataFrame
+from lfx.schema.message import Message
+
+
+class APIResponseComponent(TextComponent):
+    display_name = "API Response"
+    description = "Provides clean, stateless API responses with minimal JSON structure."
+    icon = "code-xml"
+    name = "APIResponse"
+    beta = True
+
+    inputs = [
+        HandleInput(
+            name="input_value",
+            display_name="Inputs",
+            info="Data to be passed as output.",
+            input_types=["Data", "DataFrame", "Message"],
+            required=True,
+        ),
+    ]
+    outputs = [
+        Output(display_name="Response", name="output", method="output_response"),
+    ]
+
+    def _convert_input_to_output(self):
+        """Convert input to appropriate output format based on type."""
+        if isinstance(self.input_value, str):
+            return {"text": self.input_value, "output_type": "text"}
+        if isinstance(self.input_value, Message):
+            return {"text": self.input_value.text, "output_type": "message"}
+        if isinstance(self.input_value, Data):
+            # Convert Data to JSON dict
+            serializable_data = jsonable_encoder(self.input_value.data)
+            return {"data": serializable_data, "output_type": "data"}
+        if isinstance(self.input_value, DataFrame):
+            # Convert DataFrame to list of records
+            return {"records": self.input_value.to_dict("records"), "output_type": "dataframe"}
+        # Fallback to string conversion
+        return {"value": str(self.input_value), "output_type": "unknown"}
+
+    def output_response(self) -> Message:
+        # Create a minimal response structure
+        import json
+        import time
+        from datetime import datetime, timezone
+
+        start_time = time.time()
+
+        # Convert input to appropriate output format
+        output_data = self._convert_input_to_output()
+
+        # Create the minimal output structure
+        minimal_output = {
+            "output": output_data,
+            "metadata": {
+                "flow_id": str(self.graph.flow_id) if hasattr(self, "graph") and self.graph.flow_id else None,
+                "timestamp": datetime.now(timezone.utc).isoformat(),
+                "duration_ms": int((time.time() - start_time) * 1000),
+                "status": "complete",
+                "error": False,
+            },
+        }
+
+        # Return as JSON string in the Message to maintain structure
+        message = Message(text=json.dumps(minimal_output))
+        self.status = str(self.input_value)
+        return message
```

### `src/lfx/src/lfx/components/input_output/request_payload.py` (new)

```diff
diff --git a/src/lfx/src/lfx/components/input_output/request_payload.py b/src/lfx/src/lfx/components/input_output/request_payload.py
new file mode 100644
index 0000000000..6c411cabba
--- /dev/null
+++ b/src/lfx/src/lfx/components/input_output/request_payload.py
@@ -0,0 +1,94 @@
+import json
+
+from lfx.base.io.text import TextComponent
+from lfx.io import MultilineInput, Output
+from lfx.schema.data import Data
+from lfx.schema.message import Message
+
+
+class JSONInputComponent(TextComponent):
+    display_name = "JSON Input"
+    description = "Receives and destructures an HTTP request JSON payload."
+    icon = "braces"
+    name = "JSONInput"
+
+    inputs = [
+        MultilineInput(
+            name="payload",
+            display_name="Payload",
+            info="Manual JSON payload for testing (will be overridden by actual HTTP request when used via API)",
+            value=(
+                '{\n  "method": "POST",\n  "headers": {"Content-Type": "application/json"},'
+                '\n  "body": {"name": "test", "value": 123},\n  "query": {"page": "1"},'
+                '\n  "path": {"id": "456"},\n  "url": "/api/test/456"\n}'
+            ),
+            advanced=False,
+        ),
+    ]
+
+    outputs = [
+        Output(display_name="Method", name="method", method="get_method"),
+        Output(display_name="Headers", name="headers", method="get_headers"),
+        Output(display_name="Body", name="body", method="get_body"),
+        Output(display_name="Query Params", name="query", method="get_query"),
+        Output(display_name="Path Params", name="path", method="get_path"),
+        Output(display_name="URL", name="url", method="get_url"),
+    ]
+
+    def __init__(self, *args, **kwargs):
+        super().__init__(*args, **kwargs)
+        # These will be populated by the API endpoint
+        self.request_data = None
+
+    def set_request_data(self, request_data: dict):
+        """Called by the API endpoint to inject request data."""
+        self.request_data = request_data
+
+    def _get_payload_data(self) -> dict:
+        """Get payload data from either API injection or manual input."""
+        if self.request_data is not None:
+            # Use injected data from API endpoint
+            return self.request_data
+
+        try:
+            # Parse manual payload input for testing
+            payload_text = getattr(self, "payload", "{}")
+            return json.loads(payload_text)
+        except (json.JSONDecodeError, AttributeError):
+            # Fallback to default values
+            return {"method": "GET", "headers": {}, "body": {}, "query": {}, "path": {}, "url": "/"}
+
+    def get_method(self) -> Message:
+        """Returns the HTTP method as a Message."""
+        data = self._get_payload_data()
+        return Message(text=data.get("method", "GET"))
+
+    def get_headers(self) -> Data:
+        """Returns request headers as Data."""
+        data = self._get_payload_data()
+        headers = data.get("headers", {})
+        return Data(data=headers)
+
+    def get_body(self) -> Data:
+        """Returns request body as Data."""
+        data = self._get_payload_data()
+        body = data.get("body", {})
+        return Data(data=body)
+
+    def get_query(self) -> Data:
+        """Returns query parameters as Data."""
+        data = self._get_payload_data()
+        query = data.get("query", {})
+        return Data(data=query)
+
+    def get_path(self) -> Data:
+        """Returns path parameters as Data."""
+        data = self._get_payload_data()
+        path = data.get("path", {})
+        return Data(data=path)
+
+    def get_url(self) -> Message:
+        """Returns the request URL as a Message."""
+        data = self._get_payload_data()
+        url = data.get("url", "/")
+        return Message(text=url)
```

### `src/lfx/src/lfx/components/input_output/__init__.py` (modified)

```diff
diff --git a/src/lfx/src/lfx/components/input_output/__init__.py b/src/lfx/src/lfx/components/input_output/__init__.py
index eba91e1f9b..4e0dc91ce5 100644
--- a/src/lfx/src/lfx/components/input_output/__init__.py
+++ b/src/lfx/src/lfx/components/input_output/__init__.py
@@ -5,21 +5,30 @@ from typing import TYPE_CHECKING, Any
 from lfx.components._importing import import_mod

 if TYPE_CHECKING:
+    from lfx.components.input_output.api_response import APIResponseComponent
     from lfx.components.input_output.chat import ChatInput
     from lfx.components.input_output.chat_output import ChatOutput
+    from lfx.components.input_output.request_payload import JSONInputComponent
     from lfx.components.input_output.text import TextInputComponent
-    from lfx.components.input_output.text_output import TextOutputComponent
     from lfx.components.input_output.webhook import WebhookComponent

 _dynamic_imports = {
     "ChatInput": "chat",
     "ChatOutput": "chat_output",
+    "APIResponseComponent": "api_response",
+    "JSONInputComponent": "request_payload",
     "TextInputComponent": "text",
-    "TextOutputComponent": "text_output",
     "WebhookComponent": "webhook",
 }

-__all__ = ["ChatInput", "ChatOutput", "TextInputComponent", "TextOutputComponent", "WebhookComponent"]
+__all__ = [
+    "APIResponseComponent",
+    "ChatInput",
+    "ChatOutput",
+    "JSONInputComponent",
+    "TextInputComponent",
+    "WebhookComponent",
+]


 def __getattr__(attr_name: str) -> Any:
```

### `src/lfx/src/lfx/graph/schema.py` (modified)

```diff
diff --git a/src/lfx/src/lfx/graph/schema.py b/src/lfx/src/lfx/graph/schema.py
index 38c6610715..1fae309686 100644
--- a/src/lfx/src/lfx/graph/schema.py
+++ b/src/lfx/src/lfx/graph/schema.py
@@ -52,6 +52,8 @@ class InterfaceComponentTypes(str, Enum, metaclass=ContainsEnumMeta):
     ChatOutput = "ChatOutput"
     TextInput = "TextInput"
     TextOutput = "TextOutput"
+    APIResponse = "APIResponse"
+    JSONInput = "JSONInput"
     DataOutput = "DataOutput"
     WebhookInput = "Webhook"

@@ -62,11 +64,13 @@ INPUT_COMPONENTS = [
     InterfaceComponentTypes.ChatInput,
     InterfaceComponentTypes.WebhookInput,
     InterfaceComponentTypes.TextInput,
+    InterfaceComponentTypes.JSONInput,
 ]
 OUTPUT_COMPONENTS = [
     InterfaceComponentTypes.ChatOutput,
     InterfaceComponentTypes.DataOutput,
     InterfaceComponentTypes.TextOutput,
+    InterfaceComponentTypes.APIResponse,
 ]
```
