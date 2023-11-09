from loguru import logger
from typing import TYPE_CHECKING
from pydantic import BaseModel, Field
from typing import List, Optional

from langflow.services.getters import get_monitor_service

if TYPE_CHECKING:
    from langflow.graph.vertex.base import Vertex


class SourceHandle(BaseModel):
    baseClasses: List[str] = Field(
        ..., description="List of base classes for the source handle."
    )
    dataType: str = Field(..., description="Data type for the source handle.")
    id: str = Field(..., description="Unique identifier for the source handle.")


class TargetHandle(BaseModel):
    fieldName: str = Field(..., description="Field name for the target handle.")
    id: str = Field(..., description="Unique identifier for the target handle.")
    inputTypes: Optional[List[str]] = Field(
        None, description="List of input types for the target handle."
    )
    type: str = Field(..., description="Type of the target handle.")


class Edge:
    def __init__(self, source: "Vertex", target: "Vertex", edge: dict):
        self.source: "Vertex" = source
        self.target: "Vertex" = target
        if data := edge.get("data", {}):
            self._source_handle = data.get("sourceHandle", {})
            self._target_handle = data.get("targetHandle", {})
            self.source_handle: SourceHandle = SourceHandle(**self._source_handle)
            self.target_handle: TargetHandle = TargetHandle(**self._target_handle)
            self.target_param = self.target_handle.fieldName
            # validate handles
            self.validate_handles()
        else:
            # Logging here because this is a breaking change
            logger.error("Edge data is empty")
            self._source_handle = edge.get("sourceHandle", "")
            self._target_handle = edge.get("targetHandle", "")
            # 'BaseLoader;BaseOutputParser|documents|PromptTemplate-zmTlD'
            # target_param is documents
            self.target_param = self._target_handle.split("|")[1]
        # Validate in __init__ to fail fast
        self.validate_edge()

    def validate_handles(self) -> None:
        if self.target_handle.inputTypes is None:
            self.valid_handles = (
                self.target_handle.type in self.source_handle.baseClasses
            )
        else:
            self.valid_handles = (
                any(
                    baseClass in self.target_handle.inputTypes
                    for baseClass in self.source_handle.baseClasses
                )
                or self.target_handle.type in self.source_handle.baseClasses
            )
        if not self.valid_handles:
            logger.debug(self.source_handle)
            logger.debug(self.target_handle)
            raise ValueError(
                f"Edge between {self.source.vertex_type} and {self.target.vertex_type} "
                f"has invalid handles"
            )

    def __setstate__(self, state):
        self.source = state["source"]
        self.target = state["target"]
        self.target_param = state["target_param"]
        self.source_handle = state.get("source_handle")
        self.target_handle = state.get("target_handle")

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

    def honor(self) -> None:
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
            self.source.build()

        if self.matched_type == "Text":
            self.result = self.source._built_result
        else:
            self.result = self.source._built_object

        self.target.params[self.target_param] = self.result
        self.is_fulfilled = True

    def build_clean_params(self) -> None:
        """
        Cleans the parameters of the target vertex.
        """
        # Removes all keys that the values aren't python types like str, int, bool, etc.
        params = {
            key: value
            for key, value in self.target.params.items()
            if isinstance(value, (str, int, bool, float, list, dict))
        }
        # if it is a list we need to check if the contents are python types
        for key, value in params.items():
            if isinstance(value, list):
                params[key] = [
                    item
                    for item in value
                    if isinstance(item, (str, int, bool, float, list, dict))
                ]
        return params

    def get_result(self):
        # Fulfill the contract if it has not been fulfilled.
        if not self.is_fulfilled:
            self.honor()

        log_transaction(self, "success")
        # If the target vertex is a power component we log messages
        if self.target.is_power_component and self.target.vertex_type == "ChatOutput":
            log_message(
                sender_type=self.target.params.get("sender", ""),
                sender_name=self.target.params.get("sender_name", ""),
                message=self.target.params.get("message", ""),
                artifacts=self.target.artifacts,
            )
        return self.result

    def __repr__(self) -> str:
        return f"{self.source.vertex_type} -[{self.target_param}]-> {self.target.vertex_type}"


def log_transaction(edge: ContractEdge, status, error=None):
    try:
        monitor_service = get_monitor_service()
        clean_params = edge.build_clean_params()
        data = {
            "source": edge.source.vertex_type,
            "target": edge.target.vertex_type,
            "target_args": clean_params,
            "timestamp": monitor_service.get_timestamp(),
            "status": status,
            "error": error,
        }
        monitor_service.add_row(table_name="transactions", data=data)
    except Exception as e:
        logger.error(f"Error logging transaction: {e}")


def log_message(
    sender_type: str, sender_name: str, message: str, artifacts: Optional[dict] = None
):
    try:
        monitor_service = get_monitor_service()
        row = {
            "sender_type": sender_type,
            "sender_name": sender_name,
            "message": message,
            "artifacts": artifacts or {},
            "timestamp": monitor_service.get_timestamp(),
        }
        monitor_service.add_row(table_name="messages", data=row)
    except Exception as e:
        logger.error(f"Error logging message: {e}")
