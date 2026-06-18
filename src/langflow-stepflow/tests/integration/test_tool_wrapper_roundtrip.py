"""Integration test: tool wrapper producer -> consumer roundtrip.

``component_tool_executor`` (the producer) stores a tool-mode component as a blob
and emits a tool wrapper; ``ToolWrapperInputHandler`` (the consumer) resolves that
same blob and builds a tool that executes the real component. This proves the
blob-shape contract between the two ends end-to-end, with a real component but no
LLM (a full agent-driven tool call needs a live model and is out of scope here).
"""

from __future__ import annotations

import json

import pytest
from tests.helpers.tool_components import InMemoryContext, simple_component_node_info

from langflow_stepflow.worker.component_tool import component_tool_executor
from langflow_stepflow.worker.handlers.tool_wrapper import ToolWrapperInputHandler

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_component_tool_to_execution_roundtrip():
    context = InMemoryContext()
    node_info = simple_component_node_info()

    # Producer: component_tool stores the component blob and builds the wrapper.
    produced = await component_tool_executor(
        {
            "code": node_info,
            "inputs": {},
            "component_type": "SimpleTestComponent",
            "session_id": "session_roundtrip",
        },
        context,
    )
    wrapper = produced["result"]
    assert wrapper["__tool_wrapper__"] is True
    assert "code_blob_id" in wrapper
    # text_input is tool_mode=True, so the producer exposes it as a tool param.
    assert "text_input" in wrapper["tool_input_schema"]["properties"]

    # Consumer: the handler resolves the same blob and builds an executing tool.
    handler = ToolWrapperInputHandler()
    prepared = await handler.prepare({"tools": (wrapper, {})}, context)
    tool = prepared["tools"]

    output = await tool.ainvoke({"text_input": "roundtrip"})

    assert "Processed: roundtrip" in json.dumps(output, default=str)
