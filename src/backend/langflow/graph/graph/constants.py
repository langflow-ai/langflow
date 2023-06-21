from langflow.graph.vertex.base import Vertex
from langflow.graph.vertex.types import (
    AgentVertex,
    ChainVertex,
    DocumentLoaderVertex,
    EmbeddingVertex,
    LLMVertex,
    MemoryVertex,
    PromptVertex,
    TextSplitterVertex,
    ToolVertex,
    ToolkitVertex,
    VectorStoreVertex,
    WrapperVertex,
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


VERTEX_TYPE_MAP: Dict[str, Type[Vertex]] = {
    **{t: PromptVertex for t in prompt_creator.to_list()},
    **{t: AgentVertex for t in agent_creator.to_list()},
    **{t: ChainVertex for t in chain_creator.to_list()},
    **{t: ToolVertex for t in tool_creator.to_list()},
    **{t: ToolkitVertex for t in toolkits_creator.to_list()},
    **{t: WrapperVertex for t in wrapper_creator.to_list()},
    **{t: LLMVertex for t in llm_creator.to_list()},
    **{t: MemoryVertex for t in memory_creator.to_list()},
    **{t: EmbeddingVertex for t in embedding_creator.to_list()},
    **{t: VectorStoreVertex for t in vectorstore_creator.to_list()},
    **{t: DocumentLoaderVertex for t in documentloader_creator.to_list()},
    **{t: TextSplitterVertex for t in textsplitter_creator.to_list()},
}
