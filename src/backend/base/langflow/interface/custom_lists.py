import inspect
from typing import Any

from langchain import llms, memory, requests, text_splitter
from langchain_community import agent_toolkits, document_loaders, embeddings
from langchain_community.chat_models import AzureChatOpenAI, ChatAnthropic, ChatOpenAI, ChatVertexAI

from langflow.interface.agents.custom import CUSTOM_AGENTS
from langflow.interface.chains.custom import CUSTOM_CHAINS
from langflow.interface.importing.utils import import_class

# LLMs
llm_type_to_cls_dict = {}

for k, v in llms.get_type_to_cls_dict().items():
    try:
        llm_type_to_cls_dict[k] = v()
    except Exception:
        pass
llm_type_to_cls_dict["anthropic-chat"] = ChatAnthropic  # type: ignore
llm_type_to_cls_dict["azure-chat"] = AzureChatOpenAI  # type: ignore
llm_type_to_cls_dict["openai-chat"] = ChatOpenAI  # type: ignore
llm_type_to_cls_dict["vertexai-chat"] = ChatVertexAI  # type: ignore


# Toolkits
toolkit_type_to_loader_dict: dict[str, Any] = {
    toolkit_name: import_class(f"langchain_community.agent_toolkits.{toolkit_name}")
    # if toolkit_name is lower case it is a loader
    for toolkit_name in agent_toolkits.__all__
    if toolkit_name.islower()
}

toolkit_type_to_cls_dict: dict[str, Any] = {
    toolkit_name: import_class(f"langchain_community.agent_toolkits.{toolkit_name}")
    # if toolkit_name is not lower case it is a class
    for toolkit_name in agent_toolkits.__all__
    if not toolkit_name.islower()
}

# Memories
memory_type_to_cls_dict: dict[str, Any] = {
    memory_name: import_class(f"langchain.memory.{memory_name}") for memory_name in memory.__all__
}

# Wrappers
wrapper_type_to_cls_dict: dict[str, Any] = {wrapper.__name__: wrapper for wrapper in [requests.RequestsWrapper]}

# Embeddings
embedding_type_to_cls_dict: dict[str, Any] = {
    embedding_name: import_class(f"langchain_community.embeddings.{embedding_name}")
    for embedding_name in embeddings.__all__
}


# Document Loaders
documentloaders_type_to_cls_dict: dict[str, Any] = {
    documentloader_name: import_class(f"langchain_community.document_loaders.{documentloader_name}")
    for documentloader_name in document_loaders.__all__
}

# Text Splitters
textsplitter_type_to_cls_dict: dict[str, Any] = dict(inspect.getmembers(text_splitter, inspect.isclass))

# merge CUSTOM_AGENTS and CUSTOM_CHAINS
CUSTOM_NODES = {**CUSTOM_AGENTS, **CUSTOM_CHAINS}  # type: ignore
