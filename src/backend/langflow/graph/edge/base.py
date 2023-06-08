from langflow.utils.logger import logger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langflow.graph.vertex.base import Vertex


class Edge:
    def __init__(self, source: "Vertex", target: "Vertex"):
        self.source: "Vertex" = source
        self.target: "Vertex" = target
        self.validate_edge()

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
            (
                output
                for output in self.source_types
                for target_req in self.target_reqs
                if output in target_req
            ),
            None,
        )
        no_matched_type = self.matched_type is None
        if no_matched_type:
            logger.debug(self.source_types)
            logger.debug(self.target_reqs)
        if no_matched_type:
            raise ValueError(
                f"Edge between {self.source.vertex_type} and {self.target.vertex_type} "
                f"has no matched type"
            )

    def __repr__(self) -> str:
        return (
            f"Edge(source={self.source.id}, target={self.target.id}, valid={self.valid}"
            f", matched_type={self.matched_type})"
        )
