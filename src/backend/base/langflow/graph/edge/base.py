from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from loguru import logger

from langflow.graph.edge.schema import EdgeData, SourceHandle, TargetHandle, TargetHandleDict
from langflow.schema.schema import INPUT_FIELD_NAME

if TYPE_CHECKING:
    from langflow.graph.vertex.base import Vertex


class Edge:
    def __init__(self, source: Vertex, target: Vertex, edge: EdgeData):
        self.source_id: str = source.id if source else ""
        self.target_id: str = target.id if target else ""
        self.valid_handles: bool = False
        self.target_param: str | None = None
        self._target_handle: TargetHandleDict | str | None = None
        self._data = edge.copy()
        self.is_cycle = False
        if data := edge.get("data", {}):
            self._source_handle = data.get("sourceHandle", {})
            self._target_handle = cast(TargetHandleDict, data.get("targetHandle", {}))
            self.source_handle: SourceHandle = SourceHandle(**self._source_handle)
            if isinstance(self._target_handle, dict):
                try:
                    self.target_handle: TargetHandle = TargetHandle(**self._target_handle)
                except Exception as e:
                    if "inputTypes" in self._target_handle and self._target_handle["inputTypes"] is None:
                        # Check if self._target_handle['fieldName']
                        if hasattr(target, "custom_component"):
                            display_name = getattr(target.custom_component, "display_name", "")
                            msg = (
                                f"Component {display_name} field '{self._target_handle['fieldName']}' "
                                "might not be a valid input."
                            )
                            raise ValueError(msg) from e
                        msg = (
                            f"Field '{self._target_handle['fieldName']}' on {target.display_name} "
                            "might not be a valid input."
                        )
                        raise ValueError(msg) from e
                    raise

            else:
                msg = "Target handle is not a dictionary"
                raise ValueError(msg)
            self.target_param = self.target_handle.field_name
            # validate handles
            self.validate_handles(source, target)
        else:
            # Logging here because this is a breaking change
            logger.error("Edge data is empty")
            self._source_handle = edge.get("sourceHandle", "")  # type: ignore[assignment]
            self._target_handle = edge.get("targetHandle", "")  # type: ignore[assignment]
            # 'BaseLoader;BaseOutputParser|documents|PromptTemplate-zmTlD'
            # target_param is documents
            if isinstance(self._target_handle, str):
                self.target_param = self._target_handle.split("|")[1]
                self.source_handle = None
                self.target_handle = None
            else:
                msg = "Target handle is not a string"
                raise ValueError(msg)
        # Validate in __init__ to fail fast
        self.validate_edge(source, target)

    def to_data(self):
        return self._data

    def validate_handles(self, source, target) -> None:
        if isinstance(self._source_handle, str) or self.source_handle.base_classes:
            self._legacy_validate_handles(source, target)
        else:
            self._validate_handles(source, target)

    def _validate_handles(self, source, target) -> None:
        if self.target_handle.input_types is None:
            self.valid_handles = self.target_handle.type in self.source_handle.output_types

        elif self.source_handle.output_types is not None:
            self.valid_handles = (
                any(output_type in self.target_handle.input_types for output_type in self.source_handle.output_types)
                or self.target_handle.type in self.source_handle.output_types
            )

        if not self.valid_handles:
            logger.debug(self.source_handle)
            logger.debug(self.target_handle)
            msg = f"Edge between {source.display_name} and {target.display_name} has invalid handles"
            raise ValueError(msg)

    def _legacy_validate_handles(self, source, target) -> None:
        if self.target_handle.input_types is None:
            self.valid_handles = self.target_handle.type in self.source_handle.base_classes
        else:
            self.valid_handles = (
                any(baseClass in self.target_handle.input_types for baseClass in self.source_handle.base_classes)
                or self.target_handle.type in self.source_handle.base_classes
            )
        if not self.valid_handles:
            logger.debug(self.source_handle)
            logger.debug(self.target_handle)
            msg = f"Edge between {source.vertex_type} and {target.vertex_type} has invalid handles"
            raise ValueError(msg)

    def __setstate__(self, state):
        self.source_id = state["source_id"]
        self.target_id = state["target_id"]
        self.target_param = state["target_param"]
        self.source_handle = state.get("source_handle")
        self.target_handle = state.get("target_handle")
        self._source_handle = state.get("_source_handle")
        self._target_handle = state.get("_target_handle")
        self._data = state.get("_data")
        self.valid_handles = state.get("valid_handles")
        self.source_types = state.get("source_types")
        self.target_reqs = state.get("target_reqs")
        self.matched_type = state.get("matched_type")

    def validate_edge(self, source, target) -> None:
        # If the self.source_handle has base_classes, then we are using the legacy
        # way of defining the source and target handles
        if isinstance(self._source_handle, str) or self.source_handle.base_classes:
            self._legacy_validate_edge(source, target)
        else:
            self._validate_edge(source, target)

    def _validate_edge(self, source, target) -> None:
        # Validate that the outputs of the source node are valid inputs
        # for the target node
        # .outputs is a list of Output objects as dictionaries
        # meaning: check for "types" key in each dictionary
        self.source_types = [output for output in source.outputs if output["name"] == self.source_handle.name]
        self.target_reqs = target.required_inputs + target.optional_inputs
        # Both lists contain strings and sometimes a string contains the value we are
        # looking for e.g. comgin_out=["Chain"] and target_reqs=["LLMChain"]
        # so we need to check if any of the strings in source_types is in target_reqs
        self.valid = any(
            any(output_type in target_req for output_type in output["types"])
            for output in self.source_types
            for target_req in self.target_reqs
        )
        # Get what type of input the target node is expecting

        # Update the matched type to be the first found match
        self.matched_type = next(
            (
                output_type
                for output in self.source_types
                for output_type in output["types"]
                for target_req in self.target_reqs
                if output_type in target_req
            ),
            None,
        )
        no_matched_type = self.matched_type is None
        if no_matched_type:
            logger.debug(self.source_types)
            logger.debug(self.target_reqs)
            msg = f"Edge between {source.vertex_type} and {target.vertex_type} has no matched type."
            raise ValueError(msg)

    def _legacy_validate_edge(self, source, target) -> None:
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
            msg = f"Edge between {source.vertex_type} and {target.vertex_type} has no matched type"
            raise ValueError(msg)

    def __repr__(self) -> str:
        if (hasattr(self, "source_handle") and self.source_handle) and (
            hasattr(self, "target_handle") and self.target_handle
        ):
            return f"{self.source_id} -[{self.source_handle.name}->{self.target_handle.field_name}]-> {self.target_id}"
        return f"{self.source_id} -[{self.target_param}]-> {self.target_id}"

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

    def __str__(self) -> str:
        return self.__repr__()


class CycleEdge(Edge):
    def __init__(self, source: Vertex, target: Vertex, raw_edge: EdgeData):
        super().__init__(source, target, raw_edge)
        self.is_fulfilled = False  # Whether the contract has been fulfilled.
        self.result: Any = None
        self.is_cycle = True
        source.has_cycle_edges = True
        target.has_cycle_edges = True

    async def honor(self, source: Vertex, target: Vertex) -> None:
        """Fulfills the contract by setting the result of the source vertex to the target vertex's parameter.

        If the edge is runnable, the source vertex is run with the message text and the target vertex's
        root_field param is set to the
        result. If the edge is not runnable, the target vertex's parameter is set to the result.
        :param message: The message object to be processed if the edge is runnable.
        """
        if self.is_fulfilled:
            return

        if not source.built:
            # The system should be read-only, so we should not be building vertices
            # that are not already built.
            msg = f"Source vertex {source.id} is not built."
            raise ValueError(msg)

        if self.matched_type == "Text":
            self.result = source.built_result
        else:
            self.result = source.built_object

        target.params[self.target_param] = self.result
        self.is_fulfilled = True

    async def get_result_from_source(self, source: Vertex, target: Vertex):
        # Fulfill the contract if it has not been fulfilled.
        if not self.is_fulfilled:
            await self.honor(source, target)

        # If the target vertex is a power component we log messages
        if (
            target.vertex_type == "ChatOutput"
            and isinstance(target.params.get(INPUT_FIELD_NAME), str | dict)
            and target.params.get("message") == ""
        ):
            return self.result
        return self.result

    def __repr__(self) -> str:
        str_repr = super().__repr__()
        # Add a symbol to show this is a cycle edge
        return f"{str_repr} 🔄"
