import inspect
from typing import Any

from langchain import (
    chains,
    document_loaders,
    embeddings,
    llms,
    memory,
    requests,
    text_splitter,
)
from langchain.agents import agent_toolkits
from langchain.chat_models import AzureChatOpenAI, ChatOpenAI
from langchain.chat_models import ChatAnthropic

from langflow.interface.importing.utils import import_class

## LLMs
llm_type_to_cls_dict = llms.type_to_cls_dict
llm_type_to_cls_dict["anthropic-chat"] = ChatAnthropic  # type: ignore
llm_type_to_cls_dict["azure-chat"] = AzureChatOpenAI  # type: ignore
llm_type_to_cls_dict["openai-chat"] = ChatOpenAI  # type: ignore

## Chains
chain_type_to_cls_dict: dict[str, Any] = {
    chain_name: import_class(f"langchain.chains.{chain_name}")
    for chain_name in chains.__all__
}

## Toolkits
toolkit_type_to_loader_dict: dict[str, Any] = {
    toolkit_name: import_class(f"langchain.agents.agent_toolkits.{toolkit_name}")
    # if toolkit_name is lower case it is a loader
    for toolkit_name in agent_toolkits.__all__
    if toolkit_name.islower()
}

toolkit_type_to_cls_dict: dict[str, Any] = {
    toolkit_name: import_class(f"langchain.agents.agent_toolkits.{toolkit_name}")
    # if toolkit_name is not lower case it is a class
    for toolkit_name in agent_toolkits.__all__
    if not toolkit_name.islower()
}

## Memories
memory_type_to_cls_dict: dict[str, Any] = {
    memory_name: import_class(f"langchain.memory.{memory_name}")
    for memory_name in memory.__all__
}

## Wrappers
wrapper_type_to_cls_dict: dict[str, Any] = {
    wrapper.__name__: wrapper for wrapper in [requests.RequestsWrapper]
}

## Embeddings
embedding_type_to_cls_dict: dict[str, Any] = {
    embedding_name: import_class(f"langchain.embeddings.{embedding_name}")
    for embedding_name in embeddings.__all__
}


## Document Loaders
documentloaders_type_to_cls_dict: dict[str, Any] = {
    documentloader_name: import_class(
        f"langchain.document_loaders.{documentloader_name}"
    )
    for documentloader_name in document_loaders.__all__
}

## Text Splitters
textsplitter_type_to_cls_dict: dict[str, Any] = dict(
    inspect.getmembers(text_splitter, inspect.isclass)
)
