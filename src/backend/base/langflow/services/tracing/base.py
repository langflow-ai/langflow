from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseTrace(ABC):

    @abstractmethod
    def ready(self):
        raise NotImplementedError

    @abstractmethod
    def setup_langsmith(self):
        raise NotImplementedError

    @abstractmethod
    def add_trace(self, trace_name: str, trace_type: str, inputs: Dict[str, Any], metadata: Dict[str, Any] = None):
        raise NotImplementedError

    @abstractmethod
    def _convert_to_langchain_types(self, io_dict: Dict[str, Any]):
        raise NotImplementedError

    @abstractmethod
    def _convert_to_langchain_type(self, value):
        raise NotImplementedError

    @abstractmethod
    def end_trace(self, trace_name: str, outputs: Dict[str, Any] = None, error: str = None):
        raise NotImplementedError

    @abstractmethod
    def end(self, outputs: Dict[str, Any], error: str | None = None):
        raise NotImplementedError
