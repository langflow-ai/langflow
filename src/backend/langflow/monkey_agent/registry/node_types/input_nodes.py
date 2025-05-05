"""
Input node definitions for the enhanced node registry.

This module contains definitions for input nodes such as TextInput, ChatInput, etc.
"""

from typing import Dict
from ..node_registry import (
    EnhancedNodeType,
    InputField,
    OutputField,
    ConnectionFormat,
    create_input_node,
)

# Registry of input nodes
INPUT_NODES: Dict[str, EnhancedNodeType] = {}

# TextInput node
text_input = create_input_node(
    node_id="TextInput",
    display_name="Text Input",
    description="A simple text input node",
    output_field_name="text",
    output_types=["Message"],
    output_display_name="Text",
)
INPUT_NODES[text_input.id] = text_input

# ChatInput node
chat_input = create_input_node(
    node_id="ChatInput",
    display_name="Chat Input",
    description="An input for chat messages",
    output_field_name="chat_history",
    output_types=["ChatHistory"],
    output_display_name="Chat History",
)
INPUT_NODES[chat_input.id] = chat_input

# Document Input node
document_input = create_input_node(
    node_id="DocumentInput",
    display_name="Document Input",
    description="Input for document content",
    output_field_name="document",
    output_types=["Document"],
    output_display_name="Document",
)
INPUT_NODES[document_input.id] = document_input

# FileInput node
file_input = EnhancedNodeType(
    id="FileInput",
    displayName="File Input",
    description="Input for uploading files",
    category="Inputs",
    outputs={
        "file": OutputField(
            type=["File", "Blob"],
            displayName="File",
            connectionFormat=ConnectionFormat(
                fieldName="file",
                handleFormat="{\"dataType\": \"FileInput\", \"id\": \"NODE_ID\", \"name\": \"file\", \"output_types\": [\"File\", \"Blob\"]}"
            )
        )
    }
)
INPUT_NODES[file_input.id] = file_input

# APIInput node
api_input = EnhancedNodeType(
    id="APIInput",
    displayName="API Input",
    description="Input for API requests",
    category="Inputs",
    inputs={
        "url": InputField(
            type=["str"],
            displayName="URL",
            required=True,
            connectionFormat=ConnectionFormat(
                fieldName="url",
                handleFormat="{\"fieldName\": \"url\", \"id\": \"NODE_ID\", \"inputTypes\": [\"str\"], \"type\": \"str\"}"
            )
        ),
        "method": InputField(
            type=["str"],
            displayName="Method",
            required=True,
            connectionFormat=ConnectionFormat(
                fieldName="method",
                handleFormat="{\"fieldName\": \"method\", \"id\": \"NODE_ID\", \"inputTypes\": [\"str\"], \"type\": \"str\"}"
            )
        )
    },
    outputs={
        "response": OutputField(
            type=["APIResponse"],
            displayName="Response",
            connectionFormat=ConnectionFormat(
                fieldName="response",
                handleFormat="{\"dataType\": \"APIInput\", \"id\": \"NODE_ID\", \"name\": \"response\", \"output_types\": [\"APIResponse\"]}"
            )
        )
    }
)
