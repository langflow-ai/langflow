from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any
from uuid import UUID

from langflow.services.tracing.schema import Log

if TYPE_CHECKING:
    from langchain.callbacks.base import BaseCallbackHandler

    from langflow.graph.vertex.base import Vertex


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
        inputs: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        vertex: Vertex | None = None,
    ):
        raise NotImplementedError

    @abstractmethod
    def end_trace(
        self,
        trace_id: str,
        trace_name: str,
        outputs: dict[str, Any] | None = None,
        error: Exception | None = None,
        logs: Sequence[Log | dict] = (),
    ):
        raise NotImplementedError

    @abstractmethod
    def end(
        self,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        raise NotImplementedError

    @abstractmethod
    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        raise NotImplementedError
