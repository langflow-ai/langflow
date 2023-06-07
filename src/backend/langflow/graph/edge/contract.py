# Path: src/backend/langflow/graph/edge/contract.py
from typing import TYPE_CHECKING
from langflow.graph.edge.base import Edge

if TYPE_CHECKING:
    from langflow.graph.vertex.base import Vertex


class ContractEdge(Edge):
    def __init__(self, source: "Vertex", target: "Vertex", raw_edge: dict):
        super().__init__(source, target, raw_edge)
        self.is_fulfilled = False  # Whether the contract has been fulfilled.
        self.result = None
        # a variable to identify if this edge connects
        # two runnable(or root) vertices which
        # are identiffied by both of them having
        # the can_be_root attribute set to True
        self.is_runnable = self.source.can_be_root and self.target.can_be_root

    def fulfill(self):
        if not self.source._built:
            self.source.build()

        self.result = self.source._built_object
        # TODO: Implement runnable vertices
        self.target.params[self._target_param_key] = (
            self.result if self.is_runnable else self.result.get_result()
        )
        self.is_fulfilled = True

    def get_result(self):
        # Fulfill the contract if it has not been fulfilled.
        if not self.is_fulfilled:
            self.fulfill()
        return self.result
