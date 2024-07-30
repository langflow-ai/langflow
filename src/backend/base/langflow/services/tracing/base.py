from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional
from uuid import UUID

from langflow.services.tracing.schema import Log

if TYPE_CHECKING:
    from langflow.graph.vertex.base import Vertex
    from langchain.callbacks.base import BaseCallbackHandler


class BaseTracer(ABC):
    @abstractmethod
    def __init__(self, trace_name: str, trace_type: str, project_name: str, trace_id: UUID):
        raise NotImplementedError

    @abstractmethod
    def ready(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def add_trace(
        self,
        trace_id: str,
        trace_name: str,
        trace_type: str,
        inputs: Dict[str, Any],
        metadata: Dict[str, Any] | None = None,
        vertex: Optional["Vertex"] = None,
    ):
        raise NotImplementedError

    @abstractmethod
    def end_trace(
        self,
        trace_id: str,
        trace_name: str,
        outputs: Dict[str, Any] | None = None,
        error: Exception | None = None,
        logs: list[Log | dict] = [],
    ):
        raise NotImplementedError

    @abstractmethod
    def end(
        self,
        inputs: dict[str, Any],
        outputs: Dict[str, Any],
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        raise NotImplementedError

    @abstractmethod
    def get_langchain_callback(self) -> Optional["BaseCallbackHandler"]:
        raise NotImplementedError
