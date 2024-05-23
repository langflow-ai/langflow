from typing import TYPE_CHECKING, Any, List, Optional

from loguru import logger
from pydantic import BaseModel, Field

from langflow.schema.schema import INPUT_FIELD_NAME
from langflow.services.monitor.utils import log_message

if TYPE_CHECKING:
    from langflow.graph.vertex.base import Vertex


class SourceHandle(BaseModel):
    baseClasses: List[str] = Field(..., description="List of base classes for the source handle.")
    dataType: str = Field(..., description="Data type for the source handle.")
    id: str = Field(..., description="Unique identifier for the source handle.")


class TargetHandle(BaseModel):
    fieldName: str = Field(..., description="Field name for the target handle.")
    id: str = Field(..., description="Unique identifier for the target handle.")
    inputTypes: Optional[List[str]] = Field(None, description="List of input types for the target handle.")
    type: str = Field(..., description="Type of the target handle.")


class Edge:
    def __init__(self, source: "Vertex", target: "Vertex", edge: dict):
        self.source_id: str = source.id if source else ""
        self.target_id: str = target.id if target else ""
        if data := edge.get("data", {}):
            self._source_handle = data.get("sourceHandle", {})
            self._target_handle = data.get("targetHandle", {})
            self.source_handle: SourceHandle = SourceHandle(**self._source_handle)
            self.target_handle: TargetHandle = TargetHandle(**self._target_handle)
            self.target_param = self.target_handle.fieldName
            # validate handles
            self.validate_handles(source, target)
        else:
            # Logging here because this is a breaking change
            logger.error("Edge data is empty")
            self._source_handle = edge.get("sourceHandle", "")
            self._target_handle = edge.get("targetHandle", "")
            # 'BaseLoader;BaseOutputParser|documents|PromptTemplate-zmTlD'
            # target_param is documents
            self.target_param = self._target_handle.split("|")[1]
        # Validate in __init__ to fail fast
        self.validate_edge(source, target)

    def validate_handles(self, source, target) -> None:
        if self.target_handle.inputTypes is None:
            self.valid_handles = self.target_handle.type in self.source_handle.baseClasses
        else:
            self.valid_handles = (
                any(baseClass in self.target_handle.inputTypes for baseClass in self.source_handle.baseClasses)
                or self.target_handle.type in self.source_handle.baseClasses
            )
        if not self.valid_handles:
            logger.debug(self.source_handle)
            logger.debug(self.target_handle)
            raise ValueError(f"Edge between {source.vertex_type} and {target.vertex_type} " f"has invalid handles")

    def __setstate__(self, state):
        self.source_id = state["source_id"]
        self.target_id = state["target_id"]
        self.target_param = state["target_param"]
        self.source_handle = state.get("source_handle")
        self.target_handle = state.get("target_handle")

    def validate_edge(self, source, target) -> None:
        # Validate that the outputs of the source node are valid inputs
        # for the target node
        self.source_types = source.output
        self.target_reqs = target.required_inputs + target.optional_inputs
        # Both lists contain strings and sometimes a string contains the value we are
        # looking for e.g. comgin_out=["Chain"] and target_reqs=["LLMChain"]
        # so we need to check if any of the strings in source_types is in target_reqs
        self.valid = any(output in target_req for output in self.source_types for target_req in self.target_reqs)
        # Get what type of input the target node is expecting

        self.matched_type = next(
            (output for output in self.source_types if output in self.target_reqs),
            None,
        )
        no_matched_type = self.matched_type is None
        if no_matched_type:
            logger.debug(self.source_types)
            logger.debug(self.target_reqs)
            raise ValueError(f"Edge between {source.vertex_type} and {target.vertex_type} " f"has no matched type")

    def __repr__(self) -> str:
        return (
            f"Edge(source={self.source_id}, target={self.target_id}, target_param={self.target_param}"
            f", matched_type={self.matched_type})"
        )

    def __hash__(self) -> int:
        return hash(self.__repr__())

    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, Edge):
            return False
        return (
            self._source_handle == __o._source_handle
            and self._target_handle == __o._target_handle
            and self.target_param == __o.target_param
        )


class ContractEdge(Edge):
    def __init__(self, source: "Vertex", target: "Vertex", raw_edge: dict):
        super().__init__(source, target, raw_edge)
        self.is_fulfilled = False  # Whether the contract has been fulfilled.
        self.result: Any = None

    async def honor(self, source: "Vertex", target: "Vertex") -> None:
        """
        Fulfills the contract by setting the result of the source vertex to the target vertex's parameter.
        If the edge is runnable, the source vertex is run with the message text and the target vertex's
        root_field param is set to the
        result. If the edge is not runnable, the target vertex's parameter is set to the result.
        :param message: The message object to be processed if the edge is runnable.
        """
        if self.is_fulfilled:
            return

        if not source._built:
            # The system should be read-only, so we should not be building vertices
            # that are not already built.
            raise ValueError(f"Source vertex {source.id} is not built.")

        if self.matched_type == "Text":
            self.result = source._built_result
        else:
            self.result = source._built_object

        target.params[self.target_param] = self.result
        self.is_fulfilled = True

    async def get_result_from_source(self, source: "Vertex", target: "Vertex"):
        # Fulfill the contract if it has not been fulfilled.
        if not self.is_fulfilled:
            await self.honor(source, target)

        # If the target vertex is a power component we log messages
        if target.vertex_type == "ChatOutput" and (
            isinstance(target.params.get(INPUT_FIELD_NAME), str)
            or isinstance(target.params.get(INPUT_FIELD_NAME), dict)
        ):
            if target.params.get("message") == "":
                return self.result
            await log_message(
                sender=target.params.get("sender", ""),
                sender_name=target.params.get("sender_name", ""),
                message=target.params.get(INPUT_FIELD_NAME, {}),
                session_id=target.params.get("session_id", ""),
                artifacts=target.artifacts,
                flow_id=target.graph.flow_id,
            )
        return self.result

    def __repr__(self) -> str:
        return f"{self.source_id} -[{self.target_param}]-> {self.target_id}"
