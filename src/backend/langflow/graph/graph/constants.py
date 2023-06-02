from langflow.graph.node.base import Node
from langflow.graph.node.types import (
    AgentNode,
    ChainNode,
    DocumentLoaderNode,
    EmbeddingNode,
    LLMNode,
    MemoryNode,
    PromptNode,
    TextSplitterNode,
    ToolNode,
    ToolkitNode,
    VectorStoreNode,
    WrapperNode,
)
from langflow.interface.agents.base import agent_creator
from langflow.interface.chains.base import chain_creator
from langflow.interface.document_loaders.base import documentloader_creator
from langflow.interface.embeddings.base import embedding_creator
from langflow.interface.llms.base import llm_creator
from langflow.interface.memories.base import memory_creator
from langflow.interface.prompts.base import prompt_creator
from langflow.interface.text_splitters.base import textsplitter_creator
from langflow.interface.toolkits.base import toolkits_creator
from langflow.interface.tools.base import tool_creator
from langflow.interface.vector_store.base import vectorstore_creator
from langflow.interface.wrappers.base import wrapper_creator


from typing import Dict, Type


DIRECT_TYPES = ["str", "bool", "code", "int", "float", "Any", "prompt"]


NODE_TYPE_MAP: Dict[str, Type[Node]] = {
    **{t: PromptNode for t in prompt_creator.to_list()},
    **{t: AgentNode for t in agent_creator.to_list()},
    **{t: ChainNode for t in chain_creator.to_list()},
    **{t: ToolNode for t in tool_creator.to_list()},
    **{t: ToolkitNode for t in toolkits_creator.to_list()},
    **{t: WrapperNode for t in wrapper_creator.to_list()},
    **{t: LLMNode for t in llm_creator.to_list()},
    **{t: MemoryNode for t in memory_creator.to_list()},
    **{t: EmbeddingNode for t in embedding_creator.to_list()},
    **{t: VectorStoreNode for t in vectorstore_creator.to_list()},
    **{t: DocumentLoaderNode for t in documentloader_creator.to_list()},
    **{t: TextSplitterNode for t in textsplitter_creator.to_list()},
}
