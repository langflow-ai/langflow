"""Shared helpers for tool-wrapper tests.

A real (non-mock) in-memory Stepflow context and a real, executable component
definition in the shape ``component_tool`` stores as the tool blob.
"""

from typing import Any


class InMemoryContext:
    """Minimal in-memory StepflowContext stand-in (a real object, not a mock).

    ``put_blob`` stores and returns a stable id; ``get_blob`` reads it back.
    Enough for the handler to resolve a tool's component code the way the worker
    does at runtime.
    """

    def __init__(self) -> None:
        self._blobs: dict[str, Any] = {}
        self._counter = 0

    async def put_blob(self, data: Any, *_args: Any, **_kwargs: Any) -> str:
        self._counter += 1
        blob_id = f"blob_{self._counter}"
        self._blobs[blob_id] = data
        return blob_id

    async def get_blob(self, blob_id: str) -> Any:
        return self._blobs[blob_id]


SIMPLE_COMPONENT_CODE = """
from langflow.custom.custom_component.component import Component
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message


class SimpleTestComponent(Component):
    display_name = "Simple Test"
    description = "A simple test component"

    inputs = [
        MessageTextInput(name="text_input", display_name="Text Input", info="Text input for testing")
    ]

    outputs = [
        Output(display_name="Output", name="result", method="process_text")
    ]

    async def process_text(self) -> Message:
        input_text = self.text_input or "No input provided"
        return Message(text=f"Processed: {input_text}", sender="SimpleTestComponent")
"""


def simple_component_node_info() -> dict[str, Any]:
    """Raw component definition as stored in the tool blob by ``component_tool``.

    This is ``node["data"]["node"]``: the Python source under ``template.code.value``
    plus the declared outputs.
    """
    return {
        "template": {
            "code": {"value": SIMPLE_COMPONENT_CODE},
            "text_input": {
                "type": "str",
                "value": "",
                "info": "Text input for testing",
                "required": False,
                "tool_mode": True,
            },
        },
        "outputs": [{"name": "result", "method": "process_text", "types": ["Message"]}],
        "display_name": "Simple Test",
        "description": "A simple test component",
        "base_classes": ["Message"],
    }


def make_real_tool_wrapper(
    blob_id: str,
    *,
    name: str = "simple_test",
    description: str = "Runs the simple test component",
    static_inputs: dict[str, Any] | None = None,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a tool wrapper backed by a real component blob.

    ``properties`` defaults to exposing ``text_input`` as the single tool param;
    pass ``{}`` to expose no tool params (so ``static_inputs`` drive the component).
    """
    if properties is None:
        properties = {"text_input": {"type": "string", "default": ""}}
    return {
        "__tool_wrapper__": True,
        "code_blob_id": blob_id,
        "static_inputs": static_inputs or {},
        "component_type": "SimpleTestComponent",
        "tool_metadata": {"name": name, "description": description},
        "tool_input_schema": {"properties": properties},
        "session_id": "test_session",
    }
