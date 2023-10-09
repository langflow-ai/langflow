from loguru import logger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langflow.graph.vertex.base import Vertex


class Edge:
    def __init__(self, source: "Vertex", target: "Vertex", edge: dict):
        self.source: "Vertex" = source
        self.target: "Vertex" = target
        self.source_handle = edge.get("sourceHandle", "")
        self.target_handle = edge.get("targetHandle", "")
        # 'BaseLoader;BaseOutputParser|documents|PromptTemplate-zmTlD'
        # target_param is documents
        self.target_param = self.target_handle.split("|")[1]

        self.validate_edge()

    def __setstate__(self, state):
        self.source = state["source"]
        self.target = state["target"]
        self.target_param = state["target_param"]
        self.source_handle = state["source_handle"]
        self.target_handle = state["target_handle"]

    def reset(self) -> None:
        self.source._build_params()
        self.target._build_params()

    def validate_edge(self) -> None:
        # Validate that the outputs of the source node are valid inputs
        # for the target node
        self.source_types = self.source.output
        self.target_reqs = self.target.required_inputs + self.target.optional_inputs
        # Both lists contain strings and sometimes a string contains the value we are
        # looking for e.g. comgin_out=["Chain"] and target_reqs=["LLMChain"]
        # so we need to check if any of the strings in source_types is in target_reqs
        self.valid = any(
            output in target_req
            for output in self.source_types
            for target_req in self.target_reqs
        )
        # Get what type of input the target node is expecting

        self.matched_type = next(
            (output for output in self.source_types if output in self.target_reqs),
            None,
        )
        no_matched_type = self.matched_type is None
        if no_matched_type:
            logger.debug(self.source_types)
            logger.debug(self.target_reqs)
            raise ValueError(
                f"Edge between {self.source.vertex_type} and {self.target.vertex_type} "
                f"has no matched type"
            )

    def __repr__(self) -> str:
        return (
            f"Edge(source={self.source.id}, target={self.target.id}, target_param={self.target_param}"
            f", matched_type={self.matched_type})"
        )

    def __hash__(self) -> int:
        return hash(self.__repr__())

    def __eq__(self, __value: object) -> bool:
        return (
            self.__repr__() == __value.__repr__()
            if isinstance(__value, Edge)
            else False
        )


class ContractEdge(Edge):
    def __init__(self, source: "Vertex", target: "Vertex", raw_edge: dict):
        super().__init__(source, target, raw_edge)
        self.is_fulfilled = False  # Whether the contract has been fulfilled.
        self.result = None

    def fulfill(self, force: bool = False) -> None:
        """
        Fulfills the contract by setting the result of the source vertex to the target vertex's parameter.
        If the edge is runnable, the source vertex is run with the message text and the target vertex's
        root_field param is set to the
        result. If the edge is not runnable, the target vertex's parameter is set to the result.
        :param message: The message object to be processed if the edge is runnable.
        """
        if self.is_fulfilled:
            return

        if not self.source._built:
            self.source.build(force=force)

        if self.matched_type == "Text":
            self.result = self.source._built_result
        else:
            self.result = self.source._built_object

        self.target.params[self.target_param] = self.result
        self.is_fulfilled = True

    def get_result(self, force: bool = False):
        # Fulfill the contract if it has not been fulfilled.
        if not self.is_fulfilled:
            self.fulfill(force)
        return self.result

    def __repr__(self) -> str:
        return f"{self.source.vertex_type} -[{self.target_param}]-> {self.target.vertex_type}"
