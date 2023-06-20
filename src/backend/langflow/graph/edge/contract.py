# Path: src/backend/langflow/graph/edge/contract.py
from typing import TYPE_CHECKING, Optional
from langflow.graph.edge.base import Edge
from langflow.graph.edge.run import get_result_and_steps
from langflow.graph.schema import GraphInput


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

    async def fulfill(self, message: Optional[GraphInput] = None, **kwargs):
        """
        Fulfills the contract by setting the result of the source vertex to the target vertex's parameter.
        If the edge is runnable, the source vertex is run with the message text and the target vertex's
        root_field param is set to the
        result. If the edge is not runnable, the target vertex's parameter is set to the result.
        :param message: The message object to be processed if the edge is runnable.
        """

        if not self.source._built:
            await self.source.build()

        self.result = self.source._built_object
        if self.is_runnable and message is not None:
            await self.process_runnable(message, **kwargs)
        else:
            self.target.params[self._target_param_key] = self.result
        self.is_fulfilled = True

    async def process_runnable(self, message: GraphInput):
        """
        Processes a runnable edge by running the source vertex with the message text and setting the target vertex's
        root_field param to the result. If the source vertex has a root_field param set, the message text is set to that
        value before running the source vertex.
        :param message: The message object to be processed.
        """

        # ------------------ RUNNABLE EDGE ------------------
        # First we need to check if the source vertex as a root_field param set
        # If it does, we need to set the message text to the value of that param
        # before running the source vertex
        if self.source.params.get("root_field"):
            message.add_result_pair(result=self.source.params["root_field"], extra=None)

        await self.run_source(message)
        # Then we need to check if the target vertex has a root_field param set
        # If it does not, we need to set the target vertex's root_field param
        # of that param
        if not self.target.params.get("root_field"):
            self.target.params["root_field"] = message.result_pairs[-1].result
        # ------------------ RUNNABLE EDGE ------------------

    async def run_source(self, message: GraphInput, **kwargs):
        """
        Runs the source vertex with the message text and sets the message text to the result.
        :param message: The message object to be processed.

        """
        from langflow.graph.vertex.types import LangChainVertex

        # Run the source vertex with the message text
        runnable_object = self.source.build()
        # Here is where it gets tricky.
        # If self.source is a LangChainTypeVertex, we need to pass that to a specific function
        last_result_pair = message.get_last_result_pair()
        if isinstance(self.source, LangChainVertex):
            result, extra = await get_result_and_steps(
                runnable_object, message=last_result_pair.result or "", **kwargs
            )
        else:
            result = runnable_object(last_result_pair.result, **kwargs)
            extra = None
        # Setting this will change the message text
        # outside of this function
        message.add_result_pair(result=result, extra=extra)

    async def get_result(self):
        # Fulfill the contract if it has not been fulfilled.
        if not self.is_fulfilled:
            await self.fulfill()
        return self.result
