## LLM
from typing import Any

from langchain import llms
from langchain.llms.openai import OpenAIChat

llm_type_to_cls_dict = llms.type_to_cls_dict
llm_type_to_cls_dict["openai-chat"] = OpenAIChat


## Memory

# from langchain.memory.buffer_window import ConversationBufferWindowMemory
# from langchain.memory.chat_memory import ChatMessageHistory
# from langchain.memory.combined import CombinedMemory
# from langchain.memory.entity import ConversationEntityMemory
# from langchain.memory.kg import ConversationKGMemory
# from langchain.memory.readonly import ReadOnlySharedMemory
# from langchain.memory.simple import SimpleMemory
# from langchain.memory.summary import ConversationSummaryMemory
# from langchain.memory.summary_buffer import ConversationSummaryBufferMemory

memory_type_to_cls_dict: dict[str, Any] = {
    # "CombinedMemory": CombinedMemory,
    # "ConversationBufferWindowMemory": ConversationBufferWindowMemory,
    # "ConversationBufferMemory": ConversationBufferMemory,
    # "SimpleMemory": SimpleMemory,
    # "ConversationSummaryBufferMemory": ConversationSummaryBufferMemory,
    # "ConversationKGMemory": ConversationKGMemory,
    # "ConversationEntityMemory": ConversationEntityMemory,
    # "ConversationSummaryMemory": ConversationSummaryMemory,
    # "ChatMessageHistory": ChatMessageHistory,
    # "ConversationStringBufferMemory": ConversationStringBufferMemory,
    # "ReadOnlySharedMemory": ReadOnlySharedMemory,
}


## Chain
# from langchain.chains.loading import type_to_loader_dict
# from langchain.chains.conversation.base import ConversationChain

# chain_type_to_cls_dict = type_to_loader_dict
# chain_type_to_cls_dict["conversation_chain"] = ConversationChain

from typing import Optional
from langchain.agents.load_tools import (
    _BASE_TOOLS,
    _EXTRA_LLM_TOOLS,
    _EXTRA_OPTIONAL_TOOLS,
    _LLM_TOOLS,
)
from langflow.doc_loaders import csv_loader


def get_tools_dict(name: Optional[str] = None):
    """Get the tools dictionary."""
    tools = {
        **_BASE_TOOLS,
        **_LLM_TOOLS,
        **{k: v[0] for k, v in _EXTRA_LLM_TOOLS.items()},
        **{k: v[0] for k, v in _EXTRA_OPTIONAL_TOOLS.items()},
    }
    return tools[name] if name else tools


docloaders = {
    "csv_loader": csv_loader.get_csv_loader,
}
