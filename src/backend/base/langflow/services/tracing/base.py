from abc import ABC, abstractmethod
from typing import Any, Dict
from uuid import UUID


class BaseTracer(ABC):
    @abstractmethod
    def __init__(self, trace_name: str, trace_type: str, project_name: str, trace_id: UUID):
        raise NotImplementedError

    @abstractmethod
    def ready(self):
        raise NotImplementedError

    @abstractmethod
    def add_trace(
        self, trace_name: str, trace_type: str, inputs: Dict[str, Any], metadata: Dict[str, Any] | None = None
    ):
        raise NotImplementedError

    @abstractmethod
    def end_trace(self, trace_name: str, outputs: Dict[str, Any] | None = None, error: str | None = None):
        raise NotImplementedError

    @abstractmethod
    def end(
        self,
        inputs: dict[str, Any],
        outputs: Dict[str, Any],
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        raise NotImplementedError
