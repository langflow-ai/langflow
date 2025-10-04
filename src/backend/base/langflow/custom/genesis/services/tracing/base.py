"""Base tracer class for Genesis Studio Backend."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from collections.abc import Sequence

    from langchain.callbacks.base import BaseCallbackHandler
    from langflow.graph.vertex.base import Vertex
    from langflow.services.tracing.schema import Log


class BaseTracer(ABC):
    """Abstract base class for tracers in Genesis Studio Backend."""

    trace_id: UUID

    @abstractmethod
    def __init__(
        self,
        trace_name: str,
        trace_type: str,
        project_name: str,
        trace_id: UUID,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """Initialize the tracer with required parameters."""
        raise NotImplementedError

    @property
    @abstractmethod
    def ready(self) -> bool:
        """Check if the tracer is ready for use."""

    @abstractmethod
    def add_trace(
        self,
        trace_id: str,
        trace_name: str,
        trace_type: str,
        inputs: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        vertex: Vertex | None = None,
    ) -> None:
        """Add a new trace/span."""

    @abstractmethod
    def end_trace(
        self,
        trace_id: str,
        trace_name: str,
        outputs: dict[str, Any] | None = None,
        error: Exception | None = None,
        logs: Sequence[Log | dict] = (),
    ) -> None:
        """End a trace/span."""

    @abstractmethod
    def end(
        self,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """End the entire flow trace."""

    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        """Get LangChain callback handler if available."""
        return None
