"""
Prompt node definitions for the enhanced node registry.

This module contains definitions for prompt nodes such as PromptTemplate,
ChatPromptTemplate, etc.
"""

from typing import Dict
from ..node_registry import (
    EnhancedNodeType,
    InputField,
    OutputField,
    ConnectionFormat,
)

# Registry of prompt nodes
PROMPT_NODES: Dict[str, EnhancedNodeType] = {}

# PromptTemplate node
prompt_template = EnhancedNodeType(
    id="PromptTemplate",
    displayName="Prompt Template",
    description="A template for generating prompts",
    category="Prompts",
    inputs={
        "template": InputField(
            type=["str"],
            displayName="Template",
            required=True,
            connectionFormat=ConnectionFormat(
                fieldName="template",
                handleFormat="{\"fieldName\": \"template\", \"id\": \"NODE_ID\", \"inputTypes\": [\"str\"], \"type\": \"str\"}"
            )
        ),
        "variables": InputField(
            type=["JSON", "Dict"],
            displayName="Variables",
            required=False,
            connectionFormat=ConnectionFormat(
                fieldName="variables",
                handleFormat="{\"fieldName\": \"variables\", \"id\": \"NODE_ID\", \"inputTypes\": [\"JSON\", \"Dict\"], \"type\": \"dict\"}"
            )
        )
    },
    outputs={
        "prompt": OutputField(
            type=["PromptValue", "str"],
            displayName="Prompt",
            connectionFormat=ConnectionFormat(
                fieldName="prompt",
                handleFormat="{\"dataType\": \"PromptTemplate\", \"id\": \"NODE_ID\", \"name\": \"prompt\", \"output_types\": [\"PromptValue\", \"str\"]}"
            )
        )
    }
)
PROMPT_NODES[prompt_template.id] = prompt_template

# ChatPromptTemplate node
chat_prompt_template = EnhancedNodeType(
    id="ChatPromptTemplate",
    displayName="Chat Prompt Template",
    description="A template for generating chat prompts",
    category="Prompts",
    inputs={
        "system_message": InputField(
            type=["str"],
            displayName="System Message",
            required=False,
            connectionFormat=ConnectionFormat(
                fieldName="system_message",
                handleFormat="{\"fieldName\": \"system_message\", \"id\": \"NODE_ID\", \"inputTypes\": [\"str\"], \"type\": \"str\"}"
            )
        ),
        "human_message": InputField(
            type=["str"],
            displayName="Human Message",
            required=True,
            connectionFormat=ConnectionFormat(
                fieldName="human_message",
                handleFormat="{\"fieldName\": \"human_message\", \"id\": \"NODE_ID\", \"inputTypes\": [\"str\"], \"type\": \"str\"}"
            )
        ),
        "chat_history": InputField(
            type=["ChatHistory"],
            displayName="Chat History",
            required=False,
            connectionFormat=ConnectionFormat(
                fieldName="chat_history",
                handleFormat="{\"fieldName\": \"chat_history\", \"id\": \"NODE_ID\", \"inputTypes\": [\"ChatHistory\"], \"type\": \"list\"}"
            )
        )
    },
    outputs={
        "prompt": OutputField(
            type=["ChatPromptValue", "PromptValue"],
            displayName="Prompt",
            connectionFormat=ConnectionFormat(
                fieldName="prompt",
                handleFormat="{\"dataType\": \"ChatPromptTemplate\", \"id\": \"NODE_ID\", \"name\": \"prompt\", \"output_types\": [\"ChatPromptValue\", \"PromptValue\"]}"
            )
        )
    }
)
PROMPT_NODES[chat_prompt_template.id] = chat_prompt_template

# FewShotPromptTemplate node
few_shot_template = EnhancedNodeType(
    id="FewShotPromptTemplate",
    displayName="Few-Shot Prompt Template",
    description="A template for generating few-shot prompts",
    category="Prompts",
    inputs={
        "prefix": InputField(
            type=["str"],
            displayName="Prefix",
            required=False,
            connectionFormat=ConnectionFormat(
                fieldName="prefix",
                handleFormat="{\"fieldName\": \"prefix\", \"id\": \"NODE_ID\", \"inputTypes\": [\"str\"], \"type\": \"str\"}"
            )
        ),
        "examples": InputField(
            type=["List", "JSON"],
            displayName="Examples",
            required=True,
            connectionFormat=ConnectionFormat(
                fieldName="examples",
                handleFormat="{\"fieldName\": \"examples\", \"id\": \"NODE_ID\", \"inputTypes\": [\"List\", \"JSON\"], \"type\": \"list\"}"
            )
        ),
        "suffix": InputField(
            type=["str"],
            displayName="Suffix",
            required=False,
            connectionFormat=ConnectionFormat(
                fieldName="suffix",
                handleFormat="{\"fieldName\": \"suffix\", \"id\": \"NODE_ID\", \"inputTypes\": [\"str\"], \"type\": \"str\"}"
            )
        ),
        "input_variables": InputField(
            type=["List", "JSON"],
            displayName="Input Variables",
            required=True,
            connectionFormat=ConnectionFormat(
                fieldName="input_variables",
                handleFormat="{\"fieldName\": \"input_variables\", \"id\": \"NODE_ID\", \"inputTypes\": [\"List\", \"JSON\"], \"type\": \"list\"}"
            )
        )
    },
    outputs={
        "prompt": OutputField(
            type=["PromptValue", "str"],
            displayName="Prompt",
            connectionFormat=ConnectionFormat(
                fieldName="prompt",
                handleFormat="{\"dataType\": \"FewShotPromptTemplate\", \"id\": \"NODE_ID\", \"name\": \"prompt\", \"output_types\": [\"PromptValue\", \"str\"]}"
            )
        )
    }
)
PROMPT_NODES[few_shot_template.id] = few_shot_template
