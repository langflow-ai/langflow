"""
Output node definitions for the enhanced node registry.

This module contains definitions for output nodes such as Display, File Output, etc.
"""

from typing import Dict
from ..node_registry import (
    EnhancedNodeType,
    InputField,
    OutputField,
    ConnectionFormat,
)

# Registry of output nodes
OUTPUT_NODES: Dict[str, EnhancedNodeType] = {}

# Display Output node
display_output = EnhancedNodeType(
    id="Display",
    displayName="Display",
    description="Displays text output in the UI",
    category="Outputs",
    inputs={
        "content": InputField(
            type=["str", "Message"],
            displayName="Content",
            required=True,
            connectionFormat=ConnectionFormat(
                fieldName="content",
                handleFormat="{\"fieldName\": \"content\", \"id\": \"NODE_ID\", \"inputTypes\": [\"str\", \"Message\"], \"type\": \"str\"}"
            )
        )
    }
)
OUTPUT_NODES[display_output.id] = display_output

# FileOutput node
file_output = EnhancedNodeType(
    id="FileOutput",
    displayName="File Output",
    description="Saves content to a file",
    category="Outputs",
    inputs={
        "content": InputField(
            type=["str", "Message", "Document"],
            displayName="Content",
            required=True,
            connectionFormat=ConnectionFormat(
                fieldName="content",
                handleFormat="{\"fieldName\": \"content\", \"id\": \"NODE_ID\", \"inputTypes\": [\"str\", \"Message\", \"Document\"], \"type\": \"str\"}"
            )
        ),
        "filename": InputField(
            type=["str"],
            displayName="Filename",
            required=True,
            connectionFormat=ConnectionFormat(
                fieldName="filename",
                handleFormat="{\"fieldName\": \"filename\", \"id\": \"NODE_ID\", \"inputTypes\": [\"str\"], \"type\": \"str\"}"
            )
        )
    }
)
OUTPUT_NODES[file_output.id] = file_output

# APIOutput node
api_output = EnhancedNodeType(
    id="APIOutput",
    displayName="API Output",
    description="Sends data to an API endpoint",
    category="Outputs",
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
        "data": InputField(
            type=["str", "Message", "Document", "JSON"],
            displayName="Data",
            required=True,
            connectionFormat=ConnectionFormat(
                fieldName="data",
                handleFormat="{\"fieldName\": \"data\", \"id\": \"NODE_ID\", \"inputTypes\": [\"str\", \"Message\", \"Document\", \"JSON\"], \"type\": \"str\"}"
            )
        )
    },
    outputs={
        "response": OutputField(
            type=["APIResponse"],
            displayName="Response",
            connectionFormat=ConnectionFormat(
                fieldName="response",
                handleFormat="{\"dataType\": \"APIOutput\", \"id\": \"NODE_ID\", \"name\": \"response\", \"output_types\": [\"APIResponse\"]}"
            )
        )
    }
)
OUTPUT_NODES[api_output.id] = api_output

# ChatDisplay node
chat_display = EnhancedNodeType(
    id="ChatDisplay",
    displayName="Chat Display",
    description="Displays chat messages in the UI",
    category="Outputs",
    inputs={
        "chat_history": InputField(
            type=["ChatHistory", "Message"],
            displayName="Chat History",
            required=True,
            connectionFormat=ConnectionFormat(
                fieldName="chat_history",
                handleFormat="{\"fieldName\": \"chat_history\", \"id\": \"NODE_ID\", \"inputTypes\": [\"ChatHistory\", \"Message\"], \"type\": \"str\"}"
            )
        )
    }
)
OUTPUT_NODES[chat_display.id] = chat_display
