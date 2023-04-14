from typing import Dict, List, Type, Union

from langflow.graph.base import Edge, Node
from langflow.graph.nodes import (
    AgentNode,
    ChainNode,
    DocumentLoaderNode,
    EmbeddingNode,
    FileToolNode,
    LLMNode,
    MemoryNode,
    PromptNode,
    TextSplitterNode,
    ToolkitNode,
    ToolNode,
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
from langflow.interface.tools.constants import FILE_TOOLS
from langflow.interface.vector_store.base import vectorstore_creator
from langflow.interface.wrappers.base import wrapper_creator
from langflow.utils import payload


class Graph:
    def __init__(
        self,
        nodes: List[Dict[str, Union[str, Dict[str, Union[str, List[str]]]]]],
        edges: List[Dict[str, str]],
    ) -> None:
        self._nodes = nodes
        self._edges = edges
        self._build_graph()

    def _build_graph(self) -> None:
        self.nodes = self._build_nodes()
        self.edges = self._build_edges()
        for edge in self.edges:
            edge.source.add_edge(edge)
            edge.target.add_edge(edge)

        # This is a hack to make sure that the LLM node is sent to
        # the toolkit node
        llm_node = None
        for node in self.nodes:
            node._build_params()

            if isinstance(node, LLMNode):
                llm_node = node

        for node in self.nodes:
            if isinstance(node, ToolkitNode):
                node.params["llm"] = llm_node
        # remove invalid nodes
        self.nodes = [
            node
            for node in self.nodes
            if self._validate_node(node)
            or (len(self.nodes) == 1 and len(self.edges) == 0)
        ]

    def _validate_node(self, node: Node) -> bool:
        # All nodes that do not have edges are invalid
        return len(node.edges) > 0

    def get_node(self, node_id: str) -> Union[None, Node]:
        return next((node for node in self.nodes if node.id == node_id), None)

    def get_nodes_with_target(self, node: Node) -> List[Node]:
        connected_nodes: List[Node] = [
            edge.source for edge in self.edges if edge.target == node
        ]
        return connected_nodes

    def build(self) -> List[Node]:
        # Get root node
        root_node = payload.get_root_node(self)
        if root_node is None:
            raise ValueError("No root node found")
        return root_node.build()

    def get_node_neighbors(self, node: Node) -> Dict[Node, int]:
        neighbors: Dict[Node, int] = {}
        for edge in self.edges:
            if edge.source == node:
                neighbor = edge.target
                if neighbor not in neighbors:
                    neighbors[neighbor] = 0
                neighbors[neighbor] += 1
            elif edge.target == node:
                neighbor = edge.source
                if neighbor not in neighbors:
                    neighbors[neighbor] = 0
                neighbors[neighbor] += 1
        return neighbors

    def _build_edges(self) -> List[Edge]:
        # Edge takes two nodes as arguments, so we need to build the nodes first
        # and then build the edges
        # if we can't find a node, we raise an error

        edges: List[Edge] = []
        for edge in self._edges:
            source = self.get_node(edge["source"])
            target = self.get_node(edge["target"])
            if source is None:
                raise ValueError(f"Source node {edge['source']} not found")
            if target is None:
                raise ValueError(f"Target node {edge['target']} not found")
            edges.append(Edge(source, target))
        return edges

    def _get_node_class(self, node_type: str, node_lc_type: str) -> Type[Node]:
        node_type_map: Dict[str, Type[Node]] = {
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

        if node_type in FILE_TOOLS:
            return FileToolNode
        if node_type in node_type_map:
            return node_type_map[node_type]
        if node_lc_type in node_type_map:
            return node_type_map[node_lc_type]
        return Node

    def _build_nodes(self) -> List[Node]:
        nodes: List[Node] = []
        for node in self._nodes:
            node_data = node["data"]
            node_type: str = node_data["type"]  # type: ignore
            node_lc_type: str = node_data["node"]["template"]["_type"]  # type: ignore

            NodeClass = self._get_node_class(node_type, node_lc_type)
            nodes.append(NodeClass(node))

        return nodes

    def get_children_by_node_type(self, node: Node, node_type: str) -> List[Node]:
        children = []
        node_types = [node.data["type"]]
        if "node" in node.data:
            node_types += node.data["node"]["base_classes"]
        if node_type in node_types:
            children.append(node)
        return children
